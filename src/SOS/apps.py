from django.apps import AppConfig


class SosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'SOS'
    
    def ready(self):
        """Registrer signals når app er klar."""
        import SOS.signals  # noqa: F401


