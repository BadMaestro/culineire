"""Scenario A, run on the live arena at a pace a person can watch.

THE OWNER, 2026-08-06: «перед началом эмуляции выводи на живую арену - 3 - 2 -
1 - и поехали, с шагом в 5 секунд».

    manage.py run_scenario_a            # run it
    manage.py run_scenario_a --clear    # remove what a run left behind

Why a command and not a script in somebody's scratchpad: this is the thing the
Owner watches, so it has to live where it can be read, reviewed and run again
after everyone has forgotten how it worked.

WHAT IT WRITES, all of it reversible and all of it between the two emulation
bots: one Battle row, their two readiness flags, their last_seen_at, and a few
seconds of cache holding the countdown. It never touches a real chef, never
touches the Owner's account, and never moves a rating.
"""

import time

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from chef_battle import arena_runway
from chef_battle.emulation import EMU_CHEFS
from chef_battle.models import Battle, ChefBattleProfile
from chef_battle.services import get_or_create_battle_profile, pull_start_forward_when_both_ready
from recipes.models import RecipeAuthor

THEME_PREFIX = "Scenario A"
STEP_SECONDS = 5


class Command(BaseCommand):
    help = "Run scenario A on the live arena with a 3-2-1 countdown and a five-second step."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Delete the battles a previous run left and stop.")
        parser.add_argument("--step", type=int, default=STEP_SECONDS,
                            help="Seconds between steps (default 5).")
        parser.add_argument("--lead", type=int, default=12,
                            help="Seconds between arming the countdown and the off.")

    def handle(self, *args, **opts):
        chefs = []
        for slug, _name in EMU_CHEFS:
            author = RecipeAuthor.objects.filter(slug=slug).first()
            if author is None:
                self.stderr.write(f"Emulation bot {slug} does not exist here.")
                return
            # Section 18: the Owner's account is never a participant in anything
            # the game does, and a bot list that ever named him would be a bug
            # worth stopping for rather than working around.
            if slug == settings.OWNER_SLUG:
                self.stderr.write("Refusing: the bot list names the Owner.")
                return
            chefs.append(author)

        removed = Battle.objects.filter(theme__startswith=THEME_PREFIX).delete()
        if opts["clear"]:
            arena_runway.clear()
            self.stdout.write(self.style.SUCCESS(f"Cleared: {removed}"))
            return

        step = max(1, opts["step"])
        a, b = chefs[0], chefs[1]

        # The bots have no browser, so nothing would ever mark them online. The
        # exemption in v2.5.840 covers the ring; this keeps their heartbeat
        # honest for anything else that reads it during the run.
        for author in (a, b):
            profile = get_or_create_battle_profile(author)
            profile.last_seen_at = timezone.now()
            if not profile.enrolled_at:
                profile.enrolled_at = timezone.now()
            profile.save(update_fields=["last_seen_at", "enrolled_at"])

        lead = max(5, opts["lead"])
        arena_runway.start_countdown(lead_seconds=lead, label="POEHALI", steps=6)
        self.stdout.write(f"Countdown armed: the off is in {lead}s. Watch the arena.")
        time.sleep(lead)

        def beat(note):
            arena_runway.announce(note, seconds=step + 2)
            self.stdout.write(f"  · {note}")
            time.sleep(step)

        now = timezone.now()
        beat("A2 - a challenge is accepted. The pair takes two cells side by side.")
        battle = Battle.objects.create(
            challenger=a, opponent=b,
            theme=f"{THEME_PREFIX} - Dublin Coddle",
            status=Battle.Status.SCHEDULED,
            start_time=now + timezone.timedelta(hours=10),
            submission_deadline=now + timezone.timedelta(hours=22),
            end_time=now + timezone.timedelta(days=1),
        )

        beat("A5 - the battle is announced on the Next Battle board, ten hours out.")

        beat("A4 - the pairing holds: it is keyed to the battle, not to the poll.")

        beat("A6 - the first chef presses Ready. Nothing moves yet.")
        battle.challenger_ready = True
        battle.save(update_fields=["challenger_ready", "updated_at"])

        beat("A6 - the second presses Ready. The match is pulled in to fifteen minutes.")
        battle.opponent_ready = True
        moved = pull_start_forward_when_both_ready(battle)
        fields = ["opponent_ready", "updated_at"] + (["start_time"] if moved else [])
        battle.save(update_fields=fields)

        # v2.5.849 (GreenBear, on the Owner's tightened rule): the centre is for
        # a battle that has STARTED. The pair does NOT step out there on Ready
        # any more, so this line stopped being true the moment that shipped.
        beat("The pill climbs the queue. The pair stays in the rings until the battle begins.")

        arena_runway.clear()
        battle.refresh_from_db()
        minutes = (battle.start_time - timezone.now()).total_seconds() / 60
        self.stdout.write(self.style.SUCCESS(
            f"Done. Battle #{battle.pk} starts in {minutes:.1f} min, status {battle.status}."
        ))
