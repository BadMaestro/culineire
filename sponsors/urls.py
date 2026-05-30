from django.urls import path

from . import views

app_name = "sponsors"

urlpatterns = [
    path("", views.puzzle_page, name="puzzle"),
]
