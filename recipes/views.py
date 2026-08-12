import json
import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

logger = logging.getLogger("recipes")

from django.conf import settings

from recipes.media_utils import webp_url
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.db.models import Avg, Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import Http404, HttpResponseGone, JsonResponse
from django.core.files.storage import default_storage
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
    can_grant_superuser_privileges as _can_grant_superuser_privileges,
    can_revoke_superuser_privileges as _can_revoke_superuser_privileges,
    is_moderator,
)
from config.email_utils import build_absolute_url, send_template_mail
from articles.models import Article, ArticleImage
from collection.models import SavedArticle, SavedContent, SavedRecipe
from config.release_journal import RELEASE_JOURNAL, build_git_journal, current_version
from config.turnstile import verify_turnstile
from monitoring.tracker import get_client_ip, hash_ip, track_event
from .allergens import build_present_allergen_items
from .authoring import (
    AuthorRequiredMixin,
    author_skips_approval,
    get_author_for_user,
    user_can_manage_author,
)
from .forms import (
    RecipeAuthoringForm,
    RecipeAuthorProfileForm,
    RecipeCommentForm,
    RecipeRatingForm,
    RecipeScreenshotPreviewForm,
    RecipeScreenshotUploadForm,
)
from .models import Recipe, RecipeAuthor, RecipeComment, RecipeGenerationTask, RecipeImage, RecipeRating
from .validators import validate_image_upload
from config.email_utils import build_absolute_url, send_template_mail
from .services.screenshot_recipe_importer import (
    ScreenshotExtractionError,
    build_recipe_initial_data_from_extraction,
    create_recipe_from_extraction,
    extract_recipe_from_image,
    generate_reconstructed_hero_image,
    normalise_extracted_recipe,
    to_recipe_form_data,
)

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

ARENA_MASTER_CONSOLE_PLAN_DIR = settings.BASE_DIR / "docs" / "chef_battle" / "arena_master_console"
ARENA_MASTER_CONSOLE_PLAN_FILES = (
    ("master", "Master Plan", "00_MASTER_PLAN.yaml"),
    ("capabilities", "Capability Map", "01_CAPABILITY_MAP.yaml"),
    ("p00", "P00 - Discovery, baseline, and contract freeze", "phase_00_discovery.yaml"),
    ("p01", "P01 - Visual shell and responsive arena layout", "phase_01_visual_shell.yaml"),
    ("p02", "P02 - Read models and live arena projection", "phase_02_read_models.yaml"),
    ("p03", "P03 - Battle flow and phase controls", "phase_03_battle_flow.yaml"),
    ("p04", "P04 - Combat engine and live monitor", "phase_04_combat_monitor.yaml"),
    ("p05", "P05 - Moderation, safety, and streams", "phase_05_moderation_safety.yaml"),
    ("p06", "P06 - Voting integrity and analytics", "phase_06_voting_integrity.yaml"),
    ("p07", "P07 - Economy, gifts, and artefacts", "phase_07_economy_gifts.yaml"),
    ("p08", "P08 - Governance, ranks, and rewards", "phase_08_governance.yaml"),
    ("p09", "P09 - Hardening, verification, and release", "phase_09_hardening_release.yaml"),
)

RECIPE_MOOD_CHIPS = [
    ("bread_and_baking", "Baking"),
    ("soups_and_stews", "Soups and Stews"),
    ("fish_and_seafood", "Seafood"),
    ("vegetables", "Vegetables"),
    ("meat_and_poultry", "Meat"),
    ("desserts", "Desserts"),
    ("drinks", "Drinks"),
]

AUTHOR_DASHBOARD_STATUS_FILTERS = (
    ("draft", Recipe.Status.DRAFT, "Draft"),
    ("pending", Recipe.Status.PENDING, "Waiting for review"),
    ("needs_changes", Recipe.Status.NEEDS_CHANGES, "Needs changes"),
    ("rejected", Recipe.Status.REJECTED, "Rejected"),
    ("approved", Recipe.Status.APPROVED, "Published"),
)

GOD_AUTHOR_DASHBOARD_STATUS_FILTER_KEYS = {"draft", "approved"}

AUTHOR_DASHBOARD_CONTENT_FILTERS = (
    ("ab", "Pinch"),
    ("recipes", "Recipes"),
    ("articles", "Articles"),
)

AUTHOR_DASHBOARD_VISIBLE_STATUS_FILTER_KEYS = {"draft", "approved"}


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


def _build_site_research_progress():
    approved_recipe_count = Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False).count()
    approved_article_count = Article.objects.filter(status=Article.Status.APPROVED, is_deleted=False).count()
    draft_recipe_count = Recipe.objects.filter(status__in=[Recipe.Status.DRAFT, Recipe.Status.PENDING], is_deleted=False).count()
    draft_article_count = Article.objects.filter(status__in=[Article.Status.DRAFT, Article.Status.PENDING], is_deleted=False).count()

    try:
        from pinch.models import Pinch

        approved_bite_count = Pinch.objects.filter(status=Pinch.Status.APPROVED).count()
        pending_bite_count = Pinch.objects.filter(status=Pinch.Status.PENDING).count()
    except Exception:
        approved_bite_count = 0
        pending_bite_count = 0

    areas = [
        {"label": "Accessibility", "score": 64, "status": "active"},
        {"label": "Performance", "score": 61, "status": "done"},
        {"label": "SEO", "score": 62, "status": "active"},
        {"label": "Mobile", "score": 60, "status": "pending"},
        {"label": "Security", "score": 72, "status": "done"},
        {"label": "Content", "score": 72, "status": "active"},
        {"label": "Governance", "score": 63, "status": "pending"},
    ]

    checklist = [
        {
            "status": "done",
            "label": "Research report ingested",
            "detail": "Deep research findings have been converted into a site-wide verification backlog.",
        },
        {
            "status": "done",
            "label": "Moderation mirror",
            "detail": "Create a read-only page showing the current research phase, scores, TODOs and yearly roadmap.",
        },
        {
            "status": "done",
            "label": "Recipe method accessibility",
            "detail": "Remove duplicated step numerals from recipe method markup while preserving visual numbering.",
        },
        {
            "status": "done",
            "label": "Rendered HTML comment hygiene",
            "detail": "Remove public template comments from base and sponsors templates so snippets cannot expose implementation notes.",
        },
        {
            "status": "done",
            "label": "Canonical host verification",
            "detail": "Verified deployed www duplicate, kept sitemap/canonical on apex and added app-level www-to-apex redirect.",
        },
        {
            "status": "done",
            "label": "Structured data validation",
            "detail": "Added rendered Recipe JSON-LD/BreadcrumbList validation and kept existing Article JSON-LD coverage.",
        },
        {
            "status": "done",
            "label": "Archive duplicate audit",
            "detail": "Check recipe list, category and author archive queries for duplicate rows caused by joins or category links.",
        },
        {
            "status": "done",
            "label": "SERP snippet hygiene",
            "detail": "Removed template-like fallback descriptions and verified deployed canonical/schema snippets after deploy.",
        },
        {
            "status": "done",
            "label": "Security headers baseline",
            "detail": "Verified production security headers and added CSP/header regression tests with frame-ancestors protection.",
        },
        {
            "status": "done",
            "label": "Performance evidence baseline",
            "detail": "Measured deployed HTML weight and added lazy/async image hints for public cards and detail media.",
        },
        {
            "status": "active",
            "label": "PageSpeed post-deploy check",
            "detail": "Run external PageSpeed/Core Web Vitals checks after deployment and decide whether image resizing or CSS splitting is next.",
        },
        {
            "status": "manual",
            "label": "External evidence pass",
            "detail": "Run Rich Results, Search Console, Lighthouse/PageSpeed and security header checks against deployed URLs.",
        },
    ]

    months = [
        {
            "month": "Month 1",
            "title": "Evidence baseline and P0 repairs",
            "status": "active",
            "detail": "Moderation mirror, rendered HTML audit, duplicate step numbering, archive duplicates, SERP leak, canonical redirect, security headers.",
        },
        {
            "month": "Month 2",
            "title": "Recipe and article SEO quality",
            "status": "pending",
            "detail": "Validate schema, improve meta descriptions, align BreadcrumbList, improve Recipe/Article trust signals.",
        },
        {
            "month": "Month 3",
            "title": "Accessibility hardening",
            "status": "pending",
            "detail": "Forms, ratings, comments, keyboard focus, target sizes, alt policy and WCAG 2.2 checks.",
        },
        {
            "month": "Month 4",
            "title": "Performance and Core Web Vitals",
            "status": "pending",
            "detail": "Hero image handling, lazy loading, width/height, Lighthouse budgets and field measurement plan.",
        },
        {
            "month": "Month 5",
            "title": "Security and privacy baseline",
            "status": "pending",
            "detail": "Headers, cautious HSTS policy, third-party inventory, self-hosted fonts and cookie/storage audit.",
        },
        {
            "month": "Month 6",
            "title": "Monitoring and feedback loops",
            "status": "pending",
            "detail": "Use existing monitoring to feed content, SEO and social planning without adding non-essential tracking.",
        },
        {
            "month": "Month 7",
            "title": "Archive IA and crawl hygiene",
            "status": "pending",
            "detail": "Pagination, ItemList markup, category navigation, author archives and internal linking.",
        },
        {
            "month": "Month 8",
            "title": "Content depth",
            "status": "pending",
            "detail": "Nutrition, substitutions, storage, equipment, provenance notes and editorial review notes.",
        },
        {
            "month": "Month 9",
            "title": "Distribution readiness",
            "status": "pending",
            "detail": "Telegram, social queues, share metadata, post templates and human review gates.",
        },
        {
            "month": "Month 10",
            "title": "Localization decision",
            "status": "pending",
            "detail": "Keep hreflang out until alternate-language URLs exist; design reciprocal clusters if localization starts.",
        },
        {
            "month": "Month 11",
            "title": "Governance and stack inventory",
            "status": "pending",
            "detail": "Single build version, SBOM, dependency cadence, deployment smoke checks and ownership matrix.",
        },
        {
            "month": "Month 12",
            "title": "Full re-audit",
            "status": "pending",
            "detail": "Repeat site-wide audit, compare scores, close remaining P1/P2 issues and update the next yearly plan.",
        },
    ]

    active_items = [item for item in checklist if item["status"] == "active"]
    completed_items = [item for item in checklist if item["status"] == "done"]
    done_count = len(completed_items)
    total_count = len([item for item in checklist if item["status"] != "manual"])
    percent = round((done_count / total_count) * 100) if total_count else 0

    current_focus = "P1 PageSpeed post-deploy check and image delivery decisions"

    handoff_lines = [
        "CulinEire site research tracker",
        f"Generated: {timezone.localdate().isoformat()}",
        f"Current focus: {current_focus}.",
        "",
        "Current local content counts:",
        f"- Approved recipes: {approved_recipe_count}",
        f"- Draft/pending recipes: {draft_recipe_count}",
        f"- Approved articles: {approved_article_count}",
        f"- Draft/pending articles: {draft_article_count}",
        f"- Approved Pinch: {approved_bite_count}",
        f"- Pending Pinch: {pending_bite_count}",
        "",
        "Active work:",
    ]
    for item in active_items:
        handoff_lines.append(f"- {item['label']}: {item['detail']}")

    return {
        "generated_on": timezone.localdate(),
        "current_focus": current_focus,
        "areas": areas,
        "checklist": checklist,
        "months": months,
        "active_items": active_items,
        "done_count": done_count,
        "total_count": total_count,
        "percent": percent,
        "content_counts": {
            "approved_recipes": approved_recipe_count,
            "draft_recipes": draft_recipe_count,
            "approved_articles": approved_article_count,
            "draft_articles": draft_article_count,
            "approved_bites": approved_bite_count,
            "pending_bites": pending_bite_count,
        },
        "copy_text": "\n".join(handoff_lines),
    }


def _can_view_site_update_plan(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    author = getattr(user, "recipe_author_profile", None)
    return author is not None and author.slug == settings.OWNER_SLUG



CATEGORY_IMAGE_MAP = {
    "irish_culinary_heritage": "images/categories/irish-culinary-heritage.webp",
    "modern_irish_cooking": "images/categories/modern-irish-cooking.webp",
    "everyday_irish_cooking": "images/categories/everyday-irish-cooking.webp",
    "breakfast_and_brunch": "images/categories/breakfast-and-brunch.webp",
    "lunch": "images/categories/lunch.webp",
    "dinner": "images/categories/dinner.webp",
    "grilling_and_barbecue": "images/categories/grilling-and-barbecue.webp",
    "soups_and_stews": "images/categories/soups-and-stews.webp",
    "salads": "images/categories/salads.webp",
    "seasonal_and_festive_irish": "images/categories/seasonal-and-festive.webp",
    "healthy_eating": "images/categories/healthy-eating.webp",
    "pasta_and_noodles": "images/categories/pasta-and-noodles.webp",
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
        # Normalise space-before-punctuation that AI generation can produce
        cleaned = re.sub(r"\s+([,;:!?])", r"\1", cleaned)

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
        .order_by("-created_at")[:20]
    )

    latest_articles = (
        Article.objects.select_related("author", "related_recipe")
        .prefetch_related(article_card_gallery_prefetch)
        .filter(status=Article.Status.APPROVED, is_deleted=False)
        .order_by("-published")[:6]
    )
    try:
        from pinch.visibility import can_view_pinch_public_area
        can_show_pinch = can_view_pinch_public_area(request.user)
    except Exception:
        can_show_pinch = False

    try:
        from pinch.views import _public_queryset as _ab_qs, _user_state as _ab_state
        latest_pinch = list(
            _ab_qs()[:6]
        ) if can_show_pinch else []
        _, ab_liked_ids, ab_saved_ids, ab_followed_author_ids = _ab_state(latest_pinch, request.user)
    except Exception:
        latest_pinch = []
        ab_liked_ids = set()
        ab_saved_ids = set()
        ab_followed_author_ids = set()

    try:
        from pinch.models import PinchComment
        announcement_comment_count = PinchComment.objects.filter(
            pinch_item__slug="chefs-battle-announcement-2026",
            is_deleted=False,
        ).count()
    except Exception:
        announcement_comment_count = 0

    context = {
        "latest_recipes": latest_recipes,
        "latest_articles": latest_articles,
        "latest_pinch": latest_pinch,
        "ab_liked_ids": ab_liked_ids,
        "ab_saved_ids": ab_saved_ids,
        "ab_followed_author_ids": ab_followed_author_ids,
        "announcement_comment_count": announcement_comment_count,
    }
    return render(request, "home.html", context)


def recipe_list(request):
    author_slug = (request.GET.get("author") or "").strip()
    q = (request.GET.get("q") or "").strip()
    recipes = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
        .filter(status=Recipe.Status.APPROVED, is_deleted=False)
        .order_by("-created_at")
    )
    if q:
        recipes = recipes.filter(Q(title__icontains=q) | Q(ingredients__icontains=q))
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
    can_manage_selected_author = False
    if author_slug:
        selected_author = get_object_or_404(RecipeAuthor, slug=author_slug)
        can_manage_selected_author = user_can_manage_author(request.user, selected_author) or is_moderator(request.user)
        recipes = recipes.filter(author=selected_author)
        popular_recipe_candidates = popular_recipe_candidates.filter(author=selected_author)

        if can_manage_selected_author:
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

    recent_recipes = list(recipes[:20]) if selected_author else None
    default_recent_recipes = list(recipes[:20]) if not selected_author else None
    all_recipes_grid = list(recipes[:50]) if not selected_author else None

    all_articles = None
    recent_articles = None
    if selected_author:
        all_articles = (
            Article.objects.select_related("author")
            .filter(author=selected_author, is_deleted=False)
            .order_by("-published")
        )
        if not can_manage_selected_author:
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
            else "Explore The Full Irish Recipe Collection, Old And New"
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
        "can_manage_selected_author": can_manage_selected_author,
        "dashboard_back_url": reverse("recipes:author_dashboard") if can_manage_selected_author else "",
        "search_query": q,
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
        return HttpResponseGone()

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
                        # Empty unless a WebP sibling has been generated; the
                        # template offers it as a <source> and keeps src as the
                        # fallback, so a half-converted media tree still renders.
                        "src_webp": webp_url(item.image),
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
        "can_generate_ab": (
            recipe.status == Recipe.Status.APPROVED
            and (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author))
        ),
        "recipe_ab_exists": (
            recipe.status == Recipe.Status.APPROVED
            and recipe.pinch_items.exclude(status="archived").exists()
        ),
        "recipe_ab_url": (
            ab.get_absolute_url()
            if (ab := recipe.pinch_items.exclude(status="archived").first())
            else None
        ),
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


@login_required
def author_dashboard(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(
            request,
            AuthorRequiredMixin.author_required_message,
        )
        return redirect("home")

    return author_detail(request, author.slug)


def author_detail(request, slug):
    author = get_object_or_404(RecipeAuthor, slug=slug)
    can_manage = user_can_manage_author(request.user, author)
    moderator = is_moderator(request.user)
    is_god_author = author.slug == settings.OWNER_SLUG
    dashboard_status_filters = (
        tuple(
            status_filter
            for status_filter in AUTHOR_DASHBOARD_STATUS_FILTERS
            if status_filter[0] in GOD_AUTHOR_DASHBOARD_STATUS_FILTER_KEYS
        )
        if is_god_author
        else AUTHOR_DASHBOARD_STATUS_FILTERS
    )

    battle_profile = None
    recent_battles = []
    arena_battles = []
    arena_gift_display = []
    champion_badge = None
    from chef_battle.access import is_battle_visible
    chef_battle_enabled = is_battle_visible(request)

    if chef_battle_enabled:
        try:
            from chef_battle.selectors import get_author_battle_summary
            _summary = get_author_battle_summary(author)
            battle_profile = _summary["battle_profile"]
            recent_battles = _summary["recent_battles"]
            arena_battles = _summary["battles"]
            arena_gift_display = _summary["gift_display"]
            champion_badge = _summary.get("champion_badge")
        except Exception:
            logger.exception("Chef Battle profile data is unavailable for author %s.", author.pk)

    recipes_for_count = Recipe.objects.filter(author=author, is_deleted=False)
    articles_for_count = Article.objects.filter(author=author, is_deleted=False)
    if not (can_manage or moderator):
        recipes_for_count = recipes_for_count.filter(status=Recipe.Status.APPROVED)
        articles_for_count = articles_for_count.filter(status=Article.Status.APPROVED)

    recipe_count = recipes_for_count.count()
    article_count = articles_for_count.count()
    private_dashboard = can_manage or moderator
    recipe_workspace_attention_count = 0
    if private_dashboard:
        recipe_workspace_attention_count = Recipe.objects.filter(
            author=author,
            is_deleted=False,
            status__in=[
                Recipe.Status.DRAFT,
                Recipe.Status.PENDING,
                Recipe.Status.NEEDS_CHANGES,
                Recipe.Status.REJECTED,
            ],
        ).count()
    try:
        from pinch.visibility import can_view_pinch_public_area
        can_show_public_pinch = can_view_pinch_public_area(request.user)
    except Exception:
        can_show_public_pinch = False
    can_show_pinch_workspace = private_dashboard or can_show_public_pinch

    pinch_count = 0
    try:
        from pinch.models import Pinch as _Pinch
        ab_qs = _Pinch.objects.filter(author=author)
        if not private_dashboard:
            ab_qs = ab_qs.filter(status=_Pinch.Status.APPROVED)
        if can_show_pinch_workspace:
            pinch_count = ab_qs.count()
    except Exception:
        pass

    _VALID_STATUS_FILTERS = {
        key: status_value for key, status_value, _label in dashboard_status_filters
    }
    _STATUS_FILTER_LABELS = {
        key: label for key, _status_value, label in dashboard_status_filters
    }
    status_filter = request.GET.get("status", "").lower() if private_dashboard else ""
    status_value = _VALID_STATUS_FILTERS.get(status_filter)
    if not status_value:
        status_filter = ""
    status_filter_label = _STATUS_FILTER_LABELS.get(status_filter, "")
    _CONTENT_FILTER_LABELS = {
        key: label for key, label in AUTHOR_DASHBOARD_CONTENT_FILTERS
    }
    content_filter = request.GET.get("content", "").lower() if private_dashboard else ""
    if content_filter not in _CONTENT_FILTER_LABELS:
        content_filter = ""
    content_filter_label = _CONTENT_FILTER_LABELS.get(content_filter, "")

    def _dashboard_filter_url(*, content_key=None, status_key=None):
        next_content = content_filter if content_key is None else content_key
        next_status = status_filter if status_key is None else status_key
        params = {}
        if next_content:
            params["content"] = next_content
        if next_status:
            params["status"] = next_status
        query = urlencode(params)
        return f"{request.path}?{query}" if query else request.path

    dashboard_content_filters = [
        {
            "key": key,
            "label": label,
            "url": _dashboard_filter_url(content_key=key),
            "active": content_filter == key,
        }
        for key, label in AUTHOR_DASHBOARD_CONTENT_FILTERS
    ]
    dashboard_status_filter_links = [
        {
            "key": key,
            "label": label,
            "url": _dashboard_filter_url(status_key=key),
            "active": status_filter == key,
        }
        for key, _status_value, label in dashboard_status_filters
        if key in AUTHOR_DASHBOARD_VISIBLE_STATUS_FILTER_KEYS
    ]
    dashboard_filter_links = [
        *dashboard_content_filters,
        *dashboard_status_filter_links,
    ]

    recipe_qs = Recipe.objects.filter(author=author, is_deleted=False).order_by("-created_at")
    article_qs = Article.objects.filter(author=author, is_deleted=False).order_by("-published")
    if private_dashboard:
        if status_value:
            recipe_qs = recipe_qs.filter(status=status_value)
            article_qs = article_qs.filter(status=status_value)
    else:
        recipe_qs = recipe_qs.filter(status=Recipe.Status.APPROVED)
        article_qs = article_qs.filter(status=Article.Status.APPROVED)

    if private_dashboard and content_filter:
        if content_filter != "recipes":
            recipe_qs = recipe_qs.none()
        if content_filter != "articles":
            article_qs = article_qs.none()

    dashboard_recipes = list(recipe_qs)
    dashboard_articles = list(article_qs)
    dashboard_pinch = []
    try:
        from pinch.models import Pinch as _Pinch
        if not (private_dashboard and content_filter and content_filter != "ab"):
            ab_qs2 = _Pinch.objects.filter(author=author).order_by("-published_at", "-created_at")
            if private_dashboard:
                if status_value:
                    ab_qs2 = ab_qs2.filter(status=status_value)
            else:
                ab_qs2 = ab_qs2.filter(status=_Pinch.Status.APPROVED)
            dashboard_pinch = list(ab_qs2) if can_show_pinch_workspace else []
    except Exception:
        pass

    collection_count = 0
    dashboard_saved_recipes = []
    dashboard_saved_articles = []
    dashboard_saved_pinch = []
    if private_dashboard:
        dashboard_saved_recipes = list(
            SavedRecipe.objects.filter(
                user=request.user,
                recipe__status=Recipe.Status.APPROVED,
                recipe__is_deleted=False,
            ).select_related("recipe", "recipe__author")
        )
        dashboard_saved_articles = list(
            SavedArticle.objects.filter(
                user=request.user,
                article__status=Article.Status.APPROVED,
                article__is_deleted=False,
            ).select_related("article", "article__author")
        )
        if can_show_public_pinch:
            try:
                from pinch.models import Pinch as _Pinch
                pinch_type = ContentType.objects.get_for_model(_Pinch)
                approved_pinch_ids = _Pinch.objects.filter(
                    status=_Pinch.Status.APPROVED
                ).values("pk")
                dashboard_saved_pinch = list(
                    SavedContent.objects.filter(
                        user=request.user,
                        content_type=pinch_type,
                        object_id__in=approved_pinch_ids,
                    ).select_related("content_type")
                )
            except Exception:
                pass
        collection_count = (
            len(dashboard_saved_recipes)
            + len(dashboard_saved_articles)
            + len(dashboard_saved_pinch)
        )

    context = {
        "author": author,
        "recipe_count": recipe_count,
        "recipe_workspace_attention_count": recipe_workspace_attention_count,
        "article_count": article_count,
        "pinch_count": pinch_count,
        "show_pinch_profile_links": can_show_public_pinch,
        "is_god_author": is_god_author,
        "can_manage_author_profile": can_manage,
        "is_moderator_viewer": moderator,
        "private_dashboard": private_dashboard,
        "dashboard_recipes": dashboard_recipes,
        "dashboard_articles": dashboard_articles,
        "dashboard_pinch": dashboard_pinch,
        "dashboard_saved_recipes": dashboard_saved_recipes,
        "dashboard_saved_articles": dashboard_saved_articles,
        "dashboard_saved_pinch": dashboard_saved_pinch,
        "dashboard_status_filters": dashboard_status_filters,
        "dashboard_content_filters": dashboard_content_filters,
        "dashboard_status_filter_links": dashboard_status_filter_links,
        "dashboard_filter_links": dashboard_filter_links,
        "status_filter": status_filter,
        "status_filter_label": status_filter_label,
        "content_filter": content_filter,
        "content_filter_label": content_filter_label,
        "collection_count": collection_count,
        "battle_profile": battle_profile,
        "recent_battles": recent_battles,
        "arena_battles": arena_battles,
        "arena_gift_display": arena_gift_display,
        "champion_badge": champion_badge,
        "chef_battle_enabled": chef_battle_enabled,
    }
    return render(request, "recipes/author_detail.html", context)


def _is_protected_author_action(author, user):
    linked_user = getattr(author, "user", None)
    if author.slug == settings.OWNER_SLUG:
        return True
    if author.user_id == getattr(user, "pk", None):
        return True
    # Superuser targets are protected from regular moderators, but not from other superusers
    if linked_user and linked_user.is_superuser and not getattr(user, "is_superuser", False):
        return True
    return False


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
        if action == "save_draft":
            recipe.status = Recipe.Status.DRAFT
        elif is_moderator(self.request.user) and action == "approve_publish":
            recipe.status = Recipe.Status.APPROVED
        elif author_skips_approval(self.author):
            recipe.status = Recipe.Status.APPROVED
        else:
            recipe.status = Recipe.Status.PENDING

        # If the author generated an AI hero image before saving, attach it now.
        temp_filename = self.request.POST.get("ai_hero_image_path", "").strip()
        if temp_filename and not self.request.FILES.get("hero_image"):
            from django.core.files.storage import default_storage
            if default_storage.exists(temp_filename):
                from django.core.files.base import ContentFile
                image_bytes = default_storage.open(temp_filename).read()
                import os
                ext = os.path.splitext(temp_filename)[1] or ".jpg"
                final_name = f"recipe_images/cover-draft{ext}"
                recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
                openai_model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
                recipe.image_rights_note = f"AI-generated image via {openai_model}."
                recipe.hero_image.save(final_name, ContentFile(image_bytes), save=False)
                # Clean up the temp file
                try:
                    default_storage.delete(temp_filename)
                except Exception:
                    pass

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
        _author = self.author
        _can_ai = bool(getattr(settings, "OPENAI_API_KEY", "")) and (
            is_moderator(self.request.user)
            or (_author and _author.can_generate_ai_images)
        )
        context["has_openai"] = _can_ai
        return context


@login_required
def recipe_create_from_screenshot(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author Profile Required. Please Connect This Account To An Author Profile First.")
        return redirect("home")

    if request.method == "POST":
        form = RecipeScreenshotUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["screenshot"]
            try:
                extraction = extract_recipe_from_image(uploaded, request.user)
                if "source_type" not in extraction:
                    extraction = normalise_extracted_recipe(extraction)
            except ScreenshotExtractionError as exc:
                messages.error(request, str(exc))
                return render(request, "recipes/create_from_screenshot.html", {"form": form, "author": author})

            uploaded.seek(0)
            temp_name = default_storage.save(f"recipe_screenshot_imports/{uuid.uuid4().hex}{Path(uploaded.name).suffix.lower() or '.png'}", uploaded)
            extraction["temp_screenshot_path"] = temp_name
            extraction["temp_screenshot_url"] = default_storage.url(temp_name)
            try:
                extraction.update(generate_reconstructed_hero_image(extraction))
            except Exception as exc:
                logger.warning("Screenshot image reconstruction failed: %s", exc, exc_info=True)
                messages.warning(
                    request,
                    "Recipe text was extracted, but the replacement image could not be generated. You can continue without it.",
                )
            token = uuid.uuid4().hex
            request.session.setdefault("recipe_screenshot_imports", {})
            request.session["recipe_screenshot_imports"][token] = extraction
            request.session.modified = True
            preview_form = RecipeScreenshotPreviewForm(initial=to_recipe_form_data(extraction))
            return render(
                request,
                "recipes/create_from_screenshot_preview.html",
                {
                    "author": author,
                    "screenshot_import": extraction,
                    "form": preview_form,
                    "upload_token": token,
                },
            )
    else:
        form = RecipeScreenshotUploadForm()

    return render(request, "recipes/create_from_screenshot.html", {"form": form, "author": author})


def _attach_generated_screenshot_hero(recipe: Recipe, extraction: dict) -> bool:
    temp_path = (extraction or {}).get("generated_hero_image_path", "")
    if not temp_path or not default_storage.exists(temp_path):
        return False

    try:
        with default_storage.open(temp_path, "rb") as image_file:
            image_bytes = image_file.read()
        ext = Path(temp_path).suffix or ".jpg"
        openai_model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
        recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
        recipe.image_rights_note = f"AI-generated image via {openai_model} from the uploaded recipe screenshot."
        recipe.hero_image.save(f"cover-screenshot{ext}", ContentFile(image_bytes), save=False)
        try:
            default_storage.delete(temp_path)
        except Exception:
            logger.warning("Could not delete temporary screenshot hero image %r", temp_path, exc_info=True)
        return True
    except Exception:
        logger.error("Could not attach generated screenshot hero image %r", temp_path, exc_info=True)
        return False


@login_required
def recipe_create_from_screenshot_confirm(request):
    author = get_author_for_user(request.user)
    if not author:
        messages.error(request, "Author Profile Required. Please Connect This Account To An Author Profile First.")
        return redirect("home")
    if request.method != "POST":
        return redirect("recipes:recipe_create_from_screenshot")

    token = request.POST.get("upload_token", "").strip()
    saved = request.session.get("recipe_screenshot_imports", {}).get(token)
    if not saved:
        messages.error(request, "Your screenshot preview expired. Please upload the image again.")
        return redirect("recipes:recipe_create_from_screenshot")

    form = RecipeScreenshotPreviewForm(request.POST)
    if not form.is_valid():
        preview_data = to_recipe_form_data(saved)
        preview_data.update(request.POST.dict())
        preview_form = RecipeScreenshotPreviewForm(request.POST)
        return render(
            request,
            "recipes/create_from_screenshot_preview.html",
            {
                "author": author,
                "screenshot_import": saved,
                "form": preview_form,
                "upload_token": token,
            },
        )

    recipe = form.save(commit=False, confirmed_by=request.user)
    recipe.author = author
    recipe.status = Recipe.Status.PENDING
    recipe.confirmed_own_work = False
    recipe.confirmed_image_rights = False
    recipe.confirmed_rules = False
    attached_generated_hero = _attach_generated_screenshot_hero(recipe, saved)
    if saved.get("generated_hero_image_path") and not attached_generated_hero:
        messages.warning(request, "The generated recipe image could not be attached. The recipe was submitted without it.")
    recipe.save()
    form.save_additional_categories(recipe)

    temp_path = saved.get("temp_screenshot_path")
    if temp_path and default_storage.exists(temp_path):
        try:
            default_storage.delete(temp_path)
        except Exception:
            pass
    request.session.get("recipe_screenshot_imports", {}).pop(token, None)
    request.session.modified = True
    messages.success(request, "Recipe submitted for review.")
    _send_recipe_notification(recipe, "pending")
    return redirect(recipe.get_absolute_url())


class RecipeUpdateView(AuthorRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeAuthoringForm
    template_name = "authoring/recipe_form.html"
    context_object_name = "recipe"

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Recipe.objects.all()
        return Recipe.objects.filter(author=self.author)

    def _battle_lock_redirect(self):
        """If this recipe is competing in a live battle, block the edit.

        A recipe entered in a running battle is frozen for its duration: the
        biathlon targets its ingredient lines by index and its approved status
        is what the audience votes on, so an edit would drift the indices and
        could drop the dish to a not-found for everyone but the author. Returns
        a redirect response to block on, or None to let the edit proceed.
        """
        from chef_battle.access import is_battle_visible
        from chef_battle.selectors import active_battle_locking_recipe
        recipe = self.get_object()
        battle = active_battle_locking_recipe(recipe)
        if battle is None:
            return None
        # F55, 2026-08-11: the lock itself is correct - an entered recipe
        # must stay frozen regardless of who is looking - but the message
        # named Chef Battles by name to EVERY author, including one on the
        # AUTHOR tier who is supposed to see nothing of the feature during
        # dark launch. Keep the block, neutralise the wording for anyone who
        # cannot see the Arena; staff/superusers (who can) still get the
        # real reason.
        if is_battle_visible(self.request):
            messages.error(
                self.request,
                "This recipe is in a live Chef Battle right now, so it is locked "
                "until the battle finishes. You can edit it again once the battle "
                "is over.",
            )
        else:
            messages.error(
                self.request,
                "This recipe can't be edited right now. Please try again later.",
            )
        return redirect(recipe.get_absolute_url())

    def get(self, request, *args, **kwargs):
        blocked = self._battle_lock_redirect()
        return blocked or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        blocked = self._battle_lock_redirect()
        return blocked or super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if not _validate_recipe_gallery_uploads(form, self.request.FILES):
            return self.form_invalid(form)
        action = _authoring_action(self.request)
        was_approved = self.object.status == Recipe.Status.APPROVED
        previous_status = self.object.status
        recipe = form.save(commit=False, confirmed_by=self.request.user)
        if is_moderator(self.request.user) and action == "approve_publish":
            recipe.status = Recipe.Status.APPROVED
        elif author_skips_approval(recipe.author):
            if action == "save_draft" and not was_approved:
                recipe.status = Recipe.Status.DRAFT
            else:
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
        elif (
            author_skips_approval(recipe.author)
            and previous_status != Recipe.Status.APPROVED
            and recipe.status == Recipe.Status.APPROVED
        ):
            messages.success(self.request, "Recipe approved and published.")
        elif previous_status in {Recipe.Status.DRAFT, Recipe.Status.NEEDS_CHANGES, Recipe.Status.REJECTED} and recipe.status == Recipe.Status.PENDING:
            messages.success(self.request, "Recipe submitted for review.")
            _send_recipe_notification(recipe, "pending")
        else:
            messages.success(self.request, "Recipe Updated Successfully.")
        next_url = self.request.POST.get("next") or self.request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return redirect(next_url)
        if (
            is_moderator(self.request.user)
            and action != "approve_publish"
            and not author_skips_approval(recipe.author)
        ):
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
        context["can_delete_own_profile"] = self.object.slug != settings.OWNER_SLUG
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
        context["can_admin_set_password"] = (
            _can_grant_bearseeker_privileges(self.request.user)
            and self.object.user is not None
        )
        return context


@require_POST
def moderation_author_set_password(request, slug):
    """Admin-only: manually set a new password for an author's account.

    The new password is emailed to the user automatically. Restricted to
    superusers and the site owner; protected accounts cannot be targeted.
    """
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    if not _can_grant_bearseeker_privileges(request.user):
        raise Http404
    author = get_object_or_404(RecipeAuthor.objects.select_related("user"), slug=slug)
    if _is_protected_author_action(author, request.user):
        raise Http404
    edit_url = reverse("recipes:moderation_author_edit", kwargs={"slug": author.slug})
    target = author.user
    if target is None:
        messages.error(request, "This author profile has no linked user account.")
        return redirect(edit_url)
    if not target.email:
        messages.error(request, "This user has no email address on file, so the new password cannot be sent.")
        return redirect(edit_url)
    password1 = request.POST.get("new_password1", "")
    password2 = request.POST.get("new_password2", "")
    if not password1 or password1 != password2:
        messages.error(request, "Passwords do not match.")
        return redirect(edit_url)
    try:
        validate_password(password1, user=target)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(edit_url)
    target.set_password(password1)
    target.save(update_fields=["password"])
    from monitoring.tracker import record_security_event
    record_security_event(request, "admin_password_set")
    try:
        send_template_mail(
            subject="Your CulinEire password has been updated",
            template="admin_password_set",
            context={
                "author_name": author.name or target.get_username(),
                "username": target.get_username(),
                "new_password": password1,
                "login_url": build_absolute_url(reverse("login")),
            },
            recipient_list=[target.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to email new password to user pk=%s", target.pk)
        messages.warning(
            request,
            f"Password for {target.get_username()} was changed, but the notification email could not be sent.",
        )
        return redirect(edit_url)
    messages.success(
        request,
        f"Password updated for {target.get_username()}. The new password was emailed to {target.email}.",
    )
    return redirect(edit_url)


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
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-created_at")
    )
    needs_changes_recipes = list(
        Recipe.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Recipe.Status.NEEDS_CHANGES, is_deleted=False)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-moderated_at", "-created_at")
    )
    rejected_recipes = list(
        Recipe.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Recipe.Status.REJECTED, is_deleted=False)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-created_at")
    )
    pending_articles = (
        Article.objects.select_related("author", "author__user")
        .filter(status=Article.Status.PENDING, is_deleted=False)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-published")
    )
    needs_changes_articles = (
        Article.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Article.Status.NEEDS_CHANGES, is_deleted=False)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-moderated_at", "-published")
    )
    rejected_articles = (
        Article.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Article.Status.REJECTED, is_deleted=False)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-published")
    )
    from pinch.models import Pinch

    pending_pinch = (
        Pinch.objects.select_related("author", "author__user")
        .filter(status=Pinch.Status.PENDING)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-created_at")
    )
    needs_changes_pinch = (
        Pinch.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Pinch.Status.NEEDS_CHANGES)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-moderated_at", "-created_at")
    )
    rejected_pinch = (
        Pinch.objects.select_related("author", "author__user", "moderated_by")
        .filter(status=Pinch.Status.REJECTED)
        .exclude(author__slug=settings.OWNER_SLUG)
        .order_by("-created_at")
    )
    protected_super_user_filter = Q(user__is_superuser=True) | Q(slug=settings.OWNER_SLUG)

    registered_authors = (
        RecipeAuthor.objects.select_related("user", "battle_profile")
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
    from sponsors.attention import get_sponsor_moderation_attention_breakdown, get_sponsor_moderation_attention_count

    # Forbidden claims flags (PDF v6 §30) — annotate each object directly
    try:
        from chef_battle.services import check_forbidden_claims
        for r in list(pending_recipes) + list(needs_changes_recipes):
            r.forbidden_claims_hits = check_forbidden_claims(" ".join(filter(None, [
                r.short_description, r.ingredients, r.method, r.tips, r.irish_context,
            ])))
        for a in list(pending_articles) + list(needs_changes_articles):
            a.forbidden_claims_hits = check_forbidden_claims(" ".join(filter(None, [a.excerpt, a.body])))
    except Exception:
        for r in list(pending_recipes) + list(needs_changes_recipes):
            r.forbidden_claims_hits = []
        for a in list(pending_articles) + list(needs_changes_articles):
            a.forbidden_claims_hits = []

    maintenance_flag = read_maintenance_flag()
    maintenance_web_active = maintenance_flag is not None and maintenance_flag.get("active", False)
    maintenance_until_str = maintenance_flag.get("until", "") if maintenance_flag else ""

    sponsor_attention_count = get_sponsor_moderation_attention_count()
    sponsor_attention_breakdown = get_sponsor_moderation_attention_breakdown()

    # F16, 2026-08-11: this panel is reached by is_moderator() alone, the
    # same class of gap as F8 - is_moderator() admits has_bearseeker_privileges
    # regardless of is_staff, so a general-site moderator without arena access
    # could see live Chef Battle clan and withdrawal queues before the dark
    # launch is public. The rest of the panel (recipes/articles/pinch) stays
    # open to every moderator; only the battle-specific sections are gated.
    from chef_battle.access import is_battle_visible
    pending_clans = []
    pending_withdrawals = []
    if is_battle_visible(request):
        from chef_battle.models import Clan

        pending_clans = list(
            Clan.objects.select_related("founder")
            .filter(moderation_status=Clan.Moderation.PENDING, is_active=True)
            .prefetch_related("categories")
            .order_by("-created_at")
        )

        # Withdrawal requests waiting for the final word (Owner's rule, 2026-08-05).
        # The chefs answer each other first; a moderator closes it either way.
        try:
            from chef_battle.models import BattleWithdrawal
            pending_withdrawals = list(
                BattleWithdrawal.objects
                .select_related("battle", "requester", "opponent")
                .filter(status=BattleWithdrawal.Status.AWAITING_MODERATOR)
                .order_by("created_at")
            )
        except Exception:
            pending_withdrawals = []

    return render(request, "moderation/panel.html", {
        "pending_clans": pending_clans,
        "pending_withdrawals": pending_withdrawals,
        "pending_recipes": pending_recipes,
        "needs_changes_recipes": needs_changes_recipes,
        "rejected_recipes": rejected_recipes,
        "pending_articles": pending_articles,
        "needs_changes_articles": needs_changes_articles,
        "rejected_articles": rejected_articles,
        "pending_pinch": pending_pinch,
        "needs_changes_pinch": needs_changes_pinch,
        "rejected_pinch": rejected_pinch,
        "registered_authors": registered_authors,
        "author_query": author_query,
        "can_grant_bearseeker_privileges": _can_grant_bearseeker_privileges(request.user),
        "can_grant_superuser_privileges": _can_grant_superuser_privileges(request.user),
        "can_revoke_superuser_privileges": _can_revoke_superuser_privileges(request.user),
        "can_view_site_update_plan": _can_view_site_update_plan(request.user),
        "bearseeker_super_users": bearseeker_super_users,
        "bearseeker_authors": bearseeker_authors,
        "maintenance_web_active": maintenance_web_active,
        "maintenance_until_str": maintenance_until_str,
        "maintenance_env_active": getattr(settings, "MAINTENANCE_MODE", False),
        "sponsor_attention_count": sponsor_attention_count,
        "sponsor_attention_breakdown": sponsor_attention_breakdown,
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
        custom_prompt = request.POST.get("custom_prompt", "").strip()

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
                kwargs = {"author_slug": author_slug, "status": status, "no_image": no_image, "dry_run": False, "limit": 0, "batch": None, "task_id": task_id, "category": category, "custom_prompt": custom_prompt}
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


def arena_master_console_plan(request):
    if not _can_grant_bearseeker_privileges(request.user):
        raise Http404

    plan_sections = []
    for section_id, title, filename in ARENA_MASTER_CONSOLE_PLAN_FILES:
        source = (ARENA_MASTER_CONSOLE_PLAN_DIR / filename).read_text(encoding="utf-8")
        plan_sections.append({
            "id": section_id,
            "title": title,
            "filename": filename,
            "source": source,
        })

    return render(
        request,
        "moderation/arena_master_console_plan.html",
        {"plan_sections": plan_sections},
    )


# Stages 1-13 are done and deployed. The board used to keep all 18 stages at
# equal size, which mixed history ("camera tilt — retired") with the work
# still open, and buried the seven that matter under eleven that don't.
# Collapsed here into one line; the source-of-truth stage dicts below are kept
# so nothing is lost, only folded out of the board's default view.
ARENA_ARCHIVE_STAGES = [
    {
        "n": 1, "id": "gate", "title": "Access gate & dark launch",
        "date": "2026-07-01",
        "backend": {"who": "Bolt", "done": True, "ref": "flag + is_battle_visible",
                    "task": "CHEF_BATTLE_ENABLED flag, is_battle_visible gate, staff/superuser preview"},
        "frontend": {"who": "GB", "done": True, "ref": "guarded views",
                     "task": "Arena hidden from the public until launch"},
        "depends": "Frontend depends on backend gate (is_battle_visible).",
    },
    {
        "n": 2, "id": "contracts", "title": "Read-model contracts",
        "date": "2026-07-15",
        "backend": {"who": "Bolt", "done": True, "ref": "selectors.py",
                    "task": "geometry, phase, deadline, spectators, blast, crown ladder, recent gifts"},
        "frontend": {"who": "GB", "done": True, "ref": "arena_deck.js",
                     "task": "Panels/deck consume the one poll payload"},
        "depends": "Frontend deck depends on backend payload keys.",
    },
    {
        "n": 3, "id": "renderer", "title": "Procedural renderer (SVG octagon)",
        "date": "2026-07-16",
        "backend": {"who": "Bolt", "done": True, "ref": "get_arena_geometry",
                    "task": "Declarative geometry: 8 rank rings + spectator rings, segment counts"},
        "frontend": {"who": "GB/Ember", "done": True, "ref": "arena_render.js",
                     "task": "Polar SVG grid drawn from the contract, no hardcoded rings"},
        "depends": "Frontend renderer depends on backend get_arena_geometry.",
    },
    {
        "n": 4, "id": "merge", "title": "Full arena merge (one arena)",
        "date": "2026-07-18", "version": "v2.5.321",
        "backend": {"who": "Bolt", "done": True, "ref": "master_console payload",
                    "task": "Master Console gets the full arena payload (geometry etc.)"},
        "frontend": {"who": "GB", "done": True, "ref": "?proto removed",
                     "task": "?proto gate removed, legacy renderer + sandbox deleted"},
        "depends": "Frontend legacy removal depends on backend AMC payload.",
    },
    {
        "n": 5, "id": "spectators", "title": "Real viewers are seen in the stands",
        "date": "2026-07-18",
        "backend": {"who": "Bolt", "done": True, "ref": "spectator_capacity()",
                    "task": "Online non-chef viewers, limited by the arena's own seat count "
                            "(544 across 8 rings since v2.5.337). Seat assignment is not in the "
                            "contract on purpose - where a face sits is presentation"},
        "frontend": {"who": "GB", "done": False, "ref": "overlay on the backdrop",
                     "task": "Draw REAL viewers over the backdrop, front rows first. The painted "
                             "crowd is part of the image now, so stand-ins must not be drawn on "
                             "top of it - only people who are actually online"},
        "depends": "Frontend overlay depends on the spectator payload (done).",
        "note": "This stage read '208 seats, rings 40/48/56/64' until 2026-07-20 - the contract "
                "it described had been replaced three days earlier and the board kept issuing "
                "orders against numbers that no longer existed. Worse, switching the SVG stands "
                "off under the backdrop took the real viewers with them: right now a logged-in "
                "visitor cannot see themselves in the arena at all.",
    },
    {
        "n": 6, "id": "skin", "title": "Dark amphitheatre skin (light floor, dark stands)",
        "date": "2026-07-18", "version": "v2.5.326",
        "backend": {"who": "Bolt", "done": True, "ref": "n/a",
                    "task": "No backend change (palette is scoped CSS)"},
        "frontend": {"who": "GB", "done": True, "ref": "arena_render.css",
                     "task": "Floor stays light parchment; dark moved into the spectator stands"},
        "depends": "Frontend only. Owner rule: floor light, dark = the stands.",
    },
    {
        "n": 7, "id": "spec", "title": "Mockup measurement spec",
        "date": "2026-07-19",
        "backend": {"who": "Bolt", "done": True, "ref": "n/a", "task": "No backend change"},
        "frontend": {"who": "GB", "done": True, "ref": "docs/chef_battle/arena_mockup_spec.md",
                     "task": "Measured mockup: 56 deg camera, floor 0.63 of frame, faces d~0.06R"},
        "depends": "Frontend research. Feeds stages 8-10.",
    },
    {
        "n": 8, "id": "perspective", "title": "Camera tilt — RETIRED by the owner",
        "date": "2026-07-20", "version": "v2.5.352",
        "backend": {"who": "Bolt", "done": True, "ref": "geometry stable",
                    "task": "Geometry contract stable; the camera was only ever a render transform"},
        "frontend": {"who": "GB", "done": True, "ref": "CONVERGENCE = 0",
                     "task": "Tilt built, then switched off on the owner's word: the arena is looked "
                             "at from straight above. Switched off by one number, not deleted"},
        "depends": "Closed. Depth of hall is out of scope while the view is a plan.",
        "note": "The tilt is NOT what made the mockup read as an arena — composition and content do, "
                "and both work from directly above. Reopen only if the owner asks for depth back.",
    },
    {
        "n": 9, "id": "proportions", "title": "Proportions (floor 0.63, stands 1.6R deep)",
        "date": "2026-07-19", "version": "v2.5.337",
        "backend": {"who": "Bolt", "done": True, "ref": "SPECTATOR_RING_SEGMENTS",
                    "task": "Stands went 4 rings -> 8 (40..96), 544 seats; the query limit is derived "
                            "from the geometry instead of a hardcoded 208. Verified live: 544 seats drawn"},
        "frontend": {"who": "GB", "done": True, "ref": "FLOOR_SHARE = 0.66",
                     "task": "One constant says how much of the frame width the floor takes. "
                             "Measured on prod 2026-07-20: 0.657 at both 1920 and 390"},
        "depends": "Frontend proportions DEPEND ON backend adding deeper spectator rings.",
    },
    {
        "n": 10, "id": "faces", "title": "Face framing (round portraits, depth)",
        "date": "2026-07-19", "version": "v2.5.338",
        "backend": {"who": "Bolt", "done": True, "ref": "avatar url in payload",
                    "task": "Spectator avatar_url already in payload; no backend change"},
        "frontend": {"who": "GB", "done": False, "ref": "arena-face-clip",
                     "task": "Round clip and size-by-depth SHIPPED (v2.5.338, faces 28-50px, "
                             "0.05-0.07R). Still missing the lighting half: measured 2026-07-19, "
                             "all 544 faces are opacity 1 / filter none, so the back rows are as "
                             "bright as the front and the depth does not read"},
        "depends": "Frontend only. Avatar data already provided.",
    },
    {
        "n": 11, "id": "crowd", "title": "Live avatars on the stands (544 seats)",
        "date": "2026-07-19", "version": "v2.5.340",
        "backend": {"who": "Bolt", "done": True, "ref": "spectator_capacity()",
                    "task": "Real spectators up to the arena's own seat count (now 544, derived "
                            "from the geometry); fillers take the remaining seats"},
        "frontend": {"who": "GB", "done": True, "ref": "crowdFaceFor + crowd webp",
                     "task": "All 544 seats occupied; a real viewer's avatar replaces the stand-in "
                             "when they are online. Stand-ins rebuilt for the dark hall (v2.5.340), "
                             "face contrast 12.0-14.3:1"},
        "depends": "Frontend fill depends on backend spectator payload (done).",
        "note": "Seats are full, but every face is a stand-in: 0 real spectators online. That is "
                "a traffic fact, not missing work - the arena is closed to everyone but "
                "staff/moderators until launch.",
    },
    # ── Stages 12+ come from the owner's decision of 2026-07-20 to stop building
    # the hall in code. Everything above assumed the whole arena was drawn by the
    # renderer; from here the scenery is a picture and the code owns only what
    # has to change while people watch.
    {
        "n": 12, "id": "backdrop", "title": "The hall becomes a picture, not code",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "n/a",
                    "task": "No backend change: the backdrop is an asset, the seating contract is untouched"},
        "frontend": {"who": "GB", "done": True, "ref": "placeBackdrop",
                     "task": "The hall image sits behind the floor and the raster is scaled to the "
                             "SVG rather than the other way round, so the picture follows the grid. "
                             "SVG stands are switched off under it, so the crowd is not drawn twice. "
                             "Live on prod as hall-bg-v3-final.webp; the eight corners of our "
                             "octagon land within 2% of the painted one"},
        "depends": "Frontend only. Owner: do not program the geometry of the stands.",
        "note": "The owner allowed 12 generated frames; 4 were spent. Frames 1 and 2 were drawn "
                "under a camera tilt that the owner then retired, frame 3 found the shape, frame 4 "
                "is the one in production. Eight are unused and no more are needed: the hall did "
                "not soften when the camera stepped back. Every paid frame is kept in "
                "shared/arena_frames.",
    },
    {
        "n": 13, "id": "projection", "title": "True perspective for the floor",
        "date": "2026-07-20", "version": "v2.5.349",
        "backend": {"who": "Bolt", "done": True, "ref": "geometry contract",
                    "task": "No backend change: the contract describes rings, the renderer projects them"},
        "frontend": {"who": "GB", "done": True, "ref": "arena_render.js",
                     "task": "The floor never had perspective - it was a tilted plane with both "
                             "edges the same length (ratio 1.00) while the mockup converges to 0.51. "
                             "Every ring vertex is now projected, convergence is one parameter"},
        "depends": "Frontend. Acceptance = the 8 corners of our octagon within 2% of the drawn one.",
        "note": "This is what makes the far rings smaller on their own, which is what the hand-tuned "
                "face sizes and brightness ladder were faking.",
    },
]

_ARCHIVE_DONE = sum(
    1 for s in ARENA_ARCHIVE_STAGES if s["backend"]["done"] and s["frontend"]["done"]
)
ARENA_ARCHIVE_SUMMARY = {
    "count": len(ARENA_ARCHIVE_STAGES),
    "done_count": _ARCHIVE_DONE,
    "span": "%s ... %s" % (ARENA_ARCHIVE_STAGES[0]["date"], ARENA_ARCHIVE_STAGES[-1]["date"]),
    "title": "Foundation of the arena, %d stages" % len(ARENA_ARCHIVE_STAGES),
}

# Live stages, renumbered from the closing of stage 13. Owner rule from the
# 2026-07-20 manifest review: every stage carries its own acceptance criterion
# so it cannot be swapped for a more convenient one partway through (this board
# had exactly that happen once, on the backdrop-alignment check).
ARENA_LEGACY_BUILD_STAGES = [
    {
        "n": 1, "id": "fullbleed", "title": "The arena fills the screen",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "n/a", "task": "No backend change"},
        "frontend": {"who": "GB", "done": True, "ref": "arena page shell",
                     "task": "Take the arena out of its boxed container - full-bleed, no border, "
                             "no rounded corner, no page margin. In the mockup the hall IS the screen"},
        "depends": "Frontend only.",
        "criterion": "Arena reaches the frame edge at 1920px and 390px. No horizontal scroll at either width.",
        "note": "CLOSED 2026-07-20, v2.5.377/378, confirmed live on prod by GB via the owner's START "
                "click: 1920 measures 1910x934, border/radius/margin 0, 8/8 corners within 2% (worst "
                "0.83%); 390 measures 390x344, the octagon itself does not overflow (arenaRight == "
                "clientWidth). The full-bleed rules used to sit entirely inside "
                "@media (min-width: 901px), so a phone kept the old boxed card with a border while "
                "desktop was already edge to edge — floor/stage/background sizing is now unconditional, "
                "only the floating panel overlay stays desktop-only (below 900px there's no room beside "
                "the floor to float them over it). GB also found and removed the leftover "
                "arena_render.css:373 perspective declaration (CONVERGENCE=0 zeroed the tilt numerically "
                "but the 3D context was still declared) — v2.5.376. "
                "A separate 8px document overflow at 390 (scrollWidth 406 vs clientWidth 390) is NOT "
                "the arena: GB traced it to .ce-author-panel__menu in the site header holding "
                "display:grid with no [open] condition, so the closed profile-menu <details> still "
                "occupies layout space. Shared file (base.css/header), not GB's or Bolt's alone — "
                "whoever picks it up next should search for that selector.",
    },
    {
        "n": 2, "id": "spectators", "title": "Real viewers are seen in the stands",
        "date": "2026-07-18",
        "backend": {"who": "Bolt", "done": True, "ref": "spectator_capacity()",
                    "task": "Online non-chef viewers, limited by the arena's own seat count "
                            "(544 across 8 rings since v2.5.337). Seat assignment is not in the "
                            "contract on purpose - where a face sits is presentation"},
        "frontend": {"who": "GB", "done": False, "ref": "overlay on the backdrop",
                     "task": "Draw REAL viewers over the backdrop, front rows first. The painted "
                             "crowd is part of the image now, so stand-ins must not be drawn on "
                             "top of it - only people who are actually online"},
        "depends": "Frontend overlay depends on the spectator payload (done).",
        "criterion": "A logged-in visitor sees themselves seated in the stands. 8 rings, 544 seats total.",
        "note": "The painted crowd took the real viewers with it when the SVG stands were switched "
                "off under the backdrop: right now a logged-in visitor cannot see themselves in the "
                "arena at all.",
    },
    {
        "n": 3, "id": "hud", "title": "HUD frames the arena instead of sitting under it",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "existing payload",
                    "task": "Phase, counters, ladder and gifts are already in the poll payload"},
        "frontend": {"who": "GB/Bolt", "done": True, "ref": "absolute panels",
                     "task": "Title top-left, phase panel under it, phase rail top-centre, counters "
                             "top-right, crown ladder bottom-left, gifts bottom-right, supporter "
                             "ticker along the bottom. Dark glass, backdrop-filter, bronze edge"},
        "depends": "Frontend. Bolt owns the panel styling in arena_hall.css, GB the placement.",
        "criterion": "Title top-left, phase rail top-centre, counters top-right, crown ladder "
                     "bottom-left, gifts bottom-right — all present and positioned, not stacked below the arena.",
        "note": "VERIFIED 2026-07-20 by measuring each panel's getBoundingClientRect at 1920px: header "
                "(38,214), phase-card (38,360), metrics (1471,214), ladder (38,803), gifts (1471,747), "
                "phase-rail (535,172), crowd-rail (420,927) — left column ~2%, right column ~77%, top "
                "and bottom rails centred, matching the coded left/top percentages exactly. This stage "
                "was marked not-done from a stale board read; it was already built and working.",
    },
    {
        "n": 4, "id": "fighters", "title": "The two chefs flank the crown",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "_arena_center()",
                    "task": "Challenger and opponent with name and photo in the centre payload"},
        "frontend": {"who": "GB", "done": False, "ref": "centre panels",
                     "task": "Coloured panels either side of the crown - challenger green, opponent "
                             "red - each with photo, name and flag, as drawn in the mockup"},
        "depends": "Frontend only now - the payload shape already exists.",
        "criterion": "Challenger panel green on the left, opponent panel red on the right "
                     "(manifest section 4 — the one manifest rule still live for the arena).",
        "note": "RECHECKED 2026-07-20: chef_battle/views.py _arena_center() already returns "
                "challenger.name/avatar_url and opponent.name/avatar_url whenever an active_battle "
                "or facing_pair exists - this was reported as 'no backend data' but the shape has "
                "existed since before this session. Which side is green/red is structural (challenger "
                "vs opponent), not something the backend needs to add. 'country' was in the original "
                "task text but RecipeAuthor has no country field anywhere in the schema - not adding "
                "one silently; that is a real new field needing its own decision, not a byproduct of "
                "this stage. The mockup's flag/photo panel can be built now against name+avatar_url; "
                "there is simply no active_battle in prod right now to exercise it against, which is a "
                "data-state gap (no live battle), not a missing capability.",
    },
    {
        "n": 5, "id": "ranklabels", "title": "The rank column lies on the floor",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "ring keys", "task": "Ring keys already published"},
        "frontend": {"who": "GB", "done": False, "ref": "overlay column",
                     "task": "KITCHEN PORTER down to CULINARY MASTER as a column of pills over the "
                             "centre of the floor, the way the mockup places it"},
        "depends": "Frontend only.",
        "criterion": "Rank column readable over the light floor: contrast ratio measured >= 7:1, "
                     "reported as a number, not eyeballed.",
    },
    {
        "n": 6, "id": "tokens", "title": "Raw colours become design tokens",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": True, "ref": "n/a", "task": "No backend change"},
        "frontend": {"who": "GB", "done": False, "ref": "arena*.css / arena*.js",
                     "task": "183 raw hex literals across the arena stylesheets replaced with the "
                             "nearest existing :root token from base.css. No shade is invented and "
                             "the owner is not asked - nearest existing token wins"},
        "depends": "Frontend only. CLAUDE_RULES section 3: zero tolerance for raw hex.",
        "criterion": "grep -c for a hex literal returns 0 across every arena.css / arena_render.css / "
                     "arena_hall.css / arena_command_deck.css / arena_deck_polish.css / "
                     "arena_master_console*.css / arena_octant_prototype.js file.",
        "note": "The original 183 count included matches inside comments describing already-removed "
                "palettes (grep does not parse CSS syntax) — the real, live count was 89. Fixed "
                "2026-07-20: arena.css, arena_hall.css, arena_render.css, arena_command_deck.css down "
                "to 0-6 each; arena_master_console.css and arena_deck_polish.css's remaining hex are "
                "each file's OWN local token declaration site (same category as :root itself), not "
                "scattered decorative colour. 35 hex remain: 6 in arena.css + 3 in arena_deck_polish.css "
                "are documented semantic exceptions (green='online', red='LIVE', blue=DEF — no green/"
                "red/blue token exists anywhere in :root, and color-mix cannot synthesize a hue outside "
                "the two colours it mixes); 7 in arena_master_console.css are its own declared palette; "
                "arena_master_console_plan.css (17) and arena_octant_prototype.js (2) not yet touched.",
    },
    {
        "n": 7, "id": "integrity", "title": "Vote integrity holds without the service layer",
        "date": "2026-07-20", "version": "v2.5.376",
        "backend": {"who": "Bolt", "done": True, "ref": "CheckConstraint + HMAC",
                    "task": "Self-vote now blocked by a database CheckConstraint, not only "
                            "BattleVote.clean() (which save() never calls). Request hashes moved "
                            "from a bare SHA-256 to HMAC keyed on SECRET_KEY"},
        "frontend": {"who": "GB", "done": True, "ref": "n/a", "task": "No frontend change"},
        "depends": "Closed both lanes. Found during the manifest review, not assigned by the owner.",
        "criterion": "Writing a self-vote straight through .save() raises IntegrityError. "
                     "New vote rows carry hash_scheme=v2.",
    },
]

# Frozen by the owner until the stages above go green. Kept visible so the
# work is not forgotten, but without a START button — pressing it here would
# violate the freeze the same way building it would.
ARENA_LEGACY_LATER_STAGES = [
    {
        "n": 8, "id": "mobile", "title": "Mobile arena is its own scene",
        "date": "2026-07-20",
        "backend": {"who": "Bolt", "done": False, "ref": "ring rosters",
                    "task": "Chefs grouped per rank ring for the tap-through list"},
        "frontend": {"who": "GB", "done": False, "ref": "mobile layout",
                     "task": "Floor large, rings as arcs, crowd as a band; tapping a ring opens the "
                             "list of that rank's chefs"},
        "depends": "Frontend list depends on backend serving chefs grouped by ring.",
        "criterion": "A rank ring is tappable at 390px width and opens that rank's chef list.",
        "note": "Owner's decision 2026-07-20, and it is not a style choice: at 390px an outer-ring "
                "tile is about 34px wide and 8px tall once the floor is foreshortened. Nobody can "
                "tap that, and the tile is how a chef's card is opened. Start only after the "
                "desktop backdrop is accepted - two moving floors at once is how we lose a day.",
    },
]

ARENA_DESIGN_TASKS = [
    {
        "id": "A00", "group": "Arena Hall", "title": "Reference authority and immutable constraints",
        "status": "DONE", "owner": "Ember",
        "files": "docs/ARENA_BATTLE_PLAN.md; Deployment Project reference files (read-only)",
        "depends_on": "None",
        "action": "Pin the approved mockup/build and the Owner overrides as the only implementation authority.",
        "visible_result": "No visual change; every later ticket uses one conflict-free contract.",
        "acceptance": "Plan states site gold palette; floor colours, octagon method and rotateX(42deg) frozen; mechanisms/effects retained; no K banner; Master Console excluded.",
        "forbidden": "Do not copy stale 58deg camera or stale palette prohibitions from the archived handoff.",
        "evidence": "Owner decisions and Deployment Project INDEX/README reconciled.",
    },
    {
        "id": "A01", "group": "Arena Hall", "title": "Recovered live scene baseline",
        "status": "DONE", "owner": "Ember + GreenBear",
        "files": "static/js/arena_render.js; static/css/arena_atmosphere.css; templates/chef_battle/arena.html",
        "depends_on": "A00",
        "action": "Connect the spectator oval, remove the leaked comment and reveal existing empty stands.",
        "visible_result": "The real 290-seat oval and existing stand layer render.",
        "acceptance": "One authoritative viewer count; no hidden stand layer; anonymous Arena remains 404.",
        "forbidden": "No synthetic interactive users and no seat-contract rewrite.",
        "evidence": "DONE v2.5.676-v2.5.678.",
    },
    {
        "id": "A02", "group": "Arena Hall", "title": "Chef identity inside existing floor plinths",
        "status": "DONE", "owner": "Ember",
        "files": "chef_battle/views.py; static/js/arena_render.js; static/css/arena_render.css",
        "depends_on": "A01",
        "action": "Render chef name plus static Irish flag/country inside each existing active fighter plinth.",
        "visible_result": "Active fighters identify themselves inside their octagons.",
        "acceptance": "Irish flag/country only; no separate support panel; existing battle selection preserved.",
        "forbidden": "No invented country source and no new fighter engine.",
        "evidence": "DONE v2.5.682.",
    },
    {
        "id": "A03", "group": "Arena Hall", "title": "Rank spine order and approved plinth shape",
        "status": "DONE", "owner": "Ember",
        "files": "static/css/arena_deck_polish.css; templates/chef_battle/arena.html",
        "depends_on": "A01",
        "action": "Order the eight ranks outer-to-centre and restore the bevelled brass-edged labels.",
        "visible_result": "Kitchen Porter starts at the far edge; Culinary Master finishes by the centre.",
        "acceptance": "All eight labels visible in the approved order and silhouette.",
        "forbidden": "Do not alter floor cells, rank data or camera.",
        "evidence": "DONE v2.5.684-v2.5.685; non-interactive plinth correction v2.5.695.",
    },
    {
        "id": "A04", "group": "Arena Hall", "title": "Cell click ripple and chef-card anchoring",
        "status": "DONE", "owner": "Ember",
        "files": "static/js/arena_render.js; static/css/arena.css; templates/chef_battle/_arena_render_ring.html",
        "depends_on": "A01",
        "action": "Anchor the ripple in SVG user space and the chef card beside any clicked cell in viewport space.",
        "visible_result": "Click feedback stays in the cell; the chef card opens next to that cell.",
        "acceptance": "Works on every ring; card flips above near the bottom and stays inside screen edges.",
        "forbidden": "No per-cell special cases and no change to profile/challenge behaviour.",
        "evidence": "DONE v2.5.687 and v2.5.691; close control v2.5.695.",
    },
    {
        "id": "A05", "group": "Arena Hall", "title": "Broadcast ribbon, phase rail, metrics and identity",
        "status": "DONE", "owner": "Ember",
        "files": "static/css/arena_command_deck.css; static/css/arena_deck_polish.css; templates/chef_battle/arena.html",
        "depends_on": "A00",
        "action": "Separate the identity and phase rail, compact four metrics into one row and restore readable identity contrast.",
        "visible_result": "One-row phase stepper and compact top-right signal strip match the reference hierarchy.",
        "acceptance": "Seven phases never overlap the identity; metrics remain server-updated; site tokens only.",
        "forbidden": "No phase inference and no payload rewrite.",
        "evidence": "DONE v2.5.689-v2.5.692; complete independent Cooking Widget corrected v2.5.699-v2.5.703.",
    },
    {
        "id": "A06", "group": "Arena Hall", "title": "Fresh production/reference measurement matrix",
        "status": "DONE", "owner": "GreenBear",
        "files": "docs/ARENA_BATTLE_PLAN.md; new evidence under ops/audits/arena/",
        "depends_on": "A05",
        "action": "Capture authenticated production and Design Arena at 1280x720 and 1920x1080 and record bounding boxes for every required furniture block.",
        "visible_result": "No production change; exact remaining deltas replace guesswork.",
        "acceptance": "Side-by-side images plus measurements for floor, crowd, rank spine, fighters, crown, four panels and ticker.",
        "forbidden": "Read-only ticket: no CSS, JS, template, database or production mutation.",
        "evidence": "DONE 2026-08-04, both columns and both viewports: ops/audits/arena/A06_remeasure_2026-08-04.md with raw JSON under ops/audits/arena/evidence/. Reference measured twice independently (Bolt and the audit branch), readings agreeing to the decimal - floor grid 1585.4x667.5, outer band 1675x699, crown 190x168 at (865,648). Production measured live at 1920x1080 and 1280x720 under a superuser session the Owner opened, read-only. The reference does NOT respond to the viewport: a fixed 1920 composition that overflows rather than reflows, a different layout model from production and recorded as such. The 2026-07-29 matrix keeps its SUPERSEDED banner - it cited the rejected prototype. The side-by-side comparison is two SVGs generated from the measured rectangles, both panes at one scale. NO screenshots are stored: the Owner ruled on 2026-08-04 that a screenshot is a single-use diagnostic and junk once read, and 14 stored ones (6.87 MB) were deleted from ops/audits/ in the same release.",
    },
    {
        "id": "AR1", "group": "Arena Hall", "title": "Eleven-ring octagon geometry",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/js/arena_render.js; templates/chef_battle/_arena_render_ring.html; chef_battle/tests.py",
        "depends_on": "A06",
        "action": "Emit eleven rings instead of eight: ring 1 Crown Holder, ring 2 Moat, rings 3-10 the eight ranks Culinary Master->Kitchen Porter, ring 11 VIP Guests.",
        "visible_result": "The floor draws eleven concentric rings in the approved order.",
        "acceptance": "Ring data-ring/data-ring-kind emitted 1..11 in order; camera rotateX(42deg) unchanged; real seat data preserved; ARENA_BATTLE_PLAN §2 v2.",
        "forbidden": "No fake occupants; no camera/perspective change; no raw hex (tokens only).",
        "evidence": "DONE v2.5.709-v2.5.710. Own arenaRingTable() replaces the borrowed Sponsors six-ring grid: Crown 1, Moat 2, ranks 3-10 (184 cells, counts from backend RANK_RING_SEGMENTS), VIP 11. Verified live: rank 184 / moat 8 / vip 8 / spectator 290 intact.",
    },
    {
        "id": "AR2", "group": "Arena Hall", "title": "Eleven-ring palette tokens",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_render.css",
        "depends_on": "AR1",
        "action": "Paint all eleven rings from the Owner palette as tokens: centre #52422E, ranks gradient to #EEE1CA, VIP rim #535252; missing steps interpolated logically.",
        "visible_result": "Each ring carries its approved tone.",
        "acceptance": "Tokens only, no raw hex in rules; matches ARENA_BATTLE_PLAN §2 v2 table.",
        "forbidden": "No scattered raw colour literals.",
        "evidence": "DONE. Floor palette shipped v2.5.704-707 (Owner reference ramp, 8 tones); moat + VIP tokens v2.5.709-722; --ink neutralised sitewide v2.5.728. Owner 2026-07-30: colours are settled, do not touch.",
    },
    {
        "id": "AR3", "group": "Arena Hall", "title": "Moat ring (ring 2) with lanterns",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_render.css; static/css/arena_atmosphere.css; static/js/arena_render.js",
        "depends_on": "AR1",
        "action": "Ring 2 shows no visible cells (border:0); a glowing lantern sits at each cell centre and casts glints onto the gold Crown ring.",
        "visible_result": "A dark lantern-lit moat separates the Crown from the ranks.",
        "acceptance": "No cell borders on ring 2; lantern glints read on the gold ring; tokens only.",
        "forbidden": "No occupants on the moat; no camera change.",
        "evidence": "DONE v2.5.736. Eight lanterns at the moat cell centres, each breathing on its own clock; glow reuses the existing gold token and throws a glint onto the Crown plate. Verified live: 8 lanterns, moat still borderless, 184 rank / 32 VIP intact.",
    },
    {
        "id": "AR4", "group": "Arena Hall", "title": "Author seat rows (two top, two bottom)",
        "status": "DONE", "owner": "Bolt",
        "files": "static/js/arena_render.js; static/js/arena_geometry.js; chef_battle/selectors.py; chef_battle/arena_seating.py; chef_battle/tests.py",
        "depends_on": "AR1",
        "action": "Real interactive seats belong to authors (authorised non-chef users): two rows top and two bottom, front rows first, logged-in self-seating.",
        "visible_result": "Authors seat themselves around the floor; front rows fill first.",
        "acceptance": "Real users only; front-rows-first; no synthetic occupants; ARENA_BATTLE_PLAN §2a.",
        "forbidden": "No synthetic/impersonating occupants; no seat identity for spirits.",
        "evidence": "DONE v2.5.769. Left and right seat banks removed; capacity derived 290 -> 114 (top 28+29, bottom 28+29). Ring ids 100/101/120/121 and their arcs unchanged, so nobody seated top or bottom is moved. Seats the geometry no longer declares are released on the read path and on claim, ahead of the idempotency shortcut. Eligibility (author, not an enrolled chef), front-rows-first order and the one-seat-per-person constraint were already correct and were not touched. 21 focused PostgreSQL tests green.",
    },
    {
        "id": "AR5", "group": "Arena Hall", "title": "Spirit balconies + VIP sponsor ring",
        "status": "DONE", "owner": "GreenBear + Bolt",
        "files": "chef_battle/selectors.py; chef_battle/views.py; static/js/arena_render.js; static/css/arena_render.css; chef_battle/tests.py",
        "depends_on": "AR4",
        "action": "Unauthorised users appear as bodiless spirits in the balconies behind the author rows; ring 11 VIP seats are reserved for sponsors.",
        "visible_result": "Balcony spirits behind the seats; VIP ring reads as sponsor seating.",
        "acceptance": "Spirits never impersonate real/online users and hold no seat identity; VIP ring styled per §2a.",
        "forbidden": "No spirit impersonation of real users.",
        "evidence": "DONE. VIP ring shipped v2.5.765-768 (GreenBear): published cells only, logo by the chef-avatar rule, clickable boxes, sponsor card with a Visit link. Spirit balconies shipped v2.5.778 (Bolt): stands behind both author rows, derived capacity, live count of unauthorised lobby visitors read from the existing BattleViewerPresence heartbeat - no second presence system. A stand carries no ring, no cell and no seat-map entry, so nothing can be seated there; the renderer draws the stands once and bind() lights the count on every poll. Expect ZERO spirits on production until the Arena opens - an anonymous visitor 404s before the lobby heartbeat runs - and no placeholder crowd was substituted. 576 chef_battle tests green.",
    },
    {
        "id": "A07", "group": "Arena Hall", "title": "Stage framing and full-octagon composition",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_command_deck.css; static/js/arena_render.js; templates/chef_battle/arena.html cache key",
        "depends_on": "AR5",
        "action": "The arena fits the screen whole, on every screen (Owner, 2026-08-05).",
        "visible_result": "Nothing of the arena sits below the fold: the crowd rail, its last element, ends exactly at the viewport bottom.",
        "acceptance": "Deck height is the space under the header at any width; rotateX stays 42deg; floor colours and the octagon renderer unchanged; no media query added.",
        "forbidden": "No geometry-engine rewrite, perspective/camera change or floor recolour.",
        "evidence": "v2.5.812. THE WHOLE CARD WAS ONE MULTIPLIER. arena_command_deck.css read `height: calc((100svh - var(--arena-header-h, 146px)) * 1.28)` with `min-height: 42rem`, and its own comment said why: grow the stage PAST one viewport so the octagon and oval stay large, and let the page scroll rather than clip. The Owner reversed that trade, so the 1.28 and the 42rem floor are gone - a minimum taller than a short screen is the same overflow under another name. Measured live on production, same viewport 2133x958, before -> after: deck bottom 1187 -> 959, crowd rail bottom 1186 -> 958 against a 958 viewport, page scrollHeight 1571 -> 1344 with the remaining 385 being the site footer. The cost is real and is the trade he chose: the octagon goes 848.3x664.8 -> 670.6x519.6, about 21 percent narrower. TWO THINGS FOUND ON THE WAY, both measured on the live page rather than read off the source. The camera is NOT owned by arena_render.css: arena_deck_polish.css:3666 sets it last, and two blocks above it (1912, 2277) drop rotateX entirely. The container height is not owned by arena_render.css either - its `clamp(480px, 56vw, 94vh)` loses to `height: auto` from arena_atmosphere.css at higher specificity, and the container is absolute with top/bottom 0, so it simply fills its grid cell. Also fixed: --arena-header-h was never set by anything, so the subtraction ran on a 146px fallback that is only true of the desktop header; arena_render.js measures the header now and re-fits when it changes. NOT VERIFIED IN THIS SESSION: narrow-viewport behaviour. The browser would not resize below the desktop window, so the claim for phones rests on the units (svh, and a measured header) and not on a measurement.",
    },
    {
        "id": "A08", "group": "Arena Hall", "title": "Crowd bowl depth and atmospheric population",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_atmosphere.css; static/css/arena_render.css; approved crowd assets only",
        "depends_on": "A06",
        "action": "Complete the dark crowd bowl and atmospheric depth around the separate real 290-seat layer.",
        "visible_result": "Stands read as a dense hall around the lit floor rather than a pale dot ring.",
        "acceptance": "Real seats remain honest and clickable; atmospheric figures cannot impersonate users; centre stays clear.",
        "forbidden": "No fake interactive occupants, no seat-contract change and no removal of approved effects.",
        "evidence": "DONE v2.5.775-779. Depth: --row-light was computed per row and discarded by `filter: none !important` on every cell in arena_atmosphere.css, so the fall-off moved into the fill; stands went #656463 to #292929, near row now 11.5% brighter than far, stands 4x darker than the lit floor. Population: 172 atmospheric figures in three rows BEHIND the outermost real seat row, top and bottom only - 0 in seat groups, no slug, no pointer events, honouring the 2026-07-27 order that stopped faces in empty seats. 114 real seats intact.",
    },
    {
        "id": "A09", "group": "Arena Hall", "title": "Live challenger/opponent composition",
        "status": "DONE", "owner": "Bolt + GreenBear",
        "files": "templates/chef_battle/arena.html; static/js/arena_render.js; scoped fighter CSS",
        "depends_on": "A07",
        "action": "Two stages, not one — ARENA_BATTLE_PLAN section 2b. (a) ON CHALLENGE ACCEPT the two chefs approach each other INSIDE their own rank rings: same rank, opposite cells of that ring; different ranks, a vertically aligned pair across the two rings. They do not reach the centre yet. (b) AT BATTLE TIME both leave the ring for the two placeholders beside the centre, at the measured offset, and stay for the duration; the centre carries VS and the link to the separate battle page. On completion both return to their ring cells.",
        "visible_result": "Challenger is left/green and opponent right/red around the live centre.",
        "acceptance": "Real server-selected chefs only; identity remains inside each plinth; empty/crown-only states remain truthful; a chef vacates his ring cell ONLY at battle time, never on challenge accept; the centre link goes to the battle page. Verify in the moderator preview /chef-battle/arena/?demo=vs, which is stable since v2.5.816.",
        "forbidden": "No demo fighter injection, backend selection rewrite or separate support panel.",
        "evidence": "CLOSED IN TWO HALVES BY TWO AGENTS, AND THE SECOND HALF WAS BUILT TWICE. (a) THE APPROACH: Bolt shipped it as scenario A in v2.5.844 straight from the Owner's words - a pair bound by an accepted challenge is seated first and together, same ring adjacent, different ranks one directly outside the other, and the scatter works around them. I had written the same stage independently the same hour and DROPPED MY VERSION on the rebase rather than argue two implementations of one rule into the same file (section 7, existing-code-first). His is the one that stands. (b) A FIGHTER IS NEVER FILTERED OUT OF HIS OWN BATTLE, v2.5.847: the ring payload kept only chefs inside the 180-second heartbeat window, so a chef who closed the tab vanished from the floor MID-BOUT and his battle ran with an empty ring - the one thing the arena exists to show (2b: so they can see each other). Being in an active battle is now itself enough to hold a cell. Three tests hold it, including the case that the floor still empties when the battle finishes. STILL OPEN AND IT IS THE OWNER'S: the MOVE itself. Emulation step 2 asks for the pair to WALK to the centre rather than jump, and what that looks like - how long, what path, what happens to the cell they leave - is his to say, not an agent's.",
    },
    {
        "id": "A10", "group": "Arena Hall", "title": "Crown-holder hub composition",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_deck_polish.css; existing crown assets",
        "depends_on": "A07",
        "action": "Match the central crown hub size, recess, label hierarchy and spacing below the rank spine.",
        "visible_result": "The crown holder becomes the visual centre without covering ranks or fighters.",
        "acceptance": "Existing crown data/assets and reduced-motion behaviour retained.",
        "forbidden": "Do not replace the crown mechanism or remove the crown light/effects.",
        "evidence": "DONE across v2.5.853, .855 and .857. SIZE: the hub was 0.159 of the floor against the reference 0.1198 - a third too wide - and is 0.1202 now, measured on production. RECESS: done by drawing the hub smaller inside its plate rather than by moving CROWN_OUTER, which is the inner edge of the moat and the base of rankStep, so no rank ring moved. LABEL HIERARCHY: the glyph was 0.31 of the block against the reference 0.274 and is 0.547 of the radius now; the CROWN HOLDER label (0.050 against 0.047) and the fitted name (0.120 against 0.116) were already inside measurement noise and were left alone. SPACING BELOW THE RANK SPINE: two rank titles lay across the hub. On the Owner s instruction of 2026-08-07 the ladder was moved to where the mockup has it - a compact stack above the floor, 201px instead of 449, no title within 62px of the hub. Current crown layer exists; final reference comparison pending.",
    },
    {
        "id": "A11", "group": "Arena furniture", "title": "Phase panel reference pass",
        "status": "DONE", "owner": "Bolt",
        "files": "templates/chef_battle/arena.html; static/js/arena_deck.js; scoped panel CSS",
        "depends_on": "A06",
        "action": "Align phase title, authoritative countdown, progress, centre/viewer facts and next-phase copy to the reference panel.",
        "visible_result": "Top-left phase panel is compact, legible and complete.",
        "acceptance": "Server drives phase/deadline; loading and missing-deadline states remain valid.",
        "forbidden": "No client phase inference or fixture countdown.",
        "evidence": "DONE v2.5.784. The panel's prominent clock was the 30s PAGE-REFRESH countdown, sitting in the reference panel's clock position and counting the poll rather than the phase; the authoritative server deadline existed, reconciled clock skew against server_time, and was display:none on desktop. The deadline is MOVED (not copied - one id) into the phase header and unhidden; the refresh countdown is kept, demoted to the gauge it measures and labelled \"Refreshing in\". Empty state is quiet: no battle running reads as calm, not as a fault. Copy and duplicate viewer facts stay hidden - the reference panel has neither. Before, at 1280: panel 248x245.6 vs reference 230x123 (A06). Server still owns phase and deadline; no client inference, no fixture countdown. Five focused tests pin the arrangement.",
    },
    {
        "id": "A12", "group": "Arena furniture", "title": "Crown ladder panel reference pass",
        "status": "DONE", "owner": "Bolt",
        "files": "static/css/arena_deck_polish.css; existing ladder template markup",
        "depends_on": "A06",
        "action": "Match top-four row density, crown counts, panel position and View Full Ladder action.",
        "visible_result": "Bottom-left ladder matches the approved furniture hierarchy.",
        "acceptance": "Existing links/data remain live; four rows fit without truncation at 1280 and 1920.",
        "forbidden": "No fake rankings and no ranking-query rewrite.",
        "evidence": "DONE v2.5.810 (Bolt). Rows were a flex line divided by a border, so the name column decided the widths and the crown counts on the right never lined up with each other. Now a three-column grid - 1.35rem badge, flexible name, auto count - so every count sits on one axis whether it reads 1 or 12; rows separated by space on a faint accent ground with a 9px corner, leader's row a shade stronger, as the reference marks first place by weight rather than a second colour. The count reads as a count: the existing #ad-crown symbol plus the number in the accent, tabular, with the word carried to a screen reader by aria-label instead of set in caption type. View Full Ladder stays the site's own btn-secondary, full width and centred - no pill invented for this panel. The empty state keeps the panel's shape. FORBIDDEN CHANGES AVOIDED: get_crown_ladder is untouched - real crowns awarded today, ordered by count, limit 8 - and a test pins that. Scoped .page--arena rather than !important, which is the trap this file's own header describes.",
    },
    {
        "id": "A13", "group": "Arena furniture", "title": "Recent gifts panel reference pass",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_deck_polish.css; existing gifts template markup",
        "depends_on": "A06",
        "action": "Match the three gift rows, token amounts, panel position and Send a Gift action.",
        "visible_result": "Bottom-right gifts furniture matches the reference.",
        "acceptance": "Existing gift data/action retained; empty state remains truthful.",
        "forbidden": "No fake transactions or gift-mechanism rewrite.",
        "evidence": "DONE v2.5.859, measured against the Design Template. Reference: recent gifts 330 x 223 at (1562,761) on its 1920x1080 canvas = x 0.814 y 0.705 w 0.172 h 0.207. Production was x 0.821 y 0.640 w 0.166 h 0.269 - position and width already inside one per cent, height 30 per cent over. The excess was one paragraph the reference has no equivalent for: an explanatory note about the shop and the token checks, written for us rather than for a spectator. Hidden rather than deleted. Verified on production after deploy: 0.701 / 0.208 against the reference 0.705 / 0.207.",
    },
    {
        "id": "A14", "group": "Arena furniture", "title": "Bottom ticker and Join the Crowd composition",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_deck_polish.css; existing crowd-rail markup",
        "depends_on": "A06",
        "action": "Compose top supporter, live messages and Join the Crowd into the reference bottom-centre strip.",
        "visible_result": "One unobstructed ticker sits between the two lower corner panels.",
        "acceptance": "Existing actions/data preserved; no footer overlap at supported viewports.",
        "forbidden": "No fabricated supporter identity and no spectator-control rewrite.",
        "evidence": "DONE v2.5.859. Reference bottom band 1076.5 x 52 at (421.7,1004) = x 0.220 y 0.930 w 0.561 h 0.048. Production ran edge to edge: x 0.001 w 0.999. The rail keeps its full-width backdrop - that is the floor's own edge and the reference has one too - and the content is bounded to the middle 56.07 per cent by padding rather than a wrapper div, because the three children are the markup's own. Vertical position was already right (0.926 against 0.930) and is untouched. Verified on production: content x 0.221 w 0.559 against the target 0.220 / 0.561.",
    },
    {
        "id": "A15", "group": "Arena Hall", "title": "Effects and artifacts preservation pass",
        "status": "DONE", "owner": "GreenBear",
        "files": "static/css/arena_effects.css; static/css/arena_atmosphere.css; existing effect JS/assets",
        "depends_on": "A07, A08, A09, A10",
        "action": "Verify dust, gifts, light rays, lamp shimmer and crown light remain correctly layered after composition work.",
        "visible_result": "Approved atmosphere survives without obscuring interaction or furniture.",
        "acceptance": "Effects visible where designed; reduced motion respected; no new dead keys.",
        "forbidden": "Do not remove these effects and do not touch Master Console.",
        "evidence": "DONE - VERIFICATION, NO CODE. Measured on production after the composition work of A07, A09, A10, A13 and A14. Layer order intact and in this order: shell, cells, crowd, sponsors, occupants, SPARKS, centre, walkway, balconies, spectator oval - sparks above occupants, which is the v2.5.761 fix, and the centre above both. Present and animating: 8 moat lanterns, 24 lamp strobes (three rings each), 41 crown light elements with arena-lamp-sweep running, 184 cell sparks with exactly the four seated chefs lit. prefers-reduced-motion rules present in the served CSS. ONE THING IS DELIBERATELY OFF AND WAS BEFORE ANY OF THIS WORK: the CSS floor dust, killed by arena_atmosphere.css with content:none !important under the rule that the SVG is the floor. The light rays exist under another name - they are the crown cones, which is why a search for 'ray' finds nothing.",
    },
    {
        "id": "A16", "group": "Arena Hall", "title": "CulinEire branding and K-mark audit",
        "status": "DONE", "owner": "GreenBear",
        "files": "templates/chef_battle/arena.html; Arena-only assets/CSS",
        "depends_on": "A11-A14",
        "action": "Remove or replace any remaining standalone design K with existing CulinEire branding where a mark is actually required.",
        "visible_result": "Arena reads as part of the existing CulinEire page, not a parallel product.",
        "acceptance": "Site header/logo reused; no duplicate banner or newly drawn logo.",
        "forbidden": "Do not add the reference K banner.",
        "evidence": "DONE - AUDIT, NOTHING TO REMOVE. Swept the whole deck on production for a standalone design K: every leaf element whose entire text is K, and every image, use and svg reference on the deck. Result: zero lone K elements, zero brand assets drawn on the deck at all. The only mark on the page is the site header's own CulinEire logo (logo2.webp, 80x80), which is the existing branding this card asks for. The sponsor plate on the octagon carries a sponsor's own logo and is not the design K.",
    },
    {
        "id": "A17", "group": "Arena integrity", "title": "Truthful visual state matrix",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/tests.py; templates/chef_battle/arena.html; existing Arena JS/CSS",
        "depends_on": "A09-A16",
        "action": "Verify active battle, facing pair, crown-only, empty, loading, error and unauthorised states against the final composition.",
        "visible_result": "Every real server state renders intentionally without fabricated combatants.",
        "acceptance": "Dark Launch 404 holds; no zero/demo fixture replaces real state; all panels fail safely.",
        "forbidden": "No backend contract redesign and no seeded production demo data.",
        "evidence": "docs/chef_battle/ARENA_TRUTHFUL_STATE_MATRIX.md. MEASURED ON PRODUCTION, not read off the code, 2026-08-06 to 2026-08-07 at v2.5.848 through v2.5.873, by putting the arena into each state through /chef-battle/preview/arena/<token>/ and looking. Seven rows recorded: no battle, PENDING, ACCEPTED, both Ready, BEGUN, CANCELLED/VOID, and no-battle-fighter-pads-still-drawn. Two deliberate payload/screen splits documented rather than fixed: a begun battle still lists both chefs in `rings` (the renderer removes them client-side via isDisplaced); in_battle is true from ACCEPTANCE not from the start, which is the Owner's call and not a defect.",
    },
    {
        "id": "A18", "group": "Arena integrity", "title": "Desktop accessibility and responsive gate",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/tests.py; Arena CSS/JS only where a measured defect exists",
        "depends_on": "A17",
        "action": "Verify 1280 and 1920 layouts, keyboard operation, focus, reduced motion, no horizontal overflow and rank-label contrast.",
        "visible_result": "Supported desktop widths remain usable and visually stable.",
        "acceptance": "Stepper one row; contrast >=7:1 recorded; all click targets keyboard-operable; reduced motion passes.",
        "forbidden": "Mobile redesign is frozen and not part of this ticket.",
        "evidence": "MEASURED ON PRODUCTION AT 1280x800 AND 1920x1080, 2026-08-07, by GreenBear; the card stays open and its owner is unchanged. NO HORIZONTAL OVERFLOW at either width. ONE DEFECT FOUND AND FIXED IN v2.5.861 BECAUSE IT WAS MINE: the deck is sized 100svh - var(--arena-header-h) and measureHeader() set that variable from the HEADER ELEMENT alone - 146px - while the header itself starts 77px down the page, under the site utility bar. So the arena overflowed the screen by exactly the height of that bar, and A07's promise of the whole arena on one screen was quietly false at 1920. It now measures everything above the deck, not the header's own height. STILL OPEN FOR WHOEVER TAKES THIS CARD: only two of the first six focusable controls on the deck show any focus ring (no outline and no box-shadow on the rest), and the rank chips render at 9.2px, which is small for a contrast and legibility check. Neither was touched - A18 is not mine and two agents on one card is what cost us A09's approach stage, built twice in one hour. CLOSED by Bolt after final Arena Hall composition: 1920/1440/1280/375 swept, 0px overflow, keyboard verified with real Tab (docs/ARENA_BATTLE_PLAN.md). THE TWO GAPS ABOVE - focus rings, chip contrast - DEFERRED BY THE OWNER, 2026-08-10, to Stage 3 (release-readiness); not to be worked before it.",
    },
    {
        "id": "A19", "group": "Arena Hall", "title": "Owner visual acceptance — Arena Hall",
        "status": "DONE", "owner": "Owner",
        "files": "Evidence only",
        "depends_on": "A18",
        "action": "Review production-sized side-by-side captures against mockups/arena.png.",
        "visible_result": "Owner accepts the Arena Hall or returns a finite punch list.",
        "acceptance": "All required furniture present; intentional deviations documented; no open visual blocker.",
        "forbidden": "No code changes inside the acceptance ticket.",
        "evidence": "OWNER, 2026-08-09: accepted, no punch list returned.",
    },
    {
        "id": "B01", "group": "Battle Broadcast", "title": "Broadcast shell and confrontation header",
        "status": "DONE", "owner": "Bolt",
        "files": "existing battle-room template/JS; scoped broadcast CSS",
        "depends_on": "A19",
        "action": "Port the approved challenger/VS/opponent broadcast header using existing live battle data.",
        "visible_result": "Green left chef, neutral centre and red right chef match broadcast.jpg.",
        "acceptance": "Real participants and theme only; site tokens; no second battle engine.",
        "forbidden": "Do not touch Master Console or infer battle state.",
        "evidence": "SHIPPED v2.5.874. One template serves two surfaces - the console build canvas (labelled fixture since 2026-07-14) and the public broadcast page a spectator lands on - and both wore the canvas's clothes. Before the fix: tab said 'Live Arena (Preview)', description said 'under construction', og:title fell back to the site name, and there was no h1 on the page at all. Fixed: the broadcast surface names the fight in the tab, description and Open Graph tags, and carries a heading (off-screen by clip-rect, so the sighted confrontation header stays GreenBear's composition). An empty clan no longer prints a bare label. One mistake found by looking rather than by a test: the og blocks were first written as {% if is_broadcast %} wrapped AROUND {% block %}, which does nothing - Django resolves blocks at compile time before any condition runs. Fixed by moving the condition inside the block. OWNER, 2026-08-06: THE ARENA IS A TABLOID AND THE BATTLE HAS ITS OWN PAGE. When a battle starts, a click on the centre cell takes every spectator off the arena and onto that page. The approved reference is already built and served: /chef-battle/master/live-arena/preview/, templates/chef_battle/live_arena_preview.html, added 5c457b98 on 2026-07-14. Console-gated, and its data is a LABELLED DEV FIXTURE because it is a build canvas - it is not an orphan and it is not to be tidied away. See ARENA_BATTLE_PLAN section 2c.",
    },
    {
        "id": "B02", "group": "Battle Broadcast", "title": "Streams, countdown and support furniture",
        "status": "DONE", "owner": "GreenBear",
        "files": "scoped broadcast CSS; existing stream/support markup",
        "depends_on": "B01",
        "action": "Match two stream panes, live chips, viewer counts, centre countdown and support footer.",
        "visible_result": "Broadcast body matches the approved two-sided composition.",
        "acceptance": "Existing stream/support actions remain authoritative and operable.",
        "forbidden": "No fake stream, vote or token events.",
        "evidence": "SHIPPED v2.5.869. ARENA_BATTLE_PLAN section 2c: the arena is a tabloid and the fight has its own page, reached from the centre cell. THE COMPOSITION WAS NOT BUILT FOR THIS CARD - it has existed since 2026-07-14 as the console build canvas (templates/chef_battle/live_arena_preview.html), and chef_battle/arena_snapshot.py has been feeding it REAL data for as long: viewers from BattleViewerPresence, likes from the reaction service, comments from BattleChatMessage, supporters from ViewerBattleGift, the stream URL from LiveStreamSession and the clan from an active ClanMembership. What was missing was a public route, a battle to point it at, and a result. All three landed here: /chef-battle/battles/<pk>/broadcast/ behind the same dark-launch guard as the battle room, and the centre of the arena now links to it instead of the battle room. Six tests, including one that proves the page writes nothing to the battle it is showing. B02 SPECIFICALLY: the two stream panes, the live chips, the viewer counts, the centre countdown and the support rail all render from that snapshot on a real battle. The countdown is the battle's own remaining seconds, not a decorative clock. OWNER, 2026-08-06: THE ARENA IS A TABLOID AND THE BATTLE HAS ITS OWN PAGE. When a battle starts, a click on the centre cell takes every spectator off the arena and onto that page. The approved reference is already built and served: /chef-battle/master/live-arena/preview/, templates/chef_battle/live_arena_preview.html, added 5c457b98 on 2026-07-14. Console-gated, and its data is a LABELLED DEV FIXTURE because it is a build canvas - it is not an orphan and it is not to be tidied away. Today the centre click opens the ArenaBattleRoom overlay instead (arena_render.js, stageCentre.popup_url); that is the placeholder this card replaces. See ARENA_BATTLE_PLAN section 2c. Reference available; pending.",
    },
    {
        "id": "B03", "group": "Battle Broadcast", "title": "Broadcast chat and composer",
        "status": "DONE", "owner": "GreenBear",
        "files": "existing battle chat template/JS; scoped broadcast CSS",
        "depends_on": "B02",
        "action": "Match the approved avatar/name/message/time grid and composer strip.",
        "visible_result": "Live chat is visually integrated with the broadcast.",
        "acceptance": "Existing moderation, polling and posting behaviour preserved.",
        "forbidden": "No duplicate polling/listeners and no chat backend rewrite.",
        "evidence": "SHIPPED v2.5.869. ARENA_BATTLE_PLAN section 2c: the arena is a tabloid and the fight has its own page, reached from the centre cell. THE COMPOSITION WAS NOT BUILT FOR THIS CARD - it has existed since 2026-07-14 as the console build canvas (templates/chef_battle/live_arena_preview.html), and chef_battle/arena_snapshot.py has been feeding it REAL data for as long: viewers from BattleViewerPresence, likes from the reaction service, comments from BattleChatMessage, supporters from ViewerBattleGift, the stream URL from LiveStreamSession and the clan from an active ClanMembership. What was missing was a public route, a battle to point it at, and a result. All three landed here: /chef-battle/battles/<pk>/broadcast/ behind the same dark-launch guard as the battle room, and the centre of the arena now links to it instead of the battle room. Six tests, including one that proves the page writes nothing to the battle it is showing. B03 SPECIFICALLY: the chat grid and its composer are the same BattleChatMessage rows the battle room uses, hidden messages excluded, newest six in order. OWNER, 2026-08-06: THE ARENA IS A TABLOID AND THE BATTLE HAS ITS OWN PAGE. When a battle starts, a click on the centre cell takes every spectator off the arena and onto that page. The approved reference is already built and served: /chef-battle/master/live-arena/preview/, templates/chef_battle/live_arena_preview.html, added 5c457b98 on 2026-07-14. Console-gated, and its data is a LABELLED DEV FIXTURE because it is a build canvas - it is not an orphan and it is not to be tidied away. Today the centre click opens the ArenaBattleRoom overlay instead (arena_render.js, stageCentre.popup_url); that is the placeholder this card replaces. See ARENA_BATTLE_PLAN section 2c. Reference available; pending.",
    },
    {
        "id": "R01", "group": "Result / Winner", "title": "Champion and runner-up result shell",
        "status": "DONE", "owner": "GreenBear",
        "files": "existing result template/context; scoped result CSS",
        "depends_on": "B03",
        "action": "Port champion photo/details, runner-up octagon and full-width WINNER band.",
        "visible_result": "Completed battles open the approved result hierarchy.",
        "acceptance": "Real winner/runner-up data; green winner/red runner-up roles; no text truncation.",
        "forbidden": "No client-side winner inference.",
        "evidence": "SHIPPED v2.5.869. ARENA_BATTLE_PLAN section 2c: the arena is a tabloid and the fight has its own page, reached from the centre cell. THE COMPOSITION WAS NOT BUILT FOR THIS CARD - it has existed since 2026-07-14 as the console build canvas (templates/chef_battle/live_arena_preview.html), and chef_battle/arena_snapshot.py has been feeding it REAL data for as long: viewers from BattleViewerPresence, likes from the reaction service, comments from BattleChatMessage, supporters from ViewerBattleGift, the stream URL from LiveStreamSession and the clan from an active ClanMembership. What was missing was a public route, a battle to point it at, and a result. All three landed here: /chef-battle/battles/<pk>/broadcast/ behind the same dark-launch guard as the battle room, and the centre of the arena now links to it instead of the battle room. Six tests, including one that proves the page writes nothing to the battle it is showing. R01 SPECIFICALLY, AND IT WAS A REAL DEFECT: the canvas always crowned fx.left, because a fixture has no result. On a real battle the winner is either side, so the champion and the runner-up are now taken from battle.winner. A test crowns the OPPONENT and fails if the left-hand chef appears in the champion block. result-winner.jpg available; pending.",
    },
    {
        "id": "R02", "group": "Result / Winner", "title": "Result metrics, status and chat",
        "status": "DONE", "owner": "GreenBear",
        "files": "existing result template/JS; scoped result CSS",
        "depends_on": "R01",
        "action": "Port the six metrics, finished-status pill and final chat composition.",
        "visible_result": "Result page carries the complete approved information layer.",
        "acceptance": "Server-confirmed metrics only; keyboard/focus and empty states covered.",
        "forbidden": "No fabricated results or duplicated chat implementation.",
        "evidence": "SHIPPED v2.5.869. ARENA_BATTLE_PLAN section 2c: the arena is a tabloid and the fight has its own page, reached from the centre cell. THE COMPOSITION WAS NOT BUILT FOR THIS CARD - it has existed since 2026-07-14 as the console build canvas (templates/chef_battle/live_arena_preview.html), and chef_battle/arena_snapshot.py has been feeding it REAL data for as long: viewers from BattleViewerPresence, likes from the reaction service, comments from BattleChatMessage, supporters from ViewerBattleGift, the stream URL from LiveStreamSession and the clan from an active ClanMembership. What was missing was a public route, a battle to point it at, and a result. All three landed here: /chef-battle/battles/<pk>/broadcast/ behind the same dark-launch guard as the battle room, and the centre of the arena now links to it instead of the battle room. Six tests, including one that proves the page writes nothing to the battle it is showing. R02 SPECIFICALLY: the six metrics read from the champion's own side rather than the left, and a battle with NO winner - a draw, a void, a withdrawal - says so and claims nobody, because inventing a champion is exactly the fake data this plan forbids. Reference available; pending.",
    },
    {
        "id": "G01", "group": "Release gate", "title": "Complete Design Arena regression and production evidence",
        "status": "DONE", "owner": "Bolt + Owner",
        "files": "Tests/evidence only unless a regression is found",
        "depends_on": "A19, B03, R02",
        "action": "Run the final PostgreSQL suite, visual matrix, Dark Launch checks, deployment postflight and rollback proof.",
        "visible_result": "Design Arena integration is either accepted or blocked by named evidence.",
        "acceptance": "All preceding tickets DONE; production commit/version match origin/main; Owner signs off.",
        "forbidden": "Do not mark Stage 2 DONE on partial screenshots or local-only evidence.",
        "evidence": "docs/chef_battle/G01_RELEASE_GATE_EVIDENCE.md, gathered 2026-08-09/10 against production v2.5.978. 1797/1797 non-skipped tests green (one real board-drift defect found and fixed along the way, section 17.4). Ten of twelve contract section 14 categories have real, checked evidence; the remaining two (A18's accessibility gaps, section 9 legal/payment) DEFERRED BY THE OWNER, 2026-08-10, to Stage 3. OWNER, 2026-08-10: SIGN OFF. Stage 2 closes on this.",
    },
    {
        "id": "MC01",
        "group": "Master Console",
        "title": "Battle Cancellation Simulation - walk the withdrawal through, step by step",
        "status": "DONE",
        "owner": "GreenBear",
        "files": "templates/chef_battle/arena_master_console.html; chef_battle/withdrawal_service.py (READ ONLY - reuse, do not re-implement)",
        "depends_on": "v2.5.830",
        "action": "Add a scenario to the Master Console Panel that steps through a battle withdrawal exactly as it will look on the real arena: (1) the chef presses Withdraw and writes his reason; (2) the other chef reads it and answers - without a penalty, or with one, which obliges him to say why; (3) a moderator has the final word and may rule against either of them. Nothing moves until the moderator speaks.",
        "visible_result": "Pressing the scenario in the console plays the three stages with what each actor sees at each one.",
        "acceptance": "The simulation calls the real service or mirrors it exactly; the penalty shown is 15 rating and 3 reputation; the battle ends CANCELLED with no loss and no winner; the three-per-account allowance and the dark button are shown.",
        "forbidden": "Do not re-implement the rule in the console - every guard is in withdrawal_service.py and covered by BattleWithdrawalTests. Do not merge it with the operator CANCEL action in P03_TRANSITION_MATRIX: that is an operator acting from above, this is a chef asking and a moderator answering. Nothing may route around penalise() (section 18).",
        "evidence": "MECHANISM SHIPPED v2.5.871; THE PICTURE IS STILL THE OWNER'S. The first MC01 was a console panel that walked the withdrawal through in step cards, and he deleted it the day it shipped - being a DESCRIPTION was the whole problem, because he checks the product by looking at the arena. So the three steps are PERFORMED now instead of narrated: emulation_withdrawal_step() drives ask, answer and verdict through the real withdrawal_service on the emulation battle, so the allowance is really spent, the penalty is really applied by penalise(), and the battle really ends CANCELLED with no loss and no winner. Four tests hold it, including that NOTHING moves until the moderator speaks and that it refuses any battle which is not an emulation. WHAT WAS DELIBERATELY NOT BUILT: what any of it LOOKS like on the arena - that became MC02, and the Owner CANCELLED it, 2026-08-09: no longer needed. OWNER'S INSTRUCTION, 2026-08-06: the withdrawal flow shipped in v2.5.830 must also exist inside the Master Console Panel as a Battle Cancellation Simulation, showing every step as it will look on the real arena. Handed to Bolt on the Carpet as message #3491, together with the full synchronisation of current work the Owner asked for. CLOSED: the mechanism (v2.5.871) is the whole of what this card asked for; nothing is left TO SPEC under it any more.",
    },
    {
        "id": "X01", "group": "Audit 2026-08-05", "title": "The list of upcoming battles does not exist",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py payload + selector; templates/chef_battle/arena.html",
        "depends_on": "none",
        "action": "Add the upcoming-battles list the arena is half-built for.",
        "visible_result": "The arena shows who is fighting whom next.",
        "acceptance": "Real scheduled battles only, server-selected; empty state truthful; the key joins PUBLIC_ARENA_STATE_KEYS so the poll carries it.",
        "forbidden": "No invented battles and no fixture data (v2.5.782).",
        "evidence": "DONE v2.5.822 (Bolt). Owner, 2026-08-05: the arena exists so chefs, sponsors, spectators, VIPs and spirits can see each other AND to show the list of upcoming battles. The second half had no key, no selector and no block - confirmed by counting the 16 keys in PUBLIC_ARENA_STATE_KEYS before touching anything. WHAT UPCOMING MEANS, AND IT IS NARROWER THAN 'NOT FINISHED': get_upcoming_battles() takes SCHEDULED with start_time still in the future. ACTIVE_STATUSES deliberately includes SCHEDULED so an imminent battle still draws on the floor, but a scheduled battle whose time has passed is one the arena is already SHOWING, not one it is announcing - announcing it would be the panel lying about the floor below it. WAITING is excluded too: that battle started and is sitting out the grace period for its second chef, which is late rather than forthcoming. Five tests pin exactly that boundary. THE KEY IS IN THE POLL CONTRACT, which is the trap vip_sponsors and spirit_count already fell into: bind() repaints from the payload, so a key that is not sent reads as 'nothing is booked' and would have cleared the panel thirty seconds after load. Two more tests pin the key and its shape. NO FIXTURE: real rows only, and an empty schedule says so in words - the panel keeps its shape empty, as the ladder does. The time goes out as an instant plus a server-rendered fallback; arena_deck.js reformats it in the viewer's own locale rather than the server baking 'in 3 hours' into a cached string. PLACEMENT IS PROVISIONAL AND IS THE OWNER'S: the panel sits in the left rail under the crown ladder, built on the ladder's own plate so two lists in one rail do not read as two kinds of thing. The approved reference has no such panel, so there was nothing to measure against - moving it is a CSS-only change.",
    },
    {
        "id": "X02", "group": "Audit 2026-08-05", "title": "Silence is not an offence - the ignore penalty is withdrawn",
        "status": "DONE", "owner": "GreenBear",
        "files": "chef_battle/services.py expire_stale_challenges()",
        "depends_on": "none",
        "action": "None. The Owner ruled that an unanswered challenge costs nothing.",
        "visible_result": "None.",
        "acceptance": "expire_stale_challenges() takes nothing from anyone; battle_rules.md says so too.",
        "forbidden": "Do not change the window itself here - that is X05 and it is the Owner's.",
        "evidence": "CLOSED BY THE OWNER'S RULING, 2026-08-05: silence is not an offence - a chef who never answered may be busy, away, or may simply never have seen it. The audit had reported that ignoring a challenge was free while refusing one cost fifteen Battle Moves and five reputation, and read that asymmetry as a defect because battle_rules.md gave the two the same weight. IT IS NOT A DEFECT. Not answering is not a choice a chef made - it is a message he may never have seen, and the site cannot tell contempt from a holiday. IRRESPONSIBILITY IS ACCEPTING AND THEN NOT TURNING UP, and that is already paid for by _award_walkover(), _award_forfeit_win() and the both-absent path: the loss, the broken streak and the reputation. v2.5.820 briefly shipped the penalty; v2.5.823 took it out again, and battle_rules.md - now an ACTIVE document - carries the correction with the old rows struck through rather than deleted. ChefBattleProfile.ignored_battles therefore stays unwritten by design and joins ChefBattleProfile.level as a dead column awaiting his word on a migration.",
    },
    {
        "id": "X03", "group": "Audit 2026-08-05", "title": "level is never recalculated - every chef is level 1 forever",
        "status": "DONE", "owner": "GreenBear",
        "files": "chef_battle/services.py battle completion; ChefBattleProfile.level",
        "depends_on": "Owner",
        "action": "Either wire the level ladder or delete the column and the documentation that promises it.",
        "visible_result": "Depends on the decision; today the field is invisible because it never moves.",
        "acceptance": "One ladder, not two. If level stays, it recalculates on completion and emits its event; if it goes, nothing reads it.",
        "forbidden": "Do not add a second progression system beside rank.",
        "evidence": "RESOLVED BY X09 IN v2.5.819, WITH ONE PIECE LEFT THAT NEEDS HIS WORD. The Owner ruled that wins promote rank, so there is one ladder and level is not it. ChefBattleProfile.level is read by nothing - no view, no template, no serializer; the only writes in the whole repository are four historical data migrations. It is a dead column. DROPPING IT IS A MIGRATION, and AGENTS.md section 8 excludes migrations from the standing authorisation, so the column stays until he says the word. Nothing depends on it and nothing reads it, so leaving it costs only the confusion of finding it there.",
    },
    {
        "id": "X04", "group": "Audit 2026-08-05", "title": "The build board misreports the token shop",
        "status": "DONE", "owner": "GreenBear",
        "files": "chef_battle/views.py:188",
        "depends_on": "none",
        "action": "Correct the completed-item text to the eight packages that actually exist.",
        "visible_result": "The board stops telling the Owner something untrue about his own shop.",
        "acceptance": "Count and top package match chef_battle/token_config.py.",
        "forbidden": "Do not change any price - that is X11 and it is money.",
        "evidence": "DONE by BOLT, v2.5.819, commit e32b4c2c - he shipped it while my own duplicate was in its test run, so mine was reverted rather than merged. The roadmap had said five packages topping out at Executive 1400T/EUR80; token_config.py defines eight topping out at Legend Chef 12800T/EUR768. Neither the count nor the top package matched, on a board the Owner reads to decide things. THE DUPLICATE IS THE LESSON: he was given X01 and took X04 as well, I was given X04 and never said I had started it. Two agents, one line, one wasted pass - say what you have picked up before you pick it up.",
    },
    {
        "id": "X05", "group": "Audit 2026-08-05 - Owner decides", "title": "Acceptance window: 12 hours or 48?",
        "status": "DONE", "owner": "Owner",
        "files": "Decision only - no file until he rules",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "battle_rules.md says 12 hours. forms.py:46 sets expires_at to now + 48h. The public rules page (rules.html:200) tells users 48 hours. The document CONTRADICTS ITSELF - its first table says 'Auto-refuse (48h timeout)' while its slot lifecycle says 12h. Code and the live rules agree with each other; only the archived doc dissents. CLOSED BY THE OWNER, 2026-08-06: TWELVE HOURS. Shipped v2.5.837 - CHALLENGE_ACCEPTANCE_WINDOW in chef_battle/forms.py, the challenge form, the public rules page and battle_rules.md all now say twelve, and the doc contradiction is struck through rather than deleted. A challenge nobody answers frees the slot the same day instead of two days later, and it still costs the challenged chef nothing (X02).",
    },
    {
        "id": "X06", "group": "Audit 2026-08-05 - Owner decides", "title": "Battle window: 24 hours and a field that does not exist",
        "status": "DONE", "owner": "Owner",
        "files": "docs/chef_battle/battle_rules.md",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "SETTLED BY THE OWNER, 2026-08-10: the document matches the code. battle_rules.md specified battle_deadline = accepted_at + 24h and a single 24-hour window; Battle has no such field. accept_challenge() (services.py:325) sets submission_deadline = start_time + 48h and voting_deadline = that + 2 days, and the public rules page has said 48 hours to submit all along. No code changed - the document is corrected to describe what has been running.",
    },
    {
        "id": "X07", "group": "Audit 2026-08-05 - Owner decides", "title": "Moves earned per action",
        "status": "DONE", "owner": "Owner",
        "files": "docs/chef_battle/moves_economy.md",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "SETTLED BY THE OWNER, 2026-08-10: 5/5/10/1. moves_economy.md said recipe +2, article +2, battle win +5, participation +1; energy_service.py lines 22-27 have run recipe 5, article 5, win 10, participation 1 all along. No code changed - the document's earning table and its stale 'previous values' note are corrected.",
    },
    {
        "id": "X08", "group": "Audit 2026-08-05 - Owner decides", "title": "Combat moves per round: 1-3 or 1-5",
        "status": "DONE", "owner": "Owner",
        "files": "docs/chef_battle/moves_economy.md",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "SETTLED BY THE OWNER, 2026-08-10: the document matches the code. moves_economy.md said 1-3 moves per round; COMBAT_MOVES_MAX in services.py (now line 1209) has run 5 all along, so the real range is 1-5. No code changed - the document is corrected.",
    },
    {
        "id": "X09", "group": "Audit 2026-08-05 - Owner decides", "title": "The CulinEire Hero tier is not what the document describes",
        "status": "DONE", "owner": "GreenBear",
        "files": "Decision only - no file until he rules",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "OWNER'S RULING 2026-08-05: wins promote rank. Implemented in v2.5.820, corrected in v2.5.826. Rank was derived from rating, an Elo-style number moving by 25 a battle, so the ladder a chef could see (wins) and the ladder that actually moved them (rating) were different things. RANK_THRESHOLDS is now keyed to wins at 0/3/6/9/12/15/18/21 - the step of three wins is chef_levels.md's own cadence, not a number invented for this, and it puts Head Chef at the fifteen wins that document calls the top. rating is NOT removed: it stays a published statistic and still moves on every result, it simply no longer decides anyone's rank. The documented CulinEire Hero tier is buried with this - rank does the progression and is_hero has meant the Owner's own account since it was written. ALSO FIXED IN THE SAME CHANGE, and it was a live section 18 exposure: the main result path guarded rank recomputation on infinite_moves, but the three forfeit and no-show paths did not, so a walkover could have recomputed the OWNER'S OWN RANK behind his back. promote_rank() is now the single exemption point and a test holds it. AND A DEFECT OF MY OWN, FOUND ON RE-READING AND FIXED IN v2.5.826: the ruling was that wins PROMOTE, but v2.5.820 recomputed the LOSER's rank too, so a defeat could demote a chef sitting above their win count and publish it to the news. promote_rank() now only ever raises, and the rules page finally publishes the wins ladder instead of the old rating ranges.",
    },
    {
        "id": "X10", "group": "Audit 2026-08-05 - Owner decides", "title": "Matchmaking axis: level or rank",
        "status": "DONE", "owner": "Owner",
        "files": "Decision only - no file until he rules",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "CLOSED BY THE OWNER'S OWN WORDS, 2026-08-05: RANK, plus or minus one. chef_levels.md specifies matchmaking by LEVEL, maximum difference 1; check_rank_matchup() enforces it by RANK. The code already follows his live instruction; the archived document is the stale side and stays uncorrected (AGENTS.md section 10 - an archived document cannot define current scope). No code change needed - the ruling predates this card, this closes the paperwork on it.",
    },
    {
        "id": "X11", "group": "Audit 2026-08-05 - Owner decides", "title": "Token packages: four or eight",
        "status": "DONE", "owner": "Owner",
        "files": "docs/chef_battle/token_economy.md",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "SETTLED BY THE OWNER, 2026-08-10: the document matches the code. This is money, so it was said plainly. token_economy.md described four packages - Starter 100/EUR10, Popular 250/EUR20, Pro 600/EUR40, Champion 1400/EUR80; chef_battle/token_config.py (TOKEN_PACKAGES, the canonical source X04 already pointed to) has run eight packages all along, topping out at Legend Chef 12800T/EUR768. No price changed - the document now lists all eight with their real standard and discounted prices.",
    },
    {
        "id": "X12", "group": "Audit 2026-08-05 - Owner decides", "title": "Appreciation gift catalogue and the doubled artifact price",
        "status": "DONE", "owner": "Owner",
        "files": "Decision only - no file until he rules",
        "depends_on": "Owner",
        "action": "The Owner rules which side is the rule. No agent changes code towards an archived document.",
        "visible_result": "None until the ruling.",
        "acceptance": "His answer recorded verbatim in the release journal, then the losing side corrected.",
        "forbidden": "Do not 'fix' this by editing code to match an archived doc; several of these are money.",
        "evidence": "OWNER'S RULING 2026-08-05: X12 approved. The doubled artifact price stands: send_battle_artifact() (services.py) charges artifact.token_cost * 2 - the artifact plus an equal delivery fee - and that is the intended economics, not a defect. The live catalogue also stands: six appreciation gifts at 20-100 tokens against the archived document's five at 5-20. No code change; this row exists so nobody 'corrects' the price towards audience_gifts.md later.",
    },
    {
        "id": "F1", "group": "Release Audit 2026-08-10", "title": "Public author page leaked battle data through a stale permission flag",
        "status": "DONE", "owner": "Bolt",
        "files": "recipes/views.py:1437 (author_detail)",
        "depends_on": "none",
        "action": "Replace the view's own hand-rolled visibility check with a call to is_battle_visible().",
        "visible_result": "A moderator flag without the staff bit sees nothing on someone else's author page again, matching every other Chef Battles surface.",
        "acceptance": "author_detail calls is_battle_visible(); has_bearseeker_privileges does not appear in this file's own copy of the check; recipes.tests.AuthorDetailBattleVisibilityParityTests green.",
        "forbidden": "Do not widen who sees the section while fixing this - the fix is parity with the existing gate, not a new policy.",
        "evidence": "SHIPPED v2.5.988. Full audit against docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md found author_detail re-implementing the visibility rule by hand instead of calling chef_battle.access.is_battle_visible(), and the copy still trusted has_bearseeker_privileges - the exact flag the v2.5.798 fix (see that release_journal entry) excluded everywhere else. It was a fifth hand-written copy test_gate_parity.py never covered, because that test only compares battle_widget_context against is_battle_visible(). Any account carrying the moderator flag without is_staff saw battle_profile, recent_battles, arena_battles, arena_gift_display and champion_badge on the public author page. Fixed by deleting the local copy and calling the shared function. New test recipes.tests.AuthorDetailBattleVisibilityParityTests proves a moderator-flag-only account sees neither the context values nor the rendered #chef-arena section, and that staff still does.",
    },
    {
        "id": "F2", "group": "Release Audit 2026-08-10", "title": "Token purchase accepted a real Stripe charge with no visibility gate",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (token_checkout_create); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "none",
        "action": "Add chef_battle_guard to token_checkout_create; remove its now-stale UNGUARDED_BY_DESIGN entry.",
        "visible_result": "An ordinary authenticated user (not staff) posting directly to the checkout endpoint gets the same 404 the shop page already gives them.",
        "acceptance": "token_checkout_create carries @chef_battle_guard; test_every_routed_view_is_guarded_or_listed still green; TokenOrderVatConsentTests and AgeVerificationGateTests updated for the now-enforced gate.",
        "forbidden": "Do not touch Stripe/webhook/payout code - this is an access-gate fix only, per AGENTS.md section 8's standing exclusion of the real payment integration.",
        "evidence": "SHIPPED v2.5.988. token_shop (the GET page) carried @chef_battle_guard; the POST that actually creates the Stripe Checkout session did not - only @require_POST @login_required, listed in UNGUARDED_BY_DESIGN with the reason 'wallet is resolved from the caller', which addresses data-scoping, not pre-release visibility. Contract section 5 says ordinary_authenticated_user sees Chef Battles nowhere before the Owner's release decision; this endpoint let one spend real EUR on it anyway with a guessed package_id. Guard added, exemption entry removed. Existing tests that posted to this endpoint as a plain non-staff author (TokenOrderVatConsentTests.test_checkout_requires_withdrawal_consent, AgeVerificationGateTests.test_token_checkout_blocked_when_age_not_verified) needed CHEF_BATTLE_ENABLED=True added so they still reach their own logic instead of 404ing at the gate first - same fix pattern the v2.5.871 journal entry already used for BattleSetReadyTests.",
    },
    {
        "id": "F3", "group": "Release Audit 2026-08-10", "title": "Gift and artifact sending accepted POSTs with no visibility gate",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (send_appreciation_gift_view, send_viewer_battle_gift_view); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "none",
        "action": "Add chef_battle_guard to both gift-send views; remove their now-stale UNGUARDED_BY_DESIGN entries.",
        "visible_result": "A user who cannot even load battle_detail can no longer POST a gift or artifact into that battle by pk and recipient slug.",
        "acceptance": "Both views carry @chef_battle_guard; test_every_routed_view_is_guarded_or_listed still green; AgeVerificationGateTests.test_send_gift_blocked_when_age_not_verified still exercises its own fraud-gate logic under the class-level CHEF_BATTLE_ENABLED=True override.",
        "forbidden": "Do not loosen the existing fraud gates (suspension/fraud-flag/age/velocity) while adding this - they stay, this adds the missing layer in front of them.",
        "evidence": "SHIPPED v2.5.988. Both views were @login_required @require_POST only, exempted in UNGUARDED_BY_DESIGN on the rationale 'runs the fraud gates including suspension' - true, but none of gate_suspended_account/gate_fraud_flagged/gate_age_verified check is_staff or is_battle_visible. A user who fails chef_battle_guard on every page in this app could still reach either endpoint directly. Guard added to both; exemptions removed.",
    },
    {
        "id": "F4", "group": "Release Audit 2026-08-10", "title": "No-show sweep could double-award a forfeit under overlapping runs",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (handle_no_show_battles)",
        "depends_on": "none",
        "action": "Row-lock each battle under the sweep and re-verify its status/deadline after acquiring the lock, same pattern as resolve_start_rituals/_locked_battle.",
        "visible_result": "None visible to a user - this closes a data-integrity gap in a cron sweep, not a UI change.",
        "acceptance": "handle_no_show_battles locks via _locked_battle and re-checks status+deadline before awarding; NoShowSweepIsLockedAgainstDoubleAwardTests green (SQL-mechanism test + a run-twice-only-awards-once functional test).",
        "forbidden": "Do not change the no-penalty-for-silence rule (Owner, 2026-08-05) or any forfeit amount while fixing the lock - this is concurrency-safety only.",
        "evidence": "SHIPPED v2.5.988. handle_no_show_battles iterated a plain queryset snapshot and called _award_forfeit_win() inside transaction.atomic() with no row lock - unlike calculate_battle_result/resolve_start_rituals, which lock specifically to stop double-processing (see _locked_battle's own docstring). The sweep runs from crontab every 15 minutes with no mutex (docs/chef_battle/ARENA_EMULATION_VISUAL_STEPS.md), and _notify_chef sends email synchronously inside the loop, so overlapping runs are plausible, not theoretical. Two overlapping runs seeing the same stale battle before either committed would both award the forfeit - double wins/streak/rank to the winner, double penalty to the loser. Fixed: the sweep now takes a plain id snapshot, then locks and re-verifies each battle (status still qualifying, deadline still passed) inside its own transaction before touching it, and recomputes submission state from the locked row rather than the pre-lock snapshot.",
    },
    {
        "id": "F5", "group": "Release Audit 2026-08-10", "title": "Reward issuance could lose tokens under a concurrent wallet update",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (issue_reward)",
        "depends_on": "none",
        "action": "Replace the read-modify-write wallet balance update with the same F()-expression atomic UPDATE credit_tokens/debit_tokens already use.",
        "visible_result": "None visible to a user - this closes a lost-update gap between two staff actions, not a UI change.",
        "acceptance": "issue_reward updates TokenWallet.balance via F('balance') + amount, not a Python-computed literal; IssueRewardWalletUpdateIsAtomicTests green (SQL-mechanism test + a balance_after-reconciles test).",
        "forbidden": "Do not change reverse_reward's existing select_for_update() pattern while fixing this - that one is already correct, just a different valid technique; this card is issue_reward only.",
        "evidence": "SHIPPED v2.5.988. issue_reward locked the RewardRecord (select_for_update) but read wallet.balance, added tokens_granted in Python, and .save()'d the result - a plain read-modify-write, while credit_tokens/debit_tokens in this same file use TokenWallet.objects.filter(pk=...).update(balance=F('balance')+amount) specifically to avoid this. Two RewardRecords for the same chef issued at once (two staff approving different queue rows, or a bulk 'issue selected' action racing a second session) would both read the pre-update balance; the later save silently clobbers the earlier one and TokenTransaction.balance_after stops reconciling with the real balance - a §7 auditability violation. Fixed to the same F()-expression pattern used elsewhere in this file.",
    },
    {
        "id": "F6", "group": "Release Audit 2026-08-10", "title": "Chef onboarding and age self-certification carried no visibility gate",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (chef_enroll, enroll_success, age_verification); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "none",
        "action": "Add chef_battle_guard, outermost, to all three; remove their now-stale UNGUARDED_BY_DESIGN entries.",
        "visible_result": "An ordinary authenticated user gets the same 404 every other gated arena page already gives them.",
        "acceptance": "All three carry @chef_battle_guard as the outermost decorator; OnboardingAndBattleFlowGuardTests green.",
        "forbidden": "Do not change the enrolment bonus amount or the age-verification flow itself - gate placement only.",
        "evidence": "SHIPPED v2.5.994. Only @login_required - an ordinary non-staff user, who by contract section 5 sees nothing of Chef Battles, could self-enroll as a Chef, collect award_enrol_bonus tokens, and self-certify their own age, a full onboarding/reward-mint bypass of a feature this tier should not reach at all. Guard added outermost (GreenBear's v2.5.989 convention: above login_required, so an unauthorised caller gets 404 rather than a login redirect that would announce the URL's existence), exemptions removed.",
    },
    {
        "id": "F7", "group": "Release Audit 2026-08-10", "title": "Part of the battle flow was gated inconsistently with its siblings",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (battle_changing_room, battle_recipe_attach, biathlon); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "none",
        "action": "Add chef_battle_guard, outermost, to all three; remove their now-stale UNGUARDED_BY_DESIGN entries.",
        "visible_result": "These three pages now answer the same as battle_declare_menu, biathlon_lock, biathlon_shoot and cooking_submit, which already carried the guard.",
        "acceptance": "All three carry @chef_battle_guard as the outermost decorator; OnboardingAndBattleFlowGuardTests green.",
        "forbidden": "Do not touch the participant-only PermissionDenied checks underneath - those stay, this adds the missing layer in front of them.",
        "evidence": "SHIPPED v2.5.994. Only @login_required plus a participant check, unlike their sibling battle-flow endpoints. Exploitable in the same chain as F6: a self-enrolled ordinary user, challenged by a staff member, could reach these three despite failing the app-wide gate everywhere else. Guard added outermost to match siblings; exemptions removed.",
    },
    {
        "id": "F8", "group": "Release Audit 2026-08-10", "title": "Chef Battle's own moderation surface trusted a general site-moderator flag",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (cooking_moderation, cooking_moderation_approve, battle_withdraw_resolve); chef_battle/access.py (UNGUARDED_BY_DESIGN reasons updated)",
        "depends_on": "none",
        "action": "Require is_moderator(user) AND is_battle_visible(request) in all three, instead of is_moderator() alone.",
        "visible_result": "None visible to a correctly-configured account - this closes a data-integrity gap the current data happens not to trigger.",
        "acceptance": "All three views check both conditions; ChefBattleModerationRequiresVisibilityTests green (moderator-flag-without-staff denied, staff moderator allowed).",
        "forbidden": "Do not change accounts.views.is_moderator() itself - it is used site-wide for general content moderation outside Chef Battles, and that scope is not this card's to touch.",
        "evidence": "SHIPPED v2.5.994. is_moderator() returns True for RecipeAuthor.has_bearseeker_privileges regardless of is_staff - a general site-moderation flag labelled 'Can moderate site content', not a Chef Battle one. Not currently exploitable: accounts/views.py's grant_bearseeker action now always sets is_staff=True alongside the flag, so every real moderator today also passes is_battle_visible. But nothing enforced that invariant at the data or is_moderator() level, and the doc record shows this exact drift already happened once in production. Rather than touch the shared is_moderator() function's site-wide semantics, these three chef_battle-specific views now also require is_battle_visible(request), matching every other page in this app.",
    },
    {
        "id": "F9", "group": "Release Audit 2026-08-10", "title": "Rank eligibility was checked once, at the challenge, not again at acceptance",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (accept_challenge); chef_battle/views.py (challenge_respond)",
        "depends_on": "none",
        "action": "Re-run check_rank_matchup inside accept_challenge; catch the resulting ValueError in challenge_respond and show it as a message instead of a 500.",
        "visible_result": "Accepting a challenge whose rank gap widened past adjacent since it was sent now shows an error instead of silently creating an ineligible battle.",
        "acceptance": "accept_challenge raises ValueError on a stale rank mismatch; challenge_respond redirects with a message rather than crashing; AcceptChallengeRankRecheckTests green.",
        "forbidden": "Do not auto-refuse or auto-expire the challenge on this path - the challenge stays PENDING; deciding what happens to it next is a product call, not this fix's to make.",
        "evidence": "SHIPPED v2.5.994. check_rank_matchup() ran only from challenge_create (views.py); accept_challenge() never called it. A challenge stands up to twelve hours (X05), and a win moves rank by the ladder's three-wins-per-step cadence, so a matchup legal when sent could no longer be adjacent-rank by the time it was accepted - eligibility was authoritative only at the request, not at the state transition it is meant to gate, against contract section 7's 'server-authoritative eligibility'. accept_challenge now re-checks and raises before touching the database; challenge_respond catches it and redirects with the same error message challenge_create already shows.",
    },
    {
        "id": "F10", "group": "Release Audit 2026-08-10", "title": "The reveal flag could desync from what the template actually showed",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (_score_battle, operator_force_status, _REVEAL_IMPLIED_TARGETS)",
        "depends_on": "none",
        "action": "Set is_revealed on both entries inside _score_battle, and inside operator_force_status's direct-assign branch whenever the target status is reveal-implying.",
        "visible_result": "None visible under normal play - this closes the gap between what the database records and what an operator-forced or auto-scored battle already showed.",
        "acceptance": "_score_battle and operator_force_status's direct-assign branch both set is_revealed=True on qualifying transitions; ForcedTransitionRevealsEntriesTests green (direct force-assign case + calculate_battle_result case).",
        "forbidden": "Do not change reveal_entries_if_ready() itself or the template's fallback condition - this closes the gap at the two writers that were missing it, not by changing what the template trusts.",
        "evidence": "SHIPPED v2.5.994. battle_detail.html shows entry.recipe/battle_statement when entry.is_revealed OR battle.status in {completed, presentation, voting} - a phase-name fallback. reveal_entries_if_ready() was the only place that set is_revealed, and neither _score_battle (the ACTIVE/VOTING -> COMPLETED scoring path, reachable directly and via operator_force_status's own _SERVICE_OWNED_TRANSITIONS dispatch) nor operator_force_status's direct-assign branch (any other target, e.g. forcing straight to PRESENTATION or VOTING) called it. A forced or scored transition into a reveal-implying status could show both dishes in the template while is_revealed stayed False in the database - the reveal contract held only by which code path happened to make a dish public, not as an independent invariant. Fixed at both writers: _score_battle now reveals unconditionally before scoring, and operator_force_status's direct-assign branch reveals whenever target_status is in the new _REVEAL_IMPLIED_TARGETS set.",
    },
    {
        "id": "F11", "group": "Release Audit 2026-08-10", "title": "Four personal pages carried no explicit arena gate",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (reward_agreement, payout_statement, battle_chest, changing_room); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "none",
        "action": "Add chef_battle_guard, outermost, to all four; remove their now-stale UNGUARDED_BY_DESIGN entries.",
        "visible_result": "These four pages now answer the same as every other page in the app for a user the arena is not released to.",
        "acceptance": "All four carry @chef_battle_guard as the outermost decorator; OnboardingAndBattleFlowGuardTests (extended) green.",
        "forbidden": "Do not change the own-account-only checks underneath - those stay, this adds the missing layer in front of them.",
        "evidence": "SHIPPED v2.5.996. Only @login_required plus an own-account check. Practical exposure was low - a user who cannot reach any gated battle/challenge flow has nothing to see on these four - but it was architecturally inconsistent with the contract's blanket claim that arena, galleries, shop, profiles and rankings are all behind the gate. Guard added outermost to match the rest of the app; exemptions removed.",
    },
    {
        "id": "F12", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "A dish could reach public voting with zero combat and zero moderated photo",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (battle_entry_submit, battle_detail's can_submit)",
        "depends_on": "none",
        "action": "Require battle.status == COOKING in battle_entry_submit, matching cooking_submit's own gate, instead of merely excluding SCHEDULED/MENU_LOCKED; align can_submit's phase check the same way.",
        "visible_result": "The dish-submission button and form only appear and work once a moderator has approved the cooking phase; submitting during combat or the ingredient biathlon now redirects with a message instead of quietly working.",
        "acceptance": "battle_entry_submit rejects ACTIVE and INGREDIENT_PENALTY, accepts COOKING; BattleEntrySubmitRequiresCookingPhaseTests green.",
        "forbidden": "Do not touch reveal_entries_if_ready's own branches or cooking_submit - the fix is the one gate that let a player-facing action set dish_submitted_at outside COOKING, not the readers of that field.",
        "evidence": "SHIPPED v2.5.1000. battle_entry_submit only excluded SCHEDULED/MENU_LOCKED, leaving ACTIVE (combat still running), INGREDIENT_PENALTY (biathlon not yet run) and every other mid-lifecycle status open to a dish submission. dish_submitted_at set there is exactly what reveal_entries_if_ready's ACTIVE branch reads to jump the battle straight to VOTING - so a battle could reach public voting with zero combat rounds, zero biathlon, and zero moderated cooked_photo ever uploaded. cooking_submit() (the real photo upload) already required COOKING and an existing entry; battle_entry_submit is what creates that entry, so it now requires the same phase.",
    },
    {
        "id": "F13", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "Opponents were never age-verified before accepting a real-money battle",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (challenge_respond)",
        "depends_on": "none",
        "action": "Add a gate_age_verified(author) check on the accept branch, alongside the existing rank/cooldown checks, before calling accept_challenge.",
        "visible_result": "An opponent who has not confirmed 18+ sees an error message and stays on the challenge list instead of entering a real-money battle.",
        "acceptance": "challenge_respond blocks accept when the opponent's age_verified is False; ChallengeAcceptRequiresAgeVerificationTests green.",
        "forbidden": "Do not add the check inside accept_challenge itself - it has exactly one production caller (this view); putting the gate there would also silently apply it to the internal demo_battle management command with no fraud pipeline around it to explain the failure.",
        "evidence": "SHIPPED v2.5.1000. gate_age_verified ran at challenge_create (on the challenger), token purchase and gift-sending, but never on the opponent who accepts - the one action that actually seats a chef in a real-money arena. A challenge can sit unanswered for up to twelve hours (X05), so the challenger's own age check at creation time cannot stand in for it.",
    },
    {
        "id": "F14", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "COOKING to PRESENTATION through photo moderation missed the reveal flag F10 was meant to close everywhere",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (operator_moderate_entry)",
        "depends_on": "F10",
        "action": "Reveal both entries when the second cooked-photo approval moves the battle from COOKING to PRESENTATION.",
        "visible_result": "None visible under normal play - the template already masked this via its status OR fallback. is_revealed now stays accurate through the presentation phase, which the vote gate and admin filters both rely on.",
        "acceptance": "ModerateEntryToPresentationRevealsEntriesTests green: one approval leaves the battle in COOKING, the second reveals both entries and moves it to PRESENTATION.",
        "forbidden": "Do not extend _REVEAL_IMPLIED_TARGETS-style logic into operator_moderate_entry generally - this touches only the one transition (COOKING to PRESENTATION) that function actually performs.",
        "evidence": "SHIPPED v2.5.1000. PRESENTATION is one of F10's _REVEAL_IMPLIED_TARGETS; operator_force_status's direct-assign branch and _score_battle both reveal for exactly that reason. operator_moderate_entry reaches the same target status through real photo moderation - the only place PRESENTATION is ever actually set in production - and F10 missed it because it isn't a force-console path.",
    },
    {
        "id": "F15", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "The chef enrolment bonus could be credited twice by a double-click",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (chef_enroll)",
        "depends_on": "none",
        "action": "Lock the profile row and re-check enrolled_at under the lock before crediting award_enrol_bonus, same pattern as F4/F5.",
        "visible_result": "None visible under normal play - a double-click or retried submit now credits the enrolment bonus exactly once instead of once per request that raced past the check.",
        "acceptance": "EnrolBonusIsLockedAgainstDoubleCreditTests green: asserts a FOR UPDATE lock in the captured SQL, and that a second submit neither changes the balance nor writes a second BattleMoveTransaction.",
        "forbidden": "Do not touch award_enrol_bonus's own arithmetic - the race was in the caller's check-then-act around enrolled_at, not in how the bonus is calculated or split between chest and battle moves.",
        "evidence": "SHIPPED v2.5.1000. chef_enroll checked profile.enrolled_at with no lock before calling award_enrol_bonus, which itself does a plain read-modify-write on chest_moves/battle_moves - two concurrent submits both saw enrolled_at=None and both credited the bonus, doubling it and writing two ENROL_BONUS transactions for one registration.",
    },
    {
        "id": "F16", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "The general moderation panel showed live battle content the same way F8 had already closed elsewhere",
        "status": "DONE", "owner": "Bolt",
        "files": "recipes/views.py (moderation_panel)",
        "depends_on": "F8",
        "action": "Gate pending_clans/pending_withdrawals behind is_battle_visible(request), the same invariant F8 added to cooking_moderation/cooking_moderation_approve/battle_withdraw_resolve; leave the rest of the panel open to every moderator.",
        "visible_result": "A moderator without arena access sees the panel's recipe/article/pinch queues as normal, with the Battle withdrawals and Clans sections empty instead of showing real battle participants and content.",
        "acceptance": "ModerationPanelRequiresBattleVisibilityTests green: a has_bearseeker_privileges-only moderator sees no battle content and empty context lists; a staff moderator sees both as before.",
        "forbidden": "Do not gate the whole panel on is_battle_visible - recipes, articles and pinch moderation are general-site duties that must stay available to every moderator regardless of arena visibility.",
        "evidence": "SHIPPED v2.5.1000. Gated only on is_moderator() - without is_battle_visible() - and unconditionally built pending_withdrawals (BattleWithdrawal with battle/requester/opponent) and pending_clans, both rendered in templates/moderation/panel.html. Exactly the logic F8 closed for the three chef_battle-app moderation views; this is the one general-purpose moderation page that also shows battle data, and it was missed when F8 shipped.",
    },
    {
        "id": "F17", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "cooking_moderation answered 403 instead of 404, breaking the dark-launch-is-invisible invariant",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (cooking_moderation, cooking_moderation_approve)",
        "depends_on": "none",
        "action": "raise Http404 instead of PermissionDenied on the visibility check, matching battle_withdraw_resolve and every other gate in the app.",
        "visible_result": "A rejected dark-launch caller now gets the same 404 as every other gated page instead of a 403 that confirmed the page exists.",
        "acceptance": "ChefBattleModerationRequiresVisibilityTests tightened from assertIn(status, (403, 404)) to assertEqual(status, 404), plus a new POST case for cooking_moderation_approve; both green.",
        "forbidden": "none - this was a two-line, zero-risk alignment; the prior test already tolerated either code, so nothing else could regress.",
        "evidence": "SHIPPED v2.5.1000. Every other gate in the app, including the neighbouring battle_withdraw_resolve, answers Http404. These two answered PermissionDenied (403), confirming to a rejected caller that the page exists - the opposite of the app's own stated dark-launch principle. Previously recorded as a tolerated, documented inconsistency rather than an oversight; fixed anyway since the correction was trivial and safe.",
    },
    {
        "id": "F18", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "The admin's bulk disputed-battle reset was the one remaining place a battle could reach VOTING unrevealed",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/admin.py (reset_disputed_battles)",
        "depends_on": "F10",
        "action": "Iterate and reveal entries per battle before setting VOTING, mirroring force_reveal_entries immediately above it in the same file.",
        "visible_result": "None visible under normal play - no code path currently sets Battle.Status.DISPUTED at all, so this closes a latent gap in an admin action that would otherwise misbehave the day something does.",
        "acceptance": "ResetDisputedBattlesRevealsEntriesTests green: the action moves a DISPUTED battle to VOTING and leaves both entries is_revealed=True.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1000. reset_disputed_battles moved DISPUTED battles straight to VOTING (a _REVEAL_IMPLIED_TARGETS status) through a bare queryset .update(), the same class of gap F10/F14 closed elsewhere - just reached through a direct admin bulk update instead of a service function.",
    },
    {
        "id": "F19", "group": "Release Audit 2026-08-11 (Re-Audit Round 2)", "title": "A losing race on challenge accept surfaced a bare 500",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (challenge_respond)",
        "depends_on": "none",
        "action": "Catch IntegrityError from accept_challenge's Battle.objects.create() and show 'already answered' instead of letting it become a server error.",
        "visible_result": "A losing concurrent accept now redirects with a warning message instead of a 500 page.",
        "acceptance": "DoubleAcceptRaceReturnsFriendlyMessageTests green, simulating the race deterministically by pre-occupying the OneToOne slot rather than racing real threads for a window that proves nothing.",
        "forbidden": "Do not add a row lock to accept_challenge - Battle.challenge's unique OneToOneField constraint already guarantees the data stays correct; this is error handling for an already-safe race, not a data-integrity fix.",
        "evidence": "SHIPPED v2.5.1000. Battle.challenge is a unique OneToOneField, so two simultaneous accepts never corrupted data - the second INSERT simply failed at the database. But accept_challenge doesn't lock the challenge row and the view only caught ValueError, so the second request's IntegrityError was unhandled and reached the user as a bare 500 instead of the same 'already answered' message a slightly-later request gets from the top-of-view PENDING check.",
    },
    {
        "id": "F20", "group": "Release Audit 2026-08-11 (Round 3)", "title": "A battle could be scored as a paid draw from any pre-voting phase, with zero combat and zero moderated evidence",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (battle_detail); chef_battle/services.py (void_stalled_battle, void_stalled_battles, _STALLABLE_STATUSES); chef_battle/management/commands/expire_stale_battles.py",
        "depends_on": "none",
        "action": "battle_detail now only auto-scores a battle past end_time via calculate_battle_result when it is ACTIVE or VOTING (the only statuses battle_vote itself accepts). A battle stuck in INGREDIENT_PENALTY/COOKING/PRESENTATION past end_time routes through the new void_stalled_battle instead - cancelled, no reward to either chef. A matching cron sweep (void_stalled_battles) covers the same three statuses, wired into expire_stale_battles.py alongside the existing no-show and voting-deadline sweeps.",
        "visible_result": "A battle that never reached voting - stuck waiting on a moderator's cooking-phase approval or a cooked photo - is cancelled with no reward, instead of quietly paying both chefs a full draw for a battle nobody judged.",
        "acceptance": "StalledBattleIsVoidedNotDrawnTests green: all three stallable statuses void correctly, an unexpired stalled battle is left alone, an already-COMPLETED battle is untouched, the sweep voids in bulk, and battle_detail routes correctly for both the stalled and the still-votable case.",
        "forbidden": "Do not touch calculate_battle_result/_score_battle themselves - admin's force_complete_battles and emulation.py deliberately force a result regardless of phase, and must keep working unconditionally. The fix is which caller reaches them, not what they do once reached.",
        "evidence": "SHIPPED v2.5.1002. calculate_battle_result/_score_battle only checked status != COMPLETED, never which phase the battle was actually in; battle_detail called it for ANY non-COMPLETED battle whose end_time had passed. _score_battle's zero-vote tie-break can't distinguish 'voting never opened' from 'voting opened and tied 0-0', so a battle that never reached a votable phase was scored as a draw and paid both chefs the full second-place share - rating, reputation, seasonal score, moves - for a battle with no combat and no moderated photo. Since a loss carries no penalty, stalling was strictly better than losing honestly: a rational strategy for a chef who expected to lose. Present since the original MVP (June 2026); not a regression of F1-F19 or any G-series work. get_expired_active_battles (battle_home) and the VOTING-only cron sweep were already phase-safe and needed no change; battle_detail's inline trigger was the one unguarded caller.",
    },
    {
        "id": "F21", "group": "Release Audit 2026-08-11 (Round 3)", "title": "G1's one-slot-per-chef rule had a race across two different pending challenges to the same chef",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (accept_challenge)",
        "depends_on": "none",
        "action": "accept_challenge now locks the accepting chef's ChefBattleProfile row first, then re-checks slot_occupied_reason under that lock before creating the battle - two concurrent accepts for the same chef serialise on the lock instead of both reading the slot as free before either battle exists.",
        "visible_result": "A chef who somehow fires two near-simultaneous 'accept' requests for two different pending challenges gets one battle and one rejection instead of two live battles at once.",
        "acceptance": "AcceptChallengeSlotRaceTests green, simulating the race deterministically by committing the first accept and then calling accept_challenge for the second challenge, rather than racing real threads for a window that proves nothing.",
        "forbidden": "Do not change slot_occupied_reason's own query logic - the read was already correct, the fix is making the two-caller sequence serialise around it, not changing what it computes.",
        "evidence": "SHIPPED v2.5.1002. slot_occupied_reason was checked unlocked in the view before accept_challenge ran. Two DIFFERENT pending challenges to the same chef (nothing stops two different chefs from both challenging one free opponent), accepted near-simultaneously, both passed the check before either battle existed - F19's IntegrityError guard only protects the SAME challenge being double-accepted (unique Battle.challenge), not this case. New area: G1 shipped 2026-08-11 and had never been checked for concurrency.",
    },
    {
        "id": "F22", "group": "Release Audit 2026-08-11 (Round 3)", "title": "Clan moderation was gated the same way F8/F16 had already closed on its sibling views",
        "status": "DONE", "owner": "Bolt",
        "files": "recipes/views.py (moderate_clan)",
        "depends_on": "F8, F16",
        "action": "Require is_moderator(user) AND is_battle_visible(request), matching battle_withdraw_resolve (F8) and moderation_panel's pending_clans (F16).",
        "visible_result": "A moderator without arena access can no longer approve or reject a clan.",
        "acceptance": "ModerateClanRequiresBattleVisibilityTests green: a has_bearseeker_privileges-only moderator is 404d and the clan stays PENDING; a staff moderator can still approve it.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1002. Gated only on is_moderator() - mutates Clan.moderation_status directly (approving makes the clan publicly live) - the sibling write action to battle_withdraw_resolve, which F8 already fixed. Not previously exploitable (grant_bearseeker always also sets is_staff), but missed by both F8 and F16 because it lives in recipes/views.py, outside the chef_battle URL namespace RoutedViewAccessAuditTests enumerates.",
    },
    {
        "id": "F23", "group": "Release Audit 2026-08-11 (Round 3)", "title": "A written anti-fraud gate on real-money token purchases was never wired in",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (token_checkout_create)",
        "depends_on": "none",
        "action": "Add gate_token_purchase_velocity(wallet) to token_checkout_create's fraud gate list, alongside the suspension/fraud/age/consent gates already there.",
        "visible_result": "A buyer who has completed 5+ token orders in the last 24 hours is blocked from a 6th, with a clear message, instead of the check silently never running.",
        "acceptance": "TokenPurchaseVelocityGateTests green: the gate itself fails past the threshold and passes under it, and the checkout view now surfaces that failure as a 400 with the right message.",
        "forbidden": "none. (This card originally also flagged gate_dsa_report_threshold as deliberately left unwired pending an Owner policy call - he has since ruled on it; see F32.)",
        "evidence": "SHIPPED v2.5.1002. gate_token_purchase_velocity's docstring: 'reject if the wallet has too many completed orders in the last 24 hours' - zero call sites anywhere in the repo. token_checkout_create built its own explicit gate list and left it out, on the one real-money purchase path in the app. Same gap GreenBear's 2026-08-10 audit found for a different reason; it survived two 'closed' rounds of security fixes (F1-F19) before being wired in here.",
    },
    {
        "id": "F32", "group": "Owner Directive 2026-08-11", "title": "gate_dsa_report_threshold ruled on: blocking, not log-only",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/fraud.py (gate_dsa_report_threshold); chef_battle/views.py (token_checkout_create)",
        "depends_on": "F23",
        "action": "Add gate_dsa_report_threshold(author) to token_checkout_create's fraud gate list, alongside gate_token_purchase_velocity. Corrected the gate's own docstring, which said 'does not block - logs only' while its implementation already returned passed=False past the threshold - the docstring was wrong, not the code; wiring it in makes the two agree.",
        "visible_result": "A chef whose account has 5+ moderator-logged DSA reports can no longer buy tokens until a moderator reviews the account and resets the count; the checkout returns a 400 with a support-contact message instead of silently letting the purchase through.",
        "acceptance": "DsaReportThresholdGateTests green: the gate fails at/above the threshold and passes under it, and the checkout view surfaces the failure as a 400 with the right message.",
        "forbidden": "Do not add an is_immortal/OWNER_SLUG exemption here - neither gate_suspended_account nor gate_fraud_flagged, its two sibling blocking gates already in this same list, carry one; matching that existing precedent, not inventing a new one.",
        "evidence": "SHIPPED v2.5.1008. F23 (2026-08-11) found this gate written but unwired and deliberately left it alone, flagging the block-vs-log-only question as the Owner's to rule on rather than the fix's to invent. Owner's ruling, 2026-08-11: blocking. dsa_reported_count is moderator-set only (chef_battle admin), never auto-incremented by an automated pipeline, so the block only ever fires after a human has already logged reports against the account.",
    },
    {
        "id": "F33", "group": "Owner Directive 2026-08-11", "title": "F24's residual cross-season race closed with a DB-level constraint",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/models.py (Season.Meta.constraints); chef_battle/migrations/0090_f24_season_only_one_active.py; chef_battle/season_service.py (activate_season, create_season)",
        "depends_on": "F24",
        "action": "Added a partial unique constraint on Season.status filtered to status=\"active\" - the database itself now refuses a second row with status=active, regardless of what any Python-level check saw. activate_season and create_season(activate=True) both catch the resulting IntegrityError and re-raise it as the same friendly ValueError their existing unlocked pre-check already gives the common case, matching F19's precedent for turning a DB-level race guard into a user-facing message.",
        "visible_result": "None visible under normal play - two DIFFERENT seasons activated at once (not the same-season self-overlap F24 already covered) now has its loser refused by the database instead of both succeeding.",
        "acceptance": "SeasonOnlyOneActiveConstraintTests green: with get_active_season() monkeypatched to simulate the race window (both callers seeing nothing active), activating a second season while the first is active still raises, for both activate_season and create_season(activate=True); the full SeasonEngineTests/SeasonSignalTests/SeasonCommittedSignalTests/FactionSeasonReceiverTests/SeasonStandingCarriesTheRecordTests/SeasonRulesAreDataTests regression set (including roll_seasons' normal close-then-activate rollover) stays green.",
        "forbidden": "Do not add an is_immortal/OWNER_SLUG exemption or any other bypass of the constraint - a season is not a per-chef concept, nothing about section 18 applies to it.",
        "evidence": "SHIPPED v2.5.1008. F24 (2026-08-11) locked a season's OWN row against self-overlap but explicitly left the cross-season case open, since activate_season's get_active_season() check reads a DIFFERENT row unlocked - two DIFFERENT seasons activated at once each lock their own row and never collide, so both could see nothing active and both pass. Row locking cannot close a race across two different rows; only the database can. Owner's ruling, 2026-08-11: close it. One row already active in production (id=1, 'Season 1') at migration time, so the constraint applied cleanly with no data conflict.",
    },
    {
        "id": "F34", "group": "Independent Audit 2026-08-11", "title": "Admin force-reveal could double-award an already-scored battle",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/admin.py (force_reveal_entries)",
        "depends_on": "none",
        "action": "Materialise only the candidate battle ids up front, then lock and recheck each row inside its own transaction before writing VOTING - a battle a concurrent scorer completed while the batch was still working through earlier rows is skipped instead of forced back to VOTING.",
        "visible_result": "None visible under normal play - a battle that a scorer completes naturally mid-batch keeps its COMPLETED result instead of being reopened for a second, duplicate scoring pass.",
        "acceptance": "AdminForceRevealEntriesLockedTests green: FOR UPDATE asserted in captured SQL, and a battle completed mid-batch (injected via a one-shot patch on the first select_for_update() call, not real threads) stays COMPLETED rather than being forced to VOTING.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. Independently reported and verified by direct code read before any fix: the filtered queryset was fetched ONCE at loop start, then each row written with a plain battle.save() - no lock, no recheck. A battle a scorer completes naturally while the loop is still on earlier rows got silently forced back to VOTING from the stale in-memory copy, and the very next battle_detail visit (F20's auto-trigger) would re-run calculate_battle_result on it, double-awarding wins/rating/crown/moves. Present since this action was written; missed by all four internal audit rounds - admin.py's bulk actions were never checked for this class of race, only for the reveal-flag gap F18 already closed on its sibling action.",
    },
    {
        "id": "F35", "group": "Independent Audit 2026-08-11", "title": "Admin cancel could overwrite an already-scored battle back to CANCELLED",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/admin.py (cancel_battles)",
        "depends_on": "none",
        "action": "Same restructuring as F34: candidate ids materialised up front, each row locked and rechecked inside its own transaction before writing CANCELLED.",
        "visible_result": "None visible under normal play - a battle that finishes naturally mid-batch keeps its COMPLETED result instead of being left CANCELLED while its winner's rewards stay banked.",
        "acceptance": "AdminCancelBattlesLockedTests green: FOR UPDATE asserted; a battle completed mid-batch (same one-shot-patch simulation as F34) stays COMPLETED rather than being overwritten to CANCELLED.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. Same shape and same independent report as F34, its neighbour in this file. A battle overwritten to CANCELLED after already paying out wins/rating/crown/moves is worse than F34's case - the battle record itself now says the fight never happened while the ledger says otherwise.",
    },
    {
        "id": "F36", "group": "Independent Audit 2026-08-11", "title": "A withdrawal could be resolved twice, doubling the penalty",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/withdrawal_service.py (resolve_withdrawal)",
        "depends_on": "F29",
        "action": "Lock the BattleWithdrawal row itself (F29 only locked the Battle it cancels) and re-check CLOSED under that lock before doing anything else.",
        "visible_result": "None visible under normal play - a double-click or two moderator tabs resolving the same withdrawal now gives one -15 rating / -3 reputation penalty, not -30/-6.",
        "acceptance": "ResolveWithdrawalLocksTheWithdrawalTests green: FOR UPDATE asserted against chef_battle_battlewithdrawal specifically (not just the battle F29 already locks), and a second resolve on an independently-fetched stale withdrawal copy is refused, leaving the penalty applied exactly once.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. My own F29 fix (this same session) locked the Battle a withdrawal cancels but never locked the BattleWithdrawal row itself - the CLOSED check at the top of the function ran unlocked, before the transaction even opened. Independently found and reported; verified true by direct code read. A gap in my own prior fix, not a pre-existing bug I missed for the first time.",
    },
    {
        "id": "F37", "group": "Independent Audit 2026-08-11", "title": "A battle gift could debit real tokens after the battle already finished",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (send_battle_artifact)",
        "depends_on": "none",
        "action": "Move the battle.status check inside the transaction, against a freshly select_for_update()'d row, immediately before the debit.",
        "visible_result": "A viewer sending a battle gift to a battle that finished in the last instant is refused and charged nothing, instead of losing real tokens for an artifact that locks to a battle that can never use it.",
        "acceptance": "SendBattleArtifactLocksBattleTests green: FOR UPDATE asserted; a battle updated to COMPLETED underneath a stale battle object refuses the gift and leaves the sender's wallet untouched, no ViewerBattleGift row created.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. battle.status was checked against whatever object the caller passed in, before the transaction opened; debit_tokens and the gift/artifact-lock creation ran with no re-check. This is the one finding in this batch with a direct real-money impact on a viewer, not just a chef's game state.",
    },
    {
        "id": "F38", "group": "Independent Audit 2026-08-11", "title": "Challenge accept/refuse/expire were not serialised against each other",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (accept_challenge, refuse_challenge, expire_stale_challenges); chef_battle/views.py (challenge_respond)",
        "depends_on": "F19, F21",
        "action": "All three now lock the BattleChallenge row and re-check status == PENDING before proceeding; expire_stale_challenges restructured like F34/F35 (materialise ids, lock+recheck per row). refuse_challenge now raises ValueError on a stale challenge instead of unconditionally penalising; the view's refuse branch catches it the same way its accept branch already does.",
        "visible_result": "A chef who refuses a challenge that was simultaneously accepted (or already expired) gets a clear error instead of an incorrect refusal penalty, and the challenge's own status can no longer disagree with whether a Battle exists for it.",
        "acceptance": "ChallengeTransitionsAreLockedTests green: FOR UPDATE asserted for all three functions against chef_battle_battlechallenge; refusing/accepting a challenge that was simultaneously accepted/refused (stale-object simulation) is refused and applies no penalty, leaving the real transition's outcome untouched.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. Battle.challenge's unique OneToOneField already stops a SECOND battle from ever being created for one challenge (F19) - that part of the data was always safe. What was never covered: the CHALLENGE's own status could still land as REFUSED or EXPIRED in the same instant a live Battle exists for it, because none of the three writers locked the row or checked what the others had done. refuse_challenge's penalty (reputation, Battle Moves) would then fire against a chef who had, in fact, just been accepted.",
    },
    {
        "id": "F39", "group": "Independent Audit 2026-08-11", "title": "award_moves' once-per-object and anti-farm checks had no lock",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/energy_service.py (award_moves)",
        "depends_on": "none",
        "action": "Lock the chef's ChefBattleProfile row first, before the once-per-object .exists() dedup check and the anti-farm .count(), serialising the whole function per chef.",
        "visible_result": "None visible under normal play - the balance write itself was already safe (a DB-side F()-expression capped increment); this closes the two read-then-act checks that fed it.",
        "acceptance": "AwardMovesLocksTheProfileTests green: FOR UPDATE asserted against chef_battle_chefbattleprofile; a re-published object is not awarded twice; infinite_moves/cap behaviour unchanged after moving the profile fetch earlier in the function.",
        "forbidden": "Do not add a DB-level uniqueness constraint here instead - the generic-FK reference (reference_content_type/reference_object_id) makes a clean partial-unique index a bigger, riskier change than this session's time allows to verify fully; the row lock closes the same window with the pattern already established everywhere else this session.",
        "evidence": "SHIPPED v2.5.1010. The once-per-object dedup (BattleMoveTransaction.objects.filter(...).exists()) and the like anti-farm count (_anti_farm_like_count, a plain .count()) both had nothing serialising two concurrent award_moves calls for the same chef - a re-approval signal firing twice, or two likes landing at once, could both read \"not yet awarded\"/\"under the cap\" before either committed, doubling moves and the uncapped faction/clan/reputation side-effects, or letting more than LIKE_ANTI_FARM_MAX_PER_SOURCE through in a day. Not provable by a sequential test (one connection always sees its own prior writes regardless of locking) - closed on the mechanism, same reasoning as F40 below.",
    },
    {
        "id": "F40", "group": "Independent Audit 2026-08-11", "title": "Two chefs declaring a menu at once could leave the battle stuck forever",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (declare_menu)",
        "depends_on": "none",
        "action": "Lock the battle row before the own-declaration and opponent-count checks and before computing both_declared.",
        "visible_result": "None visible under normal play - two chefs declaring within the same instant now serialise, so the second call correctly sees the first's committed menu instead of missing it under READ COMMITTED.",
        "acceptance": "DeclareMenuLocksBattleTests green: FOR UPDATE asserted; both chefs declaring sequentially still transitions the battle to ACTIVE (regression - the READ COMMITTED gap itself needs two real concurrent connections to reproduce and is not provable by a sequential test).",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. The most severe LOW-effort-to-trigger, HIGH-consequence finding in this batch: both_declared was computed from two bare .exists() checks with no lock. Two chefs declaring at nearly the same instant each ran under plain READ COMMITTED - neither transaction could see the other's not-yet-committed row, so BOTH computed both_declared as False, both menus landed after commit, and nothing ever moved the battle to ACTIVE. Worse than a lost update: a permanent soft-lock, since re-declaring is refused once a menu exists for that chef, and no sweep anywhere detects 'both menus present but still MENU_LOCKED'. Trapped both chefs in a battle neither could escape without operator intervention.",
    },
    {
        "id": "F41", "group": "Independent Audit 2026-08-11", "title": "Cooking-phase approval could resurrect a cancelled battle",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (approve_cooking_phase)",
        "depends_on": "none",
        "action": "Lock the battle row and re-check INGREDIENT_PENALTY under the lock before touching surviving_ingredients or status; sync the result back onto the caller's own object so operator_force_status's audit event (which reads battle.status after the call) still sees the real outcome.",
        "visible_result": "A moderator approving cooking phase on a stale queue page for a battle that was cancelled or voided in the meantime gets a clear error, instead of the battle silently jumping CANCELLED -> COOKING.",
        "acceptance": "ApproveCookingPhaseLocksBattleTests green: FOR UPDATE asserted; a battle cancelled underneath a stale battle object refuses the approval and stays CANCELLED.",
        "forbidden": "Do not change the function's return-object identity - operator_force_status (the force-transition path) calls this with an already-locked battle object and reads battle.status off it immediately after for its own audit event; the fix syncs status onto the caller's object rather than returning a different one.",
        "evidence": "SHIPPED v2.5.1010. Same class as F34/F35/F37: a status check against whatever object the caller's request loaded, before the transaction opened, with nothing re-checking it once inside. Same admin/moderator-only exposure as F34/F35 - not reachable by an ordinary chef.",
    },
    {
        "id": "F42", "group": "Independent Audit 2026-08-11", "title": "The four new G13 pages reloaded chef_battle.css a second time",
        "status": "DONE", "owner": "Bolt",
        "files": "templates/chef_battle/battle_history.html; templates/chef_battle/season_detail.html; templates/chef_battle/crown_holder.html; templates/chef_battle/vote_review.html",
        "depends_on": "the chef_battle.css double-load cleanup, 2026-08-11",
        "action": "Delete the extra_head override on all four templates - identical to the mechanical fix already applied to 40 other templates, just reintroduced here because these four were written after that cleanup ran.",
        "visible_result": "Each of the four pages now downloads and parses chef_battle.css once, from base.html, instead of twice.",
        "acceptance": "G13TemplatesCssIsLoadedOnceTests green: all four routes render 200 and contain exactly one 'chef_battle.css' occurrence in the response body.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1010. GreenBear's G13 work (v2.5.1005) added these four templates after the round-3 CSS cleanup (v2.5.1003) had already fixed the other 40 - a straightforward case of new code landing after a cleanup pass and reintroducing the exact pattern the cleanup removed. LOW severity: 138,630 bytes fetched and parsed twice, no functional or security impact.",
    },
    {
        "id": "F43", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "A paid Stripe checkout could be shown as cancelled, or vice versa",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (token_checkout_cancel)",
        "depends_on": "none",
        "action": "Lock the TokenOrder row and recheck its status under the lock before writing CANCELLED, matching the discipline token_stripe_webhook's own handlers (_handle_checkout_completed, _handle_checkout_expired) already use.",
        "visible_result": "A buyer landing on the Stripe-return cancel page for an order the webhook already completed sees it correctly, instead of the browser page racing the webhook to decide the final status.",
        "acceptance": "TokenCheckoutCancelLocksTheOrderTests green: FOR UPDATE asserted against chef_battle_tokenorder; an order already COMPLETED is not overwritten to CANCELLED by a visit to the cancel page.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported (second round, run fresh against origin/main after F34-F42 shipped) and verified by direct code read: token_stripe_webhook's own handlers were already correctly locked and rechecked - this view was the one unlocked writer of TokenOrder.status left standing, racing them.",
    },
    {
        "id": "F44", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "A payout could be paid via Stripe and rejected for re-payout at the same time",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (_execute_stripe_connect_transfer)",
        "depends_on": "none",
        "action": "Lock the PayoutRequest row and recheck it is still APPROVED immediately before calling Stripe (closing the gap between approve_payout_request's commit and the transfer starting); pass a stable idempotency_key on stripe.Transfer.create() (stops OUR OWN retries creating a second transfer); log at CRITICAL, rather than silently overwrite, if the record is no longer APPROVED by the time the transfer succeeds (the residual window during the live Stripe call itself - money has moved by then, so PAID is still the honest status, but a human must reconcile it).",
        "visible_result": "None visible under normal play. A reject landing between approval and the transfer call is now honoured - no transfer is attempted, and the freed reward records are not exposed to a real double payout from that specific race.",
        "acceptance": "PayoutTransferLockedAgainstRejectRaceTests green: a payout no longer APPROVED at transfer time skips the Stripe call entirely (stripe.Transfer.create asserted not called); a successful transfer passes idempotency_key=f\"payout-transfer-{pk}\"; reject_payout_request still works normally from APPROVED when no transfer is in flight.",
        "forbidden": "Do not remove APPROVED from reject_payout_request's allowed source statuses - that is the admin's legitimate way to give up on a payout whose transfer failed and is stuck (approve_payout_request explicitly leaves it APPROVED on transfer failure for exactly this reason).",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: approve_payout_request commits APPROVED, then calls the transfer function OUTSIDE any lock; the transfer function itself, on success, blindly wrote PAID regardless of what reject_payout_request might have done to the record in the meantime - and reject explicitly returns ISSUED reward records to APPROVED so the chef can re-request, which is exactly the mechanism a second, legitimate-looking payout could ride to a real double payment. The most severe finding of this round.",
    },
    {
        "id": "F45", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "A refund and a dispute on the same order could each claw back the full amount",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (handle_token_order_chargeback)",
        "depends_on": "none",
        "action": "Gate the wallet-deduction block on whether the order was ALREADY in a clawed-back state (DISPUTED or REFUNDED) when this call started; the reward-reversal block needed no change, being already naturally idempotent (a second pass finds nothing left in PENDING/QUEUED to reverse).",
        "visible_result": "A buyer's balance is debited once per underlying charge dispute, even if Stripe sends both a refund and a dispute event for it - tokens from OTHER, unrelated purchases are no longer swept up by the second event.",
        "acceptance": "TokenChargebackServiceTests green (new case added): a chargeback following an already-processed refund deducts 0 tokens and leaves an unrelated top-up untouched, while still recording the new terminal status for audit.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: charge.refunded and charge.dispute.created are two different Stripe events with different event ids: the webhook layer's own ProcessedTokenStripeEvent dedup (keyed on event_id) does not catch a genuine second event for the same underlying charge, and handle_token_order_chargeback itself had no status guard - each call independently deducted min(wallet.balance, order.tokens).",
    },
    {
        "id": "F46", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "A closed withdrawal could be silently reopened and re-resolved",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/withdrawal_service.py (decide_withdrawal)",
        "depends_on": "F36",
        "action": "Lock the BattleWithdrawal row and re-check AWAITING_OPPONENT under the lock before writing the opponent's decision.",
        "visible_result": "None visible under normal play - a late opponent decision working from a stale copy of an already-CLOSED withdrawal is now refused instead of reopening it.",
        "acceptance": "DecideWithdrawalLocksTheWithdrawalTests green: FOR UPDATE asserted against chef_battle_battlewithdrawal; a decide_withdrawal call on a withdrawal a moderator already closed (stale-object simulation) raises WithdrawalNotAllowed and the withdrawal stays CLOSED.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: F36 (same day, earlier round) locked resolve_withdrawal against a double-resolve, but decide_withdrawal - the OTHER writer of a withdrawal's status, one step earlier in the flow - had no lock of its own. A late decide_withdrawal call could reopen an already-CLOSED withdrawal from AWAITING_OPPONENT-looking staleness, handing resolve_withdrawal a second legitimate pass at it - a different route to the same double-penalty class F36 closed.",
    },
    {
        "id": "F47", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "F39's own fix locked the profile row but never used the locked copy",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/energy_service.py (award_moves)",
        "depends_on": "F39",
        "action": "Use the row select_for_update() actually returns for the headroom/cap calculation, instead of discarding it and reading the earlier, unlocked _get_profile() fetch.",
        "visible_result": "None visible under normal play - the once-per-object dedup was already correctly serialised by the lock; only the cap arithmetic downstream of it could read a stale balance.",
        "acceptance": "Covered by the existing AwardMovesLocksTheProfileTests (test_infinite_moves_and_cap_behaviour_survive_the_refactor) - regression only; the true-concurrency case this closes needs two separate connections and is not sequentially provable, same as F39 itself.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: F39 added `ChefBattleProfile.objects.select_for_update().get(pk=profile.pk)` but never assigned its return value to anything - the lock was real (correctly serialising the once-per-object/anti-farm checks that run as separate queries after it) but the cap/headroom math a few lines later still read `profile.battle_moves` off the ORIGINAL, unlocked fetch. A ledger entry could then record more moves awarded than the DB-side capped increment actually applied. My own mistake, caught by an independent second-round audit within hours of shipping F39.",
    },
    {
        "id": "F48", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "F40's own fix locked the battle row but never rechecked its status",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (declare_menu)",
        "depends_on": "F40",
        "action": "Use the row select_for_update() actually returns throughout the function, and re-check status == MENU_LOCKED against it before creating anything.",
        "visible_result": "A stale menu declaration on a battle cancelled by another path is now refused instead of writing the battle straight to ACTIVE.",
        "acceptance": "DeclareMenuLocksBattleTests green (new case added): a declare_menu call on a battle cancelled underneath a stale battle object (deterministic stale-copy simulation, unlike the READ COMMITTED gap F40 itself closes) raises ValueError and creates no ingredients.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: same shape as F47 - F40 added the lock but discarded its return value, so the MENU_LOCKED precondition check (which runs before the transaction even opens) was never re-verified once inside it. Unlike F47, this specific gap IS deterministically testable, since it is a stale-object bug rather than a pure transaction-isolation race - caught the same way F29/F41 are tested.",
    },
    {
        "id": "F49", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "Issuing a challenge did not lock the issuer's own one-slot rule",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (challenge_create)",
        "depends_on": "F21",
        "action": "Lock the challenger's own ChefBattleProfile row and re-check slot_occupied_reason under it, immediately before form.save() - the same mutex accept_challenge (F21) already takes on the ACCEPTING chef, applied here to the ISSUING chef's own slot.",
        "visible_result": "None visible under normal play - a double-submitted challenge form now serialises instead of risking two pending challenges from one chef.",
        "acceptance": "ChallengeCreateLocksTheSlotTests green: a normal challenge still creates successfully with the profile row locked (FOR UPDATE asserted); a second challenge once the slot is occupied is refused, same as today.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: F21 locked the ACCEPTING chef's profile inside accept_challenge, but challenge_create's own slot check for the ISSUING chef ran fully unlocked, with form.save() right after it - the same TOCTOU shape F21 had already closed on the other side of the same rule.",
    },
    {
        "id": "F50", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "The challenge-response view had its own unlocked expiry writer, bypassing F38",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (challenge_respond)",
        "depends_on": "F38",
        "action": "Lock the challenge row and re-check status == PENDING under the lock before writing EXPIRED.",
        "visible_result": "A challenge already accepted by a concurrent request is no longer at risk of being overwritten to EXPIRED by a stale view load, leaving its live Battle intact and correctly reflected.",
        "acceptance": "ChallengeRespondExpiryLocksTheChallengeTests green: FOR UPDATE asserted against chef_battle_battlechallenge; an already-ACCEPTED challenge (via accept_challenge) is unaffected by a later request to this same view.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: F38, earlier the same day, locked accept_challenge/refuse_challenge/expire_stale_challenges - three writers of a challenge's status - but missed this FOURTH one, a small inline expiry check sitting directly in the challenge_respond view, never routed through any of the three locked functions.",
    },
    {
        "id": "F51", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "A withdrawal request could be created against an already-finished battle",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/withdrawal_service.py (request_withdrawal)",
        "depends_on": "F29",
        "action": "Lock the battle row and re-check status in ACTIVE_STATUSES under the lock, alongside the existing allowance-profile lock.",
        "visible_result": "A withdrawal request against a battle that finished in the same instant is now refused up front, instead of creating an orphaned request and spending the chef's allowance for nothing.",
        "acceptance": "RequestWithdrawalLocksTheBattleTests green: FOR UPDATE asserted against chef_battle_battle; a request against a battle updated to COMPLETED underneath it is refused and creates no BattleWithdrawal row.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: can_withdraw's battle-status check ran unlocked before request_withdrawal's own transaction opened, which locked only the chef's allowance profile. resolve_withdrawal (F29) already refuses to CANCEL a battle that turns out to have finished, so this could not corrupt the battle outcome - but it still wasted the chef's allowance and left an orphaned withdrawal request open against a battle that no longer needed one.",
    },
    {
        "id": "F52", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "reset_disputed_battles repeats the F34/F35 unlocked-batch pattern",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/admin.py (reset_disputed_battles)",
        "depends_on": "F34, F35",
        "action": "Same restructuring as F34/F35: materialise candidate ids up front, then lock and recheck each row inside its own transaction before writing VOTING.",
        "visible_result": "None visible under normal play - a DISPUTED battle cancelled by another path mid-batch is no longer silently reset to VOTING.",
        "acceptance": "AdminResetDisputedBattlesLockedTests green: FOR UPDATE asserted; the same one-shot mid-batch interleaving simulation used for F34/F35 confirms a battle cancelled between rows keeps its CANCELLED status.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: this action, admin.py's third bulk battle-status writer alongside force_reveal_entries and cancel_battles, was deliberately left out of the F34/F35 fix - it is a rare, narrow-status (DISPUTED only) action with lower practical exposure than its two neighbours, but the code shape was identical and an independent audit correctly flagged the inconsistency of fixing two of three siblings.",
    },
    {
        "id": "F53", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "Battle emulation had no lock at either the start or step level",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/emulation.py (start_emulation, emulation_step)",
        "depends_on": "none",
        "action": "start_emulation now locks one of the two (always-existing) bots' own ChefBattleProfile rows as a mutex before its 'one already running' check. emulation_step is now wrapped in @transaction.atomic with select_for_update() on the initial battle fetch, holding the row lock for the whole multi-stage call - the domain services each branch calls (approve_cooking_phase, calculate_battle_result, etc.) already take the same lock themselves, and a connection never blocks on a lock it already holds.",
        "visible_result": "None visible under normal play - a double-click on Start Emulation or the Step button, or either racing a Master Console Cancel on the same emulation battle, now serialises instead of risking two emulation battles or a step overwriting a concurrent cancellation.",
        "acceptance": "BattleEmulationTests green (two new cases): FOR UPDATE asserted for both functions; the full 12-step emulated lifecycle (existing regression test) and the existing 'second emulation blocked' test are unaffected.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: both functions are Owner-only (single operator), so the practical exposure is limited to a double-click rather than an external actor - but the fix is real and complete, closing the same class of gap as everywhere else in this batch. There is no natural single row representing 'an emulation is running', so the fix locks one of the two bots' own profile rows instead, the same 'lock a stable existing row as mutex' pattern F30 already established for the combat artifact loadout.",
    },
    {
        "id": "F54", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "demo_battle --end repeats the F35 unlocked-write pattern",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/management/commands/demo_battle.py",
        "depends_on": "F35",
        "action": "Lock the battle row and recheck it is not already in a terminal status before writing CANCELLED.",
        "visible_result": "Running `manage.py demo_battle --end` on a battle that finished naturally in the meantime now reports it as already finished, instead of overwriting it to CANCELLED.",
        "acceptance": "DemoBattleEndLocksTheBattleTests green: --end still cancels a running battle normally; a battle already COMPLETED is left untouched.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: same unlocked plain-save pattern as F35, just in a management command rather than an admin action. LOWEST practical severity in this batch - the command is only reachable by whoever already has shell/SSH access to the server, the same tier of access that could deploy new code outright.",
    },
    {
        "id": "F55", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "The recipe-edit battle-lock message named Chef Battles to every author",
        "status": "DONE", "owner": "Bolt",
        "files": "recipes/views.py (RecipeUpdateView._battle_lock_redirect)",
        "depends_on": "none",
        "action": "Keep the edit block exactly as-is; branch the MESSAGE TEXT on is_battle_visible(request) - staff/superusers still see the real reason, everyone else sees a neutral 'can't be edited right now' message.",
        "visible_result": "An AUTHOR-tier chef whose recipe is locked by a battle they cannot otherwise see now gets a message that does not name Chef Battles at all.",
        "acceptance": "RecipeEditBattleLockMessageIsNeutralTests green: a plain author sees the neutral message and not the phrase 'live Chef Battle'; staff still sees the real reason.",
        "forbidden": "Do not weaken or remove the edit block itself - drifting ingredient-line indices mid-battle is the real invariant being protected; only the WORDING shown to a non-visible viewer changes.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified by direct code read: this is a genuine dark-launch information leak, the same class of contract violation F1-F5's original audit closed elsewhere, just never checked on this specific message. LOW severity - it reveals that Chef Battles exists and that this one recipe is in one, nothing more; no other data is exposed.",
    },
    {
        "id": "F56", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "Dead-code audit doc named the wrong file for hydrateFixtures()",
        "status": "DONE", "owner": "Bolt",
        "files": "docs/chef_battle/ARENA_DEAD_CODE_AUDIT.md",
        "depends_on": "none",
        "action": "Correct the TEST-EMULATION row to name arena_deck.js, where hydrateFixtures() actually lives, instead of arena_render.js.",
        "visible_result": "None - documentation only.",
        "acceptance": "grep confirms hydrateFixtures() exists in arena_deck.js and not in arena_render.js.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified directly: a plain factual error in the dead-code audit table, no code impact.",
    },
    {
        "id": "F57", "group": "Independent Audit 2026-08-11 (Round 2)", "title": "The dispatch-queue summary kept calling four closed cards \"actionable\"",
        "status": "DONE", "owner": "Bolt",
        "files": "docs/ARENA_BATTLE_PLAN.md (section 5)",
        "depends_on": "none",
        "action": "Rewrote the section 5 summary to state each of the four cards' real, current status (A19 DONE, G01 DONE, VD1 DONE, MC02 DELETED - all per their own rows in the same document) instead of continuing to call all four 'actionable'.",
        "visible_result": "None - documentation only.",
        "acceptance": "Section 5 no longer contradicts §1's own G01-closed note or the individual A19/VD1/MC02/G01 rows later in the same file.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1012. Independently reported and verified directly: the queue was 'cleaned and synchronised 2026-08-09' with these four cards genuinely open at the time, but the summary sentence was never updated as each one closed over the following two days, even though the individual table rows further down the SAME document were each updated correctly.",
    },
    {
        "id": "F58", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "F43 fixed only one direction of the checkout race - a paid customer could still get zero tokens",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/stripe_services.py (_handle_checkout_completed)",
        "depends_on": "F43",
        "action": "Broaden the webhook's own guard: a confirmed-paid Stripe event may now complete an order from PENDING, CANCELLED or EXPIRED - not PENDING only. REFUNDED/DISPUTED still bail, since money already came back out on those and crediting on top would be a new bug.",
        "visible_result": "A customer whose browser-return cancel page won the race and marked their order CANCELLED still gets their tokens once the real paid webhook arrives, instead of a permanently cancelled order for a real charge.",
        "acceptance": "PaidWebhookOverridesCancelledOrderTests green: a paid event credits an order from CANCELLED or EXPIRED; a paid event does NOT recredit a REFUNDED order; the normal PENDING path is unaffected.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. F43's fix locked token_checkout_cancel against overwriting an already-COMPLETED order - correct, but only one of the two directions the race can go. The webhook's own guard (\"must still be PENDING\") was never touched, so if the cancel page's write landed FIRST, the webhook - even with genuine Stripe confirmation that the customer paid - would log a warning and walk away, leaving the order permanently 'cancelled' with zero tokens credited for a real charge. A paid Stripe event is ground truth and must be able to override a premature local guess.",
    },
    {
        "id": "F59", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "F44 reduced the double-payout window but never closed it - a durable PROCESSING status now does",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/models.py (PayoutRequest.Status); chef_battle/migrations/0091_f59_payout_processing_status.py; chef_battle/services.py (_execute_stripe_connect_transfer, reject_payout_request unaffected by construction); chef_battle/admin.py (hold_payout_requests)",
        "depends_on": "F44",
        "action": "Added PayoutRequest.Status.PROCESSING. _execute_stripe_connect_transfer now transitions APPROVED -> PROCESSING in its own committed transaction BEFORE calling Stripe, and PROCESSING -> PAID on success or back to APPROVED on failure/exception. reject_payout_request's allowed-source-status list already excluded anything but PENDING/UNDER_REVIEW/APPROVED, so PROCESSING is refused with no further code change there; hold_payout_requests (admin bulk action) now excludes it explicitly alongside PAID/REVERSED.",
        "visible_result": "None visible under normal play - a reject or a compliance hold landing anywhere from approval through the live Stripe call is now refused outright while the record is PROCESSING, instead of racing a transfer that could still send money regardless.",
        "acceptance": "PayoutProcessingStatusBlocksRejectDuringTransferTests green: a mock Stripe call reads the LIVE database status from inside itself and observes PROCESSING, not APPROVED, proving the transition is committed before the network call, not merely claimed; reject is refused with status still PROCESSING; a successful transfer reaches PAID; a failed transfer reverts to APPROVED for the existing retry path; the admin hold action leaves PROCESSING untouched.",
        "forbidden": "Do not attempt to hold a DB lock across the Stripe network call itself - that trades a rare race for a guaranteed connection-pool exhaustion risk under any real load; the PROCESSING status is the correct fix precisely because it does not require that.",
        "evidence": "SHIPPED v2.5.1014. F44 (earlier the same day) added a pre-flight recheck and an idempotency key, which closed the gap between approve's commit and the transfer starting - but explicitly left the live-network-call window open, logging CRITICAL rather than preventing it, because nothing marked the record as 'a transfer is happening right now' in a way reject/hold could see and refuse to act on. A durable status accomplishes exactly that. One row already migrated cleanly (choices-only alteration, no schema risk).",
    },
    {
        "id": "F60", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "A chargeback never touched the chef's already-open payout request",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (handle_token_order_chargeback, approve_payout_request)",
        "depends_on": "none",
        "action": "handle_token_order_chargeback now also places the chef's own PENDING/UNDER_REVIEW/APPROVED payout requests ON_HOLD (PROCESSING/PAID/REVERSED left alone - a transfer already in flight or done is not something a hold can undo). approve_payout_request separately re-checks ChefBattleProfile.payout_blocked and refuses to approve if set, closing the case where a moderator clears a hold without noticing the flag.",
        "visible_result": "A chargeback on a chef's token purchase now automatically freezes any payout request they already have open, instead of relying on an admin noticing and manually running the separate 'put on hold' action.",
        "acceptance": "ChargebackHoldsExistingPayoutsTests green: a chargeback holds an open payout and reports the count; an already-PAID payout is left untouched; approval is refused once payout_blocked is set even if the payout's own status shows PENDING again.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. handle_token_order_chargeback set ChefBattleProfile.payout_blocked=True, and check_payout_eligibility already read that flag - but only at the moment a chef tries to create a NEW request. A request already sitting open when the chargeback landed sailed through approve_payout_request untouched, since that function never checked the flag at all - a chef under active dispute could still be paid real money out of disputed funds.",
    },
    {
        "id": "F61", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "A reward \"locked\" for a payout was reservable in name only",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (expire_rewards, reverse_reward)",
        "depends_on": "none",
        "action": "Both functions now exclude/refuse RewardRecords whose status_note still starts with \"Locked for PayoutRequest #\" - the exact text create_payout_request writes when it reserves a record, and the exact text reject_payout_request overwrites when it releases one.",
        "visible_result": "A reward record reserved for an open payout request can no longer be silently expired by the nightly sweep or reversed by an admin while that payout is still pending, under review or approved.",
        "acceptance": "RewardReservationIsEnforcedTests green: expire_rewards skips a locked record and still expires an unlocked one; reverse_reward refuses a locked record; a rejected payout's record shows the released status/note (APPROVED, note cleared) confirming the exclusion's own precondition no longer holds once genuinely free.",
        "forbidden": "Do not build a proper FK-based reservation (a nullable locked_for_payout field on RewardRecord) as part of this fix - a real schema relation is the more correct long-term design, but the existing status_note convention is already used consistently by every writer (create_payout_request writes it, reject_payout_request clears it) and closes the actual finding without a data migration; flagged for a future cleanup, not this one.",
        "evidence": "SHIPPED v2.5.1014. create_payout_request's only reservation mechanism is a status_note string, no schema relation. Neither expire_rewards (a cron sweep) nor reverse_reward (an admin action) ever read it, so both could free tokens an open PayoutRequest had already frozen an amount-and-EUR snapshot against - the request would then pay out for tokens that, by the time Stripe actually moved money, no longer existed.",
    },
    {
        "id": "F62", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "Combat actions could still land after a battle stopped being ACTIVE",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (submit_combat_action)",
        "depends_on": "F30",
        "action": "Lock the battle row and re-check status == ACTIVE under the lock, at the very top of the function - before F30's own (narrower) artifact-loadout mutex, which is unaffected.",
        "visible_result": "A combat action submitted the instant a battle is cancelled by another path is now refused, instead of deducting moves, consuming artifacts and creating a round on a battle the game no longer considers live.",
        "acceptance": "CombatActionLocksBattleAndRechecksStatusTests green: FOR UPDATE asserted against chef_battle_battle; a submission against a battle cancelled underneath a stale battle object is refused and creates no BattleCombatAction.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. Found by an exhaustive codebase sweep for the exact anti-pattern F47/F48 turned out to be: a select_for_update().get() call whose return value is discarded, leaving an EARLIER, unlocked status check as the only precondition ever enforced. F30 (same day, an earlier round) added exactly such a discarded lock here, but only as a mutex for the artifact loadout count - it never touched the ACTIVE check at the top of the function, which had no lock of any kind, in code that predates this entire audit arc.",
    },
    {
        "id": "F63", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "Ingredient locks and shots could still be recorded after the biathlon ended",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (place_ingredient_lock, fire_ingredient_shot)",
        "depends_on": "none",
        "action": "Both functions now re-check status == INGREDIENT_PENALTY against the row their own existing lock (previously taken only as a count-check mutex) actually returns.",
        "visible_result": "A lock or shot submitted the instant cooking approval or a cancellation moves the battle out of the ingredient-penalty phase is now refused, instead of creating a record and a public event on a battle already in COOKING or CANCELLED.",
        "acceptance": "IngredientLockAndShotRecheckStatusUnderLockTests green: FOR UPDATE asserted for both functions; a lock/shot placed against a battle moved to COOKING underneath a stale battle object is refused and creates no row.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. Same sweep, same anti-pattern as F62 - found in code that predates this session entirely (no F-number in its own history). Both functions already locked the battle row to serialise their own MAX_LOCKS/MAX_SHOTS count check, correctly, but discarded the lock's return value, so the INGREDIENT_PENALTY precondition checked at the top of each function was never re-verified against it.",
    },
    {
        "id": "F64", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "F49 locked the slot check but not the other precondition checked in the same view",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (challenge_create)",
        "depends_on": "F49",
        "action": "Use the row F49's lock actually returns for both the moves/energy minimum check and the slot check, instead of only the latter.",
        "visible_result": "A challenge is now refused if a concurrent spend has genuinely dropped the chef's balance below the minimum by the time the lock is acquired, even though the balance shown earlier in the same view still looked sufficient.",
        "acceptance": "ChallengeCreateRechecksMovesUnderTheLockTests green: a challenge is refused once the real balance is dropped below the minimum between the view's own initial check and the lock; a normal challenge still succeeds unaffected.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. F49 (earlier the same day) locked the challenger's profile row and re-checked slot_occupied_reason under it - correct for the SLOT finding as reported, but challenge_create checks a second, earlier precondition (MOVES_MIN_TO_CHALLENGE) against the same profile before the lock exists, and F49's fix never broadened to cover it.",
    },
    {
        "id": "F65", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "A sitewide cache could leak the Chef Battle promo for up to 5 minutes after the flag went off",
        "status": "DONE", "owner": "Bolt",
        "files": "config/context_processors.py (hero_chef_promotions)",
        "depends_on": "none",
        "action": "Removed the Chef Battle promo item from the cached, battle-agnostic promotions list entirely; it is now computed fresh on every request from is_battle_visible(request) and inserted into the (still cached) base list per-viewer.",
        "visible_result": "Turning CHEF_BATTLE_ENABLED off now hides the hero-chef promo text and Arena link immediately for anyone not otherwise visible, instead of leaving it live in a shared cache for up to 300 seconds.",
        "acceptance": "HeroChefPromotionsGatedPerRequestTests green: a plain visitor never sees the promo even when the shared cache was warmed moments earlier by a staff visit with the flag on; a visible viewer still sees it.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. hero_chef_promotions cached its ENTIRE promotions list, including the Chef Battle item, under one sitewide key with no per-viewer dimension, and only checked the global CHEF_BATTLE_ENABLED flag at the moment the cache happened to repopulate (a 300-second TTL). is_battle_visible() also depends on the REQUESTING viewer (staff/superusers see it regardless of the flag), which can never be safely folded into a cache keyed on nothing but time - and toggling the flag off did not clear the existing entry, so anonymous and AUTHOR-tier visitors could see the promo and the Arena link for up to 5 minutes after dark-launch was supposed to hide it again. LOW severity: the arena page itself still 404s for them; this was metadata disclosure only.",
    },
    {
        "id": "F66", "group": "Independent Audit 2026-08-11 (Round 3)", "title": "The Slice Gate's own text still described a closed Stage 2 queue as the live execution order",
        "status": "DONE", "owner": "Bolt",
        "files": "docs/ARENA_BATTLE_PLAN.md (section 3)",
        "depends_on": "F57",
        "action": "Added a note in place, matching the pattern already used for §5 in F57: the 'strictly one at a time, in §5 table order' rule described Stage 2's own (now-closed) dispatch queue, and current execution ordering is governed by declared depends_on values and the dependency matrix in ARENA_BOARD_SYNC_2026_08_09.md, not a fixed row position in a now-historical table.",
        "visible_result": "None - documentation only.",
        "acceptance": "Section 3 no longer contradicts section 5's own note (F57) that its table now holds only historical, already-shipped rows.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1014. Independently reported and verified directly: the SAME fix pattern F57 applied to §5 was needed one section earlier, in §3's own procedural rule, which still read as if a live sequential queue existed to run slices against.",
    },
    {
        "id": "F67", "group": "Self-Directed Audit 2026-08-12", "title": "Both chefs pressing Ready in the same window could silently erase each other's flag",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (battle_set_ready)",
        "depends_on": "none",
        "action": "Wrapped the view in transaction.atomic(), locked the battle row and re-read both ready flags from the locked row before deciding anything, instead of reading them from the unlocked object fetched at the top of the view.",
        "visible_result": "Two chefs clicking Ready at the same moment can no longer have one click silently overwritten by the other's save.",
        "acceptance": "BattleSetReadyLocksTheRowTests green: FOR UPDATE asserted against chef_battle_battle; one-ready and both-ready outcomes unaffected. Same as F39/F40's shape, this race needs two separate connections and cannot be reproduced sequentially - closed on the locking mechanism.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. Found by my own self-directed audit, ordered directly (\"ПРОВЕДИ СВОЙ СОБСТВЕННЫЙ ПОЛНЫЙ АУДИТ\") after three rounds of external reports. The view had no lock at all: each request read the OTHER chef's flag as whatever it was at that request's own unlocked fetch and wrote it back unchanged. Whichever request committed second overwrote the first's real click back to False, and since this view refuses any POST once status leaves SCHEDULED, that chef had no way back in before the grace period expired into an unearned walkover.",
    },
    {
        "id": "F68", "group": "Self-Directed Audit 2026-08-12", "title": "A battle past its 48h submission clock could be teleported straight to voting, skipping combat, biathlon and cooking entirely",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (handle_no_show_battles, reveal_entries_if_ready)",
        "depends_on": "none",
        "action": "handle_no_show_battles no longer jumps a MENU_LOCKED/ACTIVE battle straight to VOTING once both BattleEntry rows exist and the deadline passes - it cancels instead (no reward, no penalty), the same call F20's void_stalled_battle already makes for a phase stuck past its deadline. reveal_entries_if_ready's ACTIVE branch no longer advances on deadline_passed alone - only once both dishes are genuinely submitted.",
        "visible_result": "A battle that is still genuinely being fought when its 48h submission clock runs out is now cancelled instead of being scored on an empty, unfought vote.",
        "acceptance": "NoShowSweepDoesNotSkipCombatBiathlonAndCookingTests green: the sweep cancels an ACTIVE/MENU_LOCKED battle past its deadline instead of moving it to VOTING; reveal_entries_if_ready no longer advances ACTIVE on deadline_passed alone but still advances once both dishes are in.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. \"submitted\" here only ever meant a BattleEntry row exists, and both are auto-created (accept_challenge, battle_recipe_attach) long before combat starts - so this was near-deterministic, not a race: COMBAT_HITS_TO_WIN has no per-round deadline, so two humans playing asynchronously can easily still be mid-fight when the 48h clock runs out, and the old code would score that as a public vote with no cooked photo, no biathlon, and possibly no winner/loser ever set from combat. A leftover from a simpler recipe-submission format that predates the combat/biathlon/cooking pipeline and was never updated when that pipeline landed.",
    },
    {
        "id": "F69", "group": "Self-Directed Audit 2026-08-12", "title": "Cooked photo upload was the one function in its phase with no battle lock",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (submit_cooked_photo)",
        "depends_on": "none",
        "action": "Lock the battle row inside the existing transaction.atomic() block and re-check status == COOKING under the lock before writing the entry.",
        "visible_result": "A cooked-photo upload that lands the instant a moderator voids or cancels the battle is now refused instead of attaching a pending-moderation photo to a battle no longer live.",
        "acceptance": "SubmitCookedPhotoLocksAndRechecksBattleStatusTests green: FOR UPDATE asserted; a stale upload against a battle moved to CANCELLED is refused and writes no photo.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. Every sibling function in this phase (declare_menu, place_ingredient_lock, fire_ingredient_shot, approve_cooking_phase) already locks and rechecks; this one was missed. Not game-outcome corrupting on its own - the later moderation transition re-checks status under its own lock - but a real, reachable precondition-checked-against-stale-object gap of the exact shape this session spent all day closing elsewhere.",
    },
    {
        "id": "F70", "group": "Self-Directed Audit 2026-08-12", "title": "Five places mutated a chef's profile without locking the row first",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (refuse_challenge, _award_walkover_win, _void_battle_no_show, _award_forfeit_win), chef_battle/withdrawal_service.py (resolve_withdrawal)",
        "depends_on": "F27",
        "action": "New shared helper _lock_battle_profiles(*authors) locks one or more ChefBattleProfile rows, ordered by pk (matching _score_battle's own established pattern), and returns them keyed by author_id. All five call sites now fetch through it before mutating rating/reputation/wins/losses/win_streak.",
        "visible_result": "A chef who is finishing a DIFFERENT battle at the exact moment a walkover, forfeit, void-no-show, refused challenge or upheld withdrawal penalty lands can no longer have that update lost to a race on the same profile row.",
        "acceptance": "UnlockedProfileMutationsAreNowLockedTests green: FOR UPDATE asserted against chef_battle_chefbattleprofile for all five call sites. Genuine two-connection race, same as F39/F40/F67 - closed on the locking mechanism.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. F27 (earlier this session) already fixed exactly this shape in _award_draw_shares, with the reasoning stated directly in _score_battle's own comment: 'a chef can be in more than one battle at once... two battles finishing at once take different battle locks... lock both profile rows here.' That reasoning was never carried to walkover, forfeit, void-no-show, a refused challenge, or an upheld withdrawal penalty - all five read-modified-and-saved a profile with no lock at all.",
    },
    {
        "id": "F71", "group": "Self-Directed Audit 2026-08-12", "title": "Approving a payout only re-checked payout_blocked, not suspension or fraud flag",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (approve_payout_request)",
        "depends_on": "F60",
        "action": "Added the same is_suspended and fraud_flag checks check_payout_eligibility already runs for a NEW request, at the point that actually sends money.",
        "visible_result": "A chef suspended or fraud-flagged after submitting a payout request that is still sitting PENDING/UNDER_REVIEW can no longer be approved and paid.",
        "acceptance": "ApprovePayoutRechecksSuspensionAndFraudFlagTests green: a suspended chef's payout is refused; a fraud-flagged chef's payout is refused; a clean chef is still approved normally.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. F60 (earlier this session) brought approve_payout_request's re-check up to payout_blocked only, following the specific finding as reported. check_payout_eligibility gates a new request on all THREE of is_suspended, fraud_flag and payout_blocked - the other two were never carried into the approval-time re-check, leaving a real gap at the one point that sends real money.",
    },
    {
        "id": "F72", "group": "Self-Directed Audit 2026-08-12", "title": "Rejecting one payout could release a reward record reserved for a different one",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (reject_payout_request)",
        "depends_on": "F61",
        "action": "Changed status_note__contains=f\"PayoutRequest #{payout.pk}\" to an exact match against the full note text create_payout_request writes (\"Locked for PayoutRequest #{pk}\"), matching the anchoring reverse_reward/expire_rewards already use (startswith the full prefix).",
        "visible_result": "Rejecting a payout request now only ever releases the reward record it actually locked, never one belonging to an unrelated request whose id happens to start with the same digits.",
        "acceptance": "RejectPayoutRequestDoesNotFreeUnrelatedPayoutsTests green: rejecting a payout releases its own record and leaves a record manufactured to collide on the substring untouched.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. __contains is an unanchored substring match: \"PayoutRequest #1\" is a substring of \"PayoutRequest #10\", \"#11\"...\"#19\", \"#100\" and so on, so rejecting payout #1 could also release reward records reserved for any other payout whose id happened to start with \"1\" - corrupting the F61 reservation guarantee for a payout that was never touched by the rejection.",
    },
    {
        "id": "F73", "group": "Self-Directed Audit 2026-08-12", "title": "PayoutRequest.status was directly editable in Django admin, bypassing every service-layer safeguard",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/admin.py (PayoutRequestAdmin)",
        "depends_on": "none",
        "action": "Added status, reviewed_by, reviewed_at and paid_at to readonly_fields, so the change form can no longer write them directly; the existing actions (which call the service functions) remain the only way to move a payout forward.",
        "visible_result": "A staff user can no longer hand-type \"paid\" (or any other status) straight into a PayoutRequest's change form.",
        "acceptance": "PayoutRequestAdminStatusIsReadOnlyTests green: status/reviewed_by/reviewed_at/paid_at all present in PayoutRequestAdmin.readonly_fields.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. Any staff user with Django admin change permission on PayoutRequest could set status to \"paid\" via a plain field edit on the change form - no Stripe transfer, no is_suspended/fraud_flag/payout_blocked check, no RewardRecord transition, no ledger event, and no actual money movement to back the marked-paid state.",
    },
    {
        "id": "F74", "group": "Self-Directed Audit 2026-08-12", "title": "A refund or dispute webhook arriving before its own checkout-completed webhook was silently dropped forever",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/stripe_services.py (_handle_charge_refunded, _handle_charge_dispute)",
        "depends_on": "F58",
        "action": "Both handlers now raise TokenPaymentVerificationError when no TokenOrder is found for the payment_intent, instead of silently returning None. The raise rolls back the whole handle_stripe_event transaction, including the ProcessedTokenStripeEvent dedup row, so Stripe's own non-2xx retry schedule (up to 3 days) gets a real chance to redeliver once the ordering resolves.",
        "visible_result": "A refund or dispute Stripe delivers before the matching purchase-completed event can no longer be permanently and silently lost.",
        "acceptance": "StripeWebhookOrderingDoesNotSilentlyDropRefundsTests green: an unlinked refund event raises and is NOT recorded as processed (so a retry can still succeed); a refund that finds its order still refunds normally.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. Stripe does not guarantee webhook delivery order. stripe_payment_intent_id is only ever written by _handle_checkout_completed; if charge.refunded/charge.dispute.created is delivered (or redelivered) first, the order lookup fails. The old code returned None, which LOOKED like success to the caller - handle_stripe_event had already recorded the event_id in ProcessedTokenStripeEvent in the same transaction before calling the handler, so a 200 response permanently marked the event done and Stripe never resent it: the refund/dispute was dropped forever, and the customer kept tokens Stripe had already taken the money back on.",
    },
    {
        "id": "F75", "group": "Self-Directed Audit 2026-08-12", "title": "The profile edit page's \"Become a Chef\" prompt had no visibility gate",
        "status": "DONE", "owner": "Bolt",
        "files": "templates/authoring/profile_form.html",
        "depends_on": "none",
        "action": "Wrapped the existing {% if not author.battle_profile.enrolled_at %} block with `and chef_battle_enabled`, matching the identical prompt already gated the same way in the site header (recipes/context_processors.py).",
        "visible_result": "An author who cannot see Chef Battles anywhere else on the site no longer sees an invitation to join it on their own profile edit page.",
        "acceptance": "ProfileFormBecomeAChefIsGatedTests green: the prompt is hidden with the flag off, shown with it on.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1016. Found by the permissions-focused agent in my own self-directed audit. Low severity - it links to chef_enroll, which is itself properly guarded and 404s - but it is the exact drift class (a hand-written copy of the audience rule instead of a call to the centralised one) this session has already closed four times elsewhere (F8/F16/F22/F26/F31).",
    },
    {
        "id": "F24", "group": "Release Audit 2026-08-11 (Round 3)", "title": "Season close/activate took no row lock, letting a cron self-overlap double-fire season-end rewards",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/season_service.py (activate_season, close_season)",
        "depends_on": "none",
        "action": "Both functions now lock the Season row (select_for_update) and re-check its status under the lock before proceeding. close_season's second racer, finding the season already ENDED under the lock, returns the frozen snapshot instead of raising or reprocessing - matching the function's own documented idempotency claim.",
        "visible_result": "None visible under normal play - two overlapping roll_seasons runs on the same season now serialise instead of both snapshotting standings and both firing season_ended/season_ended_committed.",
        "acceptance": "SeasonLifecycleIsLockedAgainstDoubleFireTests green: both functions assert a FOR UPDATE lock in captured SQL, and a second call on an independently-fetched stale copy of the season (simulating a second overlapping cron run) fires season_started/season_ended_committed exactly once, not twice.",
        "forbidden": "Did not, at the time, address two DIFFERENT seasons being activated concurrently - the Owner has since ordered that closed; see F33.",
        "evidence": "SHIPPED v2.5.1002. roll_seasons.py documents no mutex, same as every other cron sweep in this app (handle_no_show_battles, resolve_start_rituals already lock for exactly this reason). close_season's own docstring claims 'idempotent per season' but the claim held only for a full run followed by a later rerun, not for two overlapping runs racing the same unlocked status check - both would snapshot SeasonStanding, both would reset seasonal_score, and both would fire season_ended_committed, which issues real SeasonReward rows. New area: G10/G11 shipped 2026-08-11 and had never been checked for concurrency.",
    },
    {
        "id": "F25", "group": "Release Audit 2026-08-11 (Round 3)", "title": "G3's artifact-tier-by-cooking-format fallback widens to the full rarity table when a chef's pool is exhausted",
        "status": "REVIEWED - NOT A BUG", "owner": "Bolt",
        "files": "chef_battle/services.py (_pick_artifact, _DROP_WEIGHTS_BASIC)",
        "depends_on": "none",
        "action": "None taken.",
        "visible_result": "None - behaviour unchanged.",
        "acceptance": "N/A - reviewed, no code change.",
        "forbidden": "Do not silently fix this without re-reading the surrounding comment first - it explains the exact tradeoff a change would reopen.",
        "evidence": "REVIEWED 2026-08-11. The re-audit read this as G3's tier rule silently defeating itself once a chef's basic (common/uncommon) pool is exhausted, falling back to any rarity. GreenBear's own comment immediately above the fallback (services.py, by _DROP_WEIGHTS_BASIC) already states the tradeoff explicitly: 'a pool that comes up empty falls back to the full table rather than paying nothing... a rule about tiers must not become a rule about getting nothing.' A static read cannot see a decision recorded only in a comment; changing this now would override an already-reasoned call without new information. Left untouched.",
    },
    {
        "id": "F26", "group": "Release Audit 2026-08-11 (Round 3)", "title": "Artifact image generation checked moderator/staff but never arena visibility",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/views.py (artifact_generate_image); chef_battle/access.py (UNGUARDED_BY_DESIGN)",
        "depends_on": "F8, F16, F22",
        "action": "Add is_battle_visible(request) to the existing (is_moderator() or is_staff) check; update the UNGUARDED_BY_DESIGN reason text.",
        "visible_result": "A moderator without arena access can no longer trigger AI artifact image generation.",
        "acceptance": "ArtifactGenerateImageRequiresBattleVisibilityTests green: a has_bearseeker_privileges-only moderator gets 403 with CHEF_BATTLE_ENABLED off.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1002. Same class of gap as F8/F16/F22, on a write action that triggers a paid AI image generation call with no is_battle_visible() check at all - consistent with UNGUARDED_BY_DESIGN's documented exemption, but the same drift pattern this audit keeps finding across three rounds now.",
    },
    {
        "id": "F27", "group": "Release Audit 2026-08-11 (Round 4)", "title": "A drawn battle's second-place shares were saved without locking either chef's profile row",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (_award_draw_shares)",
        "depends_on": "none",
        "action": "_award_draw_shares now opens its own transaction.atomic(), locks both chef profile rows (select_for_update, ordered by pk) exactly like the decisive-win branch a few lines below it in _score_battle, and awards each chef's share against the locked row.",
        "visible_result": "None visible under normal play - a chef drawn in one battle while decisively winning or drawing another at the same moment now has both results added, instead of whichever commits second silently overwriting the first.",
        "acceptance": "DrawShareLockingTests green: FOR UPDATE asserted in captured SQL against chef_battle_chefbattleprofile, and a chef drawn in two battles carries both draws' rating/reputation/seasonal_score/battle_moves, not just one.",
        "forbidden": "Do not change award_second_place's own numbers or the draw-vs-decisive tie-break in _score_battle - this is locking-only, matching the pattern the decisive branch already uses for the identical reason (a chef can be in more than one battle at once).",
        "evidence": "SHIPPED v2.5.1006. _score_battle's decisive-win branch locks winner_profile and loser_profile under select_for_update, with an explicit comment explaining why: two battles finishing at once can share a chef, and unlocked reads-then-writes lose one side's rating/streak/crown update. _award_draw_shares, three lines above it in the same function, fetched each profile with get_or_create_battle_profile and saved it straight back - no lock at all. The Owner's 2026-08-05 ruling that gave draws a real payout (previously nothing) never carried the locking discipline the decisive path already had.",
    },
    {
        "id": "F28", "group": "Release Audit 2026-08-11 (Round 4)", "title": "Resuming a paused battle shifted every deadline except the one WAITING status actually uses",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (operator_resume)",
        "depends_on": "none",
        "action": "Add waiting_until to the set of fields operator_resume shifts forward by the measured pause duration, alongside submission_deadline/voting_deadline/end_time.",
        "visible_result": "A battle Emergency-Stopped while WAITING for the second chef to turn up, then resumed after a long pause, gets its readiness grace period restarted instead of instantly expiring on the next sweep.",
        "acceptance": "OperatorResumeShiftsWaitingUntilTests green: waiting_until moves forward by the pause duration and lands in the future, and a resumed WAITING battle survives an immediate resolve_start_rituals() sweep without being walked over or voided.",
        "forbidden": "Do not add waiting_until shifting anywhere WAITING isn't the paused_from_status - the field is null outside that phase and the loop already skips null deadlines by design.",
        "evidence": "SHIPPED v2.5.1006. operator_resume's pause_duration shift loop names three fields, all populated by phases OTHER than WAITING. waiting_until - written by resolve_start_rituals when only one chef shows up, read by the same function's grace-period sweep - was never in the list, despite Emergency Stop (operator_emergency_stop) accepting a WAITING battle same as any other non-terminal status. A pause spanning the grace period left the deadline exactly where it was, already in the past the moment the battle resumed.",
    },
    {
        "id": "F29", "group": "Release Audit 2026-08-11 (Round 4)", "title": "A withdrawal resolved by a moderator could cancel a battle that had already finished naturally in the meantime",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/withdrawal_service.py (resolve_withdrawal)",
        "depends_on": "none",
        "action": "resolve_withdrawal now re-fetches the battle under select_for_update inside its own atomic block and gates the CANCELLED rewrite on that freshly-locked status, not on withdrawal.battle - whatever the caller's request happened to load, cached FK and all.",
        "visible_result": "A battle that completed by vote or was voided by the stall sweep while a withdrawal sat AWAITING_MODERATOR no longer gets dragged back to CANCELLED - with its winner cleared - when a moderator finally closes that withdrawal.",
        "acceptance": "WithdrawalResolveIgnoresStaleBattleStatusTests green: a battle completed out from under a stale withdrawal.battle stays COMPLETED with its winner intact after resolve_withdrawal runs, and the withdrawal itself still closes normally.",
        "forbidden": "Do not make the moderator's penalty decision conditional on the battle's current status - uphold_penalty is the moderator's own ruling on the withdrawal request itself and applies regardless of what became of the battle; only the CANCELLED status rewrite was the bug.",
        "evidence": "SHIPPED v2.5.1006. `battle = withdrawal.battle` ran before resolve_withdrawal's atomic block, and the CANCELLED rewrite below checked `battle.status in Battle.ACTIVE_STATUSES` against that same, possibly long-since-cached object - Django never re-queries an already-accessed FK on its own. A withdrawal can sit AWAITING_MODERATOR for as long as a moderator takes to answer, plenty of time for calculate_battle_result or the F20 stall sweep to complete or void the same battle first.",
    },
    {
        "id": "F30", "group": "Release Audit 2026-08-11 (Round 4)", "title": "Two different combat artifacts reserved into the same loadout at once could both slip past the three-per-type cap",
        "status": "DONE", "owner": "Bolt",
        "files": "chef_battle/services.py (submit_combat_action)",
        "depends_on": "none",
        "action": "The ChefArtifact fetch now takes select_for_update, and a fresh Battle.objects.select_for_update().get(pk=battle.pk) is taken as a mutex immediately before the loadout count query, so two reservations sharing a battle serialise on the battle row even though they lock different artifact rows.",
        "visible_result": "None visible under normal play - a chef's combat loadout stays capped at three artifacts per type even under back-to-back or double-submitted reservation requests.",
        "acceptance": "CombatArtifactReservationLockTests green: FOR UPDATE asserted in captured SQL against both chef_battle_battle and chef_battle_chefartifact for a fresh reservation; existing CombatArtifactTests (including the fourth-artifact-rejected case) unaffected.",
        "forbidden": "Do not lock ChefBattleProfile as the mutex instead - it would serialise a chef's combat actions across ALL of their concurrent battles, not just the one being reserved into, which is broader than the bug calls for.",
        "evidence": "SHIPPED v2.5.1006. The loadout count query and the reservation save() that follows it read-then-write with no lock between them; the row lock added on the chef_artifact fetch only protects that ONE artifact from being double-reserved, but two DIFFERENT artifacts of the same type take different row locks entirely and never contend with each other, so both could read a count one under the cap. Game-balance impact only - an extra artifact slot, not a security boundary.",
    },
    {
        "id": "F31", "group": "Release Audit 2026-08-11 (Round 4)", "title": "The inbox's battle section hand-rolled the same visibility check is_battle_visible() already centralises",
        "status": "DONE", "owner": "Bolt",
        "files": "messaging/views.py (inbox)",
        "depends_on": "none",
        "action": "Replace the inline CHEF_BATTLE_ENABLED-or-staff-or-superuser check with a call to chef_battle.access.is_battle_visible(request).",
        "visible_result": "None - identical behaviour, since the hand-rolled check and is_battle_visible() computed the same answer.",
        "acceptance": "InboxUsesCentralBattleVisibilityGateTests green: a plain user sees no battle section with the flag off, staff still does, and a plain user sees it once the flag is on.",
        "forbidden": "none.",
        "evidence": "SHIPPED v2.5.1006. Not exploitable as found - the two checks always agreed - but it is the one place in the codebase that reimplements is_battle_visible() instead of calling it, which means a future change to the real gate (the fifth time this class of drift has shown up, after F8/F16/F22/F26) would silently stop reaching this copy. Closed as hardening, not as a live gap.",
    },
    {
        "id": "T2", "group": "Release Audit 2026-08-10", "title": "Raw CSS colour literals stood where the Arena's own tokens already existed",
        "status": "DONE", "owner": "Bolt",
        "files": "static/css/arena.css",
        "depends_on": "none",
        "action": "Replace stroke/fill declarations that restated --arena-seam/--arena-seat's own value by hand with var() references to those tokens.",
        "visible_result": "None - identical pixels, since the literal and the token held the same value.",
        "acceptance": "The five flagged declarations reference var(--arena-seam)/var(--arena-seat); ArenaSeamTokenNotRawLiteralTests green; ArenaRankColumnTests (7:1 contrast) unaffected.",
        "forbidden": "Do not invent new tokens for the sponsors-ring ramp or the runway-note colour - those have no existing named token to point at, and naming one is a design decision, not this cleanup's to make.",
        "evidence": "SHIPPED v2.5.996. Contract section 12 forbids scattered raw colour literals in favour of official named Arena tokens. Five declarations in .page--arena's scope set stroke/fill to #ffffff or #f4f1ec directly, restating by hand the exact value --arena-seam and --arena-seat already held two lines above them in the same scope - not a design choice, just a copy that never got updated to var(). Fixed at all five (arena.css: the .arena-cell, [data-occupancy=\"chef\"], the eight empty-ring selector, .arena-cell--sponsors-tpl base stroke, and the ring-6 sponsors fill). Left alone, deliberately: the sponsors-ring ramp (#ede8df, #e4ddd1, #bfb49a, #ccc1aa, #d8d0c0) and one runway-note text colour (#EEE1CA) - none of these duplicates an existing named token's value, and the file's own comment at line 5271 already records that two of them were deliberately left un-tokenised as rim colours, not ring fills. Full palette-token authoring for those is the Owner's call.",
    },
    {
        "id": "T1", "group": "Release Audit 2026-08-10", "title": "User-facing text said wallet where the contract requires Token Account",
        "status": "DONE", "owner": "Bolt",
        "files": "templates/legal/purchases_and_vat.html; templates/chef_battle/arena_master_console.html",
        "depends_on": "none",
        "action": "Replace 'wallet' with 'Token Account' in the five user-facing occurrences (four on the public VAT/refunds page, one in the Master Console's read-only economy hint).",
        "visible_result": "The legal page and the console hint now say Token Account, matching the terminology the contract requires.",
        "acceptance": "TokenTerminologyNotWalletTests green: the rendered legal page and console page contain no 'wallet' and do contain 'Token Account'.",
        "forbidden": "Do NOT rename the TokenWallet Django model, its fields, or the `wallet` template/context variable name - that is a schema migration on the live Stripe payment and reward path (TokenWallet, TokenTransaction.wallet, TokenOrder.wallet, and every view/template/admin reference to it), a materially bigger and riskier change than a same-day text fix, and it is the Owner's decision to authorise, not an agent's to make unprompted on a payment-integration model. This card is user-facing wording only.",
        "evidence": "SHIPPED v2.5.996. Contract section 9.1: 'Use TokenAccount, Token Balance, Token Ledger, and Token Transaction terminology. Do not introduce new wallet or cash-balance terminology.' templates/legal/purchases_and_vat.html - the most legally sensitive page on the site for this feature - said 'wallet' four times; the Master Console's economy panel hint said 'wallet balances' once. All five corrected to 'Token Account'. The underlying TokenWallet model keeps its name: renaming it is a real schema migration on the Stripe purchase/reward path and is out of scope for a same-day terminology pass - flagged for the Owner, not attempted.",
    },
    {
        "id": "T01", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "Scoring accepts only an authoritative locked VOTING state",
        "status": "NEXT", "owner": "GreenBear",
        "files": "chef_battle/services.py (calculate_battle_result, _score_battle); chef_battle/admin.py (force-complete); chef_battle/views.py; expire_stale_battles",
        "depends_on": "none",
        "action": "Gate the scorer itself on a re-read locked status of VOTING, score the LOCKED instance rather than the caller's stale object, and route an expired ACTIVE to the explicit stalled/no-show policy. Admin force-complete uses the same contract; any genuine override becomes a separate owner-only operation with a named target state and an audit event.",
        "visible_result": "Nothing changes on a healthy battle. A battle that is cancelled, void, walkover, paused, disputed, scheduled, menu-locked, active, cooking or in presentation can no longer be completed and paid by the ordinary scorer.",
        "acceptance": "A parameterised test per non-VOTING status proving status, profiles, rating, reputation, moves, crown, rewards and ledger all unchanged; expired ACTIVE + zero votes + a plain GET does not become COMPLETED and pays no draw shares; VOTING still completes exactly once; two concurrent scorers award once.",
        "forbidden": "Do not fix only the caller in battle_detail - v2.5.1010 already did that (F20) and the class stayed open. The scorer is the thing being gated.",
        "evidence": "Owner brief 2026-08-12, ticket 1. VERIFIED PARTIAL 2026-08-12: views.py:2029 now scopes the auto-score trigger to ACTIVE/VOTING, but calculate_battle_result still accepts every status except COMPLETED, so every other caller keeps the hole.",
    },
    {
        "id": "T02", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "Reveal is atomic and cannot resurrect a terminal battle",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/services.py (reveal_entries_if_ready); chef_battle/views.py; chef_battle/emulation.py",
        "depends_on": "T01",
        "action": "Wrap in transaction.atomic, lock the battle, re-check the allowed source states under the lock, compute the entry count and deadline after the lock, and write only through the locked instance.",
        "visible_result": "A battle cancelled, voided or paused while a chef was submitting stays cancelled, voided or paused, and its entries stay hidden.",
        "acceptance": "Tests for cancel/void/pause committing between submission and reveal, and two concurrent submits; the terminal state is never overwritten, entries are not revealed, events fire once, a repeat call is idempotent.",
        "forbidden": "No write of any kind after a terminal or paused state.",
        "evidence": "Owner brief 2026-08-12, ticket 2. VERIFIED OPEN 2026-08-12: reveal_entries_if_ready has neither transaction.atomic nor select_for_update.",
    },
    {
        "id": "T03", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "Two chefs pressing Ready cannot erase each other - proved by a real race",
        "status": "PARTIAL", "owner": "GreenBear",
        "files": "chef_battle/views.py (battle_set_ready); chef_battle/services.py (pull_start_forward_when_both_ready); chef_battle/tests.py",
        "depends_on": "none",
        "action": "The lock itself shipped as F67 on 2026-08-12. What the brief additionally requires is the proof: a TransactionTestCase with two threads and a barrier, not an assertion that FOR UPDATE appears in the SQL.",
        "visible_result": "No change - this is the test that stops the fix regressing.",
        "acceptance": "Two-thread barrier test: both ready flags survive, the start time is pulled forward exactly once, the both-ready event is created once, a repeated POST is idempotent.",
        "forbidden": "Do not substitute a captured-SQL check for the interleaving test.",
        "evidence": "Owner brief 2026-08-12, ticket 3. VERIFIED DONE-IN-CODE 2026-08-12: battle_set_ready locks the row and re-reads both flags under it (F67, v2.5.1016). The barrier test is what is missing.",
    },
    {
        "id": "T04", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "Combat log cannot execute HTML a chef put in their own name",
        "status": "PENDING", "owner": "GreenBear",
        "files": "BattleRound.log_message; battle state JSON polling; templates/chef_battle/battle_detail.html; every innerHTML in the arena and battle scripts",
        "depends_on": "none",
        "action": "Stop routing user-controlled strings through innerHTML: build the nodes and set textContent. Audit every innerHTML and insertAdjacentHTML in the battle and arena scripts, not only the combat log.",
        "visible_result": "A chef named with an img/script payload renders as that literal text in the log instead of running.",
        "acceptance": "Payload names render literally; the DOM contains no created IMG, SCRIPT or event handler; a browser smoke confirms it.",
        "forbidden": "Server-side escaping alone is not the fix; a name validator is defence in depth, not a substitute for a safe DOM API.",
        "evidence": "Owner brief 2026-08-12, ticket 4.",
    },
    {
        "id": "T05", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "A cooked photo is a validated, normalised image and nothing else",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/models.py (BattleEntry.cooked_photo); the cooking submission view/service; recipes/validators.py; media serving",
        "depends_on": "none",
        "action": "Accept only JPEG, PNG and WebP, decided by the decoded image rather than the content type or the extension; byte and pixel ceilings; Pillow decompression-bomb handling; a server-generated name; decode and re-encode so active content and metadata are dropped; nothing is stored before it validates; the hash is taken from the normalised file by a stated rule.",
        "visible_result": "An HTML, SVG or polyglot file is refused with a plain message instead of being stored and served.",
        "acceptance": "Tests for HTML named .html, HTML named .jpg, SVG, a corrupt JPEG, a format/extension mismatch, oversized bytes, excessive dimensions, and valid JPEG/PNG/WebP; the stored name and content type are the normalised ones.",
        "forbidden": "Do not block the fix on a cookieless media origin - that is separate infrastructure, worth recording as defence in depth.",
        "evidence": "Owner brief 2026-08-12, ticket 5.",
    },
    {
        "id": "T06", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "The first cooked photo is the evidence, and a race cannot replace it",
        "status": "PARTIAL", "owner": "GreenBear",
        "files": "chef_battle/services.py (submit_cooked_photo)",
        "depends_on": "T05",
        "action": "Lock the battle, then the entry, always in that order; re-check COOKING, participation and the empty-photo condition under both locks; a cancellation committed first must win and refuse the stale upload.",
        "visible_result": "Two simultaneous uploads leave one photo and one honest error, and the first accepted photo is not silently replaced.",
        "acceptance": "Concurrency test: one success and one domain error; cancel-before-entry-lock mutates no photo; the moderation state and the hash belong to the file actually stored.",
        "forbidden": "Do not check the status before the transaction and call it settled.",
        "evidence": "Owner brief 2026-08-12, ticket 6. VERIFIED PARTIAL 2026-08-12: submit_cooked_photo now opens a transaction and locks the battle (F69, v2.5.1016); the entry-level lock and the ordering guarantee still need proving.",
    },
    {
        "id": "T07", "group": "Launch Blockers (Owner brief 2026-08-12)", "title": "A chargeback during PROCESSING cannot end as an ordinary PAID payout",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/stripe_services.py; the payout state machine; the webhook handler; admin/console display",
        "depends_on": "none",
        "action": "Record a durable compliance marker when a dispute lands mid-transfer; re-read the payout and its compliance state under a lock after the network call returns; settle into one explicitly chosen state - RECONCILIATION_REQUIRED, PAID_DISPUTED or REVERSAL_PENDING - and document the transition matrix.",
        "visible_result": "The console shows a payout that needs reconciliation instead of a clean PAID row.",
        "acceptance": "A blocking mocked transfer with a chargeback arriving mid-call and a successful return: the outcome is not ordinary PAID, the rewards are not available again, and a compliance state plus an immutable ledger event exist.",
        "forbidden": "No automatic external Stripe reversal without the Owner's separate decision; no second payout from the same rewards; no DB transaction held open across the network call.",
        "evidence": "Owner brief 2026-08-12, ticket 7.",
    },
    {
        "id": "T08", "group": "Money Integrity (Owner brief 2026-08-12)", "title": "Spent tokens carry a provable origin, not a timestamp",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/models.py (token lots/allocations); stripe_services refund path; a migration",
        "depends_on": "T07",
        "action": "Give a purchase an identifiable lot or ledger allocation, record which credits a spend drew from, and settle on a documented policy - FIFO preferred. A refund then touches the allocations it actually funded and nothing else.",
        "visible_result": "Refunding an old order stops clawing back a gift that a later order paid for.",
        "acceptance": "Tests: order 1 then order 2 with a gift from order 2 and a refund of order 1; a gift split across lots; an old free balance plus a purchase; concurrent spends; unrelated gifts, rewards and payouts untouched.",
        "forbidden": "A timestamp is not proof of origin. Do not invent an attribution for historical rows - mark them ambiguous for manual reconciliation.",
        "evidence": "Owner brief 2026-08-12, ticket 8.",
    },
    {
        "id": "T09", "group": "Money Integrity (Owner brief 2026-08-12)", "title": "A partial refund claws back the delta, not the whole order",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/models.py (TokenOrder cumulative fields); the Stripe webhook handler; a migration",
        "depends_on": "T08",
        "action": "Store cumulative refunded cents and cumulative clawed tokens, read the real amount from the verified payload, debit only the new delta, and fix the token rounding rule in writing.",
        "visible_result": "A EUR 5 refund on a EUR 50 order takes a tenth of the tokens rather than all of them.",
        "acceptance": "Tests: first partial, second incremental, duplicate event id, a repeat of the same cumulative amount, eventual full refund, insufficient balance; the ledger sums to what was actually clawed back.",
        "forbidden": "Do not treat charge.refunded as proof of a full refund.",
        "evidence": "Owner brief 2026-08-12, ticket 9.",
    },
    {
        "id": "T10", "group": "Money Integrity (Owner brief 2026-08-12)", "title": "One locking helper for every profile mutation, in one stable order",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/services.py (refusal, walkover, void, forfeit, withdrawal, counters); chef_battle/energy_service.py",
        "depends_on": "none",
        "action": "One helper that locks one or several profiles in ascending pk order inside the owning transaction, or a conditional F() update where no Python state is needed. Document the global lock order against Battle, Challenge and Withdrawal so no new deadlock is introduced.",
        "visible_result": "Two updates to the same chef arriving together both survive instead of one overwriting the other.",
        "acceptance": "Tests: content reputation against a refusal, a content award against a withdrawal, two terminal battles sharing a chef, forfeit against walkover - both deltas persist.",
        "forbidden": "No new lock ordering that can deadlock against the battle locks.",
        "evidence": "Owner brief 2026-08-12, ticket 10. Several call sites were locked individually in F39/F47/F70; the brief asks for the single helper and the documented order.",
    },
    {
        "id": "T11", "group": "State Machine (Owner brief 2026-08-12)", "title": "Biathlon has both 48-hour windows the contract promises",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/models.py (deadline fields); chef_battle/services.py (biathlon); a sweeper command; a migration",
        "depends_on": "T12",
        "action": "A separate lock deadline for the loser and a separate shot deadline for the winner, the transition between them, timeout resolution, a sweeper, notifications, pause and resume shifting both, and a documented outcome for no response.",
        "visible_result": "The loser can no longer place locks after their window closes, and the winner's window is not shortened by the loser stalling.",
        "acceptance": "Tests immediately before, on and after each deadline, plus pause/resume and a repeated sweep.",
        "forbidden": "Do not silently drop the contract. If the Owner cancelled these windows, cite the decision; without one, build them.",
        "evidence": "Owner brief 2026-08-12, ticket 11; docs/chef_battle/ingredient_combat.md.",
    },
    {
        "id": "T12", "group": "State Machine (Owner brief 2026-08-12)", "title": "One transition contract for Battle.status, and an audit test that keeps it",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/services.py; views; admin; cron and management commands; emulation; the operator console",
        "depends_on": "T01, T02",
        "action": "A formal allow-list of source and target states, and one domain helper that locks, validates the source and the target, performs the required side effects and writes the audit event. Every money-touching or game-determining writer goes through it.",
        "visible_result": "No visible change; an illegal transition becomes impossible rather than merely unlikely.",
        "acceptance": "An audit test enumerating the permitted direct writers, so a new one cannot appear unnoticed; the matrix is covered by tests.",
        "forbidden": "Do not leave a bare battle.status = ...; save() anywhere without proving why that writer is safe.",
        "evidence": "Owner brief 2026-08-12, ticket 12.",
    },
    {
        "id": "T13", "group": "Technical Tails (Owner brief 2026-08-12)", "title": "Inline battle scripts carry a CSP nonce",
        "status": "PENDING", "owner": "GreenBear",
        "files": "templates/chef_battle/battlefield_progress.html; clan_create.html; live_arena_progress.html; every other inline script in the app",
        "depends_on": "none",
        "action": "Add nonce=\"{{ request.csp_nonce }}\" to each executable inline script and sweep the rest of the app for the same omission.",
        "visible_result": "Pages whose inline script was being blocked start working under the policy.",
        "acceptance": "Every executable inline script carries the current nonce; a browser smoke proves the script runs; the policy is not weakened.",
        "forbidden": "Do not add unsafe-inline.",
        "evidence": "Owner brief 2026-08-12, ticket 13. VERIFIED OPEN 2026-08-12: all three templates carry an inline script and none carries a nonce.",
    },
    {
        "id": "T14", "group": "Technical Tails (Owner brief 2026-08-12)", "title": "Delete the management command that edits the Owner's own profile",
        "status": "PENDING", "owner": "GreenBear",
        "files": "chef_battle/management/commands/recalculate_owner_moves.py",
        "depends_on": "none",
        "action": "Delete it, or make it refuse before any database read or write. It is already broken - it reads BattleMoveTransaction.reason, a field that no longer exists - and it exists to rewrite a protected account.",
        "visible_result": "Nothing visible; one way to touch the Owner's account by accident stops existing.",
        "acceptance": "The command is gone or exits without mutating anything; the Owner's profile is unchanged; no doc or cron references it.",
        "forbidden": "Do not modernise it. Do not run it.",
        "evidence": "Owner brief 2026-08-12, ticket 14; AGENTS.md section 18. VERIFIED PRESENT 2026-08-12.",
    },
    {
        "id": "T15", "group": "Technical Tails (Owner brief 2026-08-12)", "title": "The board and the rulebook say what the code actually does",
        "status": "PENDING", "owner": "GreenBear",
        "files": "recipes/views.py (ARENA_RELEASE_STAGES); docs/chef_battle/artifact_3_models_rules.md; AGENTS.md-adjacent docs",
        "depends_on": "none",
        "action": "Remove the stale v2.5.823, the stale 'A09 next assignable' and the stale 2026-07-29 verification from the moderation board; show Stage 2 closed and the real baseline; correct the 24h battle window to 48h or mark it superseded; write down that CHEF_BATTLE_ENABLED is a one-way launch latch and that F65 is REVIEWED, NOT A BUG.",
        "visible_result": "The moderation board stops advertising a version and a next card that have not been true for weeks.",
        "acceptance": "Consistency tests where they are cheap, so the literal versions and rules cannot drift apart again.",
        "forbidden": "Do not turn the launch latch into an emergency kill switch without the Owner's decision.",
        "evidence": "Owner brief 2026-08-12, ticket 15, and his ruling that the flag never returns to False after launch.",
    },
    {
        "id": "T16", "group": "Technical Tails (Owner brief 2026-08-12)", "title": "Remove the unreachable guide page and the orphan wordmark",
        "status": "PENDING", "owner": "GreenBear",
        "files": "templates/chef_battle/guide.html; templates/chef_battle/_battle_wordmark.html; the unique selectors that served only them",
        "depends_on": "none",
        "action": "Delete the two templates and only the CSS and JS selectors unique to them, keeping the named guide URL and its redirect for any external link.",
        "visible_result": "None. The guide URL keeps redirecting to the rules and the home wordmark keeps rendering.",
        "acceptance": "The guide URL still redirects; the home wordmark renders; the template and static reference inventory is clean.",
        "forbidden": "Do not remove documented prototypes, emulation fixtures, the Live Arena reference, .agent-chat, or any arena visual layer.",
        "evidence": "Owner brief 2026-08-12, ticket 16. VERIFIED PRESENT 2026-08-12: both files exist and the guide view always redirects.",
    },
    {
        "id": "T17", "group": "Acceptance (Owner brief 2026-08-12)", "title": "Acceptance gate for the whole brief",
        "status": "PENDING", "owner": "GreenBear",
        "files": "the full suite; the browser smoke; the deploy record",
        "depends_on": "T01-T16",
        "action": "Focused tests per ticket, real barrier tests for every concurrency claim, the security and money suites, the state matrix, manage.py check, makemigrations --check, git diff --check, then the full suite once on PostgreSQL across eight workers, with the engine, worker count, totals, duration and any pre-existing failures recorded separately.",
        "visible_result": "Nothing new; this is the evidence that the rest is real.",
        "acceptance": "Every item of the brief's completion criteria answered with an artifact, and a browser smoke over battle detail, combat log, readiness, cooked upload, clan create, the progress pages and the console reconciliation display.",
        "forbidden": "No production writes for a demonstration. No weakened assertions. No captured SQL standing in for an interleaving test.",
        "evidence": "Owner brief 2026-08-12, ticket 17.",
    },
]



# ARCHITECTURE NORMALISATION - opened by the Owner on 2026-08-08.
#
# Twenty-nine sections, AN1 to AN29, and EVERY ONE IS TO SPEC until he dictates
# it. The block is the frame, not the content: an agent does not write a title
# here, because a section invented on his behalf is precisely what this block
# exists to stop. The full preamble - his verdict of 2026-08-07 about a puzzle
# versus a house of cards, and the measured state the work starts from - lives in
# docs/ARENA_BATTLE_PLAN.md section 5a, which is the canonical board.
# ARCHITECTURE NORMALISATION - CLOSED, and off the active board.
#
# The Owner closed the project on 2026-08-09 at production v2.5.960: 29 of 29
# cards DONE and the engineering acceptance gates satisfied. Twenty-nine rows
# stood here and they are gone from the ACTIVE board on his instruction - the
# Construction Board is for construction still to be done, and a completed
# project sitting in the queue is read as work. Nothing was destroyed: every
# card and its evidence moved verbatim to
# docs/chef_battle/ARENA_NORMALISATION_CARDS_ARCHIVE.md, the engineering
# narrative and the before/after metrics are in ARENA_NORMALISATION_REPORT.md,
# and the releases are in config/release_journal.py.
#
# It is a completed FOUNDATION, not an open blocker. No card may depend on an
# AN number, and no future card may reopen the block.
ARENA_NORMALISATION_CLOSURE = {
    "title": "Architecture normalisation",
    "status": "CLOSED",
    "cards": 29,
    "closed_on": "2026-08-09",
    "release": "v2.5.960",
    "commit": "23b9043e",
    "summary": (
        "Seven arena stylesheets to two, one camera "
        "declaration instead of six, 628 unreachable declarations removed, "
        "70 raw z-index numbers to none, and the octagon's position given a "
        "single owner. The camera is a component with its own intrinsic "
        "viewport and no longer inherits its optics from the page region. "
        "CLS 0.0255 to 0, and the rank ladder is first painted AT its final "
        "position in six load profiles instead of 441px away from it. Final "
        "gate 1799 tests, 0 failures, 2 skipped, on PostgreSQL."
    ),
    "owner_only": (
        "AN28's production-page observation is OWNER-ONLY VISUAL ACCEPTANCE: "
        "the live Arena is staff-gated, so it is his to look at and not an "
        "open engineering item."
    ),
    "records": [
        "docs/chef_battle/ARENA_NORMALISATION_CARDS_ARCHIVE.md",
        "docs/chef_battle/ARENA_NORMALISATION_REPORT.md",
        "docs/chef_battle/ARENA_NORMALISATION_FINAL_SUITE.txt",
        "docs/chef_battle/ARENA_VISUAL_DEBT.md",
    ],
    "carried_out": [
        "VD1 - the large-desktop composition, a visual/layout card of its own",
        "MC02 - the withdrawal seen live, a product card of its own",
        "static-asset residue - maintenance debt",
    ],
}


ARENA_RELEASE_STAGES = [
    {
        "n": 1, "id": "recovered-baseline",
        "title": "Recovered baseline & governance", "status": "DONE",
        "purpose": "Hold the production state the Owner spent two days restoring after the "
                   "Cursor/ArenaFront branch scatter, plus the agent roles built on it.",
        "owners": "Owner, GreenBear, Ember (Bolt weekly-limited; Cursor and ArenaFront retired)",
        "criteria": ["Production stable at v2.5.675 and rolling forward cleanly.",
                     "Rollback tag rollback/2026-07-28-stable-v2.5.675 resolves to 3b4f88ad.",
                     "HISTORICAL, both halves superseded: 'Ember writes Arena code and hands "
                     "commits; GreenBear owns the deploy gate' described the arrangement of "
                     "2026-07-28. Roles were abolished on 2026-07-29 (AGENTS.md 1) and Ember "
                     "was retired on 2026-08-04. Kept as the record of what this baseline was, "
                     "not as a rule anyone follows."],
        "dependencies": "None — this is the recovered baseline.",
        "blockers": [],
        "branch": "main", "commit": "3b4f88adea2a46f5201754728cb7417ebb4ce986",
        "verification": "Rollback tag verified on origin; production served v2.5.675 at pin time.",
        "updated": "2026-07-29T01:00:00.000Z",
        "next_action": "Keep the rollback refs; do not delete them.",
    },
    {
        "n": 2, "id": "design-arena",
        "title": "Design Arena visual integration", "status": "DONE",
        "purpose": "Complete the approved Arena Hall, Battle Broadcast and Result/Winner "
                   "surfaces as atomic tickets. Master Console is excluded.",
        "owners": "Owner assigns one card at a time. There are no roles and no deploy "
                  "gate-holder (AGENTS.md 1, 2026-07-29): any agent deploys their own work, "
                  "one at a time, through the full gate. Typical focus only — GreenBear: "
                  "visual CSS. Bolt: measurement and regression. Ember was retired by the "
                  "Owner on 2026-08-04, so integration, JS, templates and backend wiring "
                  "have no standing owner and every card that suggested Ember is now "
                  "unassigned — the Owner assigns them.",
        "criteria": ["Every A00-G01 card below is DONE with its own visible result and evidence.",
                     "Owner accepts the Arena Hall before Battle Broadcast starts.",
                     "Site gold/brass palette remains authoritative.",
                     "The eleven-ring structure of ARENA_BATTLE_PLAN §2 v2 is the target: it "
                     "supersedes the former freeze on the floor colours and on the octagon "
                     "renderer, which the remaining geometry cards are required to change. "
                     "Camera rotateX(42deg) is still frozen.",
                     "Existing mechanisms, effects, backend, real seat data and Dark Launch remain intact.",
                     "No fake production fighters, rankings, gifts, viewers or results."],
        "dependencies": "Stage 1 baseline DONE.",
        "blockers": [],
        "branch": "One disposable worktree while a card is active; origin/main after each deployed slice.",
        "commit": "37e8094e / production v2.5.1017",
        "verification": "Production v2.5.823 confirmed. A00-A08, AR0-AR5, A11 and A12 are DONE "
                        "and deployed; A09 is the next assignable card and it is UNASSIGNED. Its "
                        "number is measured and was CORRECTED on 2026-08-05 "
                        "(ops/audits/arena/A06_remeasure_2026-08-04.md section 6a): the fighters "
                        "are TWO blocks, 190x212, centred at x 700 and x 1220 - exactly 260px "
                        "either side of the 1920 canvas centre, symmetric to the pixel. The "
                        "'four plinth blocks in two symmetric pairs' this card carried until "
                        "today were cells of the reference's own 52-cell floor grid, matched "
                        "against the children of the element that has exactly 52 of them. Only "
                        "the x transfers: rotateX leaves x alone, but that block is 212 tall "
                        "against 190 wide and stands upright, while our floor fighters lie flat "
                        "on the floor plane on purpose. The "
                        "camera stays rotateX(42deg): the Design Template's own 57deg shipped as "
                        "v2.5.792 and the Owner reverted it within the hour (v2.5.793), and the "
                        "2.375 target is not reachable at 42deg by any multiplier. A07 closed at "
                        "v2.5.812 as a framing card instead: the arena now fits the screen whole "
                        "at every width. Access: Chef Battles is visible to is_staff - "
                        "(Bear)seeker Admins and Super Users - and to nobody below (AGENTS.md 20).",
        "updated": "2026-08-10T00:00:00.000Z",
        "next_action": "CLOSED. OWNER, 2026-08-10: G01 sign off. All A00-G01 DONE; Stage 3 opens.",
        "workstreams": ARENA_DESIGN_TASKS,
    },
    {
        "n": 3, "id": "release-readiness",
        "title": "Release readiness & full verification", "status": "IN PROGRESS",
        "purpose": "Full verification and the Owner's explicit release sign-off once the visual "
                   "integration matches the reference.",
        "owners": "Whichever agent holds the card (no gate-holder) + Owner (approval)",
        "criteria": ["All A00-G01 tickets accepted and marked DONE with evidence.",
                     "Full test suite green on PostgreSQL.",
                     "Production smoke checks and rollback path verified.",
                     "OWNER, 2026-08-10: A18's two open accessibility gaps (focus rings on 4 of 6 "
                     "deck controls, 9.2px rank-chip contrast) and G01's contract section-14 "
                     "legal/payment gate (real Stripe token purchases) are DEFERRED TO THIS STAGE "
                     "on his explicit word - not to be worked before it. See "
                     "docs/chef_battle/G01_RELEASE_GATE_EVIDENCE.md.",
                     "Owner grants explicit release approval."],
        "dependencies": "Stage 2 A00-G01 complete.",
        "blockers": [],
        "branch": "Not approved", "commit": "Not approved",
        "verification": "OWNER, 2026-08-10: G01 signed off. Stage started on his word.",
        "updated": "2026-08-10T00:00:00.000Z",
        "next_action": "A18's two gaps and G01's section 14 legal/payment gate are this stage's "
                       "opening items. Full production release still needs the Owner's separate, "
                       "explicit release approval - his G01 sign-off starts this stage, it is not "
                       "that approval.",
    },
]


def _arena_build_context():
    legacy_stages = [
        {**s, "done": bool(s["backend"]["done"] and s["frontend"]["done"])}
        for s in ARENA_LEGACY_BUILD_STAGES
    ]
    legacy_later_stages = [
        {**s, "done": bool(s["backend"]["done"] and s["frontend"]["done"])}
        for s in ARENA_LEGACY_LATER_STAGES
    ]
    # A stage can finish with nothing left to assign - Stage 2 did, on the
    # Owner's G01 sign-off, 2026-08-10. That is a real state, not a bug: the
    # StopIteration this used to raise with no default is the crash v2.5.778
    # caused, and forcing some other card to wear "NEXT" just to avoid it
    # would be exactly the kind of lie about the board this project keeps
    # correcting. None renders as blank in the template.
    next_design_task = next(
        (task for task in ARENA_DESIGN_TASKS if task["status"] == "NEXT"), None
    )
    return {
        "stages": ARENA_RELEASE_STAGES,
        "total": len(ARENA_RELEASE_STAGES),
        "done_count": sum(s["status"] == "DONE" for s in ARENA_RELEASE_STAGES),
        "active_stage": next(s for s in ARENA_RELEASE_STAGES if s["status"] == "IN PROGRESS"),
        "blocker_count": sum(len(s["blockers"]) for s in ARENA_RELEASE_STAGES),
        "release_readiness": "NOT READY",
        "last_verified": "2026-07-29T12:30:00.000Z",
        "design_task_total": len(ARENA_DESIGN_TASKS),
        "design_task_done_count": sum(
            task["status"] == "DONE" for task in ARENA_DESIGN_TASKS
        ),
        "next_design_task": next_design_task,
        "archive": ARENA_ARCHIVE_SUMMARY,
        "legacy_stages": legacy_stages,
        "legacy_later_stages": legacy_later_stages,
        # Derived from the footer this checkout serves, not from the hand-kept
        # RELEASE_JOURNAL. The previous line read RELEASE_JOURNAL[0] under a
        # comment promising the header would never go stale again; it read
        # v2.5.589 while production served v2.5.667, because the list only moves
        # when someone remembers to add an entry.
        "prod_version": current_version(settings.BASE_DIR),
    }


# The build board is a moderation tool: every moderator watches the arena being
# built, same tier as the rest of /recipes/moderation/. It is NOT the Mothership
# (Arena Master Console), which stays behind has_arena_console_access. Guarding
# it with can_grant_bearseeker_privileges was wrong — that gate is about handing
# OUT privileges and only lets superusers through, so bearseeker moderators got
# a 404 on a page meant for them.
def arena_build_plan(request):
    if not is_moderator(request.user):
        raise Http404
    return render(request, "moderation/arena_build_plan.html", _arena_build_context())


def arena_build_plan_public(request, share_token):
    """Read-only mirror of the build board behind an unguessable path segment.

    Owner request, 2026-07-23. The credential is the URL: the secret lives in
    ARENA_BUILD_PLAN_SHARE_TOKEN and never in the repository, because a token
    committed to Git is not a token. With the setting empty the whole route
    disappears — every request 404s, including one carrying an empty segment,
    which is why the emptiness is checked before the comparison.

    The comparison is constant-time. A plain == leaks the token's prefix through
    timing, and this endpoint is reachable by anyone.

    What the link is NOT: a login. Whoever receives it, and whoever they forward
    it to, reads branch names, commit hashes and open blockers. Rotation is
    changing the env value; there is nothing to revoke per person.

    It renders the same read-only template as the moderator route. Operator
    controls live behind arena_build_start — a separate POST endpoint under
    moderation/ with its own is_moderator gate — so nothing here can start a
    stage or message an agent. Arena visibility is untouched: the Arena itself
    stays staff/superuser only during dark launch.
    """
    import secrets

    expected = getattr(settings, "ARENA_BUILD_PLAN_SHARE_TOKEN", "")
    if not expected or not secrets.compare_digest(str(share_token), str(expected)):
        raise Http404
    response = render(request, "moderation/arena_build_plan.html", _arena_build_context())
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@require_POST
def arena_build_start(request):
    if not is_moderator(request.user):
        raise Http404
    stage_id = (request.POST.get("stage") or "").strip()
    stage = next((s for s in ARENA_LEGACY_BUILD_STAGES if s["id"] == stage_id), None)
    if stage is None:
        return JsonResponse({"ok": False, "error": "Unknown stage."}, status=400)

    from coworking.models import CoworkingMessage
    from django.utils import timezone
    ts = timezone.now().strftime("%H:%M:%S")
    subject = "START stage %d: %s -- ПОДНИМИТЕ ЖОПЫ, РАБОТАЙТЕ" % (stage["n"], stage["title"])
    body = (
        "ВЛАДЕЛЕЦ НАЖАЛ START. Немедленно вскакивайте и работайте по этой стадии до зелёного "
        "(готово, запушено, задеплоено на прод).\n\n"
        "СТАДИЯ %d: %s\n"
        "BACKEND (%s): %s\n"
        "FRONTEND (%s): %s\n"
        "ЗАВИСИМОСТЬ: %s\n\n"
        "Backend делает свою часть, отдаёт контракт -> Frontend строит поверх. Сотрудничайте "
        "живыми сообщениями, без пульса. Как задеплоите на прод -- отчитайтесь, пункт станет "
        "зелёным. Время сигнала: %s.\n-- Owner via Arena Build board"
    ) % (
        stage["n"], stage["title"],
        stage["backend"]["who"], stage["backend"]["task"],
        stage["frontend"]["who"], stage["frontend"]["task"],
        stage["depends"], ts,
    )
    sent = []
    for agent in ("bolt", "greenbear"):
        try:
            m = CoworkingMessage.send(from_agent="owner", to_agent=agent, subject=subject, body=body)
            sent.append(agent)
        except Exception:
            pass
    return JsonResponse({"ok": True, "stage": stage["n"], "signalled": sent, "at": ts})


def site_research_progress(request):
    if not _can_view_site_update_plan(request.user):
        raise Http404

    return render(
        request,
        "moderation/site_research_progress.html",
        {"research": _build_site_research_progress()},
    )


def deployment_journal(request):
    if not is_moderator(request.user):
        raise Http404

    return render(
        request,
        "moderation/deployment_journal.html",
        {"release_journal": build_git_journal(settings.BASE_DIR)},
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
def moderate_clan(request, slug):
    # F22, 2026-08-11: same class of gap as F8/F16 - is_moderator() alone
    # admits has_bearseeker_privileges regardless of is_staff, and this write
    # action mutates a Chef Battle model (Clan.moderation_status; approving
    # makes the clan publicly live) without checking is_battle_visible().
    from chef_battle.access import is_battle_visible
    if not (is_moderator(request.user) and is_battle_visible(request)):
        raise Http404
    from chef_battle.models import Clan

    clan = get_object_or_404(Clan, slug=slug)
    action = request.POST.get("action")
    if action == "approve":
        clan.moderation_status = Clan.Moderation.APPROVED
        clan.save(update_fields=["moderation_status"])
        messages.success(request, f'Clan "{clan.name}" approved and is now live.')
    elif action == "reject":
        clan.moderation_status = Clan.Moderation.REJECTED
        clan.save(update_fields=["moderation_status"])
        messages.warning(request, f'Clan "{clan.name}" rejected.')
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


# ── Regenerate full recipe text content in-place ──────────────────────────────

@require_POST
@login_required
def recipe_regenerate_text(request, slug):
    """Re-run AI generation for an existing recipe, overwriting its text fields.

    Accepts POST: custom_prompt (optional additional instructions).
    Runs synchronously — only moderators may call this.
    Returns JSON: {success, redirect_url} or {success:false, error}.
    """
    from .management.commands.generate_recipe import _call_anthropic, _normalise_recipe_payload, _map_additional_categories

    recipe = get_object_or_404(Recipe, slug=slug)
    if not (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author)):
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return JsonResponse({"success": False, "error": "ANTHROPIC_API_KEY is not configured."}, status=500)

    custom_prompt = request.POST.get("custom_prompt", "").strip()
    hint_category = recipe.category if recipe.category else ""

    try:
        payload = _call_anthropic(recipe.title, hint_category=hint_category, custom_prompt=custom_prompt)
        fields = _normalise_recipe_payload(payload, recipe.title, recipe.status)
        additional_categories = _map_additional_categories(payload.get("additional_categories"), fields["category"])

        text_fields = [
            "short_description", "category", "difficulty",
            "prep_time_minutes", "cook_time_minutes", "servings", "calories",
            "ingredients", "method", "tips", "irish_context", "author_commentary", "allergens",
        ]
        for f in text_fields:
            if f in fields:
                setattr(recipe, f, fields[f])
        recipe.save(update_fields=text_fields)

        from recipes.models import RecipeAdditionalCategory
        RecipeAdditionalCategory.objects.filter(recipe=recipe).delete()
        for cat in additional_categories:
            RecipeAdditionalCategory.objects.create(recipe=recipe, category=cat)

        logger.info("recipe_regenerate_text: regenerated text for %r by %s", recipe.slug, request.user.username)
        return JsonResponse({"success": True, "redirect_url": recipe.get_absolute_url()})

    except Exception as exc:
        logger.error("recipe_regenerate_text failed for %r: %s", recipe.slug, exc, exc_info=True)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


# ── AI hero image generation for new (unsaved) recipes ────────────────────────

@require_POST
@login_required
def recipe_ai_generate_hero(request):
    """Generate a hero image for a recipe that hasn't been saved yet.

    Accepts: title, alt_text, feedback (all POST).
    Returns JSON: {success, url, temp_filename}
    The temp_filename is a path relative to MEDIA_ROOT that the create-view
    picks up on form submit and assigns to recipe.hero_image.
    """
    import uuid
    from django.core.files.base import ContentFile
    from .management.commands.generate_recipe import fetch_image_bytes, _image_extension, _sanitise_image_subject

    if not bool(getattr(settings, "OPENAI_API_KEY", "")):
        return JsonResponse({"success": False, "error": "Image generation is not configured."}, status=503)

    author = getattr(request.user, "recipe_author_profile", None)
    if not (is_moderator(request.user) or (author and author.can_generate_ai_images)):
        return JsonResponse({"success": False, "error": "Not authorized."}, status=403)

    title = request.POST.get("title", "").strip()
    alt_text = request.POST.get("alt_text", "").strip()
    feedback = request.POST.get("feedback", "").strip()

    if not title:
        return JsonResponse({"success": False, "error": "Recipe title is required."}, status=400)

    try:
        subject = _sanitise_image_subject(title, alt_text)
        prompt = (
            f"Professional food photography: {subject}. "
            "Irish cuisine, natural light, rustic wooden surface, ceramic or white plate, "
            "appetising close-up presentation. No text, no watermarks, no people, no brand names or logos."
        )
        if feedback:
            prompt += f" Important: {feedback}."

        image_bytes = fetch_image_bytes(prompt)
        ext = _image_extension(image_bytes)
        uid = uuid.uuid4().hex[:12]
        filename = f"recipe_images/temp_hero_{uid}{ext}"

        from django.core.files.storage import default_storage
        saved_path = default_storage.save(filename, ContentFile(image_bytes))
        url = default_storage.url(saved_path)

        return JsonResponse({"success": True, "url": url, "temp_filename": saved_path})

    except Exception as exc:
        logger.error("recipe_ai_generate_hero failed: %s", exc, exc_info=True)
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


# ── Recipe Studio (Premium form) ───────────────────────────────────────────────

@login_required
def recipe_studio_view(request):
    """Premium unified recipe creation form for moderators (incl. staff/superusers)."""
    if not is_moderator(request.user):
        raise Http404

    from .models import ALLERGEN_CHOICES, RecipeAdditionalCategory
    from .management.commands.generate_recipe import _unique_slug

    authors = RecipeAuthor.objects.filter(user__isnull=False).order_by("name")
    default_author = RecipeAuthor.objects.filter(user=request.user).first()

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        if not title:
            messages.error(request, "Title is required.")
            return redirect("recipes:recipe_studio")

        author_slug = request.POST.get("author_slug", "").strip()
        author = RecipeAuthor.objects.filter(slug=author_slug).first()
        if not author:
            author = default_author
        if not author:
            messages.error(request, "No author found. Please select one.")
            return redirect("recipes:recipe_studio")

        # Collect dynamic method steps
        step_count = int(request.POST.get("step_count", "0") or 0)
        step_texts = []
        step_images = []   # (file_obj, ai_temp_path)
        for i in range(1, step_count + 1):
            text = request.POST.get(f"step_text_{i}", "").strip()
            image = request.FILES.get(f"step_image_{i}")
            ai_image_path = request.POST.get(f"step_ai_image_{i}", "").strip()
            if text:
                step_texts.append(text)
                step_images.append((image, ai_image_path))

        method = "\n".join(step_texts)

        # Allergens
        allergen_keys = request.POST.getlist("allergens")
        valid_allergen_keys = {k for k, _ in ALLERGEN_CHOICES}
        allergens = ",".join(k for k in allergen_keys if k in valid_allergen_keys)

        # Category
        category = request.POST.get("category", "").strip()
        valid_categories = {c.value for c in Recipe.Category}
        if category not in valid_categories:
            category = Recipe.Category.EVERYDAY_IRISH_COOKING

        status = request.POST.get("status", Recipe.Status.PENDING)
        if status not in (Recipe.Status.DRAFT, Recipe.Status.PENDING, Recipe.Status.APPROVED):
            status = Recipe.Status.PENDING
        if status == Recipe.Status.APPROVED and not (request.user.is_staff or request.user.is_superuser):
            status = Recipe.Status.PENDING

        def _safe_int(key, default=0, minimum=0):
            try:
                return max(int(request.POST.get(key, default) or default), minimum)
            except (TypeError, ValueError):
                return default

        slug = _unique_slug(title)

        recipe = Recipe(
            title=title,
            slug=slug,
            short_description=request.POST.get("short_description", "").strip(),
            author=author,
            category=category,
            difficulty=request.POST.get("difficulty", Recipe.Difficulty.EASY),
            prep_time_minutes=_safe_int("prep_time_minutes"),
            cook_time_minutes=_safe_int("cook_time_minutes"),
            servings=_safe_int("servings", default=4, minimum=1),
            calories=_safe_int("calories") or None,
            ingredients=request.POST.get("ingredients", "").strip(),
            method=method,
            tips=request.POST.get("tips", "").strip(),
            irish_context=request.POST.get("irish_context", "").strip(),
            author_commentary=request.POST.get("author_commentary", "").strip(),
            allergens=allergens,
            hero_image_alt_text=request.POST.get("hero_image_alt_text", "").strip(),
            source_type=request.POST.get("source_type", Recipe.SourceType.ORIGINAL),
            image_rights_status=Recipe.ImageRightsStatus.OWN,
            confirmed_own_work=True,
            confirmed_image_rights=True,
            confirmed_rules=True,
            status=status,
        )

        hero_image = request.FILES.get("hero_image")
        if hero_image:
            recipe.hero_image = hero_image

        # AI-generated hero image (temp path from studio AI generate)
        ai_hero_path = request.POST.get("ai_hero_image_path", "").strip()
        if ai_hero_path and not hero_image:
            import os
            if default_storage.exists(ai_hero_path):
                image_bytes = default_storage.open(ai_hero_path).read()
                ext = os.path.splitext(ai_hero_path)[1] or ".jpg"
                recipe.image_rights_status = Recipe.ImageRightsStatus.AI_GENERATED
                openai_model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
                recipe.image_rights_note = f"AI-generated image via {openai_model}."
                recipe.hero_image.save(f"recipe_images/studio-cover{ext}", ContentFile(image_bytes), save=False)
                try:
                    default_storage.delete(ai_hero_path)
                except Exception:
                    pass

        recipe.save()

        # Step images → RecipeImage
        import os as _os
        for idx, (text, (img_file, ai_img_path)) in enumerate(zip(step_texts, step_images), start=1):
            if img_file:
                RecipeImage.objects.create(
                    recipe=recipe,
                    image=img_file,
                    sort_order=idx,
                    alt_text=text[:200],
                    caption=f"Step {idx}",
                )
            elif ai_img_path and default_storage.exists(ai_img_path):
                img_bytes = default_storage.open(ai_img_path).read()
                ext = _os.path.splitext(ai_img_path)[1] or ".jpg"
                ri = RecipeImage(recipe=recipe, sort_order=idx, alt_text=text[:200], caption=f"Step {idx}")
                ri.image.save(f"recipe_images/step-{idx}{ext}", ContentFile(img_bytes), save=True)
                try:
                    default_storage.delete(ai_img_path)
                except Exception:
                    pass

        # Additional categories
        extra_cats = request.POST.getlist("additional_categories")
        for cat in extra_cats:
            if cat in valid_categories and cat != category:
                RecipeAdditionalCategory.objects.get_or_create(recipe=recipe, category=cat)

        logger.info("recipe_studio: created recipe %r by %s", recipe.slug, request.user.username)

        if status == Recipe.Status.APPROVED:
            messages.success(request, "Recipe published.")
        elif status == Recipe.Status.DRAFT:
            messages.success(request, "Recipe saved as draft.")
        else:
            messages.success(request, "Recipe submitted for review.")
            _send_recipe_notification(recipe, "pending")

        return redirect(recipe.get_absolute_url())

    return render(request, "authoring/recipe_studio.html", {
        "authors": authors,
        "default_author": default_author,
        "category_choices": Recipe.Category.choices,
        "difficulty_choices": Recipe.Difficulty.choices,
        "allergen_choices": ALLERGEN_CHOICES,
        "status_choices": [
            (Recipe.Status.PENDING, "Submit for review"),
            (Recipe.Status.DRAFT, "Save as draft"),
            (Recipe.Status.APPROVED, "Publish immediately"),
        ],
        "has_openai": bool(getattr(settings, "OPENAI_API_KEY", "")),
        "default_step_count": 3,
    })


@require_POST
@login_required
def recipe_studio_ai_fill(request):
    """Synchronous AI fill for the Premium Studio form.

    POST JSON: {dish_name, custom_prompt, category}
    Returns JSON with all recipe text fields pre-filled.
    """
    if not is_moderator(request.user):
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return JsonResponse({"success": False, "error": "ANTHROPIC_API_KEY is not configured."}, status=500)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST.dict()

    dish_name = (data.get("dish_name") or "").strip()
    custom_prompt = (data.get("custom_prompt") or "").strip()
    hint_category = (data.get("category") or "").strip()

    if not dish_name:
        return JsonResponse({"success": False, "error": "dish_name is required."}, status=400)

    valid_categories = {c.value for c in Recipe.Category}
    if hint_category not in valid_categories:
        hint_category = ""

    try:
        from .management.commands.generate_recipe import (
            _call_anthropic, _normalise_recipe_payload, _map_additional_categories,
        )
        payload = _call_anthropic(dish_name, hint_category=hint_category, custom_prompt=custom_prompt)
        fields = _normalise_recipe_payload(payload, dish_name, Recipe.Status.DRAFT)
        additional = _map_additional_categories(payload.get("additional_categories"), fields["category"])

        # Split method into individual steps
        method_steps = [s.strip() for s in (fields.get("method") or "").splitlines() if s.strip()]

        return JsonResponse({
            "success": True,
            "fields": {
                "title": fields.get("title", ""),
                "short_description": fields.get("short_description", ""),
                "category": fields.get("category", ""),
                "difficulty": fields.get("difficulty", ""),
                "prep_time_minutes": fields.get("prep_time_minutes", ""),
                "cook_time_minutes": fields.get("cook_time_minutes", ""),
                "servings": fields.get("servings", ""),
                "calories": fields.get("calories", "") or "",
                "ingredients": fields.get("ingredients", ""),
                "method_steps": method_steps,
                "tips": fields.get("tips", ""),
                "irish_context": fields.get("irish_context", ""),
                "author_commentary": fields.get("author_commentary", ""),
                "allergens": (fields.get("allergens") or "").split(","),
                "hero_image_alt_text": payload.get("hero_image_alt_text", ""),
                "additional_categories": additional,
            },
        })
    except Exception as exc:
        logger.error("recipe_studio_ai_fill failed: %s", exc, exc_info=True)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)
