from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from articles.models import Article
from presence.models import MaintenanceNote
from recipes.models import Recipe, RecipeAuthor


@override_settings(SITE_DOMAIN="culineire.test", SITE_SCHEME="https")
class PublicTechnicalPagesTests(TestCase):
    def test_uploaded_media_uses_web_readable_permissions(self):
        self.assertEqual(settings.FILE_UPLOAD_PERMISSIONS, 0o644)
        self.assertEqual(settings.FILE_UPLOAD_DIRECTORY_PERMISSIONS, 0o755)

    def test_about_and_privacy_pages_are_public(self):
        for url_name in ("about", "privacy"):
            response = self.client.get(reverse(url_name))

            self.assertEqual(response.status_code, 200)

    def test_about_page_uses_story_layout(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hero--about')
        self.assertContains(response, 'class="about-story"')
        self.assertContains(response, 'class="about-story__summary"')
        self.assertContains(response, 'class="about-story__mobile-jump"')
        self.assertContains(response, 'class="about-story__layout"')
        self.assertContains(response, 'class="about-story__toc"')
        self.assertContains(response, "Keep Irish cooking useful, findable and alive.")
        self.assertNotContains(response, "data-about-deck")
        self.assertNotContains(response, "about-deck__viewport")

    def test_base_template_loads_desktop_hero_chef_assets(self):
        response = self.client.get(reverse("about"))

        self.assertContains(response, 'css/hero_chef')
        self.assertContains(response, 'js/hero_chef')

        css_path = settings.BASE_DIR / "static" / "css" / "hero_chef.css"
        self.assertIn("display: block;", css_path.read_text(encoding="utf-8"))

    def test_hero_chef_promotions_link_latest_public_content_and_sponsor(self):
        from sponsors.models import SponsorCell

        author = RecipeAuthor.objects.create(name="Chef Promoter", slug="chef-promoter")
        recipe = Recipe.objects.create(
            title="Newest Recipe",
            slug="newest-recipe",
            author=author,
            ingredients="One ingredient",
            method="Cook it",
            status=Recipe.Status.APPROVED,
        )
        article = Article.objects.create(
            title="Newest Article",
            slug="newest-article",
            author=author,
            body="Article body",
            published=date.today(),
            status=Article.Status.APPROVED,
        )
        SponsorCell.objects.create(
            cell_number=1,
            ring=0,
            position_in_ring=0,
            status=SponsorCell.Status.ACTIVE,
            sponsor_name="Kitchen Partner",
            sponsor_url="https://sponsor.example/",
        )
        cache.delete("hero_chef_promotions_v1")

        response = self.client.get(reverse("about"))
        promotions = response.context["hero_chef_promotions"]
        promotions_by_text = {item["text"]: item["url"] for item in promotions}

        self.assertEqual(
            promotions_by_text["Have you read our latest article yet?"],
            article.get_absolute_url(),
        )
        self.assertEqual(
            promotions_by_text["Have you seen our latest recipe yet?"],
            recipe.get_absolute_url(),
        )
        self.assertEqual(
            promotions_by_text[
                "Our sponsor this month is Kitchen Partner, A huge thank you for their support!"
            ],
            "https://sponsor.example/",
        )
        self.assertEqual(
            promotions_by_text["I don’t accept tips! Want to thank me?"],
            "https://buymeacoffee.com/bearcave",
        )

    def test_robots_txt_points_to_sitemap_and_blocks_private_paths(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /messages/")
        self.assertContains(response, "Sitemap: https://culineire.test/sitemap.xml")

    def test_sitemap_contains_public_approved_content_only(self):
        author = RecipeAuthor.objects.create(
            name="Public Author",
            slug="public-author",
        )
        approved_recipe = Recipe.objects.create(
            title="Approved Recipe",
            author=author,
            ingredients="Potatoes",
            method="Cook",
            status=Recipe.Status.APPROVED,
        )
        Recipe.objects.create(
            title="Pending Recipe",
            author=author,
            ingredients="Potatoes",
            method="Wait",
            status=Recipe.Status.PENDING,
        )
        Recipe.objects.create(
            title="Draft Recipe",
            author=author,
            ingredients="Potatoes",
            method="Draft",
            status=Recipe.Status.DRAFT,
        )
        Recipe.objects.create(
            title="Rejected Recipe",
            author=author,
            ingredients="Potatoes",
            method="Fix",
            status=Recipe.Status.REJECTED,
        )
        Recipe.objects.create(
            title="Needs Changes Recipe",
            author=author,
            ingredients="Potatoes",
            method="Revise",
            status=Recipe.Status.NEEDS_CHANGES,
        )
        approved_article = Article.objects.create(
            title="Approved Article",
            slug="approved-article",
            author=author,
            body="Published article body",
            published=date(2026, 5, 10),
            status=Article.Status.APPROVED,
        )
        Article.objects.create(
            title="Pending Article",
            slug="pending-article",
            author=author,
            body="Pending article body",
            published=date(2026, 5, 10),
            status=Article.Status.PENDING,
        )
        Article.objects.create(
            title="Draft Article",
            slug="draft-article",
            author=author,
            body="Draft article body",
            published=date(2026, 5, 10),
            status=Article.Status.DRAFT,
        )
        Article.objects.create(
            title="Rejected Article",
            slug="rejected-article",
            author=author,
            body="Rejected article body",
            published=date(2026, 5, 10),
            status=Article.Status.REJECTED,
        )
        Article.objects.create(
            title="Needs Changes Article",
            slug="needs-changes-article",
            author=author,
            body="Needs changes article body",
            published=date(2026, 5, 10),
            status=Article.Status.NEEDS_CHANGES,
        )

        response = self.client.get(reverse("sitemap_xml"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertContains(response, "https://culineire.test/")
        self.assertContains(response, f"https://culineire.test{approved_recipe.get_absolute_url()}")
        self.assertContains(response, f"https://culineire.test{approved_article.get_absolute_url()}")
        self.assertNotContains(response, "Pending Recipe")
        self.assertNotContains(response, "Draft Recipe")
        self.assertNotContains(response, "Rejected Recipe")
        self.assertNotContains(response, "Needs Changes Recipe")
        self.assertNotContains(response, "pending-article")
        self.assertNotContains(response, "draft-article")
        self.assertNotContains(response, "rejected-article")
        self.assertNotContains(response, "needs-changes-article")


class MaintenanceModeTests(TestCase):
    @override_settings(
        MAINTENANCE_MODE=True,
        MAINTENANCE_UNTIL="2026-05-20T18:00:00+01:00",
        MAINTENANCE_RETRY_AFTER_SECONDS=10800,
    )
    def test_public_pages_show_maintenance_response(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertTemplateUsed(response, "maintenance.html")
        self.assertContains(response, "Kitchen Closed for a Deep Clean", status_code=503)
        self.assertEqual(response.headers["Retry-After"], "10800")
        self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(MAINTENANCE_MODE=True)
    def test_static_paths_are_not_blocked_by_maintenance_mode(self):
        response = self.client.get("/static/css/base.css")

        self.assertNotEqual(response.status_code, 503)

    @override_settings(MAINTENANCE_MODE=True)
    def test_telegram_link_preview_can_fetch_public_pages_during_maintenance(self):
        response = self.client.get(
            reverse("about"),
            HTTP_USER_AGENT="TelegramBot (like TwitterBot)",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Kitchen Closed for a Deep Clean")

    @override_settings(MAINTENANCE_MODE=False)
    def test_site_uses_normal_response_when_maintenance_disabled(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Kitchen Closed for a Deep Clean")

    @override_settings(MAINTENANCE_MODE=True)
    def test_visitors_can_leave_visible_maintenance_notes(self):
        response = self.client.post(
            reverse("maintenance_note_create"),
            {"display_name": "Aoife", "message": "I was here."},
            REMOTE_ADDR="203.0.113.10",
            HTTP_USER_AGENT="Test browser",
        )

        self.assertEqual(response.status_code, 302)
        note = MaintenanceNote.objects.get()
        self.assertEqual(note.display_name, "Aoife")
        self.assertEqual(note.message, "I was here.")
        self.assertTrue(note.ip_hash)

        response = self.client.get("/")
        self.assertContains(response, "Aoife", status_code=503)
        self.assertContains(response, "I was here.", status_code=503)

    @override_settings(MAINTENANCE_MODE=True)
    def test_visitors_can_reply_to_maintenance_notes(self):
        parent = MaintenanceNote.objects.create(display_name="First", message="Waiting outside.")

        self.client.post(
            reverse("maintenance_note_create"),
            {"parent_id": str(parent.id), "display_name": "Second", "message": "Same here."},
        )

        reply = MaintenanceNote.objects.get(parent=parent)
        self.assertEqual(reply.display_name, "Second")
        self.assertEqual(reply.message, "Same here.")

        response = self.client.get("/")
        self.assertContains(response, "Waiting outside.", status_code=503)
        self.assertContains(response, "Same here.", status_code=503)


    @override_settings(MAINTENANCE_MODE=True)
    def test_maintenance_note_honeypot_drops_spam(self):
        self.client.post(
            reverse("maintenance_note_create"),
            {"display_name": "Spam", "message": "Buy now", "website": "https://example.test"},
        )

        self.assertFalse(MaintenanceNote.objects.exists())

    @override_settings(MAINTENANCE_MODE=True)
    def test_maintenance_notes_are_rate_limited_by_ip_hash(self):
        for index in range(6):
            self.client.post(
                reverse("maintenance_note_create"),
                {"message": f"Note {index}"},
                REMOTE_ADDR="203.0.113.44",
            )

        self.assertEqual(MaintenanceNote.objects.count(), 5)

    @override_settings(MAINTENANCE_MODE=False)
    def test_maintenance_note_post_is_closed_when_site_is_live(self):
        response = self.client.post(reverse("maintenance_note_create"), {"message": "Hello"})

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(MaintenanceNote.objects.exists())


class CanonicalHostRedirectMiddlewareTests(TestCase):
    @override_settings(
        CANONICAL_HOST_REDIRECT=True,
        SITE_DOMAIN="culineire.ie",
        SITE_SCHEME="https",
        ALLOWED_HOSTS=["culineire.ie", "www.culineire.ie"],
    )
    def test_www_host_redirects_to_canonical_apex_host(self):
        response = self.client.get(
            "/recipes/?page=2",
            SERVER_NAME="www.culineire.ie",
            SERVER_PORT=443,
            secure=True,
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://culineire.ie/recipes/?page=2")

    @override_settings(
        CANONICAL_HOST_REDIRECT=True,
        SITE_DOMAIN="culineire.ie",
        SITE_SCHEME="https",
        ALLOWED_HOSTS=["culineire.ie", "www.culineire.ie"],
    )
    def test_canonical_apex_host_does_not_redirect(self):
        response = self.client.get("/", SERVER_NAME="culineire.ie", SERVER_PORT=443, secure=True)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        CANONICAL_HOST_REDIRECT=True,
        SITE_DOMAIN="culineire.ie",
        SITE_SCHEME="https",
        SECURE_SSL_REDIRECT=False,
        ALLOWED_HOSTS=["127.0.0.1", "localhost", "culineire.ie"],
    )
    def test_loopback_hosts_are_not_canonical_redirected(self):
        response = self.client.get("/", SERVER_NAME="localhost", SERVER_PORT=8000)

        self.assertEqual(response.status_code, 200)


class SecurityHeaderTests(TestCase):
    def test_html_responses_include_security_headers(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self' 'nonce-", csp)
        self.assertIn("https://challenges.cloudflare.com", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("form-action 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")


class TemplateCommentHygieneTests(TestCase):
    """A multi-line {# #} is not a comment — it is page text.

    Django's short comment closes at the end of its own line. Spread one over
    several lines and every line lands in the rendered HTML. That is how three
    lines of a developer note about the battle-start banner ended up printed
    under the footer of the live site, spotted by the owner on a phone on
    2026-07-20. The rule cannot be "remember it", because it looks correct in
    every editor — so it is asserted here instead.
    """

    def test_no_multiline_short_comments_in_templates(self):
        from pathlib import Path

        from django.conf import settings

        offenders = []
        roots = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
        for root in roots:
            for path in root.rglob("*.html"):
                for number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if "{#" not in line:
                        continue
                    # Everything after the opening marker has to close on the
                    # same line; a bare "{#" leaks the lines that follow it.
                    if "#}" not in line.split("{#", 1)[1]:
                        offenders.append(f"{path}:{number}: {line.strip()[:70]}")

        self.assertEqual(
            offenders,
            [],
            "Multi-line {# #} renders as visible page text. Use "
            "{% comment %}...{% endcomment %}:\n" + "\n".join(offenders),
        )
