from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("author/<slug:slug>/manage/", views.manage_author, name="manage_author"),
]
