from django.urls import path

from ledo import views

app_name = "ledo"

urlpatterns = [
    path("", views.home, name="home"),
]
