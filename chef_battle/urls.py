from django.urls import path

from . import views

app_name = "chef_battle"

urlpatterns = [
    path("", views.battle_home, name="home"),
    path("roadmap/", views.battlefield_progress, name="battlefield_progress"),
    path("rankings/", views.rankings, name="rankings"),
    path("challenges/", views.challenge_list, name="challenge_list"),
    path("challenges/create/", views.challenge_create, name="challenge_create"),
    path("challenges/<int:pk>/respond/", views.challenge_respond, name="challenge_respond"),
    path("battles/<int:pk>/", views.battle_detail, name="battle_detail"),
    path("battles/<int:pk>/submit/", views.battle_entry_submit, name="battle_entry_submit"),
    path("battles/<int:pk>/vote/", views.battle_vote, name="battle_vote"),
    path("my-moves/", views.my_moves, name="my_moves"),
    path("poll/", views.notifications_poll, name="notifications_poll"),
    path("battles/<int:pk>/combat/", views.battle_combat_action, name="battle_combat_action"),
    path("battles/<int:pk>/state/", views.battle_state_poll, name="battle_state_poll"),
]
