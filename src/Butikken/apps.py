from django.apps import AppConfig


class ButikkenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Butikken'
    verbose_name = 'Butikken (Provisions Booking)'

    def ready(self):
        import Butikken.signals  # noqa: F401


