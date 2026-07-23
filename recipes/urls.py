from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.recipe_list, name="recipe_list"),
    path("create/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("create/from-screenshot/", views.recipe_create_from_screenshot, name="recipe_create_from_screenshot"),
    path("create/from-screenshot/confirm/", views.recipe_create_from_screenshot_confirm, name="recipe_create_from_screenshot_confirm"),
    path("dashboard/", views.author_dashboard, name="author_dashboard"),
    path("profile/edit/", views.RecipeAuthorUpdateView.as_view(), name="author_edit"),
    path("profile/delete/", views.RecipeAuthorDeleteView.as_view(), name="author_delete"),
    path("moderation/", views.moderation_panel, name="moderation_panel"),
    path("moderation/automation-progress/", views.automation_progress, name="automation_progress"),
    path(
        "moderation/arena-master-console-plan/",
        views.arena_master_console_plan,
        name="arena_master_console_plan",
    ),
    # Unlisted read-only mirror of the board (owner request, 2026-07-23): anyone
    # holding the direct link may read it. It is linked from nowhere on the site
    # and answers with X-Robots-Tag: noindex, nofollow. The moderator route below
    # keeps the operator controls; this one exposes none of them.
    path("arena-build-plan/", views.arena_build_plan_public, name="arena_build_plan_public"),
    path("moderation/arena-build-plan/", views.arena_build_plan, name="arena_build_plan"),
    path("moderation/arena-build-plan/start/", views.arena_build_start, name="arena_build_start"),
    path("moderation/site-research/", views.site_research_progress, name="site_research_progress"),
    path("moderation/deployment-journal/", views.deployment_journal, name="deployment_journal"),
    path("moderation/generate/", views.generate_recipe_view, name="generate_recipe"),
    path("moderation/generate/poll/", views.generate_recipe_poll, name="generate_recipe_poll"),
    path("moderation/recipe/<slug:slug>/", views.moderate_recipe, name="moderate_recipe"),
    path("moderation/clan/<slug:slug>/", views.moderate_clan, name="moderate_clan"),
    path("moderation/author/<slug:slug>/edit/", views.ModeratorAuthorUpdateView.as_view(), name="moderation_author_edit"),
    path("moderation/author/<slug:slug>/set-password/", views.moderation_author_set_password, name="moderation_author_set_password"),
    path("moderation/author/<slug:slug>/delete/", views.ModeratorAuthorDeleteView.as_view(), name="moderation_author_delete"),
    path("category/<slug:category_slug>/", views.category_detail, name="category_detail"),
    path("author/<slug:slug>/", views.author_detail, name="author_detail"),
    path("studio/create/", views.recipe_studio_view, name="recipe_studio"),
    path("studio/ai-fill/", views.recipe_studio_ai_fill, name="recipe_studio_ai_fill"),
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
    path("<slug:slug>/regenerate-text/", views.recipe_regenerate_text, name="recipe_regenerate_text"),
    path("comment/<int:comment_id>/delete/", views.delete_recipe_comment, name="delete_recipe_comment"),
    path("<slug:slug>/comments/delete-all/", views.delete_all_recipe_comments, name="delete_all_recipe_comments"),
    path("<slug:slug>/", views.recipe_detail, name="recipe_detail"),
]
