from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from recipes.models import RecipeAuthor


def _unique_slug(base):
    slug = slugify(base) or "author"
    if not RecipeAuthor.objects.filter(slug=slug).exists():
        return slug
    counter = 2
    while RecipeAuthor.objects.filter(slug=f"{slug}-{counter}").exists():
        counter += 1
    return f"{slug}-{counter}"


class Command(BaseCommand):
    help = "Create a RecipeAuthor profile for every user who does not have one."

    def handle(self, *args, **options):
        user_model = get_user_model()
        created = 0

        for user in user_model.objects.filter(recipe_author_profile__isnull=True):
            slug = _unique_slug(user.username)
            RecipeAuthor.objects.create(user=user, name=user.username, slug=slug)
            self.stdout.write(f"  Created profile for: {user.username} (slug: {slug})")
            created += 1

        if created:
            self.stdout.write(self.style.SUCCESS(f"\nDone. Created {created} author profile(s)."))
        else:
            self.stdout.write("All users already have author profiles.")
