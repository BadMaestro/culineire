from django.db import migrations
from django.utils import timezone


def add_amuse_bouche_launch_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.update_or_create(
        event_key="version_release_amuse_bouche_public_v2",
        defaults={
            "entry_type": "version_release",
            "title": "Amuse-Bouche Is Now Open",
            "message": (
                "CulinEire now has a new short-format space for quick food ideas: Amuse-Bouche.\n\n"
                "Think of it as a small bite before the full meal. A post can be a mini recipe, "
                "Irish bite, snack, sauce, cocktail, plating idea, leftover idea, chef trick or "
                "behind-the-dish note. The rule is simple: short, clear and useful.\n\n"
                "Amuse-Bouche is connected to the rest of the site from day one. Short posts can "
                "lead back to full recipes, readable articles, author pages and future Chef Battle "
                "events, so a quick idea can still point to deeper context.\n\n"
                "The new feed is built for mobile browsing, with approval before publication, "
                "comments, likes, saves and collection support already in place. Logged-in members "
                "can keep useful bites in My Collection and return to them later."
            ),
            "url": "/amuse-bouche/",
            "version": "2.0.0",
            "is_public": True,
            "is_auto": False,
            "published_at": timezone.now(),
        },
    )


def remove_amuse_bouche_launch_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.filter(event_key="version_release_amuse_bouche_public_v2").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0005_alter_newsfeedentry_entry_type"),
    ]

    operations = [
        migrations.RunPython(add_amuse_bouche_launch_entry, remove_amuse_bouche_launch_entry),
    ]
