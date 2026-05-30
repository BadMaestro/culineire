from django.apps import AppConfig


class AmuseBoucheConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "amuse_bouche"
    verbose_name = "Amuse-Bouche"

    def ready(self):
        import amuse_bouche.signals  # noqa: F401
