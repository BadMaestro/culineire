"""
Idempotent loader for the "Traditional Irish Stew" recipe.

Why a custom command instead of plain `loaddata`:
    Django fixtures cannot reference a ForeignKey by slug unless the related
    model exposes `get_by_natural_key()` on its manager. RecipeAuthor does not,
    and we don't want to hard-code a numeric pk for GreenBear (it differs
    between databases). This command loads the JSON payload from the fixture
    file and resolves the author by slug at runtime.

Usage:
    python manage.py seed_traditional_irish_stew
    python manage.py seed_traditional_irish_stew --author-slug some-other-author
    python manage.py seed_traditional_irish_stew --no-author
"""

from __future__ import annotations

import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


FIXTURE_PATH = (
    Path(apps.get_app_config("recipes").path)
    / "fixtures"
    / "traditional_irish_stew.json"
)


class Command(BaseCommand):
    help = "Create or update the Traditional Irish Stew recipe and link it to GreenBear."

    def add_arguments(self, parser):
        parser.add_argument(
            "--author-slug",
            default="greenbear",
            help="Slug of the RecipeAuthor to attach. Default: greenbear.",
        )
        parser.add_argument(
            "--no-author",
            action="store_true",
            help="Do not attach any author (leave Recipe.author = NULL).",
        )

    def handle(self, *args, **options):
        Recipe = apps.get_model("recipes", "Recipe")
        RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

        if not FIXTURE_PATH.exists():
            raise CommandError(f"Fixture not found: {FIXTURE_PATH}")

        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            raise CommandError(
                f"Fixture {FIXTURE_PATH.name} must be a non-empty JSON array."
            )

        record = payload[0]
        if record.get("model") != "recipes.recipe":
            raise CommandError(
                f"Expected first record model 'recipes.recipe', got {record.get('model')!r}."
            )

        fields = dict(record["fields"])

        # Resolve author by slug at runtime.
        author = None
        if not options["no_author"]:
            slug = options["author_slug"]
            try:
                author = RecipeAuthor.objects.get(slug=slug)
            except RecipeAuthor.DoesNotExist as exc:
                raise CommandError(
                    f'RecipeAuthor with slug="{slug}" not found. '
                    f"Create it first or pass --no-author."
                ) from exc

        fields["author"] = author

        # Drop fields that we want the model to manage itself on save().
        # `slug` is unique and we use it for lookup; `media_folder` is
        # auto-derived; image fields are left untouched on update.
        slug = fields.pop("slug")
        fields.pop("media_folder", None)
        # `hero_image` is a path; leave None if absent.
        if not fields.get("hero_image"):
            fields["hero_image"] = None

        recipe, created = Recipe.objects.update_or_create(
            slug=slug,
            defaults=fields,
        )

        action = "Created" if created else "Updated"
        author_note = (
            f' linked to author "{author.name}"'
            if author is not None
            else " with no author"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} recipe "{recipe.title}"{author_note} '
                f"(id={recipe.pk}, slug={recipe.slug})."
            )
        )
