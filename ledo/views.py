from .i18n import translate_lazy as _
from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.utils import translation
from django.urls import reverse
from .i18n import LANGUAGES, translate

from .forms import BookingRequestForm
from .models import Booking
from .services import create_booking_request, current_fares


def ledo_access(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not settings.LEDO_ENABLED:
            raise Http404
        if settings.LEDO_PREVIEW_STAFF_ONLY and not (
            request.user.is_authenticated and request.user.is_staff
        ):
            raise Http404
        codes = {code for code, _, _ in LANGUAGES}
        language = request.GET.get('lang', request.COOKIES.get('ledo_language', 'nb'))
        if language not in codes:
            language = 'nb'
        request.ledo_language = language
        with translation.override(language):
            response = view_func(request, *args, **kwargs)
        response['Content-Language'] = language
        response['Cache-Control'] = 'private, no-store'
        if request.GET.get('lang') in codes:
            response.set_cookie('ledo_language', language, max_age=31536000,
                                path='/ledo/', secure=request.is_secure(),
                                httponly=True, samesite='Lax')
        return response

    return wrapped


def _render(request, template, context, **kwargs):
    language = request.ledo_language
    path = request.path if request.method == 'GET' else reverse('ledo:home')
    context.update({
        'ledo_language': language,
        'ledo_languages': [dict(code=code, label=label, name=name,
                                url=f'{path}?lang={code}') for code, label, name in LANGUAGES],
        'ledo_js_messages': {key: translate(key) for key in (
            'Velg en rute', 'Pris ikke tilgjengelig', 'Mva. inkludert')},
    })
    return render(request, template, context, **kwargs)


def _active_fares():
    fares = []
    seen_routes = set()
    for fare in current_fares():
        if fare.route_id not in seen_routes:
            fares.append(fare)
            seen_routes.add(fare.route_id)
    return fares


def _landing_context(form=None):
    fares = _active_fares()
    price_map = {
        str(fare.route_id): {
            "oneWay": str(fare.one_way_price),
            "return": str(fare.return_price) if fare.return_price is not None else None,
            "currency": fare.currency,
            "vatIncluded": fare.vat_included,
        }
        for fare in fares
    }
    return {
        "form": form or BookingRequestForm(),
        "fares": fares,
        "price_map": price_map,
        "booking_available": bool(fares),
    }


@require_GET
@ledo_access
def home(request):
    return _render(request, "ledo/home.html", _landing_context())


@require_POST
@ledo_access
def booking_create(request):
    if not request.session.session_key:
        request.session.create()
    rate_key = f"ledo:booking-rate:{request.session.session_key}"
    attempts = cache.get(rate_key, 0)
    if attempts >= 5:
        form = BookingRequestForm(request.POST)
        form.add_error(None, _("For mange forsøk. Vent litt før du prøver igjen."))
        return _render(request, "ledo/home.html", _landing_context(form), status=429)
    cache.set(rate_key, attempts + 1, timeout=15 * 60)

    form = BookingRequestForm(request.POST)
    if not form.is_valid():
        return _render(request, "ledo/home.html", _landing_context(form), status=400)

    booking, created = create_booking_request(form.cleaned_data)
    visible_bookings = request.session.setdefault("ledo_booking_ids", [])
    booking_id = str(booking.public_id)
    if booking_id not in visible_bookings:
        visible_bookings.append(booking_id)
        request.session.modified = True
    return redirect("ledo:booking_confirmation", public_id=booking.public_id)


@require_GET
@ledo_access
def booking_confirmation(request, public_id):
    allowed = str(public_id) in request.session.get("ledo_booking_ids", [])
    if not allowed and not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    booking = get_object_or_404(
        Booking.objects.select_related("route"),
        public_id=public_id,
    )
    pickup_at_oslo = booking.pickup_at.astimezone(ZoneInfo("Europe/Oslo"))
    return _render(
        request,
        "ledo/confirmation.html",
        {"booking": booking, "pickup_at_oslo": pickup_at_oslo},
    )


@require_GET
def health(request):
    if not settings.LEDO_ENABLED:
        raise Http404
    return JsonResponse({"application": "LEDO", "status": "ok"})
