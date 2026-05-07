from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("send/", views.send_message, name="send_message"),
    path("<int:pk>/", views.message_detail, name="message_detail"),
    path("<int:pk>/reply/", views.reply_message, name="reply_message"),
]
