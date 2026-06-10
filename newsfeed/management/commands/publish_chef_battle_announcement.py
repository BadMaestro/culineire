from django.core.management.base import BaseCommand
from django.utils import timezone

from newsfeed.models import NewsFeedEntry
from newsfeed.telegram import publish_newsfeed_entry_to_telegram

_EVENT_KEY = "chef_battle:announcement_2026_06"

_TITLE = "Something Big Is Coming To CulinEire"

_MESSAGE = (
    "We are building Chef's Battle, a live culinary duelling arena. "
    "Chefs challenge each other, cook to a theme, and the community decides who wins. "
    "Ranked seasons, leaderboards and crowns for the best in the kitchen. Watch this space."
)

_TELEGRAM_MESSAGE = (
    "Something big is coming to CulinEire.\n\n"
    "Chef's Battle: a live culinary PvP arena where chefs duel on a theme "
    "and the community votes for the winner. Ranked seasons, leaderboards, crowns.\n\n"
    "Watch this space. https://culineire.ie"
)

_URL = "/"


class Command(BaseCommand):
    help = "Publish the Chef's Battle announcement to the newsfeed and Telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-telegram",
            action="store_true",
            help="Only create/update the newsfeed entry; do not push to Telegram.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be published without creating anything.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            self.stdout.write("--- DRY RUN ---")
            self.stdout.write(f"Title:   {_TITLE}")
            self.stdout.write(f"Message: {_MESSAGE}")
            self.stdout.write(f"Telegram:\n{_TELEGRAM_MESSAGE}")
            return

        entry = NewsFeedEntry.objects.filter(event_key=_EVENT_KEY).first()
        created = entry is None

        if created:
            entry = NewsFeedEntry.objects.create(
                event_key=_EVENT_KEY,
                entry_type=NewsFeedEntry.EntryType.SITE_UPDATE,
                title=_TITLE,
                message=_MESSAGE,
                url=_URL,
                is_public=True,
                is_auto=False,
                published_at=timezone.now(),
            )
        else:
            entry.title = _TITLE
            entry.message = _MESSAGE
            entry.url = _URL
            entry.is_public = True
            entry.published_at = timezone.now()
            entry.save(update_fields=["title", "message", "url", "is_public", "published_at"])

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} feed entry #{entry.pk}: {entry.title}"))

        if options["skip_telegram"]:
            self.stdout.write("Telegram push skipped.")
            return

        result = publish_newsfeed_entry_to_telegram(
            entry,
            message=_TELEGRAM_MESSAGE,
            event_key=f"newsfeed_telegram:{_EVENT_KEY}",
        )
        if result.status == "sent":
            self.stdout.write(self.style.SUCCESS("Telegram: sent"))
        elif result.ok:
            self.stdout.write(f"Telegram: {result.status}")
        else:
            self.stdout.write(self.style.ERROR(f"Telegram: {result.status} — {result.response}"))
