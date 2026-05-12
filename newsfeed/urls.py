from django.urls import path

from . import views

app_name = "newsfeed"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("add/", views.add_entry, name="add_entry"),
]
