"""
Remove User accounts that have no linked RecipeAuthor profile.
Superusers and staff are always preserved.

Usage:
    python manage.py purge_orphan_users           # dry-run (preview only)
    python manage.py purge_orphan_users --confirm # actually delete
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete users with no RecipeAuthor profile (superusers/staff are kept)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually delete the users. Without this flag the command only previews.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()

        orphans = user_model.objects.filter(
            recipe_author_profile__isnull=True,
            is_superuser=False,
            is_staff=False,
        )

        count = orphans.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphan users found."))
            return

        self.stdout.write(f"Found {count} user(s) with no author profile:\n")
        for u in orphans:
            self.stdout.write(f"  • {u.username} (id={u.pk}, email={u.email})")

        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry-run — nothing deleted. Re-run with --confirm to delete."
                )
            )
            return

        orphans.delete()
        self.stdout.write(self.style.SUCCESS(f"\nDeleted {count} orphan user(s)."))
