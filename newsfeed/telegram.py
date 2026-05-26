from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramResult:
    ok: bool
    status: str
    response: str = ""


def build_recipe_telegram_message(recipe) -> str:
    description = (recipe.short_description or "").strip()
    url = recipe.get_absolute_url()
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    absolute_url = f"{site_url}{url}"
    parts = [f"New recipe on CulinEire: {recipe.title}"]
    if description:
        parts.append(description)
    parts.append(absolute_url)
    return "\n\n".join(parts)


def send_telegram_message(text: str) -> TelegramResult:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")

    payload = urlencode(
        {
            "chat_id": channel_id,
            "text": text,
            "disable_web_page_preview": "false",
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Telegram API returned HTTP %s: %s", exc.code, body)
        return TelegramResult(ok=False, status="failed", response=body)
    except URLError as exc:
        logger.warning("Telegram API request failed: %s", exc)
        return TelegramResult(ok=False, status="failed", response=str(exc))

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return TelegramResult(ok=False, status="failed", response=body)
    if parsed.get("ok"):
        return TelegramResult(ok=True, status="sent", response=body)
    return TelegramResult(ok=False, status="failed", response=body)


def publish_recipe_to_telegram(recipe) -> TelegramResult:
    if not getattr(settings, "TELEGRAM_BOT_TOKEN", "") or not getattr(settings, "TELEGRAM_CHANNEL_ID", ""):
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")

    from newsfeed.models import SocialPostLog

    event_key = f"recipe_published:{recipe.pk}"
    message = build_recipe_telegram_message(recipe)
    target_url = recipe.get_absolute_url()

    try:
        with transaction.atomic():
            log, created = SocialPostLog.objects.get_or_create(
                platform=SocialPostLog.Platform.TELEGRAM,
                event_key=event_key,
                defaults={
                    "status": SocialPostLog.Status.PENDING,
                    "target_url": target_url,
                    "message": message,
                },
            )
    except IntegrityError:
        log = SocialPostLog.objects.get(
            platform=SocialPostLog.Platform.TELEGRAM,
            event_key=event_key,
        )
        created = False

    if not created and log.status in {SocialPostLog.Status.PENDING, SocialPostLog.Status.SENT}:
        return TelegramResult(ok=log.status == SocialPostLog.Status.SENT, status="skipped", response="Telegram post already handled.")

    result = send_telegram_message(message)
    log.status = result.status
    log.target_url = target_url
    log.message = message
    log.response = result.response[:2000]
    log.save(update_fields=["status", "target_url", "message", "response", "updated_at"])
    return result
