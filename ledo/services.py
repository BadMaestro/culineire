from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import AuditEvent, Booking, CustomerContact, Fare, Route


TERMS_VERSION = "preview-2026-09-04"
OSLO = ZoneInfo("Europe/Oslo")


class QuoteUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    fare: Fare
    amount: Decimal
    currency: str
    return_trip: bool


def current_fares():
    today = datetime.now(OSLO).date()
    return Fare.objects.filter(
        active=True,
        route__active=True,
        valid_from__lte=today,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=today),
    ).select_related("route").order_by("route_id", "-valid_from", "-pk")


def quote_for_route(route: Route, *, return_trip: bool) -> Quote:
    fare = current_fares().filter(route=route).first()
    if fare is None:
        raise QuoteUnavailable("Pris for denne ruten er ikke tilgjengelig ennå.")
    amount = fare.return_price if return_trip else fare.one_way_price
    if amount is None:
        raise QuoteUnavailable("Tur-retur-pris for denne ruten er ikke tilgjengelig ennå.")
    return Quote(fare=fare, amount=amount, currency=fare.currency, return_trip=return_trip)


@transaction.atomic
def create_booking_request(cleaned_data):
    quote = cleaned_data["quote"]
    idempotency_key = cleaned_data["idempotency_key"]
    existing = Booking.objects.select_related("customer_contact").filter(
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        return existing, False

    snapshot = {
        "fare_id": quote.fare.pk,
        "route_name": quote.fare.route.name,
        "vehicle_class": quote.fare.vehicle_class,
        "return_trip": quote.return_trip,
        "vat_included": quote.fare.vat_included,
        "amount": str(quote.amount),
        "currency": quote.currency,
    }
    try:
        booking = _insert_booking(
            route=cleaned_data["route"],
            pickup_at=cleaned_data["pickup_at"],
            return_at=cleaned_data.get("return_at") if quote.return_trip else None,
            adults=cleaned_data["adults"],
            children=cleaned_data["children"],
            luggage=cleaned_data["luggage"],
            flight_number=cleaned_data.get("flight_number", ""),
            notes=cleaned_data.get("notes", ""),
            quoted_price=quote.amount,
            currency=quote.currency,
            fare_snapshot=snapshot,
            terms_version=TERMS_VERSION,
            terms_accepted_at=timezone.now(),
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        return Booking.objects.get(idempotency_key=idempotency_key), False

    CustomerContact.objects.create(
        booking=booking,
        name=cleaned_data["name"],
        email=cleaned_data["email"],
        phone=cleaned_data["phone"],
    )
    AuditEvent.objects.create(
        booking=booking,
        event_type="booking.requested",
        metadata={"status": booking.status},
    )
    return booking, True


@transaction.atomic
def _insert_booking(**values):
    # A savepoint keeps the outer transaction usable after a unique-key race.
    return Booking.objects.create(**values)


ALLOWED_TRANSITIONS = {
    Booking.Status.PENDING_CONFIRMATION: {
        Booking.Status.CONFIRMED,
        Booking.Status.CANCELLED_BY_CUSTOMER,
        Booking.Status.CANCELLED_BY_OPERATOR,
    },
    Booking.Status.CONFIRMED: {
        Booking.Status.COMPLETED,
        Booking.Status.CANCELLED_BY_CUSTOMER,
        Booking.Status.CANCELLED_BY_OPERATOR,
        Booking.Status.NO_SHOW,
    },
}


@transaction.atomic
def transition_booking(booking: Booking, to_status: str, *, actor=None):
    locked = Booking.objects.select_for_update().get(pk=booking.pk)
    if to_status == locked.status:
        return locked, False
    if to_status not in ALLOWED_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(
            f"Overgang fra {locked.get_status_display()} er ikke tillatt.",
        )
    previous = locked.status
    locked.status = to_status
    locked.save(update_fields=("status", "updated_at"))
    AuditEvent.objects.create(
        booking=locked,
        actor=actor,
        event_type="booking.status_changed",
        metadata={"from": previous, "to": to_status},
    )
    return locked, True
