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
from config.release_journal import RELEASE_JOURNAL, build_git_journal
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
    _flag_on = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    _u = request.user
    _ap = getattr(_u, "recipe_author_profile", None) if _u and _u.is_authenticated else None
    chef_battle_enabled = _flag_on or bool(
        _u and _u.is_authenticated and (
            _u.is_staff or _u.is_superuser
            or (_ap and _ap.has_bearseeker_privileges)
        )
    )

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
        from chef_battle.selectors import active_battle_locking_recipe
        recipe = self.get_object()
        battle = active_battle_locking_recipe(recipe)
        if battle is None:
            return None
        messages.error(
            self.request,
            "This recipe is in a live Chef Battle right now, so it is locked "
            "until the battle finishes. You can edit it again once the battle "
            "is over.",
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

    from chef_battle.models import Clan

    pending_clans = list(
        Clan.objects.select_related("founder")
        .filter(moderation_status=Clan.Moderation.PENDING, is_active=True)
        .prefetch_related("categories")
        .order_by("-created_at")
    )

    return render(request, "moderation/panel.html", {
        "pending_clans": pending_clans,
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

ARENA_RELEASE_STAGES = [
    {
        "n": 1, "id": "baseline", "title": "Project Baseline & Governance", "status": "DONE",
        "purpose": "Establish the canonical technical and operational baseline.",
        "owners": "Owner, Bolt, GreenBear, Ember",
        "criteria": ["Five canonical documents are active.", "Legacy Markdown archive is complete.",
                     "CoWork governance and agent ownership rules are established.",
                     "Repository baseline commit is recorded."],
        "dependencies": "None — this is the release baseline.", "blockers": [],
        "branch": "main", "commit": "d852fff53b8de0f7fcd46897c4ce287c6abe8a0d",
        "verification": "Canonical active set and documentation reset verified on main.",
        "updated": "2026-07-21T11:45:58.810Z", "next_action": "Retain as the immutable baseline for this release.",
    },
    {
        "n": 2, "id": "spec-lock", "title": "Audit & Technical Specification Lock", "status": "DONE",
        "purpose": "Identify defects, lock product decisions, and establish implementation scope.",
        "owners": "Bolt, GreenBear, audit agents, Owner",
        "criteria": ["Backend audit complete.", "Frontend audit complete.", "Corrected synthesis complete.",
                     "Owner access, layout, token, popup, Battle Room, and Master Console decisions recorded."],
        "dependencies": "Stage 1 governance baseline.", "blockers": [],
        "branch": "audit branches / synthesis", "commit": "be5495b… · 7061155… · 1586ec2…",
        "verification": "Backend be5495b5; frontend 70611557; synthesis 1586ec2e recorded in Git.",
        "updated": "2026-07-21T11:45:58.810Z", "next_action": "Use the locked synthesis as the implementation authority.",
    },
    {
        "n": 3, "id": "implementation", "title": "Arena Implementation", "status": "IN PROGRESS",
        "purpose": "Implement every approved backend and frontend release requirement.",
        "owners": "3A and 3B deployed; 3E code deployed (verification pending); 3C, 3D open. Pool: Bolt and Ember on weekly limits; GreenBear (6-core) near limit; Cursor (8-core) is the carrying agent.",
        "criteria": ["All mandatory workstreams complete.",
                     "Every blocker resolved or explicitly removed from release scope by the owner.",
                     "All implementation branches committed and pushed.", "No overlapping file ownership.",
                     "3A and 3B are merged to main and deployed; 3C, 3D, and 3E remain open.",
                     "Full distributed verification of the current Arena presentation remains pending; the last recorded distributed gate targeted d8f08f22."],
        "dependencies": "Stages 1 and 2 DONE.",
        "blockers": ["3D remains OPEN: owner must select or reject the country/flag data model.",
                     "CF5 (definition recovered from the Stage 2 audit synthesis, CoWork #1950): 'battle_detail.html a11y coverage 4 vs arena.html 20' — a LOW-severity accessibility gap on the Battle Room detail template. Needs no owner decision; add semantic roles/aria/focus. Now assigned to GreenBear+Cursor."],
        "branch": "impl/arena-access-and-context · impl/arena-frontend-a11y-tokens-ember",
        "commit": "ce43242b65fc3d0ca8a259544ab4d1ffb9f7eaf8 · 0dbac5e99c1c1071da966d1ede36926e489600ed",
        "verification": "3A is deployed and distributed verified. 3B is deployed and passed authenticated production re-QA 19/19 within its recorded scope. 3C, 3D, and 3E have partial deployed implementation but remain open.",
        "updated": "2026-07-23T00:02:37.965Z",
        "next_action": "Resolve the 3D country/flag data decision, then complete and verify the remaining 3C, 3D, and 3E acceptance gaps without broadening existing evidence.",
        "workstreams": [
            {"id": "3A", "title": "Backend access and initial-render context", "owner": "Bolt",
             "status": "DEPLOYED AND DISTRIBUTED VERIFIED",
             "requirements": ["Registered-author dark-launch access branch removed; Arena visibility is staff/superuser-only.",
                              "Arena Hall and Battle Room inherit the corrected policy through @chef_battle_guard and is_battle_visible().",
                              "arena_react now checks is_battle_visible().",
                              "battle_chat_poll now checks is_battle_visible().",
                              "battle_chat_send remains unchanged and retains its existing @chef_battle_guard.",
                              "Top-level crown_streak, crown_ladder, and recent_gifts supplied in the initial-render context.",
                              "Regression-test definitions updated for the new access and initial-render behaviour; stale proto-gate test renamed."],
             "evidence": "Owner Bolt (integration/deployment). Source branch impl/arena-access-and-context, source commit ce43242b65fc3d0ca8a259544ab4d1ffb9f7eaf8. Integration method: clean cherry-pick onto main (the 3 backend files were unchanged on main since base d852fff5). Resulting main commit f3edd72453f904a8f1cadd539a3a2e36dfb97029; deployed production commit f3edd724. Three changed files: chef_battle/access.py, chef_battle/views.py, chef_battle/tests.py. Static verification: py_compile, manage.py check clean, git diff --check clean; access-policy inspection confirmed the author branch is absent from is_battle_visible and that arena_react and battle_chat_poll call is_battle_visible while battle_chat_send keeps @chef_battle_guard. Deploy ran /srv/culineire/scripts/deploy.sh as the deploy user; no migrations; Unit restarted via restricted sudo and active; production checkout clean at f3edd724. Server-side production verification (deployed code, RequestFactory): anonymous Arena route returns 404 (gate intact, no widening); is_battle_visible = False for anonymous AND for a plain non-staff author, True for staff and superuser; arena_react and battle_chat_poll gated; battle_chat_send guard preserved; top-level crown_streak/crown_ladder/recent_gifts present in the arena render context; no new server errors. Tests not yet run: the distributed manifest and run_id are owned by GreenBear; the Bolt 8-core shard will run only against that manifest. Authenticated browser QA (initial-render visual) is Ember's. CoWork: 1960-1962 (impl), 1977/1978/1979 (integration start), STAGE_3A_DEPLOYED posted separately. DISTRIBUTED VERIFICATION COMPLETE (coordinator GreenBear, run_id arena-stage3-20260721-2213-d8f08f22, target commit d8f08f224a11dab4ce3ba5051cead32029d5a604 = origin/main = production): 154 tests over 13 whole test classes, split into two disjoint shards with zero shared labels and no test method split across machines. GreenBear 6-core shard, 7 classes, 64 tests, 6 workers, 110.5s: 64 passed, 0 failed, 0 errors, 0 skipped. Bolt 8-core shard, 6 classes, 90 tests, 113.9s: 90 passed, 0 failed, 0 errors, 0 skipped. Combined 154/154 passed with zero failures. The Stage 3A behaviour is directly covered by the GreenBear shard: ArenaDarkLaunchTests (CF0 author lock-out, CF2 arena_react gate, CF3 battle_chat_poll gate), ArenaInitialRenderContextTests (CF1 top-level context), and the renamed CF6 test in ArenaMasterConsoleAccessTests. Methodological caveat recorded rather than hidden: the two shards ran on different database backends (GreenBear PostgreSQL, Bolt SQLite per its own report), so any PostgreSQL-specific constraint behaviour was exercised only on the GreenBear side. CoWork evidence: manifest 1993/1994/1995, BOLT_SHARD_RESULT 1996/1997/1998."},
            {"id": "3B", "title": "Frontend accessibility and token migration", "owner": "Bolt (integration/deploy); original owner GreenBear; implementation Ember",
             "status": "DEPLOYED — AUTHENTICATED PRODUCTION RE-QA PASSED 19/19",
             "requirements": ["Popup focus entry, Tab and Shift+Tab trap, Escape close, visible close control, and focus return — implemented in arena_battle_room.js.",
                              "Popup remains preview/navigation only; the full-screen Battle Room link targets the separate full page.",
                              "Independent dark palette removed in favour of official light/parchment tokens.",
                              "Raw colours removed: zero hex/rgb/hsl across all 8 arena stylesheets and both arena scripts (no exceptions remain)."],
             "evidence": "Original frontend source commit 0dbac5e99c1c1071da966d1ede36926e489600ed was integrated and deployed as 6a2b5f52536f5b7de9aea706b1fbb1b26d8f8e11. Ember remediation source commit db017dad1ced81925be4f125d3639a6c20fb8eeb was deployed as 388f7776b433929902476f12891834eebb36f1c1; CoWork 2029/2030/2031. GreenBear then performed authenticated production re-QA and reported 19/19 PASS; synthesis CoWork 2035/2036/2037. Verified scope: the photographic backdrop is absent, all 544 illustrated crowd figures are restored, the popup is mounted under BODY at z-index 10000, its visible close control receives and handles a real pointer click, and the parchment palette, dialog semantics, focus entry, Tab and Shift+Tab trap, Escape close, exact-opener focus return, Master Console, separate full-page Battle Room, and arena overflow at desktop 1920 and mobile 390 all passed. Scope limitation: the popup was opened programmatically because production had no active battle; creating a demo battle was prohibited, so the live-battle tile click path itself was not exercised. The observed 6px mobile document overflow belongs to the site header, not the Arena. CF5 remains OPEN and UNASSIGNED and is not closed or reinterpreted by this 3B result."},
            {"id": "3C", "title": "Real spectator overlay", "owner": "Unassigned",
             "status": "OPEN",
             "requirements": ["Atmospheric crowd presentation may match the approved mockup but must not impersonate registered or online users.",
                              "Keep the eight interactive rings and 544 seats for real viewers only, assigned front rows first; do not place synthetic occupants in interactive seats.",
                              "A logged-in visitor can see themselves seated."],
             "evidence": "PARTIAL DEPLOYED IMPLEMENTATION at production baseline 0342760f: the Arena supplies live spectator data, assigns real viewers from the front rows across eight rings / 544 seats, and supports self-seating for the logged-in viewer. The workstream remains OPEN because unused interactive seats are still populated with synthetic default-avatar stand-ins and no completion verification has been recorded."},
            {"id": "3D", "title": "Chef confrontation panels", "owner": "Owner decision required",
             "status": "OPEN",
             "requirements": ["Follow the approved mockup composition: challenger in the green left panel and opponent in the red right panel, integrated around the central Crown Holder focal area.",
                              "Display each participant's real photo and name.",
                              "Display a flag only after an approved country-data source exists."],
             "evidence": "PARTIAL DEPLOYED IMPLEMENTATION at production baseline 0342760f: real battle participant names and photos are data-bound into left/right confrontation cards with green/red styling. The workstream remains OPEN: integration around the central Crown Holder composition is incomplete, RecipeAuthor has no approved country field, and the specific blocker is the Product Owner's country/flag data-source decision."},
            {"id": "3E", "title": "Rank floor column", "owner": "GreenBear + Cursor (Ember's suspended VERIFY_AND_CLOSE_STAGE_3E is now ours)",
             "status": "CODE DEPLOYED — VERIFICATION PENDING",
             "requirements": ["Display KITCHEN PORTER through CULINARY MASTER over the floor.",
                              "Measure contrast at 7:1 or higher and record numeric evidence."],
             "evidence": "DEPLOYED in release v2.5.392 (commit 2fd70161, prod d5ddb798). Both prior board gaps are now CLOSED: the eight ranks render as an ordered <ol>; contrast is recorded numerically in ops/audits/stage_3e_rank_column.json (--ink #1f2c25 on --surface #fffdf9 = 14.30:1 label, 12.62:1 count, both clearing 7:1); and the rank column is no longer display:none below 768px — it becomes a wrapped row so all eight ranks stay visible on mobile. ArenaRankColumnTests 7/7 pass. REMAINING to close the workstream: the distributed 8:6:1 gate (now runnable as Cursor 8-core + GreenBear 6-core + Linode 1-core) and live authenticated browser QA — Ember's suspended independent review, now carried by GreenBear+Cursor."},
            {"id": "3F", "title": "Legacy completed production capabilities", "owner": "Bolt / GreenBear",
             "status": "DONE — HISTORICAL EVIDENCE",
             "requirements": ["Full-bleed Arena layout.", "HUD positioned around the Arena.",
                              "Database self-vote protection.", "Versioned HMAC vote hashing."],
             "evidence": "Production history retained in Legacy Arena Milestones and Deployment Journal."},
            {"id": "3G", "title": "Visual integration (composition redesign)", "owner": "Cursor (composition/polish); ArenaFront (atmosphere assets)",
             "status": "IN PROGRESS — r10c + af5–af38 (v2.5.510)",
             "requirements": ["Carry only composition decisions from the isolated prototype into the existing Arena; the prototype is a reference, never a new frontend.",
                              "Replace every prototype token with the official CulinEire palette; no raw colour literals and no parallel visual system.",
                              "Keep the official brand assets, Playfair Display and Inter typography, and the existing octagonal geometry (get_arena_geometry sides: 8).",
                              "Preserve the existing models, backend, templates, CSS, JavaScript, spectator rings, ranks, battle state, and interactive elements.",
                              "Deliver in one-slice-one-branch-one-gate order R0 through R6, each independently deployable and revertible.",
                              "Record every slice in the Deployment Journal, this board, and ops/audits/ evidence artifacts.",
                              "Both agents must update this board + config/release_journal.py after every meaningful Arena slice/deploy (Owner 2026-07-24).",
                              "Owner no-idle: continuous visible slices (Owner 2026-07-24)."],
             "evidence": "R0/R1 done. Cursor r10c. ArenaFront af5–af38. Load order polish r10c → atmosphere af38 (v2.5.510). Pair workflow. fitScene preserved. Fence held. D2/D3 open. 8:6:1 NOT claimed.",
             "blockers": ["D2 stands: keep 544 real seats plus non-impersonating atmosphere, or remove the stands and close 3C as out of scope.",
                          "D3 country/flag data source (blocks flag in confrontation band only).",
                          "D4: Owner exempted full 8:6:1 while pool depleted for focused slices — still record honesty when a full gate is skipped."]},
        ],
    },
    {
        "n": 4, "id": "integration", "title": "Integration & Code Review", "status": "NOT STARTED",
        "purpose": "Combine approved implementation commits without releasing them.", "owners": "Integration owner (unassigned)",
        "criteria": ["One temporary integration branch with exact backend and frontend commits recorded.",
                     "Merge conflicts resolved; scope review complete; no unrelated files included.",
                     "Security and access policy reviewed; integration commit created.", "No production deployment."],
        "dependencies": "Stage 3 DONE.", "blockers": [], "branch": "Not created", "commit": "Not recorded",
        "verification": "Not started.", "updated": "2026-07-21T11:45:58.810Z",
        "next_action": "After Stage 3 closes, create the temporary integration branch and perform review.",
    },
    {
        "n": 5, "id": "verification", "title": "Distributed Verification", "status": "BLOCKED",
        "purpose": "Verify the integration commit across the available proper test machines.",
        "owners": "Bolt (8-core), GreenBear (6-core)",
        "criteria": ["One run_id and one explicit test manifest.", "Non-overlapping test shards.",
                     "Bolt and GreenBear machines used efficiently; Linode 1-core excluded from application/project suites.",
                     "All results aggregated with zero unexplained failures.",
                     "Exact test counts, durations, and failures recorded."],
        "dependencies": "Stage 4 integration commit.",
        # The old blocker here was "GreenBear 6-core environment is currently
        # rate-limited". That is no longer true and has been removed rather than
        # left to rot. It is replaced, not simply deleted: this stage is still
        # BLOCKED, but by the sequential pipeline rather than by capacity, and a
        # stage marked BLOCKED with an empty blocker list would read as an
        # oversight.
        "blockers": ["Sequentially dependent on Stage 3 completion (workstreams 3C, 3D, 3E open) and on the Stage 4 integration commit, which does not exist yet. Test capacity itself is no longer a blocker."],
        "branch": "main", "commit": "d8f08f224a11dab4ce3ba5051cead32029d5a604",
        "verification": "Distributed-verification capacity is RESTORED: the GreenBear 6-core environment is no longer rate-limited and has executed a full shard. One run has been performed under coordinator GreenBear, run_id arena-stage3-20260721-2213-d8f08f22, against commit d8f08f224a11dab4ce3ba5051cead32029d5a604 (verified equal to origin/main and to the production HEAD, with a clean production checkout and Unit active). Manifest: 154 tests over 13 whole test classes, two disjoint shards, zero shared labels, no test method split across machines, Linode 1-core excluded by design. GreenBear 6-core: 7 classes, 64 tests, 6 workers, 110.5s, 64 passed / 0 failed / 0 errors / 0 skipped. Bolt 8-core: 6 classes, 90 tests, 113.9s, 90 passed / 0 failed / 0 errors / 0 skipped. Combined 154/154 passed. Shard balance 41.6 / 58.4 against the 6:8 target of 42.9 / 57.1, split by test count because no historical per-class duration data existed; the durations recorded here are the first such data and should be used to balance the next run. Caveat recorded rather than hidden: the shards ran on different database backends (GreenBear PostgreSQL, Bolt SQLite), so PostgreSQL-specific constraint behaviour was exercised on one side only. This stage is NOT marked active or DONE: it remains sequentially dependent on the completion of Stages 3 and 4, and Stage 3 still has open workstreams.",
        "updated": "2026-07-22T00:00:00.000Z",
        "next_action": "Hold for Stage 3 completion and the Stage 4 integration commit. Capacity is available on demand; the next run should be balanced using the durations recorded above.",
    },
    {
        "n": 6, "id": "live-qa", "title": "Live Functional & Accessibility QA", "status": "NOT STARTED",
        "purpose": "Verify the release candidate through real user flows and supported viewport sizes.",
        "owners": "QA owner (unassigned)",
        "criteria": ["Staff/superuser access verified and registered non-staff denied.",
                     "Arena Hall initial render and Battle Room full-page navigation verified.",
                     "Popup keyboard entry, trap, Escape, close, and focus return verified.",
                     "Responsive checks at 390px and 1920px with no Arena-caused horizontal overflow.",
                     "Reduced motion, numeric contrast, and Master Console compatibility verified."],
        "dependencies": "Stage 5 DONE with zero unexplained failures.", "blockers": [],
        "branch": "Release-candidate branch not recorded", "commit": "Release-candidate commit not recorded",
        "verification": "Not started.", "updated": "2026-07-21T11:45:58.810Z",
        "next_action": "After distributed verification, execute the live QA matrix and record evidence.",
    },
    {
        "n": 7, "id": "owner-acceptance", "title": "Owner Acceptance & Release Candidate", "status": "NOT STARTED",
        "purpose": "Present one fully verified release candidate to the owner.", "owners": "Owner and release coordinator",
        "criteria": ["Stages 1 through 6 DONE with no unresolved release blocker.",
                     "Final commit SHA and complete change, test, and QA evidence recorded.",
                     "Known limitations and rollback plan prepared.", "Owner explicitly approves or rejects release."],
        "dependencies": "Stages 1–6 DONE.", "blockers": [], "branch": "Not selected", "commit": "Not recorded",
        "verification": "Readiness result: NOT READY.", "updated": "2026-07-21T11:45:58.810Z",
        "next_action": "Complete Stages 3–6 before requesting owner acceptance.",
    },
    {
        "n": 8, "id": "deployment", "title": "Deployment & Post-Deploy Verification", "status": "FROZEN",
        "purpose": "Deploy the approved release candidate and verify production.", "owners": "Owner-approved deployer",
        "criteria": ["Owner approval recorded and approved commit deployed.",
                     "Deployment Journal and version updated where required.",
                     "collectstatic performed where required; migration status verified.",
                     "Production access policy and smoke checks passed; rollback path verified.",
                     "Arena Build Plan updated to RELEASED."],
        "dependencies": "Stage 7 DONE with explicit owner approval.",
        "blockers": ["Requires explicit owner release approval."], "branch": "Not approved", "commit": "Not approved",
        "verification": "Frozen; no deployment or production verification performed.",
        "updated": "2026-07-21T11:45:58.810Z", "next_action": "Wait for explicit owner release approval.",
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
    return {
        "stages": ARENA_RELEASE_STAGES,
        "total": len(ARENA_RELEASE_STAGES),
        "done_count": sum(s["status"] == "DONE" for s in ARENA_RELEASE_STAGES),
        "active_stage": next(s for s in ARENA_RELEASE_STAGES if s["status"] == "IN PROGRESS"),
        "blocker_count": sum(len(s["blockers"]) for s in ARENA_RELEASE_STAGES),
        "release_readiness": "NOT READY",
        "last_verified": "2026-07-21T11:45:58.810Z",
        "archive": ARENA_ARCHIVE_SUMMARY,
        "legacy_stages": legacy_stages,
        "legacy_later_stages": legacy_later_stages,
        # Track the real latest release so the board header never goes stale
        # again (it was pinned to v2.5.326 while prod had moved several releases
        # past it). RELEASE_JOURNAL is newest-first.
        "prod_version": "v" + RELEASE_JOURNAL[0]["version"],
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
    if not is_moderator(request.user):
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
