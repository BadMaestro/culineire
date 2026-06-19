from django.core.management.base import BaseCommand
from django.utils import timezone

from newsfeed.launch_copy import (
    PINCH_LAUNCH_EVENT_KEY,
    PINCH_LAUNCH_MESSAGE,
    PINCH_LAUNCH_TELEGRAM_MESSAGE,
    PINCH_LAUNCH_TITLE,
    PINCH_LAUNCH_URL,
    PINCH_LAUNCH_VERSION,
)
from newsfeed.models import NewsFeedEntry
from newsfeed.telegram import publish_newsfeed_entry_to_telegram


class Command(BaseCommand):
    help = "Publish the Pinch launch news entry and push it to Telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-telegram",
            action="store_true",
            help="Only create/update the public news entry; do not push to Telegram.",
        )

    def handle(self, *args, **options):
        entry = NewsFeedEntry.objects.filter(event_key=PINCH_LAUNCH_EVENT_KEY).first()
        created = entry is None

        if created:
            entry = NewsFeedEntry.objects.create(
                event_key=PINCH_LAUNCH_EVENT_KEY,
                entry_type=NewsFeedEntry.EntryType.VERSION_RELEASE,
                title=PINCH_LAUNCH_TITLE,
                message=PINCH_LAUNCH_MESSAGE,
                url=PINCH_LAUNCH_URL,
                version=PINCH_LAUNCH_VERSION,
                is_public=False,
                is_auto=False,
                published_at=timezone.now(),
            )
        else:
            entry.entry_type = NewsFeedEntry.EntryType.VERSION_RELEASE
            entry.title = PINCH_LAUNCH_TITLE
            entry.message = PINCH_LAUNCH_MESSAGE
            entry.url = PINCH_LAUNCH_URL
            entry.version = PINCH_LAUNCH_VERSION
            entry.is_auto = False

        entry.is_public = True
        entry.published_at = timezone.now()
        entry.save(
            update_fields=[
                "entry_type",
                "title",
                "message",
                "url",
                "version",
                "is_public",
                "is_auto",
                "published_at",
            ]
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} feed entry #{entry.pk}: {entry.title}"))

        if options["skip_telegram"]:
            self.stdout.write("Telegram push skipped.")
            return

        result = publish_newsfeed_entry_to_telegram(
            entry,
            message=PINCH_LAUNCH_TELEGRAM_MESSAGE,
            event_key=f"newsfeed_launch:{PINCH_LAUNCH_EVENT_KEY}",
        )
        if result.status == "sent":
            self.stdout.write(self.style.SUCCESS("Telegram status: sent"))
        elif result.ok:
            self.stdout.write(f"Telegram status: {result.status}")
        else:
            self.stdout.write(f"Telegram status: {result.status} - {result.response}")
