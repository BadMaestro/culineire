from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor


class ContactPageLayoutTests(TestCase):
    def setUp(self):
        self.url = reverse("messaging:contact")
        self.user_model = get_user_model()

    def _create_owner(self):
        owner = self.user_model.objects.create_user(username="greenbear", password="pass")
        RecipeAuthor.objects.update_or_create(
            slug=settings.OWNER_SLUG,
            defaults={
                "user": owner,
                "name": "GreenBear",
            },
        )
        return owner

    def test_anonymous_contact_page_uses_contact_layout(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hero--contact')
        self.assertContains(response, 'class="contact-shell"')
        self.assertContains(response, 'class="contact-layout"')
        self.assertContains(response, 'class="contact-info-panel"')
        self.assertContains(response, 'class="contact-panel"')
        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, reverse("legal:legal_hub"))
        self.assertContains(response, reverse("legal:report_content"))

    def test_authenticated_contact_page_shows_message_form_when_owner_available(self):
        self._create_owner()
        user = self.user_model.objects.create_user(username="author", password="pass")
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="auth-form contact-form"')
        self.assertContains(response, 'id="id_subject"')
        self.assertContains(response, 'id="id_body"')
        self.assertContains(response, "Send Message")

    def test_owner_contact_page_links_to_inbox(self):
        owner = self._create_owner()
        self.client.force_login(owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You cannot send a message to yourself")
        self.assertContains(response, reverse("messaging:inbox"))


class InboxUsesCentralBattleVisibilityGateTests(TestCase):
    """F31, 2026-08-11: inbox() hand-rolled the same flag-or-staff check
    is_battle_visible() already centralizes for every other Chef Battle
    surface - not exploitable on its own (both arrived at the same answer),
    but a future edit to the real gate would silently stop reaching this
    copy. Confirms inbox() now defers to is_battle_visible() and keeps
    exactly the behaviour it always had."""

    def setUp(self):
        from chef_battle.models import Battle, BattleEvent

        User = get_user_model()
        self.plain_user = User.objects.create_user("f31-plain", password="pw")
        self.plain_author = RecipeAuthor.objects.create(
            user=self.plain_user, name="F31 Plain", slug="f31-plain")
        self.staff_user = User.objects.create_user("f31-staff", password="pw", is_staff=True)
        self.staff_author = RecipeAuthor.objects.create(
            user=self.staff_user, name="F31 Staff", slug="f31-staff")
        opponent = RecipeAuthor.objects.create(
            user=User.objects.create_user("f31-opp", password="pw"),
            name="F31 Opponent", slug="f31-opp")
        now = timezone.now()

        plain_battle = Battle.objects.create(
            challenger=self.plain_author, opponent=opponent, theme="F31 Plain Battle",
            status=Battle.Status.ACTIVE, start_time=now,
            submission_deadline=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
        )
        BattleEvent.objects.create(
            battle=plain_battle, actor=self.plain_author, target=opponent,
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            message="F31 plain event", is_public=True,
        )

        staff_battle = Battle.objects.create(
            challenger=self.staff_author, opponent=opponent, theme="F31 Staff Battle",
            status=Battle.Status.ACTIVE, start_time=now,
            submission_deadline=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
        )
        BattleEvent.objects.create(
            battle=staff_battle, actor=self.staff_author, target=opponent,
            event_type=BattleEvent.EventType.BATTLE_STARTED,
            message="F31 staff event", is_public=True,
        )

    @override_settings(CHEF_BATTLE_ENABLED=False)
    def test_plain_user_without_the_flag_sees_no_battle_section(self):
        self.client.login(username="f31-plain", password="pw")
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["battle_events"], [])

    @override_settings(CHEF_BATTLE_ENABLED=False)
    def test_staff_without_the_flag_still_sees_their_battle_events(self):
        self.client.login(username="f31-staff", password="pw")
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["battle_events"]), 1)

    @override_settings(CHEF_BATTLE_ENABLED=True)
    def test_plain_user_with_the_flag_on_sees_their_battle_events(self):
        self.client.login(username="f31-plain", password="pw")
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["battle_events"]), 1)
