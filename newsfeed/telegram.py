from __future__ import annotations

import json
import logging
import io
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import IntegrityError, transaction
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

_NOTIFICATIONS_DISABLED_RESULT = None  # populated after TelegramResult is defined


def external_notifications_disabled() -> bool:
    """True when running under the test runner or when explicitly disabled in settings.

    Read from settings at call time so override_settings() works in tests.
    """
    return (
        getattr(settings, "IS_TESTING", False)
        or getattr(settings, "DISABLE_EXTERNAL_NOTIFICATIONS", False)
    )


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


def build_article_telegram_message(article) -> str:
    description = (article.excerpt or "").strip()
    url = article.get_absolute_url()
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    absolute_url = f"{site_url}{url}"
    parts = [f"New article on CulinEire: {article.title}"]
    if description:
        parts.append(description)
    parts.append(absolute_url)
    return "\n\n".join(parts)


def build_newsfeed_telegram_message(entry) -> str:
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    parts = [entry.title]
    if entry.message:
        parts.append(entry.message)
    if entry.url:
        parts.append(f"{site_url}{entry.url}" if entry.url.startswith("/") else entry.url)
    return "\n\n".join(parts)


def build_ab_direct_telegram_message(ab) -> str:
    """Compact Amuse-Bouche caption: title + URL only, no description or author prefix."""
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    absolute_url = f"{site_url}{ab.get_absolute_url()}"
    return f"Amuse-Bouche: {ab.title}\n\n{absolute_url}"


def build_ab_telegram_message(entry) -> str:
    """Compact Amuse-Bouche notification: title + URL only, no description or author prefix."""
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    absolute_url = f"{site_url}{entry.url}" if entry.url and entry.url.startswith("/") else (entry.url or "")
    parts = [f"Amuse-Bouche: {entry.title}"]
    if absolute_url:
        parts.append(absolute_url)
    return "\n\n".join(parts)


def _call_telegram_api(token: str, method: str, payload: dict) -> TelegramResult:
    if external_notifications_disabled():
        return TelegramResult(ok=False, status="skipped", response="External notifications are disabled.")
    data = urlencode(payload).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Telegram API %s returned HTTP %s: %s", method, exc.code, body)
        return TelegramResult(ok=False, status="failed", response=body)
    except URLError as exc:
        logger.warning("Telegram API %s request failed: %s", method, exc)
        return TelegramResult(ok=False, status="failed", response=str(exc))
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return TelegramResult(ok=False, status="failed", response=body)
    if parsed.get("ok"):
        return TelegramResult(ok=True, status="sent", response=body)
    return TelegramResult(ok=False, status="failed", response=body)


def _call_telegram_multipart_api(
    token: str,
    method: str,
    payload: dict[str, str],
    *,
    file_field: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> TelegramResult:
    if external_notifications_disabled():
        return TelegramResult(ok=False, status="skipped", response="External notifications are disabled.")

    boundary = f"----CulinEireTelegram{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in payload.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        logger.warning("Telegram API %s returned HTTP %s: %s", method, exc.code, response_body)
        return TelegramResult(ok=False, status="failed", response=response_body)
    except URLError as exc:
        logger.warning("Telegram API %s request failed: %s", method, exc)
        return TelegramResult(ok=False, status="failed", response=str(exc))
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return TelegramResult(ok=False, status="failed", response=response_body)
    return TelegramResult(
        ok=bool(parsed.get("ok")),
        status="sent" if parsed.get("ok") else "failed",
        response=response_body,
    )


def send_telegram_message(text: str) -> TelegramResult:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")
    return _call_telegram_api(token, "sendMessage", {
        "chat_id": channel_id,
        "text": text,
        "disable_web_page_preview": "false",
    })


def send_telegram_message_without_link_preview(text: str) -> TelegramResult:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")
    return _call_telegram_api(token, "sendMessage", {
        "chat_id": channel_id,
        "text": text,
        "disable_web_page_preview": "true",
    })


def send_telegram_message_with_link_preview(text: str, *, preview_url: str = "") -> TelegramResult:
    """sendMessage with small link preview — used for Amuse-Bouche compact notifications."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")
    link_preview_options = {
        "is_disabled": False,
        "prefer_small_media": True,
        "show_above_text": False,
    }
    if preview_url:
        link_preview_options["url"] = preview_url
    return _call_telegram_api(token, "sendMessage", {
        "chat_id": channel_id,
        "text": text,
        "link_preview_options": json.dumps(link_preview_options),
    })


def send_telegram_photo(image_url: str, caption: str) -> TelegramResult:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")
    return _call_telegram_api(token, "sendPhoto", {
        "chat_id": channel_id,
        "photo": image_url,
        "caption": caption[:1024],
    })


def send_telegram_photo_upload(image, caption: str) -> TelegramResult:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    channel_id = getattr(settings, "TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")
    if not image:
        return TelegramResult(ok=False, status="skipped", response="Sponsor image is not available.")

    image.open("rb")
    try:
        with Image.open(image) as source:
            source = ImageOps.exif_transpose(source).convert("RGBA")
            source.thumbnail((860, 430), Image.Resampling.LANCZOS)
            card = Image.new("RGB", (1200, 630), "#f7f3ea")
            logo_layer = Image.new("RGBA", card.size, (0, 0, 0, 0))
            x = (card.width - source.width) // 2
            y = (card.height - source.height) // 2
            logo_layer.alpha_composite(source, (x, y))
            card.paste(logo_layer, mask=logo_layer.getchannel("A"))
            output = io.BytesIO()
            card.save(output, format="JPEG", quality=92, optimize=True)
            file_bytes = output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("Sponsor Telegram image could not be prepared: %s", exc)
        return TelegramResult(ok=False, status="failed", response="Sponsor image could not be prepared.")
    finally:
        image.close()
    return _call_telegram_multipart_api(
        token,
        "sendPhoto",
        {"chat_id": channel_id, "caption": caption[:1024]},
        file_field="photo",
        filename="culineire-sponsor.jpg",
        content_type="image/jpeg",
        file_bytes=file_bytes,
    )


def _publish_to_telegram(*, event_key: str, message: str, target_url: str, image_url: str = "", _send_fn=None) -> TelegramResult:
    if external_notifications_disabled():
        return TelegramResult(ok=False, status="skipped", response="External notifications are disabled.")
    if not getattr(settings, "TELEGRAM_BOT_TOKEN", "") or not getattr(settings, "TELEGRAM_CHANNEL_ID", ""):
        return TelegramResult(ok=False, status="skipped", response="Telegram settings are not configured.")

    from newsfeed.models import SocialPostLog

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

    if _send_fn is not None:
        result = _send_fn(message)
    elif image_url:
        result = send_telegram_photo(image_url, message)
    else:
        result = send_telegram_message(message)
    log.status = result.status
    log.target_url = target_url
    log.message = message
    log.response = result.response[:2000]
    log.save(update_fields=["status", "target_url", "message", "response", "updated_at"])
    return result


def publish_ab_to_telegram(ab) -> TelegramResult:
    preview_url = ""
    try:
        from amuse_bouche.telegram_preview import absolute_url, get_telegram_preview_image
        get_telegram_preview_image(ab)
        version = getattr(ab, "updated_at", None)
        version_value = int(version.timestamp()) if version else getattr(ab, "pk", "")
        preview_url = f"{absolute_url(ab.get_absolute_url())}?tg={ab.pk}-{version_value}"
    except Exception:
        logger.exception("Failed to prepare Amuse-Bouche Telegram preview image for pk=%s", getattr(ab, "pk", None))
    return _publish_to_telegram(
        event_key=f"amuse_bouche_published:{ab.pk}",
        message=build_ab_direct_telegram_message(ab),
        target_url=ab.get_absolute_url(),
        _send_fn=lambda text: send_telegram_message_with_link_preview(text, preview_url=preview_url),
    )


def publish_recipe_to_telegram(recipe) -> TelegramResult:
    return _publish_to_telegram(
        event_key=f"recipe_published:{recipe.pk}",
        message=build_recipe_telegram_message(recipe),
        target_url=recipe.get_absolute_url(),
    )


def publish_article_to_telegram(article) -> TelegramResult:
    return _publish_to_telegram(
        event_key=f"article_published:{article.pk}",
        message=build_article_telegram_message(article),
        target_url=article.get_absolute_url(),
    )


def build_sponsor_telegram_message(application) -> str:
    """Announcement when a sponsor is approved and published on the puzzle."""
    site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    sponsors_url = f"{site_url}/sponsors/"
    if application.product_type == "central_monthly":
        return (
            "CulinEire Sponsor of the Month\n\n"
            f"{application.sponsor_name} is now featured as our Sponsor of the Month.\n\n"
            "For the next 30 days, this sponsor will be highlighted through CulinEire "
            "sponsor areas, announcements and selected site placements.\n\n"
            "Discover the Sponsor Puzzle:\n"
            f"{sponsors_url}"
        )
    return (
        "New CulinEire sponsor\n\n"
        f"{application.sponsor_name} has joined the CulinEire Sponsor Puzzle.\n\n"
        f"Annual Ring Sponsorship · Ring {application.cell.ring}, cell #{application.cell.cell_number}\n\n"
        f"{sponsors_url}"
    )


def publish_sponsor_to_telegram(application) -> TelegramResult:
    def send_announcement(message):
        if application.logo:
            return send_telegram_photo_upload(application.logo, message)
        return send_telegram_message_without_link_preview(message)

    return _publish_to_telegram(
        event_key=f"sponsor_approved:{application.pk}",
        message=build_sponsor_telegram_message(application),
        target_url="/sponsors/",
        _send_fn=send_announcement,
    )


def publish_newsfeed_entry_to_telegram(entry, *, message: str | None = None, event_key: str | None = None) -> TelegramResult:
    from newsfeed.models import NewsFeedEntry as _NewsFeedEntry
    if entry.entry_type == _NewsFeedEntry.EntryType.AMUSE_BOUCHE_PUBLISHED:
        return _publish_to_telegram(
            event_key=event_key or f"newsfeed_entry:{entry.pk}",
            message=message or build_ab_telegram_message(entry),
            target_url=entry.url or "",
            _send_fn=send_telegram_message_with_link_preview,
        )
    return _publish_to_telegram(
        event_key=event_key or f"newsfeed_entry:{entry.pk}",
        message=message or build_newsfeed_telegram_message(entry),
        target_url=entry.url or "",
        image_url=getattr(entry, "image_url", "") or "",
    )
