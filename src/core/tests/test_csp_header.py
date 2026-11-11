"""Tests for the Content-Security-Policy header middleware."""
from django.test import TestCase


class ContentSecurityPolicyTests(TestCase):
    def test_csp_header_is_set_on_responses(self):
        response = self.client.get('/')
        self.assertIn('Content-Security-Policy', response.headers)

    def test_csp_header_contains_core_directives(self):
        response = self.client.get('/')
        csp = response.headers['Content-Security-Policy']

        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_csp_header_allows_required_third_party_hosts(self):
        response = self.client.get('/')
        csp = response.headers['Content-Security-Policy']

        self.assertIn('https://cdn.jsdelivr.net', csp)
        self.assertIn('https://unpkg.com', csp)
        self.assertIn('https://client.sleekplan.com', csp)
        self.assertIn('https://*.tile.openstreetmap.org', csp)
        self.assertIn('https://www.youtube.com', csp)
