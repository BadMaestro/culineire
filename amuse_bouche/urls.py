from django.urls import path

from . import views

app_name = "amuse_bouche"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("new/", views.AmuseBoucheCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/edit/", views.AmuseBoucheUpdateView.as_view(), name="edit"),
    path("<slug:slug>/like/", views.toggle_like, name="toggle_like"),
    path("<slug:slug>/save/", views.toggle_save, name="toggle_save"),
]
