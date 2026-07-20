"""Put a battle in the arena so the HUD has something to lay out.

Every panel in the reference carries battle content: the phase and its
countdown, the two chefs flanking the crown, the vote and gift counters. With
no battle running they are all empty, and the layout is being positioned blind
against a reference that shows a live one.

This exists as a command rather than a script copied onto the server: it ships
through git, it is reviewable, it runs the same way twice, and it does not
depend on somebody remembering what was in /tmp.

    manage.py demo_battle                 # show what it would do
    manage.py demo_battle --run           # create it
    manage.py demo_battle --end           # finish it and leave the arena quiet

It refuses to start a second battle while one is running, and it goes through
the real path — a challenge, then accept_challenge — so what appears on the
arena is a battle the site itself would have made, not rows written by hand.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Create or finish a demo battle so the arena HUD has content."

    #: The owner's test chefs. Real members are never paired by this command.
    PREFERRED = ("crestedten", "jam-oliver")

    def add_arguments(self, parser):
        parser.add_argument("--run", action="store_true", help="Actually create the battle.")
        parser.add_argument("--end", action="store_true",
                            help="Finish the running demo battle instead.")
        parser.add_argument("--theme", default="Emerald Hall demo",
                            help="Battle theme shown on the arena.")

    def handle(self, *args, **options):
        from chef_battle import services
        from chef_battle.models import Battle, BattleChallenge, ChefBattleProfile

        running = Battle.objects.exclude(status__in=[
            Battle.Status.COMPLETED, Battle.Status.CANCELLED,
            Battle.Status.VOID, Battle.Status.WALKOVER,
        ])

        if options["end"]:
            battle = running.first()
            if battle is None:
                self.stdout.write("Nothing running.")
                return
            battle.status = Battle.Status.CANCELLED
            battle.save(update_fields=["status"])
            self.stdout.write(self.style.SUCCESS(
                "Battle #%s closed; the arena is quiet again." % battle.pk))
            return

        if running.exists():
            battle = running.first()
            self.stdout.write(
                "Already running: #%s %s vs %s (%s). Nothing created."
                % (battle.pk, battle.challenger, battle.opponent, battle.status))
            return

        chefs = list(ChefBattleProfile.objects.select_related("author")
                     .filter(enrolled_at__isnull=False, is_suspended=False)
                     .order_by("author__slug"))
        if len(chefs) < 2:
            raise CommandError("Two enrolled chefs are needed; found %d." % len(chefs))

        preferred = [c for c in chefs if c.author.slug in self.PREFERRED]
        pair = (preferred + [c for c in chefs if c not in preferred])[:2]
        challenger, opponent = pair[0].author, pair[1].author

        self.stdout.write("Enrolled chefs: %s" % ", ".join(c.author.slug for c in chefs))
        self.stdout.write("Pairing: %s vs %s" % (challenger.slug, opponent.slug))
        if not preferred:
            self.stdout.write(self.style.WARNING(
                "Neither test chef is enrolled — this would pair real members."))

        if not options["run"]:
            self.stdout.write("Dry run. Pass --run to create it.")
            return

        now = timezone.now()
        challenge = BattleChallenge.objects.create(
            challenger=challenger,
            opponent=opponent,
            theme=options["theme"],
            status=BattleChallenge.Status.PENDING,
            proposed_start_time=now,
            # Required by the model: a challenge nobody answers has to lapse.
            expires_at=now + timezone.timedelta(days=2),
        )
        battle = services.accept_challenge(challenge)
        self.stdout.write(self.style.SUCCESS(
            "Battle #%s: %s vs %s | status %s | starts %s"
            % (battle.pk, battle.challenger, battle.opponent, battle.status,
               battle.start_time.strftime("%Y-%m-%d %H:%M"))))
        self.stdout.write("The arena HUD now has a phase, a countdown and two chefs.")
