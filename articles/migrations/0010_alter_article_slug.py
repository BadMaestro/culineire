from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('articles', '0009_alter_article_image_rights_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='slug',
            field=models.SlugField(db_index=True, max_length=220, unique=True, verbose_name='Slug'),
        ),
    ]
