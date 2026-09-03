from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from articles.models import Article
from recipes.models import Recipe, RecipeAuthor


def vote_integrity_expires_at():
    return timezone.now() + timezone.timedelta(days=90)


# Which recipe currently produces request fingerprints (see
# services.hash_request_value). "v1" was a bare SHA-256 of the value, which is
# not anonymisation: the whole IPv4 space rehashes in seconds, so an ip_hash
# could be walked back to the address it came from. "v2" is HMAC keyed on
# SECRET_KEY, which cannot. Old rows keep their v1 label rather than being
# rewritten — the input is gone, so they cannot be recomputed — and the fraud
# gates only ever compare hashes carrying the same label.
HASH_SCHEME_LEGACY = "v1"
HASH_SCHEME_CURRENT = "v2"


class ChefBattleProfile(models.Model):
    class Rank(models.TextChoices):
        KITCHEN_PORTER = "kitchen_porter", "Kitchen Porter"
        # X20, Owner 2026-08-11: tz_main.md section 10 names this rung
        # "Prep Cook" and the label said "Prep Chef". The stored value was the
        # document's all along; only what a chef reads was wrong.
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

    author = models.OneToOneField(
        RecipeAuthor,
        on_delete=models.CASCADE,
        related_name="battle_profile",
    )
    # WHO MAY MESSAGE ME PRIVATELY. The options are the ones this site already
    # has - the hall, and the clan/alliance a chef already belongs to - rather
    # than a new tier of user invented for a preference. Enforced on the SERVER
    # in open_direct_conversation(); hiding the button would only hide it.
    class DirectMessagePolicy(models.TextChoices):
        ANYONE = "anyone", "Anyone in the hall"
        TEAM = "team", "My clan and alliance only"
        NOBODY = "nobody", "Nobody"

    dm_policy = models.CharField(
        max_length=8,
        choices=DirectMessagePolicy.choices,
        default=DirectMessagePolicy.ANYONE,
        help_text="Who may start a private conversation with this chef.",
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
    # Owner's rule, 2026-08-05: a chef may pull out of an ACCEPTED battle for a
    # genuine force majeure. Three per account, for the life of the account, and
    # when they are gone the button goes dark.
    withdrawals_remaining = models.PositiveSmallIntegerField(
        default=3,
        help_text="Force-majeure withdrawals left. Fixed allowance of 3 per account.",
    )
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

    class TaskKind(models.TextChoices):
        """T19, Owner 2026-08-15: a challenge says what is being fought over.

        Either the challenger contests one of the CHALLENGED chef's existing
        recipes - a check on that recipe - or he proposes a completely new
        one. This is not theme_recipe, which is the CHALLENGER's own dish and
        becomes his entry; the two were being read as the same field.
        """

        NEW_RECIPE = "new_recipe", "A completely new recipe"
        CONTEST_RECIPE = "contest_recipe", "Contesting a recipe of the chef being challenged"

    challenger = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="sent_battle_challenges")
    opponent = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="received_battle_challenges")
    theme_recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="themed_battle_challenges",
        help_text=(
            "The challenger's own recipe for this battle. On accept it becomes the "
            "challenger's battle entry, so it must be one of their approved recipes. "
            "It is never reused as the opponent's entry: the opponent brings their own."
        ),
    )
    task_kind = models.CharField(
        max_length=20,
        choices=TaskKind.choices,
        default=TaskKind.NEW_RECIPE,
        help_text=(
            "T19: what this challenge is fought over. Existing challenges predate "
            "the field and read as a new recipe, which is what they were."
        ),
    )
    contested_recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contested_battle_challenges",
        help_text=(
            "The CHALLENGED chef's own recipe being contested. Set only when "
            "task_kind is CONTEST_RECIPE, and it must belong to the opponent."
        ),
    )
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
        # Start ritual: the readiness timer expired with only one chef ready,
        # so the arena waits out a short grace period for the other to appear.
        WAITING = "waiting", "Waiting for the second chef"
        # The grace period expired: the chef who turned up takes the win, the
        # absent one forfeits. No cooking happened.
        WALKOVER = "walkover", "Walkover (opponent never appeared)"
        # Neither chef turned up: no winner, both are penalised.
        VOID = "void", "Void (neither chef appeared)"

    # Statuses that count as "in progress" for homepage panel and selectors
    def save(self, *args, **kwargs):
        """Stamp the season on a new battle, once, and never rewrite it.

        G12, Owner 2026-08-11. The alternative was to set it at every call site
        that creates a Battle - accept_challenge, the emulation runway, whatever
        comes next - and the seventh one always forgets. Stamped here on INSERT
        only: an existing row keeps whatever season it was fought in even if the
        calendar is edited later, which is the whole reason the field exists
        rather than deriving the season from a date window every time.
        """
        if self._state.adding and self.season_id is None:
            try:
                from .season_service import get_active_season
                active = get_active_season()
            except Exception:               # pragma: no cover - defensive
                active = None
            if active is not None:
                self.season = active
        return super().save(*args, **kwargs)

    ACTIVE_STATUSES = frozenset([
        Status.SCHEDULED,
        # A battle waiting out the grace period for its second chef is still
        # live in the arena — the floor should show it, not drop it.
        Status.WAITING,
        Status.MENU_LOCKED,
        Status.ACTIVE,
        Status.AWAITING_SUBMISSIONS,
        Status.COOKING,
        Status.PRESENTATION,
        Status.VOTING,
    ])

    challenge = models.OneToOneField(BattleChallenge, on_delete=models.SET_NULL, null=True, blank=True, related_name="battle")
    #: G12, Owner 2026-08-11. tz_main.md section 17.3 lists `season` on Battle
    #: and it was never added: standings were derived from the season's date
    #: window alone, which works until a season needs re-running, a battle needs
    #: reassigning, or a battle straddles a boundary. Stamped once at creation
    #: from the active season and never rewritten, so the record of which season
    #: a fight belonged to cannot drift when the calendar is edited afterwards.
    #: NULL for every battle fought before this field existed, and for any
    #: battle created while no season is active - both are honest states and
    #: neither is backfilled by guesswork.
    season = models.ForeignKey(
        "Season", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="battles", db_index=True,
    )
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
    # Start ritual: when only one chef was ready at start_time the battle sits
    # in WAITING until this moment, giving the other chef a last chance.
    waiting_until = models.DateTimeField(null=True, blank=True, db_index=True)
    # T11, Owner 2026-08-15: the Stage 1 winner has FIFTEEN MINUTES to fire his
    # three shots. Set when _resolve_round moves the battle into
    # INGREDIENT_PENALTY; swept by sweep_ingredient_penalty_deadlines(), which
    # advances the battle to COOKING whether or not the shots were fired, so a
    # winner who walks away cannot hold his opponent's battle open forever.
    ingredient_penalty_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
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
    dish_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the chef submitted the finished battle dish; recipe attachment alone is not a dish submission.",
    )
    is_revealed = models.BooleanField(default=False)
    is_late = models.BooleanField(default=False)
    class CookingFormat(models.TextChoices):
        PHOTOS = "photos", "Photo Series"
        WEBCAM = "webcam", "Live / Recorded Webcam"

    #: G3, Owner 2026-08-11 («этого ещё и вправду нет — будем строить»).
    #: chef_levels.md sets the winner's artifact tier from how the dish was
    #: cooked - a photo series draws from the basic pool, a live cook from the
    #: premium one - and named this exact field. It did not exist, so the rule
    #: could not run and every battle drew from one table.
    #:
    #: The chef has been ANSWERING this question all along: BattleEntryForm has
    #: carried a photo/video radio since it was written, declared on the form
    #: and absent from the model, so the answer was collected and thrown away
    #: at every submission. It is stored now.
    cooking_format = models.CharField(
        max_length=16, choices=CookingFormat.choices, default=CookingFormat.PHOTOS,
        help_text="How this chef cooked the dish. Sets the artifact tier on a win.",
    )
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
    # Voting is registered-members-only: an anonymous visitor is a passer-by and
    # cannot vote (owner decision 2026-07-17). A vote is always tied to a real
    # account, so the FK is required and a deleted account takes its votes with it.
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="battle_votes")
    voted_for = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="battle_votes_received")
    # The voter's own author row, denormalised from RecipeAuthor.user at write
    # time. It exists for one reason: a database CheckConstraint cannot join, so
    # "voter is not voted_for" is unexpressible while the two sides live in
    # different tables (voter is a User, voted_for a RecipeAuthor). Comparing
    # those two ids directly would be worse than no constraint at all — it would
    # miss every real self-vote and reject an honest one whenever a user id
    # happened to equal an author id. Nullable because rows written before this
    # field existed cannot be filled in, and because a voter need not have an
    # author profile at all; the constraint therefore only bites when it is set.
    voter_author = models.ForeignKey(
        RecipeAuthor,
        on_delete=models.CASCADE,
        related_name="battle_votes_cast",
        null=True,
        blank=True,
    )
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)
    session_key_hash = models.CharField(max_length=64, blank=True)
    # Which recipe produced the three hashes above. Values from different schemes
    # are not comparable, so the fraud gates must filter on this before matching
    # one fingerprint against another. See services.hash_request_value.
    hash_scheme = models.CharField(max_length=8, default=HASH_SCHEME_CURRENT, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_suspicious = models.BooleanField(default=False)
    moderation_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["battle", "voter"],
                name="one_authenticated_vote_per_battle",
            ),
            models.CheckConstraint(
                condition=~models.Q(voter_author=models.F("voted_for")),
                name="chef_cannot_vote_for_themselves",
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
    hash_scheme = models.CharField(max_length=8, default=HASH_SCHEME_CURRENT, db_index=True)
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


class ArenaSeat(models.Model):
    """One real viewer holding one real seat in the arena stands (Stage 3C).

    BattleViewerPresence above answers "how many people are watching" from a
    pseudonymised device hash and deliberately keeps no account linkage. That
    is the right shape for a counter and the wrong shape for a seat: a seat
    belongs to a named person, has to stay theirs across polls, and cannot be
    held twice. So this is a second question about the same audience, not a
    second presence system — the count still comes from BattleViewerPresence.

    Only an authenticated viewer's own author record can occupy a row here.
    There is no path that writes a synthetic occupant: the service takes an
    author, and the atmospheric crowd the renderer draws over empty seats is
    never persisted.

    Seats are addressed by the authoritative arena geometry — ``ring_index``
    is the ring's index in ``selectors.get_arena_geometry()`` and ``seat_index``
    is the cell within it — so this table cannot drift into its own private
    topology.

    Release is explicit (``released_at``). A held seat additionally lapses when
    its occupant falls outside the arena's existing online window
    (``ARENA_ONLINE_THRESHOLD_SECONDS``, the same window that already decides
    who is present in the hall); no new expiry clock is introduced here.
    """

    viewer = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="arena_seats",
    )
    ring_index = models.PositiveSmallIntegerField()
    seat_index = models.PositiveSmallIntegerField()
    claimed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    released_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [
            # The two integrity rules of a hall, enforced by the database so a
            # caller that skips the service still cannot break them: one held
            # seat per viewer, and one holder per seat. Both are partial —
            # released rows are history and may repeat freely.
            models.UniqueConstraint(
                fields=["viewer"], condition=Q(released_at__isnull=True),
                name="unique_active_arena_seat_per_viewer",
            ),
            models.UniqueConstraint(
                fields=["ring_index", "seat_index"], condition=Q(released_at__isnull=True),
                name="unique_active_occupant_per_arena_seat",
            ),
        ]
        indexes = [
            models.Index(fields=["released_at", "ring_index", "seat_index"],
                         name="arena_seat_free_lookup_idx"),
        ]

    def __str__(self):
        state = "released" if self.released_at else "held"
        return f"Seat r{self.ring_index}c{self.seat_index} ({state})"


class ArenaChatMessage(models.Model):
    """One line spoken from one seat in the arena stands.

    This is the hall talking, which is a different thing from
    ``BattleChatMessage``: that one is the battle page's chat and every viewer
    reads every line of it. Here a line carries the seat it was spoken from,
    because who hears it depends on where the listener is sitting. The renderer
    shows the words to neighbours and a "Talking Something" label to everyone
    else; the reach itself is decided server-side in ``arena_chat`` so a client
    never receives text it was not meant to read.

    The seat is copied onto the row rather than followed through ``ArenaSeat``
    on purpose. A speaker may stand up, leave, or be reseated, and the line
    still has to be judged from where it was actually said.

    Nothing here expires. The Owner's rule (2026-08-17) is that the chat keeps
    everything written from the start of a battle to its end, so there is no
    TTL, no sweep and no purge on this model.
    """

    battle = models.ForeignKey(
        Battle, null=True, blank=True, on_delete=models.CASCADE,
        related_name="arena_chat_messages",
    )
    speaker = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="arena_chat_messages",
    )
    display_name = models.CharField(max_length=60)
    body = models.CharField(max_length=300)
    ring_index = models.PositiveSmallIntegerField()
    seat_index = models.PositiveSmallIntegerField()
    is_hidden = models.BooleanField(default=False)
    # ONE level, never a tree. This is a live spectator chat, not a forum: a
    # reply quotes the line it answers and stops there, so the log stays
    # readable while a battle is running. SET_NULL rather than CASCADE because
    # a moderator hiding the parent must not silently delete the answers to it.
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="replies",
    )
    # NULL is the hall. See ChatConversation for why the public room has no row
    # of its own rather than one invented for symmetry.
    conversation = models.ForeignKey(
        "ChatConversation", null=True, blank=True, on_delete=models.CASCADE,
        related_name="messages", db_index=True,
    )

    # AN ATTACHMENT, ON THE MESSAGE ROW RATHER THAN IN A TABLE OF ITS OWN.
    #
    # A separate table is the tidier model and the wrong one here: the hall
    # polls this table every four seconds, and a join for a column that is
    # null on most rows costs every one of those polls to serve the few
    # messages that carry a picture. Five nullable columns cost Postgres
    # almost nothing per row and cost the poll nothing at all.
    #
    # media_kind is what the renderer branches on; it is "" for the ordinary
    # case, so an old row and a text-only row read the same. FileField and not
    # ImageField deliberately - ImageField's own validation would re-open the
    # file to find its dimensions, and by the time anything is stored here
    # normalise_uploaded_chat_media() has already decoded it, re-encoded every
    # frame and measured the result.
    # AN EVENT CARD IS A ROW IN THIS TABLE, NOT A SECOND FEED. P3, Owner
    # 2026-08-26. The hall polls one table with one id space, and `since` is
    # that id; a parallel table of battle events would have needed a second
    # cursor, a merge, and an answer to what happens when the two disagree
    # about order. A card is a line in the log that renders differently.
    #
    # THE CARD DOES NOT CARRY ITS OWN COPY OF THE BATTLE. It points at the
    # BattleEvent that caused it and reads its facts from there, so a card can
    # never say something the battle did not do - the brief's rule that every
    # card renders from real state or does not render. `body` is the same
    # sentence the event already wrote, kept on the row so the log stays
    # readable with no join and so a deleted event leaves a line rather than a
    # blank.
    class Kind(models.TextChoices):
        MESSAGE = "", "Spoken line"
        CHALLENGE_ISSUED = "challenge_issued", "Challenge issued"
        VOTING_OPEN = "voting_open", "Voting opened"
        BATTLE_RESULT = "battle_result", "Battle result"
        INGREDIENT_ATTACK = "ingredient_attack", "Ingredient struck off"
        DEFENCE = "defence", "Shot blocked"
        CHEF_ENTERED = "chef_entered", "Chef entered the Arena"
        # ROUND ONE IS FOUGHT WITH ARTIFACTS, round two with three shots at a
        # menu, and the two are not the same event however alike the words for
        # them read. These two are round ONE: an attack that landed and an
        # attack that a defence turned away.
        ARTIFACT_ATTACK = "artifact_attack", "Artifact attack landed"
        ARTIFACT_DEFENCE = "artifact_defence", "Artifact defence held"
        # P2 item 16. A question the STANDS asked, never the battle's own
        # vote - see ArenaChatPoll for why that separation is structural.
        POLL = "poll", "Poll"

    kind = models.CharField(
        max_length=24, choices=Kind.choices, blank=True, default="",
    )
    event = models.ForeignKey(
        "BattleEvent", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_chat_cards",
    )
    # A ROUND-ONE CARD POINTS AT THE ROUND, NOT AT AN EVENT, because combat
    # rounds do not write BattleEvent rows and do not need to start: BattleRound
    # already records the attacker, the defender, both powers, the outcome and
    # the log line, and the two BattleCombatAction rows beside it carry the
    # artifacts and the targeted ingredient. The card reads those. Nothing new
    # is written into the battle to make the hall able to talk about it.
    combat_round = models.ForeignKey(
        "BattleRound", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_chat_cards",
    )

    class MediaKind(models.TextChoices):
        NONE = "", "No attachment"
        IMAGE = "image", "Picture"
        ANIMATION = "animation", "Animation"

    media = models.FileField(
        upload_to="chef_battle/chat/%Y/%m/", blank=True,
        help_text="Stored re-encoded; never the bytes that were uploaded.",
    )
    # An animation's first frame, stored as its own still file so a reader who
    # has turned animation off is sent no animated bytes at all.
    media_poster = models.FileField(
        upload_to="chef_battle/chat/%Y/%m/", blank=True,
    )
    media_kind = models.CharField(
        max_length=9, choices=MediaKind.choices, blank=True, default="",
    )
    # The STORED file's size, so the client can reserve the box before the
    # bytes arrive and the log does not jump under a reader mid-sentence.
    media_width = models.PositiveSmallIntegerField(null=True, blank=True)
    media_height = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["battle", "id"], name="arena_chat_since_idx"),
        ]
        # CHAT MODERATION IS ITS OWN AUTHORITY, NOT A SIDE EFFECT OF is_staff.
        # The Owner's spec is explicit that a staff flag must not silently
        # confer the power to hide other people's words, and this project had
        # no permission framework at all before this - is_moderator() is
        # "staff or superuser or bearseeker", which is exactly the conflation
        # being ruled out. These are checked with has_perm() and granted by the
        # Owner himself in the admin; no code here assigns them to anybody
        # (AGENTS.md section 20).
        permissions = [
            ("moderate_arena_chat", "Can hide and restore arena chat messages"),
            ("timeout_arena_chat_user", "Can temporarily silence a chef in arena chat"),
            ("resolve_arena_chat_report", "Can resolve arena chat reports"),
        ]

    def __str__(self):
        return f"r{self.ring_index}c{self.seat_index} {self.display_name}: {self.body[:40]}"


class ChatModerationAction(models.Model):
    """An append-only record of what a moderator did, and to whom.

    NOTHING HERE IS EVER DELETED, and hiding a message does not remove the
    message either - is_hidden is a flag, so the action is reversible and the
    evidence survives the reversal. A moderation log that can be edited by the
    people it describes is not a log.
    """

    class Action(models.TextChoices):
        HIDE = "hide", "Hide message"
        RESTORE = "restore", "Restore message"
        TIMEOUT = "timeout", "Timeout user"

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_chat_moderation_actions",
    )
    action = models.CharField(max_length=16, choices=Action.choices, db_index=True)
    target_message = models.ForeignKey(
        ArenaChatMessage, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="moderation_actions",
    )
    target_author = models.ForeignKey(
        RecipeAuthor, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_chat_moderation_received",
    )
    reason = models.CharField(max_length=200, blank=True)
    # Seconds, for a timeout. Zero for the actions that are not one.
    duration_seconds = models.PositiveIntegerField(default=0)
    # What the message's is_hidden was BEFORE this action, so the log answers
    # "what changed" and not merely "what was attempted".
    previous_state = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_author", "created_at"])]

    def __str__(self):
        return f"{self.moderator} {self.action} {self.target_message_id or self.target_author_id}"


class ArenaChatTimeout(models.Model):
    """A chef silenced in arena chat until a moment in time.

    Distinct from OwnerAccountRestriction.muted_until, which is the OWNER's
    sitewide instrument and reaches beyond this chat. This one is the chat
    moderator's, it expires by itself, and it is enforced where a line is
    written rather than where it is drawn.
    """

    author = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="arena_chat_timeouts",
    )
    until = models.DateTimeField(db_index=True)
    reason = models.CharField(max_length=200, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_chat_timeouts_issued",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} until {self.until:%Y-%m-%d %H:%M}"


class ArenaChatReaction(models.Model):
    """One tap of one emoji on one line, by one person.

    A row, not a counter: the count is a COUNT, so two taps cannot race into a
    wrong total and "did I already react" is answerable without a second table.
    The unique constraint makes the tap idempotent - tapping again removes it,
    which is the whole toggle.

    Deliberately NOT reusing BattleReaction: that one records a heart for a SIDE
    of a battle and has no message at all. Same word, different thing.
    """

    class Emoji(models.TextChoices):
        FIRE = "fire", "Fire"
        CLAP = "clap", "Clap"
        STAR = "star", "Star"
        # Added 2026-08-25 for the reaction picker upgrade - additive only,
        # existing FIRE/CLAP/STAR rows are untouched by this migration. The
        # arena_chat_react view (views.py) validates against Emoji.values
        # dynamically, so this enum extension is the entire backend change.
        SMILE = "smile", "Smile"
        LAUGH = "laugh", "Laugh"
        HEART = "heart", "Heart"
        WOW = "wow", "Wow"

    message = models.ForeignKey(
        ArenaChatMessage, on_delete=models.CASCADE, related_name="reactions",
    )
    author = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="arena_chat_reactions",
    )
    emoji = models.CharField(max_length=8, choices=Emoji.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "author", "emoji"],
                name="one_reaction_per_person_per_emoji",
            ),
        ]
        indexes = [models.Index(fields=["message", "emoji"])]

    def __str__(self):
        return f"{self.author} {self.emoji} #{self.message_id}"


class ArenaChatPoll(models.Model):
    """A question somebody in the stands asked the room. P2 item 16.

    THIS IS NOT THE BATTLE'S VOTE AND MUST NEVER BE MISTAKEN FOR IT. The
    Owner's brief is explicit, and the separation is structural rather than a
    label on a card: nothing here touches BattleVote, no scorer reads this
    table, and a tally in it cannot reach a result because no code path leads
    from here to one. The renderer says so in words as well, but the words are
    the second line of defence, not the first.

    A POLL IS A CHAT ROW, the same way P3's cards are - one log, one cursor,
    one poll loop (see arena_cards for the reasoning that already settled
    this). The row carries kind=POLL and the question as its body, so a client
    that has never heard of polls still shows the question as a spoken line
    rather than an empty bubble.

    CLOSING IS A TIME, NOT A FLAG somebody has to remember to set. `closes_at`
    is written once when the poll is made and `is_open` is derived from the
    clock, so a poll cannot be left open forever because a job did not run.
    """

    # The row that renders it. CASCADE because a poll without its message has
    # nowhere to appear - it is not a record anybody keeps for its own sake.
    message = models.OneToOneField(
        ArenaChatMessage, on_delete=models.CASCADE, related_name="poll",
    )
    question = models.CharField(max_length=140)
    created_at = models.DateTimeField(auto_now_add=True)
    closes_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["closes_at"])]

    def __str__(self):
        return self.question

    @property
    def is_open(self):
        return timezone.now() < self.closes_at


class ArenaChatPollOption(models.Model):
    """One of the answers offered. Two to five of them, decided at creation."""

    poll = models.ForeignKey(
        ArenaChatPoll, on_delete=models.CASCADE, related_name="options",
    )
    label = models.CharField(max_length=60)
    # Explicit, because the order the asker typed them in is part of the
    # question and "whatever the database returns" is not an order.
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.label


class ArenaChatPollVote(models.Model):
    """One person's answer, and they may change it while the poll is open.

    The poll is stored alongside the option rather than reached through it, so
    "one answer per person per poll" can be a database constraint instead of a
    rule the view has to remember. Changing an answer is an UPDATE of this row,
    which is why the constraint is on (poll, voter) and not on the option.
    """

    poll = models.ForeignKey(
        ArenaChatPoll, on_delete=models.CASCADE, related_name="votes",
    )
    option = models.ForeignKey(
        ArenaChatPollOption, on_delete=models.CASCADE, related_name="votes",
    )
    voter = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="arena_chat_poll_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "voter"], name="one_poll_answer_per_person",
            ),
        ]
        indexes = [models.Index(fields=["option"])]

    def __str__(self):
        return f"{self.voter} -> {self.option_id}"


class ChatMute(models.Model):
    """A PERSONAL preference: whose lines this one reader would rather not see.

    Not moderation. Nobody else's view changes, the muted person is never told,
    and their lines keep reaching everyone else exactly as before. The global,
    Owner-applied kind lives in OwnerAccountRestriction and is a different
    thing with different consequences - the two must not be confused, which is
    why this one does not share its table or its name.
    """

    owner = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="chat_mutes",
    )
    muted = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="chat_muted_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "muted"], name="one_mute_per_pair"),
            # Muting yourself is not a preference, it is a bug report.
            models.CheckConstraint(
                check=~models.Q(owner=models.F("muted")), name="no_self_mute",
            ),
        ]

    def __str__(self):
        return f"{self.owner} mutes {self.muted}"


class ChatConversation(models.Model):
    """A room. The hall is one; every private thread is another.

    ONE ENGINE, TWO KINDS. The alternative - a separate model, endpoint and
    renderer for direct messages - is the "second chat application" the Owner's
    spec rules out, and it is also how the two drift: a fix to the hall's
    escaping or reach that never reaches the DM copy. So a message belongs to a
    conversation, the conversation says what KIND of room it is, and only the
    rules that genuinely differ - who may read, and whether seat reach applies -
    branch on that.

    The hall keeps `conversation = NULL` rather than being handed a row. Every
    line ever written is already NULL, and inventing a hall row would mean a
    data migration that could half-succeed for no gain.
    """

    class Kind(models.TextChoices):
        DIRECT = "direct", "Direct"

    kind = models.CharField(
        max_length=12, choices=Kind.choices, default=Kind.DIRECT, db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} #{self.pk}"


class ChatParticipant(models.Model):
    """Who is in a conversation. Membership IS the read permission.

    Every read and every write checks this table. An id in a URL proves
    nothing: without a row here the conversation does not exist as far as the
    caller is concerned, which is what stops one person walking the id space
    into somebody else's private thread.
    """

    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name="participants",
    )
    author = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="chat_conversations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "author"], name="one_seat_per_conversation",
            ),
        ]
        indexes = [models.Index(fields=["author", "conversation"])]

    def __str__(self):
        return f"{self.author} in {self.conversation}"


class ChatBlock(models.Model):
    """Stronger than a mute, and enforced on the SERVER.

    A block stops the blocked person reaching the blocker privately at all -
    that check runs before a direct message is created, never in the browser -
    and hides their public lines from the blocker's own view. It does NOT
    remove them from the hall for anybody else: blocking is a personal wall,
    not a ban, and only the Owner bans.
    """

    owner = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="chat_blocks",
    )
    blocked = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="chat_blocked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "blocked"], name="one_block_per_pair"),
            models.CheckConstraint(
                check=~models.Q(owner=models.F("blocked")), name="no_self_block",
            ),
        ]

    def __str__(self):
        return f"{self.owner} blocks {self.blocked}"


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
        # THE BIATHLON GETS ITS OWN TWO TYPES, and the reason is a defect
        # rather than a feature: every shot fired since the biathlon shipped
        # was recorded as BATTLE_STARTED, because _post_biathlon_event had no
        # type of its own to use. A shot is not a battle starting, and an event
        # stream that says it is cannot be filtered, counted or read. Checked
        # before changing it: nothing anywhere filters BattleEvent by
        # BATTLE_STARTED, so no consumer loses a row it was relying on.
        #
        # HIT and BLOCKED, not one type with a flag: they are the two halves of
        # the biathlon the Owner's rules describe - the winner's three shots
        # against the loser's two blocks - and P3 draws them as an attack card
        # and a defence card, which is a decision the type should carry rather
        # than a payload key the renderer has to dig for.
        INGREDIENT_HIT = "ingredient_hit", "Ingredient Struck Off"
        INGREDIENT_BLOCKED = "ingredient_blocked", "Ingredient Shot Blocked"
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
    #: G9, Owner 2026-08-11. tz_main.md section 17.7 asks for balance_after on
    #: this ledger and it was never added, so the MOVES ledger could not be
    #: reconciled the way the TOKEN ledger can - TokenTransaction has carried
    #: balance_after since it was written, and nothing could prove a chef's move
    #: balance was the sum of its own history. NULL on every row written before
    #: this field existed: a number invented for those rows would be a
    #: reconciliation that reconciles nothing, and a gap that says "unknown" is
    #: worth more than a plausible fiction.
    balance_after = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Move balance immediately after this entry. NULL for rows written before 2026-08-11.",
    )
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

    #: The field default, kept as a name so save() can tell "nobody set a price"
    #: from "somebody chose ten".
    DEFAULT_TOKEN_COST = 10

    def save(self, *args, **kwargs):
        """Price a new artifact from its rarity when nobody priced it.

        RARITY_TOKEN_COST is the rulebook's price list — token_economy.md and
        audience_gifts.md both publish it — and until 2026-08-11 it was
        referenced by NOTHING. The charge came from this per-row field, whose
        default is ten, so an Epic added through the admin without a price cost
        a viewer 10 tokens instead of 150, and nothing anywhere would have said
        so. The live data happened to be correct and was held there by nobody;
        the audit of 2026-08-10 found it (X14) and the Owner ordered it closed.

        Deliberately narrow, because a price is his lever and not this method's:
        it only fills in a price on CREATE, only when the field was left at its
        default, and only when the rarity's published price is something else.
        An explicit price of any value, and every existing row, are untouched.
        """
        if self._state.adding and self.token_cost == self.DEFAULT_TOKEN_COST:
            published = self.RARITY_TOKEN_COST.get(self.rarity)
            if published and published != self.DEFAULT_TOKEN_COST:
                self.token_cost = published
        return super().save(*args, **kwargs)

    @property
    def effect_label(self):
        """Human-readable combat effect for every artifact card."""
        effect_type = (self.effect_type or "").strip().lower()
        labels = {
            "attack": "Attack",
            "defence": "Defence",
            "defense": "Defence",
        }
        label = labels.get(effect_type, effect_type.replace("_", " ").title() or "Effect")
        return f"{label} +{self.effect_value} Move"

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
    token_transaction = models.OneToOneField(
        "TokenTransaction", null=True, blank=True, on_delete=models.PROTECT,
        related_name="viewer_battle_gift",
    )

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
    token_transaction = models.OneToOneField(
        "TokenTransaction", null=True, blank=True, on_delete=models.PROTECT,
        related_name="appreciation_gift",
    )

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


class StickerPack(models.Model):
    """A set of Arena chat stickers sold together at one flat price.

    AC-STK, Owner 2026-08-27: the thirteen stickers that shipped free in
    v2.5.1372 become goods - 10 tokens each, 100 for the pack.

    THE PACK'S MEMBERSHIP IS FROZEN once anybody has bought it, and that is his
    ruling rather than a technical limit: "в этом пакете больше не будет других
    стикеров, но будут другие паки". A fourteenth sticker goes into a NEW pack.
    Adding one here after the first sale would silently enlarge what every past
    buyer paid 100 for, and there is no price at which that is fair to the next
    buyer. StickerItem.clean() refuses it.
    """

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    #: The whole-pack price, FLAT. A buyer who already owns some of it still
    #: pays this and receives only the ones they are missing - the Owner's
    #: words, "либо сразу все либо каждый по 10". The shop says so before
    #: payment; buy_sticker_pack() does not invent a discount.
    token_cost = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class StickerItem(models.Model):
    """One sticker, sold on its own or as part of a pack.

    `token` IS THE KEY, and it is the same string in three places: the body of
    a chat message (`:let_him_cook:`), the JSON map in
    templates/chef_battle/_arena_chat_stickers.html, and the WebP filename
    stem. Nothing joins them but this string, which is why the validator below
    is not decoration - see its own comment.
    """

    #: The pattern is BODY_TOKEN's own, from static/js/arena_chat.js: the
    #: renderer matches `:([a-z0-9_]{2,32}):` and nothing else. A hyphenated
    #: token already broke this feature once (v2.5.1302 - stickers among words
    #: silently stayed literal text), and a token the database accepts but the
    #: renderer cannot match is a sticker that is SOLD and cannot be SENT.
    token = models.CharField(
        max_length=32,
        unique=True,
        validators=[RegexValidator(
            regex=r"^[a-z0-9_]{2,32}$",
            message="A sticker token is 2-32 characters of a-z, 0-9 and underscore.",
        )],
    )
    label = models.CharField(max_length=60)
    #: PROTECT, not CASCADE: deleting a pack must never cascade away goods
    #: somebody paid for.
    pack = models.ForeignKey(
        StickerPack, null=True, blank=True, on_delete=models.PROTECT,
        related_name="stickers",
    )
    #: The price lives on the row rather than in a module constant, for the
    #: same reason Artifact.token_cost does: a price is data an operator
    #: changes, not a deploy.
    token_cost = models.PositiveIntegerField(default=10)
    #: Withdraws the sticker from SALE and from the PICKER. It never withdraws
    #: it from paintBody: a line already sent keeps drawing, because the check
    #: this feature adds is on SEND and never on READ.
    is_active = models.BooleanField(default=True)
    #: IN THE PACK, BUT NOT INCLUDED IN THE PACK PRICE.
    #:
    #: Owner, 2026-08-28, about NOOOO!: "входит в пак но продаётся отдельно -
    #: за 100T - только с ним коллекция будет полной". So it belongs to the
    #: collection and is shown with it, and buying the pack does not grant it.
    #:
    #: A NAMED FLAG RATHER THAN "PRICE >= 100". Deciding it by price would tie
    #: two unrelated things together, and the day he prices an ordinary sticker
    #: at 100 the pack would quietly stop including it.
    sold_separately = models.BooleanField(
        default=False,
        help_text="Shown with its pack, but the pack price does not grant it.",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "token"]

    def __str__(self):
        return f":{self.token}:"

    def clean(self):
        super().clean()
        if self.pack_id and self._state.adding:
            if ChefSticker.objects.filter(sticker__pack_id=self.pack_id).exists():
                raise ValidationError({
                    "pack": (
                        "This pack has already been bought. Its membership is frozen - "
                        "put a new sticker in a new pack."
                    ),
                })


class ChefSticker(models.Model):
    """One chef owns one sticker, forever, with no usage limit.

    WHY RecipeAuthor AND NOT User. The wallet hangs off RecipeAuthor
    (TokenWallet.chef) and the Arena chat's speaker already IS a RecipeAuthor
    (_arena_chat_speaker in views.py). Keying ownership the same way means the
    money and the goods share one key and the send-path check needs no extra
    hop from a request's user to a profile.

    WHY NOT ChefCosmetic, directly above. CosmeticItem.price is a DecimalField
    in EUROS and a sticker costs TOKENS - a column reading 10.00 that means ten
    tokens is a trap, not a saving. CosmeticItem has no key the chat can
    address, only a free-form name. And SeasonReward.cosmetic points into
    ChefCosmetic as the non-cash season-reward leg, so thirteen sticker rows
    per buyer would let a season-reward join land on a sticker.
    """

    class Source(models.TextChoices):
        SINGLE = "single", "Bought on its own"
        PACK = "pack", "Bought as part of a pack"
        GRANT = "grant", "Granted by a moderator"

    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="chef_stickers")
    sticker = models.ForeignKey(StickerItem, on_delete=models.PROTECT, related_name="owners")
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.SINGLE)
    #: The house pattern - AppreciationGift and ViewerBattleGift both carry it.
    #: With TokenSpendAllocation it is what makes a refund traceable to the lot
    #: that funded it. NULL for a moderator grant, which cost nobody anything.
    token_transaction = models.ForeignKey(
        "TokenTransaction", null=True, blank=True, on_delete=models.PROTECT,
        related_name="chef_stickers",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="granted_chef_stickers",
    )
    grant_reason = models.CharField(max_length=200, blank=True)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sticker__sort_order", "sticker__token"]
        constraints = [
            #: THIS CONSTRAINT IS THE IDEMPOTENCY, not the exists() check in
            #: the service. At READ COMMITTED two concurrent buys both pass a
            #: pre-check; the second create() raises IntegrityError inside the
            #: same atomic() as the debit, so it rolls back with it and nobody
            #: is charged twice.
            models.UniqueConstraint(fields=["chef", "sticker"], name="unique_sticker_per_chef"),
        ]

    def __str__(self):
        return f"{self.chef} - :{self.sticker.token}:"


class Season(models.Model):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    name = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPCOMING)
    #: G11, Owner 2026-08-11. tz_main.md section 17.12 lists both of these and
    #: neither existed, so a season's rules lived in season_service.py and
    #: changing them meant a deploy rather than a data edit - which is the
    #: opposite of what a season is for. Blank means "the service default",
    #: so an untouched season behaves exactly as every season has so far.
    #: G13, Owner 2026-08-11. tz_main.md section 18 asks for /battle/season/<slug>/
    #: and a season had no slug, so it could only ever be addressed by primary
    #: key. Filled from the name on save when blank, and never rewritten
    #: afterwards - a public URL that changes because somebody renamed a season
    #: is a broken link in every place that ever pointed at it.
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    crown_rule = models.CharField(
        max_length=200, blank=True,
        help_text="How the crown is decided for this season. Blank = the service default.",
    )
    reward_rules_json = models.JSONField(
        null=True, blank=True,
        help_text="Per-season reward overrides. NULL = the service default.",
    )

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            # F24 residual, 2026-08-11: activate_season locks and re-checks
            # its OWN row, but two DIFFERENT seasons activated at once take
            # different row locks and never collide - both could pass
            # get_active_season()'s unlocked read before either commits.
            # App-level locking cannot close a race across two different
            # rows; only the database can. A unique constraint on `status`
            # filtered to status="active" means every row satisfying the
            # filter must hold a distinct value of a column that only has
            # one possible value here, so at most one such row can ever
            # exist - the second writer's save() raises IntegrityError
            # instead of silently landing.
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="active"),
                name="chef_battle_season_only_one_active",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name) or "season"
            candidate, n = base, 2
            while Season.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate, n = f"{base}-{n}", n + 1
            self.slug = candidate
            if "update_fields" in kwargs and kwargs["update_fields"] is not None:
                kwargs["update_fields"] = list(kwargs["update_fields"]) + ["slug"]
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SeasonStanding(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="standings")
    chef = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="season_standings")
    score = models.IntegerField(default=0)
    rank_position = models.PositiveIntegerField(null=True, blank=True)
    #: G10, Owner 2026-08-11. tz_main.md section 17.13 asks for the chef's
    #: RECORD in that season and the row carried only a score and a position,
    #: so a season leaderboard could rank chefs but never say what any of them
    #: actually did. Frozen at close time from the season's own battles, not
    #: copied from the lifetime counters on the profile - a standing is a
    #: photograph of one season and must not move when the next one starts.
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    streak = models.PositiveIntegerField(
        default=0, help_text="Longest run of consecutive wins inside this season.")

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


# T11, Owner ruling 2026-08-15: IngredientLock is GONE, and its absence is the
# point of the ticket. The loser used to place two locks AFTER losing, on the
# raw text lines of his submitted recipe. Both halves of that are superseded:
# both chefs now place exactly two hidden locks BEFORE Stage 1, and they do it
# on their declared menu - BattleIngredient.is_key, KEY_COUNT = 2, written by
# declare_menu, which already refuses a re-declaration and only lets the battle
# reach ACTIVE once both chefs have declared. The lock the winner shoots at is
# therefore already in the database before combat starts, and a second parallel
# "lock" concept would be exactly the duplicate mechanic the standards forbid.


class IngredientShot(models.Model):
    """The Stage 1 winner's shot at one of the loser's DECLARED ingredients.

    T11, 2026-08-15: this used to carry `target_index`, a line number in the
    loser's recipe TEXT, matched against IngredientLock rows in the same index
    space. It now points at the BattleIngredient row itself - the same row
    round combat eliminates - so a hit and a bounce are decided by the
    is_key flag the chef set before the fight, not by a second lock table.

    `bounced` IS the reveal: a shot that bounced names a key ingredient the
    loser had hidden, which is what "reveal each targeted lock when it is hit"
    asks for. Nothing else needs to be stored to reveal it.
    """

    MAX_SHOTS = 3

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="ingredient_shots")
    shooter = models.ForeignKey(RecipeAuthor, on_delete=models.CASCADE, related_name="ingredient_shots")
    target_ingredient = models.ForeignKey(
        "BattleIngredient",
        on_delete=models.CASCADE,
        related_name="shots",
        help_text="The loser's declared ingredient this shot was aimed at.",
    )
    bounced = models.BooleanField(default=False, help_text="True if the shot hit a key ingredient and bounced")
    fired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fired_at"]

    def __str__(self):
        result = "bounced" if self.bounced else "hit"
        return f"Shot by {self.shooter} at {self.target_ingredient_id} ({result}, battle {self.battle_id})"


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
        #: AC-STK, 2026-08-27. A sticker is a COSMETIC and an artifact is an
        #: artifact: two goods, two ledger types, so a refund or a reconciliation
        #: never has to guess which kind of thing a debit paid for.
        #: ARTIFACT_BOUGHT above has existed since migration 0007 and is written
        #: by nothing to this day - Part B of this card is its first producer.
        COSMETIC_BOUGHT = "cosmetic_bought", "Cosmetic Bought"
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


class TokenLot(models.Model):
    """An auditable source bucket for tokens credited to a TokenWallet."""

    class SourceType(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        REWARD = "reward", "Reward / Grant"
        LEGACY = "legacy", "Legacy balance — origin ambiguous"

    wallet = models.ForeignKey(TokenWallet, on_delete=models.PROTECT, related_name="token_lots")
    source_order = models.OneToOneField(
        "TokenOrder", null=True, blank=True, on_delete=models.PROTECT,
        related_name="token_lot",
    )
    source_transaction = models.ForeignKey(
        TokenTransaction, null=True, blank=True, on_delete=models.PROTECT,
        related_name="created_lots",
    )
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    original_amount = models.PositiveIntegerField()
    remaining_amount = models.PositiveIntegerField()
    origin_ambiguous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]


class TokenSpendAllocation(models.Model):
    """FIFO allocation proving which token lot funded a debit transaction."""

    transaction = models.ForeignKey(
        TokenTransaction, on_delete=models.PROTECT, related_name="spend_allocations"
    )
    lot = models.ForeignKey(TokenLot, on_delete=models.PROTECT, related_name="spend_allocations")
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["transaction", "lot"], name="unique_token_spend_lot"),
        ]


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
        PARTIALLY_REFUNDED = "partial_refund", "Partially Refunded"
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
    refunded_amount_cents = models.PositiveIntegerField(default=0)
    clawed_tokens = models.PositiveIntegerField(default=0)
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
        # The arena hall's own chat, 2026-08-24. A new KIND rather than a new
        # model: this table already carries everything a report needs and
        # everything the moderation queue already knows how to read.
        ARENA_CHAT = "arena_chat", "Arena Chat Message"

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

    F59, 2026-08-11: PROCESSING sits between APPROVED and PAID, entered under
    a lock immediately before the Stripe transfer call and cleared (back to
    APPROVED on failure, to PAID on success) immediately after. reject/hold
    only ever act on PENDING/UNDER_REVIEW/APPROVED - PROCESSING is
    deliberately excluded everywhere, so a reject or a compliance hold can
    no longer land in the window where a transfer is genuinely in flight and
    free the underlying reward records for a second, real payout.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing (Stripe transfer in flight)"
        REJECTED = "rejected", "Rejected"
        ON_HOLD = "on_hold", "On Hold — Compliance"
        PAID = "paid", "Paid Out"
        PAID_DISPUTED = "paid_disputed", "Paid — Reconciliation Required"
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


# THE TAG IS THE TEAM'S NAME IN A CHAT LINE. Owner, 2026-08-24: chat identity
# reads `[IRL][GOD]GreenBear` - alliance tag, then clan tag, then the username.
# Neither model carried anything short enough to print there: `name` is up to
# eighty characters and `slug` is a URL, not a badge. So the tag is a real
# field, entered once by whoever creates the team, rather than a prefix sliced
# off the name at render time - a slice collides ("Fusion" and "Fusion Reborn"
# both give FUS), cannot be corrected without renaming the team, and would put
# a display accident into a permanent identity.
#
# It is NEVER concatenated into a username or into a message body (the chat
# spec's own rule): the three values travel separately and the renderer builds
# the badge. That way a chef who leaves a clan stops wearing its tag with no
# rewrite of anything already said.
_TEAM_TAG_VALIDATOR = RegexValidator(
    r"^[A-Z0-9]{2,5}$",
    "A tag is 2-5 characters, capitals and digits only - it has to fit a chat "
    "line on a phone.",
)


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
    # Blank, not null: every clan predating 2026-08-24 has none, and a chef in a
    # tagless clan simply wears no clan badge. Unique only among the clans that
    # HAVE one, so blanks never collide with each other.
    tag = models.CharField(
        max_length=5, blank=True, default="", validators=[_TEAM_TAG_VALIDATOR],
        help_text="Short badge shown in chat, e.g. GOD. 2-5 capitals or digits.",
    )
    crest_icon = models.CharField(max_length=8, blank=True)  # emoji crest
    categories = models.ManyToManyField(Faction, related_name="clans", blank=True)
    moderation_status = models.CharField(
        max_length=16, choices=Moderation.choices, default=Moderation.PENDING, db_index=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Partial, so the blanks carried by every pre-2026-08-24 clan do not
            # all collide with each other on the way in.
            models.UniqueConstraint(
                fields=["tag"],
                condition=~models.Q(tag=""),
                name="unique_clan_tag_when_set",
            ),
        ]

    def save(self, *args, **kwargs):
        # Uppercased HERE rather than trusted from the form: the admin, a
        # management command and a future API all reach this and only one of
        # them is a form. The validator demands capitals, so normalising first
        # is what stops "god" being rejected as invalid instead of accepted as
        # GOD.
        if self.tag:
            self.tag = self.tag.strip().upper()
        super().save(*args, **kwargs)

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
    # Same rules as Clan.tag above, for the same reason - see the note there.
    tag = models.CharField(
        max_length=5, blank=True, default="", validators=[_TEAM_TAG_VALIDATOR],
        help_text="Short badge shown in chat, e.g. IRL. 2-5 capitals or digits.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tag"],
                condition=~models.Q(tag=""),
                name="unique_alliance_tag_when_set",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.tag:
            self.tag = self.tag.strip().upper()
        super().save(*args, **kwargs)

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


class BattleWithdrawal(models.Model):
    """A chef asks to be let out of a battle he has already accepted.

    THE OWNER'S RULE, 2026-08-05. Pulling out is not punished by the site: the
    reasons can be anything, force majeure included, and the machine cannot tell
    them apart. So the decision is shared between the other chef and a human
    moderator, and the site itself decides nothing.

        1. The withdrawing chef states his reason - in his own words, required,
           the same shape as the contact form.
        2. The other chef answers: WITHOUT penalty, or WITH one (15 rating and 3
           reputation). Choosing the penalty obliges him to say why; waiving it
           needs no explanation at all.
        3. Either answer goes to a moderator, who is the FINAL judge. He may
           uphold the chef's answer or replace it with his own.

    The allowance is three per account. When it runs out the button goes dark
    and the chef is back to answering for a no-show.
    """

    class OpponentDecision(models.TextChoices):
        PENDING = "pending", "Waiting for the other chef"
        WITHOUT_PENALTY = "without_penalty", "Accepted without penalty"
        WITH_PENALTY = "with_penalty", "Accepted with penalty"

    class Status(models.TextChoices):
        AWAITING_OPPONENT = "awaiting_opponent", "Waiting for the other chef"
        AWAITING_MODERATOR = "awaiting_moderator", "Waiting for a moderator"
        CLOSED = "closed", "Closed"

    PENALTY_RATING = 15
    PENALTY_REPUTATION = 3

    battle = models.ForeignKey(Battle, on_delete=models.CASCADE, related_name="withdrawals")
    requester = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="battle_withdrawals_requested"
    )
    opponent = models.ForeignKey(
        RecipeAuthor, on_delete=models.CASCADE, related_name="battle_withdrawals_received"
    )
    reason = models.TextField(help_text="The withdrawing chef's own account of what happened.")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AWAITING_OPPONENT, db_index=True
    )
    opponent_decision = models.CharField(
        max_length=16, choices=OpponentDecision.choices, default=OpponentDecision.PENDING, db_index=True
    )
    opponent_reason = models.TextField(
        blank=True, help_text="Required only when the other chef asks for the penalty."
    )
    opponent_decided_at = models.DateTimeField(null=True, blank=True)

    # The moderator is the final judge: he may uphold the other chef's answer or
    # rule against it. `penalty_applied` is what actually happened to the chef.
    moderator_note = models.TextField(blank=True)
    penalty_applied = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_battle_withdrawals",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=~Q(requester=models.F("opponent")),
                name="chef_battle_withdrawal_distinct_authors",
            ),
            # One open request per battle: a second one would let a chef spend a
            # second allowance on a battle already being judged.
            models.UniqueConstraint(
                fields=["battle"],
                condition=~Q(status="closed"),
                name="chef_battle_one_open_withdrawal_per_battle",
            ),
        ]

    def __str__(self):
        return f"Withdrawal #{self.pk}: {self.requester} from battle #{self.battle_id} ({self.status})"


class OwnerAccountRestriction(models.Model):
    """Owner-imposed, time-bounded site and Arena-chat restrictions."""

    author = models.OneToOneField(
        RecipeAuthor,
        on_delete=models.CASCADE,
        related_name="owner_account_restriction",
    )
    muted_until = models.DateTimeField(null=True, blank=True, db_index=True)
    blocked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owner_account_restrictions_set",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def is_muted(self, *, at=None):
        at = at or timezone.now()
        return bool(self.muted_until and self.muted_until > at)

    def is_blocked(self, *, at=None):
        at = at or timezone.now()
        return bool(self.blocked_until and self.blocked_until > at)
class ArenaHouseStream(models.Model):
    """The Arena's own kitchen camera - one permanent channel, not a battle's.

    Owner, 2026-08-27: "я сюда буду стримить живую кухню на постоянной основе".
    That is a different thing from LiveStreamSession, which already exists and
    is deliberately left alone: a session belongs to a CHEF and a BATTLE and
    ends when the battle does. This is the house's own camera - it has no
    chef, no battle and no end, and it is the Owner's to switch on and off.
    Modelling it as a session with nulled foreign keys would have made every
    query that means "the competitors' cameras" quietly wrong.

    ONE ROW, and current() is the only way anything reads it. A settings table
    with two rows is a bug waiting for somebody to wonder which one is live,
    so there is exactly one and it is created on first read rather than by a
    data migration - nothing to keep in step, nothing to seed on a fresh
    checkout.

    WHY is_live IS A SWITCH AND NOT A GUESS. The playback URL stays put when
    the kitchen goes quiet; there is nothing in an HLS address that says
    whether anybody is standing in front of the camera. So the Owner says when
    the arena is watching, and the page shows the off-air card the rest of the
    time rather than a spinner over a dead manifest.
    """

    playback_url = models.URLField(
        max_length=500, blank=True,
        help_text="HLS manifest (.m3u8). Left empty, the widget shows the off-air card.",
    )
    title = models.CharField(
        max_length=80, blank=True,
        help_text="Shown over the picture. Empty falls back to BearCave Food Trailer.",
    )
    caption = models.CharField(
        max_length=160, blank=True,
        help_text="One quiet line under the title. Optional.",
    )
    is_live = models.BooleanField(
        default=False,
        help_text="Off shows the off-air card even when a URL is set.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="house_stream_edits",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arena house stream"
        verbose_name_plural = "Arena house stream"

    def __str__(self):
        return "House stream (%s)" % ("live" if self.on_air else "off air")

    @property
    def on_air(self):
        """Live AND actually pointed at something. Both, always - a switch on
        with no URL is an operator halfway through a change, not a broadcast."""
        return bool(self.is_live and self.playback_url.strip())

    @classmethod
    def current(cls):
        """The row, created if it is not there yet. Editing surfaces only."""
        row = cls.objects.order_by("pk").first()
        if row is None:
            row = cls.objects.create()
        return row

    @classmethod
    def for_display(cls):
        """The row or None, and NEVER a write.

        The arena page's context builder is shared with the token-gated
        preview route, whose whole contract is that it records no presence and
        creates no profile. current() would have quietly inserted a row the
        first time an anonymous holder of that link opened it - a write on a
        read-only route, which is exactly the sort of thing nobody notices
        until it is in the audit trail.
        """
        return cls.objects.order_by("pk").first()

class ArenaOperatorFlags(models.Model):
    """The switches the Master Console throws, and the only home they have.

    ``ARENA_SHOW_EMULATION_BOTS`` was never a setting. It was a
    ``getattr(settings, ..., False)`` in two modules and nothing else - no line
    in settings.py, no key in .env - so the Owner's own switch, the one he
    asked for on 2026-08-07 when he took the two test chefs off the floor,
    could only be thrown by editing code and restarting the server. A switch
    that needs a deploy is not a switch.

    ONE ROW, read through ``current()``, exactly as ``ArenaHouseStream`` does
    it - the same reasoning, not a second invention: a settings table with two
    rows is a bug waiting for somebody to wonder which one is live.

    THE SETTING STILL WINS. ``ARENA_SHOW_EMULATION_BOTS`` is read first and
    this row second, so a deployment can still pin the answer and the existing
    ``override_settings`` tests keep testing what they were written to test.
    Absent a setting - which is every real environment today - the row decides.

    NOT A PRIVILEGE STORE. Nothing here touches is_staff, is_superuser,
    has_bearseeker_privileges or has_arena_console_access; those are the
    Owner's, set in the moderation panel and nowhere else (AGENTS.md 20).
    """

    CACHE_KEY = "chef_battle:arena_flags:show_emulation_bots"
    CHAT_CACHE_KEY = "chef_battle:arena_flags:chat_is_open"
    CACHE_TTL_SECONDS = 300

    show_emulation_bots = models.BooleanField(
        default=False,
        help_text="Whether the two EMU bot chefs stand on the arena floor.",
    )
    chat_is_open = models.BooleanField(
        default=True,
        help_text=(
            "Off closes the arena chat TO NEW LINES. The panel, the history "
            "and the private threads all stay exactly where they are."
        ),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="arena_flag_edits",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arena operator flags"
        verbose_name_plural = "Arena operator flags"

    def __str__(self):
        return "Arena flags (bots %s)" % ("on" if self.show_emulation_bots else "off")

    def save(self, *args, **kwargs):
        """Any write refreshes the cached answer. The service does it too, but
        a cache that only some writers remember to clear is a stale switch
        waiting to happen - and the switch is the whole point of this row."""
        super().save(*args, **kwargs)
        cls = type(self)
        cls.forget_cached_answer(self.show_emulation_bots)
        cls.forget_cached_chat_answer(self.chat_is_open)

    @classmethod
    def current(cls):
        """The row, created if it is not there yet. Writers only."""
        row = cls.objects.order_by("pk").first()
        if row is None:
            row = cls.objects.create()
        return row

    @classmethod
    def bots_are_shown(cls):
        """The stored answer, and NEVER a write.

        Read on every arena payload build, including the token-gated preview
        route whose whole contract is that it writes nothing - so this is
        for_display()'s discipline, not current()'s. No row yet means the
        default the Owner asked for: bots off.

        CACHED, BECAUSE THE CALLERS ARE MANY. _hidden_bot_slugs() is asked the
        same question half a dozen times while one console state is assembled,
        and it used to cost nothing at all (a settings lookup). Measured, the
        naive row read took the console from 41 queries to 54 against a budget
        of 50. The cache is written through by the switch itself, so the toggle
        is still instant - the TTL is a backstop for another process, not the
        mechanism.
        """
        from django.core.cache import cache

        cached = cache.get(cls.CACHE_KEY)
        if cached is not None:
            return bool(cached)
        row = cls.objects.order_by("pk").values_list("show_emulation_bots", flat=True).first()
        value = bool(row)
        cache.set(cls.CACHE_KEY, int(value), cls.CACHE_TTL_SECONDS)
        return value

    @classmethod
    def forget_cached_answer(cls, value=None):
        """Called by the switch the moment it writes. Passing the new value
        writes it through rather than leaving the next reader to go and look."""
        from django.core.cache import cache

        if value is None:
            cache.delete(cls.CACHE_KEY)
        else:
            cache.set(cls.CACHE_KEY, int(bool(value)), cls.CACHE_TTL_SECONDS)

    @classmethod
    def chat_is_open_now(cls):
        """Whether the arena hall accepts new lines. Never a write.

        Read on every attempt to speak, so it is cached the same way the bot
        switch is, and written through by the switch itself. DEFAULT OPEN: no
        row, or a cold cache on a fresh deploy, must never silence the hall -
        the failure has to be the harmless direction.
        """
        from django.core.cache import cache

        cached = cache.get(cls.CHAT_CACHE_KEY)
        if cached is not None:
            return bool(cached)
        row = cls.objects.order_by("pk").values_list("chat_is_open", flat=True).first()
        value = True if row is None else bool(row)
        cache.set(cls.CHAT_CACHE_KEY, int(value), cls.CACHE_TTL_SECONDS)
        return value

    @classmethod
    def forget_cached_chat_answer(cls, value=None):
        from django.core.cache import cache

        if value is None:
            cache.delete(cls.CHAT_CACHE_KEY)
        else:
            cache.set(cls.CHAT_CACHE_KEY, int(bool(value)), cls.CACHE_TTL_SECONDS)
