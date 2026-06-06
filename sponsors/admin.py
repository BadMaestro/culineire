from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ProcessedStripeEvent,
    SanctionsSourceSnapshot,
    SanctionsSubject,
    SponsorApplication,
    SponsorApplicantDeclaration,
    SponsorAuditLog,
    SponsorCell,
    SponsorComplianceCheck,
    SponsorPayment,
    SponsorRoadmapItem,
)


@admin.register(SponsorCell)
class SponsorCellAdmin(admin.ModelAdmin):
    list_display = (
        "cell_number",
        "ring_label",
        "price_display_col",
        "status_badge",
        "sponsor_name",
        "sponsor_logo_thumb",
        "purchased_at",
    )
    list_filter = ("product_type", "ring", "status")
    search_fields = ("sponsor_name", "sponsor_tagline", "admin_notes")
    readonly_fields = ("cell_number", "ring", "position_in_ring", "product_type", "price_display_col", "created_at", "updated_at")
    ordering = ["ring", "position_in_ring"]

    fieldsets = (
        ("Cell Info", {
            "fields": ("cell_number", "ring", "position_in_ring", "product_type", "price_display_col", "status"),
        }),
        ("Sponsor Details", {
            "fields": ("sponsor_name", "sponsor_logo", "sponsor_url", "sponsor_tagline"),
        }),
        ("Admin", {
            "fields": ("purchased_at", "admin_notes", "created_at", "updated_at"),
        }),
    )

    def ring_label(self, obj):
        if obj.ring == 0:
            return "Centre"
        labels = {1: "Ring 1 (inner)", 2: "Ring 2", 3: "Ring 3", 4: "Ring 4 (outer)"}
        return labels.get(obj.ring, f"Ring {obj.ring}")
    ring_label.short_description = "Ring"

    def price_display_col(self, obj):
        return obj.price_display
    price_display_col.short_description = "Price"

    def status_badge(self, obj):
        colours = {
            "available": "#4caf50",
            "payment_pending": "#ff9800",
            "paid_pending_approval": "#9c27b0",
            "active": "#2196f3",
            "reserved": "#ff9800",
            "sold": "#2196f3",
            "expired": "#607d8b",
            "rejected": "#b71c1c",
            "unavailable": "#777",
        }
        colour = colours.get(obj.status, "#999")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colour,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def sponsor_logo_thumb(self, obj):
        if obj.sponsor_logo:
            return format_html(
                '<img src="{}" style="height:32px;width:32px;object-fit:contain;border-radius:4px;">',
                obj.sponsor_logo.url,
            )
        return ""
    sponsor_logo_thumb.short_description = "Logo/avatar"


@admin.register(SponsorApplication)
class SponsorApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sponsor_name",
        "cell",
        "status",
        "price_display",
        "email",
        "created_at",
        "published_at",
        "expires_at",
    )
    list_filter = ("status", "product_type", "cell__ring", "terms_version")
    search_fields = ("sponsor_name", "contact_name", "email", "website_url")
    readonly_fields = (
        "reference",
        "price_net_cents",
        "currency",
        "product_type",
        "term_days",
        "terms_accepted_at",
        "terms_version",
        "created_at",
        "updated_at",
    )
    raw_id_fields = ("cell", "approved_by", "rejected_by")
    ordering = ("-created_at",)


@admin.register(SponsorComplianceCheck)
class SponsorComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ("application", "status", "matched_name", "matched_source", "reviewed_by", "created_at")
    list_filter = ("status", "matched_source")
    search_fields = ("application__sponsor_name", "matched_name", "staff_notes")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("application", "reviewed_by")


@admin.register(SponsorApplicantDeclaration)
class SponsorApplicantDeclarationAdmin(admin.ModelAdmin):
    list_display = ("sponsor_name", "applicant_email", "contact_person", "accepted_at", "stripe_session_id")
    search_fields = ("sponsor_name", "applicant_email", "contact_person", "stripe_session_id")
    readonly_fields = ("created_at",)
    raw_id_fields = ("application",)


@admin.register(SanctionsSourceSnapshot)
class SanctionsSourceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("source_code", "status", "fetched_at", "record_count", "source_sha256")
    list_filter = ("source_code", "status")
    search_fields = ("source_name", "source_url", "source_sha256", "error_message")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SanctionsSubject)
class SanctionsSubjectAdmin(admin.ModelAdmin):
    list_display = ("primary_name", "source_code", "subject_type", "external_reference", "is_active")
    list_filter = ("source_code", "subject_type", "is_active")
    search_fields = ("primary_name", "normalised_name", "external_reference")
    raw_id_fields = ("source_snapshot",)


@admin.register(SponsorPayment)
class SponsorPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "status",
        "net_amount_cents",
        "vat_amount_cents",
        "total_amount_cents",
        "currency",
        "paid_at",
        "refunded_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "application__sponsor_name",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("application",)


@admin.register(ProcessedStripeEvent)
class ProcessedStripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "application", "processed_at")
    list_filter = ("event_type",)
    search_fields = ("event_id", "application__sponsor_name")
    raw_id_fields = ("application",)


@admin.register(SponsorAuditLog)
class SponsorAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "application", "cell", "actor", "from_status", "to_status")
    list_filter = ("action", "created_at")
    search_fields = ("application__sponsor_name", "notes")
    readonly_fields = ("created_at",)
    raw_id_fields = ("application", "cell", "actor")


@admin.register(SponsorRoadmapItem)
class SponsorRoadmapItemAdmin(admin.ModelAdmin):
    list_display = ("sort_order", "title", "phase", "status", "priority", "is_blocker", "updated_at")
    list_filter = ("status", "priority", "is_blocker", "phase")
    search_fields = ("title", "description", "phase")
    ordering = ("sort_order", "title")
