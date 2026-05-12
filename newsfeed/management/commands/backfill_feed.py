from django.core.management.base import BaseCommand

from newsfeed.models import NewsFeedEntry


class Command(BaseCommand):
    help = "Create feed entries for all already-approved recipes and articles."

    def handle(self, *args, **options):
        created = 0

        try:
            from recipes.models import Recipe
            for recipe in Recipe.objects.filter(status=Recipe.Status.APPROVED).iterator():
                _, was_created = NewsFeedEntry.objects.get_or_create(
                    event_key=f"recipe_published:{recipe.pk}",
                    defaults={
                        "entry_type": NewsFeedEntry.EntryType.RECIPE_PUBLISHED,
                        "title": f"New recipe published: {recipe.title}",
                        "url": recipe.get_absolute_url(),
                        "is_auto": True,
                        "is_public": True,
                        "published_at": recipe.created_at,
                    },
                )
                if was_created:
                    created += 1
        except Exception as e:
            self.stderr.write(f"Recipes error: {e}")

        try:
            from articles.models import Article
            from django.utils import timezone
            for article in Article.objects.filter(status=Article.Status.APPROVED).iterator():
                published_at = timezone.make_aware(
                    timezone.datetime.combine(article.published, timezone.datetime.min.time())
                ) if article.published else timezone.now()
                _, was_created = NewsFeedEntry.objects.get_or_create(
                    event_key=f"article_published:{article.pk}",
                    defaults={
                        "entry_type": NewsFeedEntry.EntryType.ARTICLE_PUBLISHED,
                        "title": f"New article published: {article.title}",
                        "url": article.get_absolute_url(),
                        "is_auto": True,
                        "is_public": True,
                        "published_at": published_at,
                    },
                )
                if was_created:
                    created += 1
        except Exception as e:
            self.stderr.write(f"Articles error: {e}")

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} feed entries."))
