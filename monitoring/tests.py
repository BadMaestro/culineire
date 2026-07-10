from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from recipes.models import RecipeAuthor

from .middleware import MonitoringMiddleware
from .models import PageView, SecurityEvent, UserActivity
from .tracker import hash_ip, track_event
from .views import _request_kind

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

    def test_skips_append_slash_redirect_candidate_404(self):
        middleware = MonitoringMiddleware(lambda r: _make_response(404))
        request = self.factory.get("/about")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()

        middleware(request)

        self.assertFalse(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.NOT_FOUND).exists()
        )

    def test_flags_suspicious_path(self):
        request = self.factory.get("/<script>alert(1)</script>")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()
        self.middleware(request)
        self.assertEqual(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST).count(), 1
        )

    def test_blocks_credential_probe_before_view(self):
        called = False

        def get_response(request):
            nonlocal called
            called = True
            return _make_response()

        middleware = MonitoringMiddleware(get_response)
        request = self.factory.get(
            "/stripe-credentials.json",
            HTTP_USER_AGENT="TLM-Audit-Scanner/1.0",
            REMOTE_ADDR="203.0.113.10",
        )
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()

        response = middleware(request)

        self.assertFalse(called)
        self.assertEqual(response.status_code, 404)
        event = SecurityEvent.objects.get(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST)
        self.assertEqual(event.severity, SecurityEvent.Severity.CRITICAL)
        self.assertEqual(event.path, "/stripe-credentials.json")
        self.assertEqual(event.user_agent, "TLM-Audit-Scanner/1.0")
        self.assertEqual(PageView.objects.count(), 0)

    @override_settings(MONITORING_BLOCK_SUSPICIOUS_PROBES=False)
    def test_can_log_suspicious_probe_without_blocking(self):
        request = self.factory.get("/credentials.json")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        event = SecurityEvent.objects.get(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST)
        self.assertEqual(event.severity, SecurityEvent.Severity.CRITICAL)

    def test_url_encoded_traversal_is_critical_and_blocked(self):
        request = self.factory.get("/%2e%2e/%2e%2e/etc/passwd")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = type("Session", (), {"session_key": None})()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 404)
        event = SecurityEvent.objects.get(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST)
        self.assertEqual(event.severity, SecurityEvent.Severity.CRITICAL)


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


class RequestKindClassificationTest(SimpleTestCase):
    def test_authenticated_user_is_human(self):
        self.assertEqual(
            _request_kind("Mozilla/5.0", "/recipes/moderation/", user=object()),
            "Human",
        )

    def test_normal_anonymous_browser_is_guest_browser(self):
        self.assertEqual(
            _request_kind("Mozilla/5.0", "/", user=None),
            "Guest/Browser",
        )

    def test_anonymous_protected_path_is_not_human(self):
        self.assertEqual(
            _request_kind("Mozilla/5.0", "/recipes/moderation/", user=None),
            "Protected Area",
        )

    def test_browser_probe_for_private_files_is_scanner(self):
        paths = [
            "/bitbucket-pipelines.yml",
            "/vite.config.js",
            "/db.sql",
            "/logs/error.log",
            "/service-account.json",
            "/firebase-adminsdk.json",
            "/config/credentials.json",
            "/api/client_secret.json",
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(
                    _request_kind("Mozilla/5.0", path, user=None),
                    "Bot/Scanner",
                )

    def test_scanner_user_agent_is_bot_even_on_root(self):
        self.assertEqual(
            _request_kind("TLM-Audit-Scanner/1.0", "/", user=None),
            "Bot/Scanner",
        )

    def test_url_encoded_private_file_probe_is_scanner(self):
        self.assertEqual(
            _request_kind("Mozilla/5.0", "/%63redentials.json", user=None),
            "Bot/Scanner",
        )


class DashboardPermissionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.regular_user = User.objects.create_user(username="regular", password="pass")
        self.superuser = User.objects.create_superuser(username="admin", password="pass", email="a@b.com")

    def test_anonymous_gets_404(self):
        response = self.client.get("/monitoring/")
        self.assertEqual(response.status_code, 404)

    def test_regular_user_gets_404(self):
        self.client.login(username="regular", password="pass")
        response = self.client.get("/monitoring/")
        self.assertEqual(response.status_code, 404)

    def test_superuser_gets_200(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/monitoring/")
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_open_detail_pages(self):
        self.client.login(username="admin", password="pass")
        paths = [
            "/monitoring/traffic/",
            "/monitoring/traffic/?kind=human",
            "/monitoring/security/",
            "/monitoring/activity/",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_greenbear_gets_200(self):
        gb_user = User.objects.create_user(username="greenbear_test", password="pass")
        author, _ = RecipeAuthor.objects.get_or_create(slug="greenbear", defaults={"name": "GreenBear"})
        author.user = gb_user
        author.save()
        self.client.login(username="greenbear_test", password="pass")
        response = self.client.get("/monitoring/")
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
