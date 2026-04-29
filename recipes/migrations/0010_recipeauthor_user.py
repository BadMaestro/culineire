from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify
import django.db.models.deletion


def link_existing_authors(apps, schema_editor):
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app_label, user_model_name)
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

    linked_user_ids = set(
        RecipeAuthor.objects.exclude(user__isnull=True).values_list("user_id", flat=True)
    )

    for author in RecipeAuthor.objects.filter(user__isnull=True):
        candidates = []
        if author.slug:
            candidates.append(author.slug)
        if author.name:
            candidates.append(slugify(author.name))
            candidates.append(author.name)

        user = None
        for candidate in candidates:
            if not candidate:
                continue
            user = User.objects.filter(username__iexact=candidate).first()
            if user and user.pk not in linked_user_ids:
                break
            user = None

        if user:
            author.user = user
            author.save(update_fields=["user"])
            linked_user_ids.add(user.pk)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("recipes", "0009_recipe_author_commentary"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipeauthor",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="recipe_author_profile",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Linked user account",
            ),
        ),
        migrations.RunPython(link_existing_authors, migrations.RunPython.noop),
    ]
