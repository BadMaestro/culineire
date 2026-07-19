"""Local dev server with the arena flag on.

The arena is gated behind CHEF_BATTLE_ENABLED (off everywhere but a moderator's
session), so a plain `runserver` renders 404 for it and there is nothing to look
at. This starts the same dev server with the flag on for THIS PROCESS ONLY —
nothing is written to .env and production is untouched.

Local visual work only. Never point this at a real environment.
"""

import os
import sys

# env_bool in config/settings.py compares lowercased to "true" — "1" is False.
os.environ["CHEF_BATTLE_ENABLED"] = "true"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, here)
    os.chdir(here)
    from django.core.management import execute_from_command_line

    execute_from_command_line(
        ["manage.py", "runserver", "127.0.0.1:8011", "--noreload"]
    )
