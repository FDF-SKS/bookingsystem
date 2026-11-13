"""Tests for the Content-Security-Policy header middleware."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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

    def test_admin_csp_allows_unsafe_eval_for_alpine(self):
        response = self.client.get('/admin/login/')
        csp = response.headers['Content-Security-Policy']

        self.assertIn("'unsafe-eval'", csp)

    def test_public_csp_does_not_allow_unsafe_eval(self):
        response = self.client.get('/')
        csp = response.headers['Content-Security-Policy']

        self.assertNotIn("'unsafe-eval'", csp)


class ThirdPartyScriptTests(TestCase):
    """Executable third-party assets must be pinned and self-hosted."""

    def _template_files(self):
        base = Path(settings.BASE_DIR)
        files = list((base / "templates").rglob("*.html"))
        for templates_dir in base.glob("*/templates"):
            files.extend(templates_dir.rglob("*.html"))
        return files

    def test_no_unpinned_cdn_script_versions(self):
        offenders = [
            str(path.relative_to(settings.BASE_DIR))
            for path in self._template_files()
            if "@latest" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_sleekplan_sdk_only_loaded_for_anonymous_pages(self):
        anonymous = self.client.get(reverse("account_login"))
        self.assertContains(anonymous, "client.sleekplan.com")

        user = get_user_model().objects.create_user(
            username="script-user",
            email="script@example.com",
            password="pw-12345-xyz",
            first_name="Script",
            last_name="User",
        )
        self.client.force_login(user)

        authenticated = self.client.get(
            reverse("organization_Volunteer_detail", args=[user.pk])
        )
        self.assertEqual(authenticated.status_code, 200)
        self.assertNotContains(authenticated, "client.sleekplan.com")
