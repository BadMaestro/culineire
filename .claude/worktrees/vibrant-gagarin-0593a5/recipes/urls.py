from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.recipe_list, name="recipe_list"),
    path("create/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("profile/edit/", views.RecipeAuthorUpdateView.as_view(), name="author_edit"),
    path("profile/delete/", views.RecipeAuthorDeleteView.as_view(), name="author_delete"),
    path("category/<slug:category_slug>/", views.category_detail, name="category_detail"),
    path("author/<slug:slug>/", views.author_detail, name="author_detail"),
    path("<slug:slug>/edit/", views.RecipeUpdateView.as_view(), name="recipe_edit"),
    path("<slug:slug>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    path("<slug:slug>/rate/", views.submit_recipe_rating, name="submit_recipe_rating"),
    path("<slug:slug>/comment/", views.submit_recipe_comment, name="submit_recipe_comment"),
    path("<slug:slug>/", views.recipe_detail, name="recipe_detail"),
]
