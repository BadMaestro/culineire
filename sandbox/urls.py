from django.urls import path

from . import views

app_name = "sandbox"

urlpatterns = [
    path("", views.index, name="index"),
    path("recipe-form/", views.recipe_form, name="recipe_form"),
]
