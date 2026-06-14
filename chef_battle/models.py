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

    class PrestigeTitle(models.TextChoices):
        NONE = "", "None"
        KITCHEN_PORTER = "kitchen_porter", "Kitchen Porter"
        COMMIS_CHEF = "commis_chef", "Commis Chef"
        CHEF_DE_PARTIE = "chef_de_partie", "Chef de Partie"
        SOUS_CHEF = "sous_chef", "Sous Chef"
        HEAD_CHEF = "head_chef", "Head Chef"
        EXECUTIVE_CHEF = "executive_chef", "Executive Chef"

    # reserved titles that are manually granted and must not be overwritten by auto-logic
    RESERVED_TITLES = {"executive_chef"}

    # wins threshold for each prestige title
    PRESTIGE_THRESHOLDS = [
        (15, PrestigeTitle.HEAD_CHEF),
        (10, PrestigeTitle.SOUS_CHEF),
        (6, PrestigeTitle.CHEF_DE_PARTIE),
        (3, PrestigeTitle.COMMIS_CHEF),
        (1, PrestigeTitle.KITCHEN_PORTER),
    ]

    WINS_PER_LEVEL = 3
    HERO_WINS_THRESHOLD = 15
    MAX_LEVEL = 5

    author = models.OneToOneField(
        RecipeAuthor,
        on_delete=models.CASCADE,
        related_name="battle_profile",
    )
    rank = models.CharField(max_length=32, choices=Rank.choices, default=Rank.KITCHEN_PORTER)
    level = models.PositiveSmallIntegerField(default=1, db_index=True)
    is_hero = models.BooleanField(default=False, db_index=True)
    michelin_stars = models.PositiveSmallIntegerField(default=0)
    infinite_moves = models.BooleanField(default=False)
    rating = models.IntegerField(default=1000, db_index=True)
    reputation = models.IntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    refused_battles = models.PositiveIntegerField(default=0)
    ignored_battles = models.PositiveIntegerField(default=0)
    win_streak = models.PositiveIntegerField(default=0)
    best_win_streak = models.PositiveIntegerField(default=0)
    crown_until = models.DateTimeField(null=True, blank=True)
    crown_count = models.PositiveIntegerField(default=0)
    battle_moves = models.PositiveIntegerField(default=0)
    seasonal_score = models.IntegerField(default=0)
    prestige_title = models.CharField(
        max_length=16, choices=PrestigeTitle.choices, default=PrestigeTitle.NONE, blank=True
    )
    is_founding_chef = models.BooleanField(default=False, db_index=True)
    # 18+ compliance
    age_verified = models.BooleanField(default=False)
    age_confirmed_at = models.DateTimeField(null=True, blank=True)
    # fraud / compliance flags
    is_suspended = models.BooleanField(default=False, db_index=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.CharField(max_length=200, blank=True)
    fraud_flag = models.BooleanField(default=False, db_index=True)
    fraud_flag_note = models.CharField(max_length=200, blank=True)
    dsa_reported_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "-wins", "author__name"]

    def __str__(self):
        return f"{self.author} - {self.get_rank_display()}"

    @property
    def has_crown(self) -> bool:
        return bool(self.crown_until and self.crown_until > timezone.now())

    @property
    def display_level(self) -> str:
        if self.is_hero:
            return "CulinEire Hero"
        return f"Level {self.level}"

    @property
    def michelin_stars_display(self) -> str:
        return "★" * self.michelin_stars if self.michelin_stars else ""

    def recalculate_level(self) -> bool:
        """Recompute level and is_hero from wins. Returns True if anything changed."""
        if self.wins >= self.HERO_WINS_THRESHOLD:
            new_level = self.MAX_LEVEL
            new_hero = True
        else:
            new_level = min(self.MAX_LEVEL, (self.wins // self.WINS_PER_LEVEL) + 1)
            new_hero = False
        changed = (self.level != new_level) or (self.is_hero != new_hero)
        self.level = new_level
        self.is_hero = new_hero
        return changed

    def recalculate_prestige_title(self) -> bool:
        """Assign highest earned prestige title based on wins. Returns True if changed.
        Reserved titles (e.g. Incognito) are never overwritten by auto-logic."""
        if self.prestige_title in self.RESERVED_TITLES:
            return False
        new_title = self.PrestigeTitle.NONE
        for threshold, title in self.PRESTIGE_THRESHOLDS:
            if self.wins >= threshold:
                new_title = title
                break
        changed = self.prestige_title != new_title
        self.prestige_title = new_title
        return changed


class BattleChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REFUSED = "refused", "Refused"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

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
    cancelled_at = models.DateTimeField(null=True, blank=True)

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
        MENU_LOCKED = "menu_locked", "Menu Locked"
        ACTIVE = "active", "Active (Combat)"
        AWAITING_SUBMISSIONS = "awaiting_submissions", "Awaiting Submissions"
        REVEALED = "revealed", "Revealed"
        COOKING = "cooking", "Cooking"
        PRESENTATION = "presentation", "Presentation"
        VOTING = "voting", "Voting"
        COMPLETED = "completed", "Completed"
        INGREDIENT_PENALTY = "ingredient_penalty", "Ingredient Penalty"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"

    # Statuses that count as "in progress" for homepage panel and selectors
    ACTIVE_STATUSES = frozenset([
        Status.SCHEDULED,
        Status.MENU_LOCKED,
        Status.ACTIVE,
        Status.AWAITING_SUBMISSIONS,
        Status.COOKING,
        Status.PRESENTATION,
        Status.VOTING,
    ])

    challenge = models.OneToOneField(BattleChallenge, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle")
    challenger = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battles_as_challenger")
    opponent = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battles_as_opponent")
    theme = models.CharField(max_length=180)
    battle_type = models.CharField(max_length=16, choices=BattleChallenge.BattleType.choices, default=BattleChallenge.BattleType.RECIPE)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    submission_deadline = models.DateTimeField()
    reveal_time = models.DateTimeField(null=True, blank=True)
    voting_deadline = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(db_index=True)
    winner = models.ForeignKey(RecipeAuthor, on_delete=models.SET_NULL, null=True, blank=True, related_name="won_battles")
    loser = models.ForeignKey(RecipeAuthor, on_delete=models.SET_NULL, null=True, blank=True, related_name="lost_battles")
    result_reason = models.CharField(max_length=120, blank=True)
    rating_delta_challenger = models.IntegerField(default=0)
    rating_delta_opponent = models.IntegerField(default=0)
    crown_awarded = models.BooleanField(default=False)
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
    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FLAGGED = "flagged", "Flagged"

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="entries")
    author = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_entries")
    recipe = models.ForeignKey(Recipe, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle_entries")
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle_entries")
    battle_statement = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_revealed = models.BooleanField(default=False)
    is_late = models.BooleanField(default=False)
    cooked_photo = models.ImageField(upload_to="chef_battle/cooked/", null=True, blank=True)
    cooked_photo_submitted_at = models.DateTimeField(null=True, blank=True)
    moderation_status = models.CharField(
        max_length=16,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    session_key_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_suspicious = models.BooleanField(default=False)
    moderation_note = models.TextField(blank=True)

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
        CHALLENGE_EXPIRED = "challenge_expired", "Challenge Expired"
        BATTLE_STARTED = "battle_started", "Battle Started"
        ENTRY_SUBMITTED = "entry_submitted", "Entry Submitted"
        BATTLE_REVEALED = "battle_revealed", "Battle Revealed"
        VOTE_CAST = "vote_cast", "Vote Cast"
        BATTLE_FINISHED = "battle_finished", "Battle Finished"
        BATTLE_COMPLETED = "battle_completed", "Battle Completed"
        CHEF_DEFEATED = "chef_defeated", "Chef Defeated"
        CROWN_AWARDED = "crown_awarded", "Crown Awarded"
        RANK_PROMOTED = "rank_promoted", "Rank Promoted"
        ARTIFACT_DROPPED = "artifact_dropped", "Artifact Dropped"

    battle = models.ForeignKey(Battle, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    challenge = models.ForeignKey(BattleChallenge, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_events_as_actor")
    target = models.ForeignKey(RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_events_as_target")
    message = models.TextField()
    payload_json = models.JSONField(null=True, blank=True)
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
        UNCOMMON = "uncommon", "Uncommon"
        RARE = "rare", "Rare"
        EPIC = "epic", "Epic"
        LEGENDARY = "legendary", "Legendary"

    RARITY_TOKEN_COST = {
        Rarity.COMMON: 10,
        Rarity.UNCOMMON: 25,
        Rarity.RARE: 60,
        Rarity.EPIC: 150,
        Rarity.LEGENDARY: 400,
    }

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    rarity = models.CharField(max_length=16, choices=Rarity.choices, default=Rarity.COMMON)
    token_cost = models.PositiveIntegerField(default=10)
    effect_type = models.CharField(max_length=64, blank=True)
    effect_value = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ChefArtifact(models.Model):
    class Source(models.TextChoices):
        PURCHASED = "purchased", "Purchased"
        GIFTED = "gifted", "Gifted"
        DROP = "drop", "Battle Drop"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONSUMED = "consumed", "Consumed"

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="chef_artifacts")
    artifact = models.ForeignKey(Artifact, on_delete=models.CASCADE, related_name="chef_artifacts")
    earned_at = models.DateTimeField(auto_now_add=True)
    equipped = models.BooleanField(default=False)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.PURCHASED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_in_battle = models.ForeignKey(
        "Battle", null=True, blank=True, on_delete=models.SET_NULL, related_name="consumed_artifacts"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chef", "artifact"], name="unique_artifact_per_chef"),
        ]

    def __str__(self):
        return f"{self.chef} - {self.artifact}"


class ViewerBattleGift(models.Model):
    """A viewer sends a battle artifact to a chef during an active battle."""

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="viewer_gifts")
    recipient = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="received_battle_gifts")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_battle_gifts"
    )
    artifact = models.ForeignKey(Artifact, on_delete=models.CASCADE, related_name="battle_gifts")
    tokens_spent = models.PositiveIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_applied = models.BooleanField(default=False)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.artifact} → {self.recipient} (battle {self.battle_id})"


class AppreciationGiftType(models.TextChoices):
    COFFEE = "coffee", "Coffee"
    VIRTUAL_BEER_TOAST = "virtual_beer_toast", "Virtual Beer Toast"
    VIRTUAL_WHISKEY_TOAST = "virtual_whiskey_toast", "Virtual Whiskey Toast"
    FLOWERS = "flowers", "Flowers"
    CELEBRATION_COCKTAIL = "celebration_cocktail", "Celebration Cocktail"
    VIRTUAL_CHAMPAGNE_BOTTLE = "virtual_champagne_bottle", "Virtual Champagne Bottle"


APPRECIATION_GIFT_EMOJI = {
    AppreciationGiftType.COFFEE: "☕",
    AppreciationGiftType.VIRTUAL_BEER_TOAST: "🍺",
    AppreciationGiftType.VIRTUAL_WHISKEY_TOAST: "🥃",
    AppreciationGiftType.FLOWERS: "🌷",
    AppreciationGiftType.CELEBRATION_COCKTAIL: "🍸",
    AppreciationGiftType.VIRTUAL_CHAMPAGNE_BOTTLE: "🍾",
}

APPRECIATION_GIFT_COST = {
    AppreciationGiftType.COFFEE: 20,
    AppreciationGiftType.VIRTUAL_BEER_TOAST: 30,
    AppreciationGiftType.VIRTUAL_WHISKEY_TOAST: 50,
    AppreciationGiftType.FLOWERS: 80,
    AppreciationGiftType.CELEBRATION_COCKTAIL: 80,
    AppreciationGiftType.VIRTUAL_CHAMPAGNE_BOTTLE: 100,
}


class AppreciationGift(models.Model):
    """A viewer sends a non-combat digital appreciation gift to a chef. All gifts are digital items only."""

    recipient = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="appreciation_gifts")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_appreciation_gifts"
    )
    gift_type = models.CharField(max_length=32, choices=AppreciationGiftType.choices)
    tokens_spent = models.PositiveIntegerField()
    message = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.gift_type} → {self.recipient}"


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


class BattleCombatAction(models.Model):
    """A chef's declared combat action for one round (hidden until both are locked)."""

    class ActionType(models.TextChoices):
        ATTACK = "attack", "Attack"
        DEFEND = "defend", "Defend"

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="combat_actions")
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="combat_actions")
    round_number = models.PositiveSmallIntegerField()
    action_type = models.CharField(max_length=8, choices=ActionType.choices)
    moves_invested = models.PositiveSmallIntegerField(default=1)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["round_number", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "chef", "round_number"],
                name="unique_combat_action_per_chef_per_round",
            ),
        ]

    def __str__(self):
        return f"{self.chef} R{self.round_number}: {self.action_type} ({self.moves_invested} moves)"


class BattleRound(models.Model):
    """Resolved outcome of one combat round."""

    class Outcome(models.TextChoices):
        FULL_HIT = "full_hit", "Full Hit"
        PARTIAL_HIT = "partial_hit", "Partial Hit"
        BLOCKED = "blocked", "Blocked"
        DRAW = "draw", "Draw"

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="combat_rounds")
    round_number = models.PositiveSmallIntegerField()
    attacker = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="attack_rounds"
    )
    defender = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="defence_rounds"
    )
    attack_power = models.PositiveSmallIntegerField()
    defence_power = models.PositiveSmallIntegerField()
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    # Running totals after this round
    challenger_hits = models.PositiveSmallIntegerField(default=0)
    opponent_hits = models.PositiveSmallIntegerField(default=0)
    log_message = models.CharField(max_length=300, blank=True)
    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["round_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "round_number"],
                name="unique_round_per_battle",
            ),
        ]

    def __str__(self):
        return f"Battle {self.battle_id} R{self.round_number}: {self.outcome}"


class IngredientLock(models.Model):
    """Loser's hidden lock on one ingredient line (placed at submission, revealed after biathlon)."""

    MAX_LOCKS = 2

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="ingredient_locks")
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="ingredient_locks")
    ingredient_index = models.PositiveSmallIntegerField(help_text="Zero-based line index in recipe.ingredients")
    is_revealed = models.BooleanField(default=False)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["placed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "chef", "ingredient_index"],
                name="unique_lock_per_ingredient",
            ),
        ]

    def __str__(self):
        return f"Lock by {self.chef} on ingredient #{self.ingredient_index} (battle {self.battle_id})"


class IngredientShot(models.Model):
    """Winner's shot at one of the loser's ingredient lines."""

    MAX_SHOTS = 3

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="ingredient_shots")
    shooter = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="ingredient_shots")
    target_index = models.PositiveSmallIntegerField(help_text="Zero-based line index in loser's recipe.ingredients")
    bounced = models.BooleanField(default=False, help_text="True if the shot hit a lock and bounced")
    fired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fired_at"]

    def __str__(self):
        result = "bounced" if self.bounced else "hit"
        return f"Shot by {self.shooter} at #{self.target_index} ({result}, battle {self.battle_id})"


class BattleChatMessage(models.Model):
    """Live viewer chat message on a battle page."""

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="chat_messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_chat_messages"
    )
    display_name = models.CharField(max_length=60)
    body = models.CharField(max_length=300)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.display_name}: {self.body[:60]}"


class TokenPackage(models.Model):
    """Purchasable token bundle shown in the shop.

    Populated and kept in sync from chef_battle.token_config.TOKEN_PACKAGES
    via data migration. Do not add packages manually — update token_config.py
    and run a new data migration.
    """

    key = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=60, unique=True)
    tokens = models.PositiveIntegerField()
    price_eur = models.DecimalField(max_digits=8, decimal_places=2, help_text="Final (discounted) price in EUR")
    discount_percent = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "tokens"]

    def __str__(self):
        return f"{self.name} ({self.tokens}T / €{self.price_eur})"

    @property
    def standard_price_cents(self) -> int:
        """Standard price before discount, in cents (100T = €10.00)."""
        return self.tokens * 10

    @property
    def final_price_cents(self) -> int:
        """Final price in cents, as stored in price_eur."""
        return int(self.price_eur * 100)

    @property
    def standard_price_eur(self):
        from decimal import Decimal
        return Decimal(self.standard_price_cents) / Decimal(100)


class TokenWallet(models.Model):
    """One wallet per chef — tracks current token balance."""

    chef = models.OneToOneField(RecipeAuthor, on_delete=models.CASCADE, related_name="token_wallet")
    balance = models.PositiveIntegerField(default=0)
    infinite_balance = models.BooleanField(default=False)
    total_purchased = models.PositiveIntegerField(default=0)
    total_spent = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.chef}: {'∞' if self.infinite_balance else self.balance}T"


class TokenTransaction(models.Model):
    """Immutable ledger entry for every token movement."""

    class TxType(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        GIFT_SENT = "gift_sent", "Gift Sent"
        GIFT_RECEIVED = "gift_received", "Gift Received"
        ARTIFACT_BOUGHT = "artifact_bought", "Artifact Bought"
        REFUND = "refund", "Refund"
        ADMIN_GRANT = "admin_grant", "Admin Grant"
        ADMIN_DEDUCT = "admin_deduct", "Admin Deduct"

    wallet = models.ForeignKey(TokenWallet, on_delete=models.CASCADE, related_name="transactions")
    tx_type = models.CharField(max_length=20, choices=TxType.choices, db_index=True)
    amount = models.IntegerField(help_text="Positive = credit, negative = debit")
    balance_after = models.PositiveIntegerField()
    description = models.CharField(max_length=200, blank=True)
    related_battle = models.ForeignKey(
        Battle, null=True, blank=True, on_delete=models.SET_NULL, related_name="token_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.wallet.chef}: {sign}{self.amount}T ({self.tx_type})"


class TokenOrder(models.Model):
    """Tracks a Stripe checkout session for a token purchase."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    wallet = models.ForeignKey(TokenWallet, on_delete=models.CASCADE, related_name="orders")
    package = models.ForeignKey(TokenPackage, on_delete=models.PROTECT, related_name="orders")
    tokens = models.PositiveIntegerField()
    amount_eur_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.wallet.chef} — {self.tokens}T ({self.status})"


class ProcessedTokenStripeEvent(models.Model):
    """Idempotency guard — prevents double-processing Stripe webhook events."""

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} / {self.event_id}"


class RewardRecord(models.Model):
    """Discretionary CBR or LSR token grant issued to a chef or supporter."""

    class RewardType(models.TextChoices):
        CBR = "cbr", "Chef Battle Reward"
        LSR = "lsr", "Live Support Reward"

    recipient = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="reward_records"
    )
    reward_type = models.CharField(max_length=8, choices=RewardType.choices, db_index=True)
    tokens_granted = models.PositiveIntegerField()
    reason = models.CharField(max_length=200)
    related_battle = models.ForeignKey(
        Battle, null=True, blank=True, on_delete=models.SET_NULL, related_name="reward_records"
    )
    related_gift = models.ForeignKey(
        AppreciationGift, null=True, blank=True, on_delete=models.SET_NULL, related_name="reward_records"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="granted_reward_records",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_reward_type_display()} → {self.recipient}: {self.tokens_granted}T"


class LedgerEvent(models.Model):
    """Immutable audit log for every significant arena event. Never update or delete rows."""

    class EventType(models.TextChoices):
        TOKEN_PURCHASE = "token_purchase", "Token Purchase"
        GIFT_SENT = "gift_sent", "Gift Sent"
        GIFT_RECEIVED = "gift_received", "Gift Received"
        BATTLE_GIFT_SENT = "battle_gift_sent", "Battle Gift Sent"
        ARTIFACT_PURCHASED = "artifact_purchased", "Artifact Purchased"
        ARTIFACT_DROPPED = "artifact_dropped", "Artifact Dropped"
        ARTIFACT_CONSUMED = "artifact_consumed", "Artifact Consumed"
        CBR_GRANTED = "cbr_granted", "CBR Granted"
        LSR_GRANTED = "lsr_granted", "LSR Granted"
        REFUND_ISSUED = "refund_issued", "Refund Issued"
        CHALLENGE_CREATED = "challenge_created", "Challenge Created"
        CHALLENGE_ACCEPTED = "challenge_accepted", "Challenge Accepted"
        CHALLENGE_REFUSED = "challenge_refused", "Challenge Refused"
        BATTLE_STARTED = "battle_started", "Battle Started"
        BATTLE_COMPLETED = "battle_completed", "Battle Completed"
        VOTE_CAST = "vote_cast", "Vote Cast"
        RANK_PROMOTED = "rank_promoted", "Rank Promoted"
        LEVEL_UP = "level_up", "Level Up"
        FRAUD_FLAG = "fraud_flag", "Fraud Flag"
        ACCOUNT_SUSPENDED = "account_suspended", "Account Suspended"

    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(
        RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ledger_events_as_actor",
    )
    target = models.ForeignKey(
        RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ledger_events_as_target",
    )
    related_battle = models.ForeignKey(
        Battle, null=True, blank=True, on_delete=models.SET_NULL, related_name="ledger_events"
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("LedgerEvent is immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("LedgerEvent is immutable and cannot be deleted.")


class ContentReport(models.Model):
    """DSA content report submitted by a user against arena content."""

    class ContentKind(models.TextChoices):
        BATTLE_CHAT = "battle_chat", "Battle Chat Message"
        BATTLE_ENTRY = "battle_entry", "Battle Entry"
        CHEF_PROFILE = "chef_profile", "Chef Profile"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        REVIEWED = "reviewed", "Reviewed"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="content_reports",
    )
    content_kind = models.CharField(max_length=20, choices=ContentKind.choices, db_index=True)
    object_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=300)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_content_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderator_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report #{self.pk}: {self.content_kind} #{self.object_id} ({self.status})"
