from django.urls import path

from . import views

app_name = "collection"

urlpatterns = [
    path("", views.my_collection, name="my_collection"),
    path("recipes/add/<slug:slug>/", views.add_recipe, name="add_recipe"),
    path("recipes/remove/<slug:slug>/", views.remove_recipe, name="remove_recipe"),
    path("articles/add/<slug:slug>/", views.add_article, name="add_article"),
    path("articles/remove/<slug:slug>/", views.remove_article, name="remove_article"),
    path("authors/follow/<slug:slug>/", views.toggle_follow, name="toggle_follow"),
]
