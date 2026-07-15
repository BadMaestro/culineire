from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from articles.models import Article
from recipes.models import Recipe, RecipeAuthor


def vote_integrity_expires_at():
    return timezone.now() + timezone.timedelta(days=90)


class ChefBattleProfile(models.Model):
    class Rank(models.TextChoices):
        KITCHEN_PORTER = "kitchen_porter", "Kitchen Porter"
        PREP_COOK = "prep_cook", "Prep Chef"
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
    rating = models.IntegerField(default=0, db_index=True)
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
    is_executive = models.BooleanField(default=False, db_index=True, help_text="Executive role — excluded from chef rankings and battle participation")
    # Enrolment — set when author explicitly completes the "Join Chef Battles" onboarding
    enrolled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    chest_moves = models.PositiveIntegerField(default=0, help_text="Overflow moves stored in the chest when wallet is full.")
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
    payout_blocked = models.BooleanField(default=False, db_index=True, help_text="Payout blocked pending compliance review")
    reward_agreement_accepted = models.BooleanField(default=False, help_text="Chef has accepted the Chef Reward Agreement")
    stripe_connect_onboarded = models.BooleanField(default=False, db_index=True, help_text="Stripe Connect onboarding completed")
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
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
    def michelin_stars_display(self) -> str:
        return "★" * self.michelin_stars if self.michelin_stars else ""

class BattleChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REFUSED = "refused", "Refused"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    class BattleType(models.TextChoices):
        PHOTO = "photo", "Photo Battle"
        VIDEO = "video", "Video Battle"

    challenger = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="sent_battle_challenges")
    opponent = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="received_battle_challenges")
    theme = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    battle_type = models.CharField(max_length=16, choices=BattleType.choices, default=BattleType.PHOTO)
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
        PAUSED = "paused", "Paused (Emergency Stop)"
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
    battle_type = models.CharField(max_length=16, choices=BattleChallenge.BattleType.choices, default=BattleChallenge.BattleType.PHOTO)
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
    # E3 — readiness gate: both chefs press Ready before menu declaration
    challenger_ready = models.BooleanField(default=False)
    opponent_ready = models.BooleanField(default=False)
    proposed_combat_time = models.DateTimeField(null=True, blank=True)
    combat_time_confirmed = models.BooleanField(default=False)
    # Emergency Stop (DG-03): set when status -> PAUSED, cleared on resume.
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_reason = models.TextField(blank=True)
    paused_from_status = models.CharField(max_length=24, blank=True)
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
        NEEDS_CHANGES = "needs_changes", "Needs Changes"
        SUSPECTED_AI = "suspected_ai", "Suspected AI Image"
        SUSPECTED_STOCK = "suspected_stock", "Suspected Stock Photo"
        DUPLICATE = "duplicate", "Duplicate Image"

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
    real_photo_confirmed = models.BooleanField(default=False, help_text="Chef confirmed cooked photo is a real photograph (§32)")
    photo_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 of cooked_photo for duplicate detection")
    moderation_status = models.CharField(
        max_length=16,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
    )
    moderation_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_battle_entries",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    surviving_ingredients = models.JSONField(
        default=list, blank=True,
        help_text="Ingredient lines the chef may use in cooking (set by approve_cooking_phase).",
    )
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
        if self.recipe and self.article:
            raise ValidationError("A battle entry cannot link both a recipe and an article.")
        if self.recipe and self.recipe.author_id != self.author_id:
            raise ValidationError("The selected recipe must belong to the submitting author.")

        if self.battle_id and self.author_id and not self.battle.author_is_participant(self.author):
            raise ValidationError("Only battle participants can submit entries.")

    @property
    def content_object(self):
        return self.recipe


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


class VoteIntegrityEvent(models.Model):
    """Private evidence for a rejected vote attempt.

    These rows are deliberately separate from BattleVote: they never contribute
    to public totals or battle results. Request metadata is pseudonymised before
    it reaches this model.
    """

    battle = models.ForeignKey(
        Battle, on_delete=models.CASCADE, related_name="vote_integrity_events"
    )
    gate_code = models.CharField(max_length=40, db_index=True)
    failed_gates = models.JSONField(default=list, blank=True)
    is_authenticated = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)
    session_key_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(default=vote_integrity_expires_at, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["battle", "-created_at"], name="vote_int_battle_time_idx"),
        ]

    def __str__(self):
        return f"Battle {self.battle_id}: {self.gate_code}"


class BattleViewerPresence(models.Model):
    """Pseudonymised viewer heartbeat for real audience counts (DG-04).

    One row per device (sha256 of IP+UA, same pseudonymisation as vote
    dedup) per surface. battle=NULL means the arena lobby page. Rows are
    upserted by the existing public 20 s polls and opportunistically purged
    after an hour — no raw IP/UA, no account linkage, no history kept.
    A viewer counts as active if seen within the last 180 seconds.
    """

    battle = models.ForeignKey(
        Battle, null=True, blank=True, on_delete=models.CASCADE,
        related_name="viewer_presences",
    )
    viewer_hash = models.CharField(max_length=64, db_index=True)
    is_authenticated = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "viewer_hash"], name="unique_viewer_per_surface"
            ),
        ]
        indexes = [
            models.Index(fields=["battle", "last_seen_at"], name="viewer_battle_seen_idx"),
        ]

    def __str__(self):
        surface = f"battle {self.battle_id}" if self.battle_id else "arena lobby"
        return f"Viewer {self.viewer_hash[:8]} on {surface}"


class BattleEvent(models.Model):
    class EventType(models.TextChoices):
        CHALLENGE_CREATED = "challenge_created", "Challenge Created"
        CHALLENGE_ACCEPTED = "challenge_accepted", "Challenge Accepted"
        CHALLENGE_REFUSED = "challenge_refused", "Challenge Refused"
        CHALLENGE_EXPIRED = "challenge_expired", "Challenge Expired"
        BATTLE_STARTED = "battle_started", "Battle Started"
        MENU_LOCKED = "menu_locked", "Menu Locked (both ready)"
        ENTRY_SUBMITTED = "entry_submitted", "Entry Submitted"
        BATTLE_REVEALED = "battle_revealed", "Battle Revealed"
        VOTE_CAST = "vote_cast", "Vote Cast"
        BATTLE_FINISHED = "battle_finished", "Battle Finished"
        BATTLE_COMPLETED = "battle_completed", "Battle Completed"
        CHEF_DEFEATED = "chef_defeated", "Chef Defeated"
        CROWN_AWARDED = "crown_awarded", "Crown Awarded"
        RANK_PROMOTED = "rank_promoted", "Rank Promoted"
        ARTIFACT_DROPPED = "artifact_dropped", "Artifact Dropped"
        OPERATOR_ACTION = "operator_action", "Operator Action"

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
    class TxType(models.TextChoices):
        RECIPE_PUBLISHED = "recipe_published", "Recipe Publication"
        ARTICLE_PUBLISHED = "article_published", "Article Publication"
        PINCH_PUBLISHED = "pinch_published", "Pinch Publication"
        LIKE_RECEIVED = "like_received", "Verified Like Received"
        BATTLE_WON = "battle_won", "Victory Bonus"
        BATTLE_PARTICIPATION = "battle_participation", "Battle Participation"
        COMBAT_ACTION_SPENT = "combat_action_spent", "Spent on Tactical Turn"
        CHALLENGE_REFUSED = "challenge_refused", "Challenge Refusal Penalty"
        ENROL_BONUS = "enrol_bonus", "Enrolment Bonus"
        ADMIN_ADJUSTMENT = "admin_adjustment", "Admin Manual Fix"

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_move_transactions")
    amount = models.IntegerField()
    transaction_type = models.CharField(
        max_length=30,
        choices=TxType.choices,
        default=TxType.ADMIN_ADJUSTMENT,
    )
    reason = models.CharField(max_length=120, blank=True)
    reference_content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reference_object_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.chef}: {self.amount} moves ({self.transaction_type})"


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
    image = models.ImageField(upload_to="chef_battle/artifacts/", blank=True)

    def __str__(self):
        return self.name


class ChefArtifact(models.Model):
    class Source(models.TextChoices):
        PURCHASED = "purchased", "Purchased"
        GIFTED = "gifted", "Gifted"
        DROP = "drop", "Battle Drop"
        ADMIN_GRANT = "admin_grant", "Admin Grant"
        BATTLE_GIFT = "battle_gift", "Battle Gift (in-battle delivery)"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved (in active battle)"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"
        REVERSED = "reversed", "Reversed"

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="chef_artifacts")
    artifact = models.ForeignKey(Artifact, on_delete=models.CASCADE, related_name="chef_artifacts")
    earned_at = models.DateTimeField(auto_now_add=True)
    equipped = models.BooleanField(default=False)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.PURCHASED)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.AVAILABLE, db_index=True
    )
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_in_battle = models.ForeignKey(
        "Battle", null=True, blank=True, on_delete=models.SET_NULL, related_name="consumed_artifacts"
    )
    reserved_in_battle = models.ForeignKey(
        "Battle", null=True, blank=True, on_delete=models.SET_NULL, related_name="reserved_artifacts"
    )
    expired_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    # Admin grant audit
    admin_granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_granted_artifacts",
    )
    admin_grant_reason = models.TextField(blank=True)
    locked_to_battle = models.ForeignKey(
        "Battle", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="battle_gift_artifacts",
        help_text="Battle-gift artifact: must be used in this battle, expires unused when battle ends.",
    )

    class Meta:
        pass  # unique_artifact_per_chef removed: battle gifts allow duplicate entries

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
    delivery_fee = models.PositiveIntegerField(default=0, help_text="In-battle delivery fee (equals artifact cost).")
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

# Whether sending this gift creates a pending LSR RewardRecord for the recipient chef.
# Per spec: artifact cost must never create LSR; only the support component of a gift can.
# All appreciation gifts (non-artifact) are eligible.
APPRECIATION_GIFT_REWARD_ELIGIBLE = {
    AppreciationGiftType.COFFEE: True,
    AppreciationGiftType.VIRTUAL_BEER_TOAST: True,
    AppreciationGiftType.VIRTUAL_WHISKEY_TOAST: True,
    AppreciationGiftType.FLOWERS: True,
    AppreciationGiftType.CELEBRATION_COCKTAIL: True,
    AppreciationGiftType.VIRTUAL_CHAMPAGNE_BOTTLE: True,
}

# Pending LSR tokens awarded to the chef (recipient) per gift.
# 1 token spent = 1 pending LSR (internal reward record, not immediate credit).
APPRECIATION_GIFT_REWARD_BASIS = {
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
    is_flagged = models.BooleanField(default=False, db_index=True, help_text="Flagged for compliance review")

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
    artifact_used = models.ForeignKey(
        "ChefArtifact",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="combat_uses",
        help_text="Artifact activated this round (consumed after resolution).",
    )
    target_ingredient = models.ForeignKey(
        "BattleIngredient",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="targeted_by_actions",
        help_text="Opponent ingredient this attack targets (attack only; ignored on defend).",
    )
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


class BattleIngredient(models.Model):
    """One ingredient declared by a chef before combat begins.

    Both chefs must declare equal-sized lists (5–7 items each) with exactly
    2 marked is_key (their hidden combat locks). Once both lists are submitted
    the battle transitions to menu_locked -> active.
    """

    MIN_COUNT = 5
    MAX_COUNT = 7
    KEY_COUNT = 2  # exactly 2 per chef must be marked is_key

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="battle_ingredients")
    chef = models.ForeignKey(
        "recipes.RecipeAuthor", on_delete=models.CASCADE, related_name="battle_ingredients"
    )
    name = models.CharField(max_length=150)
    is_key = models.BooleanField(default=False, help_text="Hidden combat lock — protects this ingredient from elimination")
    is_eliminated = models.BooleanField(default=False, db_index=True)
    eliminated_at = models.DateTimeField(null=True, blank=True)
    eliminated_by = models.ForeignKey(
        "recipes.RecipeAuthor", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ingredients_eliminated"
    )
    position = models.PositiveSmallIntegerField(default=0, help_text="Display order within this chef's list")

    class Meta:
        ordering = ["battle", "chef", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "chef", "position"],
                name="unique_ingredient_position_per_chef",
            ),
        ]

    def __str__(self):
        status = "eliminated" if self.is_eliminated else ("key" if self.is_key else "active")
        return f"{self.name} [{status}] — {self.chef} (battle {self.battle_id})"


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

    @property
    def price_with_vat(self):
        from decimal import Decimal, ROUND_HALF_UP
        return (self.price_eur * Decimal("1.23")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    """Tracks a Stripe checkout session for a token purchase.

    EU compliance notes:
    - amount_net_cents + vat_amount_cents = amount_eur_cents (total charged).
    - Under EU/Irish digital content rules, the buyer must explicitly waive the
      14-day right of withdrawal before instant delivery. This waiver must be
      recorded server-side with the exact consent text shown at purchase time.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        DISPUTED = "disputed", "Under Dispute"

    wallet = models.ForeignKey(TokenWallet, on_delete=models.CASCADE, related_name="orders")
    package = models.ForeignKey(TokenPackage, on_delete=models.PROTECT, related_name="orders")
    tokens = models.PositiveIntegerField()
    amount_eur_cents = models.PositiveIntegerField(help_text="Total charged (net + VAT), in cents")
    amount_net_cents = models.PositiveIntegerField(default=0, help_text="Pre-VAT amount in cents")
    vat_amount_cents = models.PositiveIntegerField(default=0, help_text="VAT portion in cents")
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default="0.2300",
        help_text="VAT rate applied at time of purchase (e.g. 0.2300 for 23%)"
    )
    currency = models.CharField(max_length=3, default="eur", help_text="ISO 4217 currency code")
    # EU right-of-withdrawal consent (Digital Content Directive / Irish Consumer Rights Act 2022)
    right_of_withdrawal_waived = models.BooleanField(
        default=False,
        help_text="Buyer explicitly waived 14-day right of withdrawal before instant token delivery"
    )
    withdrawal_consent_at = models.DateTimeField(null=True, blank=True)
    consent_text_snapshot = models.TextField(
        blank=True,
        help_text="Exact consent text shown to the buyer at purchase time, frozen for audit"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, db_index=True, help_text="Stripe Customer ID")
    stripe_invoice_id = models.CharField(max_length=255, blank=True, help_text="Stripe Invoice ID if issued")
    credited_at = models.DateTimeField(null=True, blank=True, help_text="When tokens were credited to the wallet")
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
    """Discretionary CBR or LSR token grant issued to a chef or supporter.

    CBR/LSR are NOT money, NOT user funds, NOT e-money. They are discretionary
    platform rewards that may be converted to tokens at the platform's sole discretion.
    Never describe them as "earned funds", "withdrawable balance", or "cash balance".
    """

    class RewardType(models.TextChoices):
        CBR = "cbr", "Chef Battle Reward"
        LSR = "lsr", "Live Support Reward"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued for Review"
        APPROVED = "approved", "Approved"
        ISSUED = "issued", "Issued to Wallet"
        ACKNOWLEDGED = "acknowledged", "Acknowledged by Recipient"
        USED = "used", "Used"
        EXPIRED = "expired", "Expired"
        REVERSED = "reversed", "Reversed"
        DISPUTED = "disputed", "Under Dispute"
        VOIDED = "voided", "Voided"
        ARCHIVED = "archived", "Archived"

    recipient = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="reward_records"
    )
    reward_type = models.CharField(max_length=8, choices=RewardType.choices, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
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
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_reward_records",
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    status_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_reward_type_display()} → {self.recipient}: {self.tokens_granted}T ({self.status})"


class LedgerEvent(models.Model):
    """Immutable audit log for every significant arena event. Never update or delete rows.

    Hash chain integrity: each event records the SHA-256 hash of the previous event's
    hash (prev_hash) and then hashes its own canonical content into event_hash.
    Any direct DB tampering breaks the chain, making it detectable.
    Use LedgerEvent.verify_chain() to check integrity.
    """

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
        ADMIN_NOTE = "admin_note", "Admin Note"
        ARTIFACT_GRANTED = "artifact_granted", "Artifact Granted (Admin)"
        CHARGEBACK_LOCK = "chargeback_lock", "Chargeback Lock"
        CONTENT_REPORT = "content_report", "Content Report"

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
    # SHA-256 hash chain — prev_hash is "" for the first event ever
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    event_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"

    def _compute_hash(self) -> str:
        import hashlib
        import json
        canonical = json.dumps({
            "id": self.pk,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "related_battle_id": self.related_battle_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("LedgerEvent is immutable and cannot be updated.")
        # Compute prev_hash from most recent event before saving
        last = LedgerEvent.objects.order_by("-pk").first()
        self.prev_hash = last.event_hash if last else ""
        super().save(*args, **kwargs)
        # Compute event_hash after save (pk and created_at are now set)
        self.event_hash = self._compute_hash()
        LedgerEvent.objects.filter(pk=self.pk).update(event_hash=self.event_hash)

    def delete(self, *args, **kwargs):
        raise ValueError("LedgerEvent is immutable and cannot be deleted.")

    @classmethod
    def verify_chain(cls) -> tuple[bool, int | None]:
        """Verify the integrity of the entire hash chain.
        Returns (True, None) if intact, or (False, first_broken_pk) if tampered."""
        events = list(cls.objects.order_by("pk").values("pk", "event_hash", "prev_hash"))
        if not events:
            return True, None
        if events[0]["prev_hash"] != "":
            return False, events[0]["pk"]
        for i in range(1, len(events)):
            if events[i]["prev_hash"] != events[i - 1]["event_hash"]:
                return False, events[i]["pk"]
        return True, None


class BattleReport(models.Model):
    """Structured post-battle report from a console operator to GreenBear (DG-06).

    The one write available to non-owner console operators: watch the battle,
    summarise it, flag issues, recommend a payout decision. Final financial
    authority stays exclusively with the owner.
    """

    class Recommendation(models.TextChoices):
        APPROVE_PAYOUT = "approve_payout", "Approve payout"
        WITHHOLD = "withhold", "Withhold payout"
        NEEDS_REVIEW = "needs_review", "Needs deeper review"
        NO_ACTION = "no_action", "No action needed"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed by owner"

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="operator_reports")
    author = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_reports")
    summary = models.TextField()
    flags = models.JSONField(default=list, blank=True, help_text="List of short flag strings raised by the operator")
    recommendation = models.CharField(max_length=20, choices=Recommendation.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_battle_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report on battle #{self.battle_id} by {self.author} ({self.recommendation})"


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
        related_name="arena_content_reports",
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


class ChefRewardAgreement(models.Model):
    """Immutable record of a chef accepting the Chef Reward Agreement before becoming payout-eligible."""

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="reward_agreements")
    accepted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    agreement_version = models.CharField(max_length=20, default="1.0")
    consent_text_snapshot = models.TextField(help_text="Full agreement text shown to chef at acceptance, frozen for audit")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"RewardAgreement v{self.agreement_version} — {self.chef} @ {self.accepted_at:%Y-%m-%d}"


class DAC7Record(models.Model):
    """DAC7/MRDP seller data collected for annual revenue reporting obligations.

    EU Directive 2021/514 (DAC7) requires platforms to collect and report income
    earned by sellers (chefs) above the reporting threshold (EUR 2 000 / 30 transactions).
    Data is retained for 10 years per Irish Revenue requirements.
    """

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending Verification"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Verification Failed"

    chef = models.OneToOneField(RecipeAuthor, on_delete=models.PROTECT, related_name="dac7_record")
    legal_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    primary_address = models.TextField(blank=True)
    country_of_tax_residence = models.CharField(max_length=2, help_text="ISO 3166-1 alpha-2 country code")
    tax_identification_number = models.CharField(max_length=50, blank=True)
    business_name = models.CharField(max_length=200, blank=True)
    business_registration_number = models.CharField(max_length=100, blank=True)
    stripe_connect_account_id = models.CharField(max_length=100, blank=True, db_index=True)
    verification_status = models.CharField(
        max_length=12, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED, db_index=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"DAC7: {self.legal_name} ({self.chef})"


class PayoutRequest(models.Model):
    """A chef's request to convert approved reward tokens into a real-money payout via Stripe Connect.

    Lifecycle: PENDING → UNDER_REVIEW → APPROVED / REJECTED / ON_HOLD
    Approved requests trigger a Stripe Connect transfer; amounts are immutable after approval.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ON_HOLD = "on_hold", "On Hold — Compliance"
        PAID = "paid", "Paid Out"
        REVERSED = "reversed", "Reversed"

    PAYOUT_RATE_EUR_PER_TOKEN = "0.025"  # €0.025 per approved reward token

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.PROTECT, related_name="payout_requests")
    dac7_record = models.ForeignKey(
        DAC7Record, on_delete=models.PROTECT, related_name="payout_requests",
        null=True, blank=True,
    )
    reward_agreement = models.ForeignKey(
        ChefRewardAgreement, on_delete=models.PROTECT, related_name="payout_requests",
        null=True, blank=True,
    )
    amount_reward_tokens = models.PositiveIntegerField(help_text="Number of approved reward tokens being redeemed")
    payout_rate_snapshot = models.DecimalField(
        max_digits=8, decimal_places=5, default="0.02500",
        help_text="EUR per token at request time — locked and immutable after creation",
    )
    gross_payout_eur = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Gross payout before any deductions (tokens × rate)",
    )
    currency = models.CharField(max_length=3, default="eur")
    stripe_connect_account_id = models.CharField(max_length=100, blank=True, db_index=True)
    stripe_transfer_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_payout_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    compliance_flags = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"PayoutRequest #{self.pk}: {self.chef} — {self.amount_reward_tokens}T / €{self.gross_payout_eur} ({self.status})"


# ---------------------------------------------------------------------------
# Phase 10 — Live Video
# ---------------------------------------------------------------------------

PRE_LIVE_CHECKLIST_ITEMS = [
    "I confirm I am 18 years of age or older.",
    "I am an approved CulinEire Chef.",
    "No minors are present in the filming area or visible on camera.",
    "I am streaming from a cooking area only — no bedrooms, bathrooms, or private spaces.",
    "No personal documents, ID cards, bank cards, or passwords are visible on camera.",
    "I am not broadcasting any copyrighted music, video, or images.",
    "My kitchen area is safe, clean, and fire-safe.",
    "I understand that injuries are my own responsibility and CulinEire is not liable.",
    "I understand that this stream may be recorded and reviewed by CulinEire staff.",
    "I understand that CulinEire may end my stream at any time without notice.",
    "I will not make false health or medical claims during the stream.",
    "I will not consume alcohol to excess or use any illegal substances during the stream.",
    "I understand that this stream is subject to the CulinEire Chef Battles Rules.",
    "I accept that violations may result in stream termination and account suspension.",
]


class LiveStreamSession(models.Model):
    """Metadata record for a chef's live stream tied to a battle."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        ENDED = "ended", "Ended"
        TERMINATED = "terminated", "Terminated by Platform"
        FAILED = "failed", "Failed / Technical Error"

    class Provider(models.TextChoices):
        NONE = "", "Not configured"
        MUX = "mux", "Mux"
        AGORA = "agora", "Agora"
        LIVEKIT = "livekit", "LiveKit"
        OTHER = "other", "Other"

    battle = models.ForeignKey(
        Battle, on_delete=models.CASCADE, related_name="live_streams",
        null=True, blank=True,
    )
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="live_stream_sessions")
    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.NONE, blank=True)
    provider_stream_id = models.CharField(max_length=200, blank=True, db_index=True)
    provider_playback_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    checklist_confirmed = models.BooleanField(default=False)
    checklist_confirmed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    terminated_reason = models.CharField(max_length=300, blank=True)
    terminated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="terminated_streams",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Stream #{self.pk}: {self.chef} / battle #{self.battle_id} ({self.status})"


class LiveBroadcast(models.Model):
    """Full moderation record for a chef's live stream broadcast during a battle.

    Extends LiveStreamSession with moderation, reporting, and safety-delay metadata.
    """

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved for Publication"
        REJECTED = "rejected", "Rejected"
        UNDER_REVIEW = "under_review", "Under Review"

    session = models.OneToOneField(
        LiveStreamSession, on_delete=models.CASCADE, related_name="broadcast"
    )
    recording_reference = models.CharField(max_length=300, blank=True)
    moderation_status = models.CharField(
        max_length=16, choices=ModerationStatus.choices, default=ModerationStatus.PENDING, db_index=True
    )
    safety_delay_enabled = models.BooleanField(default=True, help_text="30-60s broadcast delay applied")
    stopped_by_staff = models.BooleanField(default=False)
    stop_reason = models.CharField(max_length=300, blank=True)
    report_count = models.PositiveIntegerField(default=0)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_broadcasts",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Broadcast #{self.pk} — {self.session.chef} ({self.moderation_status})"


class LiveBroadcastReport(models.Model):
    """Viewer report against a live broadcast."""

    class ReportCategory(models.TextChoices):
        CHILD_SAFETY = "child_safety", "Child Safety"
        PRIVACY_BREACH = "privacy_breach", "Privacy Breach"
        PROHIBITED_CONTENT = "prohibited_content", "Prohibited Content"
        ALCOHOL_DRUG = "alcohol_drug", "Alcohol / Drug Misuse"
        ILLEGAL_CONTENT = "illegal_content", "Illegal Content"
        COPYRIGHT = "copyright", "Copyright Breach"
        OTHER = "other", "Other"

    broadcast = models.ForeignKey(LiveBroadcast, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="live_broadcast_reports",
    )
    category = models.CharField(max_length=24, choices=ReportCategory.choices, db_index=True)
    description = models.CharField(max_length=500, blank=True)
    reported_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self):
        return f"Report #{self.pk}: {self.category} on broadcast #{self.broadcast_id}"


class LiveBattleAgreement(models.Model):
    """Immutable record of a chef accepting the Live Battle Agreement before their first live stream.

    This agreement covers: minors, safety, prohibited content, alcohol, brands,
    privacy, copyright, defamation, and platform termination rights.
    Stored once per agreement version; a new version requires a new acceptance.
    """

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="live_battle_agreements")
    accepted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    agreement_version = models.CharField(max_length=20, default="1.0")
    consent_text_snapshot = models.TextField(help_text="Full agreement text shown to chef, frozen for audit")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"LiveBattleAgreement v{self.agreement_version} — {self.chef} @ {self.accepted_at:%Y-%m-%d}"


class OperatorActionIdempotencyKey(models.Model):
    """Replay guard for Arena Master Console actions with no natural
    before/after state to check (e.g. broadcast has no target status a
    repeat click would already satisfy, unlike force_status/emergency_stop/
    resume/cancel, which are already idempotent via row-locked before-state
    checks). The unique constraint on correlation_id is enforced at INSERT
    time, so a genuine race (two simultaneous requests with the same key)
    can create at most one row — the loser raises IntegrityError and the
    caller treats that as a rejected duplicate, never a second side effect.
    """

    correlation_id = models.CharField(max_length=64, unique=True)
    action = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.action}:{self.correlation_id}"


# ── Culinary Factions (Phase 6) ──────────────────────────────────────────────
# Named thresholds (kept distinct on purpose — see cuisines_design.md 3.1):
FACTION_ACTIVE_CONTRIBUTION_MIN = 1   # >= this many contributions in a season to count in sqrt(active_member_count)
FACTION_RANK_MEMBER_FLOOR = 5         # >= this many active members for a faction to appear on the ranked board


class Faction(models.Model):
    """A curated identity a chef represents for a season (Cuisine or Specialty).

    Seeded/curated — never user-created — so no name-moderation machinery is
    needed. Both axes are rows of this one table (kind discriminator).
    """

    class Kind(models.TextChoices):
        CUISINE = "cuisine", "Cuisine"
        SPECIALTY = "specialty", "Specialty"

    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80)
    crest_icon = models.CharField(max_length=8, blank=True)  # emoji crest
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "slug"], name="unique_faction_slug_per_kind"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.name}"


class FactionMembership(models.Model):
    """A chef's faction pick for one season — one Cuisine + one Specialty each."""

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="faction_memberships")
    faction = models.ForeignKey(Faction, on_delete=models.CASCADE, related_name="memberships")
    faction_kind = models.CharField(max_length=16, choices=Faction.Kind.choices, db_index=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="faction_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["chef", "faction_kind", "season"],
                name="unique_membership_per_kind_per_season",
            ),
        ]

    def __str__(self):
        return f"{self.chef} -> {self.faction} ({self.season})"


class FactionContribution(models.Model):
    """Append-only, immutable points ledger (mirrors BattleMoveTransaction).

    Standings are a SUM over this ledger — never a mutated counter. faction /
    faction_kind are denormalised at write time so points belong to the faction
    as of the earning moment and survive a later switch.
    """

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="faction_contributions")
    faction = models.ForeignKey(Faction, on_delete=models.CASCADE, related_name="contributions")
    faction_kind = models.CharField(max_length=16, choices=Faction.Kind.choices)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="faction_contributions")
    source_content_type = models.ForeignKey(
        "contenttypes.ContentType", null=True, blank=True, on_delete=models.SET_NULL
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["season", "faction"]),
            models.Index(fields=["chef", "season"]),
        ]

    def __str__(self):
        return f"{self.chef} +{self.points} -> {self.faction} ({self.season})"


class FactionSeasonStanding(models.Model):
    """Per-faction, per-season board. Written ONLY by the season receivers
    (season_started opens the row, season_ended finalises rank_position)."""

    faction = models.ForeignKey(Faction, on_delete=models.CASCADE, related_name="standings")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="faction_standings")
    total_points = models.IntegerField(default=0)
    active_member_count = models.IntegerField(default=0)
    normalized_score = models.FloatField(default=0.0)
    rank_position = models.PositiveIntegerField(null=True, blank=True)
    rewards_pending = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank_position", "-normalized_score"]
        constraints = [
            models.UniqueConstraint(fields=["faction", "season"], name="unique_standing_per_faction_per_season"),
        ]

    def __str__(self):
        return f"{self.faction} @ {self.season}: {self.normalized_score:.2f}"


class SeasonReward(models.Model):
    """Thin audit bridge for season-end rewards — NO monetary fields.

    Individual leg -> RewardRecord (CBR). Collective/placement leg -> ChefCosmetic
    (non-cash). Keeps the anti-gambling/DAC7 posture (rules sec 15-18).
    """

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="faction_season_rewards")
    faction = models.ForeignKey(Faction, on_delete=models.CASCADE, related_name="season_rewards")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="faction_rewards")
    points_snapshot = models.IntegerField(default=0)
    placement = models.PositiveIntegerField(null=True, blank=True)
    reward_record = models.ForeignKey(
        "RewardRecord", null=True, blank=True, on_delete=models.SET_NULL, related_name="faction_season_rewards"
    )
    cosmetic = models.ForeignKey(
        "ChefCosmetic", null=True, blank=True, on_delete=models.SET_NULL, related_name="faction_season_rewards"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SeasonReward {self.chef} / {self.faction} / {self.season}"


# ── Clans & Alliances (Phase 6) ──────────────────────────────────────────────
# A clan is the real *team* unit (distinct from a Faction, which is a category).
# See docs/chef_battle/clans_alliances_rules.md (canonical) + clans_design.md.
CLAN_MIN_CATEGORIES = 1               # a clan must declare at least one category
CLAN_MAX_CATEGORIES = 3               # ...and at most three (validated in the service, not the DB)
CLAN_ACTIVE_CONTRIBUTION_MIN = 1      # >= this many contributions in a season to count as an active member
CLAN_RANK_MEMBER_FLOOR = 3           # >= this many active members for a clan to appear on the ranked board


class Clan(models.Model):
    """A named team of chefs. The name is the team (e.g. Fusion, Cyber Chef);
    the categories it selects (up to 3 Faction rows, cuisines+specialties mixed)
    are where it competes. Founder-created, so it carries moderation state."""

    class Moderation(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    founder = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="founded_clans")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)
    crest_icon = models.CharField(max_length=8, blank=True)  # emoji crest
    categories = models.ManyToManyField(Faction, related_name="clans", blank=True)
    moderation_status = models.CharField(
        max_length=16, choices=Moderation.choices, default=Moderation.PENDING, db_index=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClanMembership(models.Model):
    """A chef's membership in a clan. request -> approve flow (status). A chef
    may hold at most ONE active membership at a time (partial unique below)."""

    class Role(models.TextChoices):
        FOUNDER = "founder", "Founder"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"

    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name="memberships")
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="clan_memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # One active clan per chef: only current (left_at IS NULL), active rows are exclusive.
            models.UniqueConstraint(
                fields=["chef"],
                condition=models.Q(left_at__isnull=True, status="active"),
                name="unique_active_clan_per_chef",
            ),
        ]

    def __str__(self):
        return f"{self.chef} -> {self.clan} ({self.status})"


class Alliance(models.Model):
    """A grouping of clans that stand together (Season 1 foundation; the full
    cuisine-vs-cuisine assist mechanic expands in later seasons)."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AllianceMembership(models.Model):
    """A clan's membership in an alliance. A clan may be in at most ONE active
    alliance at a time (partial unique below)."""

    alliance = models.ForeignKey(Alliance, on_delete=models.CASCADE, related_name="memberships")
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name="alliance_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clan"],
                condition=models.Q(left_at__isnull=True),
                name="unique_active_alliance_per_clan",
            ),
        ]

    def __str__(self):
        return f"{self.clan} in {self.alliance}"


class ClanContribution(models.Model):
    """Append-only, immutable points ledger for clans (mirrors
    FactionContribution). clan is denormalised at write time so points belong to
    the clan as of the earning moment and survive the chef later leaving —
    the owner's rule that points stay with the clan falls out for free."""

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="clan_contributions")
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name="contributions")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="clan_contributions")
    source_content_type = models.ForeignKey(
        "contenttypes.ContentType", null=True, blank=True, on_delete=models.SET_NULL
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["clan", "season"]),
            models.Index(fields=["chef", "season"]),
        ]

    def __str__(self):
        return f"{self.chef} -> {self.clan} +{self.points} ({self.season})"


class ClanSeasonStanding(models.Model):
    """Per-clan, per-season board. Written only by the season receivers
    (season_ended finalises total/active/rank from the ClanContribution ledger)."""

    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name="season_standings")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="clan_standings")
    total_points = models.IntegerField(default=0)
    active_member_count = models.IntegerField(default=0)
    rank_position = models.PositiveIntegerField(null=True, blank=True)
    rewards_pending = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank_position", "-total_points"]
        constraints = [
            models.UniqueConstraint(fields=["clan", "season"], name="unique_clan_standing_per_season"),
        ]

    def __str__(self):
        return f"{self.clan} @ {self.season}: {self.total_points}"


# ── Season Champion Reward: Arena Observers (Phase 6) ─────────────────────────
# Non-cash prize: the winning clan's champion seats up to 2 clan members as
# Arena Observers for the FOLLOWING season. Advisory voice in disputes only.
# Canonical rules: docs/chef_battle/clans_alliances_rules.md sec 3.
OBSERVER_SEATS_PER_SEASON = 2


class SeasonArenaObserver(models.Model):
    """One Arena Observer seat, granted by the winning clan's champion.

    The role's active window is derived from `won_season`: an observer is active
    only while the CURRENT active season is the one immediately following
    `won_season`, so the seat auto-expires once the season after it begins. No
    stored expiry flag to drift — see observer_service.is_active_arena_observer.
    """

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="arena_observer_roles")
    nominated_by = models.ForeignKey(
        RecipeAuthor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="arena_observer_nominations",
    )
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name="arena_observers")
    won_season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="arena_observers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["chef", "won_season"], name="unique_observer_per_chef_per_won_season"
            ),
        ]

    def __str__(self):
        return f"Observer {self.chef} (won {self.won_season})"


class ObserverDisputeVote(models.Model):
    """An Arena Observer's ADVISORY vote on a battle dispute (BattleReport).

    Recorded and shown to the operator, but non-binding — final authority stays
    with the owner/operator (rules sec 3). One vote per observer per report,
    updatable."""

    observer = models.ForeignKey(
        SeasonArenaObserver, on_delete=models.CASCADE, related_name="dispute_votes"
    )
    battle_report = models.ForeignKey(
        BattleReport, on_delete=models.CASCADE, related_name="observer_votes"
    )
    recommendation = models.CharField(max_length=32, choices=BattleReport.Recommendation.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["observer", "battle_report"], name="unique_observer_vote_per_report"
            ),
        ]

    def __str__(self):
        return f"{self.observer.chef} -> {self.recommendation} on report {self.battle_report_id}"


# ── Live Arena build tracker (owner-visible progress matrix) ──────────────────
class LiveArenaStage(models.Model):
    """One stage of the Live Arena implementation, tracked on two axes
    (backend presence + frontend presence) so the owner can watch progress in
    the master console. Statuses are updated live from the console (no deploy),
    each agent writing only its own column. See docs live-arena audit."""

    class Status(models.TextChoices):
        ABSENT = "absent", "Absent"
        PARTIAL = "partial", "Partial"
        PRESENT = "present", "Present"

    class Group(models.TextChoices):
        FOUNDATION = "foundation", "Foundation"
        FRAME = "frame", "Frame"
        LIVE = "live", "Live modules"
        CROSSCUTTING = "crosscutting", "Cross-cutting"

    order = models.PositiveIntegerField(default=0, db_index=True)
    key = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=160)
    phase_group = models.CharField(max_length=16, choices=Group.choices)
    backend_status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABSENT)
    frontend_status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABSENT)
    backend_notes = models.TextField(blank=True)
    frontend_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order:02d} {self.title}"


class BattleReaction(models.Model):
    """One 'heart' reaction tap on a battle stream side. Append-only; the
    per-side count is a COUNT over rows (mirrors the like/reaction counter in
    the live arena). Anti-farm is enforced in the endpoint, not the schema."""

    class Side(models.TextChoices):
        LEFT = "left", "Left (challenger)"
        RIGHT = "right", "Right (opponent)"

    battle = models.ForeignKey("Battle", on_delete=models.CASCADE, related_name="reactions")
    side = models.CharField(max_length=8, choices=Side.choices, db_index=True)
    author = models.ForeignKey(
        RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL, related_name="battle_reactions"
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["battle", "side"]),
            models.Index(fields=["battle", "created_at"]),
        ]

    def __str__(self):
        return f"heart {self.side} on battle {self.battle_id}"
