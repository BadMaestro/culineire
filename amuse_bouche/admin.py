from django.contrib import admin

from .models import AmuseBouche, AmuseBoucheGalleryImage


class AmuseBoucheGalleryImageInline(admin.TabularInline):
    model = AmuseBoucheGalleryImage
    extra = 1
    fields = ("image", "alt_text", "caption", "sort_order", "is_active")


@admin.register(AmuseBouche)
class AmuseBoucheAdmin(admin.ModelAdmin):
    list_display = ("title", "content_type", "status", "author", "is_featured", "published_at", "created_at")
    list_filter = ("status", "content_type", "is_featured", "allow_comments", "created_at")
    search_fields = ("title", "short_description", "author__name", "slug")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "linked_recipe", "linked_article")
    readonly_fields = ("created_at", "updated_at", "view_count", "media_folder")
    inlines = [AmuseBoucheGalleryImageInline]
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
        ("Publication", {
            "fields": (
                "status",
                "published_at",
                "is_featured",
                "allow_comments",
                "moderation_note",
            )
        }),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("System", {"fields": ("media_folder", "view_count", "created_at", "updated_at")}),
    )


@admin.register(AmuseBoucheGalleryImage)
class AmuseBoucheGalleryImageAdmin(admin.ModelAdmin):
    list_display = ("amuse_bouche", "sort_order", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("amuse_bouche__title", "alt_text", "caption")
    autocomplete_fields = ("amuse_bouche",)
