"""
Smoke tests for the booking apps that previously had no test coverage.

These verify that each app's primary list pages render for a logged-in staff
user (catching template/URL/import regressions) and that the dashboard is
protected. They intentionally do not assert on page contents to keep them
robust as the UI evolves.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

APP_LIST_URL_NAMES = {
    "AktivitetsTeam": [
        "AktivitetsTeam_AktivitetsTeamItem_list",
        "AktivitetsTeam_AktivitetsTeamBooking_list",
    ],
    "Butikken": [
        "Butikken_ButikkenItem_list",
        "Butikken_ButikkenBooking_list",
        "Butikken_ButikkenOrder_list",
    ],
    "Foto": [
        "Foto_FotoItem_list",
        "Foto_FotoBooking_list",
    ],
    "Sjak": [
        "Sjak_SjakItem_list",
        "Sjak_SjakBooking_list",
        "Sjak_SjakItemType_list",
    ],
    "SOS": [
        "SOS_SOSBooking_list",
        "SOS_SOSItem_list",
        "SOS_SOSType_list",
    ],
    "Teknik": [
        "Teknik_TeknikBooking_list",
        "Teknik_TeknikItem_list",
        "Teknik_TeknikType_list",
    ],
}


class AppListSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="smoke-admin",
            email="smoke@example.com",
            password="pw-12345-xyz",
            first_name="Smoke",
            last_name="Admin",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def assert_lists_render(self, url_names):
        for name in url_names:
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200, f"{name} did not render")

    def test_aktivitetsteam_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["AktivitetsTeam"])

    def test_butikken_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Butikken"])

    def test_foto_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Foto"])

    def test_sjak_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Sjak"])

    def test_sos_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["SOS"])

    def test_teknik_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Teknik"])


class DashboardAuthTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)
