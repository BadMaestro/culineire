from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0013_alter_article_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("NEEDS_CHANGES", "Needs changes"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
                verbose_name="Status",
            ),
        ),
    ]
