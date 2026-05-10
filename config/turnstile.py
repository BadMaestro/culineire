import json
import urllib.parse
import urllib.error
import urllib.request

from django.conf import settings


def verify_turnstile(token, remote_ip):
    if getattr(settings, "IS_TESTING", False):
        return True

    secret = settings.TURNSTILE_SECRET_KEY
    if not secret:
        return True
    try:
        data = urllib.parse.urlencode({
            "secret": secret,
            "response": token,
            "remoteip": remote_ip,
        }).encode()
        with urllib.request.urlopen(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=data,
                timeout=5,
        ) as resp:
            result = json.loads(resp.read())
        return result.get("success", False)
    except (json.JSONDecodeError, TimeoutError, urllib.error.URLError):
        return False
