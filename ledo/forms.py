from .i18n import translate_lazy as _
import uuid
from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django import forms
from django.utils import timezone

from .models import Route
from .services import QuoteUnavailable, current_fares, quote_for_route


OSLO = ZoneInfo("Europe/Oslo")


def _parse_oslo_datetime(raw_value):
    try:
        naive = datetime.strptime(raw_value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        raise forms.ValidationError(_("Oppgi gyldig dato og tid."))
    first = naive.replace(tzinfo=OSLO, fold=0)
    second = naive.replace(tzinfo=OSLO, fold=1)
    round_trip = first.astimezone(datetime_timezone.utc).astimezone(OSLO).replace(tzinfo=None)
    if round_trip != naive or first.utcoffset() != second.utcoffset():
        raise forms.ValidationError(
            _("Tidspunktet finnes ikke entydig på grunn av overgang til eller fra sommertid."),
        )
    return first


class OsloDateTimeField(forms.DateTimeField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime):
            return value
        return _parse_oslo_datetime(value)


class BookingRequestForm(forms.Form):
    route = forms.ModelChoiceField(
        queryset=Route.objects.none(),
        label=_("Rute"),
        empty_label=_("Velg retning"),
    )
    pickup_at = OsloDateTimeField(
        label=_("Hentedato og tid"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=("%Y-%m-%dT%H:%M",),
    )
    return_trip = forms.BooleanField(label=_("Tur-retur"), required=False)
    return_at = OsloDateTimeField(
        label=_("Returdato og tid"),
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=("%Y-%m-%dT%H:%M",),
    )
    adults = forms.IntegerField(label=_("Voksne"), min_value=1, max_value=6, initial=1)
    children = forms.IntegerField(label=_("Barn"), min_value=0, max_value=6, initial=0)
    luggage = forms.IntegerField(label=_("Bagasje"), min_value=0, max_value=12, initial=1)
    flight_number = forms.CharField(label=_("Flynummer"), max_length=24, required=False)
    notes = forms.CharField(
        label=_("Spesielle behov"),
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    name = forms.CharField(label=_("Navn"), max_length=120)
    email = forms.EmailField(label=_("E-post"))
    phone = forms.CharField(label=_("Telefon"), max_length=32)
    accept_terms = forms.BooleanField(
        label=_("Jeg godtar at dette er en forespørsel som må bekreftes av LEDO Drive."),
    )
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        route_ids = current_fares().values_list("route_id", flat=True)
        self.fields["route"].queryset = Route.objects.filter(active=True, pk__in=route_ids)
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid.uuid4()

    def clean_pickup_at(self):
        pickup_at = _parse_oslo_datetime(self.data.get("pickup_at"))
        if pickup_at <= timezone.now():
            raise forms.ValidationError(_("Velg et tidspunkt i fremtiden."))
        return pickup_at

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise forms.ValidationError(_("Forespørselen kunne ikke sendes."))

        return_trip = cleaned.get("return_trip")
        return_at = cleaned.get("return_at")
        pickup_at = cleaned.get("pickup_at")
        if return_trip and not return_at:
            self.add_error("return_at", _("Oppgi tidspunkt for returen."))
        elif return_at:
            try:
                return_at = _parse_oslo_datetime(self.data.get("return_at"))
            except forms.ValidationError as exc:
                self.add_error("return_at", exc)
                return cleaned
            else:
                cleaned["return_at"] = return_at
            if pickup_at and return_at <= pickup_at:
                self.add_error("return_at", _("Returen må være etter hentetidspunktet."))

        route = cleaned.get("route")
        if route:
            try:
                cleaned["quote"] = quote_for_route(route, return_trip=bool(return_trip))
            except QuoteUnavailable as exc:
                self.add_error("route", str(exc))
        return cleaned
