from django.contrib import admin

from .models import (
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
    CosmeticItem,
    Season,
    SeasonStanding,
)


@admin.register(ChefBattleProfile)
class ChefBattleProfileAdmin(admin.ModelAdmin):
    list_display = ("author", "rank", "rating", "wins", "losses", "refused_battles", "battle_moves", "seasonal_score")
    list_filter = ("rank",)
    search_fields = ("author__name", "author__slug")


@admin.register(BattleChallenge)
class BattleChallengeAdmin(admin.ModelAdmin):
    list_display = ("theme", "challenger", "opponent", "battle_type", "status", "created_at", "expires_at")
    list_filter = ("status", "battle_type")
    search_fields = ("theme", "challenger__name", "opponent__name")


class BattleEntryInline(admin.TabularInline):
    model = BattleEntry
    extra = 0


class BattleEventInline(admin.TabularInline):
    model = BattleEvent
    extra = 0


@admin.register(Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display = ("theme", "challenger", "opponent", "status", "winner", "start_time", "end_time")
    list_filter = ("status", "battle_type")
    search_fields = ("theme", "challenger__name", "opponent__name")
    inlines = (BattleEntryInline, BattleEventInline)


@admin.register(BattleVote)
class BattleVoteAdmin(admin.ModelAdmin):
    list_display = ("battle", "voter", "voted_for", "created_at")
    search_fields = ("battle__theme", "voted_for__name", "voter__username")


admin.site.register(BattleEvent)
admin.site.register(BattleMoveTransaction)
admin.site.register(Artifact)
admin.site.register(ChefArtifact)
admin.site.register(CosmeticItem)
admin.site.register(ChefCosmetic)
admin.site.register(Season)
admin.site.register(SeasonStanding)
