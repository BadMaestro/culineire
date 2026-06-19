from django.db import migrations, models


def rename_entry_types(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE newsfeed_newsfeedentry SET entry_type = 'pinch_published' WHERE entry_type = 'amuse_bouche_published'"
        )
        cursor.execute(
            "UPDATE newsfeed_newsfeedentry SET entry_type = 'pinch_featured' WHERE entry_type = 'amuse_bouche_featured'"
        )
        cursor.execute(
            "UPDATE newsfeed_newsfeedentry SET url = REPLACE(url, '/amuse-bouche/', '/pinch/') WHERE url LIKE '%/amuse-bouche/%'"
        )
        cursor.execute(
            "UPDATE newsfeed_newsfeedentry SET event_key = REPLACE(event_key, 'amuse_bouche_published:', 'pinch_published:') WHERE event_key LIKE 'amuse_bouche_published:%'"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0012_add_sub_type_to_newsfeedentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="newsfeedentry",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("recipe_published", "Recipe Published"),
                    ("article_published", "Article Published"),
                    ("pinch_published", "Pinch Published"),
                    ("pinch_featured", "Pinch Featured"),
                    ("site_update", "Site Update"),
                    ("security_update", "Security Update"),
                    ("version_release", "Version Release"),
                    ("admin_note", "Admin Note"),
                    ("battle_event", "Chef Battle Event"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.RunPython(rename_entry_types, migrations.RunPython.noop),
    ]
