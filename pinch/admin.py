from django.contrib import admin

from .models import Pinch, PinchGalleryImage


class PinchGalleryImageInline(admin.TabularInline):
    model = PinchGalleryImage
    extra = 1
    fields = ("image", "alt_text", "caption", "sort_order", "is_active")


@admin.register(Pinch)
class PinchAdmin(admin.ModelAdmin):
    list_display = ("title", "content_type", "status", "author", "is_featured", "published_at", "created_at")
    list_filter = ("status", "content_type", "is_featured", "allow_comments", "created_at")
    search_fields = ("title", "short_description", "author__name", "slug")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "linked_recipe", "linked_article")
    readonly_fields = ("created_at", "updated_at", "view_count", "media_folder", "confirmation_timestamp", "confirmed_by", "moderated_by", "moderated_at")
    inlines = [PinchGalleryImageInline]
    fieldsets = (
        ("Content", {
            "fields": (
                "title",
                "slug",
                "author",
                "short_description",
                "content_type",
                "cover_image",
                "cover_image_alt",
            )
        }),
        ("Discovery links", {"fields": ("linked_recipe", "linked_article")}),
        ("Image Rights & Legal", {
            "fields": (
                "image_rights_status",
                "image_rights_note",
                "source_type",
                "source_title",
                "source_author",
                "source_url",
                "source_note",
                "confirmed_own_work",
                "confirmed_image_rights",
                "confirmed_rules",
                "confirmation_timestamp",
                "confirmed_by",
            )
        }),
        ("Publication", {
            "fields": (
                "status",
                "published_at",
                "is_featured",
                "allow_comments",
                "moderation_note",
                "moderated_by",
                "moderated_at",
            )
        }),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("System", {"fields": ("media_folder", "view_count", "created_at", "updated_at")}),
    )


@admin.register(PinchGalleryImage)
class PinchGalleryImageAdmin(admin.ModelAdmin):
    list_display = ("pinch", "sort_order", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("pinch__title", "alt_text", "caption")
    autocomplete_fields = ("pinch",)
