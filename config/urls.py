from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from recipes import views as recipes_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", recipes_views.home, name="home"),

    # список и детали рецептов живут в приложении recipes
    path("recipes/", include("recipes.urls", namespace="recipes")),

    # регистрация (Sign in)
    path("accounts/signup/", recipes_views.SignUpView.as_view(), name="signup"),

    # стандартные auth-урлы: login, logout и т.д.
    path("accounts/", include("django.contrib.auth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
