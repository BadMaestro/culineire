from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from recipes.models import ALLERGEN_CHOICES, Recipe, RecipeAdditionalCategory, RecipeAuthor, RecipeImage

logger = logging.getLogger("recipes")


AI_SOURCE_TITLE = "Created specially for CulinEire"
AI_SOURCE_AUTHOR = "CulinEire Creative Studio"
AI_SOURCE_NOTE = (
    "An original CulinEire recipe, crafted with AI and reviewed by our editorial team. "
    "Free to cook and enjoy at home. "
    "If you liked it, a rating or a kind comment is the best way to say thanks."
)


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


def _map_additional_categories(value, primary_category: str) -> list[str]:
    valid = {choice.value for choice in Recipe.Category}
    items = value if isinstance(value, list) else []
    result = []
    for item in items:
        raw = str(item).strip().lower().replace("-", "_").replace(" ", "_")
        labels = {choice.label.lower(): choice.value for choice in Recipe.Category}
        mapped = raw if raw in valid else labels.get(str(item).strip().lower())
        if mapped and mapped != primary_category and mapped not in result:
            result.append(mapped)
    return result


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
        "source_type": Recipe.SourceType.AI_ASSISTED,
        "source_title": AI_SOURCE_TITLE,
        "source_author": AI_SOURCE_AUTHOR,
        "source_url": "https://www.culineire.ie/",
        "source_note": AI_SOURCE_NOTE,
        "image_rights_status": Recipe.ImageRightsStatus.NOT_APPLICABLE,
        "image_rights_note": "No image uploaded. Add a photo before publishing.",
        "status": status,
        "confirmed_own_work": False,
        "confirmed_image_rights": False,
        "confirmed_rules": False,
    }


WRITING_RULES = (
    "VOICE AND AUTHENTICITY: Write as an experienced Irish home cook who has made this dish many times. "
    "Include specific sensory details: exact taste, texture, smell, appearance. "
    "Show real kitchen knowledge — techniques, timings, what can go wrong, what to look for. "
    "Every sentence must earn its place. Cut anything that could apply to any other dish. "
    "No generic heritage phrases. No unverified historical claims. No invented regional traditions. "
    "No tourist-brochure tone. No food-blog enthusiasm. No SEO padding. "
    "The reader must never suspect a machine wrote this. "

    "FORBIDDEN WORDS: never use rich, vibrant, unique, authentic, iconic, beloved, hearty, comforting, "
    "flavourful, timeless, delightful, wonderful, amazing, incredible, perfect, ultimate, essential. "
    "FORBIDDEN PHRASES: never use 'culinary journey', 'perfect balance', 'passed down through generations', "
    "'deeply rooted', 'cultural significance', 'a taste of tradition', 'more than just', "
    "'not only... but also', 'in conclusion', 'moreover', 'furthermore', 'in addition', "
    "'plays an important role', 'from past to present', 'this highlights', 'this demonstrates', "
    "'overall', 'crowd-pleaser', 'comfort food classic', 'quick and easy', 'packed with flavour', "
    "'bursting with flavour', 'weeknight dinner', 'you'll love this', 'family favourite'. "
    "FORBIDDEN STRUCTURE: no generic opening sentence, no generic closing sentence, "
    "no paragraphs that could swap places without loss of meaning. "
    "FORBIDDEN PUNCTUATION: never use em dash (—), double dash (--), or excessive dashes of any kind. "
    "Use commas, full stops, brackets, or semicolons instead. "

    "BRITISH/IRISH ENGLISH ONLY: use flavour, colour, centre, organise, analyse, ageing, learnt. "
    "IRISH/UK CULINARY TERMS ONLY: use coriander (not cilantro), spring onions (not scallions), "
    "courgette (not zucchini), aubergine (not eggplant), rocket (not arugula), "
    "beetroot (not beets), minced meat (not ground meat), double cream (not heavy cream), "
    "plain flour (not all-purpose flour), icing sugar (not powdered sugar), "
    "baking tray (not baking sheet), frying pan (not skillet), grill (not broil/broiler). "
    "METRIC MEASUREMENTS ONLY: use grams, ml, Celsius. No cups, ounces, pounds, Fahrenheit. "
    "No American food-blog tone. No American date format. No American holidays or occasions. "
    "ALT TEXT: hero_image_alt_text must be short keyword-style tags under 100 characters, "
    "comma-separated, no full sentences, no verbs, no adjectives like 'delicious' or 'hearty'. "
    "Example: 'colcannon, Irish mashed potato, spring onions, butter, white bowl'."
)


def _prompt_for_recipe(dish_name: str) -> str:
    categories = ", ".join(choice.value for choice in Recipe.Category)
    allergen_pairs = ", ".join(f"{key} ({label})" for key, label in ALLERGEN_CHOICES)
    return (
        f'Create an original CulinEire recipe draft for "{dish_name}". '
        "Return strict JSON only with these keys: "
        "title, short_description, category, additional_categories, difficulty, prep_time_minutes, "
        "cook_time_minutes, servings, calories, ingredients, method, tips, "
        "irish_context, author_commentary, allergens, hero_image_alt_text. "
        f"category must be one of: {categories}. "
        "additional_categories must be an array of other relevant category values from the same list "
        "(do not repeat the primary category, include 2-4 that genuinely apply). "
        "difficulty must be one of: easy, medium, hard. "
        f"allergens must be an array using only these exact keys: {allergen_pairs}. "
        "List every allergen actually present in the recipe ingredients — do not leave it empty. "
        "ingredients must be an array of strings with exact gram/ml quantities. "
        "method must be an array of strings with precise techniques, temperatures in Celsius, and timings. "
        "Do not reference any real cookbook authors, websites, or external sources. "
        "Do not include image URLs. "
        "This recipe is an original creation for human review before publishing. "
        + WRITING_RULES
    )


def _sanitise_image_subject(title: str, alt_text: str) -> str:
    subject = alt_text.strip() if alt_text and alt_text.strip() else title
    return subject[:300]


# ── Visual planner ─────────────────────────────────────────────────────────────

def _planner_prompt(fields: dict) -> str:
    title = fields.get("title", "")
    short_description = fields.get("short_description", "")
    ingredients = fields.get("ingredients", "")
    method = fields.get("method", "")
    return (
        "You are a recipe visual planning assistant.\n\n"
        "Convert this cooking recipe into a strict visual generation plan "
        "for one hero image and exactly 3 step images.\n\n"
        "Rules:\n"
        "1. Select 3 key steps: one early (e.g. raw/prep stage), one middle (active cooking), "
        "one near-final (just before plating or baking finish).\n"
        "2. For each step, describe the exact visual state of the food at that moment.\n"
        "3. Do not invent ingredients, utensils, or stages not present in the recipe.\n"
        "4. Do not show a later stage in an earlier step.\n"
        "5. Maintain visual continuity: same cookware family, same kitchen style, same dish identity.\n"
        "6. For each step, explicitly list must_not_show_yet to prevent showing final dish too early.\n\n"
        "Return STRICT JSON only — no markdown, no explanation:\n"
        "{\n"
        '  "hero_image": {\n'
        '    "food_state": "string",\n'
        '    "visible_ingredients": ["string"],\n'
        '    "cookware": ["string"],\n'
        '    "background_style": "string",\n'
        '    "camera_angle": "string",\n'
        '    "must_not_show": ["string"]\n'
        "  },\n"
        '  "steps": [\n'
        "    {\n"
        '      "step_number": 1,\n'
        '      "step_summary": "string",\n'
        '      "food_state": "string",\n'
        '      "visible_ingredients": ["string"],\n'
        '      "cookware": ["string"],\n'
        '      "camera_angle": "string",\n'
        '      "continuity_notes": "string",\n'
        '      "must_not_show_yet": ["string"]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Recipe title: {title}\n"
        f"Short description: {short_description}\n\n"
        f"Ingredients:\n{ingredients}\n\n"
        f"Method:\n{method}"
    )


def _call_visual_planner(fields: dict) -> dict:
    """Call Anthropic to build a structured visual plan for the recipe images."""
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}
    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": _planner_prompt(fields)}],
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
        parsed = json.loads(body)
        text = "\n".join(
            block.get("text", "")
            for block in parsed.get("content", [])
            if block.get("type") == "text"
        )
        return _extract_json(text)
    except Exception as exc:
        logger.warning("generate_recipe: visual planner failed: %s — falling back to legacy prompts", exc)
        return {}


def _build_hero_prompt(title: str, plan: dict, feedback: str = "") -> str:
    food_state = (plan.get("food_state") or "").strip()
    visible = ", ".join(plan.get("visible_ingredients") or [])
    cookware = ", ".join(plan.get("cookware") or [])
    camera = (plan.get("camera_angle") or "close-up, slightly overhead").strip()
    background = (plan.get("background_style") or "rustic wooden surface").strip()
    must_not = ", ".join(plan.get("must_not_show") or [])

    parts = [f"Realistic editorial food photograph of the finished dish: {title}."]
    if food_state:
        parts.append(f"Food state: {food_state}.")
    if visible:
        parts.append(f"Visible: {visible}.")
    if cookware:
        parts.append(f"Served in: {cookware}.")
    if must_not:
        parts.append(f"Must not show: {must_not}.")
    parts.append(f"Camera: {camera}. Background: {background}.")
    parts.append(
        "Soft natural light. Irish cuisine. Professional recipe website quality. "
        "No text, no watermarks, no people, no logos."
    )
    if feedback:
        parts.append(f"Important: {feedback}.")
    return " ".join(parts)


def _build_step_prompt(title: str, step: dict, feedback: str = "") -> str:
    step_num = step.get("step_number", "")
    summary = (step.get("step_summary") or "").strip()
    food_state = (step.get("food_state") or "").strip()
    visible = ", ".join(step.get("visible_ingredients") or [])
    cookware = ", ".join(step.get("cookware") or [])
    camera = (step.get("camera_angle") or "45-degree angle").strip()
    continuity = (step.get("continuity_notes") or "").strip()
    must_not = ", ".join(step.get("must_not_show_yet") or [])

    parts = [
        f"Realistic editorial cooking step photo for the recipe '{title}'.",
        f"Step {step_num}: {summary}." if summary else f"Step {step_num}.",
        "Show this exact stage — not an earlier or later stage.",
    ]
    if food_state:
        parts.append(f"Food state at this moment: {food_state}.")
    if visible:
        parts.append(f"Visible: {visible}.")
    if cookware:
        parts.append(f"Cookware: {cookware}.")
    if must_not:
        parts.append(f"Must not show yet: {must_not}.")
    if continuity:
        parts.append(f"Visual continuity: {continuity}.")
    parts.append(f"Camera: {camera}.")
    parts.append(
        "Soft natural light, rustic kitchen setting. "
        "This is an intermediate cooking stage unless it is the final step. "
        "No text, no watermarks, no people, no logos."
    )
    if feedback:
        parts.append(f"Important: {feedback}.")
    return " ".join(parts)


def _generate_step_photos_from_plan(recipe: Recipe, steps: list[dict]) -> list[RecipeImage]:
    """Generate step photos using the structured visual plan from the planner."""
    created = []
    for gallery_pos, step in enumerate(steps, start=1):
        prompt = _build_step_prompt(recipe.title, step)
        step_num = step.get("step_number", gallery_pos)
        step_text = (step.get("step_summary") or step.get("food_state") or "")[:200]
        try:
            image_bytes = fetch_image_bytes(prompt)
        except (CommandError, Exception) as exc:
            logger.warning("generate_recipe: step photo (plan) failed for step %s of %r: %s", step_num, recipe.title, exc)
            continue
        img = RecipeImage(
            recipe=recipe,
            sort_order=gallery_pos,
            alt_text=step_text,
            caption=f"Step {step_num}",
        )
        img.image.save(f"step{gallery_pos}-{recipe.slug[:30]}.jpg", ContentFile(image_bytes), save=False)
        img.save()
        created.append(img)
    return created


def fetch_image_bytes(prompt: str) -> bytes:
    """Call OpenAI image API with the given prompt and return raw image bytes."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise CommandError("OPENAI_API_KEY is not configured.")
    model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
    quality = getattr(settings, "OPENAI_IMAGE_QUALITY", "low")
    payload = {"model": model, "prompt": prompt, "n": 1, "size": "1024x1024", "quality": quality}
    req = Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise CommandError(f"OpenAI API returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise CommandError(f"OpenAI image request failed: {exc}") from exc
    parsed = json.loads(body)
    image_entry = parsed["data"][0]
    if "b64_json" in image_entry:
        return base64.b64decode(image_entry["b64_json"])
    image_url = image_entry["url"]
    with urlopen(image_url, timeout=30) as img_response:
        return img_response.read()


def _generate_image(title: str, short_description: str, alt_text: str = "", feedback: str = "") -> tuple[bytes, str]:
    subject = _sanitise_image_subject(title, alt_text)
    prompt = (
        f"Professional food photography: {subject}. "
        "Irish cuisine, natural light, rustic wooden surface, ceramic or white plate, "
        "appetising close-up presentation. No text, no watermarks, no people, no brand names or logos."
    )
    if feedback:
        prompt += f" Important: {feedback}."
    return fetch_image_bytes(prompt), f"{title}, served and photographed"


def _pick_key_steps(method_text: str, max_steps: int = 3) -> list[tuple[int, str]]:
    steps = [s.strip() for s in method_text.splitlines() if s.strip()]
    if not steps:
        return []
    if len(steps) <= max_steps:
        return list(enumerate(steps, start=1))
    indices = [0, len(steps) // 2, len(steps) - 1]
    seen = set()
    result = []
    for i in indices:
        if i not in seen:
            seen.add(i)
            result.append((i + 1, steps[i]))
    return result


def _generate_step_photos(recipe: Recipe, method_text: str) -> list[RecipeImage]:
    key_steps = _pick_key_steps(method_text)
    total = len(key_steps)
    created = []
    for gallery_pos, (step_num, step_text) in enumerate(key_steps, start=1):
        prompt = (
            f"Professional food photography for the dish '{recipe.title}'. "
            f"Step {step_num} of {total}: {step_text[:250]}. "
            "Irish cuisine, natural lighting, rustic kitchen setting. "
            "No text, no watermarks, no people, no brand names or logos."
        )
        try:
            image_bytes = fetch_image_bytes(prompt)
        except (CommandError, Exception) as exc:
            logger.warning("generate_recipe: step photo failed for step %d of %r: %s", step_num, recipe.title, exc)
            continue
        img = RecipeImage(
            recipe=recipe,
            sort_order=gallery_pos,
            alt_text=step_text[:200],
            caption=f"Step {step_num}",
        )
        img.image.save(f"step{gallery_pos}-{recipe.slug[:30]}.jpg", ContentFile(image_bytes), save=False)
        img.save()
        created.append(img)
    return created


def _call_anthropic(dish_name: str) -> dict:
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise CommandError("ANTHROPIC_API_KEY is not configured.")
    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 4000,
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
        parser.add_argument("--author-slug", default="crestedten", help="RecipeAuthor slug to attach.")
        parser.add_argument("--status", choices=[Recipe.Status.DRAFT, Recipe.Status.PENDING], default=Recipe.Status.DRAFT)
        parser.add_argument("--dry-run", action="store_true", help="Call the generator and print normalized data without saving.")
        parser.add_argument("--no-image", action="store_true", help="Skip image generation even if OPENAI_API_KEY is set.")

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
            from articles.services.editorial_tools import suggest_recipe_fields
            fields.update(suggest_recipe_fields(fields))
            additional_categories = _map_additional_categories(
                payload.get("additional_categories"), fields["category"]
            )
            if options["dry_run"]:
                self.stdout.write(json.dumps(
                    {**fields, "additional_categories": additional_categories},
                    indent=2, ensure_ascii=False,
                ))
                continue
            with transaction.atomic():
                recipe = Recipe.objects.create(author=author, **fields)
                for cat in additional_categories:
                    RecipeAdditionalCategory.objects.create(recipe=recipe, category=cat)

            openai_key = getattr(settings, "OPENAI_API_KEY", "")
            generate_image = not options.get("no_image") and bool(openai_key)
            if not openai_key:
                logger.warning("generate_recipe: OPENAI_API_KEY is not set — skipping image generation for %r", recipe.title)
            elif options.get("no_image"):
                logger.info("generate_recipe: --no-image flag set — skipping image generation for %r", recipe.title)

            if generate_image:
                # Build structured visual plan first (planner → image flow)
                logger.info("generate_recipe: calling visual planner for %r", recipe.title)
                visual_plan = _call_visual_planner(fields)
                hero_plan = visual_plan.get("hero_image", {}) if visual_plan else {}
                steps_plan = visual_plan.get("steps", []) if visual_plan else []
                if visual_plan:
                    logger.info(
                        "generate_recipe: visual plan ready — %d step(s) planned for %r",
                        len(steps_plan), recipe.title,
                    )
                else:
                    logger.warning("generate_recipe: visual planner returned nothing — using legacy prompts for %r", recipe.title)

                # Hero image
                try:
                    ai_alt_text = str(payload.get("hero_image_alt_text") or "").strip()[:125]
                    if hero_plan:
                        hero_prompt = _build_hero_prompt(recipe.title, hero_plan)
                        image_bytes = fetch_image_bytes(hero_prompt)
                        fallback_alt = f"{recipe.title}, served and photographed"
                    else:
                        image_bytes, fallback_alt = _generate_image(recipe.title, recipe.short_description, ai_alt_text)
                    recipe.hero_image.save(f"cover-{recipe.slug[:40]}.jpg", ContentFile(image_bytes), save=False)
                    recipe.hero_image_alt_text = ai_alt_text or fallback_alt
                    recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
                    recipe.image_rights_note = "AI-generated image via DALL-E 3."
                    recipe.save(update_fields=["hero_image", "hero_image_alt_text", "image_rights_status", "image_rights_note"])
                    logger.info("generate_recipe: hero image generated and saved for %r", recipe.title)
                except CommandError as exc:
                    logger.error("generate_recipe: hero image generation failed for %r: %s", recipe.title, exc)

                # Step photos
                try:
                    if steps_plan:
                        step_photos = _generate_step_photos_from_plan(recipe, steps_plan)
                    else:
                        step_photos = _generate_step_photos(recipe, fields["method"])
                    if step_photos:
                        logger.info("generate_recipe: %d step photo(s) generated for %r", len(step_photos), recipe.title)
                except Exception as exc:
                    logger.error("generate_recipe: step photos failed for %r: %s", recipe.title, exc, exc_info=True)

            logger.info(
                "generate_recipe: created %s recipe %r (%s) with %d additional categories",
                recipe.get_status_display().lower(), recipe.title, recipe.slug, len(additional_categories),
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
