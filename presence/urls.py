from django.urls import path

from . import views

app_name = "presence"

urlpatterns = [
    path("events/", views.presence_events, name="events"),
]
