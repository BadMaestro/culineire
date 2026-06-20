from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Create or update the Chef's Battle announcement Pinch host object (for comments)"

    SLUG = "chefs-battle-announcement-2026"
    TITLE = "Chef's Battle Announcement — June 2026"
    OWNER_SLUG = "greenbear"

    def handle(self, *args, **options):
        from pinch.models import Pinch
        from recipes.models import RecipeAuthor

        try:
            author = RecipeAuthor.objects.get(slug=self.OWNER_SLUG)
        except RecipeAuthor.DoesNotExist:
            self.stderr.write(f"Author '{self.OWNER_SLUG}' not found — cannot create host object.")
            return

        obj, created = Pinch.objects.update_or_create(
            slug=self.SLUG,
            defaults={
                "title": self.TITLE,
                "author": author,
                "short_description": (
                    "We are building Chef's Battle — a culinary PvP arena for CulinEire. "
                    "Leave your thoughts below."
                ),
                "status": Pinch.Status.APPROVED,
                "is_announcement": True,
                "allow_comments": True,
                "published_at": timezone.now(),
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} host object: slug={self.SLUG}"))
