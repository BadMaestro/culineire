import json
import urllib.parse
import urllib.request

from django.conf import settings


def verify_turnstile(token, remote_ip):
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
    except Exception:
        return False
