from django.contrib import admin
from django.utils.html import format_html

from .models import SponsorCell


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
    list_filter = ("ring", "status")
    search_fields = ("sponsor_name", "sponsor_tagline", "admin_notes")
    readonly_fields = ("cell_number", "ring", "position_in_ring", "price_display_col", "created_at", "updated_at")
    ordering = ["ring", "position_in_ring"]

    fieldsets = (
        ("Cell Info", {
            "fields": ("cell_number", "ring", "position_in_ring", "price_display_col", "status"),
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
            "reserved": "#ff9800",
            "sold": "#2196f3",
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
    sponsor_logo_thumb.short_description = "Logo"
