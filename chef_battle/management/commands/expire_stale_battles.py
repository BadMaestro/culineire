from django.core.management.base import BaseCommand
from django.utils import timezone

from chef_battle.models import Battle, BattleChallenge
from chef_battle.services import (
    calculate_battle_result,
    expire_stale_challenges,
    handle_no_show_battles,
    resolve_start_rituals,
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

        # --- Start ritual: readiness timer / grace period ---
        due_rituals = Battle.objects.filter(
            status=Battle.Status.SCHEDULED, start_time__lte=now,
        ).count() + Battle.objects.filter(
            status=Battle.Status.WAITING, waiting_until__lte=now,
        ).count()
        if dry:
            self.stdout.write(f"[dry-run] Would resolve {due_rituals} start ritual(s).")
        else:
            started = resolve_start_rituals()
            self.stdout.write(self.style.SUCCESS(f"Resolved {started} start ritual(s)."))

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

        # --- Auto-complete expired voting battles (CB-1402) ---
        expired_voting = Battle.objects.filter(
            status=Battle.Status.VOTING,
            voting_deadline__lte=now,
        )
        voting_count = expired_voting.count()
        if dry:
            self.stdout.write(f"[dry-run] Would complete {voting_count} expired voting battle(s).")
        else:
            completed = 0
            for battle in expired_voting:
                try:
                    calculate_battle_result(battle)
                    completed += 1
                except Exception as exc:
                    self.stderr.write(f"Error completing battle {battle.pk}: {exc}")
            self.stdout.write(self.style.SUCCESS(f"Completed {completed} expired voting battle(s)."))
