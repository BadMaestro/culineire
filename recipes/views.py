from __future__ import annotations

from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy

from .models import Recipe, RecipeAuthor


def home(request):
  """
  Главная страница.
  Показываем несколько последних рецептов.
  """
  latest_recipes = Recipe.objects.order_by("-created_at")[:3]
  context = {
      "latest_recipes": latest_recipes,
  }
  return render(request, "home.html", context)


class RecipeListView(ListView):
  """
  Страница со списком рецептов: /recipes/
  """
  model = Recipe
  template_name = "recipes/recipe_list.html"
  context_object_name = "recipes"
  paginate_by = 12  # на будущее


class RecipeDetailView(DetailView):
  """
  Страница одного рецепта: /recipes/<slug>/
  """
  model = Recipe
  template_name = "recipes/recipe_detail.html"
  context_object_name = "recipe"
  slug_field = "slug"
  slug_url_kwarg = "slug"


class AuthorDetailView(DetailView):
  """
  Страница автора: /recipes/authors/<slug>/
  """
  model = RecipeAuthor
  template_name = "recipes/author_detail.html"
  context_object_name = "author"
  slug_field = "slug"
  slug_url_kwarg = "slug"


class SignUpView(CreateView):
  """
  Страница регистрации (Sign in / Sign up):
  /accounts/signup/
  """
  form_class = UserCreationForm
  template_name = "registration/signup.html"
  success_url = reverse_lazy("login")
