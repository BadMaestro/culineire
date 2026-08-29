from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from recipes.models import RecipeAuthor


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="forgetful", password="OldPass123!", email="forgetful@example.com"
        )

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("password_reset"))
        self.assertContains(response, "Forgot password?")

    def test_reset_form_page_renders(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset Password")

    def test_reset_request_sends_branded_email_with_working_link(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "forgetful@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reset your CulinEire password")
        self.assertIn("/accounts/reset/", message.body)
        # Extract the confirm link from the plain-text body and follow it
        reset_link = next(
            line for line in message.body.splitlines() if "/accounts/reset/" in line
        ).strip()
        path = "/" + reset_link.split("://", 1)[-1].split("/", 1)[1]
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set New Password")

    def test_reset_request_for_unknown_email_does_not_reveal_account_absence(self):
        response = self.client.post(
            reverse("password_reset"), {"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow_sets_new_password(self):
        self.client.post(reverse("password_reset"), {"email": "forgetful@example.com"})
        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "/accounts/reset/" in line
        ).strip()
        path = "/" + reset_link.split("://", 1)[-1].split("/", 1)[1]
        # Django redirects to a session-backed URL before showing the form
        response = self.client.get(path)
        form_url = response.url
        response = self.client.post(
            form_url,
            {"new_password1": "BrandNewPass456!", "new_password2": "BrandNewPass456!"},
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertTrue(
            self.client.login(username="forgetful", password="BrandNewPass456!")
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminSetPasswordTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="admin", password="AdminPass123!", email="admin@example.com"
        )
        self.member = user_model.objects.create_user(
            username="member", password="MemberPass123!", email="member@example.com"
        )
        self.author = RecipeAuthor.objects.create(
            name="Member Author", slug="member-author", user=self.member
        )
        self.url = reverse(
            "recipes:moderation_author_set_password", kwargs={"slug": self.author.slug}
        )

    def set_password(self, password1, password2=None):
        return self.client.post(
            self.url,
            {"new_password1": password1, "new_password2": password2 or password1},
        )

    def test_superuser_can_set_password_and_email_is_sent(self):
        self.client.force_login(self.admin)
        response = self.set_password("FreshSecret789!")
        self.assertRedirects(
            response,
            reverse(
                "recipes:moderation_author_edit", kwargs={"slug": self.author.slug}
            ),
        )
        self.assertTrue(
            self.client.login(username="member", password="FreshSecret789!")
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["member@example.com"])
        self.assertIn("FreshSecret789!", message.body)

    def test_regular_user_gets_404(self):
        self.client.force_login(self.member)
        response = self.set_password("FreshSecret789!")
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_set_password(self):
        response = self.set_password("FreshSecret789!")
        self.assertIn(response.status_code, (302, 404))
        self.assertFalse(
            self.client.login(username="member", password="FreshSecret789!")
        )

    def test_mismatched_passwords_rejected(self):
        self.client.force_login(self.admin)
        response = self.set_password("FreshSecret789!", "Different000!")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            self.client.login(username="member", password="FreshSecret789!")
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_weak_password_rejected(self):
        self.client.force_login(self.admin)
        response = self.set_password("123")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.client.login(username="member", password="123"))
        self.assertEqual(len(mail.outbox), 0)

    def test_superuser_may_target_other_superuser_but_not_owner(self):
        # Contract changed in ea6a599c: superusers may manage other superuser
        # accounts (regular moderators still cannot - covered by
        # test_regular_user_gets_404). The owner account stays untouchable.
        from django.conf import settings as django_settings

        other_admin = get_user_model().objects.create_superuser(
            username="admin2", password="AdminPass123!", email="admin2@example.com"
        )
        peer_author = RecipeAuthor.objects.create(
            name="Admin Author", slug="admin-author", user=other_admin
        )
        self.client.force_login(self.admin)
        url = reverse(
            "recipes:moderation_author_set_password",
            kwargs={"slug": peer_author.slug},
        )
        response = self.client.post(
            url, {"new_password1": "FreshSecret789!", "new_password2": "FreshSecret789!"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.client.login(username="admin2", password="FreshSecret789!")
        )

        # The owner (OWNER_SLUG) is always protected, even from superusers.
        owner_user = get_user_model().objects.create_superuser(
            username="owner-test", password="OwnerPass123!", email="owner@example.com"
        )
        # A data migration may already have created the owner author row.
        owner_author, _ = RecipeAuthor.objects.update_or_create(
            slug=django_settings.OWNER_SLUG,
            defaults={"name": "Owner", "user": owner_user},
        )
        self.client.force_login(self.admin)
        url = reverse(
            "recipes:moderation_author_set_password",
            kwargs={"slug": owner_author.slug},
        )
        response = self.client.post(
            url, {"new_password1": "FreshSecret789!", "new_password2": "FreshSecret789!"}
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_section_visible_on_moderation_edit_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("recipes:moderation_author_edit", kwargs={"slug": self.author.slug})
        )
        self.assertContains(response, "Admin: Set New Password")
        self.assertContains(response, self.url)


class LoginCsrfRecoveryTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_stale_login_post_redirects_to_a_fresh_form(self):
        response = self.client.post(
            reverse("login"),
            {"username": "someone", "password": "not-logged"},
        )
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)

        refreshed = self.client.get(reverse("login"))
        self.assertContains(refreshed, "That sign-in form expired")
        self.assertContains(refreshed, "csrfmiddlewaretoken")

    def test_other_csrf_failures_remain_forbidden(self):
        response = self.client.post(reverse("ajax_login"), {})
        self.assertEqual(response.status_code, 403)

    def test_login_form_prevents_a_second_browser_submission(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "data-login-form")
        self.assertContains(response, "button.disabled = true")


class CaseInsensitiveLoginTests(TestCase):
    """The username is one name however it is capitalised (Owner, 2026-07-29)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="CrestedTen", password="RealPass123!", email="ct@example.com"
        )

    def test_sign_in_works_in_any_capitalisation(self):
        for typed in ("CrestedTen", "crestedten", "CRESTEDTEN", "CrEsTeDtEn"):
            with self.subTest(typed=typed):
                self.client.logout()
                response = self.client.post(
                    reverse("login"),
                    {"username": typed, "password": "RealPass123!"},
                )
                self.assertEqual(response.status_code, 302, f"{typed} was refused")
                self.assertEqual(
                    self.client.session["_auth_user_id"], str(self.user.pk)
                )

    def test_ajax_sign_in_works_in_any_capitalisation(self):
        response = self.client.post(
            reverse("ajax_login"),
            {"username": "crestedten", "password": "RealPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_the_password_stays_case_sensitive(self):
        response = self.client.post(
            reverse("login"),
            {"username": "crestedten", "password": "realpass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_wrong_name_is_still_refused(self):
        response = self.client.post(
            reverse("login"),
            {"username": "crestedeleven", "password": "RealPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_inactive_account_cannot_sign_in_by_changing_case(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("login"),
            {"username": "crestedten", "password": "RealPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_stored_username_keeps_its_original_case(self):
        self.client.post(
            reverse("login"), {"username": "crestedten", "password": "RealPass123!"}
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "CrestedTen")

    def test_signup_refuses_a_username_that_differs_only_in_case(self):
        from accounts.forms import SignUpForm

        form = SignUpForm(data={
            "username": "crestedten",
            "email": "someone.else@example.com",
            "default_avatar": RecipeAuthor.DefaultAvatar.NEUTRAL,
            "password1": "AnotherPass123!",
            "password2": "AnotherPass123!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_signup_still_accepts_a_genuinely_new_username(self):
        from accounts.forms import SignUpForm

        form = SignUpForm(data={
            "username": "CrestedEleven",
            "email": "eleven@example.com",
            "default_avatar": RecipeAuthor.DefaultAvatar.NEUTRAL,
            "password1": "AnotherPass123!",
            "password2": "AnotherPass123!",
        })
        self.assertTrue(form.is_valid(), form.errors)


class AvatarGalleryIsAChoiceNeverAnAssignmentTests(TestCase):
    """The Owner, 2026-08-17.

    He asked for the site's 96 generated portraits to be used for authors with
    no photograph, picked by the gender chosen at registration. Then he stopped
    it himself, and the reason governs this whole feature: the portraits are
    realistic and carry racial features, skin colour and age, and we have no
    right to attribute those to a real person.

    So the gallery ships as a door the person opens: a "More portraits" button
    on the registration form. Nothing may ever write gallery_avatar for him.
    """

    def _payload(self, **extra):
        data = {
            "username": "GalleryUser",
            "email": "gallery@example.com",
            "default_avatar": RecipeAuthor.DefaultAvatar.NEUTRAL,
            "password1": "AnotherPass123!",
            "password2": "AnotherPass123!",
        }
        data.update(extra)
        return data

    def test_a_new_author_is_given_no_portrait_at_all(self):
        """The whole point. Signing up without opening the gallery leaves the
        field empty, and the illustration the person picked stands."""
        from accounts.forms import SignUpForm

        form = SignUpForm(data=self._payload())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["gallery_avatar"], "")

    def test_a_portrait_the_person_picked_is_kept(self):
        from accounts.forms import SignUpForm

        form = SignUpForm(data=self._payload(gallery_avatar="face-37"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["gallery_avatar"], "face-37")

    def test_a_hand_made_post_cannot_write_an_arbitrary_string(self):
        """The field is hidden, which makes it exactly as editable as any other
        thing a client sends. An unchecked value would render as a broken image
        on every page the author appears on."""
        from accounts.forms import SignUpForm

        for bad in ("face-97", "face-00", "../../etc/passwd", "male-avatar", "face-1"):
            form = SignUpForm(data=self._payload(gallery_avatar=bad))
            self.assertFalse(form.is_valid(), f"{bad!r} was accepted")
            self.assertIn("gallery_avatar", form.errors)

    def test_the_chosen_portrait_outranks_the_illustration_but_not_a_photograph(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user("galleryauthor", password="pw")
        author = RecipeAuthor.objects.create(
            user=user, name="Gallery Author", slug="gallery-author",
            default_avatar=RecipeAuthor.DefaultAvatar.NEUTRAL,
        )
        self.assertIn("neutral-avatar", author.display_avatar_url)

        author.gallery_avatar = "face-12"
        author.save(update_fields=["gallery_avatar"])
        self.assertIn("crowd/face-12", author.display_avatar_url)

    def test_a_stale_key_falls_back_instead_of_raising(self):
        """A row written before a portrait was removed must not turn a profile
        page into a 500."""
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user("staleauthor", password="pw")
        author = RecipeAuthor.objects.create(
            user=user, name="Stale", slug="stale-author",
            default_avatar=RecipeAuthor.DefaultAvatar.FEMALE,
            gallery_avatar="face-99",
        )
        self.assertIn("female-avatar", author.display_avatar_url)

    def test_the_gallery_is_offered_on_the_registration_page(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("avatar-gallery-open", body)
        self.assertIn("More portraits", body)
        self.assertIn("js/avatar_gallery.js", body)
        # Every portrait is offered, and the count is the named set's, not a
        # glob over whatever happens to be on this machine's disk.
        from recipes.avatar_gallery import GALLERY_COUNT
        self.assertEqual(body.count('data-avatar-key="face-'), GALLERY_COUNT)

    def test_no_template_comment_leaks_onto_the_page(self):
        """v2.5.1137 shipped a two-line {# ... #} to production and the Owner
        read my note to myself sitting in the middle of his registration form.

        Django's {# #} is SINGLE-LINE: the opener is not matched across a
        newline, so a wrapped comment renders as text. Multi-line notes must use
        {% comment %}. This asserts the rendered page, not the file, because the
        file looked perfectly reasonable both times.
        """
        body = self.client.get(reverse("signup")).content.decode()
        self.assertNotIn("{#", body)
        self.assertNotIn("#}", body)

    def test_the_gallery_dialog_outranks_the_site_header(self):
        """It shipped at z-index 60 against a header at 120, so the dialog opened
        UNDERNEATH the navigation: the backdrop dimmed the page but not the
        header, and the panel's own title and close button sat behind the logo.

        Asserted as a comparison against the header's real value rather than a
        hard-coded number, so raising the header later fails here instead of
        silently burying the dialog again.
        """
        from pathlib import Path
        import re

        from django.conf import settings as django_settings

        css_dir = Path(django_settings.BASE_DIR) / "static" / "css"
        auth_css = (css_dir / "auth.css").read_text(encoding="utf-8")
        header_css = (css_dir / "header.css").read_text(encoding="utf-8")

        block = auth_css[auth_css.index(".auth-avatar-modal {"):]
        block = block[:block.index("}")]
        dialog_z = int(re.search(r"z-index:\s*(\d+)", block).group(1))

        highest_header_z = max(
            int(value) for value in re.findall(r"z-index:\s*(\d+)", header_css)
        )
        self.assertGreater(dialog_z, highest_header_z)


class BearseekerAdminTierTests(TestCase):
    """The tier and the staff bit are one thing, not two.

    AGENTS.md section 20, the Owner's model of 2026-08-04: AUTHORS are
    `is_staff` False; (Bear)seeker Admins and (Bear)seeker Super Users are
    `is_staff` True. The moderation panel groups people by
    `has_bearseeker_privileges` and never reads `is_staff`, so for the whole
    life of the "Grant (Bear)seeker Privileges" action an Admin got the label
    and not the flag - while "Grant Superuser" set both. Both of this site's
    Admins were `is_staff` False, which is how they lost the Arena when the gate
    started reading the staff bit.

    These tests pin the two halves together so the panel cannot produce a tier
    that does not exist again.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from recipes.models import RecipeAuthor

        User = get_user_model()
        # A superuser grantor, NOT the owner account: `greenbear` is seeded by a
        # migration, so creating it here collides on the slug - and section 18
        # says his account is not a fixture to be conjured in a test anyway.
        # can_grant_bearseeker_privileges accepts any superuser.
        self.owner_user = User.objects.create_user(
            "tier-grantor", password="pw", is_staff=True, is_superuser=True
        )
        RecipeAuthor.objects.create(
            user=self.owner_user, name="Grantor", slug="tier-grantor"
        )
        self.target_user = User.objects.create_user("tier-target", password="pw")
        self.target = RecipeAuthor.objects.create(
            user=self.target_user, name="Tier Target", slug="tier-target"
        )
        self.url = reverse("accounts:manage_author", args=[self.target.slug])

    def _act(self, action):
        self.client.force_login(self.owner_user)
        return self.client.post(self.url, {"action": action})

    def test_granting_admin_also_grants_the_staff_bit(self):
        self.assertFalse(self.target_user.is_staff)
        self._act("grant_bearseeker")
        self.target.refresh_from_db()
        self.target_user.refresh_from_db()
        self.assertTrue(self.target.has_bearseeker_privileges)
        self.assertTrue(
            self.target_user.is_staff,
            "an Admin without is_staff is a label without a tier - AGENTS.md 20",
        )
        self.assertFalse(self.target_user.is_superuser, "admin is not a superuser")

    def test_revoking_admin_takes_the_staff_bit_back(self):
        self._act("grant_bearseeker")
        self._act("revoke_bearseeker")
        self.target.refresh_from_db()
        self.target_user.refresh_from_db()
        self.assertFalse(self.target.has_bearseeker_privileges)
        self.assertFalse(
            self.target_user.is_staff,
            "revoked back to AUTHOR, so the staff bit goes with the tier",
        )

    def test_a_granted_admin_can_see_chef_battles(self):
        """The whole point of the flag, and the reason this was found."""
        from django.test import RequestFactory
        from chef_battle.access import is_battle_visible

        request = RequestFactory().get("/chef-battle/arena/")
        request.user = self.target_user
        with override_settings(CHEF_BATTLE_ENABLED=False):
            self.assertFalse(is_battle_visible(request))
            self._act("grant_bearseeker")
            self.target_user.refresh_from_db()
            request.user = self.target_user
            self.assertTrue(is_battle_visible(request))


class SignInStaysVisibleInTheBurgerMenuTests(TestCase):
    """Owner, 2026-08-29: hovering Sign In in the collapsed menu made it vanish.

    The drawer paints its rows cream on a dark panel. Every row in it is a
    `.ce-nav__link` EXCEPT Sign In, which is a `.ce-nav__text` - so on hover it
    fell through to the header's own `.ce-nav__text:hover { color: #3a2c1e }`,
    a dark brown written for the cream desktop bar. Dark brown on a dark panel
    is invisible, and the row also carried `opacity: 0.75`, which dimmed it
    further at the exact moment it was being pointed at.

    IT WAS A TIE BROKEN BY SOURCE ORDER, which is why nothing caught it:
    `.ce-nav--open .ce-nav__text` and `.ce-nav__text:hover` are both (0,2,0),
    so the lower rule in the file wins and the desktop one is 140 lines lower.

    This asserts the fix by CONTRAST rather than by spelling: whatever colour
    the drawer's hover state ends up being, it must be a light one, because the
    panel behind it is dark."""

    @staticmethod
    def _rules(css, needle):
        """Rules whose selector mentions `needle`, comments stripped first.

        The comment above the touch rules says "iOS doesn't reliably fire
        :hover", and a scan that keeps comments reads that prose as part of
        the next selector - so this guard passed on the broken stylesheet
        the first time it was run. Four other guards in this codebase have
        been fooled by their own comments the same way."""
        import re

        css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
        out = []
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            head = " ".join(match.group(1).split())
            if needle in head:
                out.append((head, match.group(2)))
        return out

    def _css(self):
        from pathlib import Path

        from django.conf import settings as django_settings

        return (Path(django_settings.BASE_DIR) / "static" / "css"
                / "header.css").read_text(encoding="utf-8")

    def test_the_drawer_lights_the_row_it_is_pointing_at(self):
        css = self._css()
        lit = [
            body for head, body in self._rules(css, ".ce-nav--open")
            if ".ce-nav__text:hover" in head
        ]
        self.assertTrue(
            lit,
            "no rule lights a .ce-nav__text on hover inside the open drawer, "
            "so Sign In falls through to the desktop bar's dark brown",
        )
        self.assertTrue(
            any("#fff" in body or "247 242 234" in body for body in lit),
            f"the drawer's hover colour is not a light one: {lit}",
        )

    def test_sign_in_is_not_dimmed_while_it_is_hovered(self):
        css = self._css()
        hovered = [
            body for head, body in self._rules(css, ".ce-nav--open")
            if ":hover" in head and ("login" in head or "signin" in head)
        ]
        self.assertTrue(hovered, "Sign In has no hover rule in the drawer")
        self.assertTrue(
            any("opacity: 1" in body for body in hovered),
            "Sign In rests at opacity 0.75 and nothing lifts it on hover",
        )
