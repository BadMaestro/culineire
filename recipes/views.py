import re

from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Avg, Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from articles.models import Article
from .allergens import build_present_allergen_items
from .forms import RecipeCommentForm, RecipeRatingForm
from .models import Recipe, RecipeAuthor, RecipeComment, RecipeImage, RecipeRating


METHOD_STEP_PREFIX_RE = re.compile(r"^\d+\.\s*")
INGREDIENT_DETAIL_SPLIT_RE = re.compile(r"\s*(?:-|–|—|:)\s*", re.UNICODE)
CONTEXT_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=(?:["“‘]?[A-Z0-9]))')


EU_ALLERGENS = [
    {
        "key": "gluten",
        "label": "Cereals containing gluten",
        "aliases": ["gluten", "wheat", "barley", "rye", "oats", "spelt", "semolina", "breadcrumbs", "pasta", "bread", "flour"],
    },
    {
        "key": "crustaceans",
        "label": "Crustaceans",
        "aliases": ["crustacean", "crustaceans", "prawn", "prawns", "shrimp", "crab", "lobster", "langoustine", "scampi", "crayfish"],
    },
    {
        "key": "eggs",
        "label": "Eggs",
        "aliases": ["egg", "eggs", "mayonnaise", "mayo"],
    },
    {
        "key": "fish",
        "label": "Fish",
        "aliases": ["fish", "anchovy", "anchovies", "salmon", "tuna", "cod", "haddock", "sardine", "mackerel"],
    },
    {
        "key": "peanuts",
        "label": "Peanuts",
        "aliases": ["peanut", "peanuts"],
    },
    {
        "key": "soybeans",
        "label": "Soybeans",
        "aliases": ["soy", "soya", "soybean", "soybeans", "tofu", "miso", "tempeh", "edamame"],
    },
    {
        "key": "milk",
        "label": "Milk",
        "aliases": ["milk", "butter", "cream", "cheese", "yogurt", "yoghurt", "whey", "buttermilk"],
    },
    {
        "key": "tree_nuts",
        "label": "Tree nuts",
        "aliases": ["almond", "almonds", "hazelnut", "hazelnuts", "walnut", "walnuts", "cashew", "cashews", "pecan", "pecans", "pistachio", "pistachios", "macadamia", "brazil nut", "brazil nuts"],
    },
    {
        "key": "celery",
        "label": "Celery",
        "aliases": ["celery", "celeriac"],
    },
    {
        "key": "mustard",
        "label": "Mustard",
        "aliases": ["mustard", "mustards"],
    },
    {
        "key": "sesame",
        "label": "Sesame",
        "aliases": ["sesame", "tahini"],
    },
    {
        "key": "sulphites",
        "label": "Sulphur dioxide / sulphites",
        "aliases": ["sulphite", "sulphites", "sulfite", "sulfites", "sulphur dioxide", "sulfur dioxide"],
    },
    {
        "key": "lupin",
        "label": "Lupin",
        "aliases": ["lupin", "lupine"],
    },
    {
        "key": "molluscs",
        "label": "Molluscs",
        "aliases": ["mollusc", "molluscs", "mussel", "mussels", "oyster", "oysters", "clam", "clams", "scallop", "scallops", "squid", "octopus", "cuttlefish", "snail", "whelk"],
    },
]


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


def _build_allergen_items(ingredients_text: str, allergens_text: str) -> list[dict]:
    detection_source = " ".join(part for part in [ingredients_text, allergens_text] if part)
    normalized_source = f" {re.sub(r'\s+', ' ', detection_source).lower()} "
    items = []

    for allergen in EU_ALLERGENS:
        is_present = any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", normalized_source)
            for alias in allergen["aliases"]
        )
        items.append(
            {
                "key": allergen["key"],
                "label": allergen["label"],
                "is_present": is_present,
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
    latest_recipes = (
        Recipe.objects.select_related("author")
        .order_by("-created_at")[:6]
    )

    latest_articles = (
        Article.objects.select_related("author", "related_recipe")
        .order_by("-published")[:6]
    )

    context = {
        "latest_recipes": latest_recipes,
        "latest_articles": latest_articles,
    }
    return render(request, "home.html", context)


def recipe_list(request):
    recipes = (
        Recipe.objects.select_related("author")
        .order_by("-created_at")
    )

    context = {
        "recipes": recipes,
        "categories": Recipe.get_category_navigation(),
        "page_title": "Recipes | CulinEire",
        "meta_description": (
            "Browse Irish-inspired recipes, vintage cookbook dishes, and modern home "
            "cooking ideas on CulinEire."
        ),
        "page_heading": "Explore the recipe collection",
        "page_subtitle": (
            "Explore Irish classics, vintage recipes, and modern twists, all adapted "
            "for the home kitchen."
        ),
        "selected_category_label": "",
    }
    return render(request, "recipes/recipe_list.html", context)


def category_detail(request, category_slug):
    category_value = Recipe.get_category_value_from_slug(category_slug)
    if not category_value:
        raise Http404("Category not found.")

    category_label = Recipe.get_category_label(category_value)

    recipes = (
        Recipe.objects.select_related("author")
        .filter(category=category_value)
        .order_by("-created_at")
    )

    context = {
        "recipes": recipes,
        "categories": Recipe.get_category_navigation(selected_value=category_value),
        "page_title": f"{category_label} | Recipes | CulinEire",
        "meta_description": (
            f"Browse {category_label.lower()} on CulinEire and discover recipes, ideas, "
            f"and kitchen inspiration."
        ),
        "page_heading": "Explore the recipe collection",
        "page_subtitle": (
            "Explore Irish classics, vintage recipes, and modern twists, all adapted "
            "for the home kitchen."
        ),
        "selected_category_label": category_label,
    }
    return render(request, "recipes/recipe_list.html", context)


def recipe_detail(request, slug):
    recipe = get_object_or_404(
        Recipe.objects.select_related("author").prefetch_related(
            Prefetch(
                "gallery_images",
                queryset=RecipeImage.objects.filter(is_active=True).order_by("sort_order", "id"),
            ),
            Prefetch(
                "comments",
                queryset=RecipeComment.objects.filter(is_approved=True).order_by("-created_at"),
                to_attr="approved_comments_prefetched",
            ),
        ),
        slug=slug,
    )

    gallery_items = []
    active_gallery_items = list(recipe.gallery_images.all())

    if active_gallery_items:
        for item in active_gallery_items:
            image_file = getattr(item, "image", None)
            video_file = getattr(item, "video", None)
            caption = getattr(item, "caption", "") or ""
            alt_text = getattr(item, "alt_text", "") or recipe.title
            poster_file = getattr(item, "poster", None)

            if video_file:
                gallery_items.append(
                    {
                        "media_type": "video",
                        "src": video_file.url,
                        "alt": alt_text,
                        "caption": caption,
                        "poster": poster_file.url if poster_file else "",
                    }
                )
            elif image_file:
                gallery_items.append(
                    {
                        "media_type": "image",
                        "src": image_file.url,
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

    ingredient_items = _build_ingredient_items(recipe.ingredients)
    allergen_items = build_present_allergen_items(recipe.allergens)
    method_steps = _build_method_steps(recipe.method)
    irish_context_paragraphs = _build_context_paragraphs(recipe.irish_context)
    tips_paragraphs = _build_context_paragraphs(recipe.tips)
    author_commentary_paragraphs = _build_context_paragraphs(recipe.author_commentary)
    approved_comments = getattr(recipe, "approved_comments_prefetched", [])
    rating_summary = recipe.ratings.aggregate(
        average=Avg("value"),
        count=Count("id"),
    )
    average_rating_value = float(rating_summary["average"] or 0)
    ratings_count = rating_summary["count"] or 0
    average_rating_percentage = min(max((average_rating_value / 5) * 100, 0), 100)

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
    }
    return render(request, "recipes/recipe_detail.html", context)


@require_POST
def submit_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    form = RecipeRatingForm(request.POST)

    session_key = f"recipe_rating_submitted_{recipe.pk}"

    if request.session.get(session_key):
        messages.warning(request, "You have already rated this recipe from this browser session.")
        return redirect(f"{recipe.get_absolute_url()}#rating")

    if not form.is_valid():
        messages.error(request, "Please submit a valid rating between 1 and 5.")
        return redirect(f"{recipe.get_absolute_url()}#rating")

    RecipeRating.objects.create(
        recipe=recipe,
        value=form.cleaned_data["value"],
    )

    request.session[session_key] = True
    request.session.modified = True

    messages.success(request, "Thank you. Your rating has been saved.")
    return redirect(f"{recipe.get_absolute_url()}#rating")


@require_POST
def submit_recipe_comment(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    form = RecipeCommentForm(request.POST)

    last_comment_payload_key = f"recipe_comment_payload_{recipe.pk}"

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

    RecipeComment.objects.create(
        recipe=recipe,
        name=name,
        content=content,
        is_approved=True,
    )

    request.session[last_comment_payload_key] = normalized_payload
    request.session.modified = True

    messages.success(request, "Thank you. Your comment has been submitted.")
    return redirect(f"{recipe.get_absolute_url()}#comments")


def author_detail(request, slug):
    author = get_object_or_404(RecipeAuthor, slug=slug)

    recipes = (
        Recipe.objects.select_related("author")
        .filter(author=author)
        .order_by("-created_at")
    )

    related_articles = (
        Article.objects.select_related("author", "related_recipe")
        .filter(author=author)
        .order_by("-published")
    )

    is_god_author = author.slug == "greenbear"

    context = {
        "author": author,
        "recipes": recipes,
        "related_articles": related_articles,
        "is_god_author": is_god_author,
    }
    return render(request, "recipes/author_detail.html", context)


class SignUpView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("login")
