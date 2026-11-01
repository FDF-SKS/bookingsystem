from django.apps import AppConfig


class AktivitetsTeamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'AktivitetsTeam'
    verbose_name = 'AktivitetsTeam (Aktivitet Booking)'

    def ready(self):
        import AktivitetsTeam.signals  # noqa: F401


