from django.core.management.base import BaseCommand
from django.utils import timezone

from chef_battle import season_service
from chef_battle.models import Season


class Command(BaseCommand):
    help = (
        "Roll the season lifecycle: close active seasons whose end has passed "
        "(snapshotting standings and resetting scores), then activate the next "
        "upcoming season whose window has started. Safe to run on a cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without changing anything.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry = options["dry_run"]
        closed = activated = 0

        # Close finished active seasons first — this frees the single-active slot.
        for season in Season.objects.filter(status=Season.Status.ACTIVE, ends_at__lte=now):
            if dry:
                self.stdout.write(f"[dry-run] would close '{season.name}'.")
            else:
                result = season_service.close_season(season)
                self.stdout.write(
                    f"Closed '{season.name}': {result['standings_recorded']} standings recorded."
                )
            closed += 1

        # Activate the next upcoming season only if none is active.
        if closed == 0 or dry:
            has_active = season_service.get_active_season() is not None
        else:
            has_active = False  # we just closed the previously-active one(s)
        if not has_active:
            nxt = (
                Season.objects.filter(
                    status=Season.Status.UPCOMING, starts_at__lte=now, ends_at__gt=now
                )
                .order_by("starts_at")
                .first()
            )
            if nxt:
                if dry:
                    self.stdout.write(f"[dry-run] would activate '{nxt.name}'.")
                else:
                    season_service.activate_season(nxt)
                    self.stdout.write(f"Activated '{nxt.name}'.")
                activated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"roll_seasons complete: {activated} activated, {closed} closed"
                + (" (dry-run)" if dry else "")
            )
        )
