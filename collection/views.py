from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from articles.models import Article
from monitoring.tracker import track_event
from recipes.models import Recipe

from .models import SavedArticle, SavedRecipe


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
    saved_recipes = (
        SavedRecipe.objects.filter(user=request.user)
        .select_related("recipe", "recipe__author")
    )
    saved_articles = (
        SavedArticle.objects.filter(user=request.user)
        .select_related("article", "article__author")
    )
    return render(request, "collection/my_collection.html", {
        "saved_recipes": saved_recipes,
        "saved_articles": saved_articles,
        "active_tab": tab,
    })


@require_POST
@login_required
@ratelimit(key="user", rate="60/h", method="POST", block=False)
def add_recipe(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, status=Recipe.Status.APPROVED)
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
    article = get_object_or_404(Article, slug=slug, status=Article.Status.APPROVED)
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
