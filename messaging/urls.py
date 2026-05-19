from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("archive/", views.message_archive, name="archive"),
    path("send/", views.send_message, name="send_message"),
    path("contact/", views.contact, name="contact"),
    path("<int:pk>/", views.message_detail, name="message_detail"),
    path("<int:pk>/reply/", views.reply_message, name="reply_message"),
    path("<int:pk>/archive/", views.archive_message, name="archive_message"),
    path("<int:pk>/delete/", views.delete_message, name="delete_message"),
    path("<int:pk>/restore/", views.restore_message, name="restore_message"),
]
