import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Route(models.Model):
    class Direction(models.TextChoices):
        TO_AIRPORT = "to_airport", "Til Gardermoen"
        FROM_AIRPORT = "from_airport", "Fra Gardermoen"

    name = models.CharField(max_length=120)
    origin = models.CharField(max_length=120)
    destination = models.CharField(max_length=120)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    estimated_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Fare(models.Model):
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="fares")
    vehicle_class = models.CharField(max_length=80, default="Standard")
    one_way_price = models.DecimalField(max_digits=10, decimal_places=2)
    return_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="NOK")
    vat_included = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("route", "vehicle_class", "-valid_from")

    def __str__(self):
        return f"{self.route} · {self.vehicle_class}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_CONFIRMATION = "pending_confirmation", "Ny forespørsel"
        CONFIRMED = "confirmed", "Bekreftet"
        COMPLETED = "completed", "Fullført"
        CANCELLED_BY_CUSTOMER = "cancelled_customer", "Kansellert av kunden"
        CANCELLED_BY_OPERATOR = "cancelled_operator", "Kansellert av operatøren"
        NO_SHOW = "no_show", "Ikke møtt"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_CONFIRMATION,
    )
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="bookings")
    pickup_at = models.DateTimeField()
    return_at = models.DateTimeField(null=True, blank=True)
    adults = models.PositiveSmallIntegerField(
        default=1,
        validators=(MinValueValidator(1), MaxValueValidator(6)),
    )
    children = models.PositiveSmallIntegerField(
        default=0,
        validators=(MinValueValidator(0), MaxValueValidator(6)),
    )
    luggage = models.PositiveSmallIntegerField(
        default=0,
        validators=(MinValueValidator(0), MaxValueValidator(12)),
    )
    flight_number = models.CharField(max_length=24, blank=True)
    notes = models.TextField(blank=True, max_length=1000)
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NOK")
    fare_snapshot = models.JSONField(default=dict)
    terms_version = models.CharField(max_length=32)
    terms_accepted_at = models.DateTimeField()
    idempotency_key = models.UUIDField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.public_id} · {self.get_status_display()}"


class CustomerContact(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="customer_contact",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    anonymise_after = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class AuditEvent(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledo_audit_events",
    )
    event_type = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.event_type} · {self.booking.public_id}"
