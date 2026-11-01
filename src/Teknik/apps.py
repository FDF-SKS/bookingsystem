from django.apps import AppConfig


class TeknikConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Teknik'
    verbose_name = 'Teknik (Teknik Booking)'

    def ready(self):
        import Teknik.signals  # noqa: F401


