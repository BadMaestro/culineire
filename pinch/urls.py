from django.urls import path

from . import views

app_name = "pinch"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("create/", views.PinchCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/edit/", views.PinchUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.PinchDeleteView.as_view(), name="delete"),
    path("<slug:slug>/moderate/", views.moderate, name="moderate"),
    path("<slug:slug>/like/", views.toggle_like, name="toggle_like"),
    path("<slug:slug>/save/", views.toggle_save, name="toggle_save"),
    path("<slug:slug>/comments/", views.comments_panel, name="comments_panel"),
    path("<slug:slug>/comment/", views.submit_comment, name="submit_comment"),
    path("<slug:slug>/comment/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
    path("generate/from-recipe/<slug:slug>/", views.generate_from_recipe, name="generate_from_recipe"),
    path("generate/from-article/<slug:slug>/", views.generate_from_article, name="generate_from_article"),
]
