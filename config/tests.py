from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from articles.models import Article
from presence.models import MaintenanceNote
from recipes.models import Recipe, RecipeAuthor


@override_settings(SITE_DOMAIN="culineire.test", SITE_SCHEME="https")
class PublicTechnicalPagesTests(TestCase):
    def test_about_and_privacy_pages_are_public(self):
        for url_name in ("about", "privacy"):
            response = self.client.get(reverse(url_name))

            self.assertEqual(response.status_code, 200)

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

        response = self.client.get(reverse("sitemap_xml"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertContains(response, "https://culineire.test/")
        self.assertContains(response, f"https://culineire.test{approved_recipe.get_absolute_url()}")
        self.assertContains(response, f"https://culineire.test{approved_article.get_absolute_url()}")
        self.assertNotContains(response, "Pending Recipe")
        self.assertNotContains(response, "pending-article")


class MaintenanceModeTests(TestCase):
    @override_settings(MAINTENANCE_MODE=True, MAINTENANCE_UNTIL="2026-05-20T18:00:00+01:00")
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
