"""
recipes/templatetags/recipe_schema.py

Usage in recipe_detail.html:
    {% load recipe_schema %}
    {% recipe_schema_json recipe %}

Generates <script type="application/ld+json"> with full Schema.org/Recipe markup.
Reads aggregateRating data from template context (pre-computed by the view).
"""

import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _minutes_to_iso8601(minutes) -> str | None:
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"PT{hours}H{mins}M"
    if hours:
        return f"PT{hours}H"
    return f"PT{mins}M"


def _safe_json(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False)
    return raw.replace("&", "\\u0026").replace("<", "\\u003C").replace(">", "\\u003E")


@register.simple_tag(takes_context=True)
def recipe_schema_json(context, recipe) -> str:
    request = context.get("request")

    # Image: hero first, fallback to first gallery image
    image_url = None
    if recipe.hero_image:
        try:
            raw = recipe.hero_image.url
            image_url = request.build_absolute_uri(raw) if request else raw
        except Exception:
            pass
    if not image_url:
        gallery_items = context.get("gallery_items") or []
        first_img = next((i for i in gallery_items if i.get("media_type") == "image"), None)
        if first_img and first_img.get("src"):
            image_url = request.build_absolute_uri(first_img["src"]) if request else first_img["src"]

    # Times
    prep_iso = _minutes_to_iso8601(recipe.prep_time_minutes)
    cook_iso = _minutes_to_iso8601(recipe.cook_time_minutes)
    total_iso = _minutes_to_iso8601(
        (recipe.prep_time_minutes or 0) + (recipe.cook_time_minutes or 0)
    )

    # Author
    if recipe.author:
        author = {"@type": "Person", "name": recipe.author.name}
        if hasattr(recipe.author, "get_absolute_url"):
            try:
                author["url"] = request.build_absolute_uri(recipe.author.get_absolute_url()) if request else recipe.author.get_absolute_url()
            except Exception:
                pass
    else:
        author = {"@type": "Organization", "name": "CulinEire"}

    # Method steps (already computed by view and passed in context)
    method_steps = context.get("method_steps") or []
    instructions = [
        {"@type": "HowToStep", "text": step["text"]}
        for step in method_steps if step.get("text")
    ]

    # Ingredients
    ingredients = [
        line.strip()
        for line in (recipe.ingredients or "").splitlines()
        if line.strip()
    ]

    schema: dict = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "description": recipe.short_description or f"A recipe for {recipe.title}.",
        "author": author,
        "datePublished": recipe.created_at.strftime("%Y-%m-%d"),
        "dateModified": recipe.updated_at.strftime("%Y-%m-%d"),
        "recipeCategory": recipe.get_category_display(),
        "url": request.build_absolute_uri() if request else "",
    }

    if image_url:
        schema["image"] = image_url
    if prep_iso:
        schema["prepTime"] = prep_iso
    if cook_iso:
        schema["cookTime"] = cook_iso
    if total_iso:
        schema["totalTime"] = total_iso
    if recipe.servings:
        schema["recipeYield"] = str(recipe.servings)
    if ingredients:
        schema["recipeIngredient"] = ingredients
    if instructions:
        schema["recipeInstructions"] = instructions

    # Cuisine & keywords
    schema["recipeCuisine"] = "Irish"
    category_label = recipe.get_category_display()
    if category_label:
        schema["keywords"] = category_label

    # Nutrition — calories from model field
    try:
        cal = int(recipe.calories) if recipe.calories else 0
    except (TypeError, ValueError):
        cal = 0
    if cal > 0:
        schema["nutrition"] = {
            "@type": "NutritionInformation",
            "calories": f"{cal} calories",
        }

    # AggregateRating — data pre-computed by the view
    ratings_count = context.get("ratings_count") or 0
    average_rating_value = context.get("average_rating_value")
    if ratings_count >= 1 and average_rating_value:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(float(average_rating_value), 1),
            "ratingCount": ratings_count,
            "bestRating": 5,
            "worstRating": 1,
        }

    # reviewCount from approved comments (supplements ratingCount)
    comments_count = context.get("comments_count") or 0
    if comments_count > 0 and "aggregateRating" in schema:
        schema["aggregateRating"]["reviewCount"] = comments_count

    return mark_safe(f'<script type="application/ld+json">{_safe_json(schema)}</script>')
