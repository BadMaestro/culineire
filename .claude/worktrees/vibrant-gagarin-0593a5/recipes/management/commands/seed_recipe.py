"""
Generic, idempotent loader for any single-recipe JSON fixture in
`recipes/fixtures/`.

Why a custom command instead of plain `loaddata`:
    Django fixtures cannot reference a ForeignKey by slug unless the related
    model exposes `get_by_natural_key()` on its manager. RecipeAuthor does not,
    and we don't want to hard-code a numeric pk for any author (it differs
    between databases). This command loads the JSON payload from the fixture
    file and resolves the author by slug at runtime.

Fixture file format (single object in a list, the same shape Django's
loaddata expects):

    [
      {
        "model": "recipes.recipe",
        "pk": null,
        "fields": {
          "title": "Traditional Irish Stew",
          "slug": "traditional-irish-stew",
          ...
        }
      }
    ]

Usage:

    # default: looks up greenbear as author
    python manage.py seed_recipe --fixture traditional_irish_stew

    # different author
    python manage.py seed_recipe --fixture classic_boxty --author-slug some-author

    # no author at all
    python manage.py seed_recipe --fixture barm_brack --no-author

    # batch — load every *.json in recipes/fixtures/ that contains a single
    # recipes.recipe object (skips index files and prompt files)
    python manage.py seed_recipe --all
"""

from __future__ import annotations

import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


def fixtures_dir() -> Path:
    return Path(apps.get_app_config("recipes").path) / "fixtures"


def fixture_path(name: str) -> Path:
    """Resolve a fixture name (with or without .json) to an absolute path."""
    name = name.strip()
    if not name.endswith(".json"):
        name = f"{name}.json"
    return fixtures_dir() / name


def discover_recipe_fixtures() -> list[Path]:
    """Return JSON files in fixtures/ that look like a single-recipe fixture."""
    found: list[Path] = []
    for path in sorted(fixtures_dir().glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (
                isinstance(payload, list)
                and len(payload) == 1
                and isinstance(payload[0], dict)
                and payload[0].get("model") == "recipes.recipe"
        ):
            found.append(path)
    return found


class Command(BaseCommand):
    help = (
        "Create or update a Recipe from a single-object JSON fixture in "
        "recipes/fixtures/, resolving the FK to RecipeAuthor by slug."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--fixture",
            help='Fixture file name without ".json", e.g. "traditional_irish_stew".',
        )
        target.add_argument(
            "--all",
            action="store_true",
            help="Load every recipe fixture in recipes/fixtures/.",
        )

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
        if options["all"]:
            paths = discover_recipe_fixtures()
            if not paths:
                self.stdout.write(
                    self.style.WARNING("No recipe fixtures found in recipes/fixtures/.")
                )
                return
        else:
            path = fixture_path(options["fixture"])
            if not path.exists():
                raise CommandError(f"Fixture not found: {path}")
            paths = [path]

        for path in paths:
            self._load_one(path, options)

    # -- internals ---------------------------------------------------------

    def _load_one(self, path: Path, options: dict) -> None:
        Recipe = apps.get_model("recipes", "Recipe")
        RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(payload) != 1:
            raise CommandError(
                f"{path.name}: expected a JSON array with exactly one object."
            )

        record = payload[0]
        if record.get("model") != "recipes.recipe":
            raise CommandError(
                f'{path.name}: expected model "recipes.recipe", '
                f'got {record.get("model")!r}.'
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
                    f'{path.name}: RecipeAuthor with slug="{slug}" not found. '
                    "Create it first or pass --no-author."
                ) from exc

        fields["author"] = author

        # Drop / sanitise fields that are managed by the model itself.
        recipe_slug = fields.pop("slug")
        fields.pop("media_folder", None)
        if not fields.get("hero_image"):
            fields["hero_image"] = None

        recipe, created = Recipe.objects.update_or_create(
            slug=recipe_slug,
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
                f'{path.name}: {action} recipe "{recipe.title}"{author_note} '
                f"(id={recipe.pk}, slug={recipe.slug})."
            )
        )
