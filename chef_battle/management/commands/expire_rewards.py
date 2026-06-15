"""Management command: expire past-due RewardRecords.

Run via cron alongside expire_stale_battles:
  /srv/culineire/venv/bin/python manage.py expire_rewards
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Expire ISSUED RewardRecords whose expires_at is in the past."

    def handle(self, *args, **options):
        from chef_battle.services import expire_rewards

        count = expire_rewards()
        if count:
            self.stdout.write(self.style.WARNING(f"Expired {count} reward record(s)."))
        else:
            self.stdout.write("No rewards to expire.")
