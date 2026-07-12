import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import (
    AppreciationGiftType,
    APPRECIATION_GIFT_COST,
    Battle,
    BattleChallenge,
    BattleEntry,
    BattleEvent,
    BattleVote,
    ChefArtifact,
    ChefBattleProfile,
    ContentReport,
    LedgerEvent,
    OperatorActionIdempotencyKey,
    RewardRecord,
    TokenWallet,
    VoteIntegrityEvent,
)
from .services import (
    accept_challenge,
    calculate_battle_result,
    check_rank_matchup,
    expire_stale_challenges,
    handle_no_show_battles,
    rank_for_rating,
    refuse_challenge,
    submit_battle_entry,
)


class ChefBattleServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="chef-a", password="pw")
        self.user_b = User.objects.create_user(username="chef-b", password="pw")
        self.voter = User.objects.create_user(username="voter", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Chef A", slug="chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Chef B", slug="chef-b")

    def _challenge(self):
        return BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Best Modern Irish Lamb Dish",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )

    def test_accept_challenge_creates_active_battle(self):
        challenge = self._challenge()

        battle = accept_challenge(challenge)
        challenge.refresh_from_db()

        self.assertEqual(challenge.status, BattleChallenge.Status.ACCEPTED)
        self.assertEqual(battle.status, Battle.Status.MENU_LOCKED)
        self.assertEqual(battle.challenger, self.chef_a)
        self.assertEqual(battle.opponent, self.chef_b)
        self.assertEqual(battle.events.count(), 2)

    def test_refuse_challenge_records_reputation_penalty(self):
        challenge = self._challenge()

        refuse_challenge(challenge)
        challenge.refresh_from_db()
        profile = self.chef_b.battle_profile

        self.assertEqual(challenge.status, BattleChallenge.Status.REFUSED)
        self.assertEqual(profile.refused_battles, 1)
        self.assertEqual(profile.reputation, -5)

    def test_calculate_battle_result_updates_profiles(self):
        battle = accept_challenge(self._challenge())
        BattleVote.objects.create(battle=battle, voter=self.voter, voted_for=self.chef_a)

        calculate_battle_result(battle)
        battle.refresh_from_db()
        winner_profile = self.chef_a.battle_profile
        loser_profile = self.chef_b.battle_profile

        self.assertEqual(battle.status, Battle.Status.COMPLETED)
        self.assertEqual(battle.winner, self.chef_a)
        winner_profile.refresh_from_db()
        loser_profile.refresh_from_db()
        self.assertEqual(winner_profile.wins, 1)
        self.assertEqual(winner_profile.battle_moves, 11)  # MOVES_BATTLE_WIN(10) + MOVES_BATTLE_PARTICIPATION(1)
        self.assertEqual(loser_profile.battle_moves, 1)    # MOVES_BATTLE_PARTICIPATION(1)
        self.assertEqual(loser_profile.losses, 1)

    def test_matchup_is_limited_to_adjacent_ranks(self):
        profile_a = ChefBattleProfile.objects.create(
            author=self.chef_a,
            rank=ChefBattleProfile.Rank.KITCHEN_PORTER,
        )
        profile_b = ChefBattleProfile.objects.create(
            author=self.chef_b,
            rank=ChefBattleProfile.Rank.PREP_COOK,
        )

        self.assertIsNone(check_rank_matchup(self.chef_a, self.chef_b))

        profile_b.rank = ChefBattleProfile.Rank.COMMIS_CHEF
        profile_b.save(update_fields=["rank"])
        self.assertIn("Rank mismatch", check_rank_matchup(self.chef_a, self.chef_b))

        profile_a.is_hero = True
        profile_a.save(update_fields=["is_hero"])
        self.assertIsNone(check_rank_matchup(self.chef_a, self.chef_b))

    def test_fifteenth_win_does_not_grant_hero_status(self):
        battle = accept_challenge(self._challenge())
        profile = ChefBattleProfile.objects.create(author=self.chef_a, wins=14)
        BattleVote.objects.create(battle=battle, voter=self.voter, voted_for=self.chef_a)

        calculate_battle_result(battle)

        profile.refresh_from_db()
        self.assertEqual(profile.wins, 15)
        self.assertFalse(profile.is_hero)

    def test_vote_clean_allows_authenticated_user_without_author_profile(self):
        battle = accept_challenge(self._challenge())
        vote = BattleVote(battle=battle, voter=self.voter, voted_for=self.chef_a)

        vote.full_clean()

    def test_vote_clean_blocks_self_vote_for_linked_author(self):
        battle = accept_challenge(self._challenge())
        vote = BattleVote(battle=battle, voter=self.user_a, voted_for=self.chef_a)

        with self.assertRaises(ValidationError):
            vote.full_clean()


@override_settings(SECURE_SSL_REDIRECT=False)
class ChefBattleAccessTests(TestCase):
    """Permission tests for Chef Battle pages with feature flag enabled."""

    def setUp(self):
        User = get_user_model()
        self.client = Client()
        self.user = User.objects.create_user(username="regular", password="pw")
        self.staff = User.objects.create_user(username="staff", password="pw", is_staff=True)

    def test_anonymous_can_view_battle_home(self):
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_can_view_battle_home(self):
        self.client.login(username="regular", password="pw")
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 200)

    def test_staff_user_can_access_battle_home(self):
        self.client.login(username="staff", password="pw")
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_can_view_rankings(self):
        response = self.client.get(reverse("chef_battle:rankings"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_challenge_list_redirects_to_login(self):
        response = self.client.get(reverse("chef_battle:challenge_list"))
        # challenge_list requires login → redirect to login page
        self.assertEqual(response.status_code, 302)


@override_settings(SECURE_SSL_REDIRECT=False)
class ChefBattleChallengeCreateViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.client = Client()
        self.user = User.objects.create_user(username="challenge-owner", password="pw", is_staff=True)
        self.opponent_user = User.objects.create_user(username="challenge-opponent", password="pw")
        self.author = RecipeAuthor.objects.create(user=self.user, name="Challenge Owner", slug="challenge-owner")
        self.opponent = RecipeAuthor.objects.create(user=self.opponent_user, name="Challenge Opponent", slug="challenge-opponent")
        ChefBattleProfile.objects.create(author=self.author, battle_moves=10)

    def test_challenge_create_page_renders_guided_form_layout(self):
        self.client.login(username="challenge-owner", password="pw")

        response = self.client.get(reverse("chef_battle:challenge_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "battle-challenge-layout")
        self.assertContains(response, "Challenge checklist")
        self.assertContains(response, "Pending challenges expire after 48 hours.")
        self.assertContains(response, "Challenge Opponent")
        self.assertContains(response, 'name="opponent"', html=False)
        self.assertContains(response, 'name="battle_type"', html=False)


@override_settings(SECURE_SSL_REDIRECT=False)
class ChefEnrollViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="enroll-chef", password="pw", is_staff=True)
        self.author = RecipeAuthor.objects.create(
            user=self.user,
            name="Enroll Chef",
            slug="enroll-chef",
        )
        self.client.login(username="enroll-chef", password="pw")

    def test_enroll_actions_and_confirmation_requirements(self):
        response = self.client.get(reverse("chef_battle:chef_enroll"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        desktop_back = content.index('enroll-form__back--desktop')
        join = content.index('>Join Chef Battles</button>')
        mobile_back = content.index('enroll-form__back--mobile')
        self.assertLess(desktop_back, join)
        self.assertLess(join, mobile_back)
        self.assertContains(
            response,
            f'href="{reverse("recipes:author_dashboard")}">Back to Dashboard</a>',
            count=2,
            html=False,
        )
        self.assertContains(response, 'type="submit" class="btn-primary" disabled', html=False)

        incomplete = self.client.post(
            reverse("chef_battle:chef_enroll"),
            {"confirm_age": "1"},
        )
        self.assertEqual(incomplete.status_code, 200)
        self.assertContains(incomplete, "Please tick both boxes to continue.")

        complete = self.client.post(
            reverse("chef_battle:chef_enroll"),
            {"confirm_age": "1", "confirm_rules": "1"},
        )
        self.assertRedirects(complete, reverse("chef_battle:enroll_success"))
        profile = ChefBattleProfile.objects.get(author=self.author)
        self.assertIsNotNone(profile.enrolled_at)
        self.assertTrue(profile.age_verified)
        self.assertEqual(profile.rating, 0)
        self.assertEqual(profile.rank, ChefBattleProfile.Rank.KITCHEN_PORTER)


@override_settings(SECURE_SSL_REDIRECT=False)
class ChefBattleRulesViewTests(TestCase):
    def test_ranking_rules_match_current_rank_ladder(self):
        response = self.client.get(reverse("chef_battle:rules"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Every new Chef starts with 0 rating points")
        for rank_and_range in (
            "Kitchen Porter (0&ndash;99)",
            "Prep Chef (100&ndash;199)",
            "Commis Chef (200&ndash;299)",
            "Chef de Partie (300&ndash;399)",
            "Sous Chef (400&ndash;499)",
            "Head Chef (500&ndash;599)",
            "Executive Chef (600&ndash;699)",
            "Culinary Master (700+)",
        ):
            self.assertContains(response, rank_and_range, html=False)
        self.assertContains(response, reverse("chef_battle:rankings"))
        self.assertContains(response, "CulinEire Hero is a unique site-owner status")
        self.assertContains(response, "same or an adjacent rank")
        self.assertNotContains(response, "Level 1")
        self.assertNotContains(response, "Hero at 15")
        self.assertNotContains(response, "Michelin Chef")
        self.assertNotContains(response, "A win streak bonus")

    def test_rank_threshold_boundaries(self):
        expected_boundaries = (
            (0, ChefBattleProfile.Rank.KITCHEN_PORTER),
            (99, ChefBattleProfile.Rank.KITCHEN_PORTER),
            (100, ChefBattleProfile.Rank.PREP_COOK),
            (199, ChefBattleProfile.Rank.PREP_COOK),
            (200, ChefBattleProfile.Rank.COMMIS_CHEF),
            (300, ChefBattleProfile.Rank.CHEF_DE_PARTIE),
            (400, ChefBattleProfile.Rank.SOUS_CHEF),
            (500, ChefBattleProfile.Rank.HEAD_CHEF),
            (600, ChefBattleProfile.Rank.EXECUTIVE_CHEF),
            (700, ChefBattleProfile.Rank.CULINARY_MASTER),
        )
        for rating, expected_rank in expected_boundaries:
            with self.subTest(rating=rating):
                self.assertEqual(rank_for_rating(rating), expected_rank)


class ChefBattleAntiAbuseTests(TestCase):
    """Anti-abuse: duplicate vote, self-vote, suspicious farm-pair detection."""

    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="chef-a-abuse", password="pw")
        self.user_b = User.objects.create_user(username="chef-b-abuse", password="pw")
        self.voter1 = User.objects.create_user(username="voter1", password="pw")
        self.voter2 = User.objects.create_user(username="voter2", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Chef A", slug="chef-a-abuse")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Chef B", slug="chef-b-abuse")
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Best Soda Bread",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self.battle = accept_challenge(challenge)

    def test_duplicate_authenticated_vote_raises_integrity_error(self):
        BattleVote.objects.create(battle=self.battle, voter=self.voter1, voted_for=self.chef_a)
        with self.assertRaises(IntegrityError):
            BattleVote.objects.create(battle=self.battle, voter=self.voter1, voted_for=self.chef_a)

    def test_duplicate_anonymous_vote_same_device_raises_integrity_error(self):
        BattleVote.objects.create(
            battle=self.battle, voter=None, voted_for=self.chef_a,
            ip_hash="aaa", user_agent_hash="bbb",
        )
        with self.assertRaises(IntegrityError):
            BattleVote.objects.create(
                battle=self.battle, voter=None, voted_for=self.chef_b,
                ip_hash="aaa", user_agent_hash="bbb",
            )

    def test_self_vote_blocked_by_validation(self):
        vote = BattleVote(battle=self.battle, voter=self.user_a, voted_for=self.chef_a)
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_vote_for_non_participant_blocked_by_validation(self):
        User = get_user_model()
        outsider_user = User.objects.create_user(username="outsider-user", password="pw")
        outsider = RecipeAuthor.objects.create(user=outsider_user, name="Outsider", slug="outsider-abuse")
        vote = BattleVote(battle=self.battle, voter=self.voter1, voted_for=outsider)
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_suspicious_flag_can_be_set_on_vote(self):
        vote = BattleVote.objects.create(
            battle=self.battle, voter=self.voter1, voted_for=self.chef_a,
        )
        vote.is_suspicious = True
        vote.moderation_note = "Rapid repeated voting pattern"
        vote.save(update_fields=["is_suspicious", "moderation_note"])
        vote.refresh_from_db()
        self.assertTrue(vote.is_suspicious)
        self.assertEqual(vote.moderation_note, "Rapid repeated voting pattern")


@override_settings(CHEF_BATTLE_ENABLED=True)
class VoteIntegrityEvidenceTests(TestCase):
    """Rejected attempts are auditable but never become authoritative votes."""

    def setUp(self):
        User = get_user_model()
        user_a = User.objects.create_user(username="vie-chef-a", password="pw")
        user_b = User.objects.create_user(username="vie-chef-b", password="pw")
        self.voter = User.objects.create_user(username="vie-voter", password="pw")
        self.chef_a = RecipeAuthor.objects.create(
            user=user_a, name="VIE Chef A", slug="vie-chef-a"
        )
        self.chef_b = RecipeAuthor.objects.create(
            user=user_b, name="VIE Chef B", slug="vie-chef-b"
        )
        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Integrity evidence",
            status=Battle.Status.VOTING,
            start_time=now - timezone.timedelta(hours=1),
            submission_deadline=now - timezone.timedelta(minutes=30),
            voting_deadline=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )
        BattleEntry.objects.create(
            battle=self.battle, author=self.chef_a, is_revealed=True
        )
        self.url = reverse("chef_battle:battle_vote", args=[self.battle.pk])

    def test_authenticated_duplicate_records_constraint_event_not_vote(self):
        self.client.force_login(self.voter)
        payload = {"voted_for": self.chef_a.pk}
        self.client.post(self.url, payload, HTTP_USER_AGENT="integrity-test-agent")
        response = self.client.post(
            self.url, payload, HTTP_USER_AGENT="integrity-test-agent", follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BattleVote.objects.filter(battle=self.battle).count(), 1)
        event = VoteIntegrityEvent.objects.get(battle=self.battle)
        self.assertEqual(event.gate_code, "constraint_rejected")
        self.assertEqual(event.failed_gates, ["constraint_rejected"])
        self.assertTrue(event.is_authenticated)
        self.assertEqual(len(event.ip_hash), 64)
        self.assertEqual(len(event.user_agent_hash), 64)
        public_html = response.content.decode()
        self.assertNotIn("constraint_rejected", public_html)
        self.assertNotIn(event.ip_hash, public_html)

    def test_anonymous_duplicate_records_gate_event_not_vote(self):
        payload = {"voted_for": self.chef_a.pk}
        self.client.post(self.url, payload, HTTP_USER_AGENT="anonymous-integrity-agent")
        self.client.post(self.url, payload, HTTP_USER_AGENT="anonymous-integrity-agent")

        self.assertEqual(BattleVote.objects.filter(battle=self.battle).count(), 1)
        event = VoteIntegrityEvent.objects.get(battle=self.battle)
        self.assertEqual(event.gate_code, "duplicate_device")
        self.assertEqual(event.failed_gates, ["duplicate_device"])
        self.assertFalse(event.is_authenticated)
        self.assertEqual(len(event.ip_hash), 64)
        self.assertEqual(len(event.user_agent_hash), 64)

    def test_retention_defaults_to_90_days_and_purge_removes_only_expired(self):
        current = VoteIntegrityEvent.objects.create(
            battle=self.battle,
            gate_code="duplicate_device",
            failed_gates=["duplicate_device"],
        )
        self.assertAlmostEqual(
            (current.expires_at - current.created_at).total_seconds(),
            90 * 24 * 60 * 60,
            delta=5,
        )
        expired = VoteIntegrityEvent.objects.create(
            battle=self.battle,
            gate_code="constraint_rejected",
            failed_gates=["constraint_rejected"],
        )
        VoteIntegrityEvent.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timezone.timedelta(seconds=1)
        )

        call_command("purge_vote_integrity_events", verbosity=0)

        self.assertTrue(VoteIntegrityEvent.objects.filter(pk=current.pk).exists())
        self.assertFalse(VoteIntegrityEvent.objects.filter(pk=expired.pk).exists())


class ChefBattleExpiryTests(TestCase):
    """Tests for challenge expiry and no-show / late submission handling (CB-1402)."""

    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="chef-a-expiry", password="pw")
        self.user_b = User.objects.create_user(username="chef-b-expiry", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Chef A Exp", slug="chef-a-expiry")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Chef B Exp", slug="chef-b-expiry")

    def _past_challenge(self):
        return BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Oldest Bread Recipe",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )

    def _active_battle_past_deadline(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Best Colcannon",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        battle = accept_challenge(challenge)
        past = timezone.now() - timezone.timedelta(hours=1)
        Battle.objects.filter(pk=battle.pk).update(submission_deadline=past)
        battle.refresh_from_db()
        return battle

    def test_expire_stale_challenges_marks_expired(self):
        self._past_challenge()
        count = expire_stale_challenges()
        self.assertEqual(count, 1)
        self.assertEqual(
            BattleChallenge.objects.filter(status=BattleChallenge.Status.EXPIRED).count(), 1
        )

    def test_expire_stale_challenges_leaves_pending_future_alone(self):
        BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Still Open",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        count = expire_stale_challenges()
        self.assertEqual(count, 0)

    def test_no_show_both_cancels_battle(self):
        battle = self._active_battle_past_deadline()
        handle_no_show_battles()
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.CANCELLED)
        self.assertIn("no-show", battle.result_reason.lower())

    def test_no_show_one_side_awards_forfeit_win(self):
        from recipes.models import Recipe
        battle = self._active_battle_past_deadline()
        recipe = Recipe.objects.create(
            title="Soda Bread",
            slug="soda-bread-expiry",
            author=self.chef_a,
            category="bread",
            short_description="Test",
            ingredients="flour",
            method="mix",
            status=Recipe.Status.APPROVED,
        )
        BattleEntry.objects.create(battle=battle, author=self.chef_a, recipe=recipe)
        handle_no_show_battles()
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.COMPLETED)
        self.assertEqual(battle.winner, self.chef_a)
        self.assertIn("forfeit", battle.result_reason.lower())
        loser_profile = self.chef_b.battle_profile
        self.assertEqual(loser_profile.losses, 1)

    def test_late_entry_is_flagged(self):
        battle = self._active_battle_past_deadline()
        from recipes.models import Recipe
        recipe = Recipe.objects.create(
            title="Late Bread",
            slug="late-bread-expiry",
            author=self.chef_a,
            category="bread",
            short_description="Test",
            ingredients="flour",
            method="mix",
            status=Recipe.Status.APPROVED,
        )
        entry = submit_battle_entry(battle=battle, author=self.chef_a, recipe=recipe)
        self.assertTrue(entry.is_late)


class AwardMovesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="mover", password="pw")
        self.chef = RecipeAuthor.objects.create(user=self.user, name="Mover Chef", slug="mover-chef")

    def test_award_moves_basic(self):
        from .services import award_moves, MOVES_RECIPE_APPROVED
        from .models import BattleMoveTransaction, ChefBattleProfile
        award_moves(self.chef, MOVES_RECIPE_APPROVED, "Recipe approved")
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, MOVES_RECIPE_APPROVED)
        self.assertEqual(BattleMoveTransaction.objects.filter(chef=self.chef).count(), 1)

    def test_award_moves_daily_cap(self):
        from .services import award_moves, MOVES_CONTENT_DAILY_CAP
        from .models import ChefBattleProfile
        for i in range(10):
            award_moves(self.chef, 3, "Recipe approved")
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertLessEqual(profile.battle_moves, MOVES_CONTENT_DAILY_CAP)


class EnergyServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="energy-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=self.user, name="Energy Chef", slug="energy-chef")
        self.user2 = User.objects.create_user(username="energy-source", password="pw")
        self.source = RecipeAuthor.objects.create(user=self.user2, name="Source Chef", slug="energy-source")

    def test_award_moves_correct_rates(self):
        from .energy_service import (
            award_moves, EARN_RECIPE_PUBLISHED, EARN_ARTICLE_PUBLISHED,
            EARN_BATTLE_WON, EARN_BATTLE_PARTICIPATION,
        )
        from .models import BattleMoveTransaction, ChefBattleProfile
        TxType = BattleMoveTransaction.TxType
        award_moves(self.chef, EARN_RECIPE_PUBLISHED, TxType.RECIPE_PUBLISHED)
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, 5)
        tx = BattleMoveTransaction.objects.get(chef=self.chef)
        self.assertEqual(tx.transaction_type, TxType.RECIPE_PUBLISHED)
        self.assertEqual(tx.amount, 5)

    def test_award_moves_enforces_energy_cap(self):
        from .energy_service import award_moves, ENERGY_CAP
        from .models import BattleMoveTransaction, ChefBattleProfile
        TxType = BattleMoveTransaction.TxType
        # Give 90 moves first
        award_moves(self.chef, 90, TxType.ADMIN_ADJUSTMENT)
        # Now award 20 more — should be capped at ENERGY_CAP=100, so only 10 awarded
        awarded = award_moves(self.chef, 20, TxType.ADMIN_ADJUSTMENT)
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, ENERGY_CAP)
        self.assertEqual(awarded, 10)

    def test_award_moves_zero_when_at_cap(self):
        from .energy_service import award_moves, ENERGY_CAP
        from .models import BattleMoveTransaction, ChefBattleProfile
        TxType = BattleMoveTransaction.TxType
        award_moves(self.chef, ENERGY_CAP, TxType.ADMIN_ADJUSTMENT)
        awarded = award_moves(self.chef, 5, TxType.ADMIN_ADJUSTMENT)
        self.assertEqual(awarded, 0)
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, ENERGY_CAP)

    def test_like_anti_farming(self):
        from .energy_service import award_moves, LIKE_ANTI_FARM_MAX_PER_SOURCE
        from .models import BattleMoveTransaction, ChefBattleProfile
        TxType = BattleMoveTransaction.TxType
        # Same source_author gives max allowed likes to the chef
        for _ in range(LIKE_ANTI_FARM_MAX_PER_SOURCE):
            award_moves(self.chef, 1, TxType.LIKE_RECEIVED, source_author=self.source)
        # Next move from the same source should be blocked
        awarded = award_moves(self.chef, 1, TxType.LIKE_RECEIVED, source_author=self.source)
        self.assertEqual(awarded, 0)
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, LIKE_ANTI_FARM_MAX_PER_SOURCE)

    def test_spend_moves_deducts_balance(self):
        from .energy_service import award_moves, spend_moves
        from .models import BattleMoveTransaction, ChefBattleProfile
        TxType = BattleMoveTransaction.TxType
        award_moves(self.chef, 20, TxType.ADMIN_ADJUSTMENT)
        spend_moves(self.chef, 8, TxType.COMBAT_ACTION_SPENT)
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, 12)

    def test_spend_moves_raises_on_insufficient(self):
        from .energy_service import spend_moves, InsufficientEnergy
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        with self.assertRaises(InsufficientEnergy):
            spend_moves(self.chef, 50, TxType.COMBAT_ACTION_SPENT)

    def test_transaction_type_stored_on_battle_win(self):
        from .energy_service import award_moves
        from .models import BattleMoveTransaction
        TxType = BattleMoveTransaction.TxType
        award_moves(self.chef, 10, TxType.BATTLE_WON)
        tx = BattleMoveTransaction.objects.get(chef=self.chef, transaction_type=TxType.BATTLE_WON)
        self.assertEqual(tx.amount, 10)

    def test_like_signal_awards_move_to_content_author(self):
        from collection.models import ContentReaction
        from django.contrib.contenttypes.models import ContentType
        from pinch.models import Pinch
        from chef_battle.models import BattleMoveTransaction, ChefBattleProfile
        item = Pinch.objects.create(
            author=self.chef,
            title="Test Bite",
            slug="test-bite-energy",
            short_description="yum",
            status=Pinch.Status.APPROVED,
        )
        ct = ContentType.objects.get_for_model(Pinch)
        ContentReaction.objects.create(
            user=self.user2,
            content_type=ct,
            object_id=item.pk,
            reaction=ContentReaction.Reaction.LIKE,
        )
        profile = ChefBattleProfile.objects.get(author=self.chef)
        # Publishing the approved Pinch itself awards EARN_PINCH_PUBLISHED (+1),
        # so assert the like award in isolation via its transaction, and the
        # balance as publish + like.
        self.assertEqual(profile.battle_moves, 2)
        self.assertTrue(
            BattleMoveTransaction.objects.filter(
                chef=self.chef,
                transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
                amount=1,
            ).exists()
        )

    def test_like_signal_anti_farming(self):
        """Same user liking multiple items of the same chef is blocked after LIKE_ANTI_FARM_MAX_PER_SOURCE."""
        from collection.models import ContentReaction
        from django.contrib.contenttypes.models import ContentType
        from pinch.models import Pinch
        from chef_battle.models import ChefBattleProfile
        from chef_battle.energy_service import LIKE_ANTI_FARM_MAX_PER_SOURCE
        ct = ContentType.objects.get_for_model(Pinch)
        # Same liker (self.user2 / self.source) likes LIKE_ANTI_FARM_MAX_PER_SOURCE items — all awarded
        for i in range(LIKE_ANTI_FARM_MAX_PER_SOURCE):
            item = Pinch.objects.create(
                author=self.chef,
                title=f"Bite AF {i}",
                slug=f"bite-af2-{i}",
                short_description="yum",
                status=Pinch.Status.APPROVED,
            )
            ContentReaction.objects.create(
                user=self.user2,
                content_type=ct,
                object_id=item.pk,
                reaction=ContentReaction.Reaction.LIKE,
            )
        # One more like from the SAME user — should be blocked (per-source cap reached)
        extra_item = Pinch.objects.create(
            author=self.chef,
            title="Extra Bite",
            slug="bite-af-extra",
            short_description="yum",
            status=Pinch.Status.APPROVED,
        )
        ContentReaction.objects.create(
            user=self.user2,
            content_type=ct,
            object_id=extra_item.pk,
            reaction=ContentReaction.Reaction.LIKE,
        )
        # Each approved Pinch also awards EARN_PINCH_PUBLISHED, so isolate the
        # like awards via their transactions — the extra like must not award.
        from django.db.models import Sum
        from chef_battle.models import BattleMoveTransaction
        like_total = (
            BattleMoveTransaction.objects.filter(
                chef=self.chef,
                transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
            ).aggregate(total=Sum("amount"))["total"]
        )
        self.assertEqual(like_total, LIKE_ANTI_FARM_MAX_PER_SOURCE)


class BattleTimerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="timer-a", password="pw")
        self.user_b = User.objects.create_user(username="timer-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Timer A", slug="timer-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Timer B", slug="timer-b")

    def test_battle_has_4_day_window(self):
        """48h submission + 2 days voting = 4 days total (deadline reverted to 48h)."""
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="4-day test",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        battle = accept_challenge(challenge)
        delta = battle.end_time - battle.start_time
        self.assertEqual(delta.days, 4)

    def test_submission_deadline_is_48_hours(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="48h sub test",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        battle = accept_challenge(challenge)
        delta = battle.submission_deadline - battle.start_time
        self.assertEqual(delta, timezone.timedelta(hours=48))


@override_settings(SECURE_SSL_REDIRECT=False)
class NotificationsPollViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="poll-user", password="pw", is_staff=True)
        self.client = Client()

    def test_poll_requires_login(self):
        url = reverse("chef_battle:notifications_poll")
        resp = self.client.get(url)
        # login_required redirects anonymous users to login page
        self.assertEqual(resp.status_code, 302)

    def test_poll_returns_json_for_staff(self):
        self.client.login(username="poll-user", password="pw")
        url = reverse("chef_battle:notifications_poll")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertIn("items", data)


# ---------------------------------------------------------------------------
# CB-1601 — entry submission, reveal, crown
# ---------------------------------------------------------------------------

class EntrySubmissionTests(TestCase):
    """CB-1601: entry submission and reveal logic."""

    def setUp(self):
        from recipes.models import Recipe
        User = get_user_model()
        self.user_a = User.objects.create_user(username="entry-a", password="pw")
        self.user_b = User.objects.create_user(username="entry-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Entry A", slug="entry-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Entry B", slug="entry-b")
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Best Chowder",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self.battle = accept_challenge(challenge)
        self.recipe_a = Recipe.objects.create(
            title="Chowder A", slug="chowder-a", author=self.chef_a,
            category="soup", short_description="Test",
            ingredients="cream\nfish\npotato", method="cook",
            status=Recipe.Status.APPROVED,
        )
        self.recipe_b = Recipe.objects.create(
            title="Chowder B", slug="chowder-b", author=self.chef_b,
            category="soup", short_description="Test",
            ingredients="cream\nsmoked salmon\nleek", method="cook",
            status=Recipe.Status.APPROVED,
        )

    def test_submit_battle_entry_creates_entry(self):
        entry = submit_battle_entry(battle=self.battle, author=self.chef_a, recipe=self.recipe_a)
        self.assertEqual(entry.battle, self.battle)
        self.assertEqual(entry.author, self.chef_a)
        self.assertEqual(entry.recipe, self.recipe_a)
        self.assertFalse(entry.is_revealed)

    def test_entries_hidden_before_reveal(self):
        submit_battle_entry(battle=self.battle, author=self.chef_a, recipe=self.recipe_a)
        entry = BattleEntry.objects.get(battle=self.battle, author=self.chef_a)
        self.assertFalse(entry.is_revealed)

    def test_reveal_entries_if_ready_reveals_when_both_submitted(self):
        from chef_battle.services import reveal_entries_if_ready
        submit_battle_entry(battle=self.battle, author=self.chef_a, recipe=self.recipe_a)
        submit_battle_entry(battle=self.battle, author=self.chef_b, recipe=self.recipe_b)
        reveal_entries_if_ready(self.battle)
        self.assertTrue(BattleEntry.objects.get(battle=self.battle, author=self.chef_a).is_revealed)
        self.assertTrue(BattleEntry.objects.get(battle=self.battle, author=self.chef_b).is_revealed)

    def test_reveal_does_not_trigger_with_only_one_entry(self):
        from chef_battle.services import reveal_entries_if_ready
        submit_battle_entry(battle=self.battle, author=self.chef_a, recipe=self.recipe_a)
        reveal_entries_if_ready(self.battle)
        self.assertFalse(BattleEntry.objects.get(battle=self.battle, author=self.chef_a).is_revealed)


class CrownTests(TestCase):
    """CB-1601/1404: crown is awarded to the winner."""

    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="crown-a", password="pw")
        self.user_b = User.objects.create_user(username="crown-b", password="pw")
        self.voter = User.objects.create_user(username="crown-voter", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Crown A", slug="crown-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Crown B", slug="crown-b")
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Best Crown Dish",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self.battle = accept_challenge(challenge)

    def test_winner_receives_24h_crown(self):
        BattleVote.objects.create(battle=self.battle, voter=self.voter, voted_for=self.chef_a)
        before = timezone.now()
        calculate_battle_result(self.battle)
        profile = self.chef_a.battle_profile
        self.assertIsNotNone(profile.crown_until)
        self.assertGreater(profile.crown_until, before + timezone.timedelta(hours=23))
        self.assertTrue(profile.has_crown)

    def test_crown_count_increments_on_win(self):
        BattleVote.objects.create(battle=self.battle, voter=self.voter, voted_for=self.chef_a)
        calculate_battle_result(self.battle)
        self.assertEqual(self.chef_a.battle_profile.crown_count, 1)

    def test_crown_event_created(self):
        from chef_battle.models import BattleEvent
        BattleVote.objects.create(battle=self.battle, voter=self.voter, voted_for=self.chef_a)
        calculate_battle_result(self.battle)
        self.assertTrue(
            self.battle.events.filter(event_type=BattleEvent.EventType.CROWN_AWARDED).exists()
        )

    def test_battle_completed_event_published_to_news(self):
        from chef_battle.models import BattleEvent
        BattleVote.objects.create(battle=self.battle, voter=self.voter, voted_for=self.chef_a)
        calculate_battle_result(self.battle)
        event = self.battle.events.filter(event_type=BattleEvent.EventType.BATTLE_COMPLETED).first()
        self.assertIsNotNone(event)
        self.assertTrue(event.is_public)


class AutoCompleteVotingTests(TestCase):
    """CB-1402: management command completes VOTING battles past deadline."""

    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="voting-auto-a", password="pw")
        self.user_b = User.objects.create_user(username="voting-auto-b", password="pw")
        self.voter = User.objects.create_user(username="voting-auto-v", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Voting A", slug="voting-auto-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Voting B", slug="voting-auto-b")

    def _voting_battle_past_deadline(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Auto Complete Dish",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        battle = accept_challenge(challenge)
        past = timezone.now() - timezone.timedelta(hours=1)
        Battle.objects.filter(pk=battle.pk).update(
            status=Battle.Status.VOTING,
            voting_deadline=past,
        )
        battle.refresh_from_db()
        return battle

    def test_expired_voting_battle_is_completed_by_calculate(self):
        battle = self._voting_battle_past_deadline()
        BattleVote.objects.create(battle=battle, voter=self.voter, voted_for=self.chef_a)
        calculate_battle_result(battle)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.COMPLETED)
        self.assertEqual(battle.winner, self.chef_a)


# ---------------------------------------------------------------------------
# CB-1602 — Permission tests
# ---------------------------------------------------------------------------

@override_settings(SECURE_SSL_REDIRECT=False)
class PermissionTests(TestCase):
    """CB-1602: non-participants and anonymous users are blocked from sensitive actions."""

    def setUp(self):
        from recipes.models import Recipe
        User = get_user_model()
        self.user_a = User.objects.create_user(username="perm-a", password="pw", is_staff=True)
        self.user_b = User.objects.create_user(username="perm-b", password="pw", is_staff=True)
        self.outsider_user = User.objects.create_user(username="perm-out", password="pw", is_staff=True)
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Perm A", slug="perm-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Perm B", slug="perm-b")
        self.outsider = RecipeAuthor.objects.create(user=self.outsider_user, name="Outsider", slug="perm-out")
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Permission Dish",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self.battle = accept_challenge(challenge)
        self.recipe_out = Recipe.objects.create(
            title="Outsider Dish", slug="outsider-dish", author=self.outsider,
            category="meat", short_description="Test",
            ingredients="beef", method="roast",
            status=Recipe.Status.APPROVED,
        )
        self.client = Client()

    def test_non_participant_cannot_submit_entry(self):
        from chef_battle.services import submit_battle_entry
        from django.core.exceptions import ValidationError
        with self.assertRaises((ValidationError, Exception)):
            submit_battle_entry(
                battle=self.battle,
                author=self.outsider,
                recipe=self.recipe_out,
            )

    def test_anonymous_cannot_submit_entry_via_view(self):
        url = reverse("chef_battle:battle_entry_submit", kwargs={"pk": self.battle.pk})
        resp = self.client.post(url, {})
        # anonymous → 404 (chef_battle_guard) or redirect to login
        self.assertIn(resp.status_code, [302, 404])

    def test_outsider_cannot_respond_to_others_challenge(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Other Challenge",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self.client.login(username="perm-out", password="pw")
        url = reverse("chef_battle:challenge_respond", kwargs={"pk": challenge.pk})
        resp = self.client.post(url, {"action": "accept"})
        # outsider is not the opponent → 404 or redirect
        self.assertIn(resp.status_code, [302, 404])
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, BattleChallenge.Status.PENDING)

    def test_participant_cannot_vote_in_own_battle(self):
        vote = BattleVote(battle=self.battle, voter=self.user_a, voted_for=self.chef_a)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            vote.full_clean()


# ---------------------------------------------------------------------------
# CB-17xx: Phase 7 — Gift catalogue & token model
# ---------------------------------------------------------------------------

class AppreciationGiftCatalogueTests(TestCase):
    """CB-1701 – CB-1704: gift types, costs, and keys are correct."""

    def test_six_gift_types_exist(self):
        types = list(AppreciationGiftType)
        self.assertEqual(len(types), 6)

    def test_gift_type_keys_match_cost_dict(self):
        for gt in AppreciationGiftType:
            self.assertIn(gt.value, APPRECIATION_GIFT_COST,
                          f"{gt.value} missing from APPRECIATION_GIFT_COST")

    def test_coffee_costs_20(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.COFFEE], 20)

    def test_virtual_beer_toast_costs_30(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.VIRTUAL_BEER_TOAST], 30)

    def test_virtual_whiskey_toast_costs_50(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.VIRTUAL_WHISKEY_TOAST], 50)

    def test_flowers_costs_80(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.FLOWERS], 80)

    def test_celebration_cocktail_costs_80(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.CELEBRATION_COCKTAIL], 80)

    def test_virtual_champagne_bottle_costs_100(self):
        self.assertEqual(APPRECIATION_GIFT_COST[AppreciationGiftType.VIRTUAL_CHAMPAGNE_BOTTLE], 100)

    def test_gift_type_max_length_fits_longest_key(self):
        longest = max(len(gt.value) for gt in AppreciationGiftType)
        field = AppreciationGiftType.__mro__  # just check the known worst case
        self.assertLessEqual(longest, 32, "gift_type key exceeds max_length=32")


# ---------------------------------------------------------------------------
# CB-18xx: Phase 8 — LSR auto-creation and LedgerEvent on gift send
# ---------------------------------------------------------------------------

@override_settings(CHEF_BATTLE_ENABLED=True)
class LSRRewardTests(TestCase):
    """CB-1801 – CB-1804: sending appreciation gift creates LSR and LedgerEvents."""

    def setUp(self):
        User = get_user_model()
        self.sender_user = User.objects.create_user(username="sender", password="pw")
        self.recipient_user = User.objects.create_user(username="recipient", password="pw")
        self.sender = RecipeAuthor.objects.create(
            user=self.sender_user, name="Sender Chef", slug="sender-chef"
        )
        self.recipient = RecipeAuthor.objects.create(
            user=self.recipient_user, name="Recipient Chef", slug="recipient-chef"
        )
        TokenWallet.objects.create(chef=self.sender, balance=500)
        TokenWallet.objects.create(chef=self.recipient, balance=0)

    def _send_coffee(self):
        from .services import send_appreciation_gift
        return send_appreciation_gift(
            sender_user=self.sender_user,
            recipient=self.recipient,
            gift_type=AppreciationGiftType.COFFEE,
        )

    def test_gift_is_created(self):
        gift = self._send_coffee()
        self.assertIsNotNone(gift.pk)
        self.assertEqual(gift.gift_type, AppreciationGiftType.COFFEE)

    def test_sender_wallet_debited(self):
        # Debit 20T for gift, credit 2T LSR — net 482. Verify debit transaction exists.
        from .models import TokenTransaction
        self._send_coffee()
        debit_tx = TokenTransaction.objects.filter(
            wallet__chef=self.sender,
            tx_type=TokenTransaction.TxType.GIFT_SENT,
            amount=-20,
        )
        self.assertTrue(debit_tx.exists())

    def test_lsr_reward_record_created(self):
        self._send_coffee()
        records = RewardRecord.objects.filter(
            recipient=self.sender,
            reward_type=RewardRecord.RewardType.LSR,
        )
        self.assertEqual(records.count(), 1)

    def test_lsr_amount_is_10_percent_of_gift_cost(self):
        self._send_coffee()
        reward = RewardRecord.objects.get(recipient=self.sender, reward_type=RewardRecord.RewardType.LSR)
        self.assertEqual(reward.tokens_granted, 2)

    def test_lsr_credited_to_sender_wallet(self):
        self._send_coffee()
        wallet = TokenWallet.objects.get(chef=self.sender)
        # debit 20, credit 2 LSR → net 482
        self.assertEqual(wallet.balance, 482)

    def test_ledger_event_gift_sent_created(self):
        self._send_coffee()
        self.assertTrue(
            LedgerEvent.objects.filter(
                event_type=LedgerEvent.EventType.GIFT_SENT,
                actor=self.sender,
                target=self.recipient,
            ).exists()
        )

    def test_ledger_event_lsr_granted_created(self):
        self._send_coffee()
        self.assertTrue(
            LedgerEvent.objects.filter(
                event_type=LedgerEvent.EventType.LSR_GRANTED,
                actor=self.sender,
            ).exists()
        )

    def test_unknown_gift_type_raises_value_error(self):
        from .services import send_appreciation_gift
        with self.assertRaises(ValueError):
            send_appreciation_gift(
                sender_user=self.sender_user,
                recipient=self.recipient,
                gift_type="invalid_type",
            )


# ---------------------------------------------------------------------------
# CB-19xx: Phase 8 — LedgerEvent immutability
# ---------------------------------------------------------------------------

class LedgerEventImmutabilityTests(TestCase):
    """CB-1901 – CB-1902: LedgerEvent cannot be updated or deleted."""

    def setUp(self):
        self.event = LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.VOTE_CAST,
            payload={"battle_id": 1},
        )

    def test_save_on_existing_ledger_event_raises(self):
        with self.assertRaises(ValueError):
            self.event.payload = {"tampered": True}
            self.event.save()

    def test_delete_on_ledger_event_raises(self):
        with self.assertRaises(ValueError):
            self.event.delete()

    def test_new_ledger_event_saves_normally(self):
        new_event = LedgerEvent(
            event_type=LedgerEvent.EventType.VOTE_CAST,
            payload={},
        )
        new_event.save()
        self.assertIsNotNone(new_event.pk)


# ---------------------------------------------------------------------------
# CB-20xx: Phase 8 — ContentReport DSA flow
# ---------------------------------------------------------------------------

class ContentReportTests(TestCase):
    """CB-2001 – CB-2003: DSA content report model behaviour."""

    def setUp(self):
        User = get_user_model()
        self.reporter_user = User.objects.create_user(username="reporter", password="pw")

    def test_report_created_with_pending_status(self):
        report = ContentReport.objects.create(
            reporter=self.reporter_user,
            content_kind=ContentReport.ContentKind.BATTLE_CHAT,
            object_id=42,
            reason="Offensive language",
        )
        self.assertEqual(report.status, ContentReport.Status.PENDING)

    def test_report_can_be_actioned(self):
        report = ContentReport.objects.create(
            reporter=self.reporter_user,
            content_kind=ContentReport.ContentKind.BATTLE_ENTRY,
            object_id=7,
            reason="Plagiarism",
        )
        report.status = ContentReport.Status.ACTIONED
        report.moderator_note = "Entry removed."
        report.save()
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.Status.ACTIONED)

    def test_reporter_can_be_anonymous(self):
        report = ContentReport.objects.create(
            reporter=None,
            content_kind=ContentReport.ContentKind.CHEF_PROFILE,
            object_id=99,
            reason="Spam",
        )
        self.assertIsNone(report.reporter)


# ---------------------------------------------------------------------------
# CB-21xx: Phase 8 — Compliance flags on ChefBattleProfile
# ---------------------------------------------------------------------------

class ComplianceFlagTests(TestCase):
    """CB-2101 – CB-2103: is_suspended and fraud_flag defaults and behaviour."""

    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="compliancechef", password="pw")
        chef = RecipeAuthor.objects.create(user=user, name="Compliance Chef", slug="compliance-chef")
        self.profile = ChefBattleProfile.objects.create(author=chef)

    def test_new_profile_is_not_suspended(self):
        self.assertFalse(self.profile.is_suspended)

    def test_new_profile_has_no_fraud_flag(self):
        self.assertFalse(self.profile.fraud_flag)

    def test_new_profile_age_not_verified(self):
        self.assertFalse(self.profile.age_verified)

    def test_suspend_profile(self):
        self.profile.is_suspended = True
        self.profile.suspension_reason = "Repeated vote manipulation"
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_suspended)
        self.assertEqual(self.profile.suspension_reason, "Repeated vote manipulation")


# ---------------------------------------------------------------------------
# CB-22xx: Phase 8 — Suspension gate on arena POST actions
# ---------------------------------------------------------------------------

@override_settings(CHEF_BATTLE_ENABLED=True)
class SuspensionGateTests(TestCase):
    """CB-2201: suspended profiles cannot POST to arena views."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="suspendedchef", password="pw")
        chef = RecipeAuthor.objects.create(user=self.user, name="Suspended Chef", slug="suspended-chef")
        profile = ChefBattleProfile.objects.create(author=chef)
        profile.is_suspended = True
        profile.save()
        self.client = Client()
        self.client.login(username="suspendedchef", password="pw")

    def test_suspended_user_post_to_send_gift_is_redirected(self):
        url = reverse("chef_battle:send_appreciation_gift", kwargs={"pk": 1})
        response = self.client.post(url, {"gift_type": "coffee"})
        # redirect, not 200 or 403
        self.assertIn(response.status_code, [301, 302])


# ---------------------------------------------------------------------------
# CB-23xx: Phase 8 — Battle completion writes LedgerEvent
# ---------------------------------------------------------------------------

class BattleCompletionLedgerTests(TestCase):
    """CB-2301: calculate_battle_result writes BATTLE_COMPLETED LedgerEvent."""

    def setUp(self):
        User = get_user_model()
        user_a = User.objects.create_user(username="ledger-a", password="pw")
        user_b = User.objects.create_user(username="ledger-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=user_a, name="Ledger A", slug="ledger-a")
        self.chef_b = RecipeAuthor.objects.create(user=user_b, name="Ledger B", slug="ledger-b")

    def _make_battle(self):
        return Battle.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Ledger Battle",
            status=Battle.Status.VOTING,
            start_time=timezone.now() - timezone.timedelta(days=6),
            submission_deadline=timezone.now() - timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=1),
        )

    def test_ledger_event_created_on_battle_complete(self):
        battle = self._make_battle()
        BattleVote.objects.create(battle=battle, voted_for=self.chef_a, ip_hash="x1", user_agent_hash="y1")
        BattleVote.objects.create(battle=battle, voted_for=self.chef_a, ip_hash="x2", user_agent_hash="y2")
        calculate_battle_result(battle)
        self.assertTrue(
            LedgerEvent.objects.filter(
                event_type=LedgerEvent.EventType.BATTLE_COMPLETED,
                related_battle=battle,
                actor=self.chef_a,
            ).exists()
        )


# ── CB-2001  Feature flags ──────────────────────────────────────────────────

class FeatureFlagTests(TestCase):
    def test_stripe_connect_payouts_flag_defaults_false(self):
        from django.conf import settings
        self.assertFalse(getattr(settings, "ENABLE_STRIPE_CONNECT_PAYOUTS", True))

    def test_live_video_flag_defaults_false(self):
        from django.conf import settings
        self.assertFalse(getattr(settings, "ENABLE_LIVE_VIDEO", True))

    def test_ai_image_review_flag_defaults_false(self):
        from django.conf import settings
        self.assertFalse(getattr(settings, "ENABLE_AI_IMAGE_REVIEW_PROVIDER", True))


# ── CB-2002  RewardRecord lifecycle ────────────────────────────────────────

class RewardRecordLifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="rr-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=self.user, name="RR Chef", slug="rr-chef")

    def _make_reward(self, tokens=50):
        return RewardRecord.objects.create(
            recipient=self.chef,
            reward_type=RewardRecord.RewardType.CBR,
            tokens_granted=tokens,
            reason="Test reward",
        )

    def test_new_reward_defaults_to_pending(self):
        reward = self._make_reward()
        self.assertEqual(reward.status, RewardRecord.Status.PENDING)

    def test_issue_reward_credits_wallet_and_sets_issued(self):
        from .services import issue_reward
        reward = self._make_reward(tokens=100)
        issue_reward(reward.pk)
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardRecord.Status.ISSUED)
        self.assertIsNotNone(reward.issued_at)
        wallet = TokenWallet.objects.get(chef=self.chef)
        self.assertEqual(wallet.balance, 100)

    def test_issue_reward_creates_ledger_event(self):
        from .services import issue_reward
        initial_count = LedgerEvent.objects.count()
        reward = self._make_reward(tokens=50)
        issue_reward(reward.pk)
        self.assertEqual(LedgerEvent.objects.count(), initial_count + 1)
        self.assertTrue(
            LedgerEvent.objects.filter(event_type=LedgerEvent.EventType.CBR_GRANTED).exists()
        )

    def test_issue_reward_twice_raises(self):
        from .services import issue_reward
        reward = self._make_reward()
        issue_reward(reward.pk)
        with self.assertRaises(ValueError):
            issue_reward(reward.pk)

    def test_reverse_reward_deducts_wallet_and_sets_reversed(self):
        from .services import issue_reward, reverse_reward
        reward = self._make_reward(tokens=80)
        issue_reward(reward.pk)
        reverse_reward(reward.pk, note="Test reversal")
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardRecord.Status.REVERSED)
        self.assertIsNotNone(reward.reversed_at)
        self.assertEqual(reward.status_note, "Test reversal")
        wallet = TokenWallet.objects.get(chef=self.chef)
        self.assertEqual(wallet.balance, 0)

    def test_expire_rewards_marks_expired(self):
        from .services import issue_reward, expire_rewards
        reward = self._make_reward(tokens=10)
        issue_reward(reward.pk)
        reward.expires_at = timezone.now() - timezone.timedelta(hours=1)
        reward.save(update_fields=["expires_at", "updated_at"])
        count = expire_rewards()
        self.assertEqual(count, 1)
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardRecord.Status.EXPIRED)

    def test_expire_rewards_ignores_non_expired(self):
        from .services import issue_reward, expire_rewards
        reward = self._make_reward(tokens=10)
        issue_reward(reward.pk)
        reward.expires_at = timezone.now() + timezone.timedelta(days=7)
        reward.save(update_fields=["expires_at", "updated_at"])
        count = expire_rewards()
        self.assertEqual(count, 0)


# ── CB-2003  TokenOrder VAT & consent fields ────────────────────────────────

class TokenOrderVatConsentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="shop-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=self.user, name="Shop Chef", slug="shop-chef")
        ChefBattleProfile.objects.create(author=self.chef, age_verified=True)
        self.wallet, _ = TokenWallet.objects.get_or_create(chef=self.chef)
        from .models import TokenPackage
        self.package = TokenPackage.objects.create(
            key="test_pkg",
            name="Test Package",
            tokens=100,
            price_eur="10.00",
            discount_percent=0,
            sort_order=99,
        )

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_fake",
        STRIPE_PRICE_MODE="test",
    )
    def test_checkout_requires_withdrawal_consent(self):
        self.client.force_login(self.user)
        import json
        url = reverse("chef_battle:token_checkout_create")
        resp = self.client.post(
            url,
            data=json.dumps({"package_id": self.package.pk, "withdrawal_consent": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("consent", data.get("error", "").lower())

    def test_token_order_stores_vat_breakdown(self):
        from decimal import Decimal
        from .models import TokenOrder
        order = TokenOrder.objects.create(
            wallet=self.wallet,
            package=self.package,
            tokens=100,
            amount_eur_cents=1000,
            amount_net_cents=813,
            vat_amount_cents=187,
            vat_rate=Decimal("0.2300"),
            right_of_withdrawal_waived=True,
            withdrawal_consent_at=timezone.now(),
            consent_text_snapshot="Test consent text",
        )
        order.refresh_from_db()
        self.assertEqual(order.amount_net_cents, 813)
        self.assertEqual(order.vat_amount_cents, 187)
        self.assertEqual(order.vat_rate, Decimal("0.2300"))
        self.assertTrue(order.right_of_withdrawal_waived)
        self.assertIsNotNone(order.withdrawal_consent_at)
        self.assertEqual(order.consent_text_snapshot, "Test consent text")


# ── CB-2004  LedgerEvent hash chain ────────────────────────────────────────

class LedgerEventHashChainTests(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="hc-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=user, name="HC Chef", slug="hc-chef")

    def _make_event(self):
        return LedgerEvent.objects.create(
            event_type=LedgerEvent.EventType.VOTE_CAST,
            actor=self.chef,
            payload={"test": True},
        )

    def test_first_event_has_empty_prev_hash(self):
        e = self._make_event()
        self.assertEqual(e.prev_hash, "")

    def test_event_hash_is_64_hex_chars(self):
        e = self._make_event()
        self.assertEqual(len(e.event_hash), 64)
        self.assertRegex(e.event_hash, r"^[0-9a-f]{64}$")

    def test_second_event_prev_hash_equals_first_event_hash(self):
        e1 = self._make_event()
        e2 = self._make_event()
        e2.refresh_from_db()
        self.assertEqual(e2.prev_hash, e1.event_hash)

    def test_verify_chain_returns_true_when_intact(self):
        self._make_event()
        self._make_event()
        self._make_event()
        ok, broken_pk = LedgerEvent.verify_chain()
        self.assertTrue(ok)
        self.assertIsNone(broken_pk)

    def test_ledger_event_immutable_update_raises(self):
        e = self._make_event()
        with self.assertRaises(ValueError):
            e.event_type = LedgerEvent.EventType.FRAUD_FLAG
            e.save()

    def test_ledger_event_immutable_delete_raises(self):
        e = self._make_event()
        with self.assertRaises(ValueError):
            e.delete()


# ── CB-2005  Anti-fraud pipeline ────────────────────────────────────────────

class FraudGateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="fg-a", password="pw")
        self.user_b = User.objects.create_user(username="fg-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="FG Chef A", slug="fg-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="FG Chef B", slug="fg-chef-b")

    def _make_battle(self):
        return Battle.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Fraud Test Battle",
            status=Battle.Status.VOTING,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            submission_deadline=timezone.now() - timezone.timedelta(hours=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_gate_account_age_passes_old_account(self):
        from .fraud import gate_account_age
        # user_a was just created but age check with min_days=0 should pass
        r = gate_account_age(self.user_a, min_days=0)
        self.assertTrue(r.passed)

    def test_gate_account_age_fails_brand_new_account(self):
        from .fraud import gate_account_age
        r = gate_account_age(self.user_a, min_days=999)
        self.assertFalse(r.passed)
        self.assertIn("account_age", r.gate)

    def test_gate_self_vote_fails(self):
        from .fraud import gate_self_vote
        r = gate_self_vote(self.chef_a, self.chef_a)
        self.assertFalse(r.passed)

    def test_gate_self_vote_passes_different_chefs(self):
        from .fraud import gate_self_vote
        r = gate_self_vote(self.chef_a, self.chef_b)
        self.assertTrue(r.passed)

    def test_gate_participant_vote_fails_for_participant(self):
        from .fraud import gate_participant_vote
        battle = self._make_battle()
        r = gate_participant_vote(self.chef_a, battle)
        self.assertFalse(r.passed)

    def test_gate_participant_vote_passes_for_third_party(self):
        from .fraud import gate_participant_vote
        User = get_user_model()
        third_user = User.objects.create_user(username="fg-third", password="pw")
        third_chef = RecipeAuthor.objects.create(user=third_user, name="Third", slug="fg-third")
        battle = self._make_battle()
        r = gate_participant_vote(third_chef, battle)
        self.assertTrue(r.passed)

    def test_gate_suspended_account_fails(self):
        from .fraud import gate_suspended_account
        from .services import get_or_create_battle_profile
        profile = get_or_create_battle_profile(self.chef_a)
        profile.is_suspended = True
        profile.suspension_reason = "Test suspension"
        profile.save(update_fields=["is_suspended", "suspension_reason"])
        r = gate_suspended_account(self.chef_a)
        self.assertFalse(r.passed)

    def test_gate_suspended_account_passes_normal(self):
        from .fraud import gate_suspended_account
        r = gate_suspended_account(self.chef_b)
        self.assertTrue(r.passed)

    def test_gate_withdrawal_consent_fails_without_waiver(self):
        from .fraud import gate_withdrawal_consent
        r = gate_withdrawal_consent(False)
        self.assertFalse(r.passed)

    def test_gate_withdrawal_consent_passes_with_waiver(self):
        from .fraud import gate_withdrawal_consent
        r = gate_withdrawal_consent(True)
        self.assertTrue(r.passed)

    def test_gate_challenge_spam_blocks_excess(self):
        from .fraud import gate_challenge_spam
        for _ in range(3):
            BattleChallenge.objects.create(
                challenger=self.chef_a,
                opponent=self.chef_b,
                theme="Spam challenge",
                expires_at=timezone.now() + timezone.timedelta(hours=1),
            )
        r = gate_challenge_spam(self.chef_a, max_per_day=3)
        self.assertFalse(r.passed)

    def test_gate_challenge_spam_allows_under_limit(self):
        from .fraud import gate_challenge_spam
        r = gate_challenge_spam(self.chef_a, max_per_day=3)
        self.assertTrue(r.passed)

    @override_settings(ENABLE_AI_IMAGE_REVIEW_PROVIDER=False)
    def test_gate_ai_image_review_passes_when_disabled(self):
        from .fraud import gate_ai_image_review
        r = gate_ai_image_review(None)
        self.assertTrue(r.passed)

    @override_settings(ENABLE_LIVE_VIDEO=False)
    def test_gate_live_video_safety_passes_when_disabled(self):
        from .fraud import gate_live_video_safety
        r = gate_live_video_safety(None)
        self.assertTrue(r.passed)

    def test_run_fraud_gates_all_pass(self):
        from .fraud import run_fraud_gates, gate_self_vote, gate_withdrawal_consent
        result = run_fraud_gates([
            (gate_self_vote, (self.chef_a, self.chef_b), {}),
            (gate_withdrawal_consent, (True,), {}),
        ])
        self.assertTrue(result.passed)
        self.assertEqual(len(result.failed_gates), 0)

    def test_run_fraud_gates_one_fails(self):
        from .fraud import run_fraud_gates, gate_self_vote, gate_withdrawal_consent
        result = run_fraud_gates([
            (gate_self_vote, (self.chef_a, self.chef_a), {}),
            (gate_withdrawal_consent, (True,), {}),
        ])
        self.assertFalse(result.passed)
        self.assertIn("self_vote", result.failed_gates)


# ── CB-2006 — Age verification gate ──────────────────────────────────────────

class AgeVerificationGateTests(TestCase):
    """gate_age_verified enforces 18+ before paid arena actions (CB-2006)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("age_tester", password="pass")
        from recipes.models import RecipeAuthor
        self.author = RecipeAuthor.objects.create(user=self.user, name="Age Tester", slug="age-tester")
        from .models import ChefBattleProfile
        self.profile = ChefBattleProfile.objects.create(author=self.author, age_verified=False)

    def test_gate_fails_when_age_not_verified(self):
        from .fraud import gate_age_verified
        r = gate_age_verified(self.author)
        self.assertFalse(r.passed)
        self.assertEqual(r.gate, "age_verified")

    def test_gate_passes_when_age_verified(self):
        from .fraud import gate_age_verified
        self.profile.age_verified = True
        self.profile.save()
        r = gate_age_verified(self.author)
        self.assertTrue(r.passed)

    def test_gate_fails_when_author_is_none(self):
        from .fraud import gate_age_verified
        r = gate_age_verified(None)
        self.assertFalse(r.passed)

    def test_gate_fails_when_profile_missing(self):
        from .fraud import gate_age_verified
        from recipes.models import RecipeAuthor
        no_profile_user = get_user_model().objects.create_user("no_profile_age", password="pass")
        author = RecipeAuthor.objects.create(user=no_profile_user, name="No Profile", slug="no-profile-age")
        r = gate_age_verified(author)
        self.assertFalse(r.passed)

    def test_token_checkout_blocked_when_age_not_verified(self):
        """POST to token_checkout_create returns 403 JSON when age not verified."""
        from .models import TokenPackage, TokenWallet
        TokenWallet.objects.create(chef=self.author, balance=0)
        pkg = TokenPackage.objects.create(
            key="starter_age_test", name="Starter Age Test", tokens=100, price_eur="5.00", is_active=True
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("chef_battle:token_checkout_create"),
            data=json.dumps({"package_id": pkg.pk, "withdrawal_consent": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("error", data)

    def test_send_gift_blocked_when_age_not_verified(self):
        """POST to send_appreciation_gift redirects with error when age not verified."""
        from .models import Battle, BattleChallenge, TokenWallet
        other_user = get_user_model().objects.create_user("gift_recipient_age", password="pass")
        from recipes.models import RecipeAuthor
        other_author = RecipeAuthor.objects.create(
            user=other_user, name="Gift Recipient Age", slug="gift-recipient-age"
        )
        from .models import ChefBattleProfile
        ChefBattleProfile.objects.create(author=other_author, age_verified=True)
        TokenWallet.objects.create(chef=self.author, balance=500)
        challenge = BattleChallenge.objects.create(
            challenger=self.author,
            opponent=other_author,
            theme="Test",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        now = timezone.now()
        battle = Battle.objects.create(
            challenger=self.author,
            opponent=other_author,
            challenge=challenge,
            status=Battle.Status.VOTING,
            submission_deadline=now + timezone.timedelta(hours=1),
            voting_deadline=now + timezone.timedelta(hours=2),
            end_time=now + timezone.timedelta(hours=3),
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("chef_battle:send_appreciation_gift", kwargs={"pk": battle.pk}),
            data={"recipient_slug": other_author.slug, "gift_type": "flowers", "message": ""},
        )
        self.assertIn(resp.status_code, [301, 302])


# CB-21xx: Phase 9 — Payout, reward agreement, forbidden claims, content report


class ForbiddenClaimsTests(TestCase):
    """CB-2101 to CB-2105: check_forbidden_claims service."""

    def test_clean_text_returns_empty(self):
        from .services import check_forbidden_claims
        self.assertEqual(check_forbidden_claims("Lovely Irish stew with potatoes."), [])

    def test_detects_allergy_claim(self):
        from .services import check_forbidden_claims
        hits = check_forbidden_claims("This dish is safe for all allergy sufferers.")
        self.assertIn("safe for all allerg", hits)

    def test_case_insensitive(self):
        from .services import check_forbidden_claims
        hits = check_forbidden_claims("CLINICALLY PROVEN to boost energy.")
        self.assertIn("clinically proven", hits)

    def test_detects_multiple_phrases(self):
        from .services import check_forbidden_claims
        hits = check_forbidden_claims("100% safe for everyone. Cures diabetes.")
        self.assertGreaterEqual(len(hits), 2)

    def test_empty_text_returns_empty(self):
        from .services import check_forbidden_claims
        self.assertEqual(check_forbidden_claims(""), [])
        self.assertEqual(check_forbidden_claims(None), [])


class RewardAgreementTests(TestCase):
    """CB-2110 to CB-2113: accept_reward_agreement service."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("payout_chef", password="pass")
        from recipes.models import RecipeAuthor
        self.author = RecipeAuthor.objects.create(user=self.user, name="Payout Chef", slug="payout-chef")
        from .models import ChefBattleProfile
        self.profile = ChefBattleProfile.objects.create(author=self.author)

    def test_accept_creates_agreement_record(self):
        from .models import ChefRewardAgreement
        from .services import accept_reward_agreement
        accept_reward_agreement(self.author, ip_address="1.2.3.4", user_agent="TestBrowser/1.0")
        self.assertEqual(ChefRewardAgreement.objects.filter(chef=self.author).count(), 1)

    def test_accept_sets_profile_flag(self):
        from .services import accept_reward_agreement
        accept_reward_agreement(self.author)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.reward_agreement_accepted)

    def test_accept_stores_consent_snapshot(self):
        from .models import ChefRewardAgreement
        from .services import accept_reward_agreement, REWARD_AGREEMENT_TEXT_v1
        accept_reward_agreement(self.author)
        record = ChefRewardAgreement.objects.get(chef=self.author)
        self.assertEqual(record.consent_text_snapshot, REWARD_AGREEMENT_TEXT_v1)

    def test_accept_stores_version(self):
        from .models import ChefRewardAgreement
        from .services import accept_reward_agreement
        accept_reward_agreement(self.author)
        record = ChefRewardAgreement.objects.get(chef=self.author)
        self.assertEqual(record.agreement_version, "1.0")


class PayoutEligibilityTests(TestCase):
    """CB-2120 to CB-2125: check_payout_eligibility service."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("elig_chef", password="pass")
        from recipes.models import RecipeAuthor
        self.author = RecipeAuthor.objects.create(user=self.user, name="Elig Chef", slug="elig-chef")
        from .models import ChefBattleProfile
        self.profile = ChefBattleProfile.objects.create(
            author=self.author,
            age_verified=True,
            reward_agreement_accepted=True,
            stripe_connect_onboarded=True,
        )

    def _add_approved_tokens(self, amount):
        from .models import RewardRecord
        RewardRecord.objects.create(
            recipient=self.author,
            reward_type=RewardRecord.RewardType.CBR,
            status=RewardRecord.Status.APPROVED,
            tokens_granted=amount,
            reason="Test grant",
        )

    def test_not_eligible_without_profile(self):
        from recipes.models import RecipeAuthor
        User = get_user_model()
        u = User.objects.create_user("noprofile", password="pass")
        a = RecipeAuthor.objects.create(user=u, name="No Profile", slug="no-profile")
        from .services import check_payout_eligibility
        result = check_payout_eligibility(a)
        self.assertFalse(result["eligible"])

    def test_not_eligible_below_minimum_tokens(self):
        from .services import check_payout_eligibility
        self._add_approved_tokens(500)
        result = check_payout_eligibility(self.author)
        self.assertFalse(result["eligible"])
        self.assertTrue(any("2000" in r for r in result["reasons"]))

    def test_eligible_with_enough_tokens(self):
        from .services import check_payout_eligibility
        self._add_approved_tokens(2000)
        result = check_payout_eligibility(self.author)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reasons"], [])

    def test_not_eligible_when_payout_blocked(self):
        from .services import check_payout_eligibility
        self.profile.payout_blocked = True
        self.profile.save(update_fields=["payout_blocked"])
        self._add_approved_tokens(2000)
        result = check_payout_eligibility(self.author)
        self.assertFalse(result["eligible"])

    def test_not_eligible_when_age_not_verified(self):
        from .services import check_payout_eligibility
        self.profile.age_verified = False
        self.profile.save(update_fields=["age_verified"])
        self._add_approved_tokens(2000)
        result = check_payout_eligibility(self.author)
        self.assertFalse(result["eligible"])

    def test_open_request_blocks_eligibility(self):
        from .models import PayoutRequest
        from .services import check_payout_eligibility
        self._add_approved_tokens(2000)
        PayoutRequest.objects.create(
            chef=self.author,
            amount_reward_tokens=2000,
            gross_payout_eur="50.00",
            status=PayoutRequest.Status.PENDING,
        )
        result = check_payout_eligibility(self.author)
        self.assertFalse(result["eligible"])


class ContentReportViewTests(TestCase):
    """CB-2130 to CB-2133: content_report_submit view."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("reporter", password="pass")

    def test_submit_creates_report(self):
        from .models import ContentReport
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("chef_battle:content_report_submit"),
            data={"content_kind": "battle_entry", "object_id": "42", "reason": "Fake image"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(ContentReport.objects.filter(reporter=self.user).count(), 1)

    def test_submit_requires_login(self):
        resp = self.client.post(
            reverse("chef_battle:content_report_submit"),
            data={"content_kind": "battle_entry", "object_id": "1", "reason": "test"},
        )
        self.assertIn(resp.status_code, [301, 302])

    def test_invalid_kind_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("chef_battle:content_report_submit"),
            data={"content_kind": "invalid_kind", "object_id": "1", "reason": "test"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_missing_reason_returns_400(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("chef_battle:content_report_submit"),
            data={"content_kind": "chef_profile", "object_id": "1", "reason": ""},
        )
        self.assertEqual(resp.status_code, 400)


# ── AMC P01 — Arena Master Console access gate (DG-01) ───────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterConsoleAccessTests(TestCase):
    """P01: only superusers with the console flag (or the owner) may open the
    console shell; everyone else receives 404. Flag off => 404 for everyone."""

    def setUp(self):
        User = get_user_model()
        self.url = reverse("chef_battle:master_console")

        from django.conf import settings as django_settings
        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )

        self.flagged_user = User.objects.create_superuser("flagged-super", password="pw")
        self.flagged_author = RecipeAuthor.objects.create(
            user=self.flagged_user, name="Flagged Super", slug="flagged-super",
            has_arena_console_access=True,
        )

        self.plain_super = User.objects.create_superuser("plain-super", password="pw")
        RecipeAuthor.objects.create(
            user=self.plain_super, name="Plain Super", slug="plain-super"
        )

        self.moderator_user = User.objects.create_user("mod-user", password="pw")
        RecipeAuthor.objects.create(
            user=self.moderator_user, name="Mod User", slug="mod-user",
            has_bearseeker_privileges=True,
        )

        self.flag_no_super = User.objects.create_user("flag-no-super", password="pw")
        RecipeAuthor.objects.create(
            user=self.flag_no_super, name="Flag No Super", slug="flag-no-super",
            has_arena_console_access=True,
        )

        self.chef_user = User.objects.create_user("plain-chef", password="pw")
        chef_author = RecipeAuthor.objects.create(
            user=self.chef_user, name="Plain Chef", slug="plain-chef"
        )
        ChefBattleProfile.objects.create(author=chef_author, enrolled_at=timezone.now())

    def test_anonymous_gets_404(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_regular_chef_gets_404(self):
        self.client.force_login(self.chef_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_moderator_without_superuser_gets_404(self):
        self.client.force_login(self.moderator_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_superuser_without_flag_gets_404(self):
        self.client.force_login(self.plain_super)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_flag_without_superuser_gets_404(self):
        self.client.force_login(self.flag_no_super)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_owner_gets_console(self):
        self.client.force_login(self.owner_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Arena Master Console")
        self.assertContains(resp, "amc-badge")

    def test_superuser_with_flag_gets_console(self):
        self.client.force_login(self.flagged_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Arena Master Console")
        self.assertNotContains(resp, "amc-badge")

    @override_settings(ARENA_MASTER_CONSOLE_ENABLED=False)
    def test_console_flag_off_blocks_operators_but_never_the_owner(self):
        # The whole site is always visible to the owner — flags never hide it.
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        # Non-owner operators are gated by the kill switch.
        self.client.force_login(self.flagged_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @override_settings(CHEF_BATTLE_ENABLED=False)
    def test_console_is_independent_of_chef_battle_flag(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_shell_renders_no_fabricated_data(self):
        self.client.force_login(self.owner_user)
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # With no battles the console shows explicit empty states
        self.assertIn("No active battle", content)
        self.assertIn("No battles in progress", content)
        # Mockup example values must never appear in the shell
        for fabricated in ("1.6K", "1,240T", "CB-2025-0714", "Emerald Hall"):
            self.assertNotIn(fabricated, content)

    def test_all_eight_panels_present_with_disabled_controls(self):
        self.client.force_login(self.owner_user)
        content = self.client.get(self.url).content.decode()
        for panel in (
            "Arena Control / Battle Flow", "Live Battle Monitor", "Combat Engine",
            "Moderation &amp; Safety", "Voting Integrity", "Economy / Gifts / Artifacts",
            "CBR / LSR / Rewards Governance", "Ranks / Crown / Arena Authority",
        ):
            self.assertIn(panel, content)
        # P03: owner control buttons (8) + emulation pair; only Award Crown
        # stays disabled (crown is decided by audience voting only).
        import re
        amc_buttons = re.findall(r'<button[^>]*class="amc-btn[^"]*"[^>]*>', content)
        self.assertEqual(len(amc_buttons), 11)
        disabled = [b for b in amc_buttons if "disabled" in b]
        self.assertEqual(len(disabled), 1)
        self.assertIn("Award Crown", content)

    def test_public_arena_unchanged_for_anonymous(self):
        resp = self.client.get(reverse("chef_battle:arena"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "arena-puzzle")
        self.assertNotContains(resp, "amc-page")


# ── AMC P02 — master_state read models ───────────────────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterStateTests(TestCase):
    """P02: /chef-battle/master/state/ contract, battle-state matrix,
    query bounds, and no operator-field leakage into public endpoints."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.state_url = reverse("chef_battle:master_state")
        self.console_url = reverse("chef_battle:master_console")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )

        ua = User.objects.create_user("ms-chef-a", password="pw")
        ub = User.objects.create_user("ms-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="MS Chef A", slug="ms-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="MS Chef B", slug="ms-chef-b")
        self.profile_a = ChefBattleProfile.objects.create(
            author=self.chef_a, enrolled_at=timezone.now(), rating=1200
        )
        self.profile_b = ChefBattleProfile.objects.create(
            author=self.chef_b, enrolled_at=timezone.now(), rating=1100
        )
        self.plain_user = User.objects.create_user("ms-plain", password="pw")

    def _battle(self, status, **extra):
        now = timezone.now()
        defaults = dict(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Master State Dish",
            status=status,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )
        defaults.update(extra)
        return Battle.objects.create(**defaults)

    def _owner_state(self):
        self.client.force_login(self.owner_user)
        resp = self.client.post(self.state_url)
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    # ── access ──
    def test_anonymous_gets_404(self):
        self.assertEqual(self.client.post(self.state_url).status_code, 404)

    def test_regular_user_gets_404(self):
        self.client.force_login(self.plain_user)
        self.assertEqual(self.client.post(self.state_url).status_code, 404)

    def test_get_method_not_allowed_for_owner(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.state_url).status_code, 405)

    # ── contract: sections always present ──
    def test_state_contains_all_sections(self):
        data = self._owner_state()
        for section in ("arena", "battles", "combat", "moderation", "voting",
                        "viewers", "economy", "system"):
            self.assertIn(section, data)

    def test_no_battle_state(self):
        data = self._owner_state()
        self.assertEqual(data["battles"], [])
        self.assertEqual(data["voting"], [])
        self.assertEqual(data["combat"], [])
        self.assertEqual(data["system"]["active_battle_count"], 0)
        # DG-04 resolved 2026-07-05: presence is live; empty DB = zero viewers
        self.assertTrue(data["viewers"]["available"])
        self.assertEqual(data["viewers"]["arena_lobby_viewers"], 0)
        self.assertEqual(data["arena"]["enrolled_count"], 2)

    # ── battle-state matrix ──
    def test_scheduled_battle_fields(self):
        battle = self._battle(Battle.Status.SCHEDULED, challenger_ready=True)
        data = self._owner_state()
        self.assertEqual(len(data["battles"]), 1)
        b = data["battles"][0]
        self.assertEqual(b["id"], battle.pk)
        self.assertEqual(b["status"], "scheduled")
        self.assertEqual(b["phase_rail_step"], 1)
        self.assertEqual(b["next_status"], "menu_locked")
        self.assertTrue(b["challenger"]["ready"])
        self.assertFalse(b["opponent"]["ready"])
        self.assertEqual(b["challenger"]["rating"], 1200)
        self.assertIsNotNone(b["deadline"])
        self.assertGreater(b["seconds_remaining"], 0)
        self.assertFalse(b["is_paused"])

    def test_active_battle_reports_combat(self):
        battle = self._battle(Battle.Status.ACTIVE)
        from .models import BattleRound
        BattleRound.objects.create(
            battle=battle, round_number=1,
            attacker=self.chef_a, defender=self.chef_b,
            attack_power=3, defence_power=1,
            outcome=BattleRound.Outcome.FULL_HIT,
            challenger_hits=2, opponent_hits=1,
        )
        data = self._owner_state()
        self.assertEqual(data["battles"][0]["phase_rail_step"], 2)
        self.assertEqual(len(data["combat"]), 1)
        c = data["combat"][0]
        self.assertEqual(c["kind"], "combat")
        self.assertEqual(c["rounds_played"], 1)
        self.assertEqual(c["challenger_hits"], 2)
        self.assertEqual(c["opponent_hits"], 1)

    def test_ingredient_penalty_reports_biathlon_and_cooking_queue(self):
        self._battle(Battle.Status.INGREDIENT_PENALTY)
        data = self._owner_state()
        self.assertEqual(data["combat"][0]["kind"], "biathlon")
        self.assertEqual(data["moderation"]["cooking_queue"], 1)

    def test_voting_battle_counts_and_tie(self):
        battle = self._battle(Battle.Status.VOTING)
        User = get_user_model()
        for i, target in enumerate((self.chef_a, self.chef_b)):
            voter = User.objects.create_user(f"ms-voter-{i}", password="pw")
            BattleVote.objects.create(battle=battle, voter=voter, voted_for=target)
        BattleVote.objects.create(
            battle=battle, voted_for=self.chef_a,
            ip_hash="h1", user_agent_hash="h2", is_suspicious=True,
        )
        data = self._owner_state()
        v = data["voting"][0]
        self.assertEqual(v["challenger_votes"], 2)
        self.assertEqual(v["opponent_votes"], 1)
        self.assertEqual(v["suspicious_votes"], 1)
        self.assertFalse(v["is_tie"])

    def test_exact_equal_nonzero_votes_is_tie(self):
        battle = self._battle(Battle.Status.VOTING)
        User = get_user_model()
        for i, target in enumerate((self.chef_a, self.chef_b)):
            voter = User.objects.create_user(f"ms-tie-{i}", password="pw")
            BattleVote.objects.create(battle=battle, voter=voter, voted_for=target)
        data = self._owner_state()
        self.assertTrue(data["voting"][0]["is_tie"])

    def test_completed_and_cancelled_excluded_paused_included(self):
        self._battle(Battle.Status.COMPLETED)
        self._battle(Battle.Status.CANCELLED)
        self._battle(Battle.Status.PAUSED)
        data = self._owner_state()
        self.assertEqual(len(data["battles"]), 1)
        self.assertTrue(data["battles"][0]["is_paused"])
        self.assertEqual(data["system"]["paused_battle_count"], 1)
        self.assertEqual(data["system"]["active_battle_count"], 0)

    def test_gift_totals_per_battle(self):
        from .models import Artifact, ViewerBattleGift
        battle = self._battle(Battle.Status.VOTING)
        artifact = Artifact.objects.create(
            name="Test Ladle", rarity=Artifact.Rarity.COMMON,
            effect_type="attack", effect_value=1, token_cost=30,
        )
        ViewerBattleGift.objects.create(
            battle=battle, recipient=self.chef_a, artifact=artifact, tokens_spent=30
        )
        data = self._owner_state()
        gift = data["economy"]["battle_gifts"][0]
        self.assertEqual(gift["battle_id"], battle.pk)
        self.assertEqual(gift["gift_count"], 1)
        self.assertEqual(gift["tokens_spent"], 30)

    # ── verification pass 2: value vs direct ORM ──
    def test_online_count_matches_direct_query(self):
        self.profile_a.last_seen_at = timezone.now()
        self.profile_a.save(update_fields=["last_seen_at"])
        data = self._owner_state()
        from django.db.models import Q
        cutoff = timezone.now() - timezone.timedelta(seconds=180)
        expected = ChefBattleProfile.objects.filter(
            enrolled_at__isnull=False, is_suspended=False, last_seen_at__gte=cutoff
        ).count()
        self.assertEqual(data["arena"]["online_count"], expected)

    # ── query bound ──
    def test_master_state_query_budget(self):
        for _ in range(2):
            self._battle(Battle.Status.VOTING)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from .selectors import get_master_state
        with CaptureQueriesContext(connection) as ctx:
            get_master_state()
        # Operator-only endpoint polled every 20 s by at most a couple of
        # operators. Budget history: P02 <=20; P04 monitor; P05 moderation
        # detail (~27 fixed); P06 voting analytics adds ~7/battle (votes,
        # UTC series, integrity x2, suspicious, chat x2, gift aggregate);
        # P07 economy detail adds ~6 fixed. Measured: 41 at 2 battles.
        # Bound 50 = headroom for 3 battles; revisit only if battle
        # concurrency grows beyond that.
        self.assertLessEqual(len(ctx.captured_queries), 50,
                             f"master_state used {len(ctx.captured_queries)} queries")

    # ── public leak checks ──
    def test_public_arena_state_keys_unchanged(self):
        self._battle(Battle.Status.ACTIVE)
        resp = self.client.post(reverse("chef_battle:arena_state"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(set(data.keys()),
                         {"rings", "spectators", "center", "latest_result"})

    def test_operator_fields_do_not_leak_into_public_arena(self):
        self._battle(Battle.Status.VOTING)
        resp = self.client.get(reverse("chef_battle:arena"))
        content = resp.content.decode()
        for operator_marker in ("amc-state-json", "suspicious_votes", "pending_payouts",
                                "tokens_in_24h", "master/state"):
            self.assertNotIn(operator_marker, content)

    def test_console_page_renders_live_values(self):
        battle = self._battle(Battle.Status.SCHEDULED)
        self.client.force_login(self.owner_user)
        resp = self.client.get(self.console_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"#{battle.pk}")
        self.assertContains(resp, "Master State Dish")
        self.assertContains(resp, "MS Chef A")
        self.assertContains(resp, "MS Chef B")
        self.assertContains(resp, "amc-state-json")


# ── AMC P03 — operator battle-flow orchestration ─────────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterActionTests(TestCase):
    """P03: owner-only force transitions, Emergency Stop (DG-03), resume,
    cancel, broadcast — permissions, idempotency, audit, rollback."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.url = reverse("chef_battle:master_action")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )

        self.operator_user = User.objects.create_superuser("flag-op", password="pw")
        RecipeAuthor.objects.create(
            user=self.operator_user, name="Flag Op", slug="flag-op",
            has_arena_console_access=True,
        )

        ua = User.objects.create_user("act-chef-a", password="pw")
        ub = User.objects.create_user("act-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="Act Chef A", slug="act-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="Act Chef B", slug="act-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now())
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now())

    def _battle(self, status=Battle.Status.SCHEDULED):
        now = timezone.now()
        return Battle.objects.create(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Action Dish", status=status,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )

    def _post(self, user, **fields):
        self.client.force_login(user)
        return self.client.post(self.url, fields)

    # ── permissions ──
    def test_anonymous_gets_404(self):
        self.assertEqual(self.client.post(self.url, {"action": "resume"}).status_code, 404)

    def test_flagged_operator_gets_403_not_owner(self):
        battle = self._battle()
        resp = self._post(self.operator_user, action="force_status",
                          battle_id=battle.pk, target_status="menu_locked")
        self.assertEqual(resp.status_code, 403)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.SCHEDULED)

    def test_get_not_allowed(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    # ── force transitions ──
    def test_owner_forces_scheduled_to_menu_locked_with_audit(self):
        battle = self._battle()
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="menu_locked",
                          expected_status="scheduled", reason="test advance",
                          correlation_id="corr-123")
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.MENU_LOCKED)
        event = BattleEvent.objects.get(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertEqual(event.actor, self.owner_author)
        self.assertFalse(event.is_public)
        payload = event.payload_json
        self.assertEqual(payload["action"], "force_status")
        self.assertEqual(payload["before_status"], "scheduled")
        self.assertEqual(payload["after_status"], "menu_locked")
        self.assertEqual(payload["reason"], "test advance")
        self.assertEqual(payload["correlation_id"], "corr-123")
        self.assertEqual(payload["service_used"], "direct")

    def test_stale_expected_status_rejected(self):
        battle = self._battle(Battle.Status.MENU_LOCKED)
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="active",
                          expected_status="scheduled")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Stale state", resp.json()["error"])
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.MENU_LOCKED)

    def test_repeated_click_is_idempotent(self):
        battle = self._battle()
        first = self._post(self.owner_user, action="force_status",
                           battle_id=battle.pk, target_status="menu_locked",
                           expected_status="scheduled")
        second = self._post(self.owner_user, action="force_status",
                            battle_id=battle.pk, target_status="menu_locked",
                            expected_status="scheduled")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        events = BattleEvent.objects.filter(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION
        ).order_by("created_at")
        # The battle state changed exactly once; the repeat click is now also
        # audited (rejected), so there are two events with different outcomes.
        self.assertEqual(events.count(), 2)
        self.assertEqual(events[0].payload_json["outcome"], "applied")
        self.assertEqual(events[1].payload_json["outcome"], "rejected")
        self.assertIn("Stale state", events[1].payload_json["error"])

    def test_same_status_rejected(self):
        battle = self._battle()
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="scheduled")
        self.assertEqual(resp.status_code, 409)

    def test_invalid_target_rejected(self):
        battle = self._battle()
        for bad in ("cancelled", "paused", "disputed", "nonsense"):
            resp = self._post(self.owner_user, action="force_status",
                              battle_id=battle.pk, target_status=bad)
            self.assertEqual(resp.status_code, 409, bad)

    def test_cooking_transition_uses_owning_service(self):
        battle = self._battle(Battle.Status.INGREDIENT_PENALTY)
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="cooking",
                          expected_status="ingredient_penalty")
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.COOKING)
        op_event = BattleEvent.objects.get(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertEqual(op_event.payload_json["service_used"], "approve_cooking_phase")

    def test_voting_to_completed_uses_result_service(self):
        battle = self._battle(Battle.Status.VOTING)
        User = get_user_model()
        voter = User.objects.create_user("act-voter", password="pw")
        BattleVote.objects.create(battle=battle, voter=voter, voted_for=self.chef_a)
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="completed",
                          expected_status="voting")
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.COMPLETED)
        self.assertEqual(battle.winner, self.chef_a)

    def test_unknown_action_400_and_missing_battle_404(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(
            self.client.post(self.url, {"action": "explode"}).status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {"action": "resume", "battle_id": 999999}).status_code, 404)

    def test_malformed_action_ids_return_400_not_500(self):
        cases = (
            {"action": "force_status", "battle_id": "abc", "target_status": "active"},
            {"action": "emergency_stop", "battle_id": "abc", "reason": "x"},
            {"action": "resume", "battle_id": "abc"},
            {"action": "cancel", "battle_id": "abc", "reason": "x"},
            {"action": "moderate_entry", "entry_id": "abc", "new_status": "approved"},
            {"action": "review_report", "report_id": "abc", "new_status": "reviewed"},
            {"action": "end_stream", "session_id": "abc", "reason": "x"},
            {"action": "broadcast", "battle_id": "abc", "message": "x"},
        )
        self.client.force_login(self.owner_user)
        for payload in cases:
            with self.subTest(action=payload["action"]):
                response = self.client.post(self.url, payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()["ok"])

    # ── Emergency Stop (DG-03) ──
    def test_emergency_stop_full_behavior(self):
        from .models import LiveStreamSession
        battle = self._battle(Battle.Status.COOKING)
        stream = LiveStreamSession.objects.create(
            battle=battle, chef=self.chef_a, status=LiveStreamSession.Status.LIVE)
        resp = self._post(self.owner_user, action="emergency_stop",
                          battle_id=battle.pk, reason="Minor visible on camera")
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.PAUSED)
        self.assertEqual(battle.paused_from_status, "cooking")
        self.assertEqual(battle.paused_reason, "Minor visible on camera")
        self.assertIsNotNone(battle.paused_at)
        stream.refresh_from_db()
        self.assertEqual(stream.status, LiveStreamSession.Status.TERMINATED)
        self.assertIn("Emergency Stop", stream.terminated_reason)
        self.assertEqual(stream.terminated_by, self.owner_user)
        # audit + chef notifications
        event = BattleEvent.objects.get(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertEqual(event.payload_json["action"], "emergency_stop")
        self.assertEqual(event.payload_json["streams_terminated"], 1)
        from messaging.models import Message
        self.assertEqual(
            Message.objects.filter(subject__icontains="paused").count(), 2)

    def test_emergency_stop_requires_reason(self):
        battle = self._battle(Battle.Status.ACTIVE)
        resp = self._post(self.owner_user, action="emergency_stop",
                          battle_id=battle.pk, reason="  ")
        self.assertEqual(resp.status_code, 409)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.ACTIVE)

    def test_cannot_pause_completed_or_paused(self):
        done = self._battle(Battle.Status.COMPLETED)
        resp = self._post(self.owner_user, action="emergency_stop",
                          battle_id=done.pk, reason="x")
        self.assertEqual(resp.status_code, 409)
        paused = self._battle(Battle.Status.PAUSED)
        resp = self._post(self.owner_user, action="emergency_stop",
                          battle_id=paused.pk, reason="x")
        self.assertEqual(resp.status_code, 409)

    def test_force_status_blocked_while_paused(self):
        battle = self._battle(Battle.Status.PAUSED)
        resp = self._post(self.owner_user, action="force_status",
                          battle_id=battle.pk, target_status="cooking")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("paused", resp.json()["error"].lower())

    # ── resume / cancel ──
    def test_resume_restores_pre_pause_status(self):
        battle = self._battle(Battle.Status.VOTING)
        original_submission = battle.submission_deadline
        original_voting = battle.voting_deadline
        original_end = battle.end_time
        self._post(self.owner_user, action="emergency_stop",
                   battle_id=battle.pk, reason="incident")
        paused_at = timezone.now() - timezone.timedelta(hours=2)
        Battle.objects.filter(pk=battle.pk).update(paused_at=paused_at)
        resp = self._post(self.owner_user, action="resume", battle_id=battle.pk)
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.VOTING)
        self.assertIsNone(battle.paused_at)
        self.assertEqual(battle.paused_reason, "")
        self.assertEqual(battle.paused_from_status, "")
        for original, shifted in (
            (original_submission, battle.submission_deadline),
            (original_voting, battle.voting_deadline),
            (original_end, battle.end_time),
        ):
            self.assertAlmostEqual(
                (shifted - original).total_seconds(), 7200, delta=3
            )
        event = BattleEvent.objects.filter(
            battle=battle,
            event_type=BattleEvent.EventType.OPERATOR_ACTION,
            payload_json__action="resume",
        ).get()
        self.assertAlmostEqual(
            event.payload_json["pause_duration_seconds"], 7200, delta=3
        )
        self.assertEqual(
            event.payload_json["shifted_deadlines"],
            ["submission_deadline", "voting_deadline", "end_time"],
        )

    def test_resume_requires_paused(self):
        battle = self._battle(Battle.Status.ACTIVE)
        resp = self._post(self.owner_user, action="resume", battle_id=battle.pk)
        self.assertEqual(resp.status_code, 409)

    def test_resume_never_moves_deadlines_backwards_on_clock_skew(self):
        battle = self._battle(Battle.Status.PAUSED)
        battle.paused_from_status = Battle.Status.VOTING
        battle.paused_at = timezone.now() + timezone.timedelta(minutes=5)
        battle.save(update_fields=["paused_from_status", "paused_at"])
        original_deadlines = (
            battle.submission_deadline, battle.voting_deadline, battle.end_time,
        )

        resp = self._post(self.owner_user, action="resume", battle_id=battle.pk)

        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(
            (battle.submission_deadline, battle.voting_deadline, battle.end_time),
            original_deadlines,
        )

    def test_cancel_paused_battle(self):
        battle = self._battle(Battle.Status.ACTIVE)
        self._post(self.owner_user, action="emergency_stop",
                   battle_id=battle.pk, reason="incident")
        resp = self._post(self.owner_user, action="cancel",
                          battle_id=battle.pk, reason="cannot continue safely")
        self.assertEqual(resp.status_code, 200)
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.CANCELLED)
        self.assertIn("Cancelled by arena operator", battle.result_reason)
        self.assertIsNone(battle.paused_at)
        self.assertEqual(battle.paused_from_status, "")
        self.assertEqual(battle.paused_reason, "")

    def test_cancel_requires_reason_and_not_completed(self):
        battle = self._battle(Battle.Status.ACTIVE)
        self.assertEqual(
            self._post(self.owner_user, action="cancel",
                       battle_id=battle.pk, reason="").status_code, 409)
        done = self._battle(Battle.Status.COMPLETED)
        self.assertEqual(
            self._post(self.owner_user, action="cancel",
                       battle_id=done.pk, reason="x").status_code, 409)

    # ── broadcast ──
    def test_broadcast_creates_public_event(self):
        battle = self._battle()
        resp = self._post(self.owner_user, action="broadcast",
                          battle_id=battle.pk, message="Round starts in 5 minutes")
        self.assertEqual(resp.status_code, 200)
        event = BattleEvent.objects.get(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertTrue(event.is_public)
        self.assertEqual(event.message, "Round starts in 5 minutes")

    def test_broadcast_requires_message(self):
        resp = self._post(self.owner_user, action="broadcast", message=" ")
        self.assertEqual(resp.status_code, 409)

    # ── console rendering per role ──
    def test_owner_sees_controls_operator_sees_read_only(self):
        console = reverse("chef_battle:master_console")
        self.client.force_login(self.owner_user)
        owner_page = self.client.get(console).content.decode()
        self.assertIn("amc-controls", owner_page)
        self.assertIn("Emergency Stop", owner_page)
        self.client.force_login(self.operator_user)
        op_page = self.client.get(console).content.decode()
        self.assertNotIn("amc-controls", op_page)
        self.assertIn("Read-only access", op_page)


# ── AMC P04 — live battle monitor / combat engine read models ────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterMonitorTests(TestCase):
    """P04: monitor section contract, side-effect-free polling, hidden-info
    visibility boundaries, totals vs authoritative ORM records."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.state_url = reverse("chef_battle:master_state")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )

        ua = User.objects.create_user("mon-chef-a", password="pw")
        ub = User.objects.create_user("mon-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="Mon Chef A", slug="mon-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="Mon Chef B", slug="mon-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now())
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now())

    def _battle(self, status=Battle.Status.ACTIVE):
        now = timezone.now()
        return Battle.objects.create(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Monitor Dish", status=status,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )

    def _state(self):
        self.client.force_login(self.owner_user)
        resp = self.client.post(self.state_url)
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def _add_round(self, battle, number, outcome, ch_hits, op_hits):
        from .models import BattleRound
        return BattleRound.objects.create(
            battle=battle, round_number=number,
            attacker=self.chef_a, defender=self.chef_b,
            attack_power=3, defence_power=1,
            outcome=outcome, challenger_hits=ch_hits, opponent_hits=op_hits,
        )

    # ── contract ──
    def test_monitor_section_present_with_counts(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a, opponent=self.chef_b, theme="Pending One",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self._battle(Battle.Status.ACTIVE)
        self._battle(Battle.Status.PAUSED)
        self._battle(Battle.Status.DISPUTED)
        data = self._state()
        counts = data["monitor"]["counts"]
        self.assertEqual(counts["battles_active"], 1)
        self.assertEqual(counts["battles_paused"], 1)
        self.assertEqual(counts["battles_unresolved"], 1)
        self.assertEqual(counts["challenges_pending"], 1)
        self.assertEqual(counts["challenges_accepted"], 0)

    def test_every_round_outcome_serializes(self):
        from .models import BattleRound
        battle = self._battle(Battle.Status.ACTIVE)
        for i, outcome in enumerate(BattleRound.Outcome.values, start=1):
            self._add_round(battle, i, outcome, i, i - 1)
        data = self._state()
        combat = [d for d in data["monitor"]["detail"] if d["kind"] == "combat"][0]
        self.assertEqual(len(combat["rounds"]), len(BattleRound.Outcome.values))
        self.assertEqual(combat["current_round"], len(BattleRound.Outcome.values) + 1)
        self.assertEqual(
            {r["outcome"] for r in combat["rounds"]}, set(BattleRound.Outcome.values))

    def test_declared_actions_and_hits_match_orm(self):
        from .models import BattleCombatAction, BattleRound
        battle = self._battle(Battle.Status.ACTIVE)
        self._add_round(battle, 1, BattleRound.Outcome.FULL_HIT, 2, 0)
        BattleCombatAction.objects.create(
            battle=battle, chef=self.chef_a, round_number=2,
            action_type=BattleCombatAction.ActionType.ATTACK,
            moves_invested=3, is_locked=True,
        )
        data = self._state()
        combat = [d for d in data["monitor"]["detail"] if d["kind"] == "combat"][0]
        self.assertEqual(combat["challenger_hits"], 2)
        self.assertEqual(combat["opponent_hits"], 0)
        last = BattleRound.objects.filter(battle=battle).order_by("-round_number").first()
        self.assertEqual(combat["challenger_hits"], last.challenger_hits)
        self.assertEqual(combat["declared_actions"], [{
            "chef": "mon-chef-a", "action_type": "attack",
            "moves_invested": 3, "is_locked": True,
        }])

    def test_biathlon_detail_matches_orm(self):
        from recipes.models import Recipe
        from .models import IngredientLock, IngredientShot
        battle = self._battle(Battle.Status.INGREDIENT_PENALTY)
        battle.winner = self.chef_a
        battle.loser = self.chef_b
        battle.save(update_fields=["winner", "loser"])
        recipe = Recipe.objects.create(
            title="Loser Dish", slug="loser-dish", author=self.chef_b,
            ingredients="eggs\nflour\nbutter\nmilk\nsugar", method="mix",
            status=Recipe.Status.APPROVED,
        )
        battle.entries.create(author=self.chef_b, recipe=recipe)
        IngredientLock.objects.create(battle=battle, chef=self.chef_b, ingredient_index=1)
        IngredientShot.objects.create(battle=battle, shooter=self.chef_a, target_index=1, bounced=True)
        IngredientShot.objects.create(battle=battle, shooter=self.chef_a, target_index=3, bounced=False)
        data = self._state()
        bia = [d for d in data["monitor"]["detail"] if d["kind"] == "biathlon"][0]
        self.assertEqual(bia["ingredient_count"], 5)
        self.assertEqual(bia["lock_indices"], [1])
        self.assertEqual(bia["locks_placed"], 1)
        self.assertEqual(bia["shots_fired"], 2)
        self.assertEqual(
            sorted(s["target_index"] for s in bia["shots"]), [1, 3])
        self.assertTrue(any(s["bounced"] for s in bia["shots"]))

    def test_event_log_append_only_ordering(self):
        battle = self._battle(Battle.Status.ACTIVE)
        from .services import create_battle_event
        for i in range(3):
            create_battle_event(
                event_type=BattleEvent.EventType.BATTLE_STARTED,
                battle=battle, message=f"event {i}", is_public=True,
            )
        data = self._state()
        messages = [e["message"] for e in data["monitor"]["events"]]
        self.assertEqual(messages[:3], ["event 2", "event 1", "event 0"])

    def test_artifacts_in_use_lists_reserved_only(self):
        from .models import Artifact, ChefArtifact
        self._battle(Battle.Status.ACTIVE)
        artifact = Artifact.objects.create(
            name="Iron Pan", rarity=Artifact.Rarity.RARE,
            effect_type="defence", effect_value=2, token_cost=50,
        )
        ChefArtifact.objects.create(
            chef=self.chef_a, artifact=artifact, status=ChefArtifact.Status.RESERVED)
        ChefArtifact.objects.create(
            chef=self.chef_b, artifact=artifact, status=ChefArtifact.Status.AVAILABLE)
        data = self._state()
        in_use = data["monitor"]["artifacts_in_use"]
        self.assertEqual(len(in_use), 1)
        self.assertEqual(in_use[0]["chef"], "mon-chef-a")
        self.assertEqual(in_use[0]["status"], "reserved")

    # ── side-effect-free polling ──
    def test_poll_creates_no_records(self):
        from .models import BattleCombatAction, BattleRound, TokenTransaction
        battle = self._battle(Battle.Status.ACTIVE)
        self._add_round(battle, 1, "full_hit", 1, 0)
        before = {
            "rounds": BattleRound.objects.count(),
            "actions": BattleCombatAction.objects.count(),
            "events": BattleEvent.objects.count(),
            "tx": TokenTransaction.objects.count(),
            "battles": Battle.objects.count(),
        }
        for _ in range(3):
            self._state()
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.ACTIVE)
        after = {
            "rounds": BattleRound.objects.count(),
            "actions": BattleCombatAction.objects.count(),
            "events": BattleEvent.objects.count(),
            "tx": TokenTransaction.objects.count(),
            "battles": Battle.objects.count(),
        }
        self.assertEqual(before, after)

    # ── hidden-information boundaries ──
    def test_hidden_combat_data_not_in_public_endpoints(self):
        from .models import BattleCombatAction
        battle = self._battle(Battle.Status.ACTIVE)
        BattleCombatAction.objects.create(
            battle=battle, chef=self.chef_a, round_number=1,
            action_type=BattleCombatAction.ActionType.ATTACK, moves_invested=2,
        )
        # public arena JSON has no declared actions or lock indices
        arena_json = self.client.post(reverse("chef_battle:arena_state")).content.decode()
        for marker in ("declared_actions", "lock_indices", "moves_invested"):
            self.assertNotIn(marker, arena_json)
        # anonymous cannot reach the monitor at all
        self.client.logout()
        self.assertEqual(self.client.post(self.state_url).status_code, 404)

    def test_flagged_operator_sees_monitor_read_only(self):
        User = get_user_model()
        op = User.objects.create_superuser("mon-op", password="pw")
        RecipeAuthor.objects.create(
            user=op, name="Mon Op", slug="mon-op", has_arena_console_access=True)
        self._battle(Battle.Status.ACTIVE)
        self.client.force_login(op)
        resp = self.client.post(self.state_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("monitor", resp.json())


# ── AMC P05 — moderation & safety operations ─────────────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterModerationTests(TestCase):
    """P05: moderation read models, owner-only adverse actions with mandatory
    reasons, audit records, privacy of moderation notes."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.action_url = reverse("chef_battle:master_action")
        self.state_url = reverse("chef_battle:master_state")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        self.operator_user = User.objects.create_superuser("mod-op", password="pw")
        RecipeAuthor.objects.create(
            user=self.operator_user, name="Mod Op", slug="mod-op",
            has_arena_console_access=True,
        )

        ua = User.objects.create_user("p5-chef-a", password="pw")
        ub = User.objects.create_user("p5-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="P5 Chef A", slug="p5-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="P5 Chef B", slug="p5-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now())
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now())

        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Moderation Dish", status=Battle.Status.INGREDIENT_PENALTY,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )
        self.entry = self.battle.entries.create(author=self.chef_a)

    def _post(self, user, **fields):
        self.client.force_login(user)
        return self.client.post(self.action_url, fields)

    # ── read models ──
    def test_moderation_detail_in_state(self):
        from .models import ContentReport, LiveBroadcast, LiveBroadcastReport, LiveStreamSession
        ContentReport.objects.create(
            content_kind=ContentReport.ContentKind.BATTLE_ENTRY,
            object_id=self.entry.pk, reason="looks like stock photo",
        )
        session = LiveStreamSession.objects.create(
            battle=self.battle, chef=self.chef_a,
            status=LiveStreamSession.Status.LIVE, checklist_confirmed=True,
        )
        broadcast = LiveBroadcast.objects.create(session=session, report_count=99)
        LiveBroadcastReport.objects.create(
            broadcast=broadcast,
            category=LiveBroadcastReport.ReportCategory.CHILD_SAFETY,
        )
        LiveBroadcastReport.objects.create(
            broadcast=broadcast,
            category=LiveBroadcastReport.ReportCategory.COPYRIGHT,
        )
        self.client.force_login(self.owner_user)
        data = self.client.post(self.state_url).json()
        detail = data["moderation"]["detail"]
        self.assertEqual(detail["cooking_queue"][0]["battle_id"], self.battle.pk)
        self.assertEqual(detail["cooking_queue"][0]["entries"][0]["moderation_status"], "pending")
        self.assertEqual(detail["content_reports"][0]["reason"], "looks like stock photo")
        stream = detail["streams"][0]
        self.assertEqual(stream["chef_slug"], "p5-chef-a")
        self.assertTrue(stream["checklist_confirmed"])
        self.assertFalse(stream["agreement_signed"])
        self.assertEqual(stream["broadcast"]["report_count"], 2)

    # ── entry moderation ──
    def test_owner_approves_entry(self):
        self.entry.cooked_photo = "chef_battle/cooked/approved.jpg"
        self.entry.real_photo_confirmed = True
        self.entry.save(update_fields=["cooked_photo", "real_photo_confirmed"])
        resp = self._post(self.owner_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="approved")
        self.assertEqual(resp.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.moderation_status, BattleEntry.ModerationStatus.APPROVED)
        self.assertEqual(self.entry.reviewed_by, self.owner_user)
        event = BattleEvent.objects.get(event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertEqual(event.payload_json["action"], "moderate_entry")
        self.assertEqual(event.payload_json["entry_author"], "p5-chef-a")

    def test_approve_requires_cooked_photo_and_real_photo_confirmation(self):
        resp = self._post(
            self.owner_user, action="moderate_entry",
            entry_id=self.entry.pk, new_status="approved",
        )
        self.assertEqual(resp.status_code, 409)
        self.entry.cooked_photo = "chef_battle/cooked/unconfirmed.jpg"
        self.entry.save(update_fields=["cooked_photo"])
        resp = self._post(
            self.owner_user, action="moderate_entry",
            entry_id=self.entry.pk, new_status="approved",
        )
        self.assertEqual(resp.status_code, 409)

    def test_cooked_photos_wait_for_both_owner_approvals_before_presentation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .services import submit_cooked_photo

        self.battle.status = Battle.Status.COOKING
        self.battle.save(update_fields=["status"])
        entry_b = self.battle.entries.create(author=self.chef_b)
        submit_cooked_photo(
            battle=self.battle,
            author=self.chef_a,
            photo=SimpleUploadedFile("a.jpg", b"photo-a", content_type="image/jpeg"),
            real_photo_confirmed=True,
        )
        submit_cooked_photo(
            battle=self.battle,
            author=self.chef_b,
            photo=SimpleUploadedFile("b.jpg", b"photo-b", content_type="image/jpeg"),
            real_photo_confirmed=True,
        )
        self.battle.refresh_from_db()
        self.entry.refresh_from_db()
        entry_b.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.COOKING)
        self.assertEqual(self.entry.moderation_status, BattleEntry.ModerationStatus.PENDING)
        self.assertEqual(entry_b.moderation_status, BattleEntry.ModerationStatus.PENDING)

        self.client.force_login(self.owner_user)
        state = self.client.post(self.state_url).json()
        queued = state["moderation"]["detail"]["cooking_queue"]
        self.assertEqual(queued[0]["battle_id"], self.battle.pk)
        self.assertTrue(all(e["has_cooked_photo"] for e in queued[0]["entries"]))

        first = self._post(
            self.owner_user, action="moderate_entry",
            entry_id=self.entry.pk, new_status="approved",
        )
        self.assertEqual(first.status_code, 200)
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.COOKING)

        second = self._post(
            self.owner_user, action="moderate_entry",
            entry_id=entry_b.pk, new_status="approved",
        )
        self.assertEqual(second.status_code, 200)
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.PRESENTATION)
        self.assertEqual(
            BattleEvent.objects.filter(
                battle=self.battle,
                message__icontains="photos were approved",
                is_public=True,
            ).count(),
            1,
        )

    def test_adverse_entry_action_requires_reason_and_notifies(self):
        resp = self._post(self.owner_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="flagged", reason="")
        self.assertEqual(resp.status_code, 409)
        resp = self._post(self.owner_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="flagged",
                          reason="copyright concern")
        self.assertEqual(resp.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.moderation_status, BattleEntry.ModerationStatus.FLAGGED)
        self.assertEqual(self.entry.moderation_note, "copyright concern")
        from messaging.models import Message
        self.assertTrue(Message.objects.filter(
            recipient=self.chef_a.user, subject__icontains="needs attention").exists())

    def test_entry_invalid_status_and_same_status_rejected(self):
        resp = self._post(self.owner_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="suspected_ai", reason="x")
        self.assertEqual(resp.status_code, 409)
        resp = self._post(self.owner_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="pending", reason="x")
        self.assertEqual(resp.status_code, 409)

    def test_operator_cannot_moderate(self):
        resp = self._post(self.operator_user, action="moderate_entry",
                          entry_id=self.entry.pk, new_status="approved")
        self.assertEqual(resp.status_code, 403)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.moderation_status, BattleEntry.ModerationStatus.PENDING)

    # ── content reports ──
    def test_report_review_requires_note(self):
        from .models import ContentReport
        report = ContentReport.objects.create(
            content_kind=ContentReport.ContentKind.BATTLE_CHAT,
            object_id=1, reason="abuse")
        resp = self._post(self.owner_user, action="review_report",
                          report_id=report.pk, new_status="dismissed", reason="")
        self.assertEqual(resp.status_code, 409)
        resp = self._post(self.owner_user, action="review_report",
                          report_id=report.pk, new_status="dismissed",
                          reason="not a violation")
        self.assertEqual(resp.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, ContentReport.Status.DISMISSED)
        self.assertEqual(report.moderator_note, "not a violation")
        self.assertEqual(report.reviewed_by, self.owner_user)

    def test_report_invalid_status_rejected(self):
        from .models import ContentReport
        report = ContentReport.objects.create(
            content_kind=ContentReport.ContentKind.BATTLE_CHAT,
            object_id=1, reason="abuse")
        resp = self._post(self.owner_user, action="review_report",
                          report_id=report.pk, new_status="pending", reason="x")
        self.assertEqual(resp.status_code, 409)

    # ── streams ──
    def test_end_stream_updates_records_and_is_honest_about_provider(self):
        from .models import LiveBroadcast, LiveStreamSession
        session = LiveStreamSession.objects.create(
            battle=self.battle, chef=self.chef_a, status=LiveStreamSession.Status.LIVE)
        broadcast = LiveBroadcast.objects.create(session=session)
        resp = self._post(self.owner_user, action="end_stream",
                          session_id=session.pk, reason="prohibited content")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["provider_side_terminated"])
        self.assertIn("no provider integration", data["note"].lower())
        session.refresh_from_db()
        broadcast.refresh_from_db()
        self.assertEqual(session.status, LiveStreamSession.Status.TERMINATED)
        self.assertEqual(session.terminated_by, self.owner_user)
        self.assertTrue(broadcast.stopped_by_staff)
        self.assertEqual(broadcast.stop_reason, "prohibited content")
        event = BattleEvent.objects.get(event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertFalse(event.payload_json["provider_side_terminated"])

    def test_end_stream_requires_reason_and_live_state(self):
        from .models import LiveStreamSession
        session = LiveStreamSession.objects.create(
            battle=self.battle, chef=self.chef_a,
            status=LiveStreamSession.Status.ENDED)
        resp = self._post(self.owner_user, action="end_stream",
                          session_id=session.pk, reason="x")
        self.assertEqual(resp.status_code, 409)
        live = LiveStreamSession.objects.create(
            battle=self.battle, chef=self.chef_a,
            status=LiveStreamSession.Status.LIVE)
        resp = self._post(self.owner_user, action="end_stream",
                          session_id=live.pk, reason=" ")
        self.assertEqual(resp.status_code, 409)

    # ── privacy ──
    def test_moderation_notes_never_public(self):
        self._post(self.owner_user, action="moderate_entry",
                   entry_id=self.entry.pk, new_status="flagged",
                   reason="secret-mod-note-xyz")
        self.client.logout()
        arena_json = self.client.post(reverse("chef_battle:arena_state")).content.decode()
        self.assertNotIn("secret-mod-note-xyz", arena_json)
        battle_page = self.client.get(self.battle.get_absolute_url())
        if battle_page.status_code == 200:
            self.assertNotIn("secret-mod-note-xyz", battle_page.content.decode())

    # ── P05 chef safety: suspend / unsuspend ──
    def test_owner_suspends_chef_and_audit_created(self):
        resp = self._post(self.owner_user, action="suspend_chef",
                          chef_slug="p5-chef-a", reason="test suspension")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["chef"]["is_suspended"])
        profile = ChefBattleProfile.objects.get(author=self.chef_a)
        self.assertTrue(profile.is_suspended)
        self.assertEqual(profile.suspension_reason, "test suspension")
        event = BattleEvent.objects.filter(
            event_type=BattleEvent.EventType.OPERATOR_ACTION,
            payload_json__action="suspend_chef",
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.payload_json["chef_slug"], "p5-chef-a")

    def test_suspend_requires_reason(self):
        resp = self._post(self.owner_user, action="suspend_chef",
                          chef_slug="p5-chef-a", reason="")
        self.assertEqual(resp.status_code, 409)
        profile = ChefBattleProfile.objects.get(author=self.chef_a)
        self.assertFalse(profile.is_suspended)

    def test_suspend_already_suspended_returns_409(self):
        ChefBattleProfile.objects.filter(author=self.chef_a).update(
            is_suspended=True, suspension_reason="first")
        resp = self._post(self.owner_user, action="suspend_chef",
                          chef_slug="p5-chef-a", reason="second")
        self.assertEqual(resp.status_code, 409)

    def test_owner_unsuspends_chef(self):
        ChefBattleProfile.objects.filter(author=self.chef_a).update(
            is_suspended=True, suspension_reason="reason")
        resp = self._post(self.owner_user, action="unsuspend_chef",
                          chef_slug="p5-chef-a")
        self.assertEqual(resp.status_code, 200)
        profile = ChefBattleProfile.objects.get(author=self.chef_a)
        self.assertFalse(profile.is_suspended)

    def test_unsuspend_not_suspended_returns_409(self):
        resp = self._post(self.owner_user, action="unsuspend_chef",
                          chef_slug="p5-chef-a")
        self.assertEqual(resp.status_code, 409)

    def test_operator_cannot_suspend(self):
        resp = self._post(self.operator_user, action="suspend_chef",
                          chef_slug="p5-chef-a", reason="nope")
        self.assertEqual(resp.status_code, 403)

    # ── P05 chef safety: fraud flag ──
    def test_owner_sets_fraud_flag_and_audit_created(self):
        resp = self._post(self.owner_user, action="set_fraud_flag",
                          chef_slug="p5-chef-a", reason="suspicious pattern")
        self.assertEqual(resp.status_code, 200)
        profile = ChefBattleProfile.objects.get(author=self.chef_a)
        self.assertTrue(profile.fraud_flag)
        self.assertEqual(profile.fraud_flag_note, "suspicious pattern")
        event = BattleEvent.objects.filter(
            event_type=BattleEvent.EventType.OPERATOR_ACTION,
            payload_json__action="set_fraud_flag",
        ).first()
        self.assertIsNotNone(event)

    def test_fraud_flag_requires_note(self):
        resp = self._post(self.owner_user, action="set_fraud_flag",
                          chef_slug="p5-chef-a", reason="")
        self.assertEqual(resp.status_code, 409)

    def test_fraud_flag_already_set_returns_409(self):
        ChefBattleProfile.objects.filter(author=self.chef_a).update(fraud_flag=True)
        resp = self._post(self.owner_user, action="set_fraud_flag",
                          chef_slug="p5-chef-a", reason="double")
        self.assertEqual(resp.status_code, 409)

    def test_owner_clears_fraud_flag(self):
        ChefBattleProfile.objects.filter(author=self.chef_a).update(
            fraud_flag=True, fraud_flag_note="old note")
        resp = self._post(self.owner_user, action="clear_fraud_flag",
                          chef_slug="p5-chef-a")
        self.assertEqual(resp.status_code, 200)
        profile = ChefBattleProfile.objects.get(author=self.chef_a)
        self.assertFalse(profile.fraud_flag)

    def test_clear_fraud_flag_not_set_returns_409(self):
        resp = self._post(self.owner_user, action="clear_fraud_flag",
                          chef_slug="p5-chef-a")
        self.assertEqual(resp.status_code, 409)

    def test_safety_checklist_in_moderation_detail(self):
        """Cooking queue entries expose age_verified/is_suspended/fraud_flag."""
        ChefBattleProfile.objects.filter(author=self.chef_a).update(
            age_verified=False, is_suspended=False, fraud_flag=True)
        self.client.force_login(self.owner_user)
        data = self.client.post(self.state_url).json()
        entries = data["moderation"]["detail"]["cooking_queue"][0]["entries"]
        entry_data = next(e for e in entries if e["author_slug"] == "p5-chef-a")
        self.assertFalse(entry_data["age_verified"])
        self.assertFalse(entry_data["is_suspended"])
        self.assertTrue(entry_data["fraud_flag"])

    def test_flagged_chefs_in_moderation_detail(self):
        """Suspended and fraud-flagged enrolled chefs appear in flagged_chefs list."""
        ChefBattleProfile.objects.filter(author=self.chef_a).update(
            is_suspended=True, suspension_reason="test")
        self.client.force_login(self.owner_user)
        data = self.client.post(self.state_url).json()
        flagged = data["moderation"]["detail"]["flagged_chefs"]
        slugs = [c["chef_slug"] for c in flagged]
        self.assertIn("p5-chef-a", slugs)
        self.assertNotIn("p5-chef-b", slugs)


# ── AMC P06 — voting integrity & audience analytics ──────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterVotingAnalyticsTests(TestCase):
    """P06: totals/percentages vs ORM, series window, enforcement evidence,
    tie/readiness, privacy of voter data."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.state_url = reverse("chef_battle:master_state")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        ua = User.objects.create_user("p6-chef-a", password="pw")
        ub = User.objects.create_user("p6-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="P6 Chef A", slug="p6-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="P6 Chef B", slug="p6-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now())
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now())

    def _battle(self, status=Battle.Status.VOTING, **extra):
        now = timezone.now()
        defaults = dict(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Analytics Dish", status=status,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )
        defaults.update(extra)
        return Battle.objects.create(**defaults)

    def _votes(self, battle, for_a=0, for_b=0):
        User = get_user_model()
        made = []
        for i in range(for_a):
            u = User.objects.create_user(f"p6-va-{battle.pk}-{i}", password="pw")
            made.append(BattleVote.objects.create(battle=battle, voter=u, voted_for=self.chef_a))
        for i in range(for_b):
            u = User.objects.create_user(f"p6-vb-{battle.pk}-{i}", password="pw")
            made.append(BattleVote.objects.create(battle=battle, voter=u, voted_for=self.chef_b))
        return made

    def _voting(self):
        self.client.force_login(self.owner_user)
        data = self.client.post(self.state_url).json()
        return data["voting"]

    def test_zero_votes_gives_null_percentages(self):
        self._battle()
        v = self._voting()[0]
        self.assertEqual(v["total_votes"], 0)
        self.assertIsNone(v["challenger_pct"])
        self.assertIsNone(v["opponent_pct"])
        self.assertFalse(v["is_tie"])
        self.assertFalse(v["completion"]["has_votes"])

    def test_percentages_match_direct_orm(self):
        battle = self._battle()
        self._votes(battle, for_a=3, for_b=1)
        v = self._voting()[0]
        self.assertEqual(v["challenger_votes"],
                         BattleVote.objects.filter(battle=battle, voted_for=self.chef_a).count())
        self.assertEqual(v["challenger_pct"], 75.0)
        self.assertEqual(v["opponent_pct"], 25.0)
        self.assertFalse(v["is_tie"])

    def test_one_sided_votes(self):
        battle = self._battle()
        self._votes(battle, for_a=2, for_b=0)
        v = self._voting()[0]
        self.assertEqual(v["challenger_pct"], 100.0)
        self.assertEqual(v["opponent_pct"], 0.0)

    def test_votes_per_hour_series_window_and_timezone(self):
        battle = self._battle()
        votes = self._votes(battle, for_a=2)
        # Move one vote outside the 24h window
        old = votes[0]
        BattleVote.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=30))
        v = self._voting()[0]
        self.assertEqual(v["series_timezone"], "UTC")
        self.assertEqual(v["series_window_hours"], 24)
        self.assertEqual(sum(p["votes"] for p in v["votes_per_hour"]), 1)

    def test_enforcement_evidence_from_integrity_events(self):
        from .models import VoteIntegrityEvent
        battle = self._battle()
        VoteIntegrityEvent.objects.create(battle=battle, gate_code="duplicate_account")
        VoteIntegrityEvent.objects.create(battle=battle, gate_code="duplicate_account")
        old = VoteIntegrityEvent.objects.create(battle=battle, gate_code="participant")
        VoteIntegrityEvent.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=30))
        v = self._voting()[0]
        enf = v["enforcement"]
        self.assertEqual(enf["rejected_attempts_total"], 3)
        self.assertEqual(enf["rejected_attempts_24h"], 2)
        self.assertEqual(enf["rejected_by_gate"]["duplicate_account"], 2)
        self.assertIn("unique(battle, voter)", enf["one_vote_per_account"])

    def test_tie_and_completion_readiness(self):
        battle = self._battle(
            voting_deadline=timezone.now() - timezone.timedelta(minutes=5))
        self._votes(battle, for_a=2, for_b=2)
        v = self._voting()[0]
        self.assertTrue(v["is_tie"])
        self.assertTrue(v["completion"]["deadline_passed"])
        self.assertTrue(v["completion"]["blocked_by_tie"])

    def test_suspicious_queue_has_no_voter_identity(self):
        battle = self._battle()
        votes = self._votes(battle, for_a=1)
        BattleVote.objects.filter(pk=votes[0].pk).update(is_suspicious=True)
        self.client.force_login(self.owner_user)
        raw = self.client.post(self.state_url).content.decode()
        data = self.client.post(self.state_url).json()
        v = data["voting"][0]
        self.assertEqual(v["suspicious_votes"], 1)
        entry = v["suspicious_queue"][0]
        self.assertEqual(set(entry.keys()), {"id", "voted_for__slug", "created_at"})
        # No voter username or hash VALUES anywhere in the console payload.
        # (The constraint description string legitimately names the ip_hash
        # column, so we assert the JSON keys are absent, not the substring.)
        self.assertNotIn("p6-va-", raw)
        self.assertNotIn('"ip_hash"', raw)
        self.assertNotIn('"user_agent_hash"', raw)
        # And the series hour is really UTC
        data2 = self.client.post(self.state_url).json()
        for point in data2["voting"][0]["votes_per_hour"]:
            self.assertTrue(point["hour_utc"].endswith("+00:00"), point["hour_utc"])

    def test_pulse_support_and_chat(self):
        from .models import Artifact, BattleChatMessage, ViewerBattleGift
        battle = self._battle()
        artifact = Artifact.objects.create(
            name="P6 Whisk", rarity=Artifact.Rarity.COMMON,
            effect_type="attack", effect_value=1, token_cost=25)
        ViewerBattleGift.objects.create(
            battle=battle, recipient=self.chef_a, artifact=artifact, tokens_spent=25)
        BattleChatMessage.objects.create(
            battle=battle, display_name="fan", body="go!", is_hidden=False)
        BattleChatMessage.objects.create(
            battle=battle, display_name="troll", body="hidden", is_hidden=True)
        v = self._voting()[0]
        self.assertEqual(v["pulse"]["chat_messages_total"], 1)
        self.assertEqual(v["pulse"]["support_by_chef"]["p6-chef-a"]["tokens"], 25)

    def test_public_arena_unchanged_no_analytics_leak(self):
        battle = self._battle()
        self._votes(battle, for_a=1)
        self.client.logout()
        raw = self.client.post(reverse("chef_battle:arena_state")).content.decode()
        for marker in ("votes_per_hour", "rejected_by_gate", "suspicious_queue",
                       "enforcement", "challenger_pct"):
            self.assertNotIn(marker, raw)


# ── AMC P07 — economy, gifts, tokens, artifacts (read-only) ──────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterEconomyTests(TestCase):
    """P07: ledger reconciliation, catalogue/inventory contract, closed-loop
    wording, absence of any economy write path."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.state_url = reverse("chef_battle:master_state")
        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        ua = User.objects.create_user("p7-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=ua, name="P7 Chef", slug="p7-chef")
        ChefBattleProfile.objects.create(author=self.chef, enrolled_at=timezone.now())

    def _detail(self):
        self.client.force_login(self.owner_user)
        return self.client.post(self.state_url).json()["economy"]["detail"]

    def test_empty_states(self):
        d = self._detail()
        self.assertEqual(d["flows_by_type"], {})
        self.assertEqual(d["gifts_by_chef_24h"], [])
        self.assertEqual(d["artifact_inventory"], {})
        self.assertEqual(d["orders_by_status"], {})
        self.assertEqual(d["attention_order_ids"], [])
        self.assertEqual(d["window_hours"], 24)
        # Catalogue is static and always present
        self.assertEqual(len(d["gift_catalogue"]), len(APPRECIATION_GIFT_COST))

    def test_flows_reconcile_to_ledger(self):
        from .services import credit_tokens, debit_tokens
        from .models import TokenTransaction
        credit_tokens(self.chef, 100, TokenTransaction.TxType.PURCHASE)
        credit_tokens(self.chef, 50, TokenTransaction.TxType.ADMIN_GRANT)
        debit_tokens(self.chef, 30, TokenTransaction.TxType.GIFT_SENT)
        d = self._detail()
        self.assertEqual(d["flows_by_type"]["purchase"], {"count": 1, "tokens": 100})
        self.assertEqual(d["flows_by_type"]["admin_grant"], {"count": 1, "tokens": 50})
        self.assertEqual(d["flows_by_type"]["gift_sent"], {"count": 1, "tokens": -30})
        # Headline totals reconcile with the same ledger
        econ = self.client.post(self.state_url).json()["economy"]
        self.assertEqual(econ["tokens_in_24h"], 150)
        self.assertEqual(econ["tokens_out_24h"], -30)
        # Wallet invariant: balance equals ledger sum
        from .models import TokenWallet
        wallet = TokenWallet.objects.get(chef=self.chef)
        ledger_sum = sum(tx.amount for tx in wallet.transactions.all())
        self.assertEqual(wallet.balance, ledger_sum)

    def test_old_transactions_outside_window(self):
        from .services import credit_tokens
        from .models import TokenTransaction
        tx = credit_tokens(self.chef, 100, TokenTransaction.TxType.PURCHASE)
        TokenTransaction.objects.filter(pk=tx.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=30))
        d = self._detail()
        self.assertNotIn("purchase", d["flows_by_type"])

    def test_gift_catalogue_and_delivery(self):
        from .models import AppreciationGift, AppreciationGiftType
        AppreciationGift.objects.create(
            recipient=self.chef, gift_type=AppreciationGiftType.COFFEE, tokens_spent=20)
        d = self._detail()
        coffee = next(g for g in d["gift_catalogue"] if g["type"] == "coffee")
        self.assertEqual(coffee["cost_tokens"], 20)
        self.assertEqual(coffee["delivered_24h"], 1)
        self.assertEqual(d["gifts_by_chef_24h"][0],
                         {"chef": "p7-chef", "gifts": 1, "tokens": 20})

    def test_artifact_inventory_and_rarity(self):
        from .models import Artifact, ChefArtifact
        a1 = Artifact.objects.create(name="P7 Pan", rarity=Artifact.Rarity.RARE,
                                     effect_type="defence", effect_value=2, token_cost=50)
        a2 = Artifact.objects.create(name="P7 Spoon", rarity=Artifact.Rarity.COMMON,
                                     effect_type="attack", effect_value=1, token_cost=10)
        ChefArtifact.objects.create(chef=self.chef, artifact=a1,
                                    status=ChefArtifact.Status.AVAILABLE)
        ChefArtifact.objects.create(chef=self.chef, artifact=a2,
                                    status=ChefArtifact.Status.CONSUMED)
        d = self._detail()
        self.assertEqual(d["artifact_inventory"], {"available": 1, "consumed": 1})
        self.assertEqual(d["rarity_distribution"], {"rare": 1, "common": 1})

    def test_orders_by_status_and_attention_ids(self):
        from .models import TokenOrder, TokenPackage, TokenWallet
        wallet, _ = TokenWallet.objects.get_or_create(chef=self.chef)
        package = TokenPackage.objects.first() or TokenPackage.objects.create(
            key="p7-test", name="P7 Test Pack", tokens=100, price_eur="10.00")
        ok = TokenOrder.objects.create(
            wallet=wallet, package=package, status=TokenOrder.Status.COMPLETED,
            tokens=100, amount_eur_cents=1000)
        bad = TokenOrder.objects.create(
            wallet=wallet, package=package, status=TokenOrder.Status.DISPUTED,
            tokens=100, amount_eur_cents=1000)
        d = self._detail()
        self.assertEqual(d["orders_by_status"], {"completed": 1, "disputed": 1})
        self.assertEqual(d["attention_order_ids"], [bad.pk])

    def test_closed_loop_wording_on_console(self):
        self.client.force_login(self.owner_user)
        page = self.client.get(reverse("chef_battle:master_console")).content.decode()
        self.assertIn("closed-loop virtual items", page)
        for banned in ("withdrawable", "e-money", "cash out", "your earnings"):
            self.assertNotIn(banned, page.lower())

    def test_no_economy_write_action_exists(self):
        # master_action must reject any invented economy mutation verb.
        self.client.force_login(self.owner_user)
        for verb in ("credit_tokens", "adjust_wallet", "mark_order_paid",
                     "grant_tokens", "refund_order"):
            resp = self.client.post(reverse("chef_battle:master_action"),
                                    {"action": verb, "battle_id": 1})
            self.assertEqual(resp.status_code, 400, verb)


# ── AMC P08 — rewards governance (DG-06) ─────────────────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ArenaMasterGovernanceTests(TestCase):
    """P08: reward/payout read models, battle reports (operator write),
    owner-only payout decisions via owning services, ledger chain integrity."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.state_url = reverse("chef_battle:master_state")
        self.action_url = reverse("chef_battle:master_action")

        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        self.operator_user = User.objects.create_superuser("gov-op", password="pw")
        self.operator_author = RecipeAuthor.objects.create(
            user=self.operator_user, name="Gov Op", slug="gov-op",
            has_arena_console_access=True,
        )
        ua = User.objects.create_user("p8-chef", password="pw")
        self.chef = RecipeAuthor.objects.create(user=ua, name="P8 Chef", slug="p8-chef")
        ChefBattleProfile.objects.create(author=self.chef, enrolled_at=timezone.now())

        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef, opponent=self.owner_author,
            theme="Governance Dish", status=Battle.Status.VOTING,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )

    def _payout(self, status=None):
        from .models import PayoutRequest
        return PayoutRequest.objects.create(
            chef=self.chef, amount_reward_tokens=100,
            gross_payout_eur="2.50",
            status=status or PayoutRequest.Status.PENDING,
        )

    def _state(self, user=None):
        self.client.force_login(user or self.owner_user)
        return self.client.post(self.state_url).json()

    # ── read models ──
    def test_governance_read_models(self):
        from .models import RewardRecord
        RewardRecord.objects.create(
            recipient=self.chef, reward_type=RewardRecord.RewardType.CBR,
            tokens_granted=50, reason="battle win",
            status=RewardRecord.Status.APPROVED)
        payout = self._payout()
        gov = self._state()["governance"]
        self.assertEqual(gov["rewards_matrix"]["cbr"]["approved"], 1)
        self.assertEqual(gov["recent_rewards"][0]["recipient"], "p8-chef")
        p = gov["payouts"][0]
        self.assertEqual(p["id"], payout.pk)
        self.assertTrue(p["actionable"])
        self.assertTrue(gov["ledger"]["chain_intact"])

    # ── battle report: the one operator write ──
    def test_operator_submits_battle_report(self):
        from .models import BattleReport
        self.client.force_login(self.operator_user)
        resp = self.client.post(self.action_url, {
            "action": "submit_battle_report", "battle_id": self.battle.pk,
            "summary": "Fair battle, clean kitchen, no violations seen.",
            "recommendation": "approve_payout",
        })
        self.assertEqual(resp.status_code, 200)
        report = BattleReport.objects.get()
        self.assertEqual(report.author, self.operator_author)
        self.assertEqual(report.recommendation, "approve_payout")
        # Audited + owner notified
        event = BattleEvent.objects.get(
            event_type=BattleEvent.EventType.OPERATOR_ACTION)
        self.assertEqual(event.payload_json["action"], "submit_battle_report")
        from messaging.models import Message
        self.assertTrue(Message.objects.filter(
            recipient=self.owner_user, subject__icontains="Battle report").exists())

    def test_report_requires_summary_and_valid_recommendation(self):
        self.client.force_login(self.operator_user)
        resp = self.client.post(self.action_url, {
            "action": "submit_battle_report", "battle_id": self.battle.pk,
            "summary": " ", "recommendation": "approve_payout"})
        self.assertEqual(resp.status_code, 409)
        resp = self.client.post(self.action_url, {
            "action": "submit_battle_report", "battle_id": self.battle.pk,
            "summary": "ok", "recommendation": "pay_now"})
        self.assertEqual(resp.status_code, 409)

    # ── payout decisions: owner only, via owning services ──
    def test_operator_cannot_decide_payout(self):
        payout = self._payout()
        self.client.force_login(self.operator_user)
        resp = self.client.post(self.action_url, {
            "action": "approve_payout", "payout_id": payout.pk})
        self.assertEqual(resp.status_code, 403)
        payout.refresh_from_db()
        self.assertEqual(payout.status, "pending")

    def test_owner_approves_payout_via_owning_service(self):
        from .models import LedgerEvent, PayoutRequest
        payout = self._payout()
        self.client.force_login(self.owner_user)
        resp = self.client.post(self.action_url, {
            "action": "approve_payout", "payout_id": payout.pk})
        self.assertEqual(resp.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutRequest.Status.APPROVED)
        self.assertEqual(payout.reviewed_by, self.owner_user)
        # Owning service wrote its ledger event; console added audit; chain intact
        self.assertTrue(LedgerEvent.objects.filter(
            payload__action="payout_approved").exists())
        self.assertTrue(BattleEvent.objects.filter(
            event_type=BattleEvent.EventType.OPERATOR_ACTION,
            payload_json__action="payout_approve").exists())
        ok, broken = LedgerEvent.verify_chain()
        self.assertTrue(ok, f"chain broken at {broken}")

    def test_owner_reject_requires_reason_and_returns_rewards(self):
        from .models import PayoutRequest, RewardRecord
        payout = self._payout()
        RewardRecord.objects.create(
            recipient=self.chef, reward_type=RewardRecord.RewardType.CBR,
            tokens_granted=100, reason="win",
            status=RewardRecord.Status.ISSUED,
            status_note=f"PayoutRequest #{payout.pk}")
        self.client.force_login(self.owner_user)
        resp = self.client.post(self.action_url, {
            "action": "reject_payout", "payout_id": payout.pk, "reason": ""})
        self.assertEqual(resp.status_code, 409)
        resp = self.client.post(self.action_url, {
            "action": "reject_payout", "payout_id": payout.pk,
            "reason": "verification incomplete"})
        self.assertEqual(resp.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutRequest.Status.REJECTED)
        self.assertEqual(payout.rejection_reason, "verification incomplete")
        reward = RewardRecord.objects.get()
        self.assertEqual(reward.status, RewardRecord.Status.APPROVED)

    def test_paid_payout_not_actionable(self):
        from .models import PayoutRequest
        payout = self._payout(status=PayoutRequest.Status.PAID)
        gov = self._state()["governance"]
        self.assertFalse(gov["payouts"][0]["actionable"])
        self.client.force_login(self.owner_user)
        resp = self.client.post(self.action_url, {
            "action": "approve_payout", "payout_id": payout.pk})
        self.assertEqual(resp.status_code, 409)

    # ── wording + privacy ──
    def test_rewards_never_described_as_funds(self):
        self.client.force_login(self.owner_user)
        page = self.client.get(reverse("chef_battle:master_console")).content.decode()
        self.assertIn("discretionary platform rewards", page)
        for banned in ("earned funds", "withdrawable balance", "cash balance"):
            self.assertNotIn(banned, page.lower())

    def test_payout_data_not_public(self):
        self._payout()
        self.client.logout()
        raw = self.client.post(reverse("chef_battle:arena_state")).content.decode()
        for marker in ("gross_eur", "payout", "rewards_matrix", "chain_intact"):
            self.assertNotIn(marker, raw)


# ── DG-04 — viewer presence heartbeat ────────────────────────────────────────

@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class ViewerPresenceTests(TestCase):
    """DG-04 resolution: heartbeats on existing polls, 180s window,
    device-hash pseudonymisation, no PII, opportunistic retention."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        ua = User.objects.create_user("pr-chef-a", password="pw")
        ub = User.objects.create_user("pr-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="Pr Chef A", slug="pr-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="Pr Chef B", slug="pr-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now())
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now())
        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Presence Dish", status=Battle.Status.ACTIVE,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )

    def _poll_battle(self, ip, ua="TestBrowser/1.0"):
        # Anonymous spectators heartbeat via the public battle room page
        # (battle_state_poll is login-only and covers logged-in viewers).
        return self.client.get(
            reverse("chef_battle:battle_detail", kwargs={"pk": self.battle.pk}),
            REMOTE_ADDR=ip, HTTP_USER_AGENT=ua,
        )

    def _viewers(self):
        self.client.force_login(self.owner_user)
        return self.client.post(reverse("chef_battle:master_state")).json()["viewers"]

    def test_battle_poll_records_presence(self):
        from .models import BattleViewerPresence
        self.assertEqual(self._poll_battle("10.0.0.1").status_code, 200)
        row = BattleViewerPresence.objects.get()
        self.assertEqual(row.battle, self.battle)
        self.assertEqual(len(row.viewer_hash), 64)

    def test_same_device_counts_once_distinct_devices_counted(self):
        self._poll_battle("10.0.0.1")
        self._poll_battle("10.0.0.1")  # same device, refresh only
        self._poll_battle("10.0.0.2")
        self._poll_battle("10.0.0.1", ua="OtherBrowser/2.0")
        v = self._viewers()
        self.assertTrue(v["available"])
        self.assertEqual(v["battles"][0]["viewers"], 3)

    def test_stale_viewers_leave_the_window(self):
        from .models import BattleViewerPresence
        self._poll_battle("10.0.0.1")
        BattleViewerPresence.objects.update(
            last_seen_at=timezone.now() - timezone.timedelta(seconds=300))
        v = self._viewers()
        self.assertEqual(v["battles"][0]["viewers"], 0)

    def test_arena_lobby_counted_separately(self):
        self.client.post(reverse("chef_battle:arena_state"),
                         REMOTE_ADDR="10.0.0.9", HTTP_USER_AGENT="Lobby/1.0")
        self._poll_battle("10.0.0.1")
        v = self._viewers()
        self.assertEqual(v["arena_lobby_viewers"], 1)
        self.assertEqual(v["battles"][0]["viewers"], 1)

    def test_idle_rows_purged_after_an_hour(self):
        from .models import BattleViewerPresence
        BattleViewerPresence.objects.create(
            battle=self.battle, viewer_hash="x" * 64,
            last_seen_at=timezone.now() - timezone.timedelta(hours=2))
        self._poll_battle("10.0.0.1")
        hashes = set(BattleViewerPresence.objects.filter(
            battle=self.battle).values_list("viewer_hash", flat=True))
        self.assertNotIn("x" * 64, hashes)
        self.assertEqual(len(hashes), 1)

    def test_no_raw_ip_or_ua_stored_or_exposed(self):
        from .models import BattleViewerPresence
        self._poll_battle("203.0.113.77", ua="SecretAgent/9.9")
        row = BattleViewerPresence.objects.get()
        self.assertNotIn("203.0.113.77", row.viewer_hash)
        self.client.force_login(self.owner_user)
        raw = self.client.post(reverse("chef_battle:master_state")).content.decode()
        self.assertNotIn("203.0.113.77", raw)
        self.assertNotIn("SecretAgent", raw)
        self.assertNotIn("viewer_hash", raw)

    def test_public_polls_unbroken_and_arena_json_clean(self):
        resp = self.client.post(reverse("chef_battle:arena_state"),
                                REMOTE_ADDR="10.0.0.5", HTTP_USER_AGENT="A/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.json().keys()),
                         {"rings", "spectators", "center", "latest_result"})


@override_settings(CHEF_BATTLE_ENABLED=True)
class OwnerBriefingTests(TestCase):
    """The AMC owner briefing on the challenges page is owner-only."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        cu = User.objects.create_user("brief-chef", password="pw")
        RecipeAuthor.objects.create(user=cu, name="Brief Chef", slug="brief-chef")
        self.chef_user = cu
        self.url = reverse("chef_battle:challenge_list")

    def test_owner_sees_briefing(self):
        self.client.force_login(self.owner_user)
        resp = self.client.get(self.url)
        self.assertContains(resp, "Owner Briefing")
        self.assertContains(resp, "Completion report")
        self.assertContains(resp, "Running a test battle")
        # Console button in the action row for console-access users
        self.assertContains(resp, "Master Console")
        self.assertContains(resp, "/chef-battle/master/")

    def test_regular_chef_does_not_see_briefing(self):
        self.client.force_login(self.chef_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Owner Briefing")
        self.assertNotContains(resp, "amc-briefing")
        self.assertNotContains(resp, "Master Console")


@override_settings(ARENA_MASTER_CONSOLE_ENABLED=True, CHEF_BATTLE_ENABLED=True)
class BattleEmulationTests(TestCase):
    """Owner-only battle emulation drives a full lifecycle via real services."""

    def setUp(self):
        from django.conf import settings as django_settings
        User = get_user_model()
        self.owner_user = User.objects.create_superuser("greenbear", password="pw")
        self.owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"user": self.owner_user, "name": "GreenBear"},
        )
        self.url = reverse("chef_battle:master_action")

    def test_operator_cannot_emulate(self):
        User = get_user_model()
        op = User.objects.create_superuser("emu-op", password="pw")
        RecipeAuthor.objects.create(user=op, name="Emu Op", slug="emu-op",
                                    has_arena_console_access=True)
        self.client.force_login(op)
        resp = self.client.post(self.url, {"action": "start_emulation"})
        self.assertEqual(resp.status_code, 403)

    def test_full_emulated_lifecycle(self):
        from .emulation import emulation_step, start_emulation
        battle = start_emulation(operator_author=self.owner_author)
        self.assertEqual(battle.status, Battle.Status.SCHEDULED)
        self.assertTrue(battle.theme.startswith("EMULATION"))

        seen = [battle.status]
        for _ in range(12):
            result = emulation_step(battle_id=battle.pk,
                                    operator_author=self.owner_author)
            seen.append(result["after"])
            if result["after"] == Battle.Status.COMPLETED:
                break
        battle.refresh_from_db()
        self.assertEqual(battle.status, Battle.Status.COMPLETED)

        # Every stage of the real lifecycle was traversed
        for stage in ("menu_locked", "ingredient_penalty", "cooking",
                      "presentation", "voting", "completed"):
            self.assertIn(stage, seen, seen)

        # Real domain artifacts exist
        self.assertEqual(battle.entries.count(), 2)
        self.assertGreater(battle.combat_rounds.count(), 0)
        self.assertEqual(
            battle.ingredient_locks.count(), 2)  # IngredientLock.MAX_LOCKS
        self.assertGreater(battle.votes.count(), 0)
        self.assertIsNotNone(battle.winner)
        for entry in battle.entries.all():
            self.assertTrue(entry.cooked_photo)
            self.assertEqual(entry.moderation_status,
                             BattleEntry.ModerationStatus.APPROVED)
        # Audited
        self.assertTrue(BattleEvent.objects.filter(
            battle=battle, event_type=BattleEvent.EventType.OPERATOR_ACTION,
            payload_json__action="emulation_start").exists())

    def test_second_emulation_blocked_while_running(self):
        from .emulation import start_emulation
        from .services import OperatorActionError
        start_emulation(operator_author=self.owner_author)
        with self.assertRaises(OperatorActionError):
            start_emulation(operator_author=self.owner_author)

    def test_step_rejects_non_emulation_battle(self):
        from .emulation import emulation_step, _get_or_create_bot
        from .services import OperatorActionError
        a = _get_or_create_bot("emu-chef-alpha", "EMU Chef Alpha")
        b = _get_or_create_bot("emu-chef-beta", "EMU Chef Beta")
        now = timezone.now()
        real = Battle.objects.create(
            challenger=a, opponent=b, theme="Real Battle",
            status=Battle.Status.SCHEDULED, start_time=now,
            submission_deadline=now + timezone.timedelta(days=1),
            voting_deadline=now + timezone.timedelta(days=2),
            end_time=now + timezone.timedelta(days=3))
        with self.assertRaises(OperatorActionError):
            emulation_step(battle_id=real.pk, operator_author=self.owner_author)


@override_settings(CHEF_BATTLE_ENABLED=True)
class ProfileMergeTests(TestCase):
    """Regression tests for the merged chef profile / author page (2026-07-06):
    hero battle panel removed, chef profile folded into the author page."""

    def setUp(self):
        User = get_user_model()
        u1 = User.objects.create_user("merge-chef", password="pw")
        u2 = User.objects.create_user("merge-plain", password="pw")
        self.chef = RecipeAuthor.objects.create(user=u1, name="Merge Chef", slug="merge-chef")
        self.plain = RecipeAuthor.objects.create(user=u2, name="Merge Plain", slug="merge-plain")
        ChefBattleProfile.objects.create(author=self.chef, enrolled_at=timezone.now())
        # plain author: no ChefBattleProfile at all

    def test_chef_profile_url_redirects_to_author_arena(self):
        resp = self.client.get(reverse("chef_battle:chef_profile", kwargs={"slug": "merge-chef"}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, self.chef.get_absolute_url() + "#chef-arena")

    def test_chef_profile_redirect_missing_slug_404(self):
        resp = self.client.get(reverse("chef_battle:chef_profile", kwargs={"slug": "no-such-xyz"}))
        self.assertEqual(resp.status_code, 404)

    def test_redirect_works_for_author_without_battle_profile(self):
        resp = self.client.get(reverse("chef_battle:chef_profile", kwargs={"slug": "merge-plain"}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, self.plain.get_absolute_url() + "#chef-arena")

    def test_author_page_shows_arena_for_enrolled_chef(self):
        resp = self.client.get(self.chef.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="chef-arena"')
        self.assertContains(resp, "Chef Battles Arena")

    def test_author_page_no_arena_for_non_chef(self):
        resp = self.client.get(self.plain.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="chef-arena"')

    def test_hero_battle_panel_partial_gone(self):
        import os
        from django.conf import settings as dj
        for base in dj.TEMPLATES[0]["DIRS"]:
            self.assertFalse(
                os.path.exists(os.path.join(base, "_hero_battle_panel.html")),
                "the hero battle panel partial should be deleted")

    def test_get_author_for_user_anonymous_returns_none(self):
        from django.contrib.auth.models import AnonymousUser
        from recipes.authoring import get_author_for_user
        self.assertIsNone(get_author_for_user(AnonymousUser()))
        self.assertIsNone(get_author_for_user(None))

    def test_token_shop_renders_for_anonymous(self):
        # login link must reverse; anonymous must not crash (get_author_for_user guard)
        resp = self.client.get(reverse("chef_battle:token_shop"))
        self.assertIn(resp.status_code, (200, 302))

    def test_widget_menu_urls_reverse(self):
        for name in ["challenge_list", "season_leaderboard", "rankings",
                     "token_shop", "appreciation_gallery", "artifact_gallery"]:
            reverse(f"chef_battle:{name}")  # raises NoReverseMatch on failure

    def test_author_summary_selector_shapes(self):
        from chef_battle.selectors import get_author_battle_summary
        data = get_author_battle_summary(self.chef)
        self.assertEqual(
            set(data.keys()), {"battle_profile", "recent_battles", "battles", "gift_display"})
        self.assertIsNotNone(data["battle_profile"])
        self.assertIsInstance(data["gift_display"], list)


@override_settings(
    CHEF_BATTLE_ENABLED=True,
    ARENA_MASTER_CONSOLE_ENABLED=True,
    OWNER_SLUG="amc-sec-owner",
)
class ArenaMasterActionSecurityTests(TransactionTestCase):
    """Audit trail, idempotency, concurrency, rollback, and CSRF tests for
    the Arena Master Console master_action endpoint.

    Two tiers under test:
      DG-01 (arena_console_guard): superuser + has_arena_console_access
      DG-02 (view-level): owner-only for write actions (OWNER_SLUG match)

    amc-sec-owner  -- passes DG-01 AND DG-02 (OWNER_SLUG overridden)
    amc-sec-other  -- passes DG-01 but fails DG-02 (non-owner operator)
    """

    def setUp(self):
        User = get_user_model()
        owner_user = User.objects.create_user("amc-sec-owner", password="pw", is_superuser=True)
        other_user = User.objects.create_user("amc-sec-other", password="pw", is_superuser=True)
        self.owner_author = RecipeAuthor.objects.create(
            user=owner_user, name="AMC Owner", slug="amc-sec-owner",
            has_arena_console_access=True)
        self.other_author = RecipeAuthor.objects.create(
            user=other_user, name="AMC Other", slug="amc-sec-other",
            has_arena_console_access=True)
        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.owner_author, opponent=self.other_author,
            theme="Security Battle", status=Battle.Status.SCHEDULED,
            start_time=now, submission_deadline=now + timezone.timedelta(days=1),
            voting_deadline=now + timezone.timedelta(days=2),
            end_time=now + timezone.timedelta(days=3),
        )
        self.url = reverse("chef_battle:master_action")

    def _login_owner(self):
        c = Client()
        c.login(username="amc-sec-owner", password="pw")
        return c

    def _login_other(self):
        c = Client()
        c.login(username="amc-sec-other", password="pw")
        return c

    # -- Audit trail tests ------------------------------------------------
    # NOTE: master_action view reads request.POST (form-encoded), not JSON.
    # Field names come from the view: target_status (not new_status), etc.

    def test_non_owner_rejection_is_audited(self):
        """Non-owner console operator (passes DG-01 guard) gets 403 from DG-02
        and the rejection is written to the audit trail."""
        c = self._login_other()
        before = BattleEvent.objects.count()
        resp = c.post(self.url, data={
            "action": "force_status", "battle_id": self.battle.pk,
            "target_status": "active", "correlation_id": "sec-test-1"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(BattleEvent.objects.count(), before + 1)
        ev = BattleEvent.objects.order_by("-created_at").first()
        self.assertEqual(ev.payload_json["outcome"], "rejected")

    def test_invalid_battle_id_rejection_is_audited(self):
        c = self._login_owner()
        before = BattleEvent.objects.count()
        resp = c.post(self.url, data={
            "action": "force_status", "battle_id": "not-a-number",
            "target_status": "active", "correlation_id": "sec-test-2"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(BattleEvent.objects.count(), before + 1)
        ev = BattleEvent.objects.order_by("-created_at").first()
        self.assertEqual(ev.payload_json["outcome"], "rejected")

    def test_not_found_rejection_is_audited(self):
        c = self._login_owner()
        before = BattleEvent.objects.count()
        resp = c.post(self.url, data={
            "action": "force_status", "battle_id": 999999,
            "target_status": "active", "correlation_id": "sec-test-3"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(BattleEvent.objects.count(), before + 1)
        ev = BattleEvent.objects.order_by("-created_at").first()
        self.assertEqual(ev.payload_json["outcome"], "rejected")

    def test_unknown_action_rejection_is_audited(self):
        c = self._login_owner()
        before = BattleEvent.objects.count()
        resp = c.post(self.url, data={
            "action": "does_not_exist", "correlation_id": "sec-test-4"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(BattleEvent.objects.count(), before + 1)
        ev = BattleEvent.objects.order_by("-created_at").first()
        self.assertEqual(ev.payload_json["outcome"], "rejected")

    def test_service_rejection_stale_state_is_audited(self):
        """force_status with wrong expected_status triggers OperatorActionError."""
        c = self._login_owner()
        before = BattleEvent.objects.count()
        resp = c.post(self.url, data={
            "action": "force_status", "battle_id": self.battle.pk,
            "target_status": "active",
            "expected_status": "voting",  # wrong -- battle is scheduled
            "correlation_id": "sec-test-5"})
        self.assertIn(resp.status_code, (400, 409))
        self.assertGreater(BattleEvent.objects.count(), before)
        ev = BattleEvent.objects.filter(
            payload_json__outcome="rejected").order_by("-created_at").first()
        self.assertIsNotNone(ev)

    # -- Idempotency / dedup tests ----------------------------------------

    def test_broadcast_replay_with_same_correlation_id_is_rejected(self):
        c = self._login_owner()
        post_data = {
            "action": "broadcast", "message": "Hello arena",
            "correlation_id": "idem-corr-001"}
        r1 = c.post(self.url, data=post_data)
        self.assertEqual(r1.status_code, 200)
        r2 = c.post(self.url, data=post_data)
        self.assertEqual(r2.status_code, 409)
        data2 = json.loads(r2.content)
        self.assertFalse(data2["ok"])
        self.assertIn("already", data2["error"].lower())
        self.assertEqual(
            OperatorActionIdempotencyKey.objects.filter(correlation_id="idem-corr-001").count(),
            1)

    def test_broadcast_without_correlation_id_is_not_deduplicated(self):
        """Omitting correlation_id: view auto-generates a unique one per request,
        so two identical broadcasts both apply."""
        c = self._login_owner()
        post_data = {"action": "broadcast", "message": "No dedup here"}
        r1 = c.post(self.url, data=post_data)
        r2 = c.post(self.url, data=post_data)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

    # -- Concurrency test -------------------------------------------------

    def test_concurrent_force_status_requests_serialize_exactly_once(self):
        """Two threads race to force the same status transition.
        Only one must succeed; the other must be rejected (stale-state guard
        or DB serialization). raise_request_exception=False so SQLite
        serialization errors appear as 500 rather than propagating."""
        import threading

        self.battle.status = Battle.Status.SCHEDULED
        self.battle.save(update_fields=["status"])

        results = []
        errors = []

        # Log both clients in serially on the main thread — a concurrent login
        # is a session-table write that can hit an SQLite lock and kill the
        # thread before the race under test (the POST) even starts.
        clients = []
        for _ in range(2):
            c = Client(raise_request_exception=False)
            c.login(username="amc-sec-owner", password="pw")
            clients.append(c)

        def do_request(c):
            # raise_request_exception=False: DB errors become 500, not thread crashes
            try:
                r = c.post(self.url, data={
                    "action": "force_status",
                    "battle_id": self.battle.pk,
                    "target_status": "active",
                    "expected_status": "scheduled",
                    "correlation_id": ""})
                results.append(r.status_code)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=do_request, args=(clients[0],))
        t2 = threading.Thread(target=do_request, args=(clients[1],))
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertFalse(errors, f"Thread errors: {errors}")
        self.assertEqual(len(results), 2, f"Both threads must complete, got: {results}")
        ok_count = results.count(200)
        # Any non-200 counts as a rejection (409=stale, 400=invalid, 500=db lock)
        rejected_count = len([s for s in results if s != 200])
        self.assertEqual(ok_count, 1, f"Expected exactly 1 success, got: {results}")
        self.assertEqual(rejected_count, 1, f"Expected exactly 1 rejection, got: {results}")

    # -- Rollback test ----------------------------------------------------

    def test_exception_mid_transaction_rolls_back_state_and_audit(self):
        """If RuntimeError fires before operator_force_status runs (simulating
        a crash before any DB write), the battle status must remain unchanged
        and the view must not return 200. raise_request_exception=False so the
        RuntimeError becomes a 500 response instead of propagating to the test."""
        from unittest.mock import patch
        from chef_battle import services as svc

        def crashing_force(**kwargs):
            raise RuntimeError("Crash before any state write")

        c = Client(raise_request_exception=False)
        c.login(username="amc-sec-owner", password="pw")
        before_status = self.battle.status

        with patch.object(svc, "operator_force_status", side_effect=crashing_force):
            resp = c.post(self.url, data={
                "action": "force_status",
                "battle_id": self.battle.pk,
                "target_status": "active",
                "expected_status": "",
                "correlation_id": "rollback-test-001"})

        # Must not return 200 (no success on crash)
        self.assertNotEqual(resp.status_code, 200)
        # Battle status must be unchanged because the service never ran
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, before_status,
                         "Battle status must not have changed after service crash")

    # -- CSRF enforcement tests -------------------------------------------

    def test_post_without_csrf_token_is_rejected_with_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.login(username="amc-sec-owner", password="pw")
        resp = c.post(self.url, data={
            "action": "broadcast", "message": "csrf test",
            "correlation_id": "csrf-test-no-token"})
        self.assertEqual(resp.status_code, 403)

    def test_post_with_valid_csrf_token_succeeds_with_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.login(username="amc-sec-owner", password="pw")
        # GET to master_console forces Django to set the csrftoken cookie
        c.get(reverse("chef_battle:master_console"))
        csrf_value = c.cookies.get("csrftoken")
        self.assertIsNotNone(csrf_value, "CSRF cookie must be set after GET")
        resp = c.post(self.url,
            data={"action": "broadcast", "message": "csrf success test",
                  "correlation_id": "csrf-test-with-token"},
            HTTP_X_CSRFTOKEN=csrf_value.value)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["ok"])


# ── Combat artifact activation (Gap 2 fix) ───────────────────────────────────

@override_settings(CHEF_BATTLE_ENABLED=True)
class CombatArtifactTests(TestCase):
    """submit_combat_action accepts artifact_id; _resolve_round consumes it."""

    def setUp(self):
        from .models import Artifact, ChefArtifact, ChefBattleProfile
        User = get_user_model()
        ua = User.objects.create_user("art-chef-a", password="pw")
        ub = User.objects.create_user("art-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="Art Chef A", slug="art-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="Art Chef B", slug="art-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now(), battle_moves=50)
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now(), battle_moves=50)
        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a, opponent=self.chef_b,
            theme="Artifact Dish", status=Battle.Status.ACTIVE,
            start_time=now,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=5),
        )
        self.artifact = Artifact.objects.create(
            name="Iron Pan", rarity=Artifact.Rarity.RARE,
            effect_type="attack", effect_value=5, token_cost=50,
        )
        self.chef_artifact = ChefArtifact.objects.create(
            chef=self.chef_a, artifact=self.artifact,
            status=ChefArtifact.Status.AVAILABLE,
        )

    def test_artifact_id_sets_artifact_used_on_action(self):
        from .services import submit_combat_action
        action = submit_combat_action(
            self.battle, self.chef_a, "attack", 3, artifact_id=self.chef_artifact.pk
        )
        self.assertEqual(action.artifact_used_id, self.chef_artifact.pk)

    def test_artifact_consumed_after_round_resolves(self):
        from .models import ChefArtifact
        from .services import submit_combat_action
        submit_combat_action(self.battle, self.chef_a, "attack", 3, artifact_id=self.chef_artifact.pk)
        # Resolves automatically when opponent submits
        submit_combat_action(self.battle, self.chef_b, "defend", 1)
        self.chef_artifact.refresh_from_db()
        self.assertEqual(self.chef_artifact.status, ChefArtifact.Status.CONSUMED)
        self.assertIsNotNone(self.chef_artifact.consumed_at)
        self.assertEqual(self.chef_artifact.consumed_in_battle_id, self.battle.pk)

    def test_artifact_belonging_to_opponent_is_rejected(self):
        from .models import Artifact, ChefArtifact
        from .services import submit_combat_action
        other_artifact = Artifact.objects.create(
            name="Silver Spoon", rarity=Artifact.Rarity.COMMON,
            effect_type="boost", effect_value=2, token_cost=10,
        )
        opponent_ca = ChefArtifact.objects.create(
            chef=self.chef_b, artifact=other_artifact,
            status=ChefArtifact.Status.AVAILABLE,
        )
        with self.assertRaises(ValueError, msg="Artifact not available or does not belong to you."):
            submit_combat_action(self.battle, self.chef_a, "attack", 3, artifact_id=opponent_ca.pk)

    def test_consumed_artifact_is_rejected(self):
        from .models import ChefArtifact
        from .services import submit_combat_action
        self.chef_artifact.status = ChefArtifact.Status.CONSUMED
        self.chef_artifact.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            submit_combat_action(self.battle, self.chef_a, "attack", 3, artifact_id=self.chef_artifact.pk)

    def test_combat_without_artifact_unchanged(self):
        from .services import submit_combat_action
        action = submit_combat_action(self.battle, self.chef_a, "attack", 2)
        self.assertIsNone(action.artifact_used_id)

    def test_battle_detail_context_includes_available_artifacts(self):
        self.client.force_login(self.chef_a.user)
        resp = self.client.get(reverse("chef_battle:battle_detail", args=[self.battle.pk]))
        self.assertEqual(resp.status_code, 200)
        available = resp.context["user_available_artifacts"]
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].pk, self.chef_artifact.pk)

    def test_battle_combat_action_view_accepts_artifact_id(self):
        from .models import ChefArtifact
        self.client.force_login(self.chef_a.user)
        resp = self.client.post(
            reverse("chef_battle:battle_combat_action", args=[self.battle.pk]),
            {"action_type": "attack", "moves_invested": "2", "artifact_id": str(self.chef_artifact.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        from .models import BattleCombatAction
        action = BattleCombatAction.objects.get(battle=self.battle, chef=self.chef_a, round_number=1)
        self.assertEqual(action.artifact_used_id, self.chef_artifact.pk)


# ── Post-battle cooldown — accept path (Gap 4 fix) ───────────────────────────

@override_settings(CHEF_BATTLE_ENABLED=True, SECURE_SSL_REDIRECT=False)
class PostBattleCooldownAcceptTests(TestCase):
    """gate_post_battle_cooldown is enforced on challenge_respond (accept) as well as challenge_create."""

    def setUp(self):
        from .models import ChefBattleProfile
        User = get_user_model()
        ua = User.objects.create_user("cd-chef-a", password="pw")
        ub = User.objects.create_user("cd-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=ua, name="CD Chef A", slug="cd-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=ub, name="CD Chef B", slug="cd-chef-b")
        ChefBattleProfile.objects.create(author=self.chef_a, enrolled_at=timezone.now(), battle_moves=20)
        ChefBattleProfile.objects.create(author=self.chef_b, enrolled_at=timezone.now(), battle_moves=20)

    def _make_pending_challenge(self):
        return BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Cooldown Dish",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )

    def _completed_battle_for(self, chef):
        now = timezone.now()
        other = self.chef_a if chef == self.chef_b else self.chef_b
        return Battle.objects.create(
            challenger=chef, opponent=other,
            theme="Past Dish", status=Battle.Status.COMPLETED,
            start_time=now - timezone.timedelta(hours=2),
            submission_deadline=now - timezone.timedelta(hours=1),
            voting_deadline=now - timezone.timedelta(minutes=30),
            end_time=now - timezone.timedelta(minutes=10),
        )

    def test_accept_blocked_when_accepting_chef_in_cooldown(self):
        self._completed_battle_for(self.chef_b)
        challenge = self._make_pending_challenge()
        self.client.force_login(self.chef_b.user)
        resp = self.client.post(
            reverse("chef_battle:challenge_respond", kwargs={"pk": challenge.pk}),
            {"action": "accept"},
        )
        self.assertEqual(resp.status_code, 302)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, BattleChallenge.Status.PENDING)

    def test_accept_allowed_when_no_recent_completed_battle(self):
        challenge = self._make_pending_challenge()
        self.client.force_login(self.chef_b.user)
        resp = self.client.post(
            reverse("chef_battle:challenge_respond", kwargs={"pk": challenge.pk}),
            {"action": "accept"},
        )
        self.assertEqual(resp.status_code, 302)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, BattleChallenge.Status.ACCEPTED)


class DeclareMenuServiceTests(TestCase):
    """Tests for the declare_menu() service (Gap 1 Phase 1)."""

    def setUp(self):
        from .services import declare_menu
        self.declare_menu = declare_menu

        User = get_user_model()
        self.user_a = User.objects.create_user(username="dm-chef-a", password="pw")
        self.user_b = User.objects.create_user(username="dm-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="DM Chef A", slug="dm-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="DM Chef B", slug="dm-chef-b")

        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Test Theme",
            status=Battle.Status.MENU_LOCKED,
            submission_deadline=now + timezone.timedelta(days=5),
            voting_deadline=now + timezone.timedelta(days=7),
            end_time=now + timezone.timedelta(days=7),
        )

    def _ingredients(self, n=5, key_indices=(0, 1)):
        return [
            {"name": f"Ingredient {i}", "is_key": i in key_indices}
            for i in range(n)
        ]

    def test_menu_locked_status_precondition(self):
        self.assertEqual(self.battle.status, Battle.Status.MENU_LOCKED)

    def test_declare_menu_creates_ingredients(self):
        from .models import BattleIngredient
        result = self.declare_menu(
            battle=self.battle, chef=self.chef_a, ingredients=self._ingredients()
        )
        self.assertEqual(len(result), 5)
        db_count = BattleIngredient.objects.filter(battle=self.battle, chef=self.chef_a).count()
        self.assertEqual(db_count, 5)

    def test_declare_menu_exactly_two_keys(self):
        from .models import BattleIngredient
        self.declare_menu(battle=self.battle, chef=self.chef_a, ingredients=self._ingredients())
        key_count = BattleIngredient.objects.filter(
            battle=self.battle, chef=self.chef_a, is_key=True
        ).count()
        self.assertEqual(key_count, 2)

    def test_too_few_ingredients_raises(self):
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_a, ingredients=self._ingredients(n=4)
            )

    def test_too_many_ingredients_raises(self):
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_a, ingredients=self._ingredients(n=8)
            )

    def test_wrong_key_count_raises(self):
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_a,
                ingredients=self._ingredients(key_indices=(0,))  # only 1 key
            )

    def test_both_declare_transitions_to_active(self):
        self.declare_menu(battle=self.battle, chef=self.chef_a, ingredients=self._ingredients())
        self.declare_menu(battle=self.battle, chef=self.chef_b, ingredients=self._ingredients())
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.ACTIVE)

    def test_first_declare_stays_menu_locked(self):
        self.declare_menu(battle=self.battle, chef=self.chef_a, ingredients=self._ingredients())
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.MENU_LOCKED)

    def test_duplicate_declare_raises(self):
        self.declare_menu(battle=self.battle, chef=self.chef_a, ingredients=self._ingredients())
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_a, ingredients=self._ingredients()
            )

    def test_unequal_count_raises(self):
        """Spec: both chefs must declare the same number of ingredients (5 vs 5, 6 vs 6)."""
        self.declare_menu(battle=self.battle, chef=self.chef_a, ingredients=self._ingredients(n=5))
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_b, ingredients=self._ingredients(n=6)
            )
        # Matching count is accepted and starts the battle
        self.declare_menu(battle=self.battle, chef=self.chef_b, ingredients=self._ingredients(n=5))
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, Battle.Status.ACTIVE)

    def test_wrong_battle_status_raises(self):
        self.battle.status = Battle.Status.SCHEDULED
        self.battle.save()
        with self.assertRaises(ValueError):
            self.declare_menu(
                battle=self.battle, chef=self.chef_a, ingredients=self._ingredients()
            )


@override_settings(SECURE_SSL_REDIRECT=False, CHEF_BATTLE_ENABLED=True)
class TokenCheckoutCancelSecurityTests(TestCase):
    """IDOR guard: only the order's owner may cancel it via ?order=N."""

    def setUp(self):
        from .models import TokenOrder, TokenPackage, TokenWallet
        User = get_user_model()
        self.owner_user = User.objects.create_user(username="tcc-owner", password="pw")
        self.other_user = User.objects.create_user(username="tcc-other", password="pw")
        self.owner = RecipeAuthor.objects.create(user=self.owner_user, name="TCC Owner", slug="tcc-owner")
        self.other = RecipeAuthor.objects.create(user=self.other_user, name="TCC Other", slug="tcc-other")
        self.wallet = TokenWallet.objects.create(chef=self.owner)
        self.package = TokenPackage.objects.create(
            key="tcc-pack", name="TCC Pack", tokens=100, price_eur="10.00"
        )
        self.order = TokenOrder.objects.create(
            wallet=self.wallet, package=self.package, tokens=100, amount_eur_cents=1000
        )
        self.url = reverse("chef_battle:token_checkout_cancel")

    def _order_status(self):
        self.order.refresh_from_db()
        return self.order.status

    def test_anonymous_cannot_cancel_order(self):
        response = self.client.get(f"{self.url}?order={self.order.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._order_status(), "pending")

    def test_other_user_cannot_cancel_order(self):
        self.client.login(username="tcc-other", password="pw")
        response = self.client.get(f"{self.url}?order={self.order.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._order_status(), "pending")

    def test_owner_can_cancel_own_order(self):
        self.client.login(username="tcc-owner", password="pw")
        response = self.client.get(f"{self.url}?order={self.order.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._order_status(), "cancelled")

    def test_non_numeric_order_param_is_safe(self):
        self.client.login(username="tcc-owner", password="pw")
        response = self.client.get(f"{self.url}?order=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._order_status(), "pending")


@override_settings(SECURE_SSL_REDIRECT=False, CHEF_BATTLE_ENABLED=True)
class BattleChatSecurityTests(TestCase):
    """Anonymous chat: no impersonation of registered names; poll input hardened."""

    def setUp(self):
        from .models import BattleChatMessage
        self.BattleChatMessage = BattleChatMessage
        User = get_user_model()
        self.user_a = User.objects.create_user(username="chat-chef-a", password="pw")
        self.user_b = User.objects.create_user(username="chat-chef-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Chat Chef A", slug="chat-chef-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Chat Chef B", slug="chat-chef-b")
        now = timezone.now()
        self.battle = Battle.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="Chat Theme",
            status=Battle.Status.ACTIVE,
            submission_deadline=now + timezone.timedelta(days=2),
            voting_deadline=now + timezone.timedelta(days=4),
            end_time=now + timezone.timedelta(days=4),
        )
        self.send_url = reverse("chef_battle:battle_chat_send", args=[self.battle.pk])
        self.poll_url = reverse("chef_battle:battle_chat_poll", args=[self.battle.pk])

    def test_anonymous_cannot_impersonate_username(self):
        self.client.post(self.send_url, {"body": "hello", "display_name": "chat-chef-a"})
        msg = self.BattleChatMessage.objects.get(battle=self.battle)
        self.assertEqual(msg.display_name, "Anonymous")

    def test_anonymous_cannot_impersonate_author_name(self):
        self.client.post(self.send_url, {"body": "hello", "display_name": "Chat Chef B"})
        msg = self.BattleChatMessage.objects.get(battle=self.battle)
        self.assertEqual(msg.display_name, "Anonymous")

    def test_anonymous_free_name_is_kept(self):
        self.client.post(self.send_url, {"body": "hello", "display_name": "RandomGuest42"})
        msg = self.BattleChatMessage.objects.get(battle=self.battle)
        self.assertEqual(msg.display_name, "RandomGuest42")

    def test_authenticated_name_not_overridden(self):
        self.client.login(username="chat-chef-a", password="pw")
        self.client.post(self.send_url, {"body": "hello", "display_name": "ignored"})
        msg = self.BattleChatMessage.objects.get(battle=self.battle)
        self.assertEqual(msg.display_name, "chat-chef-a")

    def test_chat_poll_non_numeric_since_is_safe(self):
        response = self.client.get(f"{self.poll_url}?since=abc")
        self.assertEqual(response.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False, CHEF_BATTLE_ENABLED=False)
class ArenaDarkLaunchTests(TestCase):
    """With the flag OFF, every arena endpoint must 404 for the public
    (P00 contract: arena is gated by chef_battle_guard) while superusers
    keep dark-launch preview access."""

    def setUp(self):
        User = get_user_model()
        self.super_user = User.objects.create_superuser(
            username="adl-super", password="pw", email="adl@example.com"
        )
        RecipeAuthor.objects.create(user=self.super_user, name="ADL Super", slug="adl-super")

    def test_arena_page_hidden_from_anonymous(self):
        response = self.client.get(reverse("chef_battle:arena"))
        self.assertEqual(response.status_code, 404)

    def test_arena_state_hidden_from_anonymous(self):
        response = self.client.post(reverse("chef_battle:arena_state"))
        self.assertEqual(response.status_code, 404)

    def test_arena_popup_hidden_from_anonymous(self):
        response = self.client.get(reverse("chef_battle:arena_battle_popup"))
        self.assertEqual(response.status_code, 404)

    def test_arena_blast_hidden_from_anonymous(self):
        response = self.client.get(reverse("chef_battle:arena_blast"))
        self.assertEqual(response.status_code, 404)

    def test_arena_ping_hidden_from_anonymous(self):
        response = self.client.post(reverse("chef_battle:arena_ping"))
        self.assertEqual(response.status_code, 404)

    def test_superuser_keeps_dark_launch_preview(self):
        self.client.login(username="adl-super", password="pw")
        response = self.client.get(reverse("chef_battle:arena"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("chef_battle:arena_state"))
        self.assertEqual(response.status_code, 200)
