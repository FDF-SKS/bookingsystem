"""Tests for the Content-Security-Policy header middleware."""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

SCRIPT_SRC_RE = re.compile(r"script-src([^;]*)")


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

    def test_public_csp_blocks_inline_scripts(self):
        """script-src must use a nonce instead of 'unsafe-inline'."""
        response = self.client.get('/')
        script_src = SCRIPT_SRC_RE.search(
            response.headers['Content-Security-Policy']
        ).group(1)

        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertIn("'nonce-", script_src)

    def test_nonce_matches_rendered_inline_scripts(self):
        response = self.client.get(reverse('account_login'))
        header_nonce = re.search(
            r"'nonce-([^']+)'", response.headers['Content-Security-Policy']
        ).group(1)

        content = response.content.decode()
        self.assertIn(f'nonce="{header_nonce}"', content)
        # No executable inline script may be rendered without the nonce. Inert
        # JSON data blocks (``<script type="application/json">``, used by
        # allauth) are not script-eligible and are exempt from script-src.
        for tag in re.findall(r'<script[^>]*>', content):
            if 'src=' in tag or 'type="application/json"' in tag:
                continue
            self.assertIn(f'nonce="{header_nonce}"', tag)

    def test_nonce_is_unique_per_request(self):
        first = self.client.get('/').headers['Content-Security-Policy']
        second = self.client.get('/').headers['Content-Security-Policy']

        first_nonce = re.search(r"'nonce-([^']+)'", first).group(1)
        second_nonce = re.search(r"'nonce-([^']+)'", second).group(1)
        self.assertNotEqual(first_nonce, second_nonce)

    def test_admin_csp_allows_unsafe_inline_and_eval_for_alpine(self):
        response = self.client.get('/admin/login/')
        csp = response.headers['Content-Security-Policy']

        self.assertIn("'unsafe-inline'", csp)
        self.assertIn("'unsafe-eval'", csp)

    def test_public_csp_does_not_allow_unsafe_eval(self):
        response = self.client.get('/')
        csp = response.headers['Content-Security-Policy']

        self.assertNotIn("'unsafe-eval'", csp)


class NoInlineJavaScriptInTemplatesTests(TestCase):
    """Templates must not rely on inline JS beyond nonce-tagged <script> blocks.

    Inline event-handler attributes cannot be covered by a nonce, so the site
    expresses those behaviours as ``data-*`` attributes handled by
    ``static/js/ui-actions.js``. The staff-only admin keeps its relaxed policy.
    """

    def _template_files(self):
        base = Path(settings.BASE_DIR)
        files = list((base / "templates").rglob("*.html"))
        for templates_dir in base.glob("*/templates"):
            files.extend(templates_dir.rglob("*.html"))
        return [
            path
            for path in files
            if "/templates/admin/" not in path.as_posix()
        ]

    def test_every_inline_script_has_a_nonce(self):
        offenders = []
        for path in self._template_files():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "<script" in line and "src=" not in line and "nonce=" not in line:
                    offenders.append(f"{path.relative_to(settings.BASE_DIR)}:{number}")
        self.assertEqual(offenders, [])

    def test_no_inline_event_handler_attributes(self):
        pattern = re.compile(
            r"\son(?:click|change|submit|input|load|error|focus|blur|"
            r"keyup|keydown|mouseover|mouseout|dblclick)\s*="
        )
        offenders = []
        for path in self._template_files():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(settings.BASE_DIR)}:{number}")
        self.assertEqual(offenders, [])


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
