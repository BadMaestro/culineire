from __future__ import annotations

import logging
from dataclasses import dataclass
from hashlib import sha1
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.templatetags.static import static
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

TELEGRAM_PREVIEW_SIZE = (640, 640)
TELEGRAM_PREVIEW_QUALITY = 84


@dataclass(frozen=True)
class TelegramPreviewImage:
    name: str
    url: str
    width: int = 0
    height: int = 0


def absolute_url(url: str, request=None) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    site_root = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
    return f"{site_root}{url}" if url.startswith("/") else f"{site_root}/{url}"


def fallback_preview_image(request=None) -> TelegramPreviewImage:
    return TelegramPreviewImage(
        name="",
        url=absolute_url(static("images/hero.jpg"), request=request),
    )


def get_telegram_preview_image(item) -> TelegramPreviewImage | None:
    source = getattr(item, "card_image", None)
    source_name = getattr(source, "name", "")
    if not source_name:
        return None

    target_name = _target_name(item, source_name)
    storage = source.storage

    try:
        if not storage.exists(target_name):
            _create_preview_image(source, target_name)
        width, height = _image_dimensions(storage, target_name)
        return TelegramPreviewImage(
            name=target_name,
            url=storage.url(target_name),
            width=width,
            height=height,
        )
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        logger.warning("Could not create Telegram preview image for AB pk=%s: %s", getattr(item, "pk", None), exc)
        source_width, source_height = _safe_source_dimensions(source)
        return TelegramPreviewImage(
            name=source_name,
            url=source.url,
            width=source_width,
            height=source_height,
        )
    return None


def get_telegram_preview_meta(item, request=None) -> TelegramPreviewImage:
    preview = get_telegram_preview_image(item)
    if preview is None:
        return fallback_preview_image(request=request)
    return TelegramPreviewImage(
        name=preview.name,
        url=absolute_url(preview.url, request=request),
        width=preview.width,
        height=preview.height,
    )


def _target_name(item, source_name: str) -> str:
    digest = sha1(source_name.encode("utf-8")).hexdigest()[:12]
    stem = slugify(Path(source_name).stem)[:60] or "image"
    item_id = getattr(item, "pk", None) or "unsaved"
    return f"pinch/telegram-previews/{item_id}/{stem}-{digest}.jpg"


def _create_preview_image(source, target_name: str) -> None:
    storage = source.storage
    with storage.open(source.name, "rb") as source_file:
        with Image.open(source_file) as image:
            image = ImageOps.exif_transpose(image)
            image = ImageOps.fit(
                image,
                TELEGRAM_PREVIEW_SIZE,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            image = _to_rgb(image)
            output = BytesIO()
            image.save(output, "JPEG", quality=TELEGRAM_PREVIEW_QUALITY, optimize=True)
    storage.save(target_name, ContentFile(output.getvalue()))


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        alpha = image.convert("RGBA").getchannel("A")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    return image.convert("RGB")


def _image_dimensions(storage, name: str) -> tuple[int, int]:
    with storage.open(name, "rb") as image_file:
        with Image.open(image_file) as image:
            return image.size


def _safe_source_dimensions(source) -> tuple[int, int]:
    try:
        return _image_dimensions(source.storage, source.name)
    except (OSError, ValueError, UnidentifiedImageError):
        return 0, 0
