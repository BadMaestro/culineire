from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pinch", "0001_initial"),
    ]

    operations = [
        migrations.RenameField("PinchGalleryImage", "amuse_bouche", "pinch"),
        migrations.RenameField("PinchComment", "amuse_bouche", "pinch"),
        migrations.AlterModelTable("Pinch", None),
        migrations.AlterModelTable("PinchGalleryImage", None),
        migrations.AlterModelTable("PinchComment", None),
    ]
