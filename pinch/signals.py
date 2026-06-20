import logging
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Pinch, PinchGalleryImage

logger = logging.getLogger(__name__)


# ── File cleanup helpers (mirrors recipes/signals.py) ────────────────────────

def _safe_delete_file(file_field):
    if not file_field:
        return
    try:
        storage = file_field.storage
        name = file_field.name
    except (AttributeError, ValueError, OSError):
        return
    if not name:
        return
    try:
        if storage.exists(name):
            storage.delete(name)
    except OSError:
        return


def _cleanup_empty_parent_dirs(file_name):
    if not file_name:
        return
    media_root = Path(settings.MEDIA_ROOT).resolve()
    target_path = (media_root / file_name).resolve()
    current_dir = target_path.parent
    while True:
        if current_dir == media_root:
            break
        try:
            current_dir.rmdir()
        except OSError:
            break
        current_dir = current_dir.parent


def _delete_file_and_cleanup(file_field):
    file_name = getattr(file_field, "name", "")
    _safe_delete_file(file_field)
    if file_name:
        _cleanup_empty_parent_dirs(file_name)


# ── Cover image cleanup ───────────────────────────────────────────────────────

@receiver(pre_save, sender=Pinch)
def delete_old_cover_image_on_change(sender, instance, **kwargs):
    """Delete the old cover image file when it is replaced."""
    del sender, kwargs
    if not instance.pk:
        return
    try:
        old = Pinch.objects.get(pk=instance.pk)
    except Pinch.DoesNotExist:
        return
    old_name = getattr(old.cover_image, "name", "")
    new_name = getattr(instance.cover_image, "name", "")
    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old.cover_image)


@receiver(post_delete, sender=Pinch)
def delete_cover_image_on_delete(sender, instance, **kwargs):
    """Delete cover image file when the Pinch item is deleted."""
    del sender, kwargs
    if instance.cover_image:
        _delete_file_and_cleanup(instance.cover_image)


# ── Gallery image cleanup ─────────────────────────────────────────────────────

@receiver(pre_save, sender=PinchGalleryImage)
def delete_old_gallery_image_on_change(sender, instance, **kwargs):
    """Delete the old gallery image file when it is replaced."""
    del sender, kwargs
    if not instance.pk:
        return
    try:
        old = PinchGalleryImage.objects.get(pk=instance.pk)
    except PinchGalleryImage.DoesNotExist:
        return
    old_name = getattr(old.image, "name", "")
    new_name = getattr(instance.image, "name", "")
    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old.image)


@receiver(post_delete, sender=PinchGalleryImage)
def delete_gallery_image_on_delete(sender, instance, **kwargs):
    """Delete gallery image file when the gallery item is deleted."""
    del sender, kwargs
    if instance.image:
        _delete_file_and_cleanup(instance.image)


# ── Telegram: direct approval signal (mirrors recipes/signals.py) ────────────

@receiver(pre_save, sender=Pinch)
def remember_previous_ab_status(sender, instance, **kwargs):
    del sender, kwargs
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        instance._previous_status = Pinch.objects.only("status").get(pk=instance.pk).status
    except Pinch.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Pinch)
def publish_ab_to_telegram_on_approval(sender, instance, **kwargs):
    del sender, kwargs
    if instance.is_announcement:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if instance.status != Pinch.Status.APPROVED or previous_status == Pinch.Status.APPROVED:
        return
    try:
        from newsfeed.telegram import publish_ab_to_telegram
        publish_ab_to_telegram(instance)
    except Exception:
        logger.exception("Failed to publish pinch pk=%s to Telegram", instance.pk)


# ── Newsfeed integration ──────────────────────────────────────────────────────

def _hide_auto_entry(event_key):
    try:
        from newsfeed.models import NewsFeedEntry
        NewsFeedEntry.objects.filter(event_key=event_key, is_auto=True).update(is_public=False)
    except Exception:
        logger.exception("Failed to hide newsfeed entry for event_key=%s", event_key)


@receiver(post_save, sender=Pinch)
def create_newsfeed_entry_on_approval(sender, instance, **kwargs):
    del sender, kwargs
    if instance.is_announcement:
        return
    event_key = f"pinch_published:{instance.pk}"
    if instance.status != Pinch.Status.APPROVED:
        _hide_auto_entry(event_key)
        return
    try:
        from newsfeed.models import NewsFeedEntry
        author_name = getattr(instance.author, "name", "") if instance.author else ""
        message = instance.short_description or ""
        if author_name and message:
            message = f"{author_name}: {message}"
        elif author_name:
            message = f"By {author_name}"
        try:
            from sponsors.services import get_sponsor_of_month
            sponsor = get_sponsor_of_month()
        except Exception:
            sponsor = ""
        if sponsor:
            message = f"{message} · Sponsored by: {sponsor}" if message else f"Sponsored by: {sponsor}"
        from .telegram_preview import absolute_url, get_telegram_preview_image
        preview = get_telegram_preview_image(instance)
        image_url = absolute_url(preview.url) if preview else ""
        NewsFeedEntry.objects.update_or_create(
            event_key=event_key,
            defaults={
                "entry_type": NewsFeedEntry.EntryType.PINCH_PUBLISHED,
                "title": instance.title,
                "message": message,
                "url": instance.get_absolute_url(),
                "image_url": image_url,
                "is_auto": True,
                "is_public": True,
            },
        )
    except Exception:
        logger.exception("Failed to create newsfeed entry for Pinch pk=%s", instance.pk)


@receiver(post_delete, sender=Pinch)
def hide_newsfeed_entry_on_delete(sender, instance, **kwargs):
    del sender, kwargs
    _hide_auto_entry(f"pinch_published:{instance.pk}")
