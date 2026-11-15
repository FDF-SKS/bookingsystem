from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notifikationer'

    def ready(self):
        # Importing the modules registers the signal receivers (side effect).
        import notifications.signals  # noqa: F401
