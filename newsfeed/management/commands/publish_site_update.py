from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from newsfeed.models import NewsFeedEntry

_VALID_TYPES = {
    "site_update": NewsFeedEntry.EntryType.SITE_UPDATE,
    "security_update": NewsFeedEntry.EntryType.SECURITY_UPDATE,
    "version_release": NewsFeedEntry.EntryType.VERSION_RELEASE,
    "admin_note": NewsFeedEntry.EntryType.ADMIN_NOTE,
}


class Command(BaseCommand):
    help = "Publish a site update entry to the public news feed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            default="site_update",
            choices=list(_VALID_TYPES.keys()),
            help="Entry type (default: site_update)",
        )
        parser.add_argument("--message", required=True, help="Short update message.")
        parser.add_argument("--ver", default="", help="Version string (e.g. 1.4.3).")
        parser.add_argument("--url", default="", help="Optional link URL.")
        parser.add_argument(
            "--private",
            action="store_true",
            help="Create a private (non-public) entry.",
        )

    def handle(self, *args, **options):
        entry_type = _VALID_TYPES[options["type"]]
        message = options["message"].strip()
        version = options["ver"].strip()
        url = options["url"].strip()
        is_public = not options["private"]

        if not message:
            raise CommandError("--message cannot be empty.")

        if version:
            title = f"Version {version}: {message}"
        else:
            title = message

        entry = NewsFeedEntry.objects.create(
            entry_type=entry_type,
            title=title,
            message=message,
            url=url,
            version=version,
            is_auto=False,
            is_public=is_public,
            published_at=timezone.now(),
        )

        self.stdout.write(self.style.SUCCESS(
            f"Created feed entry #{entry.pk}: {entry.title}"
        ))
