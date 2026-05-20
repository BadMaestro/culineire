from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.templatetags.static import static
from django.urls import include, path, re_path
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve

from accounts import views as accounts_views
from config import views as config_views
from recipes import views as recipes_views

urlpatterns = [
    path("cave19850324/", admin.site.urls),

    # Home page
    path("", recipes_views.home, name="home"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("privacy/", TemplateView.as_view(template_name="privacy.html"), name="privacy"),
    path("robots.txt", config_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", config_views.sitemap_xml, name="sitemap_xml"),
    path("maintenance/notes/", config_views.maintenance_note_create, name="maintenance_note_create"),
    path("favicon.ico", RedirectView.as_view(url=static("images/favicon.ico"), permanent=True), name="favicon"),
    path("favicon.png", RedirectView.as_view(url=static("images/favicon.png"), permanent=True), name="favicon_png"),
    path(
        "apple-touch-icon.png",
        RedirectView.as_view(url=static("images/apple-touch-icon.png"), permanent=True),
        name="apple_touch_icon",
    ),

    # Recipes
    path("recipes/", include("recipes.urls", namespace="recipes")),

    # Articles
    path("articles/", include("articles.urls", namespace="articles")),

    # Messaging
    path("messages/", include("messaging.urls", namespace="messaging")),

    # Presence notifications
    path("presence/", include("presence.urls", namespace="presence")),

    # Collection
    path("collection/", include("collection.urls", namespace="collection")),

    # Legal
    path("legal/", include("legal.urls", namespace="legal")),

    # News feed
    path("news/", include("newsfeed.urls", namespace="newsfeed")),

    # Monitoring dashboard
    path("monitoring/", include("monitoring.urls", namespace="monitoring")),

    # Accounts (user management)
    path("accounts/", include("accounts.urls", namespace="accounts")),

    # Authentication
    path("accounts/login/", accounts_views.CulinEireLoginView.as_view(), name="login"),
    path("accounts/ajax-login/", accounts_views.ajax_login, name="ajax_login"),
    path("accounts/signup/", accounts_views.SignUpView.as_view(), name="signup"),
    path("accounts/activate/<uidb64>/<token>/", accounts_views.activate_account, name="activate_account"),
    path("accounts/", include("django.contrib.auth.urls")),
]

if not settings.IS_PRODUCTION:
    from django.contrib import messages as _messages
    from django.shortcuts import redirect as _redirect
    from django.shortcuts import render as _render

    def _preview_activation(request):
        return _render(request, "registration/activation_pending.html", {"email": "preview@example.com"})

    def _preview_activation_invalid(request):
        return _render(request, "registration/activation_invalid.html")

    def _preview_toasts(request):
        _messages.success(request, "Your email is confirmed. Welcome to CulinEire!")
        _messages.warning(request, "Your session will expire soon.")
        _messages.error(request, "Something went wrong. Please try again.")
        return _redirect("home")

    urlpatterns += [
        path("dev/preview/activation-pending/", _preview_activation),
        path("dev/preview/activation-invalid/", _preview_activation_invalid),
        path("dev/preview/toasts/", _preview_toasts),
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
