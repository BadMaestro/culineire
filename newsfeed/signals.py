from django.db.models.signals import post_save
from django.dispatch import receiver


def _create_recipe_entry(recipe):
    try:
        from newsfeed.models import NewsFeedEntry
        event_key = f"recipe_published:{recipe.pk}"
        NewsFeedEntry.objects.get_or_create(
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
        pass


def _create_article_entry(article):
    try:
        from newsfeed.models import NewsFeedEntry
        event_key = f"article_published:{article.pk}"
        NewsFeedEntry.objects.get_or_create(
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
        pass


def _connect_recipe_signal():
    try:
        from recipes.models import Recipe

        @receiver(post_save, sender=Recipe)
        def on_recipe_save(sender, instance, **kwargs):
            del sender, kwargs
            if instance.status == Recipe.Status.APPROVED:
                _create_recipe_entry(instance)

    except ImportError:
        pass


def _connect_article_signal():
    try:
        from articles.models import Article

        @receiver(post_save, sender=Article)
        def on_article_save(sender, instance, **kwargs):
            del sender, kwargs
            if instance.status == Article.Status.APPROVED:
                _create_article_entry(instance)

    except ImportError:
        pass


_connect_recipe_signal()
_connect_article_signal()
