from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_active_to_available(apps, schema_editor):
    ChefArtifact = apps.get_model("chef_battle", "ChefArtifact")
    ChefArtifact.objects.filter(status="active").update(status="available")


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0029_tokenorder_extended_payment_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="chefartifact",
            name="reserved_in_battle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reserved_artifacts",
                to="chef_battle.battle",
            ),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="expired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="reversed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="admin_granted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="admin_granted_artifacts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="admin_grant_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="chefartifact",
            name="source",
            field=models.CharField(
                choices=[
                    ("purchased", "Purchased"),
                    ("gifted", "Gifted"),
                    ("drop", "Battle Drop"),
                    ("admin_grant", "Admin Grant"),
                ],
                default="purchased",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="chefartifact",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("reserved", "Reserved (in active battle)"),
                    ("consumed", "Consumed"),
                    ("expired", "Expired"),
                    ("reversed", "Reversed"),
                ],
                db_index=True,
                default="available",
                max_length=10,
            ),
        ),
        migrations.RunPython(migrate_active_to_available, migrations.RunPython.noop),
    ]
