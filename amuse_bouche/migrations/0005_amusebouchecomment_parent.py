import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("amuse_bouche", "0004_alter_amusebouche_emoji_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="amusebouchecomment",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replies",
                to="amuse_bouche.amusebouchecomment",
            ),
        ),
    ]
