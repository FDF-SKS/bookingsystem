from django.apps import AppConfig


class SjakConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Sjak'
    verbose_name = 'Sjak (Equipment Booking)'

    def ready(self):
        import Sjak.signals  # noqa: F401


