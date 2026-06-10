import logging
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Recipe, RecipeImage

logger = logging.getLogger(__name__)


def _safe_delete_file(file_field):
    """
    Delete a file from storage if it exists.
    Works safely even if the file was already removed.
    """
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
        # Do not crash admin/site if filesystem cleanup fails.
        return


def _cleanup_empty_parent_dirs(file_name):
    """
    Remove empty directories upward from the file location,
    but never go above MEDIA_ROOT.
    """
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
            # Directory is not empty or cannot be removed.
            break

        current_dir = current_dir.parent


def _delete_file_and_cleanup(file_field):
    file_name = getattr(file_field, "name", "")
    _safe_delete_file(file_field)
    if file_name:
        _cleanup_empty_parent_dirs(file_name)


@receiver(pre_save, sender=Recipe)
def remember_previous_recipe_status(sender, instance, **kwargs):
    del sender, kwargs
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        instance._previous_status = Recipe.objects.only("status").get(pk=instance.pk).status
    except Recipe.DoesNotExist:
        instance._previous_status = None


@receiver(pre_save, sender=Recipe)
def delete_old_recipe_preview_on_change(sender, instance, **kwargs):
    """
    If preview image is replaced, remove the old file.
    """
    del sender, kwargs
    if not instance.pk:
        return

    try:
        old_instance = Recipe.objects.get(pk=instance.pk)
    except Recipe.DoesNotExist:
        return

    old_file = old_instance.hero_image
    new_file = instance.hero_image

    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")

    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old_file)


@receiver(post_save, sender=Recipe)
def publish_recipe_to_telegram_on_approval(sender, instance, **kwargs):
    del sender, kwargs
    previous_status = getattr(instance, "_previous_status", None)
    if instance.status != Recipe.Status.APPROVED or previous_status == Recipe.Status.APPROVED:
        return
    try:
        from newsfeed.telegram import publish_recipe_to_telegram
        publish_recipe_to_telegram(instance)
    except Exception:
        logger.exception("Failed to publish recipe pk=%s to Telegram", instance.pk)
    try:
        from chef_battle.services import award_moves, MOVES_RECIPE_APPROVED
        if instance.author:
            award_moves(instance.author, MOVES_RECIPE_APPROVED, "Recipe approved")
    except Exception:
        logger.exception("Failed to award battle moves for recipe pk=%s", instance.pk)


@receiver(pre_save, sender=RecipeImage)
def delete_old_gallery_image_on_change(sender, instance, **kwargs):
    """
    If a gallery image is replaced, remove the old file.
    """
    del sender, kwargs
    if not instance.pk:
        return

    try:
        old_instance = RecipeImage.objects.get(pk=instance.pk)
    except RecipeImage.DoesNotExist:
        return

    old_file = old_instance.image
    new_file = instance.image

    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")

    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old_file)


@receiver(post_delete, sender=Recipe)
def delete_recipe_preview_on_delete(sender, instance, **kwargs):
    """
    Delete preview image file when recipe is deleted.
    """
    del sender, kwargs
    if instance.hero_image:
        _delete_file_and_cleanup(instance.hero_image)


@receiver(post_delete, sender=RecipeImage)
def delete_gallery_image_on_delete(sender, instance, **kwargs):
    """
    Delete gallery image file when gallery item is deleted.
    """
    del sender, kwargs
    if instance.image:
        _delete_file_and_cleanup(instance.image)
