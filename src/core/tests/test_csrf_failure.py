"""Tests for the CSRF failure logger (core/views.py)."""
from django.test import RequestFactory, TestCase

from core.views import csrf_failure


class CsrfFailureViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_logs_reason_origin_and_cookie_state(self):
        request = self.factory.post(
            '/accounts/login/',
            HTTP_ORIGIN='http://localhost:8001',
            HTTP_REFERER='http://localhost:8001/accounts/login/',
        )

        with self.assertLogs('core.views', level='WARNING') as logs:
            response = csrf_failure(request, reason='Origin checking failed')

        self.assertEqual(response.status_code, 403)
        output = ' '.join(logs.output)
        self.assertIn('Origin checking failed', output)
        self.assertIn('http://localhost:8001', output)
        self.assertIn('csrf_cookie=False', output)

    def test_reason_is_never_sent_to_the_client(self):
        request = self.factory.post('/accounts/login/')

        with self.assertLogs('core.views', level='WARNING'):
            response = csrf_failure(request, reason='intern-fejl-aarsag')

        self.assertEqual(response.status_code, 403)
        self.assertNotIn('intern-fejl-aarsag', response.content.decode())

    def test_header_values_cannot_inject_log_lines(self):
        request = self.factory.post(
            '/accounts/login/',
            HTTP_ORIGIN='http://a\nFAKE LOG LINE',
        )

        with self.assertLogs('core.views', level='WARNING') as logs:
            csrf_failure(request, reason='x')

        # %r-escaping betyder, at der ikke kommer en rigtig ny linje i loggen.
        self.assertNotIn('\nFAKE', ' '.join(logs.output))
