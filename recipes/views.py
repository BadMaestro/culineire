import json
import logging
import re
from datetime import timedelta
from pathlib import Path
from typing import cast

logger = logging.getLogger("recipes")

from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg, Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
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
from monitoring.tracker import get_client_ip, hash_ip, track_event
from .allergens import build_present_allergen_items
from .authoring import AuthorRequiredMixin, user_can_manage_author
from .forms import (
    RecipeAuthoringForm,
    RecipeAuthorProfileForm,
    RecipeCommentForm,
    RecipeRatingForm,
)
from .models import Recipe, RecipeAuthor, RecipeComment, RecipeGenerationTask, RecipeImage, RecipeRating
from .validators import validate_image_upload
from config.email_utils import build_absolute_url, send_template_mail

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
    ("bread_and_baking", "Baking"),
    ("soups_and_stews", "Soups and Stews"),
    ("fish_and_seafood", "Seafood"),
    ("vegetables", "Vegetables"),
    ("meat_and_poultry", "Meat"),
    ("desserts", "Desserts"),
    ("drinks", "Drinks"),
]


def _build_automation_roadmap_progress():
    base_dir = Path(settings.BASE_DIR)
    approved_recipe_count = Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False).count()
    approved_article_count = Article.objects.filter(status=Article.Status.APPROVED, is_deleted=False).count()
    draft_pipeline_count = Recipe.objects.filter(status__in=[Recipe.Status.DRAFT, Recipe.Status.PENDING], is_deleted=False).count()
    telegram_configured = bool(getattr(settings, "TELEGRAM_BOT_TOKEN", "") and getattr(settings, "TELEGRAM_CHANNEL_ID", ""))
    anthropic_configured = bool(getattr(settings, "ANTHROPIC_API_KEY", ""))

    phases = [
        {
            "title": "Month 1 - Foundation",
            "items": [
                {
                    "label": "SEO foundation",
                    "detail": "Recipe/article schema, breadcrumbs, robots.txt and sitemap.xml are implemented.",
                    "status": "done",
                },
                {
                    "label": "Internal recipe linking",
                    "detail": "Recipe detail pages surface related approved recipes by shared category.",
                    "status": "done",
                },
                {
                    "label": "AI recipe draft command",
                    "detail": "generate_recipe.py exists and saves AI output only as draft/pending.",
                    "status": "done" if (base_dir / "recipes" / "management" / "commands" / "generate_recipe.py").exists() else "pending",
                },
                {
                    "label": "Project rules and prompt library",
                    "detail": "CLAUDE.md and content prompt templates are available for external tooling.",
                    "status": "done" if (base_dir / "CLAUDE.md").exists() and (base_dir / "content_prompts" / "README.md").exists() else "pending",
                },
                {
                    "label": "Telegram publish pipeline",
                    "detail": "Signal and duplicate-prevention log are in place; credentials decide live posting.",
                    "status": "done",
                },
                {
                    "label": "Telegram credentials",
                    "detail": "TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be set in production env.",
                    "status": "done" if telegram_configured else "pending",
                },
                {
                    "label": "Anthropic credentials",
                    "detail": "ANTHROPIC_API_KEY is required before generating real recipe drafts.",
                    "status": "done" if anthropic_configured else "pending",
                },
                {
                    "label": "Recipe publishing target",
                    "detail": f"{approved_recipe_count}/20 approved recipes published.",
                    "status": "done" if approved_recipe_count >= 20 else "active" if approved_recipe_count else "pending",
                },
                {
                    "label": "Article publishing target",
                    "detail": f"{approved_article_count}/8 approved articles published.",
                    "status": "done" if approved_article_count >= 8 else "active" if approved_article_count else "pending",
                },
                {
                    "label": "Draft queue",
                    "detail": f"{draft_pipeline_count} recipe draft/pending item(s) currently in the pipeline.",
                    "status": "active" if draft_pipeline_count else "pending",
                },
                {
                    "label": "Search Console and Pinterest",
                    "detail": "Submit sitemap, verify Pinterest Business, then enable Rich Pins manually.",
                    "status": "manual",
                },
                {
                    "label": "Core Web Vitals check",
                    "detail": "Run PageSpeed/CrUX after deployment before adding ad scripts.",
                    "status": "manual",
                },
            ],
        },
        {
            "title": "Month 2 - Content Engine",
            "items": [
                {"label": "Batch recipe generation workflow", "detail": "Use txt dish lists, draft-only generation, and moderator approval.", "status": "pending"},
                {"label": "Article generation workflow", "detail": "Create a draft-only article command/pipeline with attribution checks.", "status": "pending"},
                {"label": "Editorial calendar", "detail": "Maintain at least 30 planned topics across recipes, articles and social posts.", "status": "pending"},
            ],
        },
        {
            "title": "Month 3 - Social Distribution",
            "items": [
                {"label": "Telegram live autoposting", "detail": "Publish approved recipes to Telegram after production credentials are set.", "status": "pending"},
                {"label": "Instagram/Facebook queue", "detail": "Choose Buffer or Meta Graph API and keep human approval before posting.", "status": "manual"},
                {"label": "Reddit workflow", "detail": "Use manual approval only; avoid automated spam-like submissions.", "status": "manual"},
            ],
        },
        {
            "title": "Month 4 - Media Automation",
            "items": [
                {"label": "Image workflow", "detail": "Define rights-safe image generation/upload/alt-text review.", "status": "pending"},
                {"label": "Short video queue", "detail": "Prepare TikTok, Reels and YouTube Shorts captions/storyboards.", "status": "pending"},
                {"label": "WhatsApp approach", "detail": "Decide whether WhatsApp Business API is worth the setup cost.", "status": "manual"},
            ],
        },
        {
            "title": "Month 5 - Analytics and Feedback",
            "items": [
                {"label": "Traffic feedback loop", "detail": "Use site analytics to choose next recipes/articles/social posts.", "status": "pending"},
                {"label": "Social performance review", "detail": "Track channel-level wins and feed them back into prompts.", "status": "pending"},
                {"label": "Monetisation decision", "detail": "Revisit Ezoic/ads/affiliate links after traffic and Core Web Vitals data.", "status": "manual"},
            ],
        },
        {
            "title": "Month 6 - Agent System",
            "items": [
                {"label": "Content agent", "detail": "Suggest, draft and queue recipes/articles without auto-publishing.", "status": "pending"},
                {"label": "SEO/social agents", "detail": "Generate summaries, captions and distribution recommendations.", "status": "pending"},
                {"label": "Weekly handoff report", "detail": "Produce copyable status for Codex and Claude Code every week.", "status": "pending"},
            ],
        },
    ]
    items = [item for phase in phases for item in phase["items"]]
    done_count = sum(1 for item in items if item["status"] == "done")
    active_items = [item for item in items if item["status"] != "done"]
    completed_items = [item for item in items if item["status"] == "done"]

    text_lines = [
        "CulinEire automation roadmap handoff",
        f"Progress: {done_count}/{len(items)} auto-checked items complete ({round((done_count / len(items)) * 100) if items else 0}%).",
        "Rules for Claude Code:",
        "- Do not overwrite existing schema, sitemap, signals, moderation, Telegram or recipe generation work.",
        "- Use real current field names from CLAUDE.md before changing models or commands.",
        "- AI content must stay draft/pending until a human approves it.",
        "",
        "Open / in-progress / manual items:",
    ]
    for phase in phases:
        open_items = [item for item in phase["items"] if item["status"] != "done"]
        if open_items:
            text_lines.append(f"{phase['title']}:")
            for item in open_items:
                text_lines.append(f"- [{item['status']}] {item['label']} - {item['detail']}")
    text_lines.append("")
    text_lines.append("Completed items:")
    for item in completed_items:
        text_lines.append(f"- [done] {item['label']} - {item['detail']}")

    return {
        "phases": phases,
        "items": items,
        "active_items": active_items,
        "completed_items": completed_items,
        "done_count": done_count,
        "total_count": len(items),
        "percent": round((done_count / len(items)) * 100) if items else 0,
        "copy_text": "\n".join(text_lines),
    }

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
INGREDIENT_DETAIL_SPLIT_RE = re.compile(r"\s*:\s*|\s+[-\u2013\u2014]\s+", re.UNICODE)
CONTEXT_SENTENCE_SPLIT_RE = re.compile("(?<=[.!?])\\s+(?=[\"\\u201c\\u2018]?[A-Z0-9])")


def _split_text_lines(value: str) -> list[str]:
    if not value:
        return []

    return [
        line.strip()
        for line in value.splitlines()
        if line.strip()
    ]


def _image_alt_text(title, alt_text="", caption=""):
    return alt_text.strip() or caption.strip() or f"{title} image"


def _gallery_step_alt(post_data, step):
    return (post_data.get(f"gallery_step_{step}_alt") or "").strip()


def _validate_recipe_gallery_uploads(form, files):
    """Validate all gallery_step_* uploads against the image validator.

    Mirrors articles._validate_gallery_uploads. Returns True if valid,
    adds form errors and returns False otherwise.
    """
    from django.core.exceptions import ValidationError as DjValidationError
    is_valid = True
    uploaded = [f for key, f in files.items() if key.startswith("gallery_step_")]
    if (
        uploaded
        and form.cleaned_data.get("image_rights_status") == Recipe.ImageRightsStatus.NOT_APPLICABLE
    ):
        form.add_error(
            "image_rights_status",
            "Choose the correct image rights status when gallery images are attached.",
        )
        is_valid = False
    for uploaded_file in uploaded:
        try:
            validate_image_upload(uploaded_file)
        except DjValidationError as exc:
            for message in exc.messages:
                form.add_error(None, f"Gallery image {uploaded_file.name}: {message}")
            is_valid = False
    return is_valid


def _update_recipe_gallery_order(recipe, post_data):
    if not hasattr(post_data, "getlist"):
        return

    ordered_ids = []
    for raw_id in post_data.getlist("recipe_gallery_image_order"):
        try:
            ordered_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not ordered_ids:
        return

    images_by_id = {
        image.pk: image
        for image in recipe.gallery_images.filter(is_active=True, pk__in=ordered_ids)
    }
    for position, image_id in enumerate(ordered_ids, start=1):
        image = images_by_id.get(image_id)
        if not image or image.sort_order == position:
            continue
        image.sort_order = position
        image.save(update_fields=["sort_order"])


def _gallery_step_rows(recipe=None):
    existing = {}
    if recipe:
        existing = {
            image.sort_order: image
            for image in recipe.gallery_images.filter(is_active=True).order_by("sort_order", "id")
        }
    max_step = max(3, *(existing.keys() or [0]))
    return [
        {"step": step, "image": existing.get(step)}
        for step in range(1, min(max_step, 20) + 1)
    ]


def _authoring_action(request):
    return request.POST.get("action") if request.POST.get("action") in {"save_draft", "submit_review", "approve_publish"} else "submit_review"


def _soft_delete_recipe(recipe, user):
    """Mark a recipe as deleted without removing it from the database."""
    recipe.is_deleted = True
    recipe.deleted_at = timezone.now()
    recipe.deleted_by = user
    recipe.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


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
        name = parts[0].strip().rstrip(".")
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
        .filter(status=Recipe.Status.APPROVED, is_deleted=False)
        .order_by("-created_at")[:6]
    )

    latest_articles = (
        Article.objects.select_related("author", "related_recipe")
        .prefetch_related(article_card_gallery_prefetch)
        .filter(status=Article.Status.APPROVED, is_deleted=False)
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
        .filter(status=Recipe.Status.APPROVED, is_deleted=False)
        .order_by("-created_at")
    )
    popular_recipe_candidates = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
        .annotate(
            average_rating_value=Avg("ratings__value"),
            ratings_total=Count("ratings"),
        )
        .filter(ratings_total__gt=0, is_deleted=False)
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
                .filter(author=selected_author, is_deleted=False)
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
            .filter(author=selected_author, is_deleted=False)
            .order_by("-published")
        )
        if not (user_can_manage_author(request.user, selected_author) or is_moderator(request.user)):
            all_articles = all_articles.filter(status=Article.Status.APPROVED)
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
        .filter(status=Recipe.Status.APPROVED, is_deleted=False)
    )
    recipes = Recipe.filter_for_category(recipes, category_value).order_by("-created_at")

    mood_chip_values = {value for value, _ in RECIPE_MOOD_CHIPS}
    category_nav = Recipe.get_category_navigation(selected_value=category_value)
    category_nav_by_value = {c["value"]: c for c in category_nav}
    mood_categories = [
        {
            "label": chip_label,
            "url": category_nav_by_value[value]["url"],
            "value": value,
            "is_active": value == category_value,
        }
        for value, chip_label in RECIPE_MOOD_CHIPS
        if value in category_nav_by_value
    ] if category_value in mood_chip_values else []

    context = {
        "recipes": recipes,
        "categories": category_nav,
        "mood_categories": mood_categories,
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

    if recipe.is_deleted:
        raise Http404

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
            alt_text = _image_alt_text(recipe.title, item.alt_text, caption)

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
                "alt": _image_alt_text(recipe.title, recipe.hero_image_alt_text),
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

    # For authenticated users, check DB first (session may be lost)
    _db_rating = None
    if request.user.is_authenticated:
        _db_rating = recipe.ratings.filter(user=request.user).first()

    if _db_rating:
        has_rated = True
        user_rating_value = _db_rating.value
    elif request.user.is_authenticated and _rating_session_val:
        # Only trust session for authenticated users — anonymous users can no longer rate
        has_rated = True
        user_rating_value = _rating_session_val if isinstance(_rating_session_val, int) else None
    else:
        has_rated = False
        user_rating_value = None

    commenter_profile = None
    if request.user.is_authenticated:
        try:
            commenter_profile = request.user.recipe_author_profile
        except RecipeAuthor.DoesNotExist:
            pass

    related_category_values = recipe.get_all_category_values()
    related_recipes = []
    if related_category_values:
        current_cats = set(related_category_values)
        raw_related = list(
            Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False)
            .exclude(pk=recipe.pk)
            .filter(Q(category__in=related_category_values) | Q(additional_category_links__category__in=related_category_values))
            .select_related("author")
            .prefetch_related("additional_category_links")
            .distinct()
            .order_by("-created_at")[:4]
        )
        for r in raw_related:
            shared = current_cats & set(r.get_all_category_values())
            related_recipes.append({
                "recipe": r,
                "shared_categories": sorted(
                    [
                        {
                            "label": Recipe.get_category_label(v),
                            "url": Recipe.get_category_url_for_value(v),
                        }
                        for v in shared
                    ],
                    key=lambda x: x["label"],
                ),
            })

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
        "is_saved": request.user.is_authenticated and SavedRecipe.objects.filter(user=request.user, recipe=recipe).exists(),
        "collection_add_url": reverse("collection:add_recipe", kwargs={"slug": recipe.slug}),
        "collection_remove_url": reverse("collection:remove_recipe", kwargs={"slug": recipe.slug}),
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        "related_recipes": related_recipes,
        "related_articles": list(
            Article.objects.filter(related_recipe=recipe, status=Article.Status.APPROVED, is_deleted=False)
            .select_related("author")
            .order_by("-published")[:5]
        ),
    }
    return render(request, "recipes/recipe_detail.html", context)


@require_POST
@ratelimit(key="ip", rate="10/h", method="POST", block=False)
@require_POST
def submit_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, status=Recipe.Status.APPROVED, is_deleted=False)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Please sign in to rate this recipe."}, status=401)
        messages.warning(request, "Please sign in to rate this recipe.")
        return redirect(f"{reverse('login')}?next={recipe.get_absolute_url()}")

    if getattr(request, "limited", False):
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Too many ratings. Please try again later."})
        messages.error(request, "You have submitted too many ratings. Please try again later.")
        return redirect(recipe.get_absolute_url())

    form = RecipeRatingForm(request.POST)
    if not form.is_valid():
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Please select a rating between 1 and 5."})
        messages.error(request, "Please submit a valid rating between 1 and 5.")
        return redirect(recipe.get_absolute_url())

    RecipeRating.objects.update_or_create(
        recipe=recipe,
        user=request.user,
        defaults={"value": form.cleaned_data["value"]},
    )

    session_key = f"recipe_rating_submitted_{recipe.pk}"
    request.session[session_key] = form.cleaned_data["value"]
    request.session.modified = True

    if is_ajax:
        return JsonResponse({"ok": True})
    messages.success(request, "Thank you. Your rating has been saved.")
    return redirect(recipe.get_absolute_url())


@require_POST
def reset_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Please sign in to change your rating."}, status=401)
        messages.warning(request, "Please sign in to change your rating.")
        return redirect(f"{reverse('login')}?next={recipe.get_absolute_url()}")

    session_key = f"recipe_rating_submitted_{recipe.pk}"
    request.session.pop(session_key, None)
    request.session.modified = True
    recipe.ratings.filter(user=request.user).delete()
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
    recipe = get_object_or_404(Recipe, slug=slug, status=Recipe.Status.APPROVED, is_deleted=False)
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
    recipe = get_object_or_404(Recipe, slug=slug, status=Recipe.Status.APPROVED, is_deleted=False)

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
            RecipeRating.objects.update_or_create(
                recipe=recipe,
                user=request.user,
                defaults={"value": rating_form.cleaned_data["value"]},
            )
            request.session[rating_session_key] = rating_form.cleaned_data["value"]
            request.session.modified = True

    request.session[last_comment_payload_key] = normalized_payload
    request.session.modified = True

    messages.success(request, "Your comment has been posted.")
    return redirect(f"{recipe.get_absolute_url()}#comments")


@require_POST
@login_required
def delete_recipe_gallery_image(request, image_id):
    image = get_object_or_404(
        RecipeImage.objects.select_related("recipe", "recipe__author"),
        pk=image_id,
    )
    recipe = image.recipe

    if not (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author)):
        raise Http404

    image.delete()
    messages.success(request, "Gallery image deleted.")
    return redirect(reverse("recipes:recipe_edit", kwargs={"slug": recipe.slug}))


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
    if recipe.is_deleted or recipe.status != Recipe.Status.APPROVED:
        raise Http404

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

    recipes_for_count = Recipe.objects.filter(author=author, is_deleted=False)
    articles_for_count = Article.objects.filter(author=author, is_deleted=False)
    if not (can_manage or moderator):
        recipes_for_count = recipes_for_count.filter(status=Recipe.Status.APPROVED)
        articles_for_count = articles_for_count.filter(status=Article.Status.APPROVED)

    recipe_count = recipes_for_count.count()
    article_count = articles_for_count.count()

    private_dashboard = can_manage or moderator
    _VALID_STATUS_FILTERS = {
        "draft": Recipe.Status.DRAFT,
        "pending": Recipe.Status.PENDING,
        "needs_changes": Recipe.Status.NEEDS_CHANGES,
        "rejected": Recipe.Status.REJECTED,
        "approved": Recipe.Status.APPROVED,
    }
    status_filter = request.GET.get("status", "").lower() if private_dashboard else ""
    status_value = _VALID_STATUS_FILTERS.get(status_filter)
    if not status_value:
        status_filter = ""

    recipe_qs = Recipe.objects.filter(author=author, is_deleted=False).order_by("-created_at")
    article_qs = Article.objects.filter(author=author, is_deleted=False).order_by("-published")
    if private_dashboard:
        if status_value:
            recipe_qs = recipe_qs.filter(status=status_value)
            article_qs = article_qs.filter(status=status_value)
    else:
        recipe_qs = recipe_qs.filter(status=Recipe.Status.APPROVED)
        article_qs = article_qs.filter(status=Article.Status.APPROVED)

    dashboard_recipes = list(recipe_qs)
    dashboard_articles = list(article_qs)

    context = {
        "author": author,
        "recipe_count": recipe_count,
        "article_count": article_count,
        "is_god_author": author.slug == settings.OWNER_SLUG,
        "can_manage_author_profile": can_manage,
        "is_moderator_viewer": moderator,
        "private_dashboard": private_dashboard,
        "dashboard_recipes": dashboard_recipes,
        "dashboard_articles": dashboard_articles,
        "status_filter": status_filter,
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
        if not _validate_recipe_gallery_uploads(form, self.request.FILES):
            return self.form_invalid(form)
        action = _authoring_action(self.request)
        recipe = form.save(commit=False, confirmed_by=self.request.user)
        recipe.author = self.author
        if is_moderator(self.request.user) and action == "approve_publish":
            recipe.status = Recipe.Status.APPROVED
        elif action == "save_draft":
            recipe.status = Recipe.Status.DRAFT
        else:
            recipe.status = Recipe.Status.PENDING
        recipe.save()
        getattr(form, "save_additional_categories")(recipe)
        _update_recipe_gallery_order(recipe, self.request.POST)

        for step in range(1, 21):
            img_file = self.request.FILES.get(f"gallery_step_{step}")
            if img_file:
                RecipeImage.objects.create(
                    recipe=recipe,
                    image=img_file,
                    sort_order=step,
                    alt_text=_gallery_step_alt(self.request.POST, step),
                )

        self.object = recipe
        if recipe.status == Recipe.Status.APPROVED:
            messages.success(self.request, "Recipe approved and published.")
        elif recipe.status == Recipe.Status.DRAFT:
            messages.success(self.request, "Recipe saved as a private draft.")
        else:
            messages.success(self.request, "Recipe submitted for review.")
            _send_recipe_notification(recipe, "pending")
        return redirect(recipe.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        context["cancel_url"] = reverse_lazy("recipes:recipe_list")
        context["gallery_step_rows"] = _gallery_step_rows()
        context["can_save_draft"] = True
        context["can_approve"] = is_moderator(self.request.user)
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
        if not _validate_recipe_gallery_uploads(form, self.request.FILES):
            return self.form_invalid(form)
        action = _authoring_action(self.request)
        was_approved = self.object.status == Recipe.Status.APPROVED
        previous_status = self.object.status
        recipe = form.save(commit=False, confirmed_by=self.request.user)
        if is_moderator(self.request.user) and action == "approve_publish":
            recipe.status = Recipe.Status.APPROVED
        elif not is_moderator(self.request.user):
            if was_approved:
                recipe.status = Recipe.Status.PENDING
            elif action == "save_draft":
                recipe.status = Recipe.Status.DRAFT
            else:
                recipe.status = Recipe.Status.PENDING
        recipe.save()
        getattr(form, "save_additional_categories")(recipe)
        _update_recipe_gallery_order(recipe, self.request.POST)

        for step in range(1, 21):
            img_file = self.request.FILES.get(f"gallery_step_{step}")
            alt_text = _gallery_step_alt(self.request.POST, step)
            existing = recipe.gallery_images.filter(sort_order=step).first()
            if existing:
                existing.alt_text = alt_text
            if img_file:
                if existing:
                    # pre_save signal (delete_old_gallery_image_on_change) handles cleanup
                    existing.image = img_file
                    existing.save(update_fields=["image", "alt_text"])
                else:
                    RecipeImage.objects.create(recipe=recipe, image=img_file, sort_order=step, alt_text=alt_text)
            elif existing:
                existing.save(update_fields=["alt_text"])

        self.object = recipe
        if is_moderator(self.request.user) and action == "approve_publish":
            messages.success(self.request, "Recipe approved and published.")
        elif recipe.status == Recipe.Status.DRAFT and not is_moderator(self.request.user):
            messages.success(self.request, "Recipe saved as a private draft.")
        elif was_approved and not is_moderator(self.request.user):
            messages.success(self.request, "Recipe updated and sent back to review before it goes live again.")
        elif previous_status in {Recipe.Status.DRAFT, Recipe.Status.NEEDS_CHANGES, Recipe.Status.REJECTED} and recipe.status == Recipe.Status.PENDING:
            messages.success(self.request, "Recipe submitted for review.")
            _send_recipe_notification(recipe, "pending")
        else:
            messages.success(self.request, "Recipe Updated Successfully.")
        next_url = self.request.POST.get("next") or self.request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return redirect(next_url)
        if is_moderator(self.request.user) and action != "approve_publish":
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
        next_url = self.request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            context["cancel_url"] = next_url
            context["next_url"] = next_url
        else:
            context["cancel_url"] = self.object.get_absolute_url() if self.object else reverse_lazy("recipes:recipe_list")
        context["existing_gallery_images"] = list(
            self.object.gallery_images.filter(is_active=True).order_by("sort_order", "id")
        ) if self.object else []
        context["gallery_step_rows"] = _gallery_step_rows(self.object)
        context["will_return_to_review"] = (
            bool(self.object)
            and self.object.status == Recipe.Status.APPROVED
            and not is_moderator(self.request.user)
        )
        context["can_save_draft"] = bool(self.object) and self.object.status != Recipe.Status.APPROVED
        context["can_approve"] = is_moderator(self.request.user)
        context["has_openai"] = bool(getattr(settings, "OPENAI_API_KEY", ""))
        return context


class RecipeDeleteView(AuthorRequiredMixin, DeleteView):
    model = Recipe
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Recipe.objects.filter(is_deleted=False)
        return Recipe.objects.filter(author=self.author, is_deleted=False)

    def form_valid(self, form):
        self.object = self.get_object()
        _soft_delete_recipe(self.object, self.request.user)
        messages.success(self.request, "Recipe deleted.")
        return redirect(self.success_url)

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

    pending_recipes = list(
        Recipe.objects.select_related("author", "author__user")
        .filter(status=Recipe.Status.PENDING, is_deleted=False)
        .order_by("-created_at")
    )
    needs_changes_recipes = list(
        Recipe.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Recipe.Status.NEEDS_CHANGES, is_deleted=False)
        .order_by("-moderated_at", "-created_at")
    )
    rejected_recipes = list(
        Recipe.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Recipe.Status.REJECTED, is_deleted=False)
        .order_by("-created_at")
    )
    pending_articles = (
        Article.objects.select_related("author", "author__user")
        .filter(status=Article.Status.PENDING)
        .order_by("-published")
    )
    needs_changes_articles = (
        Article.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Article.Status.NEEDS_CHANGES)
        .order_by("-moderated_at", "-published")
    )
    rejected_articles = (
        Article.objects.select_related("author", "author__user", "moderated_by")
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

    from config.maintenance import read_maintenance_flag

    maintenance_flag = read_maintenance_flag()
    maintenance_web_active = maintenance_flag is not None and maintenance_flag.get("active", False)
    maintenance_until_str = maintenance_flag.get("until", "") if maintenance_flag else ""

    return render(request, "moderation/panel.html", {
        "pending_recipes": pending_recipes,
        "needs_changes_recipes": needs_changes_recipes,
        "rejected_recipes": rejected_recipes,
        "pending_articles": pending_articles,
        "needs_changes_articles": needs_changes_articles,
        "rejected_articles": rejected_articles,
        "registered_authors": registered_authors,
        "author_query": author_query,
        "can_grant_bearseeker_privileges": _can_grant_bearseeker_privileges(request.user),
        "can_revoke_superuser_privileges": _can_revoke_superuser_privileges(request.user),
        "bearseeker_super_users": bearseeker_super_users,
        "bearseeker_authors": bearseeker_authors,
        "maintenance_web_active": maintenance_web_active,
        "maintenance_until_str": maintenance_until_str,
        "maintenance_env_active": getattr(settings, "MAINTENANCE_MODE", False),
    })


@login_required
def generate_recipe_view(request):
    if not is_moderator(request.user):
        raise Http404

    if request.method == "POST":
        dish_name = request.POST.get("dish_name", "").strip()
        author_slug = request.POST.get("author_slug", "greenbear").strip()
        status = request.POST.get("status", Recipe.Status.PENDING)
        no_image = request.POST.get("no_image") == "1"
        category = request.POST.get("category", "").strip()

        valid_categories = {c.value for c in Recipe.Category}
        if category not in valid_categories:
            category = ""

        if not dish_name:
            messages.error(request, "Dish name is required.")
            return redirect("recipes:generate_recipe")

        if status not in (Recipe.Status.DRAFT, Recipe.Status.PENDING):
            status = Recipe.Status.PENDING

        # Pre-validate before spawning the thread so the user gets an immediate error
        if not getattr(settings, "ANTHROPIC_API_KEY", ""):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"started": False, "error": "ANTHROPIC_API_KEY is not configured."}, status=500)
            messages.error(request, "ANTHROPIC_API_KEY is not configured.")
            return redirect("recipes:generate_recipe")

        author = RecipeAuthor.objects.filter(slug=author_slug).first()
        if not author:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"started": False, "error": f'Author "{author_slug}" not found.'}, status=400)
            messages.error(request, f'Author "{author_slug}" not found.')
            return redirect("recipes:generate_recipe")

        task = RecipeGenerationTask.objects.create(
            dish_name=dish_name,
            author=author,
            requested_by=request.user,
            status=RecipeGenerationTask.Status.RUNNING,
        )
        task_id = str(task.task_id)

        import threading
        from django.core.management import call_command
        from django.db import close_old_connections

        logger.info("generate_recipe: view spawning thread for %r (task=%s)", dish_name, task_id)

        def _run():
            logger.info("generate_recipe: background thread started for %r (task=%s)", dish_name, task_id)
            close_old_connections()

            try:
                kwargs = {"author_slug": author_slug, "status": status, "no_image": no_image, "dry_run": False, "limit": 0, "batch": None, "task_id": task_id, "category": category}
                call_command("generate_recipe", dish_name, **kwargs)
            except Exception as exc:
                logger.error("generate_recipe background thread failed for %r: %s", dish_name, exc, exc_info=True)
                RecipeGenerationTask.objects.filter(task_id=task_id).update(
                    status=RecipeGenerationTask.Status.FAILED,
                    error_message=str(exc)[:1000],
                    updated_at=timezone.now(),
                )
            finally:
                close_old_connections()

        threading.Thread(target=_run, daemon=True).start()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"started": True, "dish_name": dish_name, "task_id": task_id})

        messages.success(request, f'Generation started for "{dish_name}". Check the pending queue in a couple of minutes.')
        return redirect("recipes:moderation_panel")

    authors = RecipeAuthor.objects.filter(user__isnull=False).order_by("name")
    return render(request, "moderation/generate_recipe.html", {
        "authors": authors,
        "default_author_slug": "greenbear",
        "category_choices": Recipe.Category.choices,
        "status_choices": [
            (Recipe.Status.PENDING, "Pending, goes to moderation queue"),
            (Recipe.Status.DRAFT, "Draft, saved privately, not visible"),
        ],
    })


@login_required
def generate_recipe_poll(request):
    """Poll a specific recipe generation task."""
    if not is_moderator(request.user):
        return JsonResponse({"ready": False}, status=403)

    task_id = request.GET.get("task_id", "").strip()
    if not task_id:
        return JsonResponse({"ready": False, "error": "missing task_id"}, status=400)

    try:
        task = RecipeGenerationTask.objects.select_related("result_recipe").get(
            task_id=task_id,
            requested_by=request.user,
        )
    except (RecipeGenerationTask.DoesNotExist, ValueError):
        return JsonResponse({"ready": False, "error": "task not found"}, status=404)

    if task.status == RecipeGenerationTask.Status.DONE:
        if task.result_recipe:
            return JsonResponse({
                "ready": True,
                "status": task.status,
                "slug": task.result_recipe.slug,
                "title": task.result_recipe.title,
            })
        # Recipe was deleted after task completed (FK went NULL)
        return JsonResponse({
            "ready": False,
            "failed": True,
            "status": task.status,
            "error": "The generated recipe was deleted before it could be loaded.",
        })

    if task.status == RecipeGenerationTask.Status.FAILED:
        return JsonResponse({
            "ready": False,
            "failed": True,
            "status": task.status,
            "error": task.error_message or "Recipe generation failed.",
        })

    stale_after = timezone.now() - timedelta(minutes=20)
    if task.status == RecipeGenerationTask.Status.RUNNING and task.updated_at < stale_after:
        task.status = RecipeGenerationTask.Status.FAILED
        task.error_message = "Recipe generation stopped before it completed. Please start it again."
        task.save(update_fields=["status", "error_message", "updated_at"])
        return JsonResponse({
            "ready": False,
            "failed": True,
            "status": task.status,
            "error": task.error_message,
        })

    return JsonResponse({"ready": False, "status": task.status})


def automation_progress(request):
    if not is_moderator(request.user):
        raise Http404

    return render(
        request,
        "moderation/automation_progress.html",
        {"automation_progress": _build_automation_roadmap_progress()},
    )


def _send_recipe_notification(recipe, event, moderation_note=""):
    author = recipe.author
    if not author or not author.user or not author.user.email:
        return
    email = author.user.email
    author_name = author.name or author.user.get_username()
    profile_url = build_absolute_url(author.get_absolute_url())
    recipe_url = build_absolute_url(recipe.get_absolute_url())

    if event == "pending":
        send_template_mail(
            subject=f'Your recipe "{recipe.title}" is awaiting moderation',
            template="recipe_pending",
            context={"author_name": author_name, "recipe_title": recipe.title, "profile_url": profile_url},
            recipient_list=[email],
            fail_silently=True,
        )
    elif event == "rejected":
        send_template_mail(
            subject=f'Your recipe "{recipe.title}" was not approved',
            template="recipe_rejected",
            context={"author_name": author_name, "recipe_title": recipe.title, "moderation_note": moderation_note, "profile_url": profile_url},
            recipient_list=[email],
            fail_silently=True,
        )
    elif event == "approved":
        send_template_mail(
            subject=f'Your recipe "{recipe.title}" is now live on CulinEire!',
            template="recipe_approved",
            context={"author_name": author_name, "recipe_title": recipe.title, "recipe_url": recipe_url},
            recipient_list=[email],
            fail_silently=True,
        )


@require_POST
def moderate_recipe(request, slug):
    if not is_moderator(request.user):
        raise Http404
    recipe = get_object_or_404(Recipe, slug=slug)
    action = request.POST.get("action")

    if action == "approve":
        recipe.status = Recipe.Status.APPROVED
        recipe.moderation_note = ""
        recipe.moderated_by = request.user
        recipe.moderated_at = timezone.now()
        recipe.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
        messages.success(request, f'"{recipe.title}" approved and is now live.')
        _send_recipe_notification(recipe, "approved")
    elif action == "request_changes":
        note = request.POST.get("moderation_note", "").strip()
        if not note:
            messages.error(request, "A moderation note is required. Please explain what needs to be changed.")
            return redirect(recipe.get_absolute_url())
        recipe.status = Recipe.Status.NEEDS_CHANGES
        recipe.moderation_note = note
        recipe.moderated_by = request.user
        recipe.moderated_at = timezone.now()
        recipe.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
        messages.warning(request, f'Changes requested for "{recipe.title}".')
    elif action == "reject":
        note = request.POST.get("moderation_note", "").strip()
        if not note:
            messages.error(request, "A rejection note is required. Please explain what needs to be corrected.")
            return redirect(recipe.get_absolute_url())
        recipe.status = Recipe.Status.REJECTED
        recipe.moderation_note = note
        recipe.moderated_by = request.user
        recipe.moderated_at = timezone.now()
        recipe.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
        messages.warning(request, f'"{recipe.title}" rejected.')
        _send_recipe_notification(recipe, "rejected", moderation_note=note)
    elif action == "delete":
        title = recipe.title
        _soft_delete_recipe(recipe, request.user)
        messages.success(request, f'"{title}" deleted.')
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


@require_POST
@login_required
def recipe_regenerate_image(request, slug):
    from django.core.files.base import ContentFile
    from .management.commands.generate_recipe import fetch_image_bytes, _image_extension, _sanitise_image_subject

    recipe = get_object_or_404(Recipe, slug=slug)
    if not (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author)):
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    image_type = request.POST.get("image_type")
    image_id = request.POST.get("image_id", "")
    feedback = request.POST.get("feedback", "").strip()

    try:
        if image_type == "hero":
            subject = _sanitise_image_subject(recipe.title, recipe.hero_image_alt_text or "")
            prompt = (
                f"Professional food photography: {subject}. "
                "Irish cuisine, natural light, rustic wooden surface, ceramic or white plate, "
                "appetising close-up presentation. No text, no watermarks, no people, no brand names or logos."
            )
            if feedback:
                prompt += f" Important: {feedback}."
            image_bytes = fetch_image_bytes(prompt)
            ext = _image_extension(image_bytes)
            filename = f"cover-{recipe.slug[:40]}-regen{ext}"
            # Do NOT manually delete the old file — the pre_save signal in signals.py
            # detects the name change and cleans it up safely after the new file is confirmed.
            recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
            openai_model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
            recipe.image_rights_note = f"AI-generated image via {openai_model}."
            recipe.hero_image.save(filename, ContentFile(image_bytes), save=False)
            recipe.save(update_fields=["hero_image", "image_rights_status", "image_rights_note"])
            return JsonResponse({"success": True, "url": recipe.hero_image.url})

        elif image_type == "step":
            img = get_object_or_404(RecipeImage, pk=image_id, recipe=recipe)
            # Use stored step text (alt_text) if available, otherwise derive from recipe method
            step_text = (img.alt_text or "").strip()
            if not step_text and recipe.method:
                method_lines = [s.strip() for s in recipe.method.splitlines() if s.strip()]
                if method_lines:
                    idx = min((img.sort_order or 1) - 1, len(method_lines) - 1)
                    step_text = method_lines[max(idx, 0)]
            step_label = img.caption or f"Step {img.sort_order or 1}"
            prompt = (
                f"Professional food photography for the dish '{recipe.title}'. "
                f"{step_label}: {step_text[:250]}. " if step_text else
                f"Professional food photography for the dish '{recipe.title}'. "
            )
            prompt += (
                "Irish cuisine, natural lighting, rustic kitchen setting. "
                "No text, no watermarks, no people, no brand names or logos."
            )
            if feedback:
                prompt += f" Important: {feedback}."
            image_bytes = fetch_image_bytes(prompt)
            ext = _image_extension(image_bytes)
            filename = f"step{img.sort_order}-{recipe.slug[:30]}-regen{ext}"
            # pre_save signal handles old file cleanup when name changes
            img.image.save(filename, ContentFile(image_bytes), save=True)
            if recipe.image_rights_status != Recipe.ImageRightsStatus.AI_GENERATED:
                openai_model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
                recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
                recipe.image_rights_note = f"AI-generated image via {openai_model}."
                recipe.save(update_fields=["image_rights_status", "image_rights_note"])
            return JsonResponse({"success": True, "url": img.image.url})

        return JsonResponse({"success": False, "error": "Invalid image_type"})

    except Exception as exc:
        logger.error("recipe_regenerate_image failed for %r: %s", recipe.slug, exc, exc_info=True)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


# ── Recipe format automation endpoints ────────────────────────────────────────

@require_POST
@login_required
def recipe_format_suggest(request):
    """
    POST body: JSON {title, short_description, ingredients, method, tips,
                     prep_time_minutes, cook_time_minutes, servings,
                     difficulty, irish_context, author_commentary}
    Returns JSON with normalised text fields.
    No DB writes.  Login required.
    """
    from articles.services.editorial_tools import suggest_recipe_fields
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()
    result = suggest_recipe_fields(data)
    return JsonResponse({
        "ingredients": result.get("ingredients", ""),
        "method": result.get("method", ""),
        "tips": result.get("tips", ""),
        "irish_context": result.get("irish_context", ""),
        "author_commentary": result.get("author_commentary", ""),
    })


@require_POST
@login_required
def recipe_format_preview(request):
    """
    POST body: JSON recipe fields.
    Returns JSON {preview_html: str}
    No DB writes.  Login required.
    """
    from articles.services.editorial_tools import render_recipe_preview
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()
    preview_html = render_recipe_preview(data)
    return JsonResponse({"preview_html": preview_html})
