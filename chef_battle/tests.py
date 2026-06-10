from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import Battle, BattleChallenge, BattleEntry, BattleVote
from .services import (
    accept_challenge,
    calculate_battle_result,
    expire_stale_challenges,
    handle_no_show_battles,
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
        self.assertEqual(battle.status, Battle.Status.ACTIVE)
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
        self.assertEqual(winner_profile.wins, 1)
        self.assertEqual(winner_profile.battle_moves, 6)  # MOVES_BATTLE_WIN(5) + MOVES_BATTLE_PARTICIPATION(1)
        self.assertEqual(loser_profile.battle_moves, 1)   # MOVES_BATTLE_PARTICIPATION(1)
        self.assertEqual(loser_profile.losses, 1)

    def test_vote_clean_allows_authenticated_user_without_author_profile(self):
        battle = accept_challenge(self._challenge())
        vote = BattleVote(battle=battle, voter=self.voter, voted_for=self.chef_a)

        vote.full_clean()

    def test_vote_clean_blocks_self_vote_for_linked_author(self):
        battle = accept_challenge(self._challenge())
        vote = BattleVote(battle=battle, voter=self.user_a, voted_for=self.chef_a)

        with self.assertRaises(ValidationError):
            vote.full_clean()


class ChefBattleAccessTests(TestCase):
    """Permission tests: anonymous users and non-admins see 404 when flag is off."""

    def setUp(self):
        User = get_user_model()
        self.client = Client()
        self.user = User.objects.create_user(username="regular", password="pw")
        self.staff = User.objects.create_user(username="staff", password="pw", is_staff=True)

    def test_anonymous_gets_404_on_battle_home(self):
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 404)

    def test_regular_user_gets_404_on_battle_home(self):
        self.client.login(username="regular", password="pw")
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 404)

    def test_staff_user_can_access_battle_home(self):
        self.client.login(username="staff", password="pw")
        response = self.client.get(reverse("chef_battle:home"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_gets_404_on_rankings(self):
        response = self.client.get(reverse("chef_battle:rankings"))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_gets_404_on_challenge_list(self):
        response = self.client.get(reverse("chef_battle:challenge_list"))
        # challenge_list redirects non-authenticated via @login_required to login;
        # anonymous users hit @chef_battle_guard first → 404
        self.assertEqual(response.status_code, 404)


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


class BattleTimerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="timer-a", password="pw")
        self.user_b = User.objects.create_user(username="timer-b", password="pw")
        self.chef_a = RecipeAuthor.objects.create(user=self.user_a, name="Timer A", slug="timer-a")
        self.chef_b = RecipeAuthor.objects.create(user=self.user_b, name="Timer B", slug="timer-b")

    def test_battle_has_7_day_window(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="7-day test",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        battle = accept_challenge(challenge)
        delta = battle.end_time - battle.start_time
        self.assertEqual(delta.days, 7)

    def test_submission_deadline_is_5_days(self):
        challenge = BattleChallenge.objects.create(
            challenger=self.chef_a,
            opponent=self.chef_b,
            theme="5-day sub test",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        battle = accept_challenge(challenge)
        delta = battle.submission_deadline - battle.start_time
        self.assertEqual(delta.days, 5)


class NotificationsPollViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="poll-user", password="pw", is_staff=True)
        self.client = Client()

    def test_poll_requires_login(self):
        url = reverse("chef_battle:notifications_poll")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)  # chef_battle_guard returns 404 for anon

    def test_poll_returns_json_for_staff(self):
        self.client.login(username="poll-user", password="pw")
        url = reverse("chef_battle:notifications_poll")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertIn("items", data)
