from django.db import migrations


def create_content_safety_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.get_or_create(
        event_key="site_update_profanity_filter_v1",
        defaults={
            "entry_type": "site_update",
            "title": "Content Safety Filter",
            "message": (
                "All text fields across the site now check for prohibited language in real time. "
                "Recipe titles, descriptions, ingredients, steps, article content, and contact "
                "messages are all covered. Violations are highlighted inline before submission, "
                "keeping the community clean without requiring manual moderation of every post."
            ),
            "version": "1.4.47",
            "is_public": True,
            "is_auto": False,
        },
    )


def reverse_entry(apps, schema_editor):
    NewsFeedEntry = apps.get_model("newsfeed", "NewsFeedEntry")
    NewsFeedEntry.objects.filter(event_key="site_update_profanity_filter_v1").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_content_safety_entry, reverse_entry),
    ]
