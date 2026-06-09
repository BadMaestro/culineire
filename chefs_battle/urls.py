from django.urls import path

from chefs_battle import views

app_name = "chefs_battle"

urlpatterns = [
    path("roadmap/", views.roadmap, name="roadmap"),
]
