from django.conf import settings
from django.db import migrations, models


def enable_for_owner(apps, schema_editor):
    RecipeAuthor = apps.get_model('recipes', 'RecipeAuthor')
    owner_slug = getattr(settings, 'OWNER_SLUG', 'greenbear')
    RecipeAuthor.objects.filter(slug=owner_slug).update(can_generate_ai_images=True)


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0034_alter_recipe_category_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipeauthor',
            name='can_generate_ai_images',
            field=models.BooleanField(
                default=False,
                help_text='Grants access to AI image generation in the recipe creation form (paid feature).',
                verbose_name='Can generate AI images',
            ),
        ),
        migrations.RunPython(enable_for_owner, migrations.RunPython.noop),
    ]
