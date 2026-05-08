from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0014_recipeauthor_has_bearseeker_privileges"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipeauthor",
            name="gender",
            field=models.CharField(
                choices=[
                    ("male", "Male"),
                    ("female", "Female"),
                    ("prefer_not_to_say", "Prefer not to say"),
                ],
                default="prefer_not_to_say",
                max_length=24,
                verbose_name="Gender",
            ),
        ),
    ]
