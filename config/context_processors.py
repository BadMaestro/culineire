from django.conf import settings


def site_url(request):
    """Inject SITE_URL into every template context for canonical / OG URLs."""
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        base = site_domain
    else:
        base = f"{settings.SITE_SCHEME}://{site_domain}"
    return {"SITE_URL": base}
