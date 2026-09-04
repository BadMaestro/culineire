import csv

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from .models import AuditEvent, Booking, CustomerContact, Fare, Route
from .services import transition_booking


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "origin", "destination", "direction", "active")
    list_filter = ("direction", "active")
    search_fields = ("name", "origin", "destination")


@admin.register(Fare)
class FareAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "vehicle_class",
        "one_way_price",
        "return_price",
        "currency",
        "vat_included",
        "valid_from",
        "valid_to",
        "active",
    )
    list_filter = ("active", "currency", "vat_included")
    search_fields = ("route__name", "vehicle_class")


class CustomerContactInline(admin.StackedInline):
    model = CustomerContact
    extra = 0
    can_delete = False
    readonly_fields = ("name", "email", "phone", "anonymise_after")


class AuditEventInline(admin.TabularInline):
    model = AuditEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "actor", "metadata", "created_at")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "status",
        "route",
        "pickup_at",
        "quoted_price",
        "currency",
        "created_at",
    )
    list_filter = ("status", "route", "pickup_at", "created_at")
    search_fields = (
        "public_id",
        "customer_contact__name",
        "customer_contact__email",
        "customer_contact__phone",
        "flight_number",
    )
    readonly_fields = (
        "public_id",
        "status",
        "fare_snapshot",
        "terms_version",
        "terms_accepted_at",
        "idempotency_key",
        "created_at",
        "updated_at",
    )
    inlines = (CustomerContactInline, AuditEventInline)
    actions = (
        "confirm_selected",
        "complete_selected",
        "cancel_selected",
        "mark_no_show",
        "export_csv",
    )

    def has_add_permission(self, request):
        return False

    def _transition(self, request, queryset, status):
        changed = 0
        for booking in queryset:
            try:
                _, did_change = transition_booking(booking, status, actor=request.user)
            except ValidationError as exc:
                self.message_user(request, f"{booking.public_id}: {exc.message}", messages.ERROR)
            else:
                changed += int(did_change)
        self.message_user(request, f"Oppdatert: {changed}", messages.SUCCESS)

    @admin.action(description="Bekreft valgte forespørsler")
    def confirm_selected(self, request, queryset):
        self._transition(request, queryset, Booking.Status.CONFIRMED)

    @admin.action(description="Marker valgte som fullført")
    def complete_selected(self, request, queryset):
        self._transition(request, queryset, Booking.Status.COMPLETED)

    @admin.action(description="Kanseller valgte som operatør")
    def cancel_selected(self, request, queryset):
        self._transition(request, queryset, Booking.Status.CANCELLED_BY_OPERATOR)

    @admin.action(description="Marker valgte som ikke møtt")
    def mark_no_show(self, request, queryset):
        self._transition(request, queryset, Booking.Status.NO_SHOW)

    @admin.action(description="Eksporter valgte til CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ledo-bookings.csv"'
        writer = csv.writer(response)
        writer.writerow(("public_id", "status", "route", "pickup_at", "price", "currency"))
        for booking in queryset.select_related("route"):
            writer.writerow(
                (
                    booking.public_id,
                    booking.status,
                    booking.route.name,
                    booking.pickup_at.isoformat(),
                    booking.quoted_price,
                    booking.currency,
                ),
            )
        return response


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "booking", "actor")
    list_filter = ("event_type", "created_at")
    search_fields = ("booking__public_id",)
    readonly_fields = ("booking", "actor", "event_type", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
