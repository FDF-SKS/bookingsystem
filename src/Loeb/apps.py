from django.apps import AppConfig


class LoebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Loeb'
    verbose_name = 'Løb'

    def ready(self):
        import Loeb.signals
