from django.urls import path

from . import views

app_name = "coworking"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("handoff/", views.handoff, name="handoff"),
    path("add-agent/", views.add_agent, name="add_agent"),
]
