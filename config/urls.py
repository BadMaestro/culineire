from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path
from django.views.static import serve

from recipes import views as recipes_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Home page
    path("", recipes_views.home, name="home"),

    # Recipes
    path("recipes/", include("recipes.urls", namespace="recipes")),

    # Articles
    path("articles/", include("articles.urls", namespace="articles")),

    # Authentication
    path("accounts/login/", recipes_views.CulinEireLoginView.as_view(), name="login"),
    path("accounts/signup/", recipes_views.SignUpView.as_view(), name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
]

if settings.SERVE_STATIC_LOCALLY:
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            staticfiles_serve,
            {"insecure": True},
        ),
    ]

if settings.SERVE_MEDIA_LOCALLY:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
