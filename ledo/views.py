from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import render


def _can_preview_ledo(user):
    return user.is_authenticated and user.is_staff


@user_passes_test(_can_preview_ledo, login_url="login")
def home(request):
    if not settings.LEDO_ENABLED:
        raise Http404

    return render(request, "ledo/home.html")
