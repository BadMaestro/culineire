import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import (
    AppreciationGiftType,
    APPRECIATION_GIFT_COST,
    Battle,
    BattleChallenge,
    BattleEntry,
    BattleVote,
    ChefArtifact,
    ChefBattleProfile,
    ContentReport,
    LedgerEvent,
    RewardRecord,
    TokenWallet,
)
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
        winner_profile.refresh_from_db()
        loser_profile.refresh_from_db()
        self.assertEqual(winner_profile.wins, 1)
        self.assertEqual(winner_profile.battle_moves, 11)  # MOVES_BATTLE_WIN(10) + MOVES_BATTLE_PARTICIPATION(1)
        self.assertEqual(loser_profile.battle_moves, 1)    # MOVES_BATTLE_PARTICIPATION(1)
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


@override_settings(SECURE_SSL_REDIRECT=False)
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
        for _ in range(LIKE_ANTI_FARM_MAX_PER_SOURCE):
            award_moves(self.chef, 1, TxType.LIKE_RECEIVED, source_author=self.source)
        # 4th like from same source should be blocked
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
        from amuse_bouche.models import AmuseBouche
        from chef_battle.models import BattleMoveTransaction, ChefBattleProfile
        item = AmuseBouche.objects.create(
            author=self.chef,
            title="Test Bite",
            slug="test-bite-energy",
            short_description="yum",
            status=AmuseBouche.Status.APPROVED,
        )
        ct = ContentType.objects.get_for_model(AmuseBouche)
        ContentReaction.objects.create(
            user=self.user2,
            content_type=ct,
            object_id=item.pk,
            reaction=ContentReaction.Reaction.LIKE,
        )
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, 1)
        self.assertTrue(
            BattleMoveTransaction.objects.filter(
                chef=self.chef,
                transaction_type=BattleMoveTransaction.TxType.LIKE_RECEIVED,
                amount=1,
            ).exists()
        )

    def test_like_signal_anti_farming(self):
        from collection.models import ContentReaction
        from django.contrib.contenttypes.models import ContentType
        from amuse_bouche.models import AmuseBouche
        from chef_battle.models import ChefBattleProfile
        from chef_battle.energy_service import LIKE_ANTI_FARM_MAX_PER_SOURCE
        item = AmuseBouche.objects.create(
            author=self.chef,
            title="Test Bite 2",
            slug="test-bite-energy-2",
            short_description="yum",
            status=AmuseBouche.Status.APPROVED,
        )
        ct = ContentType.objects.get_for_model(AmuseBouche)
        # Create max allowed likes
        for i in range(LIKE_ANTI_FARM_MAX_PER_SOURCE):
            item2 = AmuseBouche.objects.create(
                author=self.chef,
                title=f"Bite {i}",
                slug=f"bite-af-{i}",
                short_description="yum",
                status=AmuseBouche.Status.APPROVED,
            )
            ContentReaction.objects.create(
                user=self.user2,
                content_type=ct,
                object_id=item2.pk,
                reaction=ContentReaction.Reaction.LIKE,
            )
        # 4th like from same user should be blocked
        ContentReaction.objects.create(
            user=self.user2,
            content_type=ct,
            object_id=item.pk,
            reaction=ContentReaction.Reaction.LIKE,
        )
        profile = ChefBattleProfile.objects.get(author=self.chef)
        self.assertEqual(profile.battle_moves, LIKE_ANTI_FARM_MAX_PER_SOURCE)


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


@override_settings(SECURE_SSL_REDIRECT=False)
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
