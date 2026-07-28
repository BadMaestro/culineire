from django.apps import AppConfig


class SponsorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sponsors"
    verbose_name = "Sponsors"

    def ready(self):
        from . import signals  # noqa: F401  — connects logo file-cleanup handlers
