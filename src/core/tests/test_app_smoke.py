"""
Smoke tests for the booking apps that previously had no test coverage.

These verify that each app's primary list pages render for a logged-in staff
user (catching template/URL/import regressions) and that the dashboard is
protected. They intentionally do not assert on page contents to keep them
robust as the UI evolves.
"""
from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from AktivitetsTeam.models import AktivitetsTeamItem
from Butikken.models import ButikkenBooking, ButikkenItem
from Depot.models import DepotItem
from Foto.models import FotoItem
from organization.models import Team
from Sjak.models import SjakItem
from SOS.models import SOSItem
from Teknik.models import TeknikItem

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
    "Depot": [
        "Depot_DepotItem_list",
        "Depot_DepotBooking_list",
    ],
    "Organization": [
        "organization_VolunteerAppointment_list",
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

    def test_depot_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Depot"])

    def test_organization_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Organization"])

    def test_foto_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Foto"])

    def test_sjak_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Sjak"])

    def test_sos_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["SOS"])

    def test_teknik_pages_render(self):
        self.assert_lists_render(APP_LIST_URL_NAMES["Teknik"])


class BookingFormSmokeTests(TestCase):
    """Verify the shared booking-form layout renders for every booking type."""

    BOOKING_CREATE_URL_NAMES = [
        "AktivitetsTeam_AktivitetsTeamBooking_create",
        # Butikken bookings are created through the order/cart flow, so its
        # create URL intentionally redirects to Butikken_ButikkenOrder_create.
        "Depot_DepotBooking_create",
        "Foto_FotoBooking_create",
        "Sjak_SjakBooking_create",
        "SOS_SOSBooking_create",
        "Teknik_TeknikBooking_create",
        "organization_VolunteerAppointment_create",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="form-smoke-admin",
            email="form-smoke@example.com",
            password="pw-12345-xyz",
            first_name="Form",
            last_name="Smoke",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_booking_create_forms_render(self):
        for name in self.BOOKING_CREATE_URL_NAMES:
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200, f"{name} did not render")

    def test_butikken_booking_update_form_renders(self):
        team = Team.objects.create(name="Form Team", short_name="FT")
        item = ButikkenItem.objects.create(
            name="Form vare", type="Aktivitet", content_unit="stk"
        )
        booking = ButikkenBooking.objects.create(
            item=item,
            team=team,
            team_contact=self.user,
            start_date=date.today(),
            start_time=time(8, 0),
            quantity=1,
            unit="stk",
        )
        response = self.client.get(
            reverse("Butikken_ButikkenBooking_update", args=[booking.pk])
        )
        self.assertEqual(response.status_code, 200)


class ItemDetailSmokeTests(TestCase):
    """Verify every catalog item detail page renders through the shared layout."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="item-smoke-admin",
            email="item-smoke@example.com",
            password="pw-12345-xyz",
            first_name="Item",
            last_name="Smoke",
        )
        cls.items = {
            "Sjak_SjakItem_detail": SjakItem.objects.create(
                name="Sjak testting", description="Sjak beskrivelse", quantity_lager="3"
            ),
            "Depot_DepotItem_detail": DepotItem.objects.create(
                name="Depot testvare", description="Depot beskrivelse"
            ),
            "Butikken_ButikkenItem_detail": ButikkenItem.objects.create(
                name="Butik testvare",
                type="Aktivitet",
                description="Butik beskrivelse",
                content_normal="2",
                content_unit="stk",
            ),
            "Teknik_TeknikItem_detail": TeknikItem.objects.create(
                name="Teknik testting", description="Teknik beskrivelse"
            ),
            "Foto_FotoItem_detail": FotoItem.objects.create(
                name="Foto testting", description="Foto beskrivelse"
            ),
            "SOS_SOSItem_detail": SOSItem.objects.create(
                name="SOS testting", description="SOS beskrivelse"
            ),
            "AktivitetsTeam_AktivitetsTeamItem_detail": AktivitetsTeamItem.objects.create(
                name="Aktivitet test",
                description="Aktivitets beskrivelse",
                short_description="Kort beskrivelse",
            ),
        }

    def setUp(self):
        self.client.force_login(self.user)

    def test_item_detail_pages_render(self):
        for name, item in self.items.items():
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name, args=[item.pk]))
                self.assertEqual(response.status_code, 200, f"{name} did not render")
                self.assertContains(response, "item-detail-card")
                self.assertContains(response, item.name)


class DashboardAuthTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)
