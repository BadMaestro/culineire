from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Refresh the local sanctions cache from configured official EU/UN providers."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=("eu", "un", "all"), required=True)

    def handle(self, *args, **options):
        raise CommandError(
            "Official EU/UN source ingestion is not configured yet. "
            "Use reviewed manual SanctionsEntry records until an official-source adapter is deployed."
        )
