from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Article, ArticleImage


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


@receiver(pre_save, sender=Article)
def delete_old_article_preview_on_change(sender, instance, **kwargs):
    del sender, kwargs
    if not instance.pk:
        return

    try:
        old_instance = Article.objects.get(pk=instance.pk)
    except Article.DoesNotExist:
        return

    old_file = old_instance.hero_image
    new_file = instance.hero_image

    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")

    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old_file)


@receiver(pre_save, sender=ArticleImage)
def delete_old_article_gallery_image_on_change(sender, instance, **kwargs):
    del sender, kwargs
    if not instance.pk:
        return

    try:
        old_instance = ArticleImage.objects.get(pk=instance.pk)
    except ArticleImage.DoesNotExist:
        return

    old_file = old_instance.image
    new_file = instance.image

    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")

    if old_name and old_name != new_name:
        _delete_file_and_cleanup(old_file)


@receiver(post_delete, sender=Article)
def delete_article_preview_on_delete(sender, instance, **kwargs):
    del sender, kwargs
    if instance.hero_image:
        _delete_file_and_cleanup(instance.hero_image)


@receiver(post_delete, sender=ArticleImage)
def delete_article_gallery_image_on_delete(sender, instance, **kwargs):
    del sender, kwargs
    if instance.image:
        _delete_file_and_cleanup(instance.image)
