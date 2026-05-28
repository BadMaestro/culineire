from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0030_fix_gallery_sort_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="source_note",
            field=models.TextField(blank=True),
        ),
    ]
