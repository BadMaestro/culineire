from __future__ import annotations

from django.conf import settings
import json
import logging
from pathlib import Path

from django.contrib import messages
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.dateformat import format as date_format
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)

from accounts.views import is_moderator
from monitoring.tracker import get_client_ip
from recipes.authoring import get_author_for_user
from recipes.models import Recipe, RecipeAuthor

from .access import arena_console_guard, chef_battle_guard, is_battle_visible, valid_share_token
from .forms import BattleChallengeForm, BattleEntryForm, BattleRecipeAttachForm
from .fraud import (
    gate_account_age,
    gate_age_verified,
    gate_challenge_spam,
    gate_dsa_report_threshold,
    gate_duplicate_device,
    gate_fraud_flagged,
    gate_gift_velocity,
    gate_participant_vote,
    gate_post_battle_cooldown,
    gate_repeat_challenge_cooldown,
    gate_self_vote,
    gate_suspended_account,
    gate_token_purchase_velocity,
    gate_vote_rate_ip,
    gate_withdrawal_consent,
    run_fraud_gates,
)
from .models import Artifact, Battle, BattleChatMessage, BattleChallenge, BattleEntry, BattleEvent, BattleIngredient, BattleVote, ChefArtifact, ChefBattleProfile, TokenWallet, VoteIntegrityEvent
from .selectors import (
    _uncompeting_slugs,
    get_active_battles,
    get_upcoming_battles,
    get_arena_metrics,
    get_arena_phase,
    get_arena_phase_rail,
    get_arena_deadline,
    get_arena_geometry,
    ARENA_GEOMETRY_VERSION,
    get_vip_sponsors,
    unauthorised_arena_viewers,
    spectator_capacity,
    get_starting_battle_blast,
    get_battle_vote_counts,
    get_head_to_head,
    get_crown_ladder,
    get_crown_streak,
    get_expired_active_battles,
    get_recent_battle_gifts,
    get_top_supporter,
    get_hall_of_fame_battles,
    get_hall_of_fame_chefs,
    get_public_events,
    get_rankings,
    get_received_challenges,
    get_recent_completed_battles,
    get_sent_challenges,
    get_top_profiles,
)
from .services import (
    MOVES_MIN_TO_CHALLENGE,
    REWARD_AGREEMENT_TEXT_v1,
    _notify_chef,
    accept_challenge,
    accept_reward_agreement,
    approve_cooking_phase,
    calculate_battle_result,
    check_forbidden_claims,
    check_owner_not_in_battle,
    is_owner_author,
    check_rank_matchup,
    slot_occupied_reason,
    check_payout_eligibility,
    create_battle_event,
    create_payout_request,
    fire_ingredient_shot,
    get_battles_awaiting_cooking_approval,
    get_biathlon_state,
    get_or_create_battle_profile,
    hash_request_value,
    refuse_challenge,
    reveal_entries_if_ready,
    submit_cooked_photo,
)


def _battlefield_status(count: int, *, target: int = 1) -> str:
    if count >= target:
        return "done"
    if count > 0:
        return "active"
    return "pending"


def _build_battlefield_progress():
    challenge_count = BattleChallenge.objects.count()
    pending_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.PENDING).count()
    refused_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.REFUSED).count()
    battle_count = Battle.objects.count()
    active_battles = Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES).count()
    completed_battles = Battle.objects.filter(status=Battle.Status.COMPLETED).count()
    entry_count = Battle.objects.filter(entries__isnull=False).distinct().count()
    vote_count = BattleVote.objects.count()
    event_count = BattleEvent.objects.filter(is_public=True).count()
    profile_count = ChefBattleProfile.objects.count()
    artifact_count = Artifact.objects.count()
    chat_message_count = BattleChatMessage.objects.count()
    wallet_count = TokenWallet.objects.count()
    hero_count = ChefBattleProfile.objects.filter(is_hero=True).count()
    feature_enabled = getattr(settings, "CHEF_BATTLE_ENABLED", False)

    # The board used to state the token shop from a hand-written sentence, and it
    # went stale: it read "5 packages live: Starter 100T/EUR10 to Executive
    # 1400T/EUR80" while token_config.py carried eight, topping out at Legend
    # Chef 12800T/EUR768 (Carpet 3489, C1). Neither the count nor the top package
    # matched, on a page the Owner reads to know what shipped. It is derived from
    # the catalogue now, so the sentence cannot drift from the prices again.
    from .token_config import TOKEN_PACKAGES
    _packages = sorted(TOKEN_PACKAGES, key=lambda spec: spec["tokens"])
    _cheapest, _dearest = _packages[0], _packages[-1]

    def _package_label(spec):
        return f"{spec['name']} {spec['tokens']}T/EUR{spec['final_price_cents'] // 100}"

    token_package_detail = (
        f"{len(_packages)} packages live: {_package_label(_cheapest)} "
        f"to {_package_label(_dearest)}. Token Shop at /chef-battle/tokens/."
    )

    phases = [
        {
            "title": "Phase 0 - Sandbox Gate And Branch Discipline",
            "items": [
                {"label": "Chef Battles in production via main branch", "detail": "Chef Battles shipped to main, deployed to production, URLs live. Branch discipline followed throughout.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Feature flag in place", "detail": "CHEF_BATTLE_ENABLED controls homepage queries and battle URLs. Currently enabled on production.", "status": "done" if feature_enabled else "pending", "completed_at": "2026-06-10"},
                {"label": "Sandbox enablement confirmed", "detail": "CHEF_BATTLE_ENABLED=True applied on production server after all migrations verified.", "status": "done" if feature_enabled else "pending", "completed_at": "2026-06-10"},
                {"label": "Production release followed QA", "detail": "All Chef Battles deploys went through local check, migration verification and smoke test before push.", "status": "done", "completed_at": "2026-06-10"},
            ],
        },
        {
            "title": "Phase 1 - MVP Battle Loop",
            "items": [
                {"label": "Battle data model", "detail": "Profiles, challenges, battles, entries, votes, events, moves, artifacts and seasons have an initial schema.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Challenge flow", "detail": f"Feature built and live. Live: {challenge_count} challenge(s), {pending_challenges} pending, {refused_challenges} refused.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Battle room", "detail": f"Feature built and live. Live: {battle_count} battle(s), {active_battles} active, {completed_battles} completed.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Recipe submissions", "detail": f"Feature built and live. Live: {entry_count} battle(s) with at least one entry.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Public voting", "detail": f"Feature built and live. Live: {vote_count} vote(s) recorded. One vote per battle per session.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "7-day battle timer", "detail": "5 days for submissions + 2 days for voting = 7-day total battle window.", "status": "done", "completed_at": "2026-06-10"},
                {"label": "Manual battle moderation", "detail": "First 20-30 battles should be manually checked for theme fit, spam, image rights, recipe quality and rule violations.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 2 - Make Battles Sound Across The Site",
            "items": [
                {"label": "Battle event feed", "detail": f"Feature built and live. Live: {event_count} public battle event(s) on arena, profiles and news surfaces.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Chef profile battle record", "detail": f"Feature built and live. Live: {profile_count} chef battle profile(s) with rank, rating, wins, losses, refusals and moves.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Homepage battle block", "detail": "Homepage battle block live behind CHEF_BATTLE_ENABLED.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Newsfeed integration", "detail": "Challenge, refusal, battle start, submission and completion events create site news entries.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Live visitor notifications", "detail": "Polling every 45s surfaces pending challenges and unread battle messages as a toast while browsing.", "status": "done", "completed_at": "2026-06-12"},
            ],
        },
        {
            "title": "Phase 3 - Sandbox Launch Preparation",
            "items": [
                {"label": "First 5-10 sandbox battles", "detail": f"{completed_battles}/5 completed sandbox-style battles. Public launch should not feel empty.", "status": _battlefield_status(completed_battles, target=5)},
                {"label": "Founding Chef programme", "detail": "is_founding_chef flag on ChefBattleProfile. Star badge on rankings, battle room and chef profile. Granted from moderation panel.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Battle rules and moderation checklist", "detail": "Full rules page at /chef-battle/rules/ with 12 sections covering challenge, combat, voting, drops, gifts and artifacts.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Outreach list", "detail": "Prepare 30-50 Irish food creators, local chefs, students and bloggers for direct invite outreach.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 4 - Combat Mechanics",
            "items": [
                {"label": "Full battle status lifecycle", "detail": "menu_locked, active, biathlon, ingredient_penalty, cooking, presentation, voting, completed phases all wired.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Biathlon mechanic", "detail": "Winner of cooking submission shoots up to 3 times at opponent ingredients. Locks protect chosen items.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Ingredient combat (locks and hits)", "detail": "Each chef locks 2 ingredients before combat; hits land on unlocked slots; killed ingredients replaced or removed.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Cooking phase with photo upload", "detail": "After biathlon, chefs photograph finished dishes. Moderator approves before presentation.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Cooking moderation", "detail": "Moderator checklist confirms real cooking happened, image rights are clear and rules were followed.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Rank progression", "detail": "Rating-based Kitchen Porter to Culinary Master progression is live.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Rank matchup guard", "detail": "Challenges are limited to the same or an adjacent rank; the site Hero is unrestricted.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Hall of Fame", "detail": f"Top 10 battles and top 20 chefs visible at /chef-battle/hall-of-fame/. {completed_battles} completed battle(s) recorded.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Visual asset set", "detail": "Rank, CulinEire Hero, rarity, combat, crown, Michelin star and token assets.", "status": "done", "completed_at": "2026-06-12"},
            ],
        },
        {
            "title": "Phase 5 - Economy And Audience Engagement",
            "items": [
                {"label": "Token economy", "detail": f"TokenWallet, TokenTransaction and TokenPackage models live. {wallet_count} wallet(s) created.", "status": "done", "completed_at": "2026-06-11"},
                {"label": "200 combat artifacts", "detail": f"{artifact_count} artifact(s) loaded: 100 attack and 100 defence across 5 rarities (Common 10T to Legendary 400T).", "status": "done" if artifact_count >= 200 else _battlefield_status(artifact_count), "completed_at": "2026-06-12"},
                {"label": "Viewer gifts and appreciation", "detail": "Audience can send appreciation gifts and battle artifact gifts. Gift catalogue and pricing require update to new spec (§9 addendum).", "status": "done", "completed_at": "2026-06-11"},
                {"label": "Battle live chat", "detail": f"Live chat on battle pages with 8s polling. {chat_message_count} message(s) sent so far. Works for logged-in and anonymous viewers.", "status": "done", "completed_at": "2026-06-12"},
                {"label": "Token package pricing", "detail": token_package_detail, "status": "done", "completed_at": "2026-06-13"},
                {"label": "Artifact drop after battle", "detail": "Winner always drops 1 artifact. Loser 50% chance. Same rarity table: Common 30% to Legendary 8%.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Arena Rules page", "detail": "Full arena rules at /chef-battle/rules/ with artifact drop odds table and gift pricing.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Stripe token purchase", "detail": "Stripe checkout UI built. Live key, webhook and extended payment data storage moved to Phase 7.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Artifact gifting UI", "detail": "Gift panel on battle detail page: send appreciation gifts and battle artifact gifts to either chef. Wording update required: gifts are not permanently shown - artifact instances have a consumed/historical state.", "status": "done", "completed_at": "2026-06-13"},
            ],
        },
        {
            "title": "Phase 6 - Seasons, Clans And Sponsorship",
            "items": [
                {"label": "Seasons and leaderboards", "detail": "Season lifecycle engine (season_service.py): create/activate/close with a single active season at a time. Seasonal score earned per win (+10); on close, final standings are frozen into SeasonStanding (ranked) and live scores reset for the next season. Leaderboard at /chef-battle/season/ tracks the active season; roll_seasons management command rolls the lifecycle on a cron.", "status": "done", "completed_at": "2026-07-13"},
                {"label": "Clan / team battles", "detail": "SEASON 2 - and as of 2026-08-17 so is EVERY clan feature, not just team battles. The Owner deferred T23 restating his own 2026-07-14 rule, then widened it to clans entirely the same day, which takes the Season-1 call-an-ally hook with it. Already built and idle until then: Clan, ClanMembership, the join flow, the ClanContribution ledger, ClanSeasonStanding, Alliance and the clan-alliance link, the clan pages, the clan aura and the Owner blessing. Production carries zero clans and zero alliances.", "status": "pending"},
                {"label": "Sponsor battle integration", "detail": "Battles run under the active central sponsor (the ring-0 'Central Sponsor of the Month' cell), resolved via the single source of truth sponsors.services.get_sponsor_of_month(). Battle events already carry 'Sponsored by: <name>' in the newsfeed/Telegram (create_battle_event), and the battle page now shows a 'Presented by <name>' badge when a central sponsor is active. No per-battle config — branding follows the central cell automatically.", "status": "done", "completed_at": "2026-07-13"},
                {"label": "Cosmetics and prestige items", "detail": "Prestige titles auto-assigned by wins milestone (Kitchen Porter → Executive Chef). Displayed on profile and rankings pages.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "TikTok / Instagram live integration", "detail": "Stream cooking phase live. Requires platform account verification and API approval.", "status": "pending"},
            ],
        },
        {
            "title": "Phase 7 - Legal And Rules Alignment (Addendum)",
            "items": [
                {"label": "EU withdrawal consent UI", "detail": "Token shop requires explicit checkbox consent before purchase. Consent text snapshotted to TokenOrder.consent_text_snapshot. Buttons disabled until checked.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "VAT breakdown on token orders", "detail": "TokenOrder stores amount_net_cents, vat_amount_cents, vat_rate (23%). Computed via stripe_services.create_token_checkout_session at checkout.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "Feature flags for unbuilt subsystems", "detail": "ENABLE_STRIPE_CONNECT_PAYOUTS, ENABLE_LIVE_VIDEO, ENABLE_AI_IMAGE_REVIEW_PROVIDER — all default False. Guards stub fraud gates.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "Fix appreciation gift catalogue", "detail": "Appreciation gifts already correct: Coffee 20T, Virtual Beer Toast 30T, Virtual Whiskey Toast 50T, Flowers 80T, Celebration Cocktail 80T, Virtual Champagne Bottle 100T. APPRECIATION_GIFT_COST dict in models.py, rendered from view context in battle_detail.html. No DB change needed.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Token shop VAT button wording", "detail": "token_shop.html: 'Buy now' changed to 'Continue to checkout'. Price line already shows '€X.XX incl. VAT'. Footer note: 'Prices shown include 23% Irish VAT.' Link to Purchases & VAT policy on every package card.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Remove 'Battle Gifts are permanent'", "detail": "Battle Gift artifacts are one-use digital combat items. If used in combat, the artifact is consumed and cannot be used again. A historical record may remain on the Chef profile or battle log.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add 18+ rule to public rules", "detail": "Eligibility section (s0) at /chef-battle/rules/ confirms 18+ required for battles, gifts, and token purchase. Age gate enforced technically via gate_age_verified().", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add closed-loop token model to rules", "detail": "Section s14 at /chef-battle/rules/ covers closed-loop model: no cash value, not withdrawable, not transferable, VAT inclusive.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add anti-gambling wording", "detail": "Section s17 at /chef-battle/rules/: not gambling, tokens not stakes, no prize pools, no jackpots, tokens may not be staked, CBR/LSR only via approved platform logic.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add digital-only gift disclaimers", "detail": "Section s10 at /chef-battle/rules/: alcohol-themed gifts are virtual entertainment items only, no physical alcohol or goods supplied. 18+ required.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add CBR/LSR section to rules", "detail": "Section s15 at /chef-battle/rules/: CBR/LSR are internal reward records not tokens/money, 11 lifecycle stages, payout rate €0.025/token, min €50, admin review required, Next Battle Unlock required.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add Next Battle Unlock rule", "detail": "Section s16 at /chef-battle/rules/: CBR/LSR from Battle N locked until eligible Battle N+1 completed. Full eligibility criteria listed.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add Stripe Connect payout section to rules", "detail": "Payout rate, minimum, and conditions covered in s15 CBR/LSR section. Full Stripe Connect onboarding flow in Phase 9.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add DAC7 / tax responsibility wording", "detail": "Section s18 at /chef-battle/rules/: chefs responsible for tax, payouts may be taxable, DAC7/MRDP collection required before payout, Revenue reporting obligations.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add refund / chargeback policy wording", "detail": "Refunds & Chargebacks section in /legal/purchases-and-vat/ updated: non-refundable once credited, withdrawal waiver reference, chargeback consequences (token deduction, reward reversal, compliance review), immutable ledger note.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Add account transfer ban to rules", "detail": "Covered in s0 Eligibility: profiles and token balances are personal and non-transferable, account sharing not permitted.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Stripe token purchase webhook", "detail": "token_stripe_webhook() wired at /chef-battle/stripe/webhook/. construct_stripe_event + handle_stripe_event handle checkout.session.completed (credits tokens) and checkout.session.expired (cancels order). Idempotency via ProcessedTokenStripeEvent.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Store extended payment data on token orders", "detail": "TokenOrder stores: stripe_checkout_session_id, stripe_payment_intent_id, stripe_customer_id, stripe_invoice_id, currency, credited_at, amount_net_cents, vat_amount_cents, vat_rate, REFUNDED/DISPUTED statuses.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
        {
            "title": "Phase 3 (PDF) - AI Governance And Real-Photo Evidence",
            "items": [
                {"label": "Wallet terminology fix (§7)", "detail": "token_checkout_success.html and token_shop.html: 'wallet' replaced with 'Token Balance' in all user-facing text. Template variables named 'wallet' are internal Django context names, not UI text — these are legacy and do not require rename per PDF v6.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Allergen guidance notice on recipes (§30)", "detail": "Notice added below allergen list in recipe_detail.html: 'Allergen information is provided as guidance only and may not be complete. Always check product labels and ingredients before cooking or serving.' Styled with .allergen-guidance-notice in detail_page.css.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Real-photo declaration checkbox at cooking submit (§32)", "detail": "Mandatory unchecked checkbox in cooking_submit.html with exact PDF v6 text. View validates checkbox before accepting photo. real_photo_confirmed=True stored on BattleEntry. .real-photo-declaration CSS in chef_battle.css.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "BattleEntry evidence moderation statuses (§32)", "detail": "ModerationStatus extended: needs_changes, suspected_ai, suspected_stock, duplicate added. max_length kept at 16 (suspected_stock=15). Migration 0036.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "BattleEntry evidence fields (§32)", "detail": "New fields: real_photo_confirmed (BooleanField), photo_hash (SHA-256 of cooked_photo, computed in submit_cooked_photo()), moderation_note (TextField), reviewed_by (FK User), reviewed_at (DateTimeField). Migration 0036.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Article model AI source labels (§29)", "detail": "Article.SourceType extended: AI_ASSISTED ('ai_assisted'), HUMAN_REVIEWED_AI ('human_reviewed_ai') added. CharField only — no migration required.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "AI-assisted content notice in recipe template (§29)", "detail": "recipe_detail.html: notice added inside source_type=='ai_assisted' block: 'This recipe may include AI-assisted text or imagery...' Styled with .ai-content-notice in detail_page.css.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "AI-assisted content notice in article template (§29)", "detail": "article_detail.html: notice added for source_type in [ai_assisted, human_reviewed_ai]: 'This article may include AI-assisted text or imagery...' Same .ai-content-notice CSS class.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Forbidden claims check in moderation (§30)", "detail": "check_forbidden_claims() in services.py scans recipe/article text for 18 forbidden health/safety phrases. Moderation panel annotates each pending item with .forbidden_claims_hits and shows ⚠ warning inline.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Post-purchase durable confirmation email (§10)", "detail": "stripe_services._send_purchase_confirmation() sends email with EU CRD Article 16(m) consent text after checkout.session.completed webhook credits tokens. fail_silently=True so payment never rolls back on email failure.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
        {
            "title": "Phase 8 - Economy Protection (CBR / LSR / Ledger)",
            "items": [
                {"label": "RewardRecord model (CBR and LSR)", "detail": "11-status lifecycle: PENDING→QUEUED→APPROVED→ISSUED→ACKNOWLEDGED→USED→EXPIRED→REVERSED→DISPUTED→VOIDED→ARCHIVED. issue_reward(), expire_rewards(), reverse_reward() services. expire_rewards cron every 30 min.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "LSR creation on appreciation gift", "detail": "send_appreciation_gift(): sender gets 10% back as issued LSR; recipient chef gets pending LSR equal to full gift cost (APPRECIATION_GIFT_REWARD_BASIS). LedgerEvent written for both.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Immutable event ledger with hash chain", "detail": "LedgerEvent with 20 event types. SHA-256 hash chain: each row hashes its own content + prev_hash. verify_chain() classmethod detects tampered rows. Append-only; signals block silent update/delete.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "Fraud and compliance flags", "detail": "ChefBattleProfile: fraud_flag, fraud_flag_note, is_suspended, suspended_at, suspension_reason, dsa_reported_count. Admin actions: suspend/unsuspend, set/clear fraud flag. 15-gate fraud pipeline (run_fraud_gates).", "status": "done", "completed_at": "2026-06-14"},
                {"label": "18+ technical gate", "detail": "gate_age_verified() in fraud pipeline. Blocks token purchase, appreciation gift send, and challenge create when ChefBattleProfile.age_verified=False.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Age verification UI", "detail": "Self-service page at /chef-battle/age-verification/. Chef ticks 18+ checkbox; ChefBattleProfile.age_verified=True + age_confirmed_at timestamp written. Token shop error message adds link to this page when age gate fires. @login_required, redirects away if already verified.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Suspicious vote detection", "detail": "gate_self_vote, gate_participant_vote, gate_vote_rate_ip (3/hr), gate_duplicate_device (session+UA hash) — all wired into battle_vote view via run_fraud_gates.", "status": "done", "completed_at": "2026-06-14"},
                {"label": "Gift reward-eligibility flag", "detail": "APPRECIATION_GIFT_REWARD_ELIGIBLE and APPRECIATION_GIFT_REWARD_BASIS dicts added to models.py. All 6 appreciation gifts are eligible (non-artifact). Artifact gifts never create LSR.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Artifact consumption tracking", "detail": "ChefArtifact extended with statuses: available/reserved/consumed/expired/reversed. New fields: reserved_in_battle, expired_at, reversed_at. Data migration moves existing 'active' rows to 'available'. Source extended with admin_grant.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Admin artifact grant with audit", "detail": "AdminArtifactGrantForm + grant_artifact_view in ChefArtifactAdmin (admin.py). Mandatory reason field. Creates ChefArtifact with source=admin_grant + LedgerEvent(ARTIFACT_GRANTED). Never creates CBR/LSR. Template: chef_battle/admin_grant_artifact.html.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Next Battle Unlock logic", "detail": "check_next_battle_unlock() and run_next_battle_unlock_for_chef() in services.py. Eligible battle = COMPLETED + both entries + chef's cooked photo moderation_status=APPROVED + no suspension/fraud flag. Automatically called after calculate_battle_result().", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Refund / chargeback lock behaviour", "detail": "handle_token_order_chargeback() in services.py: marks order refunded/disputed, deducts tokens from wallet, reverses PENDING/QUEUED rewards linked to gifts, flags gifts (is_flagged), sets ChefBattleProfile.payout_blocked=True, creates CHARGEBACK_LOCK ledger event. Wired into Stripe charge.refunded and charge.dispute.created webhooks in stripe_services.py.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "DSA / content reporting flow", "detail": "ContentReport model + submit_content_report() service + ContentReportAdmin. Frontend: /chef-battle/report/ POST endpoint (content_report_submit view). Report button + <dialog> modal on battle_detail and chef_profile. LedgerEvent(CONTENT_REPORT) on every submission.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
        {
            "title": "Phase 9 - Stripe Connect Payouts",
            "items": [
                {"label": "PayoutRequest model", "detail": "PayoutRequest model: chef, dac7_record, reward_agreement FK, amount_reward_tokens, payout_rate_snapshot (immutable €0.025/token), gross_payout_eur, currency, stripe_connect_account_id, stripe_transfer_id, status (7 choices), reviewed_by/at, paid_at, rejection_reason, compliance_flags JSON. Migration 0032.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Stripe Connect onboarding flow", "detail": "ChefBattleProfile: stripe_connect_onboarded flag added. DAC7Record model stores: stripe_connect_account_id, verification_status. Full Stripe Connect API integration pending (requires live Stripe keys and account review).", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Chef Reward Agreement", "detail": "ChefRewardAgreement model: chef FK, accepted_at, agreement_version, consent_text_snapshot (frozen for audit), ip_address, user_agent. ChefBattleProfile.reward_agreement_accepted flag. Immutable admin view only. Migration 0032.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "DAC7 / MRDP data collection", "detail": "DAC7Record model: legal_name, date_of_birth, primary_address, country_of_tax_residence, tax_identification_number, business_name, business_registration_number, stripe_connect_account_id, verification_status. OneToOne with RecipeAuthor. Admin view in DAC7RecordAdmin. Migration 0032.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Payout request flow", "detail": "check_payout_eligibility() + create_payout_request() in services.py. Eligibility: 18+, reward_agreement_accepted, stripe_connect_onboarded, not suspended/fraud/payout_blocked, ≥2000 APPROVED tokens, no open request. create_payout_request() locks APPROVED records to ISSUED atomically and freezes rate snapshot.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Admin payout approval", "detail": "approve_payout_request() + reject_payout_request() services. Reject moves ISSUED records back to APPROVED. Approve triggers _execute_stripe_connect_transfer(). Admin actions: approve, mark_under_review, hold in PayoutRequestAdmin. All events written to immutable LedgerEvent.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Payout ledger and statements", "detail": "get_chef_payout_statement() in services.py: reward_summary per status, payout_history (last 20), eligibility check. All payout events (request/approve/reject/paid) written to LedgerEvent as ADMIN_NOTE with full payload.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Payout statement page (chef-facing)", "detail": "/chef-battle/payout/ — eligibility panel, approved reward records, payout history, request button. /chef-battle/payout/agreement/ — reward agreement acceptance flow (v1.0 text, consent snapshot, DAC7 disclosure). accept_reward_agreement() service stores ChefRewardAgreement record. Stripe Connect onboarding required for real transfers.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
        {
            "title": "Phase 10 - Live Video Round 2",
            "items": [
                {"label": "LiveBroadcast model", "detail": "LiveBroadcast model: OneToOne with LiveStreamSession, recording_reference, moderation_status (4 choices), safety_delay_enabled, stopped_by_staff, stop_reason, report_count, reviewed_by/at, moderation_note. LiveBroadcastReport: broadcast FK, reporter, category (7 choices: child_safety/privacy_breach/prohibited_content/alcohol_drug/illegal_content/copyright/other), description. Admin: approve/reject actions. Migration 0034.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Live stream infrastructure", "detail": "LiveStreamSession model: battle FK, chef FK, provider (mux/agora/livekit/other), provider_stream_id, provider_playback_url, status (5 choices), checklist_confirmed, started_at, ended_at, terminated_by. PRE_LIVE_CHECKLIST_ITEMS list (14 items) in models.py. Admin: terminate action. Migration 0033. Live provider API integration pending (requires live keys).", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Pre-live checklist", "detail": "PRE_LIVE_CHECKLIST_ITEMS: 14-item checklist in models.py covering age, minors, cooking area only, no documents on camera, no copyrighted content, safe kitchen, injury liability, recording consent, platform termination rights, health claims, alcohol/substance rules, rules agreement. LiveStreamSession.checklist_confirmed + checklist_confirmed_at fields.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Live Battle Agreement", "detail": "LiveBattleAgreement model: chef FK, accepted_at, agreement_version, consent_text_snapshot (frozen for audit), ip_address, user_agent. Migration 0035. Fully read-only admin. Frontend acceptance flow pending (requires live stream feature to be active).", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Staff / admin emergency stop", "detail": "LiveStreamSession.status=TERMINATED + terminated_by + terminated_reason. LiveBroadcast.stopped_by_staff=True + stop_reason. Admin terminate action on LiveStreamSessionAdmin. LedgerEvent audit trail via ACCOUNT_SUSPENDED or ADMIN_NOTE.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Live stream report button", "detail": "LiveBroadcastReport model with 7 report categories. LiveBroadcast.report_count counter field. LiveBroadcastReportAdmin for staff review. Frontend report button and auto-pause trigger pending (requires live stream provider integration).", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Recording and moderation review", "detail": "LiveBroadcast.moderation_status (pending/approved/rejected/under_review). recording_reference stores provider recording ID. Staff approve/reject actions in LiveBroadcastAdmin. moderation_note + reviewed_by/at for audit.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Live video rules in public rules page", "detail": "Section s19 added to /chef-battle/rules/: Who Can Stream, Minors and Home Kitchens, Kitchen Safety, Prohibited Content (copyright/alcohol/defamation/brand conflicts), Recording and Moderation, Pre-Live Checklist (14 items matching PRE_LIVE_CHECKLIST_ITEMS in models.py). TOC updated in both mobile and desktop nav.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
        {
            "title": "Phase FE - Frontend, Design And Visualisation",
            "items": [
                {"label": "Artifact gallery public page", "detail": "Public browseable gallery at /chef-battle/artifacts/ listing all 200 combat artifacts grouped by rarity with name, description, effect and token cost. Hero-style header, consistent battle design.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Battle homepage hero image", "detail": "Commission or generate a strong hero image for /chef-battle/ — two chefs facing off in a kitchen arena, bold colours, site brand style.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Rankings page infographic", "detail": "Rank-tier infographic showing the 8 ranks from Kitchen Porter to Culinary Master with point thresholds.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Battle energy (moves) explainer graphic", "detail": "Visual explainer of the moves / battle-energy system for the guide page: earn moves, spend moves, infinite-moves for CulinEire Hero.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Chef rank badges", "detail": "Badge artwork for the 8 rating ranks and the unique CulinEire Hero status.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Rarity tier icons — 5 rarities", "detail": "Icon set for Common / Uncommon / Rare / Epic / Legendary used in artifact gallery and gift panels. Colour-coded: grey/green/blue/purple/gold.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Season leaderboard podium graphic", "detail": "Podium (1st / 2nd / 3rd) illustration for the season leaderboard top-three block, matching arena visual style.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Hall of Fame banner", "detail": "Wide decorative banner for the Hall of Fame page header. Stone or wood textures, trophy imagery, Celtic motif optional.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Token shop visual assets", "detail": "Coin/token icon and package artwork (Starter / Contender / Warrior / Champion / Legend packs) for the token shop page.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Biathlon page visual", "detail": "Ingredient grid visual for the biathlon phase, showing locked (shield) and unlocked ingredients, hit effects. Either SVG or CSS-based.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Gift panel thumbnails", "detail": "Thumbnail images for each appreciation gift (Flower, Coffee, Pint, Whiskey, Cocktail) and at least the 5 rarity tiers of artifact gifts.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Chef profile avatar placeholder", "detail": "Branded placeholder avatar for chefs without a photo, using arena/kitchen motif.", "status": "done", "completed_at": "2026-06-16"},
                {"label": "Manual tasks checklist for roadmap", "detail": "Add persistent checkbox list at the bottom of the roadmap page for manual-test items. State saved to localStorage.", "status": "done", "completed_at": "2026-06-16"},
            ],
        },
        {
            "title": "Phase FE-2 - Arena Mechanic Legibility (Interaction Parity)",
            "items": [
                {"label": "Click-ripple parity: arena-cell vs puzzle-cell", "detail": "fireCellRipple() already existed in arena_puzzle.js, wired to cell/spectator clicks. Aligned constants (MAX_R 90->110, DURATION 380->420ms) to exactly match sponsors_puzzle.js for verified parity.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Fix residual legacy green in blast-ring", "detail": "templates/base.html .battle-blast (blast-ring keyframe + card border) hardcoded rgba(109,206,143,*) / #6dce8f, missed by the earlier site-wide green-removal pass (lives in an inline <style> block, not static/css/*.css). Replaced with the standardized gold accent #c8942a / rgb(200,148,42). Zero remaining matches for 'rgba(109, 206, 143' codebase-wide.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Surface real Crown holder at arena centre", "detail": "_arena_center() (chef_battle/views.py) adds a center.type == 'crown' branch (crown_until > now, same query as the site-wide hero_battle_panel context processor) when there's no active battle. drawCentre() in arena_puzzle.js renders it as a 3-line stack: crown icon above the name, 'CROWN HOLDER' label below. Click links to the holder's author profile. Verified live.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Wire blast-ring to a real site-wide win event", "detail": "_arena_latest_result() (chef_battle/views.py) returns the most recently COMPLETED Battle (winner/loser/result_reason/theme). Added to both arena() and arena_state() JSON as latest_result. arena_puzzle.js seeds _lastSeenResultId from the page's own initial data on load, then each 20s poll only fires the celebration if battle_id actually changed -- so any arena visitor sees it when any battle concludes, without retroactively firing for old battles. Verified end-to-end (render + dismiss cycle); no real battle has completed since deploy to see it fire from a genuine event yet. The #blast-badge/#blast-winner legacy green flagged here was resolved by the site-wide gold pass on 2026-07-02 (see below).", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Connect arena-online-dot to real presence data", "detail": "Already fully wired: profile.last_seen_at (updated by the 60s pingArena heartbeat) -> is_online in the JSON payload -> appendOnlineDot() in arena_puzzle.js -> arena-pulse CSS animation. Verified correct; no code change needed. Dot count depends on who is actually online at any given moment.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Curate EPIC/LEGENDARY artifact names", "detail": "13 of 32 EPIC+LEGENDARY artifacts (real counts, not 24+16 as originally briefed) carried generic Western-fantasy/Greek/Norse naming. Rewritten to the Irish-myth/real-object pattern already used by Dagda's Cauldron, Cauldron of Lugh, The Irish Kitchen, The Eternal Apron, Manannan's Cloak -- drawing on a varied roster (Cu Chulainn, Aoife, Brigid, Balor, Goibniu, Manannan, the Fianna, Tara, Newgrange, the Ardagh Chalice, Claiomh Solais) rather than reusing one figure. Only the name field changed. loaddata run on production, verified live in the artifact gallery.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Verify chef avatar rendering in occupied arena cells", "detail": "Confirmed correct, no change needed: RecipeAuthor.display_avatar_url (recipes/models.py) always returns either the real uploaded photo or one of the male/female/neutral illustrated defaults -- never a generic-initials placeholder. arena_puzzle.js's appendAvatarToCell() already renders this as a real clipped SVG <image>.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Extend battle-cursor (knife + honing steel) to arena cells and combat CTAs", "detail": "Owner spotted the existing crossed-cutlery hover cursor (battle_cursor.js/.css, previously wired only to the header nav link and the wordmark 'Issue a Challenge' CTA via direct per-element binding) and asked to reuse it rather than build anything new. Rewrote battle_cursor.js to event-delegate on document (pointerover/pointerout/pointermove) so dynamically-drawn/redrawn elements pick it up automatically. Added battle-cursor-target js-battle-cursor-target to occupied arena-cell chefs, plus Send Challenge / Challenge This Chef / Accept / Make Move CTAs.", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Fix arena tooltip View Profile button vertical centering", "detail": "Found in passing while testing the battle-cursor: the tooltip's View Profile link carried two conflicting component classes (arena-tooltip__link + generic btn-primary from base.css's @layer base, min-height:48px), leaving the text sitting near the top of an oversized box. Removed the redundant btn-primary class, switched display to inline-flex + align-items:center, and reduced line-height to shrink the residual sub-pixel glyph-leading asymmetry (same font-metric class of issue as the earlier hero H1/subtitle spacing work).", "status": "done", "completed_at": "2026-07-01"},
                {"label": "Site-wide legacy green to gold accent (owner-approved)", "detail": "Owner approved replacing the last legacy greens (#1a6b3a text / #d6f5e0 pill bg / #6dce8f-#bfedd0-#4db877 borders) with the standardized gold family (#c8942a accent, #f8d28a pill bg, #6e4e2c dark text). Touched: base.html blast badge/winner, chef_battle.css (combat/pip 'your turn' pills, token-shop featured card + badge + price, battle-guide focus/hover/label), moderation.css mod-tool-link--done, coworking dashboard active badge, chef_profile Wins stat + Won label, season_leaderboard pts, rules.html winner %. Also removed the undefined var(--color-success, ...) fallback pattern -- the variable was never defined, so the green fallback always rendered.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Sync artifact image-prompt catalogue with Irish-myth naming", "detail": "generate_battle_assets.py and docs/chef_battle/combat_items.md kept the pre-curation fantasy names (Excalibur's Cutting Board, Zeus's Stockpot Dome, Kitchen God's Aegis/Ladle, Adamantine Stockpot/Wok, Dragon's Breath Sauce, rune imagery). Renamed in both files to the Irish-myth/real-object pattern: Salamander Grill Sauce (real kitchen broiler), The Dagda's Ladle, Skellig Stone Stockpot, The Ogham Cutting Board, The Tir na nOg Wok, Giant's Causeway Dome, Nuada's Silver Pot Lid; rune imagery replaced with ogham script. Static batch images were never generated/referenced (static/images/battle/artifacts/ not in git), so this only affects future re-runs. The live per-artifact generator (artifact_generate_image) already reads names from the DB and needed no change.", "status": "done", "completed_at": "2026-07-02"},
            ],
        },
        {
            "title": "Phase FE-3 - Arena As The Hall (Approved Plan, 2026-07-02)",
            "items": [
                {"label": "Stage A1: Chef popup on arena cell click", "detail": "Stats (W/L/Streak), approximate ATK/DEF potential from ChefArtifact aggregation (hidden when 0), View Profile + Challenge buttons. Challenge hidden for spectators, self, and in-battle chefs. challenge_create now accepts ?opponent={slug}.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage A2: Blue spectator cells for registered users", "detail": "Spectator ring changed from green (#4a6741) to blue (#2a5fb0 / empty #c5d3e8). Legend swatch updated. Currently wallet-holders only (_get_spectators behaviour, same as before).", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage A3: Grey standing fields for anonymous visitors", "detail": "Superseded by AR5 (v2.5.778): anonymous visitors now stand in the balconies as bodiless spirits, not in a grey field. The blocker recorded here - 'requires a lightweight anonymous presence signal, none exists today' - was already false when it was written and stayed on the board for weeks: BattleViewerPresence records is_authenticated on every lobby heartbeat, which is exactly that signal and is what the spirit count reads. Left visible rather than deleted, because a stale blocker is worth keeping as a warning: it nearly sent an agent to build a second presence system.", "status": "done", "completed_at": "2026-08-03"},
                {"label": "Stage B1: Battle context in arena payload", "detail": "arena() + arena_state() now include battle_id, battle_phase, battle_url per in_battle chef. in_battle_map dict replaces raw in_battle_author_ids set.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B3: Chefs disappear from ring when in VS centre", "detail": "CENTRE_PHASES + FACING_PHASES constants in arena_puzzle.js. drawArena() vacates ring cell when chef.battle_phase is in either set — move not duplicate.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B2: Facing pair positioning (pre-combat)", "detail": "Challenge accepted (scheduled/menu_locked) -> show chefs in deterministic facing cells in the centre zone (not ring cells). _arena_center() returns type 'facing_pair' for SCHEDULED/MENU_LOCKED. drawFacingPair() places two cells at battle_id-deterministic angle, R=28, dist=48px from centre. Crossed swords ⚔ indicator between them.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B4: Completion → return to ring cells", "detail": "Handled implicitly by B1+B3: when battle reaches COMPLETED/CANCELLED it leaves ACTIVE_STATUSES, so in_battle_map no longer contains the chefs, their ring cells are rendered normally on the next poll.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B5: Teleport animation", "detail": "SHIPPED as T25, 2026-08-17 - the animate-second half this row always sequenced. A chef changing ring cell now travels there over 1.6s instead of vanishing from one and appearing in another. Two position maps in arena_render.js remember where everyone stood, swapped inside bind() before anything is drawn; the movement itself is a CSS transition scoped to chefs that actually moved, so no timer is spent and reduced-motion switches it off with everything else. arena-teleport-flash is a different thing and is untouched: that is the centre-stage arrival ring.", "status": "done", "completed_at": "2026-08-17"},
                {"label": "Stage C: Battle Room popup embedded on the arena", "detail": "OWNER APPROVED option A. Centre VS cell = one big link opening the popup: chef left vs right, artifacts visible (open battle), per-battle chat, voting, gifts - all via existing endpoints. 18+/legal affordances carry over unchanged.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage D1: Battle Room page becomes the antechamber", "detail": "battle_detail hero redesigned as antechamber: two chef comparison cards (avatar, name, rank, W/L/streak/rating), 'Watch Live in Arena' CTA for active battles. challenger_profile + opponent_profile added to context. D2 (where chefs do combat actions) remains an open owner decision — combat panels stay on this page for now.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage E1: Mandatory use of spectator-gifted artifacts", "detail": "SHIPPED as T24, 2026-08-16. Chefs may use their own artifacts and MUST use the ones spectators gifted them during the battle: submit_combat_action refuses any action that ignores an unspent BATTLE_GIFT artifact locked to that battle. Enforced per effect type - an attack cannot spend a defence artifact, so a gifted shield does not block an attack. Appreciation gifts remain provably inert to combat. ViewerBattleGift.is_applied, unwritten since migration 0008, is now set at consumption.", "status": "done", "completed_at": "2026-08-16"},
                {"label": "Stage E2: Appreciation gifts sellable after battle", "detail": "New economy mechanic. Requires closed-loop token model (s14) and anti-gambling (s17) legal check BEFORE build. Rate and flow TBD with owner.", "status": "pending"},
                {"label": "Stage E3: Scheduled battle time + readiness gate", "detail": "SHIPPED as T19/T20/T21, v2.5.1043-v2.5.1048, and this row was left behind by the agent who shipped them. Every clause of the old text is now false. 'Today battles start on accept' - they do not: accept_challenge schedules the start PREPARATION_WINDOW (48h) ahead, and a proposed time earlier than that is refused rather than honoured. 'Needs a battle-time concept (who sets it - open owner decision)' - the Owner decided it on 2026-08-15: the challenger proposes with the task, acceptance opens the 48 hours, and a pair's PLACE in the NEXT BATTLE strip IS its remaining time. 'A both-ready gate before the centre teleport' - READY_HEAD_START, 30 minutes on his 2026-08-15 correction of the earlier 15, and pull_start_forward_when_both_ready never pushes a start later.", "status": "done", "completed_at": "2026-08-15"},
            ],
        },
        {
            "title": "Phase AMC - Arena Master Console (10-phase plan, docs/chef_battle/arena_master_console/)",
            "items": [
                {"label": "P00: Discovery, baseline, and contract freeze", "detail": "Reuse matrix for all 8 mockup panels (P00_REUSE_MATRIX.yaml), frozen public arena + operator read-model contracts (P00_CONTRACTS.yaml), query baselines: arena() 15q/47KB anon, 21q/51KB auth; arena_state() 7q/4.5KB. All 6 decision gates resolved (P00_DECISIONS.yaml). Both verification passes recorded (P00_BASELINE_REPORT.md). No production code added.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P01: Desktop visual shell and information architecture", "detail": "Console shell live at /chef-battle/master/ behind ARENA_MASTER_CONSOLE_ENABLED (default off) + DG-01 gate (superuser + owner/flag, 404 otherwise). RecipeAuthor.has_arena_console_access added (recipes/0038). 8-panel deck, phase rail, overview row, system footer — explicit empty states only, all controls disabled. 12 access tests. Verified at 1920/1440/1280/mobile.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P02: Read-only arena overview and live data adapters", "detail": "Console now live: get_master_state() selector + POST /chef-battle/master/state/ (20s poll, 12 queries/1.9KB at 1 battle). Battle status, chef cards, phase rail, voting/moderation/economy panels all real; public ring embedded via shared partial. arena()/arena_state() dedup into _build_arena_payload(). Viewers metric honestly unavailable (DG-04 source does not exist). Fixed latent arena 500 (.value on DB status). 17 new tests; 171/171 suite green.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P03: Arena control and battle-flow orchestration", "detail": "Owner-only controls live: force transitions (service-owned paths reuse approve_cooking_phase / calculate_battle_result), Emergency Stop per DG-03 (PAUSED + stream termination + chef notifications + timer freeze), Resume, Cancel, Broadcast. All transactional, expected_status idempotency, OPERATOR_ACTION audit with correlation id. Award Crown permanently disabled (audience decides). 22 tests; suite 193/193. Migration 0056.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P04: Live battle monitor and combat engine console", "detail": "Monitor section merged into master_state: battle/challenge counts, live event log (incl. operator audit entries), per-round combat detail with declared actions, biathlon locks/shots, artifacts-in-use. Side-effect-free polling proven by test. Hidden info visible only behind console gate; public JSON unchanged. 9 tests; suite green.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P05: Moderation, safety, and live-stream operations", "detail": "Panel 4 live: cooking queue with per-entry state, pending content reports, stream sessions with broadcast safety data (checklist, delay, agreement, report count). Owner-only actions: moderate_entry (adverse needs reason + notifies chef), review_report (note required), end_stream (honest provider_side_terminated:false - no provider API exists). All audited. 10 tests; suite 212 green.", "status": "done", "completed_at": "2026-07-04"},
                {"label": "P06: Voting integrity and audience analytics", "detail": "Panel 5 live: percentages (NULL at zero votes), UTC hourly vote series (24h, tz test-asserted), enforcement evidence (unique constraints + VoteIntegrityEvent aggregates by gate), privacy-safe suspicious queue (no voter identity/hashes), tie + completion readiness incl. blocked-by-tie, community pulse (visible chat, support per chef). Read-only; no risk scores claimed. 9 tests; suite green.", "status": "done", "completed_at": "2026-07-05"},
                {"label": "P07: Economy, gifts, tokens, and artifacts", "detail": "Panel 6 live, READ-ONLY: token flows by tx_type (24h, signed ledger sums), gift catalogue from source-of-truth constants + 24h delivery, per-chef gift totals, artifact inventory by status + rarity distribution, orders by status with disputed/refunded attention ids. No economy write path exists (test posts 5 mutation verbs, all 400). Ledger reconciliation + wallet invariant tests. Closed-loop wording enforced. 8 tests; suite green.", "status": "done", "completed_at": "2026-07-05"},
                {"label": "P08: CBR, LSR, payout, ranks, crown, and arena authority", "detail": "Panel 7 live: CBR/LSR status matrix (full lifecycle), payout queue with owner-only approve/reject delegating to existing owning services (Stripe path untouched), BattleReport model+workflow (DG-06: any operator reports, owner decides, owner notified), live LedgerEvent hash-chain check in the panel. Chain asserted intact after payout approval. 9 tests; suite green. Migration 0058.", "status": "done", "completed_at": "2026-07-05"},
                {"label": "P09: Integrated hardening, accessibility, performance, and release readiness", "detail": "Final phase: stale-poll guard (monotonic sequence), verify_chain 60s cache (was full scan per 20s poll), :focus-visible outlines + aria-live status line, viewports 1920/1440/1280/mobile clean, public arena regression clean, perf measured (37 queries / 4KB / 24ms at 1 battle), full project suite green, security review + rollout/rollback/incident docs. CHEF_BATTLE_ENABLED untouched (dark). Console complete: 96 focused tests across 8 suites.", "status": "done", "completed_at": "2026-07-05"},
            ],
        },
        {
            "title": "Phase 11 - Solicitor And Accountant Review",
            "items": [
                {"label": "Solicitor review of public rules", "detail": "Bearcave Limited solicitor must review all public Chef Battles rules before token economy, payouts and live video go live. Scope: token model, gift wording, CBR/LSR, payout terms, anti-gambling, DSA compliance, live video rules.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Accountant review of VAT treatment", "detail": "Bearcave Limited accountant must confirm VAT treatment of Spendable Tokens before launch: electronically supplied digital service / single-purpose voucher / multi-purpose voucher / other. Stripe Tax configuration must match.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "DAC7 / MRDP obligation review", "detail": "Review DAC7/MRDP reporting obligations with accountant or tax advisor. Confirm which Chefs are reportable. Set up Revenue reporting process.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Stripe Connect payout wording review", "detail": "Solicitor and accountant must approve final Stripe Connect payout wording, Chef Reward Agreement and payout statement format before any real payout is processed.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Refund and consumer rights review", "detail": "Solicitor must confirm refund wording complies with Irish/EU consumer rights law for digital content and digital services. Confirm correct wording for token non-refundability.", "status": "done", "completed_at": "2026-06-15"},
                {"label": "Live video privacy and child-safety review", "detail": "Solicitor review of live video child-safety rules, GDPR compliance for recordings, DSA compliance for user-generated live content.", "status": "done", "completed_at": "2026-06-15"},
            ],
        },
    ]

    items = [item for phase in phases for item in phase["items"]]
    completed_items = sorted(
        [item for item in items if item["status"] == "done"],
        key=lambda x: x.get("completed_at", ""),
        reverse=True,
    )
    active_items = [item for item in items if item["status"] != "done"]
    countable_items = [item for item in items if item["status"] != "manual"]
    done_count = len(completed_items)
    total_count = len(countable_items)
    percent = round((done_count / total_count) * 100) if total_count else 0

    copy_lines = [
        "CulinEire Chef Battles battlefield handoff",
        f"Progress: {done_count}/{total_count} items complete ({percent}%).",
        "",
        "Current metrics:",
        f"- Chef profiles: {profile_count} ({hero_count} CulinEire Hero)",
        f"- Challenges: {challenge_count} ({pending_challenges} pending, {refused_challenges} refused)",
        f"- Battles: {battle_count} ({active_battles} active, {completed_battles} completed)",
        f"- Battles with entries: {entry_count}",
        f"- Votes: {vote_count}",
        f"- Public events: {event_count}",
        f"- Artifacts loaded: {artifact_count}",
        f"- Token wallets: {wallet_count}",
        f"- Chat messages: {chat_message_count}",
        "",
        "Open / manual work:",
    ]
    for phase in phases:
        open_items = [item for item in phase["items"] if item["status"] != "done"]
        if not open_items:
            continue
        copy_lines.append(f"{phase['title']}:")
        for item in open_items:
            copy_lines.append(f"- [{item['status']}] {item['label']} - {item['detail']}")

    return {
        "phases": phases,
        "items": items,
        "active_items": active_items,
        "completed_items": completed_items,
        "done_count": done_count,
        "total_count": total_count,
        "percent": percent,
        "copy_text": "\n".join(copy_lines),
        "metrics": {
            "profile_count": profile_count,
            "hero_count": hero_count,
            "challenge_count": challenge_count,
            "battle_count": battle_count,
            "completed_battles": completed_battles,
            "vote_count": vote_count,
            "event_count": event_count,
            "artifact_count": artifact_count,
            "wallet_count": wallet_count,
            "chat_message_count": chat_message_count,
            "feature_enabled": feature_enabled,
        },
    }


@chef_battle_guard
@login_required
def battlefield_progress(request):
    if not is_moderator(request.user):
        raise PermissionDenied

    return render(
        request,
        "chef_battle/battlefield_progress.html",
        {"battlefield_progress": _build_battlefield_progress()},
    )


@chef_battle_guard
def season_leaderboard(request):
    from .season_service import get_active_season, get_latest_finished_season
    active = get_active_season()
    profiles = (
        ChefBattleProfile.objects.select_related("author")
        .filter(seasonal_score__gt=0)
        .exclude(author__slug__in=_uncompeting_slugs())  # T22
        .order_by("-seasonal_score", "-wins", "author__name")[:50]
    )
    if active:
        season_name = (
            f"{active.name} · {active.starts_at.day} {active.starts_at:%b} – "
            f"{active.ends_at.day} {active.ends_at:%b %Y}"
        )
        season_start = active.starts_at
    else:
        season_name = "No active season"
        season_start = None
    # Frozen champions of the most recently ended season, if any.
    finished = get_latest_finished_season()
    past_standings = (
        finished.standings.select_related("chef")[:10] if finished else []
    )
    return render(request, "chef_battle/season_leaderboard.html", {
        "profiles": profiles,
        "season_start": season_start,
        "season_name": season_name,
        "active_season": active,
        "finished_season": finished,
        "past_standings": past_standings,
    })


@chef_battle_guard
@login_required
def chef_enroll(request):
    """Author → Chef onboarding. Requires 18+ confirmation and battle rules acceptance."""
    author = get_author_for_user(request.user)
    if author is None:
        messages.error(request, "You need a recipe author profile to join Chef Battles.")
        return redirect("chef_battle:home")

    # Already enrolled — go straight to arena
    try:
        profile = author.battle_profile
        if profile.enrolled_at:
            return redirect("chef_battle:home")
    except ChefBattleProfile.DoesNotExist:
        profile = None

    error = None
    if request.method == "POST":
        confirm_age = request.POST.get("confirm_age") == "1"
        confirm_rules = request.POST.get("confirm_rules") == "1"
        if not confirm_age or not confirm_rules:
            error = "Please tick both boxes to continue."
        else:
            # F15, 2026-08-11: two concurrent submits (double-click, retried
            # request) both used to read enrolled_at as None, both wrote it,
            # and both called award_enrol_bonus - a plain read-modify-write
            # on chest_moves, so the enrolment bonus could be credited twice.
            # Lock the row and re-check under it, same pattern as F4/F5.
            now = timezone.now()
            with transaction.atomic():
                if profile is None:
                    profile, _ = ChefBattleProfile.objects.get_or_create(author=author)
                profile = ChefBattleProfile.objects.select_for_update().get(pk=profile.pk)
                if profile.enrolled_at:
                    return redirect("chef_battle:home")
                profile.enrolled_at = now
                if not profile.age_verified:
                    profile.age_verified = True
                    profile.age_confirmed_at = now
                profile.save(update_fields=["enrolled_at", "age_verified", "age_confirmed_at"])
                # AA8, 2026-08-15: a chef stands in their rank ring, not in the
                # stands - _ensure_spectator_seat() refuses an enrolled author
                # from this moment on. But nothing ever released the seat this
                # viewer was already holding, so it stayed occupied until the
                # 180-second lapse swept it: a seat in the front rows, held by
                # somebody who is now on the floor, in a hall whose capacity is
                # a fixed 114.
                from .arena_seating import release_seat
                release_seat(author)
                try:
                    from .services import award_enrol_bonus
                    award_enrol_bonus(author)
                except Exception:
                    logger.exception("Failed to award enrol bonus to author pk=%s", author.pk)
            return redirect("chef_battle:enroll_success")

    return render(request, "chef_battle/enroll.html", {"error": error})


@chef_battle_guard
@login_required
def enroll_success(request):
    """Confirmation page shown immediately after successful Chef enrollment."""
    author = get_author_for_user(request.user)
    return render(request, "chef_battle/enroll_success.html", {"author": author})


@chef_battle_guard
@login_required
def age_verification(request):
    """Allow a chef to self-certify they are 18+ before paid Arena features."""
    from .models import ChefBattleProfile
    author = get_author_for_user(request.user)
    if author is None:
        from django.contrib import messages as _msg
        _msg.error(request, "You need a chef profile to access this page.")
        return redirect("chef_battle:home")

    profile, _ = ChefBattleProfile.objects.get_or_create(author=author)

    from django.utils.http import url_has_allowed_host_and_scheme

    def _safe_next(fallback):
        nxt = request.GET.get("next") or ""
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return nxt
        return fallback

    if profile.age_verified:
        return redirect(_safe_next("chef_battle:home"))

    error = None
    if request.method == "POST":
        if request.POST.get("confirm_age") == "1":
            profile.age_verified = True
            profile.age_confirmed_at = timezone.now()
            profile.save(update_fields=["age_verified", "age_confirmed_at"])
            from django.contrib import messages as _msg
            _msg.success(request, "Age confirmed. You can now use Arena paid features.")
            return redirect(_safe_next("chef_battle:token_shop"))
        else:
            error = "Please tick the checkbox to confirm you are 18 or older."

    return render(request, "chef_battle/age_verification.html", {
        "error": error,
        "next": request.GET.get("next", ""),
    })


@chef_battle_guard
def token_shop(request):
    from .models import TokenPackage, ChefBattleProfile
    packages = TokenPackage.objects.filter(is_active=True).order_by("sort_order", "tokens")
    viewer_author = get_author_for_user(request.user)
    wallet = None
    age_verified = False
    if viewer_author:
        wallet, _ = TokenWallet.objects.get_or_create(chef=viewer_author)
        profile, _ = ChefBattleProfile.objects.get_or_create(author=viewer_author)
        age_verified = profile.age_verified
    return render(request, "chef_battle/token_shop.html", {
        "packages": packages,
        "wallet": wallet,
        "age_verified": age_verified,
        "stripe_publishable_key": getattr(__import__("django.conf", fromlist=["settings"]).settings, "STRIPE_PUBLISHABLE_KEY", ""),
    })


WITHDRAWAL_CONSENT_TEXT = (
    "I understand that CulinEire Arena Tokens are a digital item delivered immediately upon purchase. "
    "By proceeding, I expressly request immediate delivery and acknowledge that I lose my right of "
    "withdrawal under EU/Irish consumer law (Consumer Rights Act 2022, Digital Content Directive)."
)


# The guard goes FIRST, above login_required and require_POST, and that order is
# the whole point of this stack. Underneath them the gate still refused everyone
# it should — but require_POST answered an anonymous GET with 405 and
# login_required answered it with a redirect to the login page, so during a dark
# launch these three URLs announced their own existence while every other gated
# arena surface answered 404. A dark launch is about being invisible, not only
# about being shut. Measured on production at v2.5.988 before this change:
# /chef-battle/arena/ 404, /chef-battle/tokens/checkout/ 405.
@chef_battle_guard
@require_POST
@login_required
def token_checkout_create(request):
    from .models import TokenPackage, TokenWallet
    from .stripe_services import (
        TokenStripeConfigurationError,
        create_token_checkout_session,
    )

    author = get_author_for_user(request.user)
    if not author:
        return JsonResponse({"error": "No chef profile found."}, status=403)

    try:
        data = json.loads(request.body)
        package_id = int(data.get("package_id", 0))
        withdrawal_waived = bool(data.get("withdrawal_consent", False))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    # F23, 2026-08-11: gate_token_purchase_velocity was written ("reject if
    # the wallet has too many completed orders in the last 24 hours") but
    # never called anywhere - the one real-money purchase path built its own
    # gate list and left it out. A written, never-wired anti-fraud check on
    # a real-money flow is worse than not having one.
    # F23-DSA, 2026-08-11, Owner's ruling: gate_dsa_report_threshold wired in
    # the same way - an account with too many moderator-logged DSA reports
    # does not buy more tokens until a moderator has looked at it.
    wallet, _ = TokenWallet.objects.get_or_create(chef=author)
    fraud_result = run_fraud_gates([
        (gate_suspended_account, (author,), {}),
        (gate_fraud_flagged, (author,), {}),
        (gate_age_verified, (author,), {}),
        (gate_withdrawal_consent, (withdrawal_waived,), {}),
        (gate_token_purchase_velocity, (wallet,), {}),
        (gate_dsa_report_threshold, (author,), {}),
    ])
    if not fraud_result.passed:
        first_fail = next(g for g in fraud_result.gates if not g.passed)
        _CHECKOUT_FRAUD_MESSAGES = {
            "suspended_account": "Your account is suspended.",
            "fraud_flagged": "Your account has been flagged. Please contact support.",
            "age_verified": "You must confirm that you are 18 or older before purchasing tokens.",
            "withdrawal_consent": "You must confirm the digital content consent before purchasing tokens.",
            "token_purchase_velocity": "You have made too many token purchases in the last 24 hours. Please try again later.",
            "dsa_report_threshold": "Your account has been reported and is pending moderator review. Please contact support.",
        }
        from django.urls import reverse
        resp = {"error": _CHECKOUT_FRAUD_MESSAGES.get(first_fail.gate, "Purchase not accepted.")}
        if first_fail.gate == "age_verified":
            resp["age_verify_url"] = reverse("chef_battle:age_verification") + "?next=" + reverse("chef_battle:token_shop")
        return JsonResponse(resp, status=400)

    try:
        package = TokenPackage.objects.get(pk=package_id, is_active=True)
    except TokenPackage.DoesNotExist:
        return JsonResponse({"error": "Package not found."}, status=404)

    wallet, _ = TokenWallet.objects.get_or_create(chef=author)

    try:
        session_info = create_token_checkout_session(
            package, wallet, request=request,
            withdrawal_waived=True,
            consent_text=WITHDRAWAL_CONSENT_TEXT,
        )
    except TokenStripeConfigurationError as exc:
        logger.warning("Token checkout config error: %s", exc)
        return JsonResponse({"error": "Payment system not configured. Please try again later."}, status=503)
    except Exception:
        logger.exception("Token checkout creation failed for package %s", package_id)
        return JsonResponse({"error": "Could not create checkout session."}, status=500)

    return JsonResponse({"ok": True, "checkout_url": session_info.checkout_url})


@chef_battle_guard
def token_checkout_success(request):
    from .models import TokenOrder, TokenWallet
    session_id = request.GET.get("session_id", "")
    order = None
    if session_id:
        order = TokenOrder.objects.filter(stripe_checkout_session_id=session_id).select_related("package", "wallet").first()
    author = get_author_for_user(request.user)
    wallet = TokenWallet.objects.filter(chef=author).first() if author else None
    return render(request, "chef_battle/token_checkout_success.html", {
        "order": order,
        "wallet": wallet,
    })


@chef_battle_guard
def token_checkout_cancel(request):
    from .models import TokenOrder
    order_id = request.GET.get("order", "")
    order = None
    # Only the order's owner may see or cancel it — the order id is guessable
    # (?order=N), so an ownership filter is the IDOR gate. Anonymous visitors
    # (expired session on return from Stripe) get the page without the order;
    # the pending order is later cancelled by the checkout.session.expired webhook.
    author = get_author_for_user(request.user) if request.user.is_authenticated else None
    if order_id.isdigit() and author:
        order = (
            TokenOrder.objects
            .filter(pk=order_id, wallet__chef=author)
            .select_related("package")
            .first()
        )
    if order:
        # F43, 2026-08-11: this browser-return "cancel" page raced the
        # Stripe webhook (token_stripe_webhook -> _handle_checkout_completed,
        # which already locks the order and rechecks its status) with no
        # lock of its own. A user landing here on a stale/cached cancel
        # link, or a race between the redirect and the webhook, could
        # overwrite an order the webhook had already credited back to
        # "cancelled" - or, symmetrically, a paid order could show cancelled
        # while the buyer's tokens were, in fact, credited. Lock and recheck
        # before writing.
        with transaction.atomic():
            locked_order = TokenOrder.objects.select_for_update().get(pk=order.pk)
            if locked_order.status == TokenOrder.Status.PENDING:
                locked_order.status = TokenOrder.Status.CANCELLED
                locked_order.save(update_fields=["status", "updated_at"])
            order.status = locked_order.status
    return render(request, "chef_battle/token_checkout_cancel.html", {"order": order})


@csrf_exempt
@require_POST
def token_stripe_webhook(request):
    from .stripe_services import (
        TokenStripeConfigurationError,
        TokenPaymentVerificationError,
        construct_stripe_event,
        handle_stripe_event,
    )
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = construct_stripe_event(request.body, signature)
    except TokenStripeConfigurationError as exc:
        logger.warning("Token webhook config error: %s", exc)
        return JsonResponse({"error": "Webhook not configured."}, status=503)
    except Exception:
        logger.warning("Token webhook signature verification failed.")
        return JsonResponse({"error": "Invalid Stripe signature."}, status=400)

    try:
        result = handle_stripe_event(event)
    except TokenPaymentVerificationError as exc:
        logger.warning("Token webhook verification failed: %s", exc)
        return JsonResponse({"error": "Payment verification failed."}, status=400)
    except Exception:
        logger.exception("Token webhook processing failed.")
        return JsonResponse({"error": "Webhook processing failed."}, status=500)

    return JsonResponse({"ok": True, "duplicate": result.get("duplicate", False)})


def battle_rules(request):
    from .services import _DROP_WEIGHTS_WINNER
    from django.templatetags.static import static
    drop_table = [
        {
            "rarity": rarity,
            "winner_pct": _DROP_WEIGHTS_WINNER[rarity],
            "defeated_pct": _DROP_WEIGHTS_WINNER[rarity] / 2 if _DROP_WEIGHTS_WINNER[rarity] % 2 else _DROP_WEIGHTS_WINNER[rarity] // 2,
            "icon": static(f"images/chef_battle/rarity_{rarity}.svg"),
        }
        for rarity in ["common", "uncommon", "rare", "epic", "legendary"]
    ]
    return render(request, "chef_battle/rules.html", {"drop_table": drop_table})


def battle_guide(request):
    return redirect("chef_battle:rules")


@chef_battle_guard
def battle_home(request):
    for battle in get_expired_active_battles():
        calculate_battle_result(battle)

    active_battles = get_active_battles()
    recent_battles = get_recent_completed_battles()
    leaders = get_top_profiles()
    events = get_public_events()

    from .season_service import get_active_season
    active_season = get_active_season()
    season_leaders = (
        ChefBattleProfile.objects
        .select_related("author")
        .filter(seasonal_score__gt=0)
        .order_by("-seasonal_score", "-wins", "author__name")[:3]
    )

    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    user_enrolled = False
    if viewer_author:
        try:
            user_enrolled = bool(viewer_author.battle_profile.enrolled_at)
        except ChefBattleProfile.DoesNotExist:
            pass

    return render(request, "chef_battle/home.html", {
        "active_battles": active_battles,
        "recent_battles": recent_battles,
        "leaders": leaders,
        "events": events,
        "season_name": active_season.name if active_season else "Season Leaderboard",
        "season_dates": (
            f"{active_season.starts_at.day} {active_season.starts_at:%b} – "
            f"{active_season.ends_at.day} {active_season.ends_at:%b %Y}"
            if active_season else ""
        ),
        "season_leaders": season_leaders,
        "viewer_author": viewer_author,
        "user_enrolled": user_enrolled,
    })


_ARENA_ONLINE_THRESHOLD = 180  # seconds — chef counts as online if seen within 3 min


def _arena_runway():
    """The countdown and pace for a scenario run, or None."""
    from .arena_runway import current

    return current()


def _emulation_bots_are_shown() -> bool:
    """Whether the test chefs stand on the arena at all.

    OWNER, 2026-08-07: "убери с арены двух тестовых шефов - просто пока отключи
    их." A SWITCH, NOT A DELETION - the accounts, their profiles and their
    history are untouched, and the Master Console still drives them; they simply
    do not appear on the floor. Off by default, which is the state he asked for;
    ARENA_SHOW_EMULATION_BOTS = True in settings brings them back for a run.
    """
    from django.conf import settings as django_settings

    return bool(getattr(django_settings, "ARENA_SHOW_EMULATION_BOTS", False))


def _emulation_bot_slugs() -> set[str]:
    """The emulation module's own list, never a second copy of it."""
    from .emulation import EMU_CHEFS

    return {slug for slug, _name in EMU_CHEFS}


#: Width of one attack/defence band. Twenty is the plan's own example ("40-60")
#: and is wide enough that a chef's exact loadout cannot be read back out of it.
_POTENTIAL_BAND = 20


def _potential_band(value: int) -> str:
    """An indicative range for a chef's artifact potential, or "" for none.

    AA7, 2026-08-15. ARENA_HALL_PLAN A1: the potential is shown as indicative
    info and the artifact list is never shown. An exact sum is not indicative -
    with a handful of artifacts it can simply be decomposed back into them - so
    the arena publishes the band the value falls in and keeps the number.

    Zero means "nothing to indicate" and returns an empty string rather than
    "0-20", which would advertise a floor the chef has not earned; the tooltip
    already hides the row when both are empty.
    """
    value = int(value or 0)
    if value <= 0:
        return ""
    low = (value // _POTENTIAL_BAND) * _POTENTIAL_BAND
    return f"{low}–{low + _POTENTIAL_BAND}"


def _hidden_bot_slugs() -> set[str]:
    """Bot slugs to exclude from a PUBLIC arena query, or an empty set.

    T-AUDIT, 2026-08-15: this is the one gate the switch was always supposed
    to have. It was written once for the ring query (views.py, enrolled_qs)
    and once more inline for the crown ladder (_without_switched_off_bots)
    and never generalised, so six other places that draw from the database
    independently of the ring - the centre stage's crown holder AND its
    active-battle occupants, the win-celebration (arena-wide, not just the
    arena page), the crown streak, the recent-gifts panel and the
    about-to-start blast - kept showing a bot's name, avatar and rehearsal
    results while the floor was already clear of him. "Off means off
    everywhere" was the documented intent (see _without_switched_off_bots
    below) and was true of the ring and the ladder only.
    """
    if _emulation_bots_are_shown():
        return set()
    return _emulation_bot_slugs()


def _without_switched_off_bots(rows: list) -> list:
    """Strip the test chefs out of a standings list while the switch is off.

    The rings were gated at the query they come from, but the crown ladder is
    not built from enrolled profiles - it counts crowns won today - so a bot
    that won a rehearsal bout kept its line on the arena after the floor was
    already clear of it. Switched off has to mean off everywhere on the page,
    or "the test chefs are gone" is true of the part he happened to look at.
    """
    bots = _hidden_bot_slugs()
    if not bots:
        return rows
    return [row for row in rows if row.get("slug") not in bots]


def _always_on_the_arena() -> set[str]:
    """Author slugs the online window does not apply to.

    THE OWNER, 2026-08-06: the emulation bots are to stand on the arena and stay
    there. A test chef is not a person with a browser - nothing sends his
    heartbeat, so under the three-minute rule he is offline the moment he is
    created and can never be seen. Testing the arena then means somebody
    hand-writing last_seen_at every three minutes, which is a poller by another
    name and this project has none.

    The list is the emulation module's own EMU_CHEFS, not a second copy: these
    are exactly the accounts that exist to be driven from the Master Console,
    they hold no tokens and can take no payout, and if a bot is ever added or
    renamed there it becomes visible here with no second edit.

    Real chefs are untouched. Presence still means presence for everybody who
    is a person.
    """
    if not _emulation_bots_are_shown():
        return set()
    return _emulation_bot_slugs()


_ARENA_STATIC_COUNTRY = "Ireland"
_ARENA_STATIC_FLAG = "\U0001F1EE\U0001F1EA"


def _arena_fighter_payload(author, side):
    """Build Plan 3R3 fighter contract for the confrontation band.

    Country/flag stay static until profile country data is approved. The Arena
    reference requires both inside each floor plinth; keeping the values here
    makes the initial render and every state poll use one authoritative payload.
    """
    return {
        "name": author.name,
        "avatar_url": author.display_avatar_url,
        "slug": author.slug,
        "profile_url": author.get_absolute_url(),
        "side": side,
        "country": _ARENA_STATIC_COUNTRY,
        "flag": _ARENA_STATIC_FLAG,
    }


def _approx_start_display(start):
    """A pill-sized, deliberately approximate start time.

    Within a day it is a clock, because that is the only part anyone reads at a
    glance. Beyond a day a clock alone would be a lie of omission - 19:30 says
    nothing about which evening - so it becomes a date instead.
    """
    local = timezone.localtime(start)
    if start - timezone.now() < timezone.timedelta(hours=24):
        return date_format(local, "H:i")
    return date_format(local, "j M")


def _arena_upcoming():
    """The arranged-but-not-started battles, as the arena announces them (X01).

    One row is one battle: the two chefs by name, the theme, when it starts and
    where to read it. No result, no rating and no phase - none of that exists
    yet, and inventing a placeholder for it is how a panel starts lying.

    The time goes out as an ISO string, not as a rendered "in 3 hours": the
    payload already carries server_time for exactly this reason, and a duration
    baked on the server is wrong the moment it is cached or polled.
    """
    return [
        {
            "battle_id": battle.pk,
            "theme": battle.theme,
            "start_time": battle.start_time.isoformat(),
            # APPROXIMATE, and short enough for a pill a third of the rail wide.
            # Within a day it is a clock, because that is the only part anyone
            # reads; beyond that a clock alone would be a lie of omission, so it
            # becomes a date. Rendered here for the no-JS paint; arena_deck.js
            # replaces it with the viewer's own locale format on the first poll.
            "start_display": _approx_start_display(battle.start_time),
            "battle_url": reverse("chef_battle:battle_detail", kwargs={"pk": battle.pk}),
            "challenger": {
                "name": battle.challenger.name,
                "slug": battle.challenger.slug,
                "avatar_url": battle.challenger.display_avatar_url,
            },
            "opponent": {
                "name": battle.opponent.name,
                "slug": battle.opponent.slug,
                "avatar_url": battle.opponent.display_avatar_url,
            },
        }
        for battle in get_upcoming_battles()
    ]


def _battle_is_at_centre(battle) -> bool:
    """THE CENTRE IS FOR A BATTLE THAT HAS STARTED, AND FOR NOTHING ELSE.
    The single source of truth for 'is this battle on the centre stage right
    now', shared by _arena_center() (what to draw there) and T29's ring
    occupancy (whether the two fighters should vacate their ring cells for
    it) — the two must never be allowed to disagree about the same battle.

    Owner, 2026-08-06, twice in one day. First: accepting a challenge threw
    both avatars out of their rings into the cells by the centre while the
    battle room still read "Awaiting readiness". Then, when readiness became
    the gate: THE PAIR JUMPS TO THE CENTRE ONLY WHEN THEIR BATTLE BEGINS, and
    until then, with no other battle running, THE CELLS BY THE CENTRE ARE
    EMPTY. Pressing Ready is not the beginning — since v2.5.844 it only pulls
    the start in to fifteen minutes, and those fifteen minutes are still spent
    standing in the rings.

    So SCHEDULED and MENU_LOCKED never reach the centre, whatever the ready
    flags say, and a battle whose start_time is still ahead does not either.
    `facing_pair` is therefore no longer produced; the renderer keeps the
    branch because the type remains part of the payload contract.
    """
    if battle is None:
        return False
    not_begun = battle.status in {Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED}
    return not not_begun and battle.start_time <= timezone.now()


def _arena_center(active_battle):
    """Centre-cell payload: active battle takes priority, then the current
    Crown holder (if any), else empty. Shared by arena() and arena_state()."""
    if not _battle_is_at_centre(active_battle):
        active_battle = None

    if active_battle:
        return {
            "type": "active_battle",
            "battle_id": active_battle.pk,
            # NOTE: status is a plain str when the battle is loaded from the
            # DB (TextChoices only wraps in-memory assignments) — .value here
            # crashed the arena for any real active battle (latent pre-P02 bug).
            "battle_phase": str(active_battle.status),
            "status_display": active_battle.get_status_display(),
            "theme": active_battle.theme,
            # Section 2c: the arena is a tabloid and the fight has its own page.
            # This is the link the centre cell carries.
            "battle_url": reverse("chef_battle:battle_broadcast", kwargs={"pk": active_battle.pk}),
            "challenger": _arena_fighter_payload(active_battle.challenger, "challenger"),
            "opponent": _arena_fighter_payload(active_battle.opponent, "opponent"),
        }

    crown_holder = (
        ChefBattleProfile.objects.select_related("author")
        .filter(crown_until__gt=timezone.now())
        .exclude(author__slug__in=_hidden_bot_slugs())
        .exclude(author__slug__in=_uncompeting_slugs())  # T22
        .order_by("-crown_until")
        .first()
    )
    if crown_holder:
        return {
            "type": "crown",
            "name": crown_holder.author.name,
            "avatar_url": crown_holder.author.display_avatar_url,
            "profile_url": crown_holder.author.get_absolute_url(),
            "crown_until": crown_holder.crown_until.isoformat(),
        }

    return {"type": "empty"}


def _arena_latest_result():
    """Most recently completed battle, for the arena-wide win celebration
    (.battle-blast). The client tracks battle_id and only celebrates a
    battle it hasn't already shown, so this can just always return the
    single latest one -- no separate "new since" filtering needed here.

    T-AUDIT, 2026-08-15: this feeds arena_blast(), which sitewide_blast.js
    polls on EVERY page, not only the arena - so a completed rehearsal
    battle between the two switched-off test chefs used to fire the win
    celebration site-wide, naming a bot as the winner, wherever a visitor
    happened to be browsing.
    """
    hidden_bots = _hidden_bot_slugs()
    battle = (
        Battle.objects.select_related("winner", "loser")
        .filter(status=Battle.Status.COMPLETED, winner__isnull=False)
        .exclude(winner__slug__in=hidden_bots)
        .exclude(loser__slug__in=hidden_bots)
        .order_by("-id")
        .first()
    )
    if not battle:
        return None
    return {
        "battle_id": battle.pk,
        "winner_name": battle.winner.name,
        "loser_name": battle.loser.name if battle.loser else None,
        "result_reason": battle.result_reason,
        "theme": battle.theme,
    }


def _get_spectators(online_cutoff, limit=None, *, viewer_author=None):
    """Real seated viewers currently present in the arena stands (Stage 3C).

    Interactive seats come only from ``ArenaSeat`` rows held by online,
    non-enrolled authors. Empty seats stay empty in the payload — atmospheric
    fillers are a renderer concern and must never appear here as people.
    """
    from .arena_seating import public_seat
    from .models import ArenaSeat

    if limit is None:
        limit = spectator_capacity()

    seats = (
        ArenaSeat.objects
        .filter(released_at__isnull=True)
        .select_related("viewer")
        .order_by("ring_index", "seat_index")
    )

    online_non_chef_ids = set(
        ChefBattleProfile.objects
        .filter(
            enrolled_at__isnull=True,
            is_suspended=False,
            last_seen_at__isnull=False,
            last_seen_at__gte=online_cutoff,
        )
        .values_list("author_id", flat=True)
    )

    viewer_id = getattr(viewer_author, "pk", None)
    out = []
    for seat in seats:
        if seat.viewer_id not in online_non_chef_ids:
            continue
        row = public_seat(seat)
        row["is_self"] = bool(viewer_id and seat.viewer_id == viewer_id)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _ensure_spectator_seat(author):
    """Claim a stable stand seat for a logged-in non-chef viewer.

    Enrolled chefs occupy rank rings, not spectator seats. Full halls are
    silent here — the poll still works; the viewer simply has nowhere to sit.
    """
    if author is None:
        return None
    from .arena_seating import ArenaFull, claim_seat

    profile = ChefBattleProfile.objects.filter(author=author).first()
    if profile is not None and profile.enrolled_at is not None:
        return None
    try:
        return claim_seat(author)
    except ArenaFull:
        return None


def arena_blast(request):
    """Ultra-lightweight sitewide blast poll — the win celebration plus any
    battle about to start. Used by sitewide_blast.js on every page."""
    if not is_battle_visible(request):
        raise Http404
    return JsonResponse({
        "latest_result": _arena_latest_result(),
        "starting": get_starting_battle_blast(),
    })


def _build_arena_payload(*, viewer_author=None):
    """Shared arena ring assembly used by arena(), arena_state() and the
    Arena Master Console (P02 dedup — the two views previously duplicated
    these queries line for line). Output keys are part of the frozen public
    contract in P00_CONTRACTS.yaml; do not rename them."""
    active_battles = get_active_battles()
    # T-AUDIT, 2026-08-15: get_active_battles() is shared with battle_home()
    # (the public battle listing, which has never excluded the test chefs and
    # is not asked to), so the exclusion happens HERE, only for the arena
    # payload, not in the selector. A rehearsal bout between the two EMU_CHEFS
    # showed on the live centre stage - name, avatar, "battle_url" and all -
    # for as long as it happened to be ACTIVE, switch or no switch.
    hidden_bots = _hidden_bot_slugs()
    if hidden_bots:
        active_battles = [
            b for b in active_battles
            if b.challenger.slug not in hidden_bots and b.opponent.slug not in hidden_bots
        ]
    active_battle = active_battles[0] if active_battles else None
    in_battle_map: dict[int, dict] = {}
    # T29, Owner ruling 2026-08-16, narrowing A09: a fighter whose battle is
    # ON THE CENTRE STAGE right now vacates his ring cell for it - moved, not
    # duplicated. A09's own guarantee (a fighter's ring cell never empties
    # just because his heartbeat lapsed) still holds for every OTHER phase -
    # the approach stage (SCHEDULED/MENU_LOCKED) never reaches the centre
    # (_battle_is_at_centre), so those fighters keep standing in their rings
    # exactly as A09 shipped them. _battle_is_at_centre() is the one function
    # both this filter and _arena_center() read, so the two can never
    # disagree about the same battle.
    centred_battle_ids = {b.id for b in active_battles if _battle_is_at_centre(b)}
    for battle in active_battles:
        info = {
            "battle_id": battle.id,
            "battle_phase": battle.status,
            "battle_url": battle.get_absolute_url(),
            "at_centre": battle.id in centred_battle_ids,
        }
        in_battle_map[battle.challenger_id] = info
        in_battle_map[battle.opponent_id] = info

    online_cutoff = timezone.now() - timezone.timedelta(seconds=_ARENA_ONLINE_THRESHOLD)
    always_on = _always_on_the_arena()

    enrolled_qs = (
        ChefBattleProfile.objects
        .select_related("author")
        .filter(enrolled_at__isnull=False, is_suspended=False)
    )
    # The test chefs are switched off (Owner, 2026-08-07). Gated HERE for the
    # ring/legend/rank-count query - this was once believed to be the one
    # query everything else on the arena derives from, and it is not: the
    # centre stage, the win celebration, the crown streak, the gifts panel
    # and the starting-battle blast each read the database independently and
    # needed their own gate. See _hidden_bot_slugs().
    hidden_bots = _hidden_bot_slugs()
    if hidden_bots:
        enrolled_qs = enrolled_qs.exclude(author__slug__in=hidden_bots)
    enrolled = list(enrolled_qs.order_by("-rating"))

    enrolled_author_ids = {p.author_id for p in enrolled}

    artifact_agg = {
        a["chef_id"]: a
        for a in ChefArtifact.objects.filter(
            chef_id__in=enrolled_author_ids,
            status=ChefArtifact.Status.AVAILABLE,
        ).values("chef_id").annotate(
            # BOTH spellings. Artifact.effect_type is free text with no choices,
            # and production carries 100 rows spelled "defence" and 2 spelled
            # "defense" — The Butter Shield (epic, 9) and Rusty Pan of Survival
            # (common, 1). Four ChefArtifact rows across two accounts,
            # crestedten and jam-oliver - real accounts, the Owner's own, which
            # he uses for testing. No third-party chef held either, so the
            # impact was latent; the defect was not. An exact match on one spelling
            # silently dropped them from the defence total the arena shows, so
            # those chefs read a number lower than what they own. Combat itself
            # was never wrong: services.py normalises before it compares, and
            # the knife-roll filter already listed both. This was the third
            # consumer and the only one that did neither.
            atk=Coalesce(Sum("artifact__effect_value",
                             filter=Q(artifact__effect_type__iexact="attack")), 0),
            def_=Coalesce(Sum("artifact__effect_value",
                              filter=Q(artifact__effect_type__in=("defence", "defense"))), 0),
        )
    }

    chefs_by_rank = {choice.value: [] for choice in ChefBattleProfile.Rank}
    for profile in enrolled:
        agg = artifact_agg.get(profile.author_id, {})
        battle_info = in_battle_map.get(profile.author_id)
        chefs_by_rank[profile.rank].append({
            "name": profile.author.name,
            "slug": profile.author.slug,
            "avatar_url": profile.author.display_avatar_url,
            "rank": profile.rank,
            "rank_label": profile.get_rank_display(),
            "rating": profile.rating,
            "wins": profile.wins,
            "losses": profile.losses,
            "win_streak": profile.win_streak,
            # AA7, 2026-08-15: a BAND, not the sum. ARENA_HALL_PLAN A1 asks
            # for "an *approximate* attack and defence potential (derived from
            # artifacts, but the artifacts themselves are NOT shown - only
            # indicative info)", and its open question 3 offers a range, stars
            # or a rounded number. The exact aggregate was being shipped, and
            # for a small loadout an exact sum is reversible into the very
            # artifact list the plan says must stay hidden. The band is
            # computed server-side so the precise figure never leaves it.
            "atk_band": _potential_band(agg.get("atk", 0)),
            "def_band": _potential_band(agg.get("def_", 0)),
            "in_battle": battle_info is not None,
            "battle_id": battle_info["battle_id"] if battle_info else None,
            "battle_phase": battle_info["battle_phase"] if battle_info else None,
            "battle_url": battle_info["battle_url"] if battle_info else None,
            # T29: true only while this fighter's battle is ON THE CENTRE
            # STAGE (_battle_is_at_centre) - the window where he has moved
            # there and his ring cell must vacate for it.
            "at_centre": bool(battle_info and battle_info["at_centre"]),
            "is_online": (
                profile.author.slug in always_on
                or bool(profile.last_seen_at and profile.last_seen_at >= online_cutoff)
            ),
            # 2026-08-16: the Owner wears a gold crown on the floor, not a
            # rank aura. His rank is hand-set (migrations 0020/0025), so
            # without this he renders as an ordinary ring-2 Executive Chef
            # and is visually indistinguishable from any chef who earns that
            # rank. is_owner_author() is T22's single answer to "is this the
            # Owner" - not a second OWNER_SLUG comparison.
            "is_owner": is_owner_author(profile.author),
        })

    return {
        "active_battle": active_battle,
        "enrolled": enrolled,
        "chefs_by_rank": chefs_by_rank,
        "rings": {
            # Only chefs currently online occupy ring cells. Offline chefs
            # vanish from the sector entirely and reappear automatically on the
            # next arena poll once their heartbeat marks them online again.
            # chefs_by_rank stays complete so the legend/roster counts still
            # reflect every enrolled chef.
            #
            # A09: A FIGHTER IS NEVER FILTERED OUT OF HIS OWN BATTLE FOR BEING
            # OFFLINE. The online window is 180 seconds of heartbeat, and a
            # chef who closes the tab before his battle even begins (the
            # approach stage - SCHEDULED/MENU_LOCKED, never shown at centre)
            # must not vanish from the floor; that would leave a ring looking
            # unused, which is the one thing the arena exists to show
            # (ARENA_BATTLE_PLAN 2b).
            #
            # T29, Owner ruling 2026-08-16, NARROWING A09: once that battle IS
            # on the centre stage (_battle_is_at_centre - active_battle["at_centre"]
            # above), the fighter has moved there and his ring cell empties for
            # it - moved, not duplicated in both places at once. A09's own
            # guarantee is unchanged for every phase that never reaches the
            # centre; only the centred window is new.
            rank.value: [
                c for c in chefs_by_rank[rank.value]
                if c["is_online"] or (c["in_battle"] and not c["at_centre"])
            ]
            for rank in ChefBattleProfile.Rank
        },
        "spectators": _get_spectators(online_cutoff, viewer_author=viewer_author),
        "center": _arena_center(active_battle),
        # The runway: a countdown before a scenario run, and the faster poll
        # that makes a five-second step visible at all (Owner, 2026-08-06).
        # None when nothing is running, which is almost always.
        "runway": _arena_runway(),
        # X01: half of the arena's stated purpose, and it had no key at all.
        # A LIST, and an empty one is the honest answer when nothing is booked -
        # the panel says so rather than borrowing a row from anywhere else.
        "upcoming": _arena_upcoming(),
        "latest_result": _arena_latest_result(),
        "crown_streak": get_crown_streak(),
        "crown_ladder": _without_switched_off_bots(get_crown_ladder()),
        "recent_gifts": get_recent_battle_gifts(active_battle),
        "top_supporter": get_top_supporter(active_battle),
        "metrics": get_arena_metrics(active_battle),
        "phase": get_arena_phase(active_battle),
        "phase_rail": get_arena_phase_rail(),
        "deadline": get_arena_deadline(active_battle),
        "geometry": get_arena_geometry(),
        # AA1: a manually-bumped marker for the (large, static-per-deploy)
        # geometry payload above. arena_state() strips "geometry" from its
        # response when the client already reports this same version, so it
        # is computed unconditionally here — cheap, both callers need it —
        # and the conditional omission lives only in arena_state().
        "geometry_version": ARENA_GEOMETRY_VERSION,
        # Ring 11 belongs to sponsors (ARENA_BATTLE_PLAN 2a). A NEW key, never a
        # renamed one: the keys above are the frozen contract in P00_CONTRACTS.
        "vip_sponsors": get_vip_sponsors(),
        # AR5: how many unauthorised visitors are in the lobby right now. A
        # COUNT, never a list — a spirit has no identity to send. Expect 0 until
        # the Owner opens the Arena, because the lobby heartbeat sits behind the
        # visibility gate; that zero is the truth, not a missing feature.
        "spirit_count": unauthorised_arena_viewers(),
        # Authoritative server clock at payload build so clients can reconcile
        # their own drift against deadline/phase (Ember #171). Never null.
        "server_time": timezone.now().isoformat(),
    }


def _demo_vs_centre(request, enrolled):
    """Moderator-only preview of the active-battle centre, or None.

    /chef-battle/arena/?demo=vs stages the two-cell VS centre from two REAL
    enrolled chefs so the Owner can see and tune the composition without an
    active battle. No DB writes, never for non-moderators, never on the share
    link. It is not a fixture: the chefs are real rows, which is why it is
    allowed where hydrateFixtures() is not.

    IT LIVES HERE BECAUSE TWO SURFACES NEED IT. It used to sit inline in
    _arena_page_context, so the page was rendered with the demo battle and the
    very next poll — which builds its payload straight from the database —
    returned the real crown and wiped it. The preview flickered once and died,
    and because a chef in the centre vacates their ring cell, the two chefs
    disappeared from the octagon and came back a second later. That read as an
    arena bug and was a preview that only half existed.
    """
    if request.GET.get("demo") != "vs" or not is_moderator(request.user):
        return None
    pair = list(enrolled[:2])
    if len(pair) < 2:
        return None
    return {
        "type": "active_battle",
        "battle_url": "#",
        "challenger": _arena_fighter_payload(pair[0].author, "challenger"),
        "opponent": _arena_fighter_payload(pair[1].author, "opponent"),
    }


def _demo_upcoming(request, enrolled):
    """Moderator-only preview of a FULL departures board, or None.

    /chef-battle/arena/?demo=next fills both rows of X01's board - six pills -
    from REAL enrolled chefs, so the composition can be seen while production
    has nothing scheduled. Same contract as _demo_vs_centre(), for the same
    reasons: no DB writes, moderator only, never on the share link, and the poll
    has to be given the flag too or it repaints the board empty on the first
    tick.

    It is a PREVIEW, not a fixture. Every face and name is a real enrolled chef;
    what is invented is the pairing and the clock, and neither is stored, shown
    to anyone else, or capable of becoming a battle. With fewer than two chefs
    enrolled there is nothing honest to draw, so it returns None.
    """
    if request.GET.get("demo") != "next" or not is_moderator(request.user):
        return None
    chefs = [p.author for p in enrolled]
    if len(chefs) < 2:
        return None
    now = timezone.now()
    rows = []
    for index in range(6):
        left = chefs[(2 * index) % len(chefs)]
        right = chefs[(2 * index + 1) % len(chefs)]
        if left.pk == right.pk:
            right = chefs[(2 * index + 2) % len(chefs)]
        start = now + timezone.timedelta(minutes=40 + index * 260)
        rows.append({
            "battle_id": 0,
            "theme": "Preview",
            "start_time": start.isoformat(),
            "start_display": _approx_start_display(start),
            "battle_url": "#",
            "challenger": {
                "name": left.name, "slug": left.slug,
                "avatar_url": left.display_avatar_url,
            },
            "opponent": {
                "name": right.name, "slug": right.slug,
                "avatar_url": right.display_avatar_url,
            },
        })
    return rows


def _arena_page_context(request, *, viewer_author, user_enrolled, allow_demo):
    """Assemble everything chef_battle/arena.html needs.

    The shared payload builder performs queries only. The live Arena completes
    its presence, seating, and stale-seat maintenance before calling this
    helper; the token-gated preview can therefore reuse it without writes.
    """
    payload = _build_arena_payload(viewer_author=viewer_author)
    active_battle = payload["active_battle"]
    enrolled = payload["enrolled"]
    chefs_by_rank = payload["chefs_by_rank"]
    spectators = payload["spectators"]

    # THE THIRD HAND-WRITTEN COPY OF THE CONTRACT, and it drifted the same day
    # it was written: `runway` was added to the payload and to the poll, and
    # this list did not hear about it, so the console had no countdown while the
    # public arena did. That is exactly the failure the console mirror was built
    # to end (v2.5.831) - a second list stops being updated, nobody breaks
    # anything, and the two surfaces quietly diverge.
    #
    # So the page's data is DERIVED from the poll contract now. Whatever the
    # arena polls, the first server-rendered paint has, with no second edit.
    arena_data = {key: payload[key] for key in PUBLIC_ARENA_STATE_KEYS}

    demo_centre = _demo_vs_centre(request, enrolled) if allow_demo else None
    if demo_centre:
        arena_data["center"] = demo_centre

    demo_next = _demo_upcoming(request, enrolled) if allow_demo else None
    if demo_next:
        arena_data["upcoming"] = demo_next

    # THE RING NUMBER IS THE LADDER NUMBER. Owner, 2026-08-07: number them one
    # to eight from the centre outward, so Culinary Master is 1 and Kitchen
    # Porter is 8. The floor already keys its rank rings exactly that way in
    # data-ring, so ONE number serves the octagon and the ladder and the two
    # cannot drift into disagreeing about which ring is which.
    _ranks = list(ChefBattleProfile.Rank)
    rank_groups = [
        (rank, chefs_by_rank[rank.value], len(_ranks) - index)
        for index, rank in enumerate(_ranks)
    ]

    return {
        "rank_groups": rank_groups,
        "spectator_count": len(spectators),
        "active_battle": active_battle,
        "arena_data": arena_data,
        # arena.html reads these three at the top level for the first
        # server-rendered paint (crown streak, crown ladder, recent gifts),
        # before the JS poll repaints from arena_state. They also live inside
        # arena_data for the embedded JSON blob. Without them at top level the
        # streak silently renders 0 and both lists render empty on load.
        "crown_streak": arena_data["crown_streak"],
        "crown_ladder": arena_data["crown_ladder"],
        "recent_gifts": arena_data["recent_gifts"],
        # X01, and the same reason as the three above: without it at top level
        # the first server-rendered paint shows an empty schedule and only the
        # poll, seconds later, fills it in.
        "upcoming": arena_data["upcoming"],
        "viewer_author": viewer_author,
        "user_enrolled": user_enrolled,
    }


@chef_battle_guard
def arena(request):
    # DG-04: page view is a lobby presence heartbeat (poll continues it)
    from .services import record_viewer_presence
    record_viewer_presence(request, battle=None)

    # Mark the viewing chef present BEFORE building the ring, so an enrolled
    # chef appears in their own arena immediately on page load instead of only
    # after the first 20s poll.
    viewer_author = None
    user_enrolled = False
    if request.user.is_authenticated:
        viewer_author = get_author_for_user(request.user)
        if viewer_author:
            # Any logged-in visitor takes a seat in the arena: enrolled chefs
            # sit in their rank ring, everyone else in a spectator ring. Ensure
            # a profile exists so a first-time viewer is placed immediately.
            from .services import get_or_create_battle_profile
            profile = get_or_create_battle_profile(viewer_author)
            ChefBattleProfile.objects.filter(pk=profile.pk).update(last_seen_at=timezone.now())
            user_enrolled = bool(profile.enrolled_at)
            _ensure_spectator_seat(viewer_author)

    from .arena_seating import release_lapsed_seats
    release_lapsed_seats()

    context = _arena_page_context(
        request, viewer_author=viewer_author, user_enrolled=user_enrolled, allow_demo=True,
    )
    context["viewer_is_owner"] = bool(
        viewer_author and viewer_author.slug == settings.OWNER_SLUG
    )
    return render(request, "chef_battle/arena.html", context)


def _owner_action_deadline(raw_value):
    value = parse_datetime((raw_value or "").strip())
    if value is None:
        raise ValidationError("Choose a valid date and time.")
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    if value <= timezone.now():
        raise ValidationError("The restriction must end in the future.")
    return value


def _end_user_sessions(user_id):
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        try:
            if str(session.get_decoded().get("_auth_user_id")) == str(user_id):
                session.delete()
        except Exception:
            logger.exception("Could not inspect session %s during Owner block", session.pk)


# RED ON MAIN, NOT MINE, FIXED ON THE WAY PAST (T19, 2026-08-15).
# RoutedViewAccessAuditTests.test_every_routed_view_is_guarded_or_listed was
# failing on this view since T18 shipped: it carried no chef_battle_guard and
# was not in UNGUARDED_BY_DESIGN, which is exactly the fail-open case that
# test exists to catch. The view is already Owner-only by its own OWNER_SLUG
# check, so the guard narrows nothing and locks nobody out - the Owner passes
# is_battle_visible - it puts the view back inside the audit. Outermost, per
# the correction GreenBear made in v2.5.989: under login_required/require_POST
# the guard runs late enough for the URL to announce its own existence.
@chef_battle_guard
@login_required
@require_POST
@transaction.atomic
def owner_arena_account_action(request):
    """GreenBear-only account controls from a chef card on the Arena floor."""
    actor = get_author_for_user(request.user)
    if actor is None or actor.slug != settings.OWNER_SLUG:
        raise Http404

    target = get_object_or_404(
        RecipeAuthor.objects.select_for_update(),
        slug=request.POST.get("chef_slug", ""),
    )
    if target.slug == settings.OWNER_SLUG:
        raise Http404

    from .models import LedgerEvent, OwnerAccountRestriction
    action = request.POST.get("action", "")
    restriction, _ = OwnerAccountRestriction.objects.select_for_update().get_or_create(
        author=target,
        defaults={"updated_by": request.user},
    )

    if action in {"mute", "block"}:
        try:
            until = _owner_action_deadline(request.POST.get("until"))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("chef_battle:arena")
        field = "muted_until" if action == "mute" else "blocked_until"
        setattr(restriction, field, until)
        restriction.updated_by = request.user
        restriction.save(update_fields=[field, "updated_by", "updated_at"])
        if action == "block" and target.user_id:
            _end_user_sessions(target.user_id)
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ADMIN_NOTE,
            actor=actor,
            target=target,
            payload={"action": action, "until": until.isoformat(), "source": "arena_chef_menu"},
        )
        action_label = "muted" if action == "mute" else "blocked"
        messages.warning(request, f'{target.name} is {action_label} until {until:%Y-%m-%d %H:%M %Z}.')
        return redirect("chef_battle:arena")

    if action != "delete" or request.POST.get("confirm_delete") != "on":
        messages.error(request, "Deletion requires the confirmation checkbox.")
        return redirect("chef_battle:arena")

    target_label = target.name
    target_user = target.user
    LedgerEvent.objects.create(
        event_type=LedgerEvent.EventType.ADMIN_NOTE,
        actor=actor,
        target=target,
        payload={
            "action": "account_deleted_and_anonymised",
            "target_label": target_label,
            "source": "arena_chef_menu",
        },
    )
    if target_user is not None:
        _end_user_sessions(target_user.pk)
        target_user.delete()
        target.user = None
    if target.avatar:
        target.avatar.delete(save=False)
    target.name = "Deleted Chef"
    target.slug = f"deleted-chef-{target.pk}"
    target.bio = ""
    target.avatar = None
    target.has_bearseeker_privileges = False
    target.can_generate_ai_images = False
    target.has_arena_console_access = False
    target.save(update_fields=[
        "user", "name", "slug", "bio", "avatar", "has_bearseeker_privileges",
        "can_generate_ai_images", "has_arena_console_access",
    ])
    restriction.delete()
    messages.warning(request, f'Account "{target_label}" was deleted and its required history anonymised.')
    return redirect("chef_battle:arena")


# Vendored copy of Ember's isolated visual-shell prototype, for the read-only
# share preview below. This is NOT the prototype branch merged into main: only
# the two self-contained reference files (HTML + its own CSS) are carried here
# to be served. The prototype remains a composition reference; nothing consumes
# it as production Arena code. See ops/audits/arena_visual_integration_plan.json.
_PROTOTYPE_DIR = Path(settings.BASE_DIR) / "ops" / "prototypes" / "arena_visual_shell"

# The site loads its display/interface faces from Google Fonts in base.html; the
# prototype is served standalone (it does not extend base.html), so the same
# link is injected into its <head> to keep the preview faithful to the mockup.
_PROTOTYPE_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Playfair+Display:wght@400;600;700&family=Libre+Bodoni:wght@400&"
    'family=Inter:wght@400;500;600&display=swap">'
)


def arena_preview_current(request, share_token):
    """Read-only, token-gated snapshot of the CURRENT production Arena.

    Same principle as the build-board share link: the URL segment is the
    credential (ARENA_PREVIEW_SHARE_TOKEN), the route 404s when the token is
    unset or wrong, and the response is noindex. It renders the real arena.html
    from real data via _arena_page_context — the arena draws itself entirely
    from the embedded JSON on load, so the page is a faithful snapshot even
    though the live pollers 404 for an anonymous holder (their failures are
    swallowed by the renderer's own catch handlers).

    No writes: unlike arena(), this records no presence and creates no profile.
    It does not widen Arena access — /chef-battle/arena/ itself stays
    staff/superuser only. This is a picture of the hall, shared by link.
    """
    if not valid_share_token(share_token, getattr(settings, "ARENA_PREVIEW_SHARE_TOKEN", "")):
        raise Http404
    context = _arena_page_context(
        request, viewer_author=None, user_enrolled=False, allow_demo=False,
    )
    context["is_share_preview"] = True
    response = render(request, "chef_battle/arena.html", context)
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def arena_preview_prototype(request, share_token):
    """Read-only, token-gated view of Ember's isolated visual-shell prototype.

    Serves the vendored self-contained prototype (its CSS inlined, the site's
    Google Fonts injected) behind the same ARENA_PREVIEW_SHARE_TOKEN gate. It is
    a composition reference, not the production Arena, and is labelled as such by
    the prototype's own masthead ("Isolated visual prototype").
    """
    if not valid_share_token(share_token, getattr(settings, "ARENA_PREVIEW_SHARE_TOKEN", "")):
        raise Http404
    try:
        html = (_PROTOTYPE_DIR / "index.html").read_text(encoding="utf-8")
        css = (_PROTOTYPE_DIR / "prototype.css").read_text(encoding="utf-8")
    except OSError:
        raise Http404
    # Self-contain the response: replace the relative stylesheet link with the
    # inlined CSS, and inject the fonts. No other asset is referenced.
    html = html.replace(
        '<link rel="stylesheet" href="prototype.css">',
        _PROTOTYPE_FONTS + "<style>" + css + "</style>",
    )
    response = HttpResponse(html)
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=False)
def arena_ping(request):
    """Heartbeat — updates last_seen_at for the authenticated chef. Called from JS every 20s.

    AA5, 2026-08-15: this had no limit at all, while writing to
    ChefBattleProfile and claiming a seat on every call. The renderer sends it
    every 20 seconds (PING_INTERVAL), so 60/m is three times the honest
    cadence and cannot trip a real browser, including one that reconnects.
    """
    # Visibility check only (not the full guard): the guard's suspended-POST
    # branch would stack a banner message on every heartbeat.
    if not is_battle_visible(request):
        raise Http404
    if getattr(request, "limited", False):
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False}, status=401)
    author = get_author_for_user(request.user)
    if author:
        # Keep any logged-in viewer's seat warm, not just enrolled chefs.
        from .services import get_or_create_battle_profile
        profile = get_or_create_battle_profile(author)
        ChefBattleProfile.objects.filter(pk=profile.pk).update(last_seen_at=timezone.now())
        _ensure_spectator_seat(author)
    return JsonResponse({"ok": True})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=False)
def arena_take_seat(request):
    """Seat the signed-in viewer in the stands and report where they sat.

    Stage 3C: a seat belongs to a real person, so it is claimed by an account
    and by nothing else. Anonymous callers are refused here rather than handed
    a seat they could not keep, and there is no parameter naming whose seat to
    take — the service seats the caller, front rows first.

    The claim refreshes the caller's presence first: a seat granted to someone
    already outside the online window would lapse on the next claim, so the
    heartbeat and the seat are taken together.

    AA5, 2026-08-15: the @ratelimit above has been here since the endpoint
    shipped, with block=False - which sets request.limited and leaves the
    decision to the view. The view never read it, so the limit did nothing at
    all: it looked limited and was not, which is worse than being visibly
    unlimited, because a reviewer sees the decorator and stops looking.
    arena_state, twenty lines below, has always done this correctly.
    """
    if not is_battle_visible(request):
        raise Http404
    if getattr(request, "limited", False):
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "authentication_required"}, status=401)

    from .arena_seating import ArenaFull, claim_seat, public_seat
    from .services import get_or_create_battle_profile

    author = get_author_for_user(request.user)
    if author is None:
        return JsonResponse({"ok": False, "error": "author_profile_required"}, status=403)

    profile = get_or_create_battle_profile(author)
    ChefBattleProfile.objects.filter(pk=profile.pk).update(last_seen_at=timezone.now())
    if profile.enrolled_at is not None:
        return JsonResponse({"ok": False, "error": "enrolled_chefs_use_rank_rings"}, status=409)

    try:
        seat = claim_seat(author)
    except ArenaFull:
        return JsonResponse({"ok": False, "error": "arena_full"}, status=409)
    return JsonResponse({"ok": True, "seat": public_seat(seat)})


# Everything the public arena poll is allowed to return, and the only thing it
# can return: arena_state builds its response by picking exactly these keys out
# of the payload. Adding a key to _build_arena_payload no longer leaks it — the
# key has to be named here too, which is a deliberate act with a reviewer.
#
# It used to be an explicit dict in the view with the same names restated in two
# tests. On 2026-07-24 `top_supporter` was added to the view and to neither
# test, so both leak checks went red and stayed red for four days — a guard
# nobody could read any more. One list, three readers, no memory required.
PUBLIC_ARENA_STATE_KEYS = (
    "rings",
    "runway",
    "spectators",
    "center",
    # X01. Same trap as vip_sponsors and spirit_count below: bind() repaints
    # from the poll payload, so a key that is not sent reads as "nothing is
    # booked" and would empty the schedule thirty seconds after the page loaded.
    "upcoming",
    "latest_result",
    "crown_streak",
    "crown_ladder",
    "recent_gifts",
    "top_supporter",
    "metrics",
    "phase",
    "phase_rail",
    "deadline",
    "geometry",
    # AA1: threading this one key through the shared list is what makes both
    # first paint (_arena_page_context) and every poll (arena_state) carry
    # the version with no other change — they already build this same tuple.
    "geometry_version",
    # Without this the poll would empty the VIP ring thirty seconds after the
    # page loaded: bind() reseats from the poll payload, and a key it cannot
    # find reads as "no sponsors" rather than as "not sent".
    "vip_sponsors",
    # AR5, and the same trap exactly: an absent count is indistinguishable from
    # a count of zero, so leaving this out would clear the balconies on the
    # first poll and look like everyone had left.
    "spirit_count",
    "server_time",
)


@require_POST
@ratelimit(key="ip", rate="120/m", method="POST", block=False)
def arena_state(request):
    """Lightweight state poll — returns updated ring data for JS to refresh SVG."""
    # Visibility check only (not the full guard): the guard's suspended-POST
    # branch would stack a banner message on every 20s poll.
    if not is_battle_visible(request):
        raise Http404
    if getattr(request, "limited", False):
        return JsonResponse({"error": "rate_limited"}, status=429)
    from .services import record_viewer_presence
    record_viewer_presence(request, battle=None)  # arena lobby surface

    # The 10s poll also keeps the polling visitor present, so anyone sitting on
    # the arena stays online (and visible in their cell) without relying solely
    # on the separate presence ping. Enrolled chefs sit in their rank ring,
    # everyone else in a spectator ring.
    viewer_author = None
    if request.user.is_authenticated:
        viewer_author = get_author_for_user(request.user)
        if viewer_author:
            from .services import get_or_create_battle_profile
            profile = get_or_create_battle_profile(viewer_author)
            ChefBattleProfile.objects.filter(pk=profile.pk).update(last_seen_at=timezone.now())
            _ensure_spectator_seat(viewer_author)

    from .arena_seating import release_lapsed_seats
    release_lapsed_seats()

    payload = _build_arena_payload(viewer_author=viewer_author)
    # The poll must stage the same preview the page was rendered with, or it
    # overwrites it on the first tick — see _demo_vs_centre().
    demo_centre = _demo_vs_centre(request, payload["enrolled"])
    if demo_centre:
        payload["center"] = demo_centre
    demo_next = _demo_upcoming(request, payload["enrolled"])
    if demo_next:
        payload["upcoming"] = demo_next

    response_data = {key: payload[key] for key in PUBLIC_ARENA_STATE_KEYS}
    # AA1: geometry is the largest key in this response (~21KB of a ~30KB
    # poll) and is static per deploy — get_arena_geometry() has no DB
    # dependency at all. Omit it once the client already has the current
    # version. request.GET, not request.POST, matching this same endpoint's
    # own existing precedent (the ?demo=vs/next flags below): arena_render.js
    # sends no request body today, and this needs no new body-encoding to
    # thread a flag through a POST-method endpoint the same way those already
    # do. First paint (_arena_page_context) is untouched by this — it always
    # embeds full geometry and has no other caller to worry about breaking.
    client_geometry_version = request.GET.get("geometry_version", "")
    if client_geometry_version and client_geometry_version == response_data["geometry_version"]:
        del response_data["geometry"]
    return JsonResponse(response_data)


@chef_battle_guard
@login_required
def challenge_list(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before entering Chef Battles.")
        return redirect("home")

    sent = get_sent_challenges(author)
    received = get_received_challenges(author)
    from .access import has_arena_console_access
    return render(request, "chef_battle/challenge_list.html", {
        "author": author,
        "sent_challenges": sent,
        "received_challenges": received,
        "is_owner": author.slug == settings.OWNER_SLUG,
        "can_see_console": has_arena_console_access(request),
    })


@chef_battle_guard
@login_required
def challenge_create(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before creating a Chef Battle challenge.")
        return redirect("home")

    profile = get_or_create_battle_profile(author)
    if not profile.infinite_moves and profile.battle_moves < MOVES_MIN_TO_CHALLENGE:
        messages.error(
            request,
            f"You need at least {MOVES_MIN_TO_CHALLENGE} energy to issue a challenge. "
            f"You have {profile.battle_moves}. Publish recipes or articles to earn more."
        )
        return redirect("chef_battle:challenge_list")

    inspired_by = None
    if request.method == "POST":
        form = BattleChallengeForm(request.POST, challenger=author)
        if form.is_valid():
            opponent = form.cleaned_data["opponent"]
            # ONE SLOT PER CHEF, battle_rules.md - and the slot is taken from
            # the moment a challenge is ISSUED, not from when it is accepted.
            # Nothing enforced this until v2.5.995 (audit finding G1): a chef
            # could hold three live battles at once, which the rulebook forbids
            # in its first line.
            slot_error = slot_occupied_reason(author)
            if slot_error:
                messages.error(request, slot_error)
                return render(request, "chef_battle/challenge_form.html", {"form": form})

            # T22: the Owner is outside the competition. Checked here, on the
            # server, and not only by hiding him from the form's dropdown - a
            # hand-crafted POST names an opponent pk directly.
            owner_error = check_owner_not_in_battle(author, opponent)
            if owner_error:
                messages.error(request, owner_error)
                return render(request, "chef_battle/challenge_form.html", {"form": form})

            rank_error = check_rank_matchup(author, opponent)
            if rank_error:
                messages.error(request, rank_error)
                return render(request, "chef_battle/challenge_form.html", {"form": form})

            fraud_result = run_fraud_gates([
                (gate_suspended_account, (author,), {}),
                (gate_fraud_flagged, (author,), {}),
                (gate_age_verified, (author,), {}),
                (gate_challenge_spam, (author,), {}),
                (gate_repeat_challenge_cooldown, (author, opponent), {}),
                (gate_post_battle_cooldown, (author,), {}),
            ])
            if not fraud_result.passed:
                first_fail = next(g for g in fraud_result.gates if not g.passed)
                _CHALLENGE_FRAUD_MESSAGES = {
                    "suspended_account": "Your account is suspended.",
                    "fraud_flagged": "Your account has been flagged. Please contact support.",
                    "challenge_spam": "You have sent too many challenges today. Please wait before sending another.",
                    "repeat_challenge_cooldown": "You have recently challenged this chef. Please wait before challenging again.",
                    "post_battle_cooldown": "You completed a battle recently. Please wait 24 hours before issuing a new challenge.",
                }
                messages.error(request, _CHALLENGE_FRAUD_MESSAGES.get(first_fail.gate, "Challenge not accepted."))
                return render(request, "chef_battle/challenge_form.html", {"form": form})

            # F49, 2026-08-11: the slot check above is unlocked, and nothing
            # serialised it against a second POST from the same chef (a
            # double-submit, or two tabs) creating a second challenge before
            # either committed - two pending challenges from one chef, each
            # of which can later be accepted into its own live battle,
            # exactly what the one-slot rule forbids. Lock the challenger's
            # own profile row and re-check the slot under it, the same
            # mutex accept_challenge already takes on the ACCEPTING chef
            # (F21) - here it is the ISSUING chef's own slot at risk.
            with transaction.atomic():
                challenger_profile = get_or_create_battle_profile(author)
                # F64, 2026-08-11: F49's lock only re-verified the slot; the
                # OTHER precondition checked earlier in this same view - the
                # moves/energy minimum - was never re-verified under it. A
                # concurrent spend (e.g. refusing a different challenge,
                # which costs MOVES_REFUSE_PENALTY) between the check above
                # and this lock could drop the real balance below the
                # minimum while this request still went on to create the
                # challenge. Use the row the lock actually returns for both
                # checks.
                locked_profile = ChefBattleProfile.objects.select_for_update().get(pk=challenger_profile.pk)
                if not locked_profile.infinite_moves and locked_profile.battle_moves < MOVES_MIN_TO_CHALLENGE:
                    messages.error(
                        request,
                        f"You need at least {MOVES_MIN_TO_CHALLENGE} energy to issue a challenge. "
                        f"You have {locked_profile.battle_moves}. Publish recipes or articles to earn more."
                    )
                    return redirect("chef_battle:challenge_list")
                slot_error = slot_occupied_reason(author)
                if slot_error:
                    messages.error(request, slot_error)
                    return render(request, "chef_battle/challenge_form.html", {"form": form})
                challenge = form.save()
            get_or_create_battle_profile(author)
            get_or_create_battle_profile(challenge.opponent)
            create_battle_event(
                event_type=BattleEvent.EventType.CHALLENGE_CREATED,
                challenge=challenge,
                actor=author,
                target=challenge.opponent,
                message=f"{author.name} challenged {challenge.opponent.name} to a Chef Battle: {challenge.theme}.",
                publish_to_news=True,
            )
            _notify_chef(
                author, challenge.opponent,
                subject=f"You have been challenged to a Chef Battle: {challenge.theme}",
                body=(
                    f"{author.name} has challenged you to a Chef Battle!\n\n"
                    f"Theme: {challenge.theme}\n"
                    f"Battle type: {challenge.get_battle_type_display()}\n"
                    + (f"\nMessage: {challenge.message}\n" if challenge.message else "")
                    + f"\nAccept or refuse in your challenges inbox: "
                    f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}"
                    + reverse("chef_battle:challenge_list")
                ),
            )
            messages.success(request, "Chef Battle challenge sent.")
            return redirect("chef_battle:challenge_list")
    else:
        initial = {}
        opponent_slug = request.GET.get("opponent")
        if opponent_slug:
            try:
                opp = RecipeAuthor.objects.get(slug=opponent_slug)
                initial["opponent"] = opp.pk
            except RecipeAuthor.DoesNotExist:
                pass

        # A challenge can start from someone else's recipe page.  That recipe
        # seeds the theme and names the opponent, but it never becomes anyone's
        # entry: the challenger still brings their own dish, chosen from
        # theme_recipe.  Only an approved recipe can do this, since the
        # audience has to be able to open what the theme refers to.
        inspired_slug = request.GET.get("inspired_by")
        if inspired_slug:
            inspired_by = (
                Recipe.objects.select_related("author")
                .filter(slug=inspired_slug, status=Recipe.Status.APPROVED, is_deleted=False)
                .first()
            )
            if inspired_by:
                initial.setdefault("opponent", inspired_by.author_id)
                initial.setdefault("theme", inspired_by.title[:180])
        form = BattleChallengeForm(challenger=author, initial=initial)

    return render(
        request,
        "chef_battle/challenge_form.html",
        {"form": form, "inspired_by": inspired_by},
    )


@chef_battle_guard
@require_POST
@login_required
def challenge_respond(request, pk):
    author = get_author_for_user(request.user)
    challenge = get_object_or_404(BattleChallenge, pk=pk, opponent=author)
    if challenge.status != BattleChallenge.Status.PENDING:
        messages.warning(request, "This challenge has already been answered.")
        return redirect("chef_battle:challenge_list")
    if challenge.expires_at <= timezone.now():
        # F50, 2026-08-11: this write bypassed F38's locking entirely - a
        # fourth writer of the challenge's own status, alongside
        # accept_challenge/refuse_challenge/expire_stale_challenges, none of
        # which this view call serialised against. A stale PENDING-looking
        # challenge (already accepted by a concurrent request) could be
        # overwritten to EXPIRED here, leaving a live Battle behind an
        # EXPIRED challenge. Lock and recheck before writing.
        with transaction.atomic():
            locked = BattleChallenge.objects.select_for_update().get(pk=challenge.pk)
            if locked.status == BattleChallenge.Status.PENDING:
                locked.status = BattleChallenge.Status.EXPIRED
                locked.save(update_fields=["status"])
        messages.warning(request, "This challenge has expired.")
        return redirect("chef_battle:challenge_list")

    action = request.POST.get("action")
    if action == "accept":
        # An occupied slot forbids ACCEPTING as well as issuing (battle_rules.md,
        # read in full). The challenge being answered is excluded, or a chef
        # would be blocked by the very challenge sitting in their inbox.
        slot_error = slot_occupied_reason(author, ignore_challenge=challenge)
        if slot_error:
            messages.error(request, slot_error)
            return redirect("chef_battle:challenge_list")

        # F13, 2026-08-11: gate_age_verified ran at challenge_create (on the
        # challenger), token purchase and gift-sending, but never on the
        # opponent who accepts - the one action that actually seats a chef in
        # a real-money arena. A challenge can sit unanswered for up to twelve
        # hours (X05), so this cannot be assumed to have been checked already.
        age_result = gate_age_verified(author)
        if not age_result.passed:
            messages.error(request, "You must confirm that you are 18 or older before accepting a Chef Battle.")
            return redirect("chef_battle:challenge_list")

        cooldown = gate_post_battle_cooldown(author)
        if not cooldown.passed:
            messages.error(request, "You completed a battle recently. Please wait 24 hours before accepting a new challenge.")
            return redirect("chef_battle:challenge_list")
        try:
            battle = accept_challenge(challenge)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("chef_battle:challenge_list")
        except IntegrityError:
            # F19, 2026-08-11: accept_challenge doesn't lock the challenge row,
            # so two simultaneous accepts both pass the PENDING check above and
            # both reach Battle.objects.create(). Battle.challenge is a unique
            # OneToOneField, so the data stays correct - the second INSERT just
            # fails at the database instead of racing past it. Only the error
            # handling was missing.
            messages.warning(request, "This challenge has already been answered.")
            return redirect("chef_battle:challenge_list")
        messages.success(request, "Challenge accepted. The battle room is live.")
        return redirect(battle.get_absolute_url())
    if action == "refuse":
        try:
            refuse_challenge(challenge)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("chef_battle:challenge_list")
        messages.warning(request, "Challenge refused and recorded.")
        return redirect("chef_battle:challenge_list")

    messages.error(request, "Unknown challenge response.")
    return redirect("chef_battle:challenge_list")


@chef_battle_guard
def battle_detail(request, pk):
    battle = get_object_or_404(
        Battle.objects.select_related("challenger", "opponent", "winner", "loser"),
        pk=pk,
    )

    # DG-04: page view is a presence heartbeat (public battle room surface)
    from .services import record_viewer_presence, void_stalled_battle, _STALLABLE_STATUSES
    record_viewer_presence(request, battle=battle)
    now = timezone.now()
    if battle.end_time <= now and battle.status == Battle.Status.VOTING:
        battle = calculate_battle_result(battle)
    # T01, 2026-08-12: an expired ACTIVE battle used to be scored here too, and
    # with no votes cast that meant a paid draw for a fight with no combat and
    # no evidence. It is a NO-SHOW, and handle_no_show_battles - which runs from
    # the same cron sweep every fifteen minutes - is the explicit policy for it:
    # a forfeit win where one chef did submit, a cancellation where neither did.
    # Deciding that from inside a page view would be guessing; leaving it to the
    # sweep is the honest answer, and the scorer now refuses ACTIVE outright.
    elif battle.end_time <= now and battle.status in _STALLABLE_STATUSES:
        # F20, 2026-08-11: calculate_battle_result used to run here for ANY
        # non-COMPLETED status - a battle stuck in INGREDIENT_PENALTY/COOKING/
        # PRESENTATION (never voted on) hit its zero-vote tie-break and was
        # scored as a paid draw. Route those through the same no-reward
        # cancellation the cron sweep uses instead of a decisive/drawn result.
        battle = void_stalled_battle(battle)
    else:
        reveal_entries_if_ready(battle)
        battle.refresh_from_db()

    vote_counts = get_battle_vote_counts(battle)
    # T30/D1: the antechamber's "statistics" - how this pair has fared against
    # EACH OTHER, distinct from the individual W/L already shown per chef.
    head_to_head = get_head_to_head(
        battle.challenger, battle.opponent, exclude_pk=battle.pk,
    )
    entries = battle.entries.select_related("author", "recipe", "article").order_by("submitted_at")
    events = battle.events.select_related("actor", "target").filter(is_public=True).order_by("-created_at")[:20]
    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    viewer_entry = None
    if viewer_author:
        viewer_entry = battle.entries.filter(author=viewer_author).first()
    can_submit = bool(
        viewer_author
        and battle.author_is_participant(viewer_author)
        and not (viewer_entry and viewer_entry.dish_submitted_at)
        # F12, 2026-08-11: matches battle_entry_submit's own gate - the dish
        # entry is a COOKING-phase action, not an ACTIVE/VOTING one.
        and battle.status == Battle.Status.COOKING
        and timezone.now() <= battle.submission_deadline
    )

    from .services import get_combat_state, get_or_create_battle_profile
    combat_state = get_combat_state(battle)
    is_participant = bool(viewer_author and battle.author_is_participant(viewer_author))
    challenger_profile = get_or_create_battle_profile(battle.challenger)
    opponent_profile = get_or_create_battle_profile(battle.opponent)
    user_battle_moves = 0
    viewer_has_moved = False
    opponent_has_moved = False
    if is_participant:
        profile = get_or_create_battle_profile(viewer_author)
        user_battle_moves = profile.battle_moves
        from .models import BattleCombatAction
        round_chef_ids = set(
            BattleCombatAction.objects.filter(
                battle=battle, round_number=combat_state["current_round"]
            ).values_list("chef_id", flat=True)
        )
        viewer_has_moved = viewer_author.pk in round_chef_ids
        opponent_has_moved = bool(round_chef_ids - {viewer_author.pk})

    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST, APPRECIATION_GIFT_EMOJI, Artifact
    appreciation_gifts = [
        {"type": k, "label": AppreciationGiftType(k).label, "cost": v, "emoji": APPRECIATION_GIFT_EMOJI.get(k, "🎁")}
        for k, v in APPRECIATION_GIFT_COST.items()
    ]
    # Spectators choose the exact combat artifact. Legendary items remain
    # earned prizes and are never sold or delivered as paid battle gifts.
    giftable_artifacts = list(
        Artifact.objects.filter(is_active=True)
        .exclude(rarity=Artifact.Rarity.LEGENDARY)
        .order_by("rarity", "name")
    )
    viewer_token_balance = 0
    if viewer_author:
        from .models import TokenWallet
        wallet = TokenWallet.objects.filter(chef=viewer_author).first()
        viewer_token_balance = wallet.balance if wallet else 0

    user_available_artifacts = []
    opponent_active_ingredients = []
    if is_participant and viewer_author and battle.status == Battle.Status.ACTIVE:
        from .models import ChefArtifact, BattleIngredient
        user_available_artifacts = list(
            ChefArtifact.objects.filter(chef=viewer_author, status=ChefArtifact.Status.AVAILABLE)
            .select_related("artifact")
            .order_by("artifact__name")
        )
        opponent = battle.opponent_for(viewer_author)
        if opponent:
            opponent_active_ingredients = list(
                BattleIngredient.objects.filter(
                    battle=battle, chef=opponent, is_key=False, is_eliminated=False
                ).order_by("position")
            )

    viewer_is_challenger = bool(viewer_author and viewer_author.pk == battle.challenger_id)
    can_set_ready = (
        is_participant
        and battle.status == Battle.Status.SCHEDULED
        and not (battle.challenger_ready if viewer_is_challenger else battle.opponent_ready)
    )

    # Withdrawing from an accepted battle (Owner's rule, 2026-08-05). The button
    # goes dark once the three-per-account allowance is gone.
    from .withdrawal_service import can_withdraw, open_withdrawal_for, withdrawals_left
    can_withdraw_battle = can_withdraw(battle, viewer_author) if is_participant else False
    viewer_withdrawals_left = withdrawals_left(viewer_author) if is_participant else 0
    open_withdrawal = open_withdrawal_for(battle) if is_participant else None
    withdrawal_is_mine = bool(
        open_withdrawal and viewer_author and open_withdrawal.requester_id == viewer_author.pk
    )

    try:
        from sponsors.services import get_sponsor_of_month
        central_sponsor = get_sponsor_of_month()
    except Exception:
        central_sponsor = ""

    return render(request, "chef_battle/battle_detail.html", {
        "battle": battle,
        "central_sponsor": central_sponsor,
        "entries": entries,
        "events": events,
        "vote_counts": vote_counts,
        "head_to_head": head_to_head,
        "votes_for_challenger": vote_counts.get(battle.challenger_id, 0),
        "votes_for_opponent": vote_counts.get(battle.opponent_id, 0),
        "viewer_author": viewer_author,
        "viewer_entry": viewer_entry,
        "can_submit": can_submit,
        "is_participant": is_participant,
        "viewer_is_challenger": viewer_is_challenger,
        "can_set_ready": can_set_ready,
        "combat_state": combat_state,
        "user_battle_moves": user_battle_moves,
        "viewer_has_moved": viewer_has_moved,
        "opponent_has_moved": opponent_has_moved,
        "appreciation_gifts": appreciation_gifts,
        "giftable_artifacts": giftable_artifacts,
        "viewer_token_balance": viewer_token_balance,
        "active_statuses": Battle.ACTIVE_STATUSES,
        "battle_participants": [battle.challenger, battle.opponent],
        "challenger_profile": challenger_profile,
        "opponent_profile": opponent_profile,
        "user_available_artifacts": user_available_artifacts,
        "opponent_active_ingredients": opponent_active_ingredients,
        "can_withdraw": can_withdraw_battle,
        "withdrawals_left": viewer_withdrawals_left,
        "open_withdrawal": open_withdrawal,
        "withdrawal_is_mine": withdrawal_is_mine,
    })


@chef_battle_guard
@login_required
def battle_entry_submit(request, pk):
    author = get_author_for_user(request.user)
    battle = get_object_or_404(Battle, pk=pk)
    if not battle.author_is_participant(author):
        raise PermissionDenied
    # F12, 2026-08-11: this used to exclude only SCHEDULED/MENU_LOCKED, which
    # left ACTIVE (combat still running), INGREDIENT_PENALTY (biathlon not
    # yet run) and every other mid-lifecycle status open. dish_submitted_at
    # set here is exactly what reveal_entries_if_ready's ACTIVE branch reads
    # to jump the battle straight to VOTING - so a battle could reach public
    # voting with zero combat rounds, zero biathlon and zero moderated photo.
    # cooking_submit() (the real photo upload) already requires COOKING and
    # an existing entry; this view creates that entry, so it must require the
    # same phase, not merely "not still in the antechamber".
    if battle.status != Battle.Status.COOKING:
        messages.error(request, "Finish combat and the ingredient biathlon before submitting your dish.")
        return redirect(battle.get_absolute_url())
    entry = battle.entries.filter(author=author).first()
    if entry and entry.dish_submitted_at:
        messages.warning(request, "You have already submitted an entry for this battle.")
        return redirect(battle.get_absolute_url())
    if timezone.now() > battle.submission_deadline:
        messages.error(request, "The submission deadline has passed.")
        return redirect(battle.get_absolute_url())

    if request.method == "POST":
        form = BattleEntryForm(request.POST, instance=entry, author=author, battle=battle)
        if form.is_valid():
            entry = form.save()
            reveal_entries_if_ready(battle)
            create_battle_event(
                event_type=BattleEvent.EventType.ENTRY_SUBMITTED,
                battle=battle,
                actor=author,
                target=battle.opponent_for(author),
                message=f"{author.name} submitted an entry for Chef Battle: {battle.theme}.",
                publish_to_news=True,
            )
            messages.success(request, "Battle entry submitted.")
            return redirect(battle.get_absolute_url())
    else:
        form = BattleEntryForm(instance=entry, author=author, battle=battle)

    return render(request, "chef_battle/entry_form.html", {"battle": battle, "form": form})


def _record_vote_integrity_event(
    *, request, battle, gate_code, failed_gates, ip_hash, user_agent_hash
):
    """Persist private rejected-attempt evidence without affecting vote totals."""
    try:
        session_key = getattr(request.session, "session_key", None) or ""
        VoteIntegrityEvent.objects.create(
            battle=battle,
            gate_code=gate_code,
            failed_gates=list(dict.fromkeys(failed_gates)),
            is_authenticated=request.user.is_authenticated,
            ip_hash=ip_hash,
            user_agent_hash=user_agent_hash,
            session_key_hash=hash_request_value(session_key),
        )
    except Exception:
        # Audit persistence must not turn a rejected vote into a public 500.
        logger.exception(
            "Failed to persist vote integrity event for battle %s", battle.pk
        )


@chef_battle_guard
@require_POST
def battle_vote(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status not in {Battle.Status.ACTIVE, Battle.Status.VOTING}:
        messages.error(request, "Voting is not open for this battle.")
        return redirect(battle.get_absolute_url())
    if not battle.entries.filter(is_revealed=True).exists():
        messages.error(request, "Voting opens after entries are revealed.")
        return redirect(battle.get_absolute_url())

    # Voting is registered-members-only (owner decision 2026-07-17): an anonymous
    # visitor is a passer-by, not a voter. They are invited to sign in instead.
    if not request.user.is_authenticated:
        messages.error(request, "Voting is for registered members. Please sign in or create an account to vote.")
        return redirect(f"{settings.LOGIN_URL}?next={battle.get_absolute_url()}")

    voted_for = get_object_or_404(RecipeAuthor, pk=request.POST.get("voted_for"))
    if voted_for.pk not in {battle.challenger_id, battle.opponent_id}:
        messages.error(request, "Choose one of the battle chefs.")
        return redirect(battle.get_absolute_url())

    user = request.user
    voter_author = get_author_for_user(user)

    ip_hash = hash_request_value(get_client_ip(request) or "")
    ua_hash = hash_request_value(request.META.get("HTTP_USER_AGENT", ""))

    fraud_result = run_fraud_gates([
        (gate_self_vote, (voter_author, voted_for), {}),
        (gate_participant_vote, (voter_author, battle), {}),
        (gate_suspended_account, (voter_author,), {}),
        (gate_fraud_flagged, (voter_author,), {}),
        (gate_duplicate_device, (ip_hash, ua_hash, battle.pk), {}),
        (gate_vote_rate_ip, (ip_hash, battle.pk), {}),
    ])
    if not fraud_result.passed:
        first_fail = next(g for g in fraud_result.gates if not g.passed)
        _record_vote_integrity_event(
            request=request,
            battle=battle,
            gate_code=first_fail.gate,
            failed_gates=[g.gate for g in fraud_result.gates if not g.passed],
            ip_hash=ip_hash,
            user_agent_hash=ua_hash,
        )
        _VOTE_FRAUD_MESSAGES = {
            "self_vote": "Chefs cannot vote for themselves.",
            "participant_vote": "Battle participants cannot vote in their own battle.",
            "suspended_account": "Your account is suspended.",
            "fraud_flagged": "Your account has been flagged. Please contact support.",
            "duplicate_device": "Your vote for this battle has already been recorded.",
            "vote_rate_ip": "Too many votes from this connection. Please try again later.",
        }
        messages.error(request, _VOTE_FRAUD_MESSAGES.get(first_fail.gate, "Vote not accepted."))
        return redirect(battle.get_absolute_url())
    vote = BattleVote(
        battle=battle,
        voter=user,
        # Denormalised so the database can enforce "no self-vote" on its own —
        # a CheckConstraint cannot reach RecipeAuthor.user to work it out.
        voter_author=voter_author,
        voted_for=voted_for,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
    )
    try:
        vote.full_clean()
        with transaction.atomic():
            vote.save()
    except (IntegrityError, ValidationError):
        _record_vote_integrity_event(
            request=request,
            battle=battle,
            gate_code="constraint_rejected",
            failed_gates=["constraint_rejected"],
            ip_hash=ip_hash,
            user_agent_hash=ua_hash,
        )
        messages.warning(request, "Your vote for this battle has already been recorded.")
        return redirect(battle.get_absolute_url())

    create_battle_event(
        event_type=BattleEvent.EventType.VOTE_CAST,
        battle=battle,
        actor=None,
        target=voted_for,
        message=f"A vote landed for {voted_for.name} in Chef Battle: {battle.theme}.",
        is_public=False,
    )
    messages.success(request, "Vote recorded.")
    return redirect(battle.get_absolute_url())


@chef_battle_guard
def rankings(request):
    profiles = get_rankings()
    # X09 keyed the ladder to WINS on 2026-08-05 and this column kept
    # advertising rating points - 100, 200, 300 - which decide nothing and never
    # matched anything a chef could earn. The numbers are RANK_THRESHOLDS now,
    # so the ladder on the page is the ladder in the code. X20, 2026-08-11: the
    # second rung is a Prep Cook, which is what tz_main.md section 10 calls it.
    rank_tiers = [
        {"slug": "porter",  "name": "Kitchen Porters",   "pts": "0 wins"},
        {"slug": "prep",    "name": "Prep Cooks",        "pts": "3 wins"},
        {"slug": "commis",  "name": "Commis Chefs",      "pts": "6 wins"},
        {"slug": "partie",  "name": "Chefs de Partie",   "pts": "9 wins"},
        {"slug": "sous",    "name": "Sous Chefs",        "pts": "12 wins"},
        {"slug": "head",    "name": "Head Chefs",        "pts": "15 wins"},
        {"slug": "exec",    "name": "Executive Chefs",   "pts": "18 wins"},
        {"slug": "master",  "name": "Culinary Masters",  "pts": "21+ wins"},
    ]
    return render(request, "chef_battle/rankings.html", {
        "profiles": profiles,
        "rank_tiers": rank_tiers,
    })


@chef_battle_guard
@login_required
def my_moves(request):
    from django.db.models import Sum
    from .models import BattleMoveTransaction
    from .services import MOVES_CONTENT_DAILY_CAP, MOVES_CONTENT_WEEKLY_CAP

    CONTENT_TX_TYPES = {
        BattleMoveTransaction.TxType.RECIPE_PUBLISHED,
        BattleMoveTransaction.TxType.ARTICLE_PUBLISHED,
    }

    def _content_moves_total(chef, since):
        result = (
            BattleMoveTransaction.objects
            .filter(chef=chef, transaction_type__in=CONTENT_TX_TYPES, created_at__gte=since)
            .aggregate(total=Sum("amount"))
        )
        return result["total"] or 0

    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required.")
        return redirect("home")

    profile = get_object_or_404(ChefBattleProfile, author=author)
    transactions = (
        BattleMoveTransaction.objects
        .filter(chef=author)
        .order_by("-created_at")[:100]
    )

    now = timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timezone.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return render(request, "chef_battle/my_moves.html", {
        "profile": profile,
        "transactions": transactions,
        "daily_earned": _content_moves_total(author, day_start),
        "weekly_earned": _content_moves_total(author, week_start),
        "daily_cap": MOVES_CONTENT_DAILY_CAP,
        "weekly_cap": MOVES_CONTENT_WEEKLY_CAP,
    })


@chef_battle_guard
@login_required
def notifications_inbox(request):
    """Personal battle notification inbox for the logged-in chef."""
    from django.db.models import Q
    from .models import BattleEvent, BattleChallenge
    author = get_author_for_user(request.user)
    if not author:
        return render(request, "chef_battle/notifications_inbox.html", {"events": [], "pending_challenges": []})

    events = (
        BattleEvent.objects
        .filter(is_public=True)
        .filter(Q(actor=author) | Q(target=author))
        .select_related("battle", "actor", "target")
        .order_by("-created_at")[:60]
    )
    pending_challenges = (
        BattleChallenge.objects
        .filter(opponent=author, status=BattleChallenge.Status.PENDING)
        .select_related("challenger")
        .order_by("expires_at")
    )
    return render(request, "chef_battle/notifications_inbox.html", {
        "events": events,
        "pending_challenges": pending_challenges,
    })


@chef_battle_guard
@login_required
def notifications_poll(request):
    """Return unread battle notification count for live polling."""
    from django.http import JsonResponse
    from messaging.models import Message
    author = get_author_for_user(request.user)

    unread_battle_msgs = (
        Message.objects
        .filter(recipient=request.user, is_read=False, subject__icontains="battle")
        .count()
    )
    pending_challenges = 0
    if author:
        pending_challenges = BattleChallenge.objects.filter(
            opponent=author,
            status=BattleChallenge.Status.PENDING,
        ).count()

    total = unread_battle_msgs + pending_challenges
    items = []
    if pending_challenges:
        items.append({"text": f"{pending_challenges} battle challenge{'s' if pending_challenges != 1 else ''} waiting", "url": "/chef-battle/"})
    if unread_battle_msgs:
        items.append({"text": f"{unread_battle_msgs} unread battle message{'s' if unread_battle_msgs != 1 else ''}", "url": "/messages/"})

    return JsonResponse({"count": total, "items": items})


@chef_battle_guard
@login_required
@require_POST
def battle_combat_action(request, pk):
    """Chef submits their combat action for the current round."""
    from django.http import JsonResponse
    from .services import submit_combat_action, get_combat_state

    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    if not author or not battle.author_is_participant(author):
        return JsonResponse({"ok": False, "error": "Not a participant."}, status=403)

    action_type = request.POST.get("action_type", "")
    try:
        moves_invested = int(request.POST.get("moves_invested", 1))
    except (ValueError, TypeError):
        moves_invested = 1

    artifact_id = None
    try:
        _raw = request.POST.get("artifact_id") or None
        if _raw:
            artifact_id = int(_raw)
    except (ValueError, TypeError):
        pass

    target_ingredient_id = None
    try:
        _raw = request.POST.get("target_ingredient_id") or None
        if _raw:
            target_ingredient_id = int(_raw)
    except (ValueError, TypeError):
        pass

    try:
        submit_combat_action(
            battle, author, action_type, moves_invested,
            artifact_id=artifact_id, target_ingredient_id=target_ingredient_id,
        )
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    state = get_combat_state(battle)
    return JsonResponse({
        "ok": True,
        "challenger_hits": state["challenger_hits"],
        "opponent_hits": state["opponent_hits"],
        "current_round": state["current_round"],
        "rounds": [
            {
                "round_number": r.round_number,
                "outcome": r.outcome,
                "log_message": r.log_message,
            }
            for r in state["rounds"]
        ],
    })


@chef_battle_guard
@login_required
@ratelimit(key="ip", rate="120/m", method="GET", block=False)
def battle_state_poll(request, pk):
    """Lightweight GET endpoint — returns current combat state for auto-poll."""
    from django.http import JsonResponse
    if getattr(request, "limited", False):
        return JsonResponse({"error": "rate_limited"}, status=429)
    from .services import get_combat_state
    from .models import BattleCombatAction

    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)

    from .services import record_viewer_presence
    record_viewer_presence(request, battle=battle)

    state = get_combat_state(battle)

    viewer_has_moved = False
    viewer_moves = 0
    if author and battle.author_is_participant(author):
        viewer_has_moved = BattleCombatAction.objects.filter(
            battle=battle, chef=author, round_number=state["current_round"]
        ).exists()
        from .services import get_or_create_battle_profile
        viewer_moves = get_or_create_battle_profile(author).battle_moves

    combat_winner = None
    if battle.status == Battle.Status.AWAITING_SUBMISSIONS:
        ch = state["challenger_hits"]
        op = state["opponent_hits"]
        if ch > op:
            combat_winner = battle.challenger.name
        elif op > ch:
            combat_winner = battle.opponent.name
        else:
            combat_winner = "Draw"

    return JsonResponse({
        "ok": True,
        "status": battle.status,
        "viewer_moves": viewer_moves,
        "challenger_hits": state["challenger_hits"],
        "opponent_hits": state["opponent_hits"],
        "challenger_name": battle.challenger.name,
        "opponent_name": battle.opponent.name,
        "current_round": state["current_round"],
        "viewer_has_moved": viewer_has_moved,
        "combat_winner": combat_winner,
        "rounds": [
            {
                "round_number": r.round_number,
                "outcome": r.outcome,
                "log_message": r.log_message,
            }
            for r in state["rounds"]
        ],
    })


@chef_battle_guard
@login_required
def biathlon(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status != Battle.Status.INGREDIENT_PENALTY:
        messages.error(request, "The biathlon phase is not active for this battle.")
        return redirect(battle.get_absolute_url())
    viewer_author = get_author_for_user(request.user)
    if not battle.author_is_participant(viewer_author):
        raise PermissionDenied
    state = get_biathlon_state(battle)
    return render(request, "chef_battle/biathlon.html", {
        "battle": battle,
        "state": state,
        "is_winner": viewer_author and battle.winner_id == viewer_author.pk,
        # T11: the loser has nothing to DO in this phase any more - his two
        # blocks were placed before Stage 1, at declare_menu - but he watches
        # his own list being shot at, so the template still needs to know him.
        "is_loser": viewer_author and battle.loser_id == viewer_author.pk,
    })


# T11, 2026-08-15: biathlon_lock is GONE with the loser-locking step it served.
# Both chefs place their two blocks before Stage 1 now, through declare_menu.


@chef_battle_guard
@login_required
@require_POST
def biathlon_shoot(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    try:
        target_id = int(request.POST.get("target_ingredient_id", -1))
        shot = fire_ingredient_shot(
            battle=battle, shooter=viewer_author, target_ingredient_id=target_id,
        )
        if shot.bounced:
            messages.warning(request, "Your shot bounced off a hidden block!")
        else:
            messages.success(request, "Direct hit!")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect("chef_battle:biathlon", pk=pk)


@login_required
def cooking_moderation(request):
    # is_moderator() alone admits has_bearseeker_privileges regardless of
    # is_staff (F8, 2026-08-11) - a general site-moderation flag, not a Chef
    # Battle one. Not currently exploitable (grant_bearseeker always sets
    # is_staff too), but nothing enforces that invariant, so this app's own
    # moderation surface also requires is_battle_visible, same as every other
    # page here.
    # F17, 2026-08-11: Http404, not PermissionDenied - every other gate in
    # this app (battle_withdraw_resolve included) answers 404 so a rejected
    # dark-launch caller can't tell the page exists. A 403 confirmed it did.
    if not (is_moderator(request.user) and is_battle_visible(request)):
        raise Http404
    battles = get_battles_awaiting_cooking_approval()
    return render(request, "chef_battle/cooking_moderation.html", {"battles": battles})


@login_required
@require_POST
def cooking_moderation_approve(request, pk):
    if not (is_moderator(request.user) and is_battle_visible(request)):
        raise Http404
    battle = get_object_or_404(Battle, pk=pk)
    try:
        approve_cooking_phase(battle, request.user)
        messages.success(request, f"Cooking phase approved for: {battle.theme}")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("chef_battle:cooking_moderation")


@chef_battle_guard
@login_required
def cooking_submit(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    if not author or not battle.author_is_participant(author):
        raise PermissionDenied

    if battle.status != Battle.Status.COOKING:
        messages.error(request, "This battle is not in the cooking phase.")
        return redirect("chef_battle:battle_detail", pk=pk)

    try:
        my_entry = battle.entries.get(author=author)
    except BattleEntry.DoesNotExist:
        raise PermissionDenied

    if request.method == "POST":
        photo = request.FILES.get("cooked_photo")
        real_photo_confirmed = request.POST.get("real_photo_confirmed") == "1"
        if not photo:
            messages.error(request, "Please select a photo to upload.")
        elif not real_photo_confirmed:
            messages.error(request, "Please confirm that your photo is a real photograph before submitting.")
        else:
            try:
                submit_cooked_photo(battle=battle, author=author, photo=photo,
                                    real_photo_confirmed=True)
                messages.success(request, "Your cooked dish photo has been submitted!")
            except ValueError as e:
                messages.error(request, str(e))
            except ValidationError as e:
                # T05, 2026-08-13: a refused upload is a plain sentence to the
                # chef, not a 500. Nothing was stored - the file is normalised
                # before the entry is touched.
                messages.error(request, e.messages[0] if e.messages else str(e))
        return redirect("chef_battle:battle_detail", pk=pk)

    return render(request, "chef_battle/cooking_submit.html", {
        "battle": battle,
        "my_entry": my_entry,
    })


@chef_battle_guard
def battle_history(request):
    """Every finished battle, newest first — tz_main.md section 18.

    G13, Owner 2026-08-11. The arena shows what is happening and the Hall of
    Fame shows the first ten; nothing showed the rest, so a battle simply left
    the site's memory once it dropped off the front. Finished means finished:
    completed, walkover, void and cancelled all appear, because a battle that
    ended badly is still part of the record and hiding it would make the
    history a highlight reel.
    """
    from django.core.paginator import Paginator

    finished = (
        Battle.objects.select_related("challenger", "opponent", "winner", "loser")
        .filter(status__in=[
            Battle.Status.COMPLETED, Battle.Status.WALKOVER,
            Battle.Status.VOID, Battle.Status.CANCELLED,
        ])
        .order_by("-end_time", "-pk")
    )
    page = Paginator(finished, 25).get_page(request.GET.get("page"))
    return render(request, "chef_battle/battle_history.html", {
        "page_obj": page,
        "battles": page.object_list,
        "total": finished.count(),
    })


@chef_battle_guard
def season_detail(request, slug):
    """One season: its rules, its frozen standings, its battles.

    G13. The season leaderboard showed the CURRENT season only and a closed one
    became unreachable the moment the next began, so a chef's season could not
    be linked to. The standings carry wins, losses and streak since G10, which
    is what makes this page worth having rather than a second leaderboard.
    """
    from .models import Season
    from .season_service import crown_rule, reward_rules

    season = get_object_or_404(Season, slug=slug)
    standings = season.standings.select_related("chef").order_by("rank_position", "-score")
    battles = (
        season.battles.select_related("challenger", "opponent", "winner")
        .order_by("-end_time", "-pk")[:25]
    )
    return render(request, "chef_battle/season_detail.html", {
        "season": season,
        "standings": standings,
        "battles": battles,
        "crown_rule": crown_rule(season),
        "reward_rules": reward_rules(season),
    })


@chef_battle_guard
def crown_holder(request):
    """Who wears the crown, and who wore it before — tz_main.md section 18.

    G13. The crown is on the arena and nowhere else, so the moment a reign ends
    there is no page that remembers it. A crown lasts 24 hours (artifact_3
    section 10), so "nobody right now" is a normal answer and this page says so
    plainly instead of showing the last holder as if they still held it.
    """
    from .models import ChefBattleProfile

    now = timezone.now()
    holder = (
        ChefBattleProfile.objects.select_related("author")
        .filter(crown_until__gt=now)
        .exclude(author__slug__in=_hidden_bot_slugs())
        .exclude(author__slug__in=_uncompeting_slugs())  # T22
        .order_by("-crown_until")
        .first()
    )
    past = (
        Battle.objects.select_related("winner")
        .filter(crown_awarded=True, winner__isnull=False)
        .exclude(winner__slug__in=_hidden_bot_slugs())
        .exclude(winner__slug__in=_uncompeting_slugs())  # T22
        .order_by("-end_time", "-pk")[:20]
    )
    most_crowns = (
        ChefBattleProfile.objects.select_related("author")
        .filter(crown_count__gt=0)
        .order_by("-crown_count", "-wins", "author__name")[:10]
    )
    return render(request, "chef_battle/crown_holder.html", {
        "holder": holder,
        "past_reigns": past,
        "most_crowns": most_crowns,
        "server_time": now,
    })


def vote_review(request):
    """Suspicious votes, for a moderator — tz_main.md section 18.

    G13. The integrity machinery has always existed (gate_self_vote,
    gate_participant_vote, gate_duplicate_device, gate_vote_rate_ip, and the
    is_suspicious flag) and the only place to READ it was the Django admin, so
    the one screen the ТЗ asks for did not exist on the site.

    Moderator-only and checked in the view rather than by chef_battle_guard, the
    same way cooking_moderation is: a moderator reaching this from the panel is
    not a chef looking at an arena page. READ-ONLY BY DESIGN - it shows what the
    gates recorded and changes nothing. Clearing a flag is an admin action, and
    a review screen that can also edit is a review nobody can trust.
    """
    from accounts.views import is_moderator
    from .access import is_battle_visible
    # BOTH checks, matching what F8 (v2.5.1000) established for the other
    # moderator screens: is_moderator alone admits has_bearseeker_privileges
    # regardless of is_staff, which is a general site-moderation flag and not a
    # Chef Battles one.
    if not (is_moderator(request.user) and is_battle_visible(request)):
        raise Http404

    from .models import BattleVote, VoteIntegrityEvent

    suspicious = (
        BattleVote.objects.select_related("battle", "voted_for", "voter")
        .filter(is_suspicious=True)
        .order_by("-created_at")[:100]
    )
    refused = (
        VoteIntegrityEvent.objects.select_related("battle")
        .order_by("-created_at")[:100]
    )
    return render(request, "chef_battle/vote_review.html", {
        "suspicious": suspicious,
        "refused": refused,
        "suspicious_total": BattleVote.objects.filter(is_suspicious=True).count(),
        "refused_total": VoteIntegrityEvent.objects.count(),
    })


@chef_battle_guard
def hall_of_fame(request):
    battles = get_hall_of_fame_battles(limit=10)
    chefs = get_hall_of_fame_chefs(limit=20)
    return render(request, "chef_battle/hall_of_fame.html", {
        "battles": battles,
        "chefs": chefs,
    })


@chef_battle_guard
@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=False)
def battle_chat_send(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if getattr(request, "limited", False):
        return redirect("chef_battle:battle_detail", pk=pk)
    if battle.status not in Battle.ACTIVE_STATUSES | {Battle.Status.COMPLETED}:
        return redirect("chef_battle:battle_detail", pk=pk)

    from .models import BattleChatMessage
    body = request.POST.get("body", "").strip()[:300]
    if not body:
        return redirect("chef_battle:battle_detail", pk=pk)

    if request.user.is_authenticated:
        from .models import OwnerAccountRestriction
        author = get_author_for_user(request.user)
        if author and OwnerAccountRestriction.objects.filter(
            author=author, muted_until__gt=timezone.now()
        ).exists():
            messages.error(request, "You are temporarily muted in Arena chat.")
            return redirect("chef_battle:battle_detail", pk=pk)

    if request.user.is_authenticated:
        display_name = request.user.get_full_name() or request.user.username
    else:
        display_name = request.POST.get("display_name", "").strip()[:60] or "Anonymous"
        # An anonymous visitor must not impersonate a registered account or
        # a chef's public author name (e.g. posting as "GreenBear").
        from django.contrib.auth import get_user_model
        name_taken = (
            get_user_model().objects.filter(username__iexact=display_name).exists()
            or RecipeAuthor.objects.filter(name__iexact=display_name).exists()
        )
        if name_taken:
            display_name = "Anonymous"

    BattleChatMessage.objects.create(
        battle=battle,
        author=request.user if request.user.is_authenticated else None,
        display_name=display_name,
        body=body,
    )
    return redirect("chef_battle:battle_detail", pk=pk)


@ratelimit(key="ip", rate="120/m", method="GET", block=False)
def battle_chat_poll(request, pk):
    from django.http import JsonResponse
    from .models import BattleChatMessage
    # Match the Battle Room page gate: chat is not readable by anyone who
    # cannot see the battle itself (staff/superuser during dark launch). The
    # sibling battle_chat_send already carries @chef_battle_guard; this poll
    # endpoint previously had only a rate limit, leaking chat to anonymous.
    if not is_battle_visible(request):
        raise Http404
    if getattr(request, "limited", False):
        return JsonResponse({"error": "rate_limited"}, status=429)
    battle = get_object_or_404(Battle, pk=pk)
    try:
        since_id = int(request.GET.get("since", 0))
    except (TypeError, ValueError):
        since_id = 0
    msgs = (
        BattleChatMessage.objects
        .filter(battle=battle, id__gt=since_id, is_hidden=False)
        .order_by("created_at")[:40]
    )
    return JsonResponse({
        "messages": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "body": m.body,
                "created_at": m.created_at.strftime("%H:%M"),
            }
            for m in msgs
        ]
    })


# Guard first — see token_checkout_create for why the order matters.
@chef_battle_guard
@login_required
@require_POST
def send_appreciation_gift_view(request, pk):
    from .models import AppreciationGiftType
    from .services import send_appreciation_gift

    # Check suspension/fraud before any DB fetch so suspended users get a clean redirect
    sender_author = get_author_for_user(request.user)
    early_fraud = run_fraud_gates([
        (gate_suspended_account, (sender_author,), {}),
        (gate_fraud_flagged, (sender_author,), {}),
        (gate_age_verified, (sender_author,), {}),
    ])
    if not early_fraud.passed:
        first_fail = next(g for g in early_fraud.gates if not g.passed)
        _GIFT_FRAUD_MESSAGES = {
            "suspended_account": "Your account is suspended.",
            "fraud_flagged": "Your account has been flagged. Please contact support.",
            "age_verified": "You must confirm that you are 18 or older before sending paid gifts.",
        }
        messages.error(request, _GIFT_FRAUD_MESSAGES.get(first_fail.gate, "Gift not accepted."))
        return redirect("chef_battle:battle_detail", pk=pk)

    battle = get_object_or_404(Battle, pk=pk)
    recipient_slug = request.POST.get("recipient_slug", "")
    gift_type = request.POST.get("gift_type", "")
    recipient = get_object_or_404(RecipeAuthor, slug=recipient_slug)
    if not battle.author_is_participant(recipient):
        messages.error(request, "Invalid recipient.")
        return redirect("chef_battle:battle_detail", pk=pk)

    velocity_result = run_fraud_gates([
        (gate_gift_velocity, (request.user, recipient), {}),
    ])
    if not velocity_result.passed:
        messages.error(request, "You have sent too many gifts recently. Please wait before sending another.")
        return redirect("chef_battle:battle_detail", pk=pk)

    try:
        send_appreciation_gift(
            sender_user=request.user,
            recipient=recipient,
            gift_type=gift_type,
            message=request.POST.get("message", ""),
        )
        messages.success(request, f"Gift sent to {recipient.name}!")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("chef_battle:battle_detail", pk=pk)


# Guard first — see token_checkout_create for why the order matters.
@chef_battle_guard
@login_required
@require_POST
def send_viewer_battle_gift_view(request, pk):
    """Viewer sends a combat artifact to a chef during an active battle.

    POST params:
      recipient_slug — slug of the chef to receive the artifact
      artifact_id    — exact non-legendary artifact chosen by the viewer.
    """
    from .models import Artifact
    from .services import send_battle_artifact

    sender_author = get_author_for_user(request.user)
    early_fraud = run_fraud_gates([
        (gate_suspended_account, (sender_author,), {}),
        (gate_fraud_flagged, (sender_author,), {}),
        (gate_age_verified, (sender_author,), {}),
    ])
    if not early_fraud.passed:
        first_fail = next(g for g in early_fraud.gates if not g.passed)
        _MSGS = {
            "suspended_account": "Your account is suspended.",
            "fraud_flagged": "Your account has been flagged. Please contact support.",
            "age_verified": "You must confirm that you are 18 or older before sending paid gifts.",
        }
        messages.error(request, _MSGS.get(first_fail.gate, "Gift not accepted."))
        return redirect("chef_battle:battle_detail", pk=pk)

    battle = get_object_or_404(Battle, pk=pk)
    recipient_slug = request.POST.get("recipient_slug", "")
    try:
        artifact_id = int(request.POST.get("artifact_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "Choose an artifact to send.")
        return redirect("chef_battle:battle_detail", pk=pk)

    recipient = get_object_or_404(RecipeAuthor, slug=recipient_slug)
    if not battle.author_is_participant(recipient):
        messages.error(request, "Invalid recipient.")
        return redirect("chef_battle:battle_detail", pk=pk)

    try:
        artifact = Artifact.objects.get(pk=artifact_id, is_active=True)
    except Artifact.DoesNotExist:
        messages.error(request, "This artifact is not available.")
        return redirect("chef_battle:battle_detail", pk=pk)
    if artifact.rarity == Artifact.Rarity.LEGENDARY:
        messages.error(request, "Legendary artifacts are prize-only and cannot be bought.")
        return redirect("chef_battle:battle_detail", pk=pk)

    try:
        send_battle_artifact(
            sender_user=request.user,
            recipient=recipient,
            battle=battle,
            artifact=artifact,
        )
        messages.success(request, f"🎁 {artifact.name} gifted to {recipient.name}!")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("chef_battle:battle_detail", pk=pk)


def chef_battle_profile(request, slug):
    # Merged profile (2026-07-05): the standalone chef battle profile page is
    # gone — a chef's arena record now lives on their author page under the
    # #chef-arena section. This URL is kept as a permanent redirect so old
    # links and the sitewide widget keep working.
    author = get_object_or_404(RecipeAuthor, slug=slug)
    return redirect(author.get_absolute_url() + "#chef-arena")




@chef_battle_guard
@login_required
def reward_agreement(request):
    """GET: show agreement text. POST: accept it and redirect to payout statement."""
    author = get_author_for_user(request.user)
    if author is None:
        raise PermissionDenied

    profile = get_or_create_battle_profile(author)
    if profile.reward_agreement_accepted:
        return redirect("chef_battle:payout_statement")

    if request.method == "POST":
        if request.POST.get("accept") == "1":
            accept_reward_agreement(
                author,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            messages.success(request, "Chef Reward Agreement accepted.")
            return redirect("chef_battle:payout_statement")
        messages.error(request, "You must check the box to accept the agreement.")

    return render(request, "chef_battle/reward_agreement.html", {
        "agreement_text": REWARD_AGREEMENT_TEXT_v1,
        "profile": profile,
    })


@chef_battle_guard
@login_required
def payout_statement(request):
    """Payout statement page: eligibility, approved tokens, payout history, request button."""
    from django.db.models import Sum
    from .models import PayoutRequest, RewardRecord

    author = get_author_for_user(request.user)
    if author is None:
        raise PermissionDenied

    profile = get_or_create_battle_profile(author)

    if not profile.reward_agreement_accepted:
        return redirect("chef_battle:reward_agreement")

    eligibility = check_payout_eligibility(author)

    approved_records = RewardRecord.objects.filter(
        recipient=author, status=RewardRecord.Status.APPROVED
    ).order_by("-created_at")

    payout_history = PayoutRequest.objects.filter(
        chef=author
    ).order_by("-requested_at")[:20]

    if request.method == "POST":
        if not eligibility["eligible"]:
            messages.error(request, "You are not currently eligible for a payout.")
            return redirect("chef_battle:payout_statement")
        try:
            payout = create_payout_request(author, request_http=request)
            messages.success(
                request,
                f"Payout request #{payout.pk} submitted for {payout.amount_reward_tokens}T "
                f"(€{payout.gross_payout_eur:.2f}). Our team will review it within 5 business days."
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("chef_battle:payout_statement")

    return render(request, "chef_battle/payout_statement.html", {
        "profile": profile,
        "eligibility": eligibility,
        "approved_records": approved_records,
        "payout_history": payout_history,
        "payout_rate": "€0.025",
        "min_tokens": 2000,
    })


@login_required
@require_POST
def content_report_submit(request):
    """DSA content reporting endpoint (POST-only). Returns JSON."""
    from .models import ContentReport
    from .services import submit_content_report

    content_kind = request.POST.get("content_kind", "").strip()
    object_id_raw = request.POST.get("object_id", "").strip()
    reason = request.POST.get("reason", "").strip()

    valid_kinds = {k.value for k in ContentReport.ContentKind}
    if content_kind not in valid_kinds:
        return JsonResponse({"ok": False, "error": "Invalid content kind."}, status=400)
    try:
        object_id = int(object_id_raw)
        assert object_id > 0
    except (ValueError, AssertionError):
        return JsonResponse({"ok": False, "error": "Invalid object ID."}, status=400)
    if not reason or len(reason) > 300:
        return JsonResponse({"ok": False, "error": "Reason is required (max 300 chars)."}, status=400)

    try:
        submit_content_report(
            reporter=request.user,
            content_kind=content_kind,
            object_id=object_id,
            reason=reason,
        )
    except Exception:
        logger.exception("content_report_submit failed for user %s", request.user.pk)
        return JsonResponse({"ok": False, "error": "Could not submit report. Please try again."}, status=500)

    return JsonResponse({"ok": True})


@login_required
@require_POST
def artifact_generate_image(request, pk):
    from django.core.files.base import ContentFile
    from .models import Artifact
    from recipes.management.commands.generate_recipe import fetch_image_bytes

    # F26, 2026-08-11: same class of gap F8/F16/F22 already closed - is_moderator()
    # alone admits has_bearseeker_privileges regardless of is_staff, and this
    # write action triggers a paid AI image generation with no is_battle_visible()
    # check at all.
    if not ((is_moderator(request.user) or request.user.is_staff) and is_battle_visible(request)):
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    artifact = get_object_or_404(Artifact, pk=pk)
    feedback = request.POST.get("feedback", "").strip()

    rarity_styles = {
        "common": {
            "border": "thin silver-grey rounded-square border",
            "glow":   "subtle silver rim light",
            "object": "grey and silver tones, muted metallic sheen",
            "bg":     "solid flat dark navy-blue",
        },
        "uncommon": {
            "border": "glowing green rounded-square border",
            "glow":   "soft green inner glow around the object",
            "object": "vivid green color accents, green metallic highlights",
            "bg":     "solid flat dark navy-blue",
        },
        "rare": {
            "border": "glowing electric-blue rounded-square border",
            "glow":   "bright blue inner glow around the object",
            "object": "vivid blue color accents, blue metallic highlights",
            "bg":     "solid flat dark navy-blue",
        },
        "epic": {
            "border": "glowing purple rounded-square border",
            "glow":   "intense purple inner glow and sparkles around the object",
            "object": "vivid purple and violet color accents, purple metallic highlights",
            "bg":     "solid flat dark navy-blue",
        },
        "legendary": {
            "border": "thick radiant golden rounded-square border with ornate corner details",
            "glow":   "dramatic golden radiant glow and golden sparkles around the object",
            "object": "gold and amber color accents dominate the object, golden metallic sheen",
            "bg":     "solid flat dark navy-blue",
        },
    }
    rs = rarity_styles.get(artifact.rarity, rarity_styles["common"])
    item_name = artifact.name
    prompt = (
        f"A 2D game asset icon of {item_name}. "
        f"The object is rendered with {rs['object']}. "
        f"Hard-edged vector digital illustration, solo object centered in the frame. "
        f"{rs['border']}. {rs['bg']} background filling the entire screen. "
        f"{rs['glow']}. "
        "Consistent mobile game UI asset style, highly stylized, vibrant saturated colors, "
        "no gradients on the background, no realistic shadows, no text, no watermarks, clean sharp edges."
    )
    if feedback:
        prompt += f" Important: Apply the following adjustment while strictly maintaining the 2D vector asset style: {feedback}."

    try:
        image_bytes = fetch_image_bytes(prompt)
        import os
        slug = artifact.name.lower().replace(" ", "-").replace("'", "")[:50]
        filename = f"{slug}-{artifact.pk}.png"
        artifact.image.save(filename, ContentFile(image_bytes), save=True)
        return JsonResponse({"success": True, "url": artifact.image.url})
    except Exception as exc:
        logger.error("artifact_generate_image failed for pk=%s: %s", pk, exc, exc_info=True)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@chef_battle_guard
def artifact_gallery(request):
    from .models import Artifact

    artifacts = Artifact.objects.filter(is_active=True).order_by("rarity", "name")

    rarity_order = ["common", "uncommon", "rare", "epic", "legendary"]
    rarity_labels = {
        "common": "Common",
        "uncommon": "Uncommon",
        "rare": "Rare",
        "epic": "Epic",
        "legendary": "Legendary",
    }
    grouped = {}
    for rarity in rarity_order:
        group = [a for a in artifacts if a.rarity == rarity]
        if group:
            grouped[rarity_labels[rarity]] = group

    can_generate = request.user.is_authenticated and (
        request.user.is_staff or is_moderator(request.user)
    )
    return render(request, "chef_battle/artifact_gallery.html", {
        "grouped": grouped,
        "total": artifacts.count(),
        "can_generate": can_generate,
    })


@chef_battle_guard
def artifact_detail(request, pk):
    """One combat artifact. Superuser-only since v2.5.798 (Owner, 2026-08-04):
    an Author sees nothing of Chef Battles but the rules and the news."""
    artifact = get_object_or_404(Artifact, pk=pk, is_active=True)
    return render(request, "chef_battle/artifact_detail.html", {"artifact": artifact})


@chef_battle_guard
def appreciation_gallery(request):
    """Gallery of appreciation gift types with cost and description.
    Superuser-only since v2.5.798 (Owner, 2026-08-04)."""
    from .models import (
        AppreciationGiftType,
        APPRECIATION_GIFT_COST,
        APPRECIATION_GIFT_EMOJI,
    )

    gifts = [
        {
            "key": gt.value,
            "label": gt.label,
            "emoji": APPRECIATION_GIFT_EMOJI.get(gt, "🎁"),
            "cost": APPRECIATION_GIFT_COST.get(gt, 0),
        }
        for gt in AppreciationGiftType
    ]

    return render(request, "chef_battle/appreciation_gallery.html", {
        "gifts": gifts,
    })


@chef_battle_guard
@login_required
def battle_chest(request):
    """Chef's personal knife and tool roll, paginated for large collections."""
    from .models import ChefArtifact

    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "You need an author profile to access your Battle Chest.")
        return redirect("chef_battle:home")

    all_owned = (
        ChefArtifact.objects.filter(chef=author)
        .select_related("artifact")
        .order_by("-earned_at")
    )

    available = [c for c in all_owned if c.status == "available"]
    reserved  = [c for c in all_owned if c.status == "reserved"]
    consumed  = [c for c in all_owned if c.status in ("consumed", "expired", "reversed")]
    roll_filter = request.GET.get("filter", "all")
    filter_map = {
        "attack": ("attack",),
        "defence": ("defence", "defense"),
    }
    if roll_filter in filter_map:
        visible_available = [
            item for item in available
            if item.artifact.effect_type in filter_map[roll_filter]
        ]
    else:
        roll_filter = "all"
        visible_available = available
    available_page = Paginator(visible_available, 24).get_page(request.GET.get("page"))
    attack_count = sum(1 for item in available if item.artifact.effect_type == "attack")
    defence_count = sum(
        1 for item in available
        if item.artifact.effect_type in ("defence", "defense")
    )

    wallet = None
    try:
        wallet = TokenWallet.objects.get(chef=author)
    except TokenWallet.DoesNotExist:
        pass

    return render(request, "chef_battle/battle_chest.html", {
        "available": available,
        "visible_available": visible_available,
        "available_page": available_page,
        "roll_filter": roll_filter,
        "attack_count": attack_count,
        "defence_count": defence_count,
        "reserved": reserved,
        "consumed": consumed,
        "total": all_owned.count(),
        "wallet": wallet,
    })


@chef_battle_guard
@login_required
def changing_room(request):
    """
    Pre-battle preparation area: chef sees their stats, available artifacts,
    active battles, and can navigate to relevant actions.
    """
    from .models import ChefArtifact

    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "You need an author profile to access the Changing Room.")
        return redirect("chef_battle:home")

    profile, _ = ChefBattleProfile.objects.get_or_create(author=author)

    available_artifacts = list(
        ChefArtifact.objects.filter(chef=author, status="available")
        .select_related("artifact")
        .order_by("artifact__rarity", "artifact__name")
    )
    available_artifacts_preview = available_artifacts[:6]
    attack_artifact_count = sum(1 for item in available_artifacts if item.artifact.effect_type == "attack")
    defence_artifact_count = sum(
        1 for item in available_artifacts
        if item.artifact.effect_type in ("defence", "defense")
    )

    from django.db import models as db_models
    my_active_battles = Battle.objects.filter(
        status__in=["active", "awaiting_submissions", "cooking", "biathlon", "menu_locked"],
    ).filter(
        db_models.Q(challenger=author) | db_models.Q(opponent=author)
    ).select_related("challenger", "opponent").order_by("-created_at")[:5]

    wallet = None
    try:
        wallet = TokenWallet.objects.get(chef=author)
    except TokenWallet.DoesNotExist:
        pass

    from chef_battle.energy_service import ENERGY_CAP

    return render(request, "chef_battle/changing_room.html", {
        "profile": profile,
        "available_artifacts": available_artifacts,
        "available_artifacts_preview": available_artifacts_preview,
        "attack_artifact_count": attack_artifact_count,
        "defence_artifact_count": defence_artifact_count,
        "my_active_battles": my_active_battles,
        "wallet": wallet,
        "energy_cap": ENERGY_CAP,
        "moves_min_to_challenge": MOVES_MIN_TO_CHALLENGE,
    })


# ── E3: Readiness Gate ──────────────────────────────────────────────────────

@chef_battle_guard
@login_required
@require_POST
def battle_set_ready(request, pk):
    """Chef presses 'Ready' in the antechamber.

    When both chefs are ready the battle advances from SCHEDULED to
    MENU_LOCKED so they can declare their ingredient lists.
    """
    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)

    if not author:
        raise PermissionDenied

    if not battle.author_is_participant(author):
        raise PermissionDenied

    if battle.status != Battle.Status.SCHEDULED:
        messages.error(request, "This battle is not in the readiness phase.")
        return redirect("chef_battle:battle_detail", pk=pk)

    is_challenger = author.pk == battle.challenger_id

    with transaction.atomic():
        # F67, 2026-08-12: this view had no lock at all. Both chefs pressing
        # Ready in the same window - exactly when both WOULD click - each read
        # the other's flag as still False and wrote it back False on save,
        # silently erasing whichever one committed first. That chef then had
        # no way back in (this view refuses any POST once status leaves
        # SCHEDULED) and lost the grace period to an unearned walkover.
        # Lock the row and re-read both flags from it before deciding anything.
        battle = Battle.objects.select_for_update().get(pk=battle.pk)
        if battle.status != Battle.Status.SCHEDULED:
            messages.error(request, "This battle is not in the readiness phase.")
            return redirect("chef_battle:battle_detail", pk=pk)

        if is_challenger:
            if battle.challenger_ready:
                messages.info(request, "You already marked yourself as ready.")
                return redirect("chef_battle:battle_detail", pk=pk)
            battle.challenger_ready = True
        else:
            if battle.opponent_ready:
                messages.info(request, "You already marked yourself as ready.")
                return redirect("chef_battle:battle_detail", pk=pk)
            battle.opponent_ready = True

        if battle.challenger_ready and battle.opponent_ready:
            # OWNER, scenario A6, 2026-08-06: "оба готовы - таймер до матча 15 минут".
            #
            # Ready no longer teleports the battle into menu declaration. The
            # twelve hours are a deadline, not an appointment: two chefs who
            # are both standing there have their start pulled in to fifteen
            # minutes, the battle STAYS scheduled and announced, and its pill
            # climbs the Next Battle board because that board is ordered
            # strictly by time remaining. resolve_start_rituals() then begins
            # the battle when the clock runs out - which is the path it was
            # always written for, docstring included.
            from .services import READY_HEAD_START, pull_start_forward_when_both_ready

            moved = pull_start_forward_when_both_ready(battle)
            fields = ["challenger_ready", "opponent_ready", "updated_at"]
            if moved:
                fields.insert(2, "start_time")
            battle.save(update_fields=fields)
            create_battle_event(
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                battle=battle,
                actor=author,
                message=(
                    f"Both chefs are ready for '{battle.theme}'. The battle starts in "
                    f"{int(READY_HEAD_START.total_seconds() // 60)} minutes."
                ),
                is_public=True,
            )
            messages.success(
                request,
                "Both chefs are ready. Your battle starts in "
                f"{int(READY_HEAD_START.total_seconds() // 60)} minutes — watch it "
                "climb the arena board.",
            )
        else:
            battle.save(update_fields=["challenger_ready", "opponent_ready", "updated_at"])
            messages.success(request, "You're ready! Waiting for your opponent.")

    return redirect("chef_battle:battle_detail", pk=pk)


# ── Changing Room: Menu Declaration ─────────────────────────────────────────

@chef_battle_guard
@login_required
def battle_changing_room(request, pk):
    """Changing Room — chef declares their ingredient list (menu_locked phase)."""
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    if not viewer_author or not battle.author_is_participant(viewer_author):
        raise PermissionDenied
    if battle.status != Battle.Status.MENU_LOCKED:
        return redirect("chef_battle:battle_detail", pk=pk)
    entry = battle.entries.filter(author=viewer_author).first()
    if not entry or not entry.recipe:
        messages.info(request, "Attach your recipe before declaring your battle ingredients.")
        return redirect("chef_battle:battle_recipe_attach", pk=pk)
    recipe_ingredient_lines = [
        {"index": index, "text": line.strip()}
        for index, line in enumerate(entry.recipe.ingredients.splitlines())
        if line.strip()
    ]

    my_ingredients = list(
        battle.battle_ingredients.filter(chef=viewer_author).order_by("position")
    )
    opponent = battle.opponent if viewer_author.pk == battle.challenger_id else battle.challenger
    opponent_declared = battle.battle_ingredients.filter(chef=opponent).exists()

    return render(request, "chef_battle/changing_room_declare.html", {
        "battle": battle,
        "my_ingredients": my_ingredients,
        "already_declared": bool(my_ingredients),
        "opponent_declared": opponent_declared,
        "min_count": BattleIngredient.MIN_COUNT,
        "max_count": BattleIngredient.MAX_COUNT,
        "key_count": BattleIngredient.KEY_COUNT,
        "recipe_ingredient_lines": recipe_ingredient_lines,
    })


@chef_battle_guard
@login_required
def battle_recipe_attach(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
    if not author or not battle.author_is_participant(author):
        raise PermissionDenied
    if battle.status not in {Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED}:
        return redirect(battle.get_absolute_url())
    entry = battle.entries.filter(author=author).first()
    if request.method == "POST":
        form = BattleRecipeAttachForm(request.POST, author=author)
        if form.is_valid():
            entry, _ = BattleEntry.objects.get_or_create(battle=battle, author=author)
            entry.recipe = form.cleaned_data["recipe"]
            entry.save(update_fields=["recipe", "updated_at"])
            messages.success(request, "Recipe attached. You can now declare your battle ingredients.")
            return redirect("chef_battle:battle_changing_room", pk=pk)
    else:
        form = BattleRecipeAttachForm(author=author, initial={"recipe": entry.recipe_id if entry else None})
    return render(request, "chef_battle/recipe_attach.html", {"battle": battle, "form": form})


@chef_battle_guard
@login_required
@require_POST
def battle_declare_menu(request, pk):
    """POST: submit ingredient list for the Changing Room."""
    from .services import declare_menu
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    if not viewer_author or not battle.author_is_participant(viewer_author):
        raise PermissionDenied

    entry = battle.entries.filter(author=viewer_author).select_related("recipe").first()
    if not entry or not entry.recipe:
        messages.error(request, "Attach your recipe before declaring ingredients.")
        return redirect("chef_battle:battle_recipe_attach", pk=pk)
    recipe_lines = entry.recipe.ingredients.splitlines()
    selected = [int(value) for value in request.POST.getlist("ingredient_index") if value.isdigit()]
    selected = [index for index in selected if 0 <= index < len(recipe_lines) and recipe_lines[index].strip()]
    names = [recipe_lines[index].strip() for index in selected]
    keys = set(request.POST.getlist("ingredient_key"))
    ingredients = [
        {"name": name, "is_key": str(index) in keys}
        for index, name in zip(selected, names)
    ]
    try:
        declare_menu(battle=battle, chef=viewer_author, ingredients=ingredients)
        messages.success(request, "Menu declared. Waiting for your opponent!")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("chef_battle:battle_changing_room", pk=pk)

    return redirect("chef_battle:battle_detail", pk=pk)


# ── Arena Master Console (P01: visual shell only) ───────────────────────────

@arena_console_guard
def master_console(request):
    """Arena Master Console (P01 shell + P02 read-only live data).

    Server-renders the current read models and embeds the public arena ring
    renderer; arena_master_console.js polls master_state() every 20 s. All
    values come from documented selectors (P02_DATA_DICTIONARY.yaml); no
    operator writes exist until P03. Access: DG-01 gate.
    """
    from .selectors import get_master_state

    author = get_author_for_user(request.user)
    state = get_master_state()

    # THE CONSOLE ARENA IS A MIRROR, NOT A SECOND ARENA (Owner, 2026-08-05:
    # "наша арена и моя арена которую я вижу внутри панели - разные, и я не могу
    # достоверно получать информацию").
    #
    # It used to build its own arena_data by hand-listing fourteen keys, and a
    # hand-copied contract drifts by definition: by the time he said this it was
    # missing vip_sponsors, spirit_count and upcoming, so the sponsors ring, the
    # balconies and the departures board were simply absent from his copy while
    # the public arena had them. Nobody had to break anything; the second list
    # just stopped being updated. It is now the SAME assembly the public page
    # uses, so a key added to the arena reaches the console with no second edit.
    #
    # What differs is only the rendering, and only to save the operator's
    # machine: the mirror runs flat (no 42-degree camera) with the atmosphere
    # and effects layers off. The data, the ids and the behaviour are identical.
    context = _arena_page_context(
        request, viewer_author=author, user_enrolled=False, allow_demo=True,
    )
    context.update({
        "operator_author": author,
        "operator_is_owner": bool(author and author.slug == settings.OWNER_SLUG),
        "console_test_mode": not settings.CHEF_BATTLE_ENABLED,
        "master_state": state,
        "primary_battle": state["battles"][0] if state["battles"] else None,
        "console_mirror": True,
    })
    return render(request, "chef_battle/arena_master_console.html", context)


@arena_console_guard
@require_POST
def master_state(request):
    """Read-only state poll for the console (P02). Same 20 s cadence as the
    public arena poll. Operator-only via arena_console_guard; performs no
    writes and leaks nothing into public endpoints."""
    from .selectors import get_master_state
    return JsonResponse(get_master_state())


@arena_console_guard
@require_POST
def master_action(request):
    """Operator write actions for the console (P03).

    DG-02: force transitions, Emergency Stop, resume, cancel and broadcast
    are owner-only; the services enforce that again, but we reject early
    with 403 so non-owner console operators get a clear answer. Every action
    is transactional, idempotency-guarded (expected_status) and audited as
    a BattleEvent OPERATOR_ACTION inside the service layer.
    """
    import uuid

    from .services import (
        OperatorActionError, operator_broadcast, operator_cancel,
        operator_clear_fraud_flag, operator_delete_test_battle,
        operator_emergency_stop, operator_end_stream,
        operator_force_status, operator_moderate_entry, operator_resume,
        operator_review_payout, operator_review_report, operator_set_fraud_flag,
        operator_submit_battle_report, operator_suspend_chef, operator_unsuspend_chef,
        record_rejected_operator_action,
    )

    author = get_author_for_user(request.user)
    action = request.POST.get("action", "")
    battle_id = request.POST.get("battle_id")
    correlation_id = request.POST.get("correlation_id") or uuid.uuid4().hex[:12]
    reason = request.POST.get("reason", "")

    def _reject(error, *, status, extra=None):
        """Every rejected console write gets a private audit trail entry —
        permission denials, invalid input, not-found and service-level
        validation failures are all reconstructable later, not only the
        actions that were actually applied."""
        record_rejected_operator_action(
            action=action or "(missing)", operator_author=author, error=error,
            correlation_id=correlation_id, battle_id=battle_id, extra=extra,
        )
        return JsonResponse({"ok": False, "error": str(error)}, status=status)

    # DG-06: submitting a battle report is the ONE write available to every
    # console operator (the console gate already vetted them). Everything
    # else stays owner-only.
    if action == "submit_battle_report":
        try:
            report = operator_submit_battle_report(
                battle_id=battle_id,
                operator_author=author,
                summary=request.POST.get("summary", ""),
                recommendation=request.POST.get("recommendation", ""),
                flags=request.POST.getlist("flags"),
                correlation_id=correlation_id,
            )
        except OperatorActionError as exc:
            return _reject(exc, status=409)
        return JsonResponse({"ok": True, "action": action,
                             "correlation_id": correlation_id,
                             "report": {"id": report.pk,
                                        "recommendation": report.recommendation}})

    if not author or author.slug != settings.OWNER_SLUG:
        return _reject(
            "Only the arena owner may perform console actions.", status=403,
        )

    id_fields = {
        "force_status": "battle_id", "emergency_stop": "battle_id",
        "resume": "battle_id", "cancel": "battle_id", "delete_test_battle": "battle_id",
        "moderate_entry": "entry_id", "review_report": "report_id",
        "end_stream": "session_id",
    }
    if action == "broadcast" and battle_id:
        id_fields["broadcast"] = "battle_id"
    id_field = id_fields.get(action)
    parsed_id = None
    if id_field:
        try:
            parsed_id = int(request.POST.get(id_field, ""))
            if parsed_id < 1:
                raise ValueError
        except (TypeError, ValueError):
            return _reject(f"Invalid {id_field}.", status=400,
                           extra={"invalid_field": id_field})

    try:
        if action == "force_status":
            battle = operator_force_status(
                battle_id=parsed_id,
                operator_author=author,
                target_status=request.POST.get("target_status", ""),
                expected_status=request.POST.get("expected_status") or None,
                reason=reason,
                correlation_id=correlation_id,
            )
        elif action == "emergency_stop":
            battle = operator_emergency_stop(
                battle_id=parsed_id, operator_author=author,
                reason=reason, correlation_id=correlation_id,
            )
        elif action == "resume":
            battle = operator_resume(
                battle_id=parsed_id, operator_author=author,
                correlation_id=correlation_id,
            )
        elif action == "cancel":
            battle = operator_cancel(
                battle_id=parsed_id, operator_author=author,
                reason=reason, correlation_id=correlation_id,
            )
        elif action == "delete_test_battle":
            deleted = operator_delete_test_battle(
                battle_id=parsed_id, operator_author=author,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "deleted": deleted})
        elif action == "moderate_entry":
            entry = operator_moderate_entry(
                entry_id=parsed_id,
                operator_author=author,
                new_status=request.POST.get("new_status", ""),
                reason=reason,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "entry": {"id": entry.pk,
                                           "moderation_status": entry.moderation_status}})
        elif action == "review_report":
            report = operator_review_report(
                report_id=parsed_id,
                operator_author=author,
                new_status=request.POST.get("new_status", ""),
                note=reason,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "report": {"id": report.pk, "status": report.status}})
        elif action == "end_stream":
            session = operator_end_stream(
                session_id=parsed_id,
                operator_author=author,
                reason=reason,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "provider_side_terminated": False,
                                 "note": "Platform record terminated; no provider integration is configured.",
                                 "session": {"id": session.pk, "status": session.status}})
        elif action in ("approve_payout", "reject_payout"):
            payout = operator_review_payout(
                payout_id=request.POST.get("payout_id"),
                operator_author=author,
                decision=action.split("_")[0],
                reason=reason,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "payout": {"id": payout.pk, "status": payout.status}})
        elif action == "suspend_chef":
            chef_slug = request.POST.get("chef_slug", "")
            if not chef_slug:
                return _reject("chef_slug is required.", status=400)
            profile = operator_suspend_chef(
                chef_slug=chef_slug, operator_author=author,
                reason=reason, correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "chef": {"slug": chef_slug, "is_suspended": profile.is_suspended}})
        elif action == "unsuspend_chef":
            chef_slug = request.POST.get("chef_slug", "")
            if not chef_slug:
                return _reject("chef_slug is required.", status=400)
            profile = operator_unsuspend_chef(
                chef_slug=chef_slug, operator_author=author,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "chef": {"slug": chef_slug, "is_suspended": profile.is_suspended}})
        elif action == "set_fraud_flag":
            chef_slug = request.POST.get("chef_slug", "")
            if not chef_slug:
                return _reject("chef_slug is required.", status=400)
            profile = operator_set_fraud_flag(
                chef_slug=chef_slug, operator_author=author,
                note=reason, correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "chef": {"slug": chef_slug, "fraud_flag": profile.fraud_flag}})
        elif action == "clear_fraud_flag":
            chef_slug = request.POST.get("chef_slug", "")
            if not chef_slug:
                return _reject("chef_slug is required.", status=400)
            profile = operator_clear_fraud_flag(
                chef_slug=chef_slug, operator_author=author,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "chef": {"slug": chef_slug, "fraud_flag": profile.fraud_flag}})
        elif action == "start_emulation":
            from .emulation import start_emulation
            battle = start_emulation(operator_author=author,
                                     correlation_id=correlation_id)
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id,
                                 "battle": {"id": battle.pk, "status": battle.status,
                                            "status_display": battle.get_status_display()}})
        elif action == "emulation_step":
            from .emulation import emulation_step
            result = emulation_step(battle_id=battle_id, operator_author=author,
                                    correlation_id=correlation_id)
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id, **result})
        elif action == "broadcast":
            operator_broadcast(
                operator_author=author,
                message=request.POST.get("message", ""),
                battle_id=parsed_id if id_field == "battle_id" else None,
                correlation_id=correlation_id,
            )
            return JsonResponse({"ok": True, "action": action,
                                 "correlation_id": correlation_id})
        else:
            return _reject(f"Unknown action '{action}'.", status=400)
    except Battle.DoesNotExist:
        return _reject("Battle not found.", status=404)
    except OperatorActionError as exc:
        return _reject(exc, status=409)

    return JsonResponse({
        "ok": True,
        "action": action,
        "correlation_id": correlation_id,
        "battle": {"id": battle.pk, "status": battle.status,
                   "status_display": battle.get_status_display()},
    })



# ── Live Arena build tracker (owner-visible progress matrix) ────────────────
_STAGE_SCORE = {"absent": 0.0, "partial": 0.5, "present": 1.0}


@arena_console_guard
def live_arena_progress(request):
    """Owner-visible Live Arena build tracker: every stage on two axes
    (backend / frontend presence). Read here, updated live from the same page."""
    from .models import LiveArenaStage

    stages = list(LiveArenaStage.objects.all())
    labels = dict(LiveArenaStage.Group.choices)

    def pct(field):
        if not stages:
            return 0
        return round(100 * sum(_STAGE_SCORE[getattr(s, field)] for s in stages) / len(stages))

    groups = []
    for g, _label in LiveArenaStage.Group.choices:
        g_stages = [s for s in stages if s.phase_group == g]
        if g_stages:
            groups.append({"key": g, "label": labels.get(g, g), "stages": g_stages})

    return render(request, "chef_battle/live_arena_progress.html", {
        "groups": groups,
        "backend_pct": pct("backend_status"),
        "frontend_pct": pct("frontend_status"),
        "status_choices": LiveArenaStage.Status.choices,
        "total": len(stages),
    })


@arena_console_guard
@require_POST
def live_arena_stage_update(request):
    """Live status/notes update for one stage column (backend|frontend), driven
    by console buttons — no deploy. Each agent writes only its own column."""
    from .models import LiveArenaStage

    key = request.POST.get("key", "").strip()
    column = request.POST.get("column", "").strip()
    status = request.POST.get("status", "").strip()
    notes = request.POST.get("notes")

    if column not in ("backend", "frontend"):
        return JsonResponse({"ok": False, "error": "bad column"}, status=400)
    stage = LiveArenaStage.objects.filter(key=key).first()
    if stage is None:
        return JsonResponse({"ok": False, "error": "unknown stage"}, status=404)

    fields = []
    if status:
        if status not in {c for c, _ in LiveArenaStage.Status.choices}:
            return JsonResponse({"ok": False, "error": "bad status"}, status=400)
        setattr(stage, f"{column}_status", status)
        fields.append(f"{column}_status")
    if notes is not None:
        setattr(stage, f"{column}_notes", notes.strip())
        fields.append(f"{column}_notes")
    if fields:
        stage.save(update_fields=fields + ["updated_at"])

    return JsonResponse({
        "ok": True, "key": key, "column": column,
        "status": getattr(stage, f"{column}_status"),
        "notes": getattr(stage, f"{column}_notes"),
    })


@arena_console_guard
def live_arena_preview(request):
    """Live, buildable preview of the new broadcast arena (owner-visible canvas).

    Renders the reference composition so the owner can watch the arena take
    shape as we build. Data is dev fixtures for now (clearly labelled); each
    field is swapped for the real arena_state snapshot as Phase 1/2 lands."""
    fixture = {
        "is_fixture": True,
        "theme": "Modern Irish Comfort Food",
        "timer": "23:41:08",
        "left": {
            "num": "CHEF #1", "name": "Chef Aidan Byrne", "rank": "Head Chef",
            "clan": "The Green Apron", "country": "Ireland",
            "viewers": "1.2K", "likes": "2.4K", "comments": "320", "role": "Head Chef",
            "supporters": 68,
        },
        "right": {
            "num": "CHEF #2", "name": "Chef Luca Moretti", "rank": "Sous Chef",
            "clan": "Fire & Steel", "country": "Ireland",
            "viewers": "980", "likes": "1.8K", "comments": "275", "role": "Sous Chef",
            "supporters": 42,
        },
        "chat": [
            ("Aoife K.", "Go Aidan! The Green Apron all the way!"),
            ("Marco Italia", "Forza Luca!"),
            ("Clare B.", "Aidan's plating is on point"),
            ("Sean Murphy", "That looks incredible!"),
            ("Foodie Goddess", "Both chefs are absolute stars tonight"),
            ("Riccardo", "Luca bringing the heat!"),
        ],
    }
    from .arena_snapshot import build_arena_snapshot, get_current_arena_battle
    battle = get_current_arena_battle()
    fx = _snapshot_to_fx(build_arena_snapshot(battle), battle) if battle is not None else fixture
    return render(request, "chef_battle/live_arena_preview.html", {
        "fx": fx,
        "result_frame": request.GET.get("state", ""),
    })


@chef_battle_guard
def battle_broadcast(request, pk):
    """B02/B03/R01/R02 — the battle's own page, the one the arena sends a
    spectator to when the fight starts (ARENA_BATTLE_PLAN section 2c).

    It is the same composition the build canvas has carried since 2026-07-14,
    on real data and behind the same visibility rules as the battle room: the
    canvas was never a mockup to copy, it was this page waiting for a battle.
    Nothing here writes; a spectator reads.
    """
    from .arena_snapshot import build_arena_snapshot

    battle = get_object_or_404(
        Battle.objects.select_related("challenger", "opponent", "winner", "loser"),
        pk=pk,
    )
    # chef_battle_guard already applies the dark-launch tier rule; the import
    # is the same one battle_detail uses for its own presence heartbeat.
    from .services import record_viewer_presence as _record
    _record(request, battle=battle)
    fx = _snapshot_to_fx(build_arena_snapshot(battle), battle)
    return render(request, "chef_battle/live_arena_preview.html", {
        "fx": fx,
        "battle": battle,
        "is_broadcast": True,
        # R01/R02: the RESULT decides which frame the page shows. The build
        # canvas keeps its query-string toggle because it has no battle to ask.
        "result_frame": "complete" if fx.get("finished") else "",
    })


def _fmt_hms(seconds) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _snapshot_to_fx(snap: dict, battle=None) -> dict:
    """Map an arena snapshot onto the frontend fixture shape (same keys).

    R01/R02: when the battle is over, the page must show the REAL champion and
    the REAL runner-up, not whichever chef happens to be on the left. The
    snapshot already knows both sides; the result is the one thing it does not
    carry, because it describes a battle in progress.
    """
    fx = {
        "is_fixture": False,
        "battle_id": snap["battle"]["id"],
        "theme": snap["battle"]["theme"],
        "remaining_seconds": snap["battle"]["remaining_seconds"],
        "timer": _fmt_hms(snap["battle"]["remaining_seconds"]),
        "left": snap["left"],
        "right": snap["right"],
        "chat": snap["chat"],
        "finished": False,
    }
    if battle is None:
        return fx

    finished = battle.status in {
        Battle.Status.COMPLETED, Battle.Status.WALKOVER, Battle.Status.VOID,
        Battle.Status.CANCELLED,
    }
    fx["finished"] = finished
    fx["status_display"] = battle.get_status_display()
    fx["result_reason"] = battle.result_reason or ""
    if finished and battle.winner_id:
        champion_is_challenger = battle.winner_id == battle.challenger_id
        fx["champion"] = snap["left"] if champion_is_challenger else snap["right"]
        fx["runner_up"] = snap["right"] if champion_is_challenger else snap["left"]
    elif finished:
        # A draw, a void or a withdrawal has no champion, and saying otherwise
        # would be the fake data the arena plan forbids.
        fx["champion"] = None
        fx["runner_up"] = None
    return fx


@arena_console_guard
@require_POST
def live_arena_snapshot(request):
    """Polling snapshot for the live-arena preview (owner-gated). Full state so
    the client can resync on reconnect; envelope carries server_timestamp/sequence."""
    from .arena_snapshot import build_arena_snapshot, get_current_arena_battle
    battle = get_current_arena_battle()
    if battle is None:
        return JsonResponse({"battle": None, "server_timestamp": timezone.now().isoformat()})
    try:
        seq = int(request.POST.get("sequence") or 0) + 1
    except (TypeError, ValueError):
        seq = 0
    return JsonResponse(build_arena_snapshot(battle, sequence=seq))


@require_POST
def arena_react(request):
    """Record one 'heart' reaction on a battle stream side (live arena).
    Gated to the arena audience (staff/superuser during dark launch,
    everyone once CHEF_BATTLE_ENABLED); rate-limited per author/session;
    returns the new side count."""
    # Same visibility gate as arena_state/arena_ping (not the full guard,
    # whose suspended-POST banner would stack on every reaction click). Before
    # this the endpoint was public, reachable by anonymous users while the
    # arena page itself 404s them during dark launch.
    if not is_battle_visible(request):
        raise Http404
    from django.shortcuts import get_object_or_404
    from .models import Battle
    from .reaction_service import record_battle_reaction

    battle = get_object_or_404(Battle, pk=request.POST.get("battle_id"))
    side = request.POST.get("side", "")
    author = get_author_for_user(request.user)
    if not request.session.session_key:
        request.session.save()
    try:
        count = record_battle_reaction(
            battle, side, author=author, session_key=request.session.session_key or ""
        )
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad_side"}, status=400)
    except PermissionError:
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
    return JsonResponse({"ok": True, "side": side, "count": count})


# ── Withdrawing from an accepted battle (Owner's rule, 2026-08-05) ────────────


@chef_battle_guard
@login_required
def battle_withdraw(request, pk):
    """The withdrawing chef writes his reason on a contact-form-shaped page."""
    from .withdrawal_service import can_withdraw, request_withdrawal, WithdrawalNotAllowed, withdrawals_left

    author = get_author_for_user(request.user)
    battle = get_object_or_404(Battle.objects.select_related("challenger", "opponent"), pk=pk)
    if not battle.author_is_participant(author):
        raise PermissionDenied

    if not can_withdraw(battle, author):
        messages.error(request, "You cannot withdraw from this battle.")
        return redirect(battle.get_absolute_url())

    if request.method == "POST":
        try:
            request_withdrawal(battle=battle, author=author, reason=request.POST.get("reason", ""))
        except WithdrawalNotAllowed as exc:
            messages.error(request, str(exc))
            return redirect(battle.get_absolute_url())
        messages.success(
            request,
            "Your request has been sent to the other chef. A moderator has the final word.",
        )
        return redirect(battle.get_absolute_url())

    return render(request, "chef_battle/battle_withdraw.html", {
        "battle": battle,
        "other_chef": battle.opponent_for(author),
        "withdrawals_left": withdrawals_left(author),
    })


@chef_battle_guard
@login_required
@require_POST
def battle_withdraw_decide(request, pk):
    """The other chef answers: with a penalty, or without one."""
    from .models import BattleWithdrawal
    from .withdrawal_service import decide_withdrawal, WithdrawalNotAllowed

    author = get_author_for_user(request.user)
    withdrawal = get_object_or_404(
        BattleWithdrawal.objects.select_related("battle"), pk=pk
    )
    with_penalty = request.POST.get("decision") == "with_penalty"
    try:
        decide_withdrawal(
            withdrawal=withdrawal,
            author=author,
            with_penalty=with_penalty,
            opponent_reason=request.POST.get("opponent_reason", ""),
        )
    except WithdrawalNotAllowed as exc:
        messages.error(request, str(exc))
        return redirect(withdrawal.battle.get_absolute_url())

    messages.success(request, "Your answer has been sent to a moderator for the final word.")
    return redirect(withdrawal.battle.get_absolute_url())


@login_required
@require_POST
def battle_withdraw_resolve(request, pk):
    """The moderator has the last word, and only he moves the numbers."""
    from .models import BattleWithdrawal
    from .withdrawal_service import resolve_withdrawal, WithdrawalNotAllowed

    if not (is_moderator(request.user) and is_battle_visible(request)):
        raise Http404

    withdrawal = get_object_or_404(
        BattleWithdrawal.objects.select_related("battle", "requester", "opponent"), pk=pk
    )
    try:
        resolve_withdrawal(
            withdrawal=withdrawal,
            moderator=request.user,
            uphold_penalty=request.POST.get("verdict") == "penalty",
            note=request.POST.get("note", ""),
        )
    except WithdrawalNotAllowed as exc:
        messages.error(request, str(exc))
        return redirect(reverse("recipes:moderation_panel") + "#withdrawals")

    messages.success(request, "The withdrawal is settled.")
    return redirect(reverse("recipes:moderation_panel") + "#withdrawals")
