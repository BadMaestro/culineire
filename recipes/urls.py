from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.recipe_list, name="recipe_list"),
    path("create/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("profile/edit/", views.RecipeAuthorUpdateView.as_view(), name="author_edit"),
    path("profile/delete/", views.RecipeAuthorDeleteView.as_view(), name="author_delete"),
    path("moderation/", views.moderation_panel, name="moderation_panel"),
    path("moderation/automation-progress/", views.automation_progress, name="automation_progress"),
    path("moderation/generate/", views.generate_recipe_view, name="generate_recipe"),
    path("moderation/generate/poll/", views.generate_recipe_poll, name="generate_recipe_poll"),
    path("moderation/recipe/<slug:slug>/", views.moderate_recipe, name="moderate_recipe"),
    path("moderation/author/<slug:slug>/edit/", views.ModeratorAuthorUpdateView.as_view(), name="moderation_author_edit"),
    path("moderation/author/<slug:slug>/delete/", views.ModeratorAuthorDeleteView.as_view(), name="moderation_author_delete"),
    path("category/<slug:category_slug>/", views.category_detail, name="category_detail"),
    path("author/<slug:slug>/", views.author_detail, name="author_detail"),
    path("format/suggest/", views.recipe_format_suggest, name="recipe_format_suggest"),
    path("format/preview/", views.recipe_format_preview, name="recipe_format_preview"),
    path("generate-hero-image/", views.recipe_ai_generate_hero, name="recipe_ai_generate_hero"),
    path("<slug:slug>/edit/", views.RecipeUpdateView.as_view(), name="recipe_edit"),
    path("<slug:slug>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    path("<slug:slug>/rate/", views.submit_recipe_rating, name="submit_recipe_rating"),
    path("<slug:slug>/rate/reset/", views.reset_recipe_rating, name="reset_recipe_rating"),
    path("<slug:slug>/rate/reset-all/", views.reset_all_recipe_ratings, name="reset_all_recipe_ratings"),
    path("<slug:slug>/ratings/", views.recipe_ratings_api, name="recipe_ratings_api"),
    path("<slug:slug>/comment/", views.submit_recipe_comment, name="submit_recipe_comment"),
    path("comment/<int:comment_id>/reply/", views.add_comment_reply, name="add_comment_reply"),
    path("gallery/<int:image_id>/delete/", views.delete_recipe_gallery_image, name="delete_gallery_image"),
    path("<slug:slug>/regenerate-image/", views.recipe_regenerate_image, name="recipe_regenerate_image"),
    path("comment/<int:comment_id>/delete/", views.delete_recipe_comment, name="delete_recipe_comment"),
    path("<slug:slug>/comments/delete-all/", views.delete_all_recipe_comments, name="delete_all_recipe_comments"),
    path("<slug:slug>/", views.recipe_detail, name="recipe_detail"),
]
