from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from .models import (
    AppreciationGift,
    Artifact,
    Battle,
    BattleChallenge,
    BattleEntry,
    BattleEvent,
    BattleMoveTransaction,
    BattleVote,
    ChefArtifact,
    ChefBattleProfile,
    ChefCosmetic,
    ContentReport,
    CosmeticItem,
    LedgerEvent,
    ProcessedTokenStripeEvent,
    RewardRecord,
    Season,
    SeasonStanding,
    TokenOrder,
    TokenPackage,
    TokenTransaction,
    TokenWallet,
    ViewerBattleGift,
)
from .services import create_battle_event, issue_reward, reverse_reward


# ---------------------------------------------------------------------------
# CB-0014 Admin actions
# ---------------------------------------------------------------------------

@admin.action(description="Cancel selected challenges")
def cancel_challenges(modeladmin, request, queryset):
    cancellable = queryset.exclude(status__in=[
        BattleChallenge.Status.ACCEPTED,
        BattleChallenge.Status.CANCELLED,
    ])
    count = cancellable.update(status=BattleChallenge.Status.CANCELLED, cancelled_at=timezone.now())
    modeladmin.message_user(request, f"{count} challenge(s) cancelled.", messages.SUCCESS)


@admin.action(description="Cancel selected battles")
def cancel_battles(modeladmin, request, queryset):
    cancellable = queryset.exclude(status__in=[
        Battle.Status.COMPLETED,
        Battle.Status.CANCELLED,
    ])
    count = 0
    for battle in cancellable:
        battle.status = Battle.Status.CANCELLED
        battle.save(update_fields=["status", "updated_at"])
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_FINISHED,
            battle=battle,
            message=f"Battle cancelled by staff: {battle.theme}.",
            is_public=False,
        )
        count += 1
    modeladmin.message_user(request, f"{count} battle(s) cancelled.", messages.SUCCESS)


@admin.action(description="Force-reveal entries for selected battles")
def force_reveal_entries(modeladmin, request, queryset):
    count = 0
    for battle in queryset.filter(status__in=[Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS]):
        battle.entries.filter(is_revealed=False).update(is_revealed=True)
        battle.status = Battle.Status.VOTING
        battle.save(update_fields=["status", "updated_at"])
        count += 1
    modeladmin.message_user(request, f"Entries revealed for {count} battle(s).", messages.SUCCESS)


@admin.action(description="Force-complete selected battles (recalculate winner)")
def force_complete_battles(modeladmin, request, queryset):
    from .services import calculate_battle_result
    count = 0
    for battle in queryset.exclude(status=Battle.Status.COMPLETED):
        calculate_battle_result(battle)
        count += 1
    modeladmin.message_user(request, f"{count} battle(s) force-completed.", messages.SUCCESS)


@admin.action(description="Reset disputed battles to Voting")
def reset_disputed_battles(modeladmin, request, queryset):
    count = queryset.filter(status=Battle.Status.DISPUTED).update(
        status=Battle.Status.VOTING,
    )
    modeladmin.message_user(request, f"{count} disputed battle(s) reset to voting.", messages.SUCCESS)


@admin.action(description="Mark selected votes as suspicious")
def mark_votes_suspicious(modeladmin, request, queryset):
    count = queryset.update(is_suspicious=True)
    modeladmin.message_user(request, f"{count} vote(s) marked suspicious.", messages.SUCCESS)


@admin.action(description="Clear suspicious flag on selected votes")
def clear_votes_suspicious(modeladmin, request, queryset):
    count = queryset.update(is_suspicious=False)
    modeladmin.message_user(request, f"{count} vote(s) cleared.", messages.SUCCESS)


# ---------------------------------------------------------------------------
# CB-0013 Model admin registrations
# ---------------------------------------------------------------------------

@admin.action(description="Suspend selected profiles")
def suspend_profiles(modeladmin, request, queryset):
    count = 0
    for profile in queryset.filter(is_suspended=False):
        profile.is_suspended = True
        profile.suspended_at = timezone.now()
        profile.suspension_reason = f"Suspended by {request.user.username}"
        profile.save(update_fields=["is_suspended", "suspended_at", "suspension_reason"])
        from .models import LedgerEvent
        LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.ACCOUNT_SUSPENDED,
            actor=profile.author,
            payload={"suspended_by": request.user.username, "reason": profile.suspension_reason},
        )
        count += 1
    modeladmin.message_user(request, f"{count} profile(s) suspended.", messages.WARNING)


@admin.action(description="Unsuspend selected profiles")
def unsuspend_profiles(modeladmin, request, queryset):
    count = queryset.filter(is_suspended=True).update(
        is_suspended=False, suspended_at=None, suspension_reason=""
    )
    modeladmin.message_user(request, f"{count} profile(s) unsuspended.", messages.SUCCESS)


@admin.action(description="Set fraud flag on selected profiles")
def set_fraud_flag(modeladmin, request, queryset):
    count = queryset.filter(fraud_flag=False).update(
        fraud_flag=True,
        fraud_flag_note=f"Flagged by {request.user.username} on {timezone.now().date()}",
    )
    modeladmin.message_user(request, f"{count} profile(s) fraud-flagged.", messages.WARNING)


@admin.action(description="Clear fraud flag on selected profiles")
def clear_fraud_flag(modeladmin, request, queryset):
    count = queryset.filter(fraud_flag=True).update(fraud_flag=False, fraud_flag_note="")
    modeladmin.message_user(request, f"{count} profile(s) fraud flag cleared.", messages.SUCCESS)


@admin.register(ChefBattleProfile)
class ChefBattleProfileAdmin(admin.ModelAdmin):
    list_display = (
        "author", "rank", "rating", "wins", "losses", "win_streak",
        "best_win_streak", "refused_battles", "ignored_battles",
        "crown_count", "battle_moves", "seasonal_score",
        "is_suspended", "fraud_flag",
    )
    list_filter = ("rank", "is_suspended", "fraud_flag", "is_hero")
    search_fields = ("author__name", "author__slug")
    readonly_fields = ("created_at", "updated_at", "suspended_at")
    actions = [suspend_profiles, unsuspend_profiles, set_fraud_flag, clear_fraud_flag]
    ordering = ("-rating",)
    fieldsets = (
        ("Chef", {
            "fields": ("author", "rank", "level", "is_hero", "rating", "reputation"),
        }),
        ("Stats", {
            "fields": (
                "wins", "losses", "win_streak", "best_win_streak",
                "refused_battles", "ignored_battles", "crown_count",
                "crown_until", "michelin_stars",
            ),
        }),
        ("Moves & Tokens", {
            "fields": ("battle_moves", "seasonal_score", "infinite_moves", "prestige_title"),
        }),
        ("Compliance", {
            "fields": (
                "age_verified", "age_confirmed_at",
                "is_suspended", "suspended_at", "suspension_reason",
                "fraud_flag", "fraud_flag_note", "dsa_reported_count",
            ),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(BattleChallenge)
class BattleChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "theme", "challenger", "opponent", "battle_type",
        "status", "created_at", "expires_at",
    )
    list_filter = ("status", "battle_type")
    search_fields = ("theme", "challenger__name", "opponent__name")
    readonly_fields = ("created_at", "accepted_at", "refused_at", "cancelled_at")
    actions = [cancel_challenges]
    ordering = ("-created_at",)


class BattleEntryInline(admin.TabularInline):
    model = BattleEntry
    extra = 0
    readonly_fields = ("submitted_at", "created_at", "updated_at")
    fields = (
        "author", "recipe", "article", "battle_statement",
        "is_revealed", "is_late", "moderation_status",
        "submitted_at",
    )


class BattleEventInline(admin.TabularInline):
    model = BattleEvent
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("event_type", "actor", "target", "message", "is_public", "created_at")


@admin.register(Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display = (
        "theme", "challenger", "opponent", "status",
        "winner", "start_time", "end_time", "crown_awarded",
    )
    list_filter = ("status", "battle_type", "crown_awarded")
    search_fields = ("theme", "challenger__name", "opponent__name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (BattleEntryInline, BattleEventInline)
    actions = [cancel_battles, force_reveal_entries, force_complete_battles, reset_disputed_battles]
    ordering = ("-created_at",)
    fieldsets = (
        ("Participants", {
            "fields": ("challenge", "challenger", "opponent", "theme", "battle_type"),
        }),
        ("Status & Timing", {
            "fields": (
                "status", "start_time", "submission_deadline",
                "reveal_time", "voting_deadline", "end_time",
            ),
        }),
        ("Result", {
            "fields": (
                "winner", "loser", "result_reason",
                "rating_delta_challenger", "rating_delta_opponent", "crown_awarded",
            ),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(BattleEntry)
class BattleEntryAdmin(admin.ModelAdmin):
    list_display = (
        "battle", "author", "moderation_status", "is_revealed",
        "is_late", "submitted_at",
    )
    list_filter = ("moderation_status", "is_revealed", "is_late")
    search_fields = ("battle__theme", "author__name")
    readonly_fields = ("submitted_at", "created_at", "updated_at")
    ordering = ("-submitted_at",)


@admin.register(BattleVote)
class BattleVoteAdmin(admin.ModelAdmin):
    list_display = (
        "battle", "voter", "voted_for", "is_suspicious", "created_at",
    )
    list_filter = ("is_suspicious",)
    search_fields = ("battle__theme", "voted_for__name", "voter__username")
    readonly_fields = ("created_at", "ip_hash", "user_agent_hash", "session_key_hash")
    actions = [mark_votes_suspicious, clear_votes_suspicious]
    ordering = ("-created_at",)


@admin.register(BattleEvent)
class BattleEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "actor", "target", "battle", "is_public", "created_at")
    list_filter = ("event_type", "is_public")
    search_fields = ("message", "actor__name", "target__name")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(BattleMoveTransaction)
class BattleMoveTransactionAdmin(admin.ModelAdmin):
    list_display = ("chef", "amount", "reason", "created_at")
    search_fields = ("chef__name", "reason")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("name", "rarity", "effect_type", "effect_value", "is_active")
    list_filter = ("rarity", "is_active")
    search_fields = ("name",)


class AdminArtifactGrantForm(forms.Form):
    chef = forms.ModelChoiceField(
        queryset=None,
        label="Chef (RecipeAuthor)",
        help_text="The chef who will receive the artifact.",
    )
    artifact = forms.ModelChoiceField(
        queryset=None,
        label="Artifact",
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Grant reason (mandatory)",
        help_text="Explain why this artifact is being granted. This is immutable audit data.",
        min_length=10,
    )

    def __init__(self, *args, **kwargs):
        from recipes.models import RecipeAuthor
        from .models import Artifact
        super().__init__(*args, **kwargs)
        self.fields["chef"].queryset = RecipeAuthor.objects.order_by("name")
        self.fields["artifact"].queryset = Artifact.objects.filter(is_active=True).order_by("name")


@admin.register(ChefArtifact)
class ChefArtifactAdmin(admin.ModelAdmin):
    list_display = (
        "chef", "artifact", "source", "status", "equipped",
        "earned_at", "consumed_at", "admin_granted_by",
    )
    list_filter = ("equipped", "source", "status")
    search_fields = ("chef__name", "artifact__name")
    readonly_fields = (
        "earned_at", "consumed_at", "reserved_in_battle",
        "expired_at", "reversed_at", "admin_granted_by", "admin_grant_reason",
    )
    ordering = ("-earned_at",)
    fieldsets = (
        (None, {"fields": ("chef", "artifact", "source", "status", "equipped")}),
        ("Consumption", {"fields": ("consumed_at", "consumed_in_battle", "reserved_in_battle")}),
        ("Lifecycle", {"fields": ("expired_at", "reversed_at")}),
        ("Admin Grant Audit", {"fields": ("admin_granted_by", "admin_grant_reason")}),
        ("Timestamps", {"fields": ("earned_at",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "grant-artifact/",
                self.admin_site.admin_view(self.grant_artifact_view),
                name="chef_battle_chefartifact_grant",
            )
        ]
        return custom + urls

    def grant_artifact_view(self, request):
        if not request.user.is_staff:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        form = AdminArtifactGrantForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            chef = form.cleaned_data["chef"]
            artifact = form.cleaned_data["artifact"]
            reason = form.cleaned_data["reason"]

            if ChefArtifact.objects.filter(chef=chef, artifact=artifact).exists():
                messages.error(request, f"{chef} already has {artifact}. Each artifact can only be held once.")
            else:
                instance = ChefArtifact.objects.create(
                    chef=chef,
                    artifact=artifact,
                    source=ChefArtifact.Source.ADMIN_GRANT,
                    status=ChefArtifact.Status.AVAILABLE,
                    admin_granted_by=request.user,
                    admin_grant_reason=reason,
                )
                LedgerEvent.objects.create(
                    event_type=LedgerEvent.EventType.ARTIFACT_GRANTED,
                    actor=chef,
                    payload={
                        "action": "admin_artifact_grant",
                        "artifact_id": artifact.pk,
                        "artifact_name": artifact.name,
                        "granted_by": request.user.username,
                        "reason": reason,
                        "chef_artifact_id": instance.pk,
                    },
                )
                messages.success(request, f"Artifact '{artifact}' granted to {chef}. Audit entry created.")
                return redirect("../")

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            title="Admin: Grant Artifact to Chef",
            opts=self.model._meta,
        )
        return render(request, "chef_battle/admin_grant_artifact.html", context)


@admin.register(CosmeticItem)
class CosmeticItemAdmin(admin.ModelAdmin):
    list_display = ("name", "item_type", "rarity", "price", "is_active")
    list_filter = ("rarity", "is_active", "item_type")
    search_fields = ("name",)


@admin.register(ChefCosmetic)
class ChefCosmeticAdmin(admin.ModelAdmin):
    list_display = ("chef", "item", "equipped", "purchased_at")
    list_filter = ("equipped",)
    search_fields = ("chef__name", "item__name")
    readonly_fields = ("purchased_at",)
    ordering = ("-purchased_at",)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "starts_at", "ends_at")
    list_filter = ("status",)
    search_fields = ("name",)
    ordering = ("-starts_at",)


@admin.register(SeasonStanding)
class SeasonStandingAdmin(admin.ModelAdmin):
    list_display = ("season", "chef", "score", "rank_position")
    list_filter = ("season",)
    search_fields = ("chef__name",)
    ordering = ("season", "rank_position")


@admin.register(AppreciationGift)
class AppreciationGiftAdmin(admin.ModelAdmin):
    list_display = ("gift_type", "recipient", "sender", "tokens_spent", "sent_at")
    list_filter = ("gift_type",)
    search_fields = ("recipient__name",)
    readonly_fields = ("sent_at",)
    ordering = ("-sent_at",)


@admin.register(ViewerBattleGift)
class ViewerBattleGiftAdmin(admin.ModelAdmin):
    list_display = ("artifact", "recipient", "battle", "tokens_spent", "is_applied", "sent_at")
    list_filter = ("is_applied",)
    search_fields = ("recipient__name", "artifact__name")
    readonly_fields = ("sent_at",)
    ordering = ("-sent_at",)


@admin.register(TokenPackage)
class TokenPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "tokens", "price_eur", "discount_percent", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "key")
    ordering = ("sort_order",)


@admin.register(TokenWallet)
class TokenWalletAdmin(admin.ModelAdmin):
    list_display = ("chef", "balance", "infinite_balance", "total_purchased", "total_spent", "updated_at")
    list_filter = ("infinite_balance",)
    search_fields = ("chef__name",)
    readonly_fields = ("updated_at",)


@admin.register(TokenTransaction)
class TokenTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "tx_type", "amount", "balance_after", "description", "created_at")
    list_filter = ("tx_type",)
    search_fields = ("wallet__chef__name", "description")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(TokenOrder)
class TokenOrderAdmin(admin.ModelAdmin):
    list_display = (
        "wallet", "package", "tokens", "amount_eur_cents",
        "vat_amount_cents", "right_of_withdrawal_waived", "status", "created_at",
    )
    list_filter = ("status", "right_of_withdrawal_waived")
    search_fields = ("wallet__chef__name", "stripe_checkout_session_id")
    list_display = (
        "wallet", "package", "tokens", "amount_eur_cents",
        "vat_amount_cents", "currency", "right_of_withdrawal_waived", "status", "credited_at", "created_at",
    )
    readonly_fields = (
        "created_at", "updated_at", "withdrawal_consent_at", "credited_at",
        "amount_net_cents", "vat_amount_cents", "vat_rate",
        "consent_text_snapshot", "stripe_customer_id", "stripe_invoice_id",
        "stripe_checkout_session_id", "stripe_payment_intent_id",
    )
    ordering = ("-created_at",)
    fieldsets = (
        ("Order", {
            "fields": ("wallet", "package", "tokens", "status"),
        }),
        ("Pricing & VAT", {
            "fields": (
                "amount_eur_cents", "amount_net_cents",
                "vat_amount_cents", "vat_rate", "currency",
            ),
        }),
        ("EU Consent", {
            "fields": (
                "right_of_withdrawal_waived", "withdrawal_consent_at",
                "consent_text_snapshot",
            ),
        }),
        ("Stripe", {
            "fields": (
                "stripe_checkout_session_id", "stripe_payment_intent_id",
                "stripe_customer_id", "stripe_invoice_id",
            ),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "credited_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(ProcessedTokenStripeEvent)
class ProcessedTokenStripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "received_at")
    readonly_fields = ("event_id", "event_type", "received_at")
    ordering = ("-received_at",)


@admin.action(description="Issue selected rewards (credit tokens to wallets)")
def issue_selected_rewards(modeladmin, request, queryset):
    issuable = queryset.filter(status__in=[
        RewardRecord.Status.PENDING,
        RewardRecord.Status.QUEUED,
        RewardRecord.Status.APPROVED,
    ])
    count = 0
    errors = 0
    for record in issuable:
        try:
            issue_reward(record.pk, reviewed_by=request.user)
            count += 1
        except Exception as exc:
            modeladmin.message_user(request, f"Error issuing reward #{record.pk}: {exc}", messages.ERROR)
            errors += 1
    if count:
        modeladmin.message_user(request, f"{count} reward(s) issued successfully.", messages.SUCCESS)


@admin.action(description="Reverse selected rewards (deduct tokens)")
def reverse_selected_rewards(modeladmin, request, queryset):
    reversible = queryset.filter(status=RewardRecord.Status.ISSUED)
    count = 0
    for record in reversible:
        try:
            reverse_reward(record.pk, note="Reversed by staff", reversed_by=request.user)
            count += 1
        except Exception as exc:
            modeladmin.message_user(request, f"Error reversing reward #{record.pk}: {exc}", messages.ERROR)
    if count:
        modeladmin.message_user(request, f"{count} reward(s) reversed.", messages.WARNING)


@admin.register(RewardRecord)
class RewardRecordAdmin(admin.ModelAdmin):
    list_display = (
        "recipient", "reward_type", "status", "tokens_granted",
        "reason", "granted_by", "issued_at", "created_at",
    )
    list_filter = ("reward_type", "status")
    search_fields = ("recipient__name", "reason")
    readonly_fields = (
        "created_at", "updated_at", "issued_at", "acknowledged_at",
        "reversed_at", "reviewed_by",
    )
    actions = [issue_selected_rewards, reverse_selected_rewards]
    ordering = ("-created_at",)
    fieldsets = (
        ("Reward", {
            "fields": (
                "recipient", "reward_type", "status", "tokens_granted",
                "reason", "expires_at",
            ),
        }),
        ("Links", {
            "fields": ("related_battle", "related_gift"),
        }),
        ("Lifecycle", {
            "fields": (
                "granted_by", "reviewed_by", "issued_at",
                "acknowledged_at", "reversed_at", "status_note",
            ),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.action(description="Verify hash chain integrity")
def verify_ledger_chain(modeladmin, request, queryset):
    ok, broken_pk = LedgerEvent.verify_chain()
    if ok:
        modeladmin.message_user(
            request, "Hash chain integrity check PASSED. No tampering detected.", messages.SUCCESS
        )
    else:
        modeladmin.message_user(
            request,
            f"Hash chain BROKEN at LedgerEvent pk={broken_pk}. Possible tampering — investigate immediately.",
            messages.ERROR,
        )


@admin.register(LedgerEvent)
class LedgerEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "actor", "target", "related_battle", "short_hash", "created_at")
    list_filter = ("event_type",)
    search_fields = ("actor__name", "target__name")
    readonly_fields = (
        "event_type", "actor", "target", "related_battle",
        "payload", "prev_hash", "event_hash", "created_at",
    )
    actions = [verify_ledger_chain]
    ordering = ("-created_at",)

    @admin.display(description="Hash")
    def short_hash(self, obj):
        return obj.event_hash[:12] + "…" if obj.event_hash else ""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = ("content_kind", "object_id", "reporter", "status", "created_at", "reviewed_at")
    list_filter = ("content_kind", "status")
    search_fields = ("reason", "moderator_note")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    fieldsets = (
        ("Report", {
            "fields": ("reporter", "content_kind", "object_id", "reason", "status", "created_at"),
        }),
        ("Moderation", {
            "fields": ("reviewed_by", "reviewed_at", "moderator_note"),
        }),
    )
