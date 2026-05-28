from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from articles.models import Article
from recipes.models import Recipe, RecipeAuthor


class ChefBattleProfile(models.Model):
    class Rank(models.TextChoices):
        KITCHEN_PORTER = "kitchen_porter", "Kitchen Porter"
        PREP_COOK = "prep_cook", "Prep Cook"
        COMMIS_CHEF = "commis_chef", "Commis Chef"
        CHEF_DE_PARTIE = "chef_de_partie", "Chef de Partie"
        SOUS_CHEF = "sous_chef", "Sous Chef"
        HEAD_CHEF = "head_chef", "Head Chef"
        EXECUTIVE_CHEF = "executive_chef", "Executive Chef"
        CULINARY_MASTER = "culinary_master", "Culinary Master"

    author = models.OneToOneField(
        RecipeAuthor,
        on_delete=models.CASCADE,
        related_name="battle_profile",
    )
    rank = models.CharField(max_length=32, choices=Rank.choices, default=Rank.KITCHEN_PORTER)
    rating = models.IntegerField(default=1000, db_index=True)
    reputation = models.IntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    refused_battles = models.PositiveIntegerField(default=0)
    win_streak = models.PositiveIntegerField(default=0)
    crown_until = models.DateTimeField(null=True, blank=True)
    battle_moves = models.PositiveIntegerField(default=0)
    seasonal_score = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "-wins", "author__name"]

    def __str__(self):
        return f"{self.author} - {self.get_rank_display()}"

    @property
    def has_crown(self) -> bool:
        return bool(self.crown_until and self.crown_until > timezone.now())


class BattleChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REFUSED = "refused", "Refused"
        EXPIRED = "expired", "Expired"

    class BattleType(models.TextChoices):
        RECIPE = "recipe", "Recipe Duel"
        ARTICLE = "article", "Article Duel"
        MIXED = "mixed", "Recipe Or Article"

    challenger = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="sent_battle_challenges")
    opponent = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="received_battle_challenges")
    theme = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    battle_type = models.CharField(max_length=16, choices=BattleType.choices, default=BattleType.RECIPE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    proposed_start_time = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    refused_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=~Q(challenger=models.F("opponent")),
                name="chef_battle_challenge_distinct_authors",
            ),
        ]

    def __str__(self):
        return f"{self.challenger} vs {self.opponent}: {self.theme}"


class Battle(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        VOTING = "voting", "Voting"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    challenge = models.OneToOneField(BattleChallenge, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle")
    challenger = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battles_as_challenger")
    opponent = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battles_as_opponent")
    theme = models.CharField(max_length=180)
    battle_type = models.CharField(max_length=16, choices=BattleChallenge.BattleType.choices, default=BattleChallenge.BattleType.RECIPE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    submission_deadline = models.DateTimeField()
    end_time = models.DateTimeField(db_index=True)
    winner = models.ForeignKey(RecipeAuthor, on_delete=models.SET_NULL, null=True, blank=True, related_name="won_battles")
    loser = models.ForeignKey(RecipeAuthor, on_delete=models.SET_NULL, null=True, blank=True, related_name="lost_battles")
    result_reason = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=~Q(challenger=models.F("opponent")),
                name="chef_battle_distinct_authors",
            ),
        ]

    def __str__(self):
        return f"{self.challenger} vs {self.opponent}: {self.theme}"

    def get_absolute_url(self):
        return reverse("chef_battle:battle_detail", kwargs={"pk": self.pk})

    def author_is_participant(self, author) -> bool:
        return bool(author and author.pk in {self.challenger_id, self.opponent_id})

    def opponent_for(self, author):
        if not author:
            return None
        if author.pk == self.challenger_id:
            return self.opponent
        if author.pk == self.opponent_id:
            return self.challenger
        return None


class BattleEntry(models.Model):
    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="entries")
    author = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_entries")
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle_entries")
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle_entries")
    note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_revealed = models.BooleanField(default=False)

    class Meta:
        ordering = ["submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["battle", "author"], name="one_battle_entry_per_author"),
        ]

    def __str__(self):
        return f"{self.author} entry for battle {self.battle_id}"

    def clean(self):
        super().clean()
        if bool(self.recipe) == bool(self.article):
            raise ValidationError("Choose exactly one recipe or article for the battle entry.")
        if self.recipe and self.recipe.author_id != self.author_id:
            raise ValidationError("The selected recipe must belong to the submitting author.")
        if self.article and self.article.author_id != self.author_id:
            raise ValidationError("The selected article must belong to the submitting author.")
        if self.battle_id and self.author_id and not self.battle.author_is_participant(self.author):
            raise ValidationError("Only battle participants can submit entries.")

    @property
    def content_object(self):
        return self.recipe or self.article


class BattleVote(models.Model):
    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_votes")
    voted_for = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_votes_received")
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "voter"],
                condition=Q(voter__isnull=False),
                name="one_authenticated_vote_per_battle",
            ),
            models.UniqueConstraint(
                fields=["battle", "ip_hash", "user_agent_hash"],
                condition=Q(voter__isnull=True) & ~Q(ip_hash="") & ~Q(user_agent_hash=""),
                name="one_anonymous_vote_per_battle_device",
            ),
        ]

    def clean(self):
        super().clean()
        if self.battle_id and self.voted_for_id not in {self.battle.challenger_id, self.battle.opponent_id}:
            raise ValidationError("Vote must be for one of the battle participants.")
        voter_author = RecipeAuthor.objects.filter(user=self.voter).first() if self.voter_id else None
        if voter_author and voter_author.pk == self.voted_for_id:
            raise ValidationError("Chefs cannot vote for themselves.")


class BattleEvent(models.Model):
    class EventType(models.TextChoices):
        CHALLENGE_CREATED = "challenge_created", "Challenge Created"
        CHALLENGE_ACCEPTED = "challenge_accepted", "Challenge Accepted"
        CHALLENGE_REFUSED = "challenge_refused", "Challenge Refused"
        BATTLE_STARTED = "battle_started", "Battle Started"
        ENTRY_SUBMITTED = "entry_submitted", "Entry Submitted"
        VOTE_CAST = "vote_cast", "Vote Cast"
        BATTLE_COMPLETED = "battle_completed", "Battle Completed"
        RANK_PROMOTION = "rank_promotion", "Rank Promotion"

    battle = models.ForeignKey(Battle, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    challenge = models.ForeignKey(BattleChallenge, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_events_as_actor")
    target = models.ForeignKey(RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_events_as_target")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message


class BattleMoveTransaction(models.Model):
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_move_transactions")
    amount = models.IntegerField()
    reason = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.chef}: {self.amount} moves"


class Artifact(models.Model):
    class Rarity(models.TextChoices):
        COMMON = "common", "Common"
        RARE = "rare", "Rare"
        EPIC = "epic", "Epic"
        LEGENDARY = "legendary", "Legendary"

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    rarity = models.CharField(max_length=16, choices=Rarity.choices, default=Rarity.COMMON)
    effect_type = models.CharField(max_length=64, blank=True)
    effect_value = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ChefArtifact(models.Model):
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="chef_artifacts")
    artifact = models.ForeignKey(Artifact, on_delete=models.CASCADE, related_name="chef_artifacts")
    earned_at = models.DateTimeField(auto_now_add=True)
    equipped = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chef", "artifact"], name="unique_artifact_per_chef"),
        ]

    def __str__(self):
        return f"{self.chef} - {self.artifact}"


class CosmeticItem(models.Model):
    name = models.CharField(max_length=120, unique=True)
    item_type = models.CharField(max_length=64)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    rarity = models.CharField(max_length=16, choices=Artifact.Rarity.choices, default=Artifact.Rarity.COMMON)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ChefCosmetic(models.Model):
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="chef_cosmetics")
    item = models.ForeignKey(CosmeticItem, on_delete=models.CASCADE, related_name="chef_cosmetics")
    purchased_at = models.DateTimeField(auto_now_add=True)
    equipped = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chef", "item"], name="unique_cosmetic_per_chef"),
        ]


class Season(models.Model):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    name = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPCOMING)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.name


class SeasonStanding(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="standings")
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="season_standings")
    score = models.IntegerField(default=0)
    rank_position = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["rank_position", "-score"]
        constraints = [
            models.UniqueConstraint(fields=["season", "chef"], name="unique_season_standing_per_chef"),
        ]

    def __str__(self):
        return f"{self.season}: {self.chef}"
