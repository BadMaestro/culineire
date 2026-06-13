from django.urls import path

from . import views

app_name = "chef_battle"

urlpatterns = [
    path("", views.battle_home, name="home"),
    path("rules/", views.battle_rules, name="rules"),
    path("tokens/", views.token_shop, name="token_shop"),
    path("season/", views.season_leaderboard, name="season_leaderboard"),
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
    path("battles/<int:pk>/biathlon/", views.biathlon, name="biathlon"),
    path("battles/<int:pk>/biathlon/lock/", views.biathlon_lock, name="biathlon_lock"),
    path("battles/<int:pk>/biathlon/shoot/", views.biathlon_shoot, name="biathlon_shoot"),
    path("moderation/cooking/", views.cooking_moderation, name="cooking_moderation"),
    path("battles/<int:pk>/moderation/cooking/approve/", views.cooking_moderation_approve, name="cooking_moderation_approve"),
    path("battles/<int:pk>/cooking/submit/", views.cooking_submit, name="cooking_submit"),
    path("hall-of-fame/", views.hall_of_fame, name="hall_of_fame"),
    path("battles/<int:pk>/chat/send/", views.battle_chat_send, name="battle_chat_send"),
    path("battles/<int:pk>/chat/poll/", views.battle_chat_poll, name="battle_chat_poll"),
    path("profile/<slug:slug>/", views.chef_battle_profile, name="chef_profile"),
    path("battles/<int:pk>/gift/appreciation/", views.send_appreciation_gift_view, name="send_appreciation_gift"),
]
