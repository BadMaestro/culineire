from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import Battle, BattleChallenge, BattleVote
from .services import accept_challenge, calculate_battle_result, refuse_challenge


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
        self.assertEqual(winner_profile.battle_moves, 3)
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
