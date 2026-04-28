from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
