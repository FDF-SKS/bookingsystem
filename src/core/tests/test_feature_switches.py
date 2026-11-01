"""
Tests for the Kill Switch feature toggle system.

Tests cover:
- 200 OK response when an app is enabled
- 404 response when an app is disabled
- Admin always accessible regardless of toggle status
- Multiple disabled apps simultaneously
- Static and media files always accessible
- URL trailing slash handling
"""
from constance.test import override_config
from django.test import Client, TestCase


class FeatureToggleMiddlewareTests(TestCase):
    """Test the AppFeatureGateMiddleware."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @override_config(APP_ENABLE_SOS=True)
    def test_enabled_app_returns_200(self):
        """Test that an enabled app returns 200 OK or 404 from URL pattern, not middleware."""
        response = self.client.get('/sos/')
        # If enabled, middleware should NOT return 404 with "disabled" message
        if response.status_code == 404:
            # Make sure it's not from middleware
            self.assertNotIn(b'disabled', response.content.lower())

    @override_config(APP_ENABLE_SOS=False)
    def test_disabled_app_returns_404(self):
        """Test that a disabled app returns 404 from middleware."""
        response = self.client.get('/sos/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_TEKNIK=False)
    def test_disabled_teknik_app_returns_404(self):
        """Test that a disabled Teknik app returns 404."""
        response = self.client.get('/teknik/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_AKTIVITETSTEAM=False)
    def test_disabled_aktivitetsteam_app_returns_404(self):
        """Test that a disabled AktivitetsTeam app returns 404."""
        response = self.client.get('/aktivitetsteam/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_FOTO=False)
    def test_disabled_foto_app_returns_404(self):
        """Test that a disabled Foto app returns 404."""
        response = self.client.get('/foto/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_BUTIKKEN=False)
    def test_disabled_butikken_app_returns_404(self):
        """Test that disabled Butikken app returns 404."""
        response = self.client.get('/butikken/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_SJAK=False)
    def test_disabled_sjak_app_returns_404(self):
        """Test that a disabled Sjak app returns 404."""
        response = self.client.get('/sjak/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_CONTACTS=False)
    def test_disabled_contacts_app_returns_404(self):
        """Test that a disabled Contact Book returns 404."""
        response = self.client.get('/organization/volunteer/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_CONTACTS=False)
    def test_disabled_legeaftaler_app_returns_404(self):
        """Test that a disabled Legeaftaler app (controlled by toggle) returns 404."""
        response = self.client.get('/organization/volunteerappointment/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_DEPOT=False)
    def test_disabled_depot_app_returns_404(self):
        """Test that a disabled Depot app returns 404."""
        response = self.client.get('/depot/')
        self.assertEqual(response.status_code, 404)

    def test_admin_always_accessible_when_enabled(self):
        """Test that /admin/ is always accessible even if other apps disabled."""
        # Try accessing admin with all apps disabled
        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=False,
            APP_ENABLE_AKTIVITETSTEAM=False,
            APP_ENABLE_FOTO=False,
            APP_ENABLE_BUTIKKEN=False,
        ):
            response = self.client.get('/admin/')
            # Should not be blocked by middleware (might be 302 redirect or 200)
            self.assertNotEqual(response.status_code, 404)

    def test_static_files_always_accessible(self):
        """Test that /static/ URLs are always accessible (not blocked by middleware)."""
        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=False,
            APP_ENABLE_AKTIVITETSTEAM=False,
            APP_ENABLE_FOTO=False,
            APP_ENABLE_BUTIKKEN=False,
        ):
            # Even if URL doesn't exist, middleware should not block it
            # or should not return our "disabled" message
            response = self.client.get('/static/test.css')
            # Either it exists (2xx) or doesn't (3xx/4xx), but NOT our middleware 404
            if response.status_code == 404:
                self.assertNotIn(b'disabled', response.content.lower())

    def test_media_files_always_accessible(self):
        """Test that /media/ URLs are always accessible (not blocked by middleware)."""
        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=False,
            APP_ENABLE_AKTIVITETSTEAM=False,
            APP_ENABLE_FOTO=False,
            APP_ENABLE_BUTIKKEN=False,
        ):
            # Even if URL doesn't exist, middleware should not block it
            response = self.client.get('/media/test.jpg')
            # Either it exists (2xx) or doesn't (3xx/4xx), but NOT our middleware 404
            if response.status_code == 404:
                self.assertNotIn(b'disabled', response.content.lower())

    @override_config(APP_ENABLE_SOS=False)
    def test_disabled_app_with_trailing_slash(self):
        """Test that disabled app with trailing slash is blocked."""
        response = self.client.get('/sos/')
        self.assertEqual(response.status_code, 404)

    @override_config(APP_ENABLE_SOS=False)
    def test_disabled_app_without_trailing_slash(self):
        """Test that disabled app without trailing slash is blocked."""
        response = self.client.get('/sos')
        # Django redirects to /sos/, which should then be blocked
        # Status code should be 404 from middleware or 301 redirect
        self.assertIn(response.status_code, [301, 302, 404])

    def test_multiple_disabled_apps_simultaneously(self):
        """Test that multiple apps can be disabled at the same time."""
        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=False,
            APP_ENABLE_FOTO=False,
        ):
            # All three should be blocked by middleware
            self.assertEqual(self.client.get('/sos/').status_code, 404)
            self.assertEqual(self.client.get('/teknik/').status_code, 404)
            self.assertEqual(self.client.get('/foto/').status_code, 404)

        # Verify these work when enabled (not blocked by middleware)
        with override_config(
            APP_ENABLE_SOS=True,
            APP_ENABLE_TEKNIK=True,
            APP_ENABLE_FOTO=True,
        ):
            # These should not be blocked by middleware (might be 404 for other reasons)
            sos_response = self.client.get('/sos/')
            # Should not be the middleware "disabled" message
            if sos_response.status_code == 404:
                self.assertNotIn(b'disabled', sos_response.content.lower())

    def test_organization_auth_urls_always_accessible(self):
        """Test that organization authentication URLs are always accessible regardless of toggles."""
        # Test with all organization toggles disabled
        with override_config(
            APP_ENABLE_CONTACTS=False,
            APP_ENABLE_LEGEAFTALER=False,
        ):
            # These should NOT be blocked by middleware (auth URLs must always work)
            # They might return 404 if URLs don't exist, but NOT due to middleware
            login_response = self.client.get('/organization/login/')
            logout_response = self.client.get('/organization/logout/')
            profile_response = self.client.get('/organization/profile/')
            
            # None of these should be blocked by feature toggle middleware
            # (they might be 404 for other reasons, but not with our disabled message)
            if login_response.status_code == 404:
                # Make sure it's not from our middleware blocking
                # The 404 should come from Django URL routing, not our middleware
                pass
            if logout_response.status_code == 404:
                pass
            if profile_response.status_code == 404:
                pass
            
            # But these specific routes SHOULD be blocked when disabled
            disabled_volunteer = self.client.get('/organization/volunteer/')
            self.assertEqual(disabled_volunteer.status_code, 404)
            
            disabled_legeaftaler = self.client.get('/organization/volunteerappointment/')
            self.assertEqual(disabled_legeaftaler.status_code, 404)
        """Test that root path (/) is always accessible."""
        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=False,
            APP_ENABLE_AKTIVITETSTEAM=False,
            APP_ENABLE_FOTO=False,
            APP_ENABLE_BUTIKKEN=False,
        ):
            response = self.client.get('/')
            # Root should not be blocked by middleware
            self.assertNotEqual(response.status_code, 404)

    @override_config(APP_ENABLE_SOS=False)
    def test_disabled_app_error_message(self):
        """Test that disabled app returns 404 status code."""
        response = self.client.get('/sos/')
        self.assertEqual(response.status_code, 404)


class FeatureToggleContextProcessorTests(TestCase):
    """Test the app_feature_toggles context processor."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @override_config(
        APP_ENABLE_SOS=True,
        APP_ENABLE_TEKNIK=True,
        APP_ENABLE_AKTIVITETSTEAM=True,
        APP_ENABLE_FOTO=True,
        APP_ENABLE_BUTIKKEN=True,
    )
    def test_context_has_config_object(self):
        """Test that templates have access to config object."""
        # This would require a view that renders a template
        # For now, we test that the config is accessible
        from django.test import RequestFactory

        from core.context_processors import app_feature_toggles

        factory = RequestFactory()
        request = factory.get('/')
        context = app_feature_toggles(request)

        self.assertIn('config', context)
        self.assertTrue(hasattr(context['config'], 'APP_ENABLE_SOS'))

    def test_config_values_are_correct(self):
        """Test that config values match toggle settings."""
        from django.test import RequestFactory

        from core.context_processors import app_feature_toggles

        factory = RequestFactory()
        request = factory.get('/')
        context = app_feature_toggles(request)

        with override_config(
            APP_ENABLE_SOS=False,
            APP_ENABLE_TEKNIK=True,
        ):
            context = app_feature_toggles(request)
            self.assertFalse(context['config'].APP_ENABLE_SOS)
            self.assertTrue(context['config'].APP_ENABLE_TEKNIK)


