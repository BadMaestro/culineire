from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from recipes.models import RecipeGenerationTask


class Command(BaseCommand):
    help = "Delete old recipe generation task records."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Delete tasks older than this many days.")
        parser.add_argument("--dry-run", action="store_true", help="Show how many tasks would be deleted.")

    def handle(self, *args, **options):
        days = max(options["days"], 1)
        cutoff = timezone.now() - timedelta(days=days)
        queryset = RecipeGenerationTask.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(f"{count} recipe generation task(s) would be deleted.")
            return

        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} recipe generation task(s)."))
