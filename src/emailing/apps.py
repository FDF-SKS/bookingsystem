from django.apps import AppConfig


class EmailingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emailing'
    verbose_name = 'Emails'

    def ready(self):
        from . import signals  # noqa: F401
