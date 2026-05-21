from django.urls import path
from .views import (
    ArticleCreateView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleListView,
    ArticleUpdateView,
    delete_article_gallery_image,
    moderate_article,
)

app_name = 'articles'

urlpatterns = [
    path('', ArticleListView.as_view(), name='article_list'),
    path('create/', ArticleCreateView.as_view(), name='article_create'),
    path('moderation/<slug:slug>/', moderate_article, name='moderate_article'),
    path('gallery/<int:image_id>/delete/', delete_article_gallery_image, name='delete_gallery_image'),
    path('<slug:slug>/edit/', ArticleUpdateView.as_view(), name='article_edit'),
    path('<slug:slug>/delete/', ArticleDeleteView.as_view(), name='article_delete'),
    path('<slug:slug>/', ArticleDetailView.as_view(), name='article_detail'),
]
