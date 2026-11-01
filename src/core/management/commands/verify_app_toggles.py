"""
Management command to verify app feature toggles.

This command checks the status of all feature toggles and displays:
- Current backend (Redis or Database)
- Backend connectivity status
- Status of each app toggle (enabled/disabled)
"""
import redis
from constance import config
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify app feature toggles and backend configuration'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== App Feature Toggles Verification ===\n')
        )

        # Display environment
        environment = settings.ENVIRONMENT
        self.stdout.write(f'Environment: {self.style.SUCCESS(environment)}')

        # Determine and test backend
        backend_status = self._check_backend_status()
        
        if backend_status['success']:
            self.stdout.write(
                f'Backend: {self.style.SUCCESS(backend_status["backend"])}'
            )
            self.stdout.write(
                f'Backend Status: {self.style.SUCCESS("Connected")}\n'
            )
        else:
            self.stdout.write(
                f'Backend: {self.style.WARNING(backend_status["backend"])}'
            )
            self.stdout.write(
                f'Backend Status: {self.style.ERROR("Disconnected")}\n'
            )
            self.stdout.write(
                self.style.WARNING(f'Warning: {backend_status["error"]}\n')
            )

        # Display all feature toggles
        self.stdout.write(self.style.SUCCESS('=== App Toggle Status ===\n'))

        toggles = {
            'APP_ENABLE_SOS': 'SOS',
            'APP_ENABLE_TEKNIK': 'Teknik',
            'APP_ENABLE_AKTIVITETSTEAM': 'AktivitetsTeam',
            'APP_ENABLE_FOTO': 'Foto',
            'APP_ENABLE_BUTIKKEN': 'Butikken (Store)',
            'APP_ENABLE_SJAK': 'Sjak (Tools & Materials)',
            'APP_ENABLE_CONTACTS': 'Contact Book',
            'APP_ENABLE_LEGEAFTALER': 'Volunteer Appointments',
            'APP_ENABLE_DEPOT': 'Depot (Inventory)',
        }

        for toggle_name, display_name in toggles.items():
            is_enabled = getattr(config, toggle_name, True)
            status_color = self.style.SUCCESS if is_enabled else self.style.WARNING
            status_text = 'ENABLED' if is_enabled else 'DISABLED'
            self.stdout.write(
                f'{display_name}: {status_color(status_text)}'
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Verification complete'))

    def _check_backend_status(self):
        """
        Check if the configured constance backend is accessible.
        
        Returns a dict with:
        - success: bool
        - backend: str (Redis or Database)
        - error: str (if success is False)
        """
        environment = settings.ENVIRONMENT

        if environment in ['staging', 'production']:
            return self._check_redis_backend()
        else:
            return self._check_database_backend()

    def _check_redis_backend(self):
        """Check Redis backend connectivity."""
        try:
            redis_config = settings.CONSTANCE_REDIS_CONNECTION
            conn = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                decode_responses=True,
                socket_connect_timeout=5,
            )
            conn.ping()
            return {
                'success': True,
                'backend': 'Redis',
                'error': None,
            }
        except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
            return {
                'success': False,
                'backend': 'Redis',
                'error': str(e),
            }

    def _check_database_backend(self):
        """Check Database backend connectivity."""
        try:
            from django.db import connection
            connection.ensure_connection()
            return {
                'success': True,
                'backend': 'Database',
                'error': None,
            }
        except Exception as e:
            return {
                'success': False,
                'backend': 'Database',
                'error': str(e),
            }


