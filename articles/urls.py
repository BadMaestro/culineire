from django.urls import path
from .views import (
    ArticleCreateView,
    ArticleDeleteView,
    ArticleDetailView,
    ArticleListView,
    ArticleUpdateView,
    moderate_article,
)

app_name = 'articles'

urlpatterns = [
    path('', ArticleListView.as_view(), name='article_list'),
    path('create/', ArticleCreateView.as_view(), name='article_create'),
    path('moderation/<slug:slug>/', moderate_article, name='moderate_article'),
    path('<slug:slug>/edit/', ArticleUpdateView.as_view(), name='article_edit'),
    path('<slug:slug>/delete/', ArticleDeleteView.as_view(), name='article_delete'),
    path('<slug:slug>/', ArticleDetailView.as_view(), name='article_detail'),
]
