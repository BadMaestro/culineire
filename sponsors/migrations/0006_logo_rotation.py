from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sponsors', '0005_payment_intent_unique_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsorcell',
            name='logo_rotation',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='sponsorapplication',
            name='logo_rotation',
            field=models.FloatField(default=0.0),
        ),
    ]
