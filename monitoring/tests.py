from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .middleware import MonitoringMiddleware
from .models import PageView, SecurityEvent, UserActivity
from .tracker import hash_ip, track_event

User = get_user_model()


def _make_response(status=200):
    from django.http import HttpResponse
    return HttpResponse(status=status)


class MiddlewareSkipTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = MonitoringMiddleware(lambda r: _make_response())

    def test_skips_static(self):
        request = self.factory.get("/static/css/base.css")
        self.middleware(request)
        self.assertEqual(PageView.objects.count(), 0)

    def test_skips_media(self):
        request = self.factory.get("/media/recipe/photo.jpg")
        self.middleware(request)
        self.assertEqual(PageView.objects.count(), 0)

    def test_records_normal_page(self):
        request = self.factory.get("/recipes/")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": "abc123"})()
        self.middleware(request)
        self.assertEqual(PageView.objects.filter(path="/recipes/").count(), 1)

    def test_records_404_as_security_event(self):
        middleware = MonitoringMiddleware(lambda r: _make_response(404))
        request = self.factory.get("/nonexistent/page/")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()
        middleware(request)
        self.assertEqual(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.NOT_FOUND).count(), 1
        )

    def test_flags_suspicious_path(self):
        request = self.factory.get("/<script>alert(1)</script>")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()
        self.middleware(request)
        self.assertEqual(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST).count(), 1
        )


class TrackEventTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="pass")

    def test_creates_user_activity(self):
        request = self.factory.get("/recipes/test-recipe/")
        request.user = self.user
        request.session = type("Session", (), {"session_key": "testsession"})()
        track_event(request, "recipe_view", object_type="recipe", object_id=1, object_title="Test Recipe")
        self.assertEqual(UserActivity.objects.filter(event_type="recipe_view").count(), 1)

    def test_no_error_on_exception(self):
        request = self.factory.get("/")
        request.user = self.user
        # No session attribute — should not raise
        track_event(request, "recipe_view")


class HashIpTest(TestCase):
    def test_returns_hex_string(self):
        result = hash_ip("127.0.0.1")
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_empty_string(self):
        self.assertEqual(hash_ip(""), "")

    def test_same_ip_same_hash(self):
        self.assertEqual(hash_ip("1.2.3.4"), hash_ip("1.2.3.4"))

    def test_different_ips_different_hashes(self):
        self.assertNotEqual(hash_ip("1.2.3.4"), hash_ip("5.6.7.8"))


class DashboardPermissionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.regular_user = User.objects.create_user(username="regular", password="pass")
        self.superuser = User.objects.create_superuser(username="admin", password="pass", email="a@b.com")

    def test_anonymous_gets_404(self):
        response = self.client.get("/recipes/moderation/monitoring/")
        self.assertEqual(response.status_code, 404)

    def test_regular_user_gets_404(self):
        self.client.login(username="regular", password="pass")
        response = self.client.get("/recipes/moderation/monitoring/")
        self.assertEqual(response.status_code, 404)

    def test_superuser_gets_200(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/recipes/moderation/monitoring/")
        self.assertEqual(response.status_code, 200)

    def test_greenbear_gets_200(self):
        gb_user = User.objects.create_user(username="greenbear_test", password="pass")
        author, _ = RecipeAuthor.objects.get_or_create(slug="greenbear", defaults={"name": "GreenBear"})
        author.user = gb_user
        author.save()
        self.client.login(username="greenbear_test", password="pass")
        response = self.client.get("/recipes/moderation/monitoring/")
        self.assertEqual(response.status_code, 200)


class CleanupCommandTest(TestCase):
    def test_deletes_old_records(self):
        from django.core.management import call_command

        old_time = timezone.now() - timezone.timedelta(days=100)
        pv = PageView.objects.create(path="/old/", status_code=200)
        PageView.objects.filter(pk=pv.pk).update(created_at=old_time)

        ua = UserActivity.objects.create(event_type="login")
        UserActivity.objects.filter(pk=ua.pk).update(created_at=old_time)

        call_command("cleanup_monitoring", "--days=90", verbosity=0)

        self.assertEqual(PageView.objects.count(), 0)
        self.assertEqual(UserActivity.objects.count(), 0)

    def test_dry_run_does_not_delete(self):
        from django.core.management import call_command

        old_time = timezone.now() - timezone.timedelta(days=100)
        pv = PageView.objects.create(path="/old/", status_code=200)
        PageView.objects.filter(pk=pv.pk).update(created_at=old_time)

        call_command("cleanup_monitoring", "--days=90", "--dry-run", verbosity=0)

        self.assertEqual(PageView.objects.count(), 1)
