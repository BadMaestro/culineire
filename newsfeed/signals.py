import logging

from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)


def _create_recipe_entry(recipe):
    try:
        from newsfeed.models import NewsFeedEntry
        event_key = f"recipe_published:{recipe.pk}"
        NewsFeedEntry.objects.update_or_create(
            event_key=event_key,
            defaults={
                "entry_type": NewsFeedEntry.EntryType.RECIPE_PUBLISHED,
                "title": f"New recipe published: {recipe.title}",
                "url": recipe.get_absolute_url(),
                "is_auto": True,
                "is_public": True,
            },
        )
    except Exception:
        logger.exception("Failed to create newsfeed entry for recipe pk=%s", recipe.pk)


def _create_article_entry(article):
    try:
        from newsfeed.models import NewsFeedEntry
        event_key = f"article_published:{article.pk}"
        NewsFeedEntry.objects.update_or_create(
            event_key=event_key,
            defaults={
                "entry_type": NewsFeedEntry.EntryType.ARTICLE_PUBLISHED,
                "title": f"New article published: {article.title}",
                "url": article.get_absolute_url(),
                "is_auto": True,
                "is_public": True,
            },
        )
    except Exception:
        logger.exception("Failed to create newsfeed entry for article pk=%s", article.pk)


def _hide_auto_entry(event_key):
    try:
        from newsfeed.models import NewsFeedEntry
        NewsFeedEntry.objects.filter(event_key=event_key, is_auto=True).update(is_public=False)
    except Exception:
        logger.exception("Failed to hide newsfeed entry for event_key=%s", event_key)


def on_recipe_save(sender, instance, **kwargs):
    del sender, kwargs
    from recipes.models import Recipe
    if instance.status == Recipe.Status.APPROVED:
        _create_recipe_entry(instance)
    else:
        _hide_auto_entry(f"recipe_published:{instance.pk}")


def on_recipe_delete(sender, instance, **kwargs):
    del sender, kwargs
    _hide_auto_entry(f"recipe_published:{instance.pk}")


def on_article_save(sender, instance, **kwargs):
    del sender, kwargs
    from articles.models import Article
    if instance.status == Article.Status.APPROVED:
        _create_article_entry(instance)
    else:
        _hide_auto_entry(f"article_published:{instance.pk}")


def on_article_delete(sender, instance, **kwargs):
    del sender, kwargs
    _hide_auto_entry(f"article_published:{instance.pk}")


def on_newsfeed_entry_save(sender, instance, created, **kwargs):
    del sender, kwargs
    if not created:
        return
    if not instance.is_public or instance.is_auto:
        return
    try:
        from newsfeed.telegram import _publish_to_telegram
        parts = [instance.title]
        if instance.message:
            parts.append(instance.message)
        if instance.url:
            from django.conf import settings
            site_url = f"{settings.SITE_SCHEME}://{settings.SITE_DOMAIN}".rstrip("/")
            parts.append(f"{site_url}{instance.url}" if instance.url.startswith("/") else instance.url)
        message = "\n\n".join(parts)
        _publish_to_telegram(
            event_key=f"newsfeed_entry:{instance.pk}",
            message=message,
            target_url=instance.url or "",
        )
    except Exception:
        logger.exception("Failed to publish newsfeed entry pk=%s to Telegram", instance.pk)


def _connect_signals():
    try:
        from recipes.models import Recipe
        post_save.connect(on_recipe_save, sender=Recipe, weak=False)
        post_delete.connect(on_recipe_delete, sender=Recipe, weak=False)
    except ImportError:
        pass

    try:
        from articles.models import Article
        post_save.connect(on_article_save, sender=Article, weak=False)
        post_delete.connect(on_article_delete, sender=Article, weak=False)
    except ImportError:
        pass

    try:
        from newsfeed.models import NewsFeedEntry
        post_save.connect(on_newsfeed_entry_save, sender=NewsFeedEntry, weak=False)
    except ImportError:
        pass


_connect_signals()
