from django.core.management.base import BaseCommand
from django.utils import timezone

from chef_battle.models import Battle, BattleChallenge, BattleEvent
from chef_battle.services import (
    create_battle_event,
    expire_stale_challenges,
    handle_no_show_battles,
)


class Command(BaseCommand):
    help = (
        "Expire pending challenges past their deadline and handle no-show battles "
        "where one or both chefs missed the submission deadline."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without making any changes.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        now = timezone.now()

        # --- Expire stale challenges ---
        stale = BattleChallenge.objects.filter(
            status=BattleChallenge.Status.PENDING,
            expires_at__lte=now,
        )
        challenge_count = stale.count()
        if dry:
            self.stdout.write(f"[dry-run] Would expire {challenge_count} pending challenge(s).")
        else:
            expired = expire_stale_challenges()
            self.stdout.write(self.style.SUCCESS(f"Expired {expired} pending challenge(s)."))

        # --- Handle no-show battles ---
        no_show_battles = Battle.objects.filter(
            status__in=[Battle.Status.ACTIVE, Battle.Status.AWAITING_SUBMISSIONS],
            submission_deadline__lte=now,
        )
        no_show_count = no_show_battles.count()
        if dry:
            self.stdout.write(f"[dry-run] Would process {no_show_count} no-show battle(s).")
        else:
            handled = handle_no_show_battles()
            self.stdout.write(self.style.SUCCESS(f"Processed {handled} no-show battle(s)."))
