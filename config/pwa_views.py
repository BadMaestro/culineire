"""
PWA views: manifest.json, service worker (/sw.js) and offline fallback (/offline/).

To bump the cache version after a major deploy (forces all clients to
refresh their cached assets), increment PWA_CACHE_VERSION in settings.py
or change the string below.
"""

import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static

# Bump this string after significant static-asset changes to force clients
# to refresh their service-worker cache.  Format: culineire-pwa-vN
PWA_CACHE_VERSION = getattr(settings, "PWA_CACHE_VERSION", "culineire-pwa-v1")

# URL path prefixes that the service worker must NEVER cache.
# Covers admin, auth, user-specific, and private-content pages.
_NO_CACHE_PREFIXES = [
    "/cave19850324/",
    "/accounts/",
    "/messages/",
    "/presence/",
    "/monitoring/",
    "/sandbox/",
    "/recipes/moderation/",
    "/collection/",
    "/pinch/",
    "/recipes/create",
    "/recipes/edit/",
    "/articles/create",
    "/articles/edit/",
]


def pwa_manifest(request):
    """Serve the PWA web app manifest at /manifest.json."""
    icon_192 = request.build_absolute_uri(static("images/favicon-192.png"))
    icon_512 = request.build_absolute_uri(static("images/pwa-icon-512.png"))
    apple_icon = request.build_absolute_uri(static("images/apple-touch-icon.png"))

    manifest = {
        "name": "CulinEire",
        "short_name": "CulinEire",
        "description": "Irish culinary heritage, recipes, articles and modern food stories.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#faf6f0",
        "theme_color": "#123c2d",
        "categories": ["food", "lifestyle", "social"],
        "icons": [
            {
                "src": icon_192,
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": icon_512,
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": apple_icon,
                "sizes": "180x180",
                "type": "image/png",
                "purpose": "any",
            },
        ],
    }
    return HttpResponse(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        content_type="application/manifest+json; charset=utf-8",
    )


def pwa_service_worker(request):
    """Serve the PWA service worker at /sw.js.

    Served as a rendered Django template so the cache-version string and
    no-cache path list can be injected from Python without hard-coding them
    in a static JS file.
    """
    context = {
        "cache_name": PWA_CACHE_VERSION,
        "no_cache_prefixes_json": json.dumps(_NO_CACHE_PREFIXES),
    }
    response = render(
        request,
        "pwa/sw.js",
        context,
        content_type="application/javascript; charset=utf-8",
    )
    # Allow the SW to control the entire origin
    response["Service-Worker-Allowed"] = "/"
    # Never cache the SW itself — browsers must always re-fetch it
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def pwa_offline(request):
    """Serve the offline fallback page at /offline/.

    Status 200 is intentional: the service worker's cache.add() only stores
    responses with a 2xx status, so this must succeed for the offline
    fallback to work.
    """
    return render(request, "pwa/offline.html", status=200)
