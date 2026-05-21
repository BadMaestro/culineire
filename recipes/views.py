import json
import re
from typing import cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView
# noinspection PyPackageRequirements
from django_ratelimit.decorators import ratelimit

from accounts.views import (
    can_grant_bearseeker_privileges as _can_grant_bearseeker_privileges,
    can_revoke_superuser_privileges as _can_revoke_superuser_privileges,
    is_moderator,
)
from articles.models import Article, ArticleImage
from collection.models import SavedRecipe
from config.turnstile import verify_turnstile
from monitoring.tracker import track_event
from .allergens import build_present_allergen_items
from .authoring import AuthorRequiredMixin, user_can_manage_author
from .forms import (
    RecipeAuthoringForm,
    RecipeAuthorProfileForm,
    RecipeCommentForm,
    RecipeRatingForm,
)
from .models import Recipe, RecipeAuthor, RecipeComment, RecipeImage, RecipeRating

POPULAR_CATEGORY_PRIORITY = [
    ("irish_culinary_heritage", "Irish Culinary Heritage"),
    ("modern_irish_cooking", "Modern Irish Cooking"),
    ("everyday_irish_cooking", "Everyday Irish Cooking"),
    ("breakfast_and_brunch", "Breakfast and Brunch"),
    ("lunch", "Lunch"),
    ("dinner", "Dinner"),
    ("grilling_and_barbecue", "Grilling and Barbecue"),
    ("soups_and_stews", "Soups"),
    ("salads", "Salads"),
    ("seasonal_and_festive_irish", "Seasonal and Festive"),
    ("healthy_eating", "Healthy Eating"),
    ("pasta_and_noodles", "Pasta and Noodles"),
]

RECIPE_MOOD_CHIPS = [
    ("meat_and_poultry", "Meat"),
    ("fish_and_seafood", "Fish"),
    ("salads", "Salads"),
    ("soups_and_stews", "Soups"),
    ("pasta_and_noodles", "Pasta"),
    ("breakfast_and_brunch", "Breakfast"),
    ("lunch", "Lunch"),
    ("dinner", "Dinner"),
    ("grilling_and_barbecue", "Grilling"),
    ("healthy_eating", "Healthy"),
    ("vegetables", "Veggie"),
    ("desserts", "Desserts"),
    ("drinks", "Drinks"),
    ("traditional_irish_dishes", "Irish Classics"),
    ("modern_irish_cooking", "Modern Irish"),
]

CATEGORY_IMAGE_MAP = {
    "irish_culinary_heritage": "images/categories/irish-culinary-heritage.png",
    "modern_irish_cooking": "images/categories/modern-irish-cooking.png",
    "everyday_irish_cooking": "images/categories/everyday-irish-cooking.png",
    "breakfast_and_brunch": "images/categories/breakfast-and-brunch.png",
    "lunch": "images/categories/lunch.png",
    "dinner": "images/categories/dinner.png",
    "grilling_and_barbecue": "images/categories/grilling-and-barbecue.png",
    "soups_and_stews": "images/categories/soups-and-stews.png",
    "salads": "images/categories/salads.png",
    "seasonal_and_festive_irish": "images/categories/seasonal-and-festive.png",
    "healthy_eating": "images/categories/healthy-eating.png",
    "pasta_and_noodles": "images/categories/pasta-and-noodles.png",
}


METHOD_STEP_PREFIX_RE = re.compile(r"^\d+\.\s*")
INGREDIENT_DETAIL_SPLIT_RE = re.compile("\\s*[-\u2013\u2014:]\\s*", re.UNICODE)
CONTEXT_SENTENCE_SPLIT_RE = re.compile("(?<=[.!?])\\s+(?=[\"\\u201c\\u2018]?[A-Z0-9])")




def _split_text_lines(value: str) -> list[str]:
    if not value:
        return []

    return [
        line.strip()
        for line in value.splitlines()
        if line.strip()
    ]


def _build_method_steps(method_text: str) -> list[dict]:
    raw_lines = _split_text_lines(method_text)

    steps = []
    for line in raw_lines:
        cleaned = line.strip()
        cleaned = METHOD_STEP_PREFIX_RE.sub("", cleaned)
        cleaned = cleaned.strip()

        if not cleaned or cleaned.isdigit():
            continue

        steps.append(
            {
                "number": len(steps) + 1,
                "text": cleaned,
            }
        )

    return steps


def _ensure_sentence_punctuation(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _build_ingredient_items(ingredients_text: str) -> list[dict]:
    items = []

    for raw_line in _split_text_lines(ingredients_text):
        parts = INGREDIENT_DETAIL_SPLIT_RE.split(raw_line, maxsplit=1)
        name = parts[0].strip()
        detail = parts[1].strip() if len(parts) > 1 else ""

        items.append(
            {
                "name": name,
                "detail": detail,
                "detail_display": _ensure_sentence_punctuation(detail) if detail else "",
            }
        )

    return items



def _build_context_paragraphs(context_text: str) -> list[str]:
    if not context_text:
        return []

    explicit_paragraphs = [
        re.sub(r"\s+", " ", chunk).strip()
        for chunk in re.split(r"\n\s*\n+", context_text)
        if chunk.strip()
    ]
    if len(explicit_paragraphs) > 1:
        return explicit_paragraphs

    normalized_text = re.sub(r"\s+", " ", context_text).strip()
    if not normalized_text:
        return []

    sentences = [
        sentence.strip()
        for sentence in CONTEXT_SENTENCE_SPLIT_RE.split(normalized_text)
        if sentence.strip()
    ]
    if len(sentences) <= 2:
        return [normalized_text]

    return [
        " ".join(sentences[index:index + 2])
        for index in range(0, len(sentences), 2)
    ]


def home(request):
    article_card_gallery_prefetch = Prefetch(
        "gallery_images",
        queryset=ArticleImage.objects.filter(is_active=True).order_by("sort_order", "id"),
        to_attr="active_card_gallery_images",
    )
    latest_recipes = (
        Recipe.objects.select_related("author")
        .filter(status=Recipe.Status.APPROVED)
        .order_by("-created_at")[:6]
    )

    latest_articles = (
        Article.objects.select_related("author", "related_recipe")
        .prefetch_related(article_card_gallery_prefetch)
        .filter(status=Article.Status.APPROVED)
        .order_by("-published")[:6]
    )

    context = {
        "latest_recipes": latest_recipes,
        "latest_articles": latest_articles,
    }
    return render(request, "home.html", context)


def recipe_list(request):
    author_slug = (request.GET.get("author") or "").strip()
    recipes = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
        .filter(status=Recipe.Status.APPROVED)
        .order_by("-created_at")
    )
    popular_recipe_candidates = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
        .annotate(
            average_rating_value=Avg("ratings__value"),
            ratings_total=Count("ratings"),
        )
        .filter(ratings_total__gt=0)
        .order_by("-average_rating_value", "-ratings_total", "-created_at")
    )
    selected_author = None
    if author_slug:
        selected_author = get_object_or_404(RecipeAuthor, slug=author_slug)
        recipes = recipes.filter(author=selected_author)
        popular_recipe_candidates = popular_recipe_candidates.filter(author=selected_author)

        if user_can_manage_author(request.user, selected_author) or is_moderator(request.user):
            recipes = (
                Recipe.objects.select_related("author")
                .prefetch_related("additional_category_links")
                .filter(author=selected_author)
                .order_by("-created_at")
            )

    popular_recipe_by_category = {}
    popular_recipe_counts = {}
    for recipe in popular_recipe_candidates:
        for category_value in recipe.get_all_category_values():
            popular_recipe_counts[category_value] = popular_recipe_counts.get(category_value, 0) + 1
            if category_value not in popular_recipe_by_category:
                popular_recipe_by_category[category_value] = recipe

    category_navigation = Recipe.get_category_navigation()
    category_navigation_by_value = {
        category["value"]: category
        for category in category_navigation
    }
    mood_categories = [
        {
            "label": chip_label,
            "url": category_navigation_by_value[category_value]["url"],
            "value": category_value,
        }
        for category_value, chip_label in RECIPE_MOOD_CHIPS
        if category_value in category_navigation_by_value
    ]
    ordered_popular_category_specs = sorted(
        enumerate(POPULAR_CATEGORY_PRIORITY),
        key=lambda item: (
            -popular_recipe_counts.get(item[1][0], 0),
            item[0],
        ),
    )
    popular_categories = []

    for _, (category_value, category_label) in ordered_popular_category_specs:
        category = category_navigation_by_value.get(category_value)
        if not category:
            continue

        representative_recipe = popular_recipe_by_category.get(category_value)
        static_image_path = CATEGORY_IMAGE_MAP.get(category_value, "")
        image_url = f"{static(static_image_path)}?v=20260429e" if static_image_path else ""
        image_alt = category_label

        if not image_url and representative_recipe and representative_recipe.hero_image:
            image_url = representative_recipe.hero_image.url
            image_alt = category_label

        popular_categories.append(
            {
                "label": category_label,
                "url": category["url"],
                "image_url": image_url,
                "image_alt": image_alt,
            }
        )

    recent_recipes = list(recipes[:6]) if selected_author else None
    default_recent_recipes = list(recipes[:6]) if not selected_author else None
    all_recipes_grid = list(recipes[:50]) if not selected_author else None

    all_articles = None
    recent_articles = None
    if selected_author:
        all_articles = (
            Article.objects.select_related("author")
            .filter(author=selected_author)
            .order_by("-published")
        )
        recent_articles = list(all_articles[:6])

    context = {
        "recipes": recipes,
        "recent_recipes": recent_recipes,
        "all_articles": all_articles,
        "recent_articles": recent_articles,
        "popular_categories": popular_categories if not selected_author else [],
        "mood_categories": mood_categories if not selected_author else [],
        "categories": category_navigation,
        "page_title": (
            f"{selected_author.name} Recipes | CulinEire"
            if selected_author
            else "Recipes | CulinEire"
        ),
        "meta_description": (
            f"Browse recipes by {selected_author.name} on CulinEire."
            if selected_author
            else (
                "Browse Irish-inspired recipes, vintage cookbook dishes, and modern home "
                "cooking ideas on CulinEire."
            )
        ),
        "page_heading": (
            "Recipe Collection"
            if selected_author
            else "Explore The Recipe Collection"
        ),
        "page_subtitle": (
            "Irish classics, seasonal dishes and home-kitchen favourites from the CulinEire Kitchen."
            if selected_author
            else (
                "Irish classics, treasured vintage recipes, and modern home-kitchen twists, "
                "bringing familiar flavours back to the table and opening Ireland's culinary "
                "heritage to food lovers."
            )
        ),
        "selected_category_label": "",
        "default_recent_recipes": default_recent_recipes,
        "all_recipes_grid": all_recipes_grid,
        "selected_author": selected_author,
        "can_manage_selected_author": user_can_manage_author(request.user, selected_author),
    }
    return render(request, "recipes/recipe_list.html", context)


def category_detail(request, category_slug):
    category_value = Recipe.get_category_value_from_slug(category_slug)
    if not category_value:
        raise Http404("Category not found.")

    category_label = Recipe.get_category_label(category_value)

    recipes = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
        .filter(status=Recipe.Status.APPROVED)
    )
    recipes = Recipe.filter_for_category(recipes, category_value).order_by("-created_at")

    context = {
        "recipes": recipes,
        "categories": Recipe.get_category_navigation(selected_value=category_value),
        "page_title": f"{category_label} | Recipes | CulinEire",
        "meta_description": (
            f"Browse {category_label.lower()} on CulinEire and discover recipes, ideas, "
            f"and kitchen inspiration."
        ),
        "page_heading": category_label,
        "page_subtitle": (
            f"Browse the full {category_label} collection — Irish classics and home kitchen favourites."
        ),
        "selected_category_label": category_label,
    }
    return render(request, "recipes/recipe_list.html", context)


def recipe_detail(request, slug):
    recipe = get_object_or_404(
        Recipe.objects.select_related("author").prefetch_related(
            "additional_category_links",
            Prefetch(
                "gallery_images",
                queryset=RecipeImage.objects.filter(is_active=True).order_by("sort_order", "id"),
            ),
            Prefetch(
                "comments",
                queryset=RecipeComment.objects.filter(is_approved=True, parent__isnull=True).select_related("author").prefetch_related(
                    Prefetch(
                        "replies",
                        queryset=RecipeComment.objects.filter(is_approved=True).select_related("author").order_by("created_at"),
                        to_attr="approved_replies",
                    )
                ).order_by("-created_at"),
                to_attr="approved_comments_prefetched",
            ),
        ),
        slug=slug,
    )

    if recipe.status != Recipe.Status.APPROVED:
        if not is_moderator(request.user):
            viewer_author = getattr(request.user, "recipe_author_profile", None)
            if not viewer_author or viewer_author != recipe.author:
                raise Http404

    gallery_items = []
    active_gallery_items = list(recipe.gallery_images.all())

    if active_gallery_items:
        for item in active_gallery_items:
            caption = item.caption or ""
            alt_text = item.alt_text or recipe.title

            if item.image:
                gallery_items.append(
                    {
                        "media_type": "image",
                        "src": item.image.url,
                        "alt": alt_text,
                        "caption": caption,
                        "poster": "",
                    }
                )
    elif recipe.hero_image:
        gallery_items.append(
            {
                "media_type": "image",
                "src": recipe.hero_image.url,
                "alt": recipe.title,
                "caption": "",
                "poster": "",
            }
        )

    track_event(
        request,
        "recipe_view",
        object_type="recipe",
        object_id=recipe.pk,
        object_title=recipe.title,
    )

    ingredient_items = _build_ingredient_items(recipe.ingredients)
    allergen_items = build_present_allergen_items(recipe.allergens)
    method_steps = _build_method_steps(recipe.method)
    irish_context_paragraphs = _build_context_paragraphs(recipe.irish_context)
    tips_paragraphs = _build_context_paragraphs(recipe.tips)
    author_commentary_paragraphs = _build_context_paragraphs(recipe.author_commentary)
    approved_comments = getattr(recipe, "approved_comments_prefetched", [])
    rating_summary = getattr(recipe, "ratings").aggregate(
        average=Avg("value"),
        count=Count("id"),
    )
    average_rating_value = float(rating_summary["average"] or 0)
    ratings_count = rating_summary["count"] or 0
    average_rating_percentage = min(max((average_rating_value / 5) * 100, 0), 100)

    session_key = f"recipe_rating_submitted_{recipe.pk}"
    _rating_session_val = request.session.get(session_key)
    has_rated = bool(_rating_session_val)
    user_rating_value = _rating_session_val if isinstance(_rating_session_val, int) else None

    commenter_profile = None
    if request.user.is_authenticated:
        try:
            commenter_profile = request.user.recipe_author_profile
        except RecipeAuthor.DoesNotExist:
            pass

    _schema: dict = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "description": recipe.short_description or f"A recipe for {recipe.title}.",
        "author": {"@type": "Person", "name": recipe.author.name} if recipe.author else {"@type": "Organization", "name": "CulinEire"},
        "datePublished": recipe.created_at.strftime("%Y-%m-%d"),
        "dateModified": recipe.updated_at.strftime("%Y-%m-%d"),
        "recipeCategory": recipe.get_category_display(),
        "url": request.build_absolute_uri(),
    }
    if recipe.hero_image:
        _schema["image"] = request.build_absolute_uri(recipe.hero_image.url)
    elif gallery_items:
        _first_img = next((item for item in gallery_items if item.get("media_type") == "image"), None)
        if _first_img:
            _schema["image"] = request.build_absolute_uri(_first_img["src"])
    if recipe.prep_time_minutes:
        _schema["prepTime"] = f"PT{recipe.prep_time_minutes}M"
    if recipe.cook_time_minutes:
        _schema["cookTime"] = f"PT{recipe.cook_time_minutes}M"
        _schema["totalTime"] = f"PT{(recipe.prep_time_minutes or 0) + recipe.cook_time_minutes}M"
    if recipe.servings:
        _schema["recipeYield"] = str(recipe.servings)
    if recipe.ingredients:
        _schema["recipeIngredient"] = [line.strip() for line in recipe.ingredients.split("\n") if line.strip()]
    if method_steps:
        _schema["recipeInstructions"] = [
            {"@type": "HowToStep", "text": step["text"]}
            for step in method_steps if step.get("text")
        ]
    if ratings_count > 0:
        _schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(average_rating_value, 1),
            "ratingCount": ratings_count,
            "bestRating": 5,
            "worstRating": 1,
        }

    context = {
        "recipe": recipe,
        "gallery_items": gallery_items,
        "ingredient_items": ingredient_items,
        "allergen_items": allergen_items,
        "method_steps": method_steps,
        "irish_context_paragraphs": irish_context_paragraphs,
        "tips_paragraphs": tips_paragraphs,
        "author_commentary_paragraphs": author_commentary_paragraphs,
        "approved_comments": approved_comments,
        "comments_count": len(approved_comments),
        "rating_form": RecipeRatingForm(),
        "comment_form": RecipeCommentForm(),
        "average_rating_value": average_rating_value,
        "ratings_count": ratings_count,
        "average_rating_percentage": average_rating_percentage,
        "can_manage_recipe": is_moderator(request.user) or user_can_manage_author(request.user, recipe.author),
        "is_greenbear": request.user.is_authenticated and hasattr(request.user, "recipe_author_profile") and request.user.recipe_author_profile.slug == settings.OWNER_SLUG,
        "can_moderate_bar": is_moderator(request.user) and recipe.status != Recipe.Status.APPROVED,
        "has_rated": has_rated,
        "user_rating_value": user_rating_value,
        "commenter_profile": commenter_profile,
        "recipe_json_ld": mark_safe(json.dumps(_schema, ensure_ascii=False)),
        "is_saved": request.user.is_authenticated and SavedRecipe.objects.filter(user=request.user, recipe=recipe).exists(),
        "collection_add_url": reverse("collection:add_recipe", kwargs={"slug": recipe.slug}),
        "collection_remove_url": reverse("collection:remove_recipe", kwargs={"slug": recipe.slug}),
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }
    return render(request, "recipes/recipe_detail.html", context)


@require_POST
@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def submit_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    form = RecipeRatingForm(request.POST)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    session_key = f"recipe_rating_submitted_{recipe.pk}"

    if getattr(request, "limited", False):
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Too many ratings. Please try again later."})
        messages.error(request, "You have submitted too many ratings. Please try again later.")
        return redirect(recipe.get_absolute_url())

    if request.session.get(session_key):
        if is_ajax:
            return JsonResponse({"ok": False, "error": "You have already rated this recipe."})
        messages.warning(request, "You have already rated this recipe from this browser session.")
        return redirect(recipe.get_absolute_url())

    if not form.is_valid():
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Please select a rating between 1 and 5."})
        messages.error(request, "Please submit a valid rating between 1 and 5.")
        return redirect(recipe.get_absolute_url())

    RecipeRating.objects.create(
        recipe=recipe,
        value=form.cleaned_data["value"],
        user=request.user if request.user.is_authenticated else None,
    )

    request.session[session_key] = form.cleaned_data["value"]
    request.session.modified = True

    if is_ajax:
        return JsonResponse({"ok": True})
    messages.success(request, "Thank you. Your rating has been saved.")
    return redirect(recipe.get_absolute_url())


@require_POST
@login_required
def reset_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    session_key = f"recipe_rating_submitted_{recipe.pk}"
    request.session.pop(session_key, None)
    request.session.modified = True
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_ajax:
        return JsonResponse({"ok": True})
    return redirect(recipe.get_absolute_url())


@require_POST
@login_required
def reset_all_recipe_ratings(request, slug):
    if not hasattr(request.user, "recipe_author_profile"):
        return JsonResponse({"ok": False}, status=403)
    if request.user.recipe_author_profile.slug != settings.OWNER_SLUG:
        return JsonResponse({"ok": False}, status=403)
    recipe = get_object_or_404(Recipe, slug=slug)
    recipe.ratings.all().delete()
    session_key = f"recipe_rating_submitted_{recipe.pk}"
    request.session.pop(session_key, None)
    request.session.modified = True
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_ajax:
        return JsonResponse({"ok": True})
    messages.success(request, "All ratings have been reset.")
    return redirect(recipe.get_absolute_url())


def recipe_ratings_api(request, slug):
    """Return rating breakdown + recent named raters as JSON."""
    recipe = get_object_or_404(Recipe, slug=slug, status="approved")
    ratings_qs = recipe.ratings.select_related("user__recipe_author_profile").order_by("-created_at")

    total = ratings_qs.count()
    agg = ratings_qs.aggregate(avg=Avg("value"))
    average = round(agg["avg"] or 0, 1)

    breakdown = {str(v): 0 for v in range(5, 0, -1)}
    for r in ratings_qs.values("value").annotate(cnt=Count("value")):
        breakdown[str(r["value"])] = r["cnt"]

    recent = []
    for rating in ratings_qs[:20]:
        entry = {"value": rating.value, "date": rating.created_at.strftime("%-d %b %Y")}
        author = None
        if rating.user:
            try:
                author = rating.user.recipe_author_profile
            except Exception:
                pass
        if author:
            entry["author_name"] = author.name
            entry["author_slug"] = author.slug
            entry["author_avatar"] = author.display_avatar_url
        recent.append(entry)

    return JsonResponse({"total": total, "average": average, "breakdown": breakdown, "recent": recent})


@require_POST
@login_required
@ratelimit(key="ip", rate="5/h", method="POST", block=False)
def submit_recipe_comment(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)

    try:
        display_name = request.user.recipe_author_profile.name
    except RecipeAuthor.DoesNotExist:
        display_name = request.user.get_full_name() or request.user.username

    post_data = request.POST.copy()
    post_data["name"] = display_name
    form = RecipeCommentForm(post_data)

    last_comment_payload_key = f"recipe_comment_payload_{recipe.pk}"

    if getattr(request, "limited", False):
        messages.error(request, "You have submitted too many comments. Please try again later.")
        return redirect(f"{recipe.get_absolute_url()}#comments")

    token = request.POST.get("cf-turnstile-response", "")
    if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
        messages.error(request, "Security check failed. Please try again.")
        return redirect(f"{recipe.get_absolute_url()}#comments")

    if not form.is_valid():
        messages.error(request, "Please complete the comment form correctly.")
        return redirect(f"{recipe.get_absolute_url()}#comments")

    name = form.cleaned_data["name"]
    content = form.cleaned_data["content"]

    normalized_payload = f"{name.strip().lower()}|{content.strip().lower()}"
    previous_payload = request.session.get(last_comment_payload_key)

    if previous_payload == normalized_payload:
        messages.warning(request, "This comment looks like a duplicate and was not submitted again.")
        return redirect(f"{recipe.get_absolute_url()}#comments")

    author_fk = None
    try:
        author_fk = request.user.recipe_author_profile
    except RecipeAuthor.DoesNotExist:
        pass

    RecipeComment.objects.create(
        recipe=recipe,
        author=author_fk,
        name=name,
        content=content,
        is_approved=True,
    )

    # Optionally save rating submitted alongside the comment
    rating_session_key = f"recipe_rating_submitted_{recipe.pk}"
    rating_value = request.POST.get("rating_value", "").strip()
    if rating_value and not request.session.get(rating_session_key):
        rating_form = RecipeRatingForm({"value": rating_value})
        if rating_form.is_valid():
            RecipeRating.objects.create(recipe=recipe, value=rating_form.cleaned_data["value"])
            request.session[rating_session_key] = rating_form.cleaned_data["value"]
            request.session.modified = True

    request.session[last_comment_payload_key] = normalized_payload
    request.session.modified = True

    messages.success(request, "Your comment has been posted.")
    return redirect(f"{recipe.get_absolute_url()}#comments")


@require_POST
@login_required
def delete_recipe_comment(request, comment_id):
    comment = get_object_or_404(RecipeComment, pk=comment_id)
    recipe = comment.recipe
    if not (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    comment.delete()
    return redirect(f"{recipe.get_absolute_url()}#comments")


@require_POST
@login_required
def delete_all_recipe_comments(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if not is_moderator(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    recipe.comments.all().delete()
    return redirect(f"{recipe.get_absolute_url()}#comments")


@require_POST
@login_required
def add_comment_reply(request, comment_id):
    target = get_object_or_404(RecipeComment, pk=comment_id, is_approved=True)
    root = target if target.parent_id is None else target.parent
    recipe = root.recipe

    try:
        author = request.user.recipe_author_profile
        display_name = author.name
    except RecipeAuthor.DoesNotExist:
        messages.error(request, "Only registered authors can reply to comments.")
        return redirect(f"{recipe.get_absolute_url()}#comment-{root.pk}")

    token = request.POST.get("cf-turnstile-response", "")
    if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
        messages.error(request, "Security check failed. Please try again.")
        return redirect(f"{recipe.get_absolute_url()}#comment-{root.pk}")

    content = request.POST.get("content", "").strip()
    if not content:
        return redirect(f"{recipe.get_absolute_url()}#comment-{root.pk}")

    reply = RecipeComment.objects.create(
        recipe=recipe,
        parent=root,
        author=author,
        name=display_name,
        content=content,
        is_approved=True,
    )
    return redirect(f"{recipe.get_absolute_url()}#comment-{reply.pk}")


def author_detail(request, slug):
    author = get_object_or_404(RecipeAuthor, slug=slug)
    can_manage = user_can_manage_author(request.user, author)
    moderator = is_moderator(request.user)

    recipes_for_count = Recipe.objects.filter(author=author)
    articles_for_count = Article.objects.filter(author=author)
    if not (can_manage or moderator):
        recipes_for_count = recipes_for_count.filter(status=Recipe.Status.APPROVED)
        articles_for_count = articles_for_count.filter(status=Article.Status.APPROVED)

    recipe_count = recipes_for_count.count()
    article_count = articles_for_count.count()

    pending_recipes = []
    pending_articles = []
    if can_manage or moderator:
        pending_recipes = list(
            Recipe.objects.filter(author=author)
            .exclude(status=Recipe.Status.APPROVED)
            .order_by("-created_at")
        )
        pending_articles = list(
            Article.objects.filter(author=author)
            .exclude(status=Article.Status.APPROVED)
            .order_by("-published")
        )

    context = {
        "author": author,
        "recipe_count": recipe_count,
        "article_count": article_count,
        "is_god_author": author.slug == settings.OWNER_SLUG,
        "can_manage_author_profile": can_manage,
        "is_moderator_viewer": moderator,
        "pending_recipes": pending_recipes,
        "pending_articles": pending_articles,
    }
    return render(request, "recipes/author_detail.html", context)


def _is_protected_author_action(author, user):
    linked_user = getattr(author, "user", None)
    return (
        author.slug == settings.OWNER_SLUG
        or author.user_id == getattr(user, "pk", None)
        or bool(linked_user and linked_user.is_superuser)
    )


def _delete_author_profile_and_account(author):
    user_id = author.user_id
    with transaction.atomic():
        Article.objects.filter(author=author).delete()
        Recipe.objects.filter(author=author).delete()
        author.delete()
        if user_id:
            get_user_model().objects.filter(pk=user_id).delete()


class RecipeCreateView(AuthorRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeAuthoringForm
    template_name = "authoring/recipe_form.html"

    def post(self, request, *args, **kwargs):
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            messages.error(request, "Security check failed. Please try again.")
            return redirect("recipes:recipe_create")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        recipe = form.save(commit=False, confirmed_by=self.request.user)
        recipe.author = self.author
        if is_moderator(self.request.user):
            recipe.status = Recipe.Status.APPROVED
        recipe.save()
        getattr(form, "save_additional_categories")(recipe)

        for step in range(1, 21):
            img_file = self.request.FILES.get(f"gallery_step_{step}")
            if img_file:
                RecipeImage.objects.create(recipe=recipe, image=img_file, sort_order=step)

        self.object = recipe
        messages.success(self.request, "Recipe Created Successfully.")
        return redirect(recipe.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        context["cancel_url"] = reverse_lazy("recipes:recipe_list")
        return context


class RecipeUpdateView(AuthorRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeAuthoringForm
    template_name = "authoring/recipe_form.html"
    context_object_name = "recipe"

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Recipe.objects.all()
        return Recipe.objects.filter(author=self.author)

    def form_valid(self, form):
        was_approved = self.object.status == Recipe.Status.APPROVED
        recipe = form.save(commit=False, confirmed_by=self.request.user)
        if not is_moderator(self.request.user):
            recipe.status = Recipe.Status.PENDING
        recipe.save()
        getattr(form, "save_additional_categories")(recipe)

        for step in range(1, 21):
            img_file = self.request.FILES.get(f"gallery_step_{step}")
            if img_file:
                existing = recipe.gallery_images.filter(sort_order=step).first()
                if existing:
                    existing.image.delete(save=False)
                    existing.image = img_file
                    existing.save()
                else:
                    RecipeImage.objects.create(recipe=recipe, image=img_file, sort_order=step)

        self.object = recipe
        if was_approved and not is_moderator(self.request.user):
            messages.success(self.request, "Recipe updated and sent back to review before it goes live again.")
        else:
            messages.success(self.request, "Recipe Updated Successfully.")
        if is_moderator(self.request.user):
            return redirect(reverse_lazy("recipes:moderation_panel"))
        return redirect(recipe.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Recipe"
        context["form_intro"] = (
            "Refine your recipe, update categories and keep the CulinEire collection current."
        )
        context["submit_label"] = "Save Changes"
        context["cancel_url"] = self.object.get_absolute_url() if self.object else reverse_lazy("recipes:recipe_list")
        context["existing_gallery_images"] = list(
            self.object.gallery_images.filter(is_active=True).order_by("sort_order", "id")
        ) if self.object else []
        context["will_return_to_review"] = (
            bool(self.object)
            and self.object.status == Recipe.Status.APPROVED
            and not is_moderator(self.request.user)
        )
        return context


class RecipeDeleteView(AuthorRequiredMixin, DeleteView):
    model = Recipe
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Recipe.objects.all()
        return Recipe.objects.filter(author=self.author)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, "Recipe Deleted Successfully.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["delete_title"] = "Delete Recipe"
        context["delete_intro"] = (
            f'You are about to delete "{self.object.title}". This action cannot be undone.'
        )
        context["delete_label"] = "Delete Recipe"
        context["cancel_url"] = self.object.get_absolute_url()
        return context


class RecipeAuthorUpdateView(AuthorRequiredMixin, UpdateView):
    model = RecipeAuthor
    form_class = RecipeAuthorProfileForm
    template_name = "authoring/profile_form.html"

    def get_object(self, queryset=None):
        return self.author

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Profile Updated Successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.object
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Profile"
        context["form_intro"] = (
            "Update your public author profile, bio and image for the CulinEire site."
        )
        context["submit_label"] = "Save Profile"
        context["show_profile_privacy_notice"] = True
        return context


class RecipeAuthorDeleteView(AuthorRequiredMixin, DeleteView):
    model = RecipeAuthor
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("home")

    def get_object(self, queryset=None):
        return self.author

    def post(self, request, *args, **kwargs):
        self.object = cast(RecipeAuthor, self.get_object())

        if self.object.slug == settings.OWNER_SLUG:
            messages.error(request, "This account cannot be deleted.")
            return redirect(self.object.get_absolute_url())

        _delete_author_profile_and_account(self.object)
        logout(request)

        messages.success(request, "Your account and all associated content have been permanently deleted.")
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        related_recipe_count = Recipe.objects.filter(author=self.author).count()
        related_article_count = Article.objects.filter(author=self.author).count()
        context["author"] = self.author
        context["delete_title"] = "Delete Profile"
        context["delete_intro"] = (
            "This will permanently delete your account, your author profile, "
            "all your recipes and all your articles. This action cannot be undone."
        )
        context["delete_label"] = "Delete My Account"
        context["cancel_url"] = self.author.get_absolute_url()
        context["delete_warnings"] = [
            f"{related_recipe_count} recipe(s) will be permanently deleted." if related_recipe_count else "",
            f"{related_article_count} article(s) will be permanently deleted." if related_article_count else "",
            "Your user account and login credentials will be removed.",
            "You will be logged out immediately.",
        ]
        return context


class ModeratorAuthorUpdateView(UpdateView):
    model = RecipeAuthor
    form_class = RecipeAuthorProfileForm
    template_name = "authoring/profile_form.html"
    slug_url_kwarg = "slug"

    def dispatch(self, request, *args, **kwargs):
        if not is_moderator(request.user):
            raise Http404
        author = self.get_object()
        if _is_protected_author_action(author, request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return RecipeAuthor.objects.select_related("user")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Author profile "{self.object.name}" updated.')
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.object
        context["form_mode"] = "moderation-edit"
        context["form_heading"] = "Edit Author Profile"
        context["form_intro"] = "Update this author's public profile, bio and avatar."
        context["submit_label"] = "Save Author Profile"
        context["show_profile_privacy_notice"] = False
        return context


class ModeratorAuthorDeleteView(DeleteView):
    model = RecipeAuthor
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("recipes:moderation_panel")

    def dispatch(self, request, *args, **kwargs):
        if not is_moderator(request.user):
            raise Http404
        author = self.get_object()
        if _is_protected_author_action(author, request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return RecipeAuthor.objects.select_related("user")

    def post(self, request, *args, **kwargs):
        self.object = cast(RecipeAuthor, self.get_object())
        if _is_protected_author_action(self.object, request.user):
            raise Http404

        author_name = self.object.name
        _delete_author_profile_and_account(self.object)

        messages.success(request, f'Author profile "{author_name}" and associated content have been deleted.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        related_recipe_count = Recipe.objects.filter(author=self.object).count()
        related_article_count = Article.objects.filter(author=self.object).count()
        context["author"] = self.object
        context["delete_title"] = "Delete Author Profile"
        context["delete_intro"] = (
            "This will permanently delete this author account, author profile, "
            "all recipes and all articles connected to it. This action cannot be undone."
        )
        context["delete_label"] = "Delete Author Profile"
        context["cancel_url"] = self.object.get_absolute_url()
        context["delete_warnings"] = [
            f"{related_recipe_count} recipe(s) will be permanently deleted." if related_recipe_count else "",
            f"{related_article_count} article(s) will be permanently deleted." if related_article_count else "",
            "The linked user account and login credentials will be removed.",
        ]
        return context


# ── Moderation ────────────────────────────────────────────────────────────────


def moderation_panel(request):
    if not is_moderator(request.user):
        raise Http404

    author_query = request.GET.get("author_q", "").strip()

    pending_recipes = (
        Recipe.objects.select_related("author", "author__user")
        .filter(status=Recipe.Status.PENDING)
        .order_by("-created_at")
    )
    rejected_recipes = (
        Recipe.objects.select_related("author", "author__user")
        .filter(status=Recipe.Status.REJECTED)
        .order_by("-created_at")
    )
    pending_articles = (
        Article.objects.select_related("author", "author__user")
        .filter(status=Article.Status.PENDING)
        .order_by("-published")
    )
    rejected_articles = (
        Article.objects.select_related("author", "author__user")
        .filter(status=Article.Status.REJECTED)
        .order_by("-published")
    )
    protected_super_user_filter = Q(user__is_superuser=True) | Q(slug=settings.OWNER_SLUG)

    registered_authors = (
        RecipeAuthor.objects.select_related("user")
        .filter(user__isnull=False, has_bearseeker_privileges=False)
        .exclude(protected_super_user_filter)
        .order_by("name", "user__username")
    )
    if author_query:
        registered_authors = registered_authors.filter(
            Q(name__icontains=author_query)
            | Q(user__username__icontains=author_query)
        )

    bearseeker_authors = (
        RecipeAuthor.objects.select_related("user")
        .filter(has_bearseeker_privileges=True, user__isnull=False)
        .exclude(protected_super_user_filter)
        .order_by("name")
    )
    bearseeker_super_users = (
        RecipeAuthor.objects.select_related("user")
        .filter(user__isnull=False)
        .filter(protected_super_user_filter)
        .annotate(
            owner_priority=Case(
                When(slug=settings.OWNER_SLUG, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("owner_priority", "name", "user__username")
    )

    return render(request, "moderation/panel.html", {
        "pending_recipes": pending_recipes,
        "rejected_recipes": rejected_recipes,
        "pending_articles": pending_articles,
        "rejected_articles": rejected_articles,
        "registered_authors": registered_authors,
        "author_query": author_query,
        "can_grant_bearseeker_privileges": _can_grant_bearseeker_privileges(request.user),
        "can_revoke_superuser_privileges": _can_revoke_superuser_privileges(request.user),
        "bearseeker_super_users": bearseeker_super_users,
        "bearseeker_authors": bearseeker_authors,
    })


@require_POST
def moderate_recipe(request, slug):
    if not is_moderator(request.user):
        raise Http404
    recipe = get_object_or_404(Recipe, slug=slug)
    action = request.POST.get("action")

    if action == "approve":
        recipe.status = Recipe.Status.APPROVED
        recipe.save(update_fields=["status"])
        messages.success(request, f'"{recipe.title}" approved and is now live.')
    elif action == "reject":
        recipe.status = Recipe.Status.REJECTED
        recipe.save(update_fields=["status"])
        messages.warning(request, f'"{recipe.title}" rejected.')
    elif action == "delete":
        title = recipe.title
        recipe.delete()
        messages.success(request, f'"{title}" permanently deleted.')
    elif action == "block":
        user = recipe.author.user if recipe.author else None
        if user:
            user.is_active = False
            user.save(update_fields=["is_active"])
            messages.warning(request, f'User "{user.username}" has been blocked.')
        else:
            messages.error(request, "No linked user account found.")

    if action not in ("delete", "block") and recipe.pk:
        return redirect(recipe.get_absolute_url())
    return redirect("recipes:moderation_panel")


