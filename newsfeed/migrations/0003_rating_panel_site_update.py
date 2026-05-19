from django.db import migrations
from django.utils import timezone


def add_rating_panel_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.get_or_create(
        event_key="site_update_rating_panel_v1",
        defaults={
            "entry_type": "site_update",
            "title": "Recipe Ratings Now Show Who Voted",
            "message": (
                "Recipe ratings just got an upgrade. You can now click the rating count on any "
                "recipe page to see a full breakdown by star level, plus a list of community "
                "members who left a rating, with links to their author profiles.\n\n"
                "Ratings submitted while logged in are now linked to your account, so your name "
                "appears in the panel when others view that recipe."
            ),
            "version": "1.4.48",
            "is_public": True,
            "is_auto": False,
            "published_at": timezone.now(),
        },
    )


def remove_rating_panel_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.filter(event_key="site_update_rating_panel_v1").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0002_content_safety_newsfeed_entry"),
    ]

    operations = [
        migrations.RunPython(add_rating_panel_entry, remove_rating_panel_entry),
    ]
