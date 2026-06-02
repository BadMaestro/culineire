from django.db import migrations
from django.utils import timezone

from newsfeed.launch_copy import (
    AMUSE_BOUCHE_LAUNCH_EVENT_KEY,
    AMUSE_BOUCHE_LAUNCH_MESSAGE,
    AMUSE_BOUCHE_LAUNCH_TITLE,
    AMUSE_BOUCHE_LAUNCH_URL,
    AMUSE_BOUCHE_LAUNCH_VERSION,
)


def add_telegram_cta_to_launch_news(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.update_or_create(
        event_key=AMUSE_BOUCHE_LAUNCH_EVENT_KEY,
        defaults={
            "entry_type": "version_release",
            "title": AMUSE_BOUCHE_LAUNCH_TITLE,
            "message": AMUSE_BOUCHE_LAUNCH_MESSAGE,
            "url": AMUSE_BOUCHE_LAUNCH_URL,
            "version": AMUSE_BOUCHE_LAUNCH_VERSION,
            "is_public": True,
            "is_auto": False,
            "published_at": timezone.now(),
        },
    )


def noop_reverse(apps, schema_editor):
    del apps, schema_editor


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0008_refresh_amuse_bouche_launch_v2_copy"),
    ]

    operations = [
        migrations.RunPython(add_telegram_cta_to_launch_news, noop_reverse),
    ]
