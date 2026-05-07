from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"
    verbose_name = "Monitoring"

    def ready(self):
        import monitoring.signals  # noqa: F401
