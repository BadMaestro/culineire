from django.urls import path

from .views import RecipeListView, RecipeDetailView, AuthorDetailView

app_name = "recipes"

urlpatterns = [
    path("", RecipeListView.as_view(), name="recipe_list"),
    path("authors/<slug:slug>/", AuthorDetailView.as_view(), name="author_detail"),
    path("<slug:slug>/", RecipeDetailView.as_view(), name="recipe_detail"),
]
