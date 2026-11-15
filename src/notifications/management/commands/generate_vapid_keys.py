"""Generate a VAPID key pair for Web Push.

Usage::

    python manage.py generate_vapid_keys

Copy the two values into the environment (``.env`` locally, the server's
environment in production) as ``WEBPUSH_VAPID_PUBLIC_KEY`` and
``WEBPUSH_VAPID_PRIVATE_KEY``. The public key is safe to share with browsers;
the private key must stay secret.
"""
import base64

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


class Command(BaseCommand):
    help = 'Generate a VAPID key pair for Web Push notifications.'

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()

        private_key = _b64url(
            vapid.private_key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        public_key = _b64url(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )

        self.stdout.write('Tilføj disse linjer til din .env-fil:\n')
        self.stdout.write(f'WEBPUSH_VAPID_PUBLIC_KEY={public_key}')
        self.stdout.write(f'WEBPUSH_VAPID_PRIVATE_KEY={private_key}')
        self.stdout.write(
            '\nDen private nøgle må ikke committes eller deles. '
            'Genstarter du tjenesten, skal nøglerne være sat i miljøet.'
        )
