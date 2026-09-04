from django.urls import path

from ledo import views

app_name = "ledo"

urlpatterns = [
    path("", views.home, name="home"),
    path("bestill/", views.booking_create, name="booking_create"),
    path("bestill/<uuid:public_id>/takk/", views.booking_confirmation, name="booking_confirmation"),
    path("health/", views.health, name="health"),
]
