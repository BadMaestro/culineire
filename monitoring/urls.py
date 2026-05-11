from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("traffic/", views.traffic_detail, name="traffic_detail"),
    path("activity/", views.activity_detail, name="activity_detail"),
    path("security/", views.security_detail, name="security_detail"),
]
