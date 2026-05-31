import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import AmuseBouche

logger = logging.getLogger(__name__)


def _hide_auto_entry(event_key):
    try:
        from newsfeed.models import NewsFeedEntry
        NewsFeedEntry.objects.filter(event_key=event_key, is_auto=True).update(is_public=False)
    except Exception:
        logger.exception("Failed to hide newsfeed entry for event_key=%s", event_key)


@receiver(post_save, sender=AmuseBouche)
def create_newsfeed_entry_on_approval(sender, instance, **kwargs):
    del sender, kwargs
    event_key = f"amuse_bouche_published:{instance.pk}"
    if instance.status != AmuseBouche.Status.APPROVED:
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
        NewsFeedEntry.objects.update_or_create(
            event_key=event_key,
            defaults={
                "entry_type": NewsFeedEntry.EntryType.AMUSE_BOUCHE_PUBLISHED,
                "title": instance.title,
                "message": message,
                "url": instance.get_absolute_url(),
                "is_auto": True,
                "is_public": True,
            },
        )
    except Exception:
        logger.exception("Failed to create newsfeed entry for Amuse-Bouche pk=%s", instance.pk)


@receiver(post_delete, sender=AmuseBouche)
def hide_newsfeed_entry_on_delete(sender, instance, **kwargs):
    del sender, kwargs
    _hide_auto_entry(f"amuse_bouche_published:{instance.pk}")
