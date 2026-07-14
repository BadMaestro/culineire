from django.urls import path

from . import views

app_name = "coworking"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("handoff/", views.handoff, name="handoff"),
    path("send-message/", views.send_message, name="send_message"),
    path("add-agent/", views.add_agent, name="add_agent"),
]
