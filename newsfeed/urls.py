from django.urls import path

from . import views

app_name = "newsfeed"

urlpatterns = [
    path("", views.feed, name="feed"),
]
