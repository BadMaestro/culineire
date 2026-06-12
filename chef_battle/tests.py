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
