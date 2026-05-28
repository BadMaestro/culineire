from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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
