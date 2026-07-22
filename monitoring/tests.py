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


class _SessionStub(dict):
    """Dict-backed session stand-in: supports item assignment like the real
    SessionStore (the middleware force-creates sessions for browser UAs)."""

    def __init__(self, session_key=None):
        super().__init__()
        self.session_key = session_key


# RequestFactory defaults REMOTE_ADDR to 127.0.0.1; pin the internal-IP list to
# empty so an ambient MONITORING_INTERNAL_IPS (e.g. the production .env listing
# 127.0.0.1) can't classify these synthetic requests as internal and skip them.
@override_settings(MONITORING_INTERNAL_IPS=[])
class MiddlewareSkipTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # staff logins in other test classes mark ips internal in cache
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
        request.session = _SessionStub("abc123")
        self.middleware(request)
        self.assertEqual(PageView.objects.filter(path="/recipes/").count(), 1)

    def test_internal_ip_from_settings_excluded(self):
        with override_settings(MONITORING_INTERNAL_IPS=["10.9.8.7"]):
            middleware = MonitoringMiddleware(lambda r: _make_response())
            request = self.factory.get("/recipes/", REMOTE_ADDR="10.9.8.7")
            request.user = type("AnonUser", (), {"is_authenticated": False})()
            request.session = _SessionStub("int1")
            middleware(request)
        self.assertEqual(PageView.objects.count(), 0)

    def test_staff_machine_auto_learned_and_excluded(self):
        from django.core.cache import cache
        cache.clear()
        staff = User.objects.create_user("mon-staff", password="pw", is_staff=True)
        # 1) authenticated staff request: skipped AND marks the ip_hash
        request = self.factory.get("/recipes/", REMOTE_ADDR="10.1.2.3")
        request.user = staff
        request.session = _SessionStub("s1")
        self.middleware(request)
        self.assertEqual(PageView.objects.count(), 0)
        # 2) anonymous request from the SAME machine (e.g. manifest fetch, curl)
        anon = self.factory.get("/manifest.json", REMOTE_ADDR="10.1.2.3")
        anon.user = type("AnonUser", (), {"is_authenticated": False})()
        anon.session = _SessionStub("s2")
        self.middleware(anon)
        self.assertEqual(PageView.objects.count(), 0)
        # 3) a different visitor is still recorded
        visitor = self.factory.get("/recipes/", REMOTE_ADDR="10.4.5.6")
        visitor.user = type("AnonUser", (), {"is_authenticated": False})()
        visitor.session = _SessionStub("s3")
        self.middleware(visitor)
        self.assertEqual(PageView.objects.count(), 1)

    def test_records_404_as_security_event(self):
        middleware = MonitoringMiddleware(lambda r: _make_response(404))
        request = self.factory.get("/nonexistent/page/")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = _SessionStub()
        middleware(request)
        self.assertEqual(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.NOT_FOUND).count(), 1
        )

    def test_skips_append_slash_redirect_candidate_404(self):
        middleware = MonitoringMiddleware(lambda r: _make_response(404))
        request = self.factory.get("/about")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = _SessionStub()

        middleware(request)

        self.assertFalse(
            SecurityEvent.objects.filter(event_type=SecurityEvent.EventType.NOT_FOUND).exists()
        )

    def test_flags_suspicious_path(self):
        request = self.factory.get("/<script>alert(1)</script>")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = _SessionStub()
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
        request.session = _SessionStub()

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
        request.session = _SessionStub()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        event = SecurityEvent.objects.get(event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST)
        self.assertEqual(event.severity, SecurityEvent.Severity.CRITICAL)

    def test_url_encoded_traversal_is_critical_and_blocked(self):
        request = self.factory.get("/%2e%2e/%2e%2e/etc/passwd")
        request.user = type("AnonUser", (), {"is_authenticated": False})()
        request.session = _SessionStub()

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


class ServerMetricsPageTest(TestCase):
    """The health mirror added after the 2026-07-22 disk-full outage.

    The point of these tests is that the page must survive the very conditions it
    exists to report on: no Linode token, an unreachable API, an API that answers
    with rubbish. A monitoring page that 500s during an incident is worse than no
    monitoring page at all.
    """

    def setUp(self):
        from django.core.cache import cache

        cache.delete("monitoring:linode:stats")
        User = get_user_model()
        self.staff = User.objects.create_user("srv-staff", password="pw", is_staff=True)
        self.plain = User.objects.create_user("srv-plain", password="pw")
        self.url = "/monitoring/server/"

    def test_anonymous_gets_404(self):
        self.assertEqual(Client().get(self.url).status_code, 404)

    def test_non_moderator_gets_404(self):
        client = Client()
        client.force_login(self.plain)
        self.assertEqual(client.get(self.url).status_code, 404)

    def test_moderator_gets_page(self):
        client = Client()
        client.force_login(self.staff)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Server health")

    def test_page_works_without_a_linode_token(self):
        """Host readings must still render, and the page must explain the gap."""
        from unittest.mock import patch

        client = Client()
        client.force_login(self.staff)
        with patch.dict("os.environ", {"LINODE_API_TOKEN": "", "LINODE_INSTANCE_ID": ""}, clear=False):
            response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not connected yet")

    def test_api_failure_does_not_break_the_page(self):
        from unittest.mock import patch

        client = Client()
        client.force_login(self.staff)
        with patch.dict(
            "os.environ",
            {"LINODE_API_TOKEN": "x" * 10, "LINODE_INSTANCE_ID": "1"},
            clear=False,
        ), patch("monitoring.server_metrics._fetch", side_effect=OSError("network is down")):
            response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not read Linode")



class ServerMetricsSeriesTest(SimpleTestCase):
    def test_polyline_scales_to_the_series_maximum(self):
        """CPU on this Linode is reported above 100%, so a fixed 0-100 axis would
        clip the exact spike worth looking at."""
        from .server_metrics import Series

        s = Series(key="cpu", label="CPU", unit="%", points=[(0, 0.0), (1, 116.0)])
        points = s.polyline(width=100, height=10).split()
        self.assertEqual(len(points), 2)
        self.assertTrue(points[0].endswith(",10.0"))  # lowest value sits on the floor
        self.assertTrue(points[1].endswith(",0.0"))   # the peak reaches the top

    def test_polyline_is_empty_for_a_single_point(self):
        from .server_metrics import Series

        self.assertEqual(Series(key="x", label="X", unit="%", points=[(0, 5.0)]).polyline(), "")

    def test_series_ignores_null_samples(self):
        """Linode returns nulls for gaps; they must not become zeroes."""
        from .server_metrics import _series_from

        s = _series_from([[1000, 5.0], [2000, None], [3000, 7.0]], "cpu", "CPU", "%")
        self.assertEqual(s.values, [5.0, 7.0])

    def test_host_metrics_never_raises(self):
        from .server_metrics import host_metrics

        data = host_metrics()
        self.assertIn("disk", data)
        self.assertIn("memory", data)


class ServerMetricsCacheResilienceTest(SimpleTestCase):
    """A single root-owned cache file made /monitoring/server/ return 500 on
    2026-07-22. The page whose job is to report that the server is unhappy must
    not be the thing that falls over when the server is unhappy.

    Tested at the helper level on purpose. Patching django.core.cache globally
    also breaks MonitoringMiddleware, which reaches for the same cache on every
    request -- that would test Django's middleware stack, not this fix.
    """

    def test_cache_get_swallows_backend_errors(self):
        from unittest.mock import patch

        from .server_metrics import _cache_get

        with patch("monitoring.server_metrics.cache.get", side_effect=PermissionError("denied")):
            self.assertIsNone(_cache_get())

    def test_cache_set_swallows_backend_errors(self):
        from unittest.mock import patch

        from .server_metrics import _cache_set

        with patch("monitoring.server_metrics.cache.set", side_effect=PermissionError("denied")):
            _cache_set({"configured": False}, 60)  # must not raise

    def test_linode_metrics_returns_a_payload_when_the_cache_is_dead(self):
        from unittest.mock import patch

        from .server_metrics import linode_metrics

        with patch("monitoring.server_metrics.cache.get", side_effect=PermissionError("denied")), \
             patch("monitoring.server_metrics.cache.set", side_effect=PermissionError("denied")), \
             patch.dict("os.environ", {"LINODE_API_TOKEN": "", "LINODE_INSTANCE_ID": ""}, clear=False):
            result = linode_metrics()
        self.assertFalse(result["configured"])
        self.assertIn("series", result)


class MiddlewareCacheResilienceTest(TestCase):
    """MonitoringMiddleware runs on every request, so an unreachable cache here
    returns 500 for the WHOLE SITE, not one page.

    Proven the hard way on 2026-07-22: one .djcache file owned by root, written
    by a diagnostic run as the wrong user, made the deploy worker unable to write
    it. Losing the internal-IP memory only makes the stats slightly noisier.
    Losing the site is not comparable.
    """

    def test_site_still_serves_when_the_cache_backend_is_dead(self):
        from unittest.mock import patch

        with patch("django.core.cache.cache.get", side_effect=PermissionError("denied")), \
             patch("django.core.cache.cache.set", side_effect=PermissionError("denied")):
            response = Client().get("/")
        self.assertEqual(response.status_code, 200)

    def test_is_internal_returns_false_rather_than_raising(self):
        from unittest.mock import patch

        from .middleware import MonitoringMiddleware

        mw = MonitoringMiddleware(lambda request: None)
        with patch("django.core.cache.cache.get", side_effect=PermissionError("denied")):
            self.assertFalse(mw._is_internal("some-hash", None))

    def test_staff_marking_survives_an_unwritable_cache(self):
        from unittest.mock import patch

        from .middleware import MonitoringMiddleware

        User = get_user_model()
        staff = User.objects.create_user("mw-cache-staff", password="pw", is_staff=True)
        mw = MonitoringMiddleware(lambda request: None)
        with patch("django.core.cache.cache.set", side_effect=PermissionError("denied")):
            self.assertTrue(mw._is_internal("some-hash", staff))
