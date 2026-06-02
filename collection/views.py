from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from articles.models import Article, ArticleImage
from amuse_bouche.models import AmuseBouche
from amuse_bouche.visibility import can_view_amuse_bouche_public_area
from monitoring.tracker import track_event
from recipes.models import Recipe, RecipeAuthor

from .models import AuthorFollow, SavedArticle, SavedContent, SavedRecipe


def _safe_next(request, fallback):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


@login_required
def my_collection(request):
    tab = request.GET.get("tab", "recipes")
    show_amuse_bouche = can_view_amuse_bouche_public_area(request.user)
    if tab == "amuse-bouche" and not show_amuse_bouche:
        tab = "recipes"
    article_card_gallery_prefetch = Prefetch(
        "article__gallery_images",
        queryset=ArticleImage.objects.filter(is_active=True).order_by("sort_order", "id"),
        to_attr="active_card_gallery_images",
    )
    saved_recipes = (
        SavedRecipe.objects.filter(user=request.user)
        .filter(recipe__status=Recipe.Status.APPROVED, recipe__is_deleted=False)
        .select_related("recipe", "recipe__author")
    )
    saved_articles = (
        SavedArticle.objects.filter(user=request.user)
        .filter(article__status=Article.Status.APPROVED, article__is_deleted=False)
        .select_related("article", "article__author")
        .prefetch_related(article_card_gallery_prefetch)
    )
    amuse_bouche_type = ContentType.objects.get_for_model(AmuseBouche)
    saved_amuse_bouche = []
    if show_amuse_bouche:
        saved_amuse_bouche = [
            saved for saved in SavedContent.objects.filter(user=request.user, content_type=amuse_bouche_type)
            .select_related("content_type")
            if getattr(saved.content_object, "status", None) == AmuseBouche.Status.APPROVED
        ]
    return render(request, "collection/my_collection.html", {
        "saved_recipes": saved_recipes,
        "saved_articles": saved_articles,
        "saved_amuse_bouche": saved_amuse_bouche,
        "active_tab": tab,
        "show_amuse_bouche": show_amuse_bouche,
    })


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def add_recipe(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, status=Recipe.Status.APPROVED, is_deleted=False)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
    else:
        SavedRecipe.objects.get_or_create(user=request.user, recipe=recipe)
        track_event(request, "collection_add", object_type="recipe", object_id=recipe.pk, object_title=recipe.title)
        messages.success(request, "Added to your collection.")
    return _safe_next(request, recipe.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def remove_recipe(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
    else:
        SavedRecipe.objects.filter(user=request.user, recipe=recipe).delete()
        track_event(request, "collection_remove", object_type="recipe", object_id=recipe.pk, object_title=recipe.title)
        messages.success(request, "Removed from your collection.")
    return _safe_next(request, recipe.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def add_article(request, slug):
    article = get_object_or_404(Article, slug=slug, status=Article.Status.APPROVED, is_deleted=False)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
    else:
        SavedArticle.objects.get_or_create(user=request.user, article=article)
        track_event(request, "collection_add", object_type="article", object_id=article.pk, object_title=article.title)
        messages.success(request, "Added to your collection.")
    return _safe_next(request, article.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def remove_article(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
    else:
        SavedArticle.objects.filter(user=request.user, article=article).delete()
        track_event(request, "collection_remove", object_type="article", object_id=article.pk, object_title=article.title)
        messages.success(request, "Removed from your collection.")
    return _safe_next(request, article.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def toggle_follow(request, slug):
    """Follow or unfollow a RecipeAuthor. Returns to the next URL or the author page."""
    author = get_object_or_404(RecipeAuthor, slug=slug)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
        return _safe_next(request, author.get_absolute_url())
    follow, created = AuthorFollow.objects.get_or_create(user=request.user, author=author)
    if created:
        track_event(request, "author_follow", object_type="recipe_author", object_id=author.pk, object_title=author.name)
        messages.success(request, f"You are now following {author.name}.")
    else:
        follow.delete()
        track_event(request, "author_unfollow", object_type="recipe_author", object_id=author.pk, object_title=author.name)
        messages.success(request, f"You unfollowed {author.name}.")
    return _safe_next(request, author.get_absolute_url())
