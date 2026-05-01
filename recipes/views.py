import re

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db.models import Avg, Count, Prefetch
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView
from django_ratelimit.decorators import ratelimit

from articles.models import Article
from .allergens import build_present_allergen_items
from .authoring import AuthorRequiredMixin, user_can_manage_author
from .forms import (
    RecipeAuthoringForm,
    RecipeAuthorProfileForm,
    RecipeCommentForm,
    RecipeRatingForm,
    SignInForm,
    SignUpForm,
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
    "breakfast_and_brunch": "images/categories/breakfast-and-brunch",
    "lunch": "images/categories/lunch.png",
    "dinner": "images/categories/dinner.png",
    "grilling_and_barbecue": "images/categories/grilling-and-barbecue.png",
    "soups_and_stews": "images/categories/soups-and-stews.png",
    "salads": "images/categories/salads.png",
    "seasonal_and_festive_irish": "images/categories/seasonal-and-festive",
    "healthy_eating": "images/categories/healthy-eating.png",
    "pasta_and_noodles": "images/categories/pasta-and-noodles.png",
}


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
    author_slug = (request.GET.get("author") or "").strip()
    recipes = (
        Recipe.objects.select_related("author")
        .prefetch_related("additional_category_links")
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
            f"{selected_author.name}'s recipes"
            if selected_author
            else "Explore The Recipe Collection"
        ),
        "page_subtitle": (
            f"A curated view of recipes created by {selected_author.name}."
            if selected_author
            else (
                "Irish classics, treasured vintage recipes, and modern home-kitchen twists, "
                "bringing familiar flavours back to the table and opening Ireland's culinary "
                "heritage to food lovers."
            )
        ),
        "selected_category_label": "",
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
        "page_heading": "Explore The Recipe Collection",
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
            "additional_category_links",
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
        "can_manage_recipe": user_can_manage_author(request.user, recipe.author),
    }
    return render(request, "recipes/recipe_detail.html", context)


@require_POST
@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def submit_recipe_rating(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    form = RecipeRatingForm(request.POST)

    session_key = f"recipe_rating_submitted_{recipe.pk}"

    if getattr(request, "limited", False):
        messages.error(request, "You have submitted too many ratings. Please try again later.")
        return redirect(f"{recipe.get_absolute_url()}#rating")

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
@ratelimit(key="ip", rate="5/h", method="POST", block=False)
def submit_recipe_comment(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    form = RecipeCommentForm(request.POST)

    last_comment_payload_key = f"recipe_comment_payload_{recipe.pk}"

    if getattr(request, "limited", False):
        messages.error(request, "You have submitted too many comments. Please try again later.")
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

    RecipeComment.objects.create(
        recipe=recipe,
        name=name,
        content=content,
        is_approved=False,
    )

    request.session[last_comment_payload_key] = normalized_payload
    request.session.modified = True

    messages.success(request, "Your comment has been submitted and is awaiting moderation.")
    return redirect(f"{recipe.get_absolute_url()}#comments")


def author_detail(request, slug):
    author = get_object_or_404(RecipeAuthor, slug=slug)

    recipe_count = Recipe.objects.filter(author=author).count()
    article_count = Article.objects.filter(author=author).count()

    context = {
        "author": author,
        "recipe_count": recipe_count,
        "article_count": article_count,
        "is_god_author": author.slug == "greenbear",
        "can_manage_author_profile": user_can_manage_author(request.user, author),
        "profile_delete_will_remove_articles": article_count > 0,
        "profile_delete_will_orphan_recipes": recipe_count > 0,
    }
    return render(request, "recipes/author_detail.html", context)


class RecipeCreateView(AuthorRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeAuthoringForm
    template_name = "authoring/recipe_form.html"

    def form_valid(self, form):
        recipe = form.save(commit=False)
        recipe.author = self.author
        recipe.save()
        form.save_additional_categories(recipe)

        self.object = recipe
        messages.success(self.request, "Recipe Created Successfully.")
        return redirect(recipe.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        return context


class RecipeUpdateView(AuthorRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeAuthoringForm
    template_name = "authoring/recipe_form.html"
    context_object_name = "recipe"

    def get_queryset(self):
        return Recipe.objects.filter(author=self.author)

    def form_valid(self, form):
        response = super().form_valid(form)
        form.save_additional_categories(self.object)
        messages.success(self.request, "Recipe Updated Successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Recipe"
        context["form_intro"] = (
            "Refine your recipe, update categories and keep the CulinEire collection current."
        )
        context["submit_label"] = "Save Changes"
        return context


class RecipeDeleteView(AuthorRequiredMixin, DeleteView):
    model = Recipe
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
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
        return context


class RecipeAuthorDeleteView(AuthorRequiredMixin, DeleteView):
    model = RecipeAuthor
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("home")

    def get_object(self, queryset=None):
        return self.author

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        Article.objects.filter(author=self.object).delete()
        try:
            response = super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                "Profile deletion was blocked because related content is still protected.",
            )
            return redirect(self.object.get_absolute_url())

        messages.success(
            request,
            "Profile Deleted. Your articles were removed and recipe author links were cleared.",
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        related_recipe_count = Recipe.objects.filter(author=self.author).count()
        related_article_count = Article.objects.filter(author=self.author).count()
        context["author"] = self.author
        context["delete_title"] = "Delete Profile"
        context["delete_intro"] = (
            "Deleting your profile will remove your author page, delete your articles and "
            "remove your author link from existing recipes."
        )
        context["delete_label"] = "Delete Profile"
        context["cancel_url"] = self.author.get_absolute_url()
        context["delete_warnings"] = [
            f"{related_article_count} article(s) will be deleted." if related_article_count else "",
            f"{related_recipe_count} recipe(s) will stay on the site but lose the author link."
            if related_recipe_count
            else "",
        ]
        return context


class CulinEireLoginView(LoginView):
    authentication_form = SignInForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    @method_decorator(sensitive_post_parameters("password"))
    @method_decorator(ratelimit(key="ip", rate="5/10m", method="POST", block=False))
    @method_decorator(ratelimit(key="post:username", rate="5/10m", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            messages.error(request, "Too many sign-in attempts. Please wait a few minutes and try again.")
            return redirect("login")
        return super().post(request, *args, **kwargs)


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("home")

    @method_decorator(sensitive_post_parameters("password1", "password2"))
    @method_decorator(ratelimit(key="ip", rate="3/h", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            messages.error(request, "Too many account creation attempts. Please try again later.")
            return redirect("signup")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Welcome to CulinEire. Your account is ready.")
        return response
