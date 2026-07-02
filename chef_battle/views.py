from __future__ import annotations

from django.conf import settings
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from accounts.views import is_moderator
from monitoring.tracker import get_client_ip
from recipes.authoring import get_author_for_user
from recipes.models import RecipeAuthor

from .access import chef_battle_guard
from .forms import BattleChallengeForm, BattleEntryForm
from .fraud import (
    gate_account_age,
    gate_age_verified,
    gate_challenge_spam,
    gate_duplicate_device,
    gate_fraud_flagged,
    gate_gift_velocity,
    gate_participant_vote,
    gate_repeat_challenge_cooldown,
    gate_self_vote,
    gate_suspended_account,
    gate_vote_rate_ip,
    gate_withdrawal_consent,
    run_fraud_gates,
)
from .models import Artifact, Battle, BattleChatMessage, BattleChallenge, BattleEntry, BattleEvent, BattleVote, ChefArtifact, ChefBattleProfile, TokenWallet
from .selectors import (
    get_active_battles,
    get_battle_vote_counts,
    get_expired_active_battles,
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
    check_rank_matchup,
    check_payout_eligibility,
    create_battle_event,
    create_payout_request,
    fire_ingredient_shot,
    get_battles_awaiting_cooking_approval,
    get_biathlon_state,
    get_or_create_battle_profile,
    hash_request_value,
    place_ingredient_lock,
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
                {"label": "AllFresh / sponsor pilot", "detail": "Draft one sponsor-ready battle concept, value proposition and sample landing copy.", "status": "pending"},
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
                {"label": "Token package pricing", "detail": "5 packages live: Starter 100T/EUR10 to Executive 1400T/EUR80. Token Shop at /chef-battle/tokens/.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Artifact drop after battle", "detail": "Winner always drops 1 artifact. Loser 50% chance. Same rarity table: Common 30% to Legendary 8%.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Arena Rules page", "detail": "Full arena rules at /chef-battle/rules/ with artifact drop odds table and gift pricing.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Stripe token purchase", "detail": "Stripe checkout UI built. Live key, webhook and extended payment data storage moved to Phase 7.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Artifact gifting UI", "detail": "Gift panel on battle detail page: send appreciation gifts and battle artifact gifts to either chef. Wording update required: gifts are not permanently shown - artifact instances have a consumed/historical state.", "status": "done", "completed_at": "2026-06-13"},
            ],
        },
        {
            "title": "Phase 6 - Seasons, Clans And Sponsorship",
            "items": [
                {"label": "Seasons and leaderboards", "detail": "Season 1 leaderboard live at /chef-battle/season/. Seasonal score earned per win (+10). Resets each season.", "status": "done", "completed_at": "2026-06-13"},
                {"label": "Clan / team battles", "detail": "Team-based battle formats after individual battle mechanics are stable and tested.", "status": "pending"},
                {"label": "Sponsor battle integration", "detail": "Named sponsor battles, branded themes and sponsor landing pages after AllFresh pilot.", "status": "pending"},
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
                {"label": "Stage A3: Grey standing fields for anonymous visitors", "detail": "New arena SVG zone (owner-approved geometry ADDITION). Requires a lightweight anonymous presence signal - none exists today.", "status": "pending"},
                {"label": "Stage B1: Battle context in arena payload", "detail": "arena() + arena_state() now include battle_id, battle_phase, battle_url per in_battle chef. in_battle_map dict replaces raw in_battle_author_ids set.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B3: Chefs disappear from ring when in VS centre", "detail": "CENTRE_PHASES + FACING_PHASES constants in arena_puzzle.js. drawArena() vacates ring cell when chef.battle_phase is in either set — move not duplicate.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B2: Facing pair positioning (pre-combat)", "detail": "Challenge accepted (scheduled/menu_locked) -> show chefs in deterministic facing cells in the centre zone (not ring cells). _arena_center() returns type 'facing_pair' for SCHEDULED/MENU_LOCKED. drawFacingPair() places two cells at battle_id-deterministic angle, R=28, dist=48px from centre. Crossed swords ⚔ indicator between them.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B4: Completion → return to ring cells", "detail": "Handled implicitly by B1+B3: when battle reaches COMPLETED/CANCELLED it leaves ACTIVE_STATUSES, so in_battle_map no longer contains the chefs, their ring cells are rendered normally on the next poll.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage B5: Teleport animation", "detail": "SVG transitions between 20s polls. Ship static relocation first (done via B2+B3), animate second per original handoff advice.", "status": "pending"},
                {"label": "Stage C: Battle Room popup embedded on the arena", "detail": "OWNER APPROVED option A. Centre VS cell = one big link opening the popup: chef left vs right, artifacts visible (open battle), per-battle chat, voting, gifts - all via existing endpoints. 18+/legal affordances carry over unchanged.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage D1: Battle Room page becomes the antechamber", "detail": "battle_detail hero redesigned as antechamber: two chef comparison cards (avatar, name, rank, W/L/streak/rating), 'Watch Live in Arena' CTA for active battles. challenger_profile + opponent_profile added to context. D2 (where chefs do combat actions) remains an open owner decision — combat panels stay on this page for now.", "status": "done", "completed_at": "2026-07-02"},
                {"label": "Stage E1: Mandatory use of spectator-gifted artifacts", "detail": "Combat logic change + public rules update: chefs may use own artifacts, MUST use artifacts gifted by spectators during the battle. Appreciation gifts never affect the battle.", "status": "pending"},
                {"label": "Stage E2: Appreciation gifts sellable after battle", "detail": "New economy mechanic. Requires closed-loop token model (s14) and anti-gambling (s17) legal check BEFORE build. Rate and flow TBD with owner.", "status": "pending"},
                {"label": "Stage E3: Scheduled battle time + readiness gate", "detail": "Today battles start on accept. Needs a battle-time concept (who sets it - open owner decision) and a both-ready gate before the centre teleport.", "status": "pending"},
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
    from django.utils import timezone
    season_start = timezone.datetime(2026, 6, 1, tzinfo=timezone.get_current_timezone())
    profiles = (
        ChefBattleProfile.objects.select_related("author")
        .filter(seasonal_score__gt=0)
        .order_by("-seasonal_score", "-wins", "author__name")[:50]
    )
    return render(request, "chef_battle/season_leaderboard.html", {
        "profiles": profiles,
        "season_start": season_start,
        "season_name": "Season 1 · Summer 2026",
    })


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
            now = timezone.now()
            if profile is None:
                profile, _ = ChefBattleProfile.objects.get_or_create(author=author)
            profile.enrolled_at = now
            if not profile.age_verified:
                profile.age_verified = True
                profile.age_confirmed_at = now
            profile.save(update_fields=["enrolled_at", "age_verified", "age_confirmed_at"])
            return redirect("chef_battle:enroll_success")

    return render(request, "chef_battle/enroll.html", {"error": error})


@login_required
def enroll_success(request):
    """Confirmation page shown immediately after successful Chef enrollment."""
    author = get_author_for_user(request.user)
    return render(request, "chef_battle/enroll_success.html", {"author": author})


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

    if profile.age_verified:
        return redirect(request.GET.get("next") or "chef_battle:home")

    error = None
    if request.method == "POST":
        if request.POST.get("confirm_age") == "1":
            profile.age_verified = True
            profile.age_confirmed_at = timezone.now()
            profile.save(update_fields=["age_verified", "age_confirmed_at"])
            from django.contrib import messages as _msg
            _msg.success(request, "Age confirmed. You can now use Arena paid features.")
            return redirect(request.GET.get("next") or "chef_battle:token_shop")
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

    fraud_result = run_fraud_gates([
        (gate_suspended_account, (author,), {}),
        (gate_fraud_flagged, (author,), {}),
        (gate_age_verified, (author,), {}),
        (gate_withdrawal_consent, (withdrawal_waived,), {}),
    ])
    if not fraud_result.passed:
        first_fail = next(g for g in fraud_result.gates if not g.passed)
        _CHECKOUT_FRAUD_MESSAGES = {
            "suspended_account": "Your account is suspended.",
            "fraud_flagged": "Your account has been flagged. Please contact support.",
            "age_verified": "You must confirm that you are 18 or older before purchasing tokens.",
            "withdrawal_consent": "You must confirm the digital content consent before purchasing tokens.",
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
    if order_id:
        order = TokenOrder.objects.filter(pk=order_id).select_related("package").first()
    if order and order.status == "pending":
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
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
        "season_name": "Season 1 · Summer 2026",
        "season_dates": "1 Jun – 31 Aug 2026",
        "season_leaders": season_leaders,
        "viewer_author": viewer_author,
        "user_enrolled": user_enrolled,
    })


_ARENA_ONLINE_THRESHOLD = 180  # seconds — chef counts as online if seen within 3 min


def _arena_center(active_battle):
    """Centre-cell payload: active battle takes priority, then the current
    Crown holder (if any), else empty. Shared by arena() and arena_state()."""
    if active_battle:
        is_facing = active_battle.status in {Battle.Status.SCHEDULED, Battle.Status.MENU_LOCKED}
        return {
            "type": "facing_pair" if is_facing else "active_battle",
            "battle_id": active_battle.pk,
            "battle_phase": active_battle.status.value,
            "battle_url": reverse("chef_battle:battle_detail", kwargs={"pk": active_battle.pk}),
            "popup_url": reverse("chef_battle:arena_battle_popup"),
            "challenger": {
                "name": active_battle.challenger.name,
                "avatar_url": active_battle.challenger.display_avatar_url,
            },
            "opponent": {
                "name": active_battle.opponent.name,
                "avatar_url": active_battle.opponent.display_avatar_url,
            },
        }

    crown_holder = (
        ChefBattleProfile.objects.select_related("author")
        .filter(crown_until__gt=timezone.now())
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


def arena_battle_popup(request):
    """AJAX partial — Battle Room popup embedded on the arena page.
    Returns an HTML fragment (no base.html). No login required — anonymous visitors
    can view the popup; voting and gifts require auth and are gated in the target views.
    """
    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST, APPRECIATION_GIFT_EMOJI

    active = list(get_active_battles(limit=1))
    if not active:
        return render(request, "chef_battle/arena_battle_popup.html", {"no_battle": True})

    battle = active[0]
    vote_counts = get_battle_vote_counts(battle)

    challenger_artifacts = list(
        ChefArtifact.objects
        .filter(
            chef=battle.challenger,
            status__in=[ChefArtifact.Status.AVAILABLE, ChefArtifact.Status.RESERVED],
        )
        .select_related("artifact")
        .order_by("-artifact__effect_value")[:6]
    )
    opponent_artifacts = list(
        ChefArtifact.objects
        .filter(
            chef=battle.opponent,
            status__in=[ChefArtifact.Status.AVAILABLE, ChefArtifact.Status.RESERVED],
        )
        .select_related("artifact")
        .order_by("-artifact__effect_value")[:6]
    )

    recent_chat = list(
        BattleChatMessage.objects
        .filter(battle=battle, is_hidden=False)
        .order_by("created_at")[:20]
    )

    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    is_participant = bool(viewer_author and battle.author_is_participant(viewer_author))

    can_vote = bool(
        viewer_author
        and battle.status in {Battle.Status.ACTIVE, Battle.Status.VOTING}
        and not is_participant
    )
    has_voted = False
    if can_vote:
        has_voted = BattleVote.objects.filter(battle=battle, voter=request.user).exists()

    appreciation_gifts = [
        {
            "type": k,
            "label": AppreciationGiftType(k).label,
            "cost": v,
            "emoji": APPRECIATION_GIFT_EMOJI.get(k, "🎁"),
        }
        for k, v in APPRECIATION_GIFT_COST.items()
    ]
    viewer_token_balance = 0
    if viewer_author:
        wallet = TokenWallet.objects.filter(chef=viewer_author).first()
        viewer_token_balance = wallet.balance if wallet else 0

    now = timezone.now()
    time_remaining = None
    if hasattr(battle, "end_time") and battle.end_time and battle.end_time > now:
        delta = battle.end_time - now
        total_s = int(delta.total_seconds())
        h, rem = divmod(total_s, 3600)
        m = rem // 60
        time_remaining = f"{h}h {m}m" if h else f"{m}m"

    return render(request, "chef_battle/arena_battle_popup.html", {
        "battle": battle,
        "votes_for_challenger": vote_counts.get(battle.challenger_id, 0),
        "votes_for_opponent": vote_counts.get(battle.opponent_id, 0),
        "challenger_artifacts": challenger_artifacts,
        "opponent_artifacts": opponent_artifacts,
        "recent_chat": recent_chat,
        "viewer_author": viewer_author,
        "is_participant": is_participant,
        "can_vote": can_vote,
        "has_voted": has_voted,
        "appreciation_gifts": appreciation_gifts,
        "viewer_token_balance": viewer_token_balance,
        "time_remaining": time_remaining,
    })


def _arena_latest_result():
    """Most recently completed battle, for the arena-wide win celebration
    (.battle-blast). The client tracks battle_id and only celebrates a
    battle it hasn't already shown, so this can just always return the
    single latest one -- no separate "new since" filtering needed here."""
    battle = (
        Battle.objects.select_related("winner", "loser")
        .filter(status=Battle.Status.COMPLETED, winner__isnull=False)
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


def _get_spectators(enrolled_author_ids, limit=40):
    """Authors with token balance who are not enrolled chefs, up to `limit`."""
    wallets = (
        TokenWallet.objects
        .select_related("chef")
        .filter(balance__gt=0)
        .exclude(chef_id__in=enrolled_author_ids)
        .order_by("-balance")[:limit]
    )
    spectators = []
    for w in wallets:
        spectators.append({
            "name": w.chef.name,
            "slug": w.chef.slug,
            "avatar_url": w.chef.display_avatar_url,
            "tokens": w.balance,
        })
    return spectators


def arena(request):
    active_battles = get_active_battles()
    active_battle = active_battles[0] if active_battles else None
    in_battle_author_ids = set()
    in_battle_map: dict[int, dict] = {}
    for battle in active_battles:
        info = {
            "battle_id": battle.id,
            "battle_phase": battle.status,
            "battle_url": battle.get_absolute_url(),
        }
        in_battle_map[battle.challenger_id] = info
        in_battle_map[battle.opponent_id] = info
        in_battle_author_ids.add(battle.challenger_id)
        in_battle_author_ids.add(battle.opponent_id)

    online_cutoff = timezone.now() - timezone.timedelta(seconds=_ARENA_ONLINE_THRESHOLD)

    enrolled = list(
        ChefBattleProfile.objects
        .select_related("author")
        .filter(enrolled_at__isnull=False, is_suspended=False)
        .order_by("-rating")
    )

    enrolled_author_ids = {p.author_id for p in enrolled}

    artifact_agg = {
        a["chef_id"]: a
        for a in ChefArtifact.objects.filter(
            chef_id__in=enrolled_author_ids,
            status=ChefArtifact.Status.AVAILABLE,
        ).values("chef_id").annotate(
            atk=Coalesce(Sum("artifact__effect_value", filter=Q(artifact__effect_type="attack")), 0),
            def_=Coalesce(Sum("artifact__effect_value", filter=Q(artifact__effect_type="defence")), 0),
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
            "atk": agg.get("atk", 0),
            "def": agg.get("def_", 0),
            "in_battle": battle_info is not None,
            "battle_id": battle_info["battle_id"] if battle_info else None,
            "battle_phase": battle_info["battle_phase"] if battle_info else None,
            "battle_url": battle_info["battle_url"] if battle_info else None,
            "is_online": bool(profile.last_seen_at and profile.last_seen_at >= online_cutoff),
        })

    center = _arena_center(active_battle)

    spectators = _get_spectators(enrolled_author_ids)

    arena_data = {
        "rings": {
            rank.value: chefs_by_rank[rank.value]
            for rank in ChefBattleProfile.Rank
        },
        "spectators": spectators,
        "center": center,
        "latest_result": _arena_latest_result(),
    }

    # Opt-in preview of the active-battle centre (Phase 1 choreography).
    # /chef-battle/arena/?demo=vs stages the two-cell VS centre using two real
    # enrolled chefs, so the owner can see and tune it without an active battle.
    # Purely visual, no DB writes; only for logged-in users who add the param.
    # Temporary verification aid — remove once the geometry is signed off.
    if request.GET.get("demo") == "vs" and request.user.is_authenticated:
        demo_pair = list(enrolled[:2])
        if len(demo_pair) >= 2:
            arena_data["center"] = {
                "type": "active_battle",
                "battle_url": "#",
                "challenger": {
                    "name": demo_pair[0].author.name,
                    "avatar_url": demo_pair[0].author.display_avatar_url,
                },
                "opponent": {
                    "name": demo_pair[1].author.name,
                    "avatar_url": demo_pair[1].author.display_avatar_url,
                },
            }

    rank_groups = [
        (rank, chefs_by_rank[rank.value])
        for rank in ChefBattleProfile.Rank
    ]

    # Update last_seen_at for the authenticated viewer
    viewer_author = None
    user_enrolled = False
    if request.user.is_authenticated:
        viewer_author = get_author_for_user(request.user)
        if viewer_author:
            ChefBattleProfile.objects.filter(
                author=viewer_author, enrolled_at__isnull=False
            ).update(last_seen_at=timezone.now())
            try:
                user_enrolled = bool(viewer_author.battle_profile.enrolled_at)
            except ChefBattleProfile.DoesNotExist:
                user_enrolled = False

    return render(request, "chef_battle/arena.html", {
        "rank_groups": rank_groups,
        "spectator_count": len(spectators),
        "active_battle": active_battle,
        "arena_data": arena_data,
        "viewer_author": viewer_author,
        "user_enrolled": user_enrolled,
    })


@require_POST
def arena_ping(request):
    """Heartbeat — updates last_seen_at for the authenticated chef. Called from JS every 60s."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False}, status=401)
    author = get_author_for_user(request.user)
    if author:
        ChefBattleProfile.objects.filter(
            author=author, enrolled_at__isnull=False
        ).update(last_seen_at=timezone.now())
    return JsonResponse({"ok": True})


@require_POST
def arena_state(request):
    """Lightweight state poll — returns updated ring data for JS to refresh SVG."""
    active_battles = get_active_battles()
    active_battle = active_battles[0] if active_battles else None
    in_battle_author_ids = set()
    in_battle_map: dict[int, dict] = {}
    for battle in active_battles:
        info = {
            "battle_id": battle.id,
            "battle_phase": battle.status,
            "battle_url": battle.get_absolute_url(),
        }
        in_battle_map[battle.challenger_id] = info
        in_battle_map[battle.opponent_id] = info
        in_battle_author_ids.add(battle.challenger_id)
        in_battle_author_ids.add(battle.opponent_id)

    online_cutoff = timezone.now() - timezone.timedelta(seconds=_ARENA_ONLINE_THRESHOLD)

    enrolled = list(
        ChefBattleProfile.objects
        .select_related("author")
        .filter(enrolled_at__isnull=False, is_suspended=False)
        .order_by("-rating")
    )

    enrolled_author_ids = {p.author_id for p in enrolled}

    artifact_agg = {
        a["chef_id"]: a
        for a in ChefArtifact.objects.filter(
            chef_id__in=enrolled_author_ids,
            status=ChefArtifact.Status.AVAILABLE,
        ).values("chef_id").annotate(
            atk=Coalesce(Sum("artifact__effect_value", filter=Q(artifact__effect_type="attack")), 0),
            def_=Coalesce(Sum("artifact__effect_value", filter=Q(artifact__effect_type="defence")), 0),
        )
    }

    rings = {choice.value: [] for choice in ChefBattleProfile.Rank}
    for profile in enrolled:
        agg = artifact_agg.get(profile.author_id, {})
        battle_info = in_battle_map.get(profile.author_id)
        rings[profile.rank].append({
            "name": profile.author.name,
            "slug": profile.author.slug,
            "avatar_url": profile.author.display_avatar_url,
            "rank": profile.rank,
            "rank_label": profile.get_rank_display(),
            "rating": profile.rating,
            "wins": profile.wins,
            "losses": profile.losses,
            "win_streak": profile.win_streak,
            "atk": agg.get("atk", 0),
            "def": agg.get("def_", 0),
            "in_battle": battle_info is not None,
            "battle_id": battle_info["battle_id"] if battle_info else None,
            "battle_phase": battle_info["battle_phase"] if battle_info else None,
            "battle_url": battle_info["battle_url"] if battle_info else None,
            "is_online": bool(profile.last_seen_at and profile.last_seen_at >= online_cutoff),
        })

    center = _arena_center(active_battle)

    spectators = _get_spectators(enrolled_author_ids)
    return JsonResponse({
        "rings": rings,
        "spectators": spectators,
        "center": center,
        "latest_result": _arena_latest_result(),
    })


@chef_battle_guard
@login_required
def challenge_list(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author profile required before entering Chef Battles.")
        return redirect("home")

    sent = get_sent_challenges(author)
    received = get_received_challenges(author)
    return render(request, "chef_battle/challenge_list.html", {
        "author": author,
        "sent_challenges": sent,
        "received_challenges": received,
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

    if request.method == "POST":
        form = BattleChallengeForm(request.POST, challenger=author)
        if form.is_valid():
            opponent = form.cleaned_data["opponent"]
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
            ])
            if not fraud_result.passed:
                first_fail = next(g for g in fraud_result.gates if not g.passed)
                _CHALLENGE_FRAUD_MESSAGES = {
                    "suspended_account": "Your account is suspended.",
                    "fraud_flagged": "Your account has been flagged. Please contact support.",
                    "challenge_spam": "You have sent too many challenges today. Please wait before sending another.",
                    "repeat_challenge_cooldown": "You have recently challenged this chef. Please wait before challenging again.",
                }
                messages.error(request, _CHALLENGE_FRAUD_MESSAGES.get(first_fail.gate, "Challenge not accepted."))
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
        form = BattleChallengeForm(challenger=author, initial=initial)

    return render(request, "chef_battle/challenge_form.html", {"form": form})


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
        challenge.status = BattleChallenge.Status.EXPIRED
        challenge.save(update_fields=["status"])
        messages.warning(request, "This challenge has expired.")
        return redirect("chef_battle:challenge_list")

    action = request.POST.get("action")
    if action == "accept":
        battle = accept_challenge(challenge)
        messages.success(request, "Challenge accepted. The battle room is live.")
        return redirect(battle.get_absolute_url())
    if action == "refuse":
        refuse_challenge(challenge)
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
    if battle.end_time <= timezone.now() and battle.status != Battle.Status.COMPLETED:
        battle = calculate_battle_result(battle)
    else:
        reveal_entries_if_ready(battle)
        battle.refresh_from_db()

    vote_counts = get_battle_vote_counts(battle)
    entries = battle.entries.select_related("author", "recipe", "article").order_by("submitted_at")
    events = battle.events.select_related("actor", "target").filter(is_public=True).order_by("-created_at")[:20]
    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    viewer_entry = None
    if viewer_author:
        viewer_entry = battle.entries.filter(author=viewer_author).first()
    can_submit = bool(
        viewer_author
        and battle.author_is_participant(viewer_author)
        and not viewer_entry
        and battle.status in {Battle.Status.MENU_LOCKED, Battle.Status.ACTIVE, Battle.Status.VOTING}
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

    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST, APPRECIATION_GIFT_EMOJI
    appreciation_gifts = [
        {"type": k, "label": AppreciationGiftType(k).label, "cost": v, "emoji": APPRECIATION_GIFT_EMOJI.get(k, "🎁")}
        for k, v in APPRECIATION_GIFT_COST.items()
    ]
    viewer_token_balance = 0
    if viewer_author:
        from .models import TokenWallet
        wallet = TokenWallet.objects.filter(chef=viewer_author).first()
        viewer_token_balance = wallet.balance if wallet else 0

    viewer_is_challenger = bool(viewer_author and viewer_author.pk == battle.challenger_id)
    can_set_ready = (
        is_participant
        and battle.status == Battle.Status.SCHEDULED
        and not (battle.challenger_ready if viewer_is_challenger else battle.opponent_ready)
    )

    return render(request, "chef_battle/battle_detail.html", {
        "battle": battle,
        "entries": entries,
        "events": events,
        "vote_counts": vote_counts,
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
        "viewer_token_balance": viewer_token_balance,
        "active_statuses": Battle.ACTIVE_STATUSES,
        "battle_participants": [battle.challenger, battle.opponent],
        "challenger_profile": challenger_profile,
        "opponent_profile": opponent_profile,
    })


@chef_battle_guard
@login_required
def battle_entry_submit(request, pk):
    author = get_author_for_user(request.user)
    battle = get_object_or_404(Battle, pk=pk)
    if not battle.author_is_participant(author):
        raise PermissionDenied
    if battle.entries.filter(author=author).exists():
        messages.warning(request, "You have already submitted an entry for this battle.")
        return redirect(battle.get_absolute_url())
    if timezone.now() > battle.submission_deadline:
        messages.error(request, "The submission deadline has passed.")
        return redirect(battle.get_absolute_url())

    if request.method == "POST":
        form = BattleEntryForm(request.POST, author=author, battle=battle)
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
        form = BattleEntryForm(author=author, battle=battle)

    return render(request, "chef_battle/entry_form.html", {"battle": battle, "form": form})


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

    voted_for = get_object_or_404(RecipeAuthor, pk=request.POST.get("voted_for"))
    if voted_for.pk not in {battle.challenger_id, battle.opponent_id}:
        messages.error(request, "Choose one of the battle chefs.")
        return redirect(battle.get_absolute_url())

    user = request.user if request.user.is_authenticated else None
    voter_author = get_author_for_user(user) if user else None

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
        voted_for=voted_for,
        ip_hash=ip_hash,
        user_agent_hash=ua_hash,
    )
    try:
        vote.full_clean()
        vote.save()
    except (IntegrityError, ValidationError):
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
    rank_tiers = [
        {"slug": "porter",  "name": "Kitchen Porters",   "pts": "0"},
        {"slug": "prep",    "name": "Prep Chefs",        "pts": "100"},
        {"slug": "commis",  "name": "Commis Chefs",      "pts": "200"},
        {"slug": "partie",  "name": "Chefs de Partie",   "pts": "300"},
        {"slug": "sous",    "name": "Sous Chefs",        "pts": "400"},
        {"slug": "head",    "name": "Head Chefs",        "pts": "500"},
        {"slug": "exec",    "name": "Executive Chefs",   "pts": "600"},
        {"slug": "master",  "name": "Culinary Masters",  "pts": "700+"},
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

    try:
        submit_combat_action(battle, author, action_type, moves_invested)
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
def battle_state_poll(request, pk):
    """Lightweight GET endpoint — returns current combat state for auto-poll."""
    from django.http import JsonResponse
    from .services import get_combat_state
    from .models import BattleCombatAction

    battle = get_object_or_404(Battle, pk=pk)
    author = get_author_for_user(request.user)
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
        "is_loser": viewer_author and battle.loser_id == viewer_author.pk,
    })


@login_required
@require_POST
def biathlon_lock(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    try:
        index = int(request.POST.get("ingredient_index", -1))
        place_ingredient_lock(battle=battle, chef=viewer_author, ingredient_index=index)
        messages.success(request, "Lock placed.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect("chef_battle:biathlon", pk=pk)


@login_required
@require_POST
def biathlon_shoot(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    viewer_author = get_author_for_user(request.user)
    try:
        index = int(request.POST.get("target_index", -1))
        shot = fire_ingredient_shot(battle=battle, shooter=viewer_author, target_index=index)
        if shot.bounced:
            messages.warning(request, "Your shot bounced off a lock!")
        else:
            messages.success(request, "Direct hit!")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    return redirect("chef_battle:biathlon", pk=pk)


@login_required
def cooking_moderation(request):
    if not is_moderator(request.user):
        raise PermissionDenied
    battles = get_battles_awaiting_cooking_approval()
    return render(request, "chef_battle/cooking_moderation.html", {"battles": battles})


@login_required
@require_POST
def cooking_moderation_approve(request, pk):
    if not is_moderator(request.user):
        raise PermissionDenied
    battle = get_object_or_404(Battle, pk=pk)
    try:
        approve_cooking_phase(battle, request.user)
        messages.success(request, f"Cooking phase approved for: {battle.theme}")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("chef_battle:cooking_moderation")


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
        return redirect("chef_battle:battle_detail", pk=pk)

    return render(request, "chef_battle/cooking_submit.html", {
        "battle": battle,
        "my_entry": my_entry,
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
def battle_chat_send(request, pk):
    battle = get_object_or_404(Battle, pk=pk)
    if battle.status not in Battle.ACTIVE_STATUSES | {Battle.Status.COMPLETED}:
        return redirect("chef_battle:battle_detail", pk=pk)

    from .models import BattleChatMessage
    body = request.POST.get("body", "").strip()[:300]
    if not body:
        return redirect("chef_battle:battle_detail", pk=pk)

    if request.user.is_authenticated:
        display_name = request.user.get_full_name() or request.user.username
    else:
        display_name = request.POST.get("display_name", "").strip()[:60] or "Anonymous"

    BattleChatMessage.objects.create(
        battle=battle,
        author=request.user if request.user.is_authenticated else None,
        display_name=display_name,
        body=body,
    )
    return redirect("chef_battle:battle_detail", pk=pk)


def battle_chat_poll(request, pk):
    from django.http import JsonResponse
    from .models import BattleChatMessage
    battle = get_object_or_404(Battle, pk=pk)
    since_id = int(request.GET.get("since", 0))
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


def chef_battle_profile(request, slug):
    from django.db.models import Q, Count
    from .models import AppreciationGiftType, APPRECIATION_GIFT_COST, APPRECIATION_GIFT_EMOJI
    author = get_object_or_404(RecipeAuthor, slug=slug)
    profile = get_object_or_404(ChefBattleProfile, author=author)
    battles = (
        Battle.objects
        .filter(Q(challenger=author) | Q(opponent=author))
        .select_related("challenger", "opponent", "challenge")
        .order_by("-created_at")[:20]
    )
    # Aggregate gifts by type
    gift_counts = (
        author.appreciation_gifts
        .values("gift_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    gift_display = [
        {
            "type": g["gift_type"],
            "label": AppreciationGiftType(g["gift_type"]).label,
            "count": g["total"],
            "emoji": APPRECIATION_GIFT_EMOJI.get(g["gift_type"], "🎁"),
        }
        for g in gift_counts
    ]
    viewer_author = get_author_for_user(request.user) if request.user.is_authenticated else None
    return render(request, "chef_battle/chef_profile.html", {
        "profile": profile,
        "author": author,
        "battles": battles,
        "gift_display": gift_display,
        "is_own_profile": viewer_author and viewer_author.pk == author.pk,
    })


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

    if not (is_moderator(request.user) or request.user.is_staff):
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


def appreciation_gallery(request):
    """Public gallery of all appreciation gift types with cost and description."""
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


@login_required
def battle_chest(request):
    """Chef's personal artifact inventory (backpack / chest)."""
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

    wallet = None
    try:
        wallet = TokenWallet.objects.get(chef=author)
    except TokenWallet.DoesNotExist:
        pass

    return render(request, "chef_battle/battle_chest.html", {
        "available": available,
        "reserved": reserved,
        "consumed": consumed,
        "total": all_owned.count(),
        "wallet": wallet,
    })


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

    available_artifacts = (
        ChefArtifact.objects.filter(chef=author, status="available")
        .select_related("artifact")
        .order_by("artifact__rarity", "artifact__name")
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
        "my_active_battles": my_active_battles,
        "wallet": wallet,
        "energy_cap": ENERGY_CAP,
        "moves_min_to_challenge": MOVES_MIN_TO_CHALLENGE,
    })


# ── E3: Readiness Gate ──────────────────────────────────────────────────────

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
        battle.status = Battle.Status.MENU_LOCKED
        battle.save(update_fields=["challenger_ready", "opponent_ready", "status", "updated_at"])
        create_battle_event(
            battle,
            event_type="status_change",
            note="Both chefs ready — battle advanced to menu declaration phase.",
            author=author,
        )
        messages.success(request, "Both chefs are ready! Declare your ingredients now.")
    else:
        battle.save(update_fields=["challenger_ready", "opponent_ready", "updated_at"])
        messages.success(request, "You're ready! Waiting for your opponent.")

    return redirect("chef_battle:battle_detail", pk=pk)

