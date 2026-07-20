"""The arrival announcement belongs to one account.

GreenBear announcing himself to the site is the owner's own privilege. It had
been widened at some point to fire for staff, superusers and bearseekers too, so
a bearseeker signing in raised the same popup the owner only ever expected to
see for himself — from the outside, indistinguishable from someone signing in as
him.

Nothing guarded it: this module had no tests at all, which is why the rule could
drift without anyone noticing. These are that guard.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from presence.models import PresenceEvent
from recipes.models import RecipeAuthor


# A slug of this test's own: the real owner's author row already
# exists in the database, and this is about the RULE, not the name.
@override_settings(OWNER_SLUG="test-owner-slug")
class PresenceEventOwnerOnlyTests(TestCase):
    def _user(self, username, slug, **flags):
        user = get_user_model().objects.create_user(username=username, password="pw", **flags)
        if slug:
            RecipeAuthor.objects.create(user=user, name=username, slug=slug,
                                        has_bearseeker_privileges=flags.pop("bearseeker", False))
        return user

    def test_the_owner_announces_himself(self):
        owner = self._user("owner-acct", "test-owner-slug")
        self.assertEqual(PresenceEvent.resolve_event_type(owner), PresenceEvent.OWNER)
        self.assertIsNotNone(PresenceEvent.fire(owner))

    def test_a_bearseeker_does_not(self):
        """This is the case the owner caught: a bearseeker raised his popup."""
        user = self._user("seeker", "seeker")
        author = user.recipe_author_profile
        author.has_bearseeker_privileges = True
        author.save(update_fields=["has_bearseeker_privileges"])
        self.assertIsNone(PresenceEvent.resolve_event_type(user))
        self.assertIsNone(PresenceEvent.fire(user))

    def test_staff_and_superusers_do_not(self):
        staff = self._user("staffer", "staffer", is_staff=True)
        boss = self._user("super", "super", is_superuser=True)
        for user in (staff, boss):
            self.assertIsNone(PresenceEvent.resolve_event_type(user), user.username)
            self.assertIsNone(PresenceEvent.fire(user), user.username)

    def test_a_plain_member_does_not(self):
        member = self._user("member", "member")
        self.assertIsNone(PresenceEvent.resolve_event_type(member))

    def test_an_anonymous_visitor_does_not(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(PresenceEvent.resolve_event_type(AnonymousUser()))
        self.assertIsNone(PresenceEvent.resolve_event_type(None))

    def test_nothing_but_the_owner_ever_writes_a_row(self):
        """The table is what the site polls; one stray row is one stray popup."""
        self._user("seeker2", "seeker2")
        self._user("staffer2", "staffer2", is_staff=True)
        for user in get_user_model().objects.all():
            PresenceEvent.fire(user)
        self.assertEqual(PresenceEvent.objects.count(), 0)

        owner = self._user("owner2", "test-owner-slug")
        PresenceEvent.fire(owner)
        self.assertEqual(
            list(PresenceEvent.objects.values_list("event_type", flat=True)),
            [PresenceEvent.OWNER],
        )
