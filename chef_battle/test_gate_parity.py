from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings

from chef_battle.access import is_battle_visible
from config.context_processors import battle_widget_context
from recipes.models import RecipeAuthor


@override_settings(CHEF_BATTLE_ENABLED=False)
class ChefBattleGateParityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.request_factory = RequestFactory()

        self.plain_author_user = user_model.objects.create_user(
            username="gate-parity-plain-author",
        )
        RecipeAuthor.objects.create(
            user=self.plain_author_user,
            name="Gate Parity Plain Author",
            slug="gate-parity-plain-author",
        )

        self.bearseeker_user = user_model.objects.create_user(
            username="gate-parity-bearseeker",
        )
        RecipeAuthor.objects.create(
            user=self.bearseeker_user,
            name="Gate Parity Bearseeker",
            slug="gate-parity-bearseeker",
            has_bearseeker_privileges=True,
        )

        self.staff_user = user_model.objects.create_user(
            username="gate-parity-staff",
            is_staff=True,
        )

        self.superuser = user_model.objects.create_user(
            username="gate-parity-superuser",
            is_staff=True,
            is_superuser=True,
        )

    def test_widget_visibility_matches_page_access(self):
        """The Owner's three tiers, 2026-08-04, separated by `is_staff`.

        AUTHOR is_staff False; (Bear)seeker Admin and (Bear)seeker Super User
        is_staff True. AGENTS.md section 20.

        These expectations moved twice in one day and both moves are worth
        keeping. They first asserted that a bearseeker author gets in, which was
        green while contradicting the contract. Then they asserted superuser
        ONLY, which was too narrow - it read "only a Super User sees the WHOLE
        application" as "nobody below sees any of it", and the Owner corrected
        it the same hour. What separates the tiers is the staff bit, not the
        moderator flag and not superuser.
        """
        users = {
            "anonymous": (AnonymousUser(), False),
            "AUTHOR": (self.plain_author_user, False),
            # The moderator flag ALONE is not the tier. An account carrying it
            # without is_staff is what the panel's grant action used to produce,
            # and it is not an Admin - it is an Author wearing a label.
            "moderator flag but no staff bit": (self.bearseeker_user, False),
            # (Bear)seeker Admin as the panel now creates one.
            "staff": (self.staff_user, True),
            # (Bear)seeker Super User.
            "superuser": (self.superuser, True),
        }

        for label, (user, expected) in users.items():
            with self.subTest(user=label):
                request = self.request_factory.get("/")
                request.user = user

                shown = bool(battle_widget_context(request))
                allowed_in = is_battle_visible(request)
                if shown and not allowed_in:
                    direction = "shown the entrance but denied access"
                elif allowed_in and not shown:
                    direction = "allowed access but entrance hidden"
                else:
                    direction = "gates agree"

                self.assertEqual(
                    shown,
                    allowed_in,
                    f"{label}: {direction}",
                )
                self.assertEqual(
                    shown,
                    expected,
                    f"{label}: both gates returned {shown}, expected {expected}",
                )
