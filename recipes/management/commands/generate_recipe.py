from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from recipes.models import ALLERGEN_CHOICES, Recipe, RecipeAuthor


AI_SOURCE_NOTE = "AI-assisted draft generated for human review. Verify accuracy, attribution, allergens, and image rights before publishing."


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise CommandError("Anthropic response did not contain a JSON object.")
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise CommandError(f"Anthropic response was not valid JSON: {exc}") from exc


def _to_text_lines(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _to_int(value, default=0, minimum=0, maximum=32767) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _to_optional_int(value):
    if value in (None, ""):
        return None
    parsed = _to_int(value, default=0, minimum=0)
    return parsed or None


def _map_category(value: str) -> str:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    labels = {choice.label.lower(): choice.value for choice in Recipe.Category}
    values = {choice.value.lower(): choice.value for choice in Recipe.Category}
    return values.get(raw) or labels.get((value or "").strip().lower()) or Recipe.Category.EVERYDAY_IRISH_COOKING


def _map_difficulty(value: str) -> str:
    raw = (value or "").strip().lower()
    valid = {choice.value for choice in Recipe.Difficulty}
    return raw if raw in valid else Recipe.Difficulty.EASY


def _map_allergens(value) -> str:
    valid = {key for key, _label in ALLERGEN_CHOICES}
    labels = {label.lower(): key for key, label in ALLERGEN_CHOICES}
    items = value if isinstance(value, list) else str(value or "").replace(",", "\n").splitlines()
    mapped = []
    for item in items:
        raw = str(item).strip().lower()
        key = raw if raw in valid else labels.get(raw)
        if key and key not in mapped:
            mapped.append(key)
    return ",".join(mapped)


def _unique_slug(title: str) -> str:
    base = slugify(title)[:210].strip("-") or "recipe"
    slug = base
    counter = 2
    while Recipe.objects.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[:220 - len(suffix)]}{suffix}"
        counter += 1
    return slug


def _normalise_recipe_payload(payload: dict, dish_name: str, status: str) -> dict:
    title = str(payload.get("title") or dish_name).strip()[:200]
    if not title:
        raise CommandError("Generated recipe has no title.")
    ingredients = _to_text_lines(payload.get("ingredients"))
    method = _to_text_lines(payload.get("method"))
    if not ingredients or not method:
        raise CommandError(f'Generated recipe "{title}" must include ingredients and method.')

    return {
        "title": title,
        "slug": _unique_slug(title),
        "short_description": str(payload.get("short_description") or "").strip(),
        "category": _map_category(payload.get("category")),
        "difficulty": _map_difficulty(payload.get("difficulty")),
        "prep_time_minutes": _to_int(payload.get("prep_time_minutes"), default=0),
        "cook_time_minutes": _to_int(payload.get("cook_time_minutes"), default=0),
        "servings": _to_int(payload.get("servings"), default=4, minimum=1),
        "calories": _to_optional_int(payload.get("calories")),
        "ingredients": ingredients,
        "method": method,
        "tips": str(payload.get("tips") or "").strip(),
        "irish_context": str(payload.get("irish_context") or "").strip(),
        "author_commentary": str(payload.get("author_commentary") or "").strip(),
        "allergens": _map_allergens(payload.get("allergens")),
        "source_type": Recipe.SourceType.OTHER,
        "source_title": str(payload.get("source_title") or "AI-assisted draft").strip()[:255],
        "source_author": str(payload.get("source_author") or "CulinEire editorial workflow").strip()[:255],
        "source_url": str(payload.get("source_url") or "").strip(),
        "source_note": str(payload.get("source_note") or AI_SOURCE_NOTE).strip()[:255],
        "image_rights_status": Recipe.ImageRightsStatus.NOT_APPLICABLE,
        "image_rights_note": "No image generated or uploaded by this command.",
        "status": status,
        "confirmed_own_work": False,
        "confirmed_image_rights": False,
        "confirmed_rules": False,
    }


def _prompt_for_recipe(dish_name: str) -> str:
    categories = ", ".join(choice.value for choice in Recipe.Category)
    allergens = ", ".join(key for key, _label in ALLERGEN_CHOICES)
    return (
        f'Create a CulinEire recipe draft for "{dish_name}". Return strict JSON only. '
        "Use these keys: title, short_description, category, difficulty, prep_time_minutes, "
        "cook_time_minutes, servings, calories, ingredients, method, tips, irish_context, "
        "author_commentary, allergens, source_title, source_author, source_url, source_note. "
        f"category must be one of: {categories}. "
        f"allergens must use these keys only: {allergens}. "
        "ingredients and method must be arrays of strings. Do not include image URLs. "
        "This is a draft for human review, not a published recipe."
    )


def _call_anthropic(dish_name: str) -> dict:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise CommandError("ANTHROPIC_API_KEY is not configured.")
    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": _prompt_for_recipe(dish_name)}],
    }
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CommandError(f"Anthropic API returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise CommandError(f"Anthropic API request failed: {exc}") from exc
    parsed = json.loads(body)
    text = "\n".join(block.get("text", "") for block in parsed.get("content", []) if block.get("type") == "text")
    return _extract_json(text)


class Command(BaseCommand):
    help = "Generate AI-assisted recipe drafts. Recipes are saved as draft/pending only."

    def add_arguments(self, parser):
        parser.add_argument("dish_name", nargs="*", help='Dish name, e.g. "Irish Colcannon".')
        parser.add_argument("--batch", help="Path to a .txt file with one dish name per line.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum batch items to process.")
        parser.add_argument("--author-slug", default="greenbear", help="RecipeAuthor slug to attach.")
        parser.add_argument("--status", choices=[Recipe.Status.DRAFT, Recipe.Status.PENDING], default=Recipe.Status.DRAFT)
        parser.add_argument("--dry-run", action="store_true", help="Call the generator and print normalized data without saving.")

    def handle(self, *args, **options):
        dish_names = self._dish_names(options)
        if not dish_names:
            raise CommandError("Provide a dish name or --batch file.")

        try:
            author = RecipeAuthor.objects.get(slug=options["author_slug"])
        except RecipeAuthor.DoesNotExist as exc:
            raise CommandError(f'RecipeAuthor with slug "{options["author_slug"]}" not found.') from exc

        for dish_name in dish_names:
            payload = _call_anthropic(dish_name)
            fields = _normalise_recipe_payload(payload, dish_name, options["status"])
            if options["dry_run"]:
                self.stdout.write(json.dumps(fields, indent=2, ensure_ascii=False))
                continue
            with transaction.atomic():
                recipe = Recipe.objects.create(author=author, **fields)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created {recipe.get_status_display().lower()} recipe "{recipe.title}" ({recipe.slug}).'
                )
            )

    @staticmethod
    def _dish_names(options) -> list[str]:
        if options.get("batch"):
            path = Path(options["batch"])
            if not path.exists():
                raise CommandError(f"Batch file not found: {path}")
            names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            limit = options.get("limit") or 0
            return names[:limit] if limit > 0 else names
        return [" ".join(options.get("dish_name") or []).strip()]
