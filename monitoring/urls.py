from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("traffic/", views.traffic_detail, name="traffic_detail"),
    path("activity/", views.activity_detail, name="activity_detail"),
    path("security/", views.security_detail, name="security_detail"),
    path("export/", views.export_detail, name="export_detail"),
    path("clear/", views.clear_stats, name="clear_stats"),
    path("profanity/", views.profanity_list, name="profanity_list"),
    path("profanity/words.json", views.profanity_words_api, name="profanity_words_api"),
]
