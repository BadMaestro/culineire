from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponsePermanentRedirect


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "culineire.localhost", "testserver"}


def _configured_site_host() -> str:
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        return urlsplit(site_domain).netloc.lower()
    return site_domain.lower()


def _host_without_port(host: str) -> str:
    host = host.strip("[]").lower()
    if ":" in host and host.count(":") == 1:
        return host.split(":", 1)[0]
    return host


class CanonicalHostRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "CANONICAL_HOST_REDIRECT", False):
            try:
                request_host = request.get_host().lower()
            except DisallowedHost:
                return self.get_response(request)

            canonical_host = _configured_site_host()
            if (
                canonical_host
                and request_host != canonical_host
                and _host_without_port(request_host) not in LOCAL_HOSTS
                and _host_without_port(canonical_host) not in LOCAL_HOSTS
            ):
                scheme = str(settings.SITE_SCHEME).strip() or "https"
                return HttpResponsePermanentRedirect(
                    f"{scheme}://{canonical_host}{request.get_full_path()}"
                )

        return self.get_response(request)
