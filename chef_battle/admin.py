from django.contrib import admin, messages
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
from .services import create_battle_event


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

@admin.register(ChefBattleProfile)
class ChefBattleProfileAdmin(admin.ModelAdmin):
    list_display = (
        "author", "rank", "rating", "wins", "losses", "win_streak",
        "best_win_streak", "refused_battles", "ignored_battles",
        "crown_count", "battle_moves", "seasonal_score",
    )
    list_filter = ("rank",)
    search_fields = ("author__name", "author__slug")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-rating",)


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


@admin.register(ChefArtifact)
class ChefArtifactAdmin(admin.ModelAdmin):
    list_display = ("chef", "artifact", "source", "status", "equipped", "earned_at", "consumed_at")
    list_filter = ("equipped", "source", "status")
    search_fields = ("chef__name", "artifact__name")
    readonly_fields = ("earned_at", "consumed_at")
    ordering = ("-earned_at",)


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
    list_display = ("wallet", "package", "tokens", "amount_eur_cents", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("wallet__chef__name", "stripe_checkout_session_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(ProcessedTokenStripeEvent)
class ProcessedTokenStripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "received_at")
    readonly_fields = ("event_id", "event_type", "received_at")
    ordering = ("-received_at",)


@admin.register(RewardRecord)
class RewardRecordAdmin(admin.ModelAdmin):
    list_display = ("recipient", "reward_type", "tokens_granted", "reason", "granted_by", "created_at")
    list_filter = ("reward_type",)
    search_fields = ("recipient__name", "reason")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(LedgerEvent)
class LedgerEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "actor", "target", "related_battle", "created_at")
    list_filter = ("event_type",)
    search_fields = ("actor__name", "target__name")
    readonly_fields = ("event_type", "actor", "target", "related_battle", "payload", "created_at")
    ordering = ("-created_at",)

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
