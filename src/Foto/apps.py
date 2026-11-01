from django.apps import AppConfig


class FotoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Foto'
    verbose_name = 'Foto (Foto Booking)'

    def ready(self):
        import Foto.signals  # noqa: F401


