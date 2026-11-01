import datetime as dt

from django.test import TestCase

from organization.models import Team, Volunteer

from .models import DepotBooking, DepotItem


class DepotTestMixin:
    """Shared fixtures for the depot tests."""

    def setUp(self):
        self.item = DepotItem.objects.create(
            name="Test Item",
            description="Test Description",
            quantity=10,
        )
        self.volunteer = Volunteer.objects.create_user(
            username="testuser",
            first_name="Test",
            last_name="Volunteer",
            email="test@example.com",
        )
        self.team = Team.objects.create(name="Test Team", short_name="TT")
        self.start_date = dt.date(2026, 1, 1)
        self.end_date = self.start_date + dt.timedelta(days=1)

    def create_booking(self, quantity, status):
        return DepotBooking.objects.create(
            item=self.item,
            team=self.team,
            team_contact=self.volunteer,
            quantity=quantity,
            start_date=self.start_date,
            end_date=self.end_date,
            status=status,
        )


class DepotItemTestCase(DepotTestMixin, TestCase):
    """Test cases for DepotItem."""

    def test_item_creation(self):
        self.assertEqual(self.item.name, "Test Item")
        self.assertEqual(self.item.quantity, 10)
        self.assertIsNotNone(self.item.created)

    def test_item_str(self):
        self.assertEqual(str(self.item), "Test Item")

    def test_available_quantity_no_bookings(self):
        self.assertEqual(self.item.available_quantity(self.start_date, self.end_date), 10)

    def test_available_quantity_with_approved_booking(self):
        self.create_booking(quantity=3, status="Approved")
        self.assertEqual(self.item.available_quantity(self.start_date, self.end_date), 7)

    def test_available_quantity_with_pending_booking(self):
        self.create_booking(quantity=4, status="Pending")
        self.assertEqual(self.item.available_quantity(self.start_date, self.end_date), 6)

    def test_available_quantity_ignores_rejected_bookings(self):
        self.create_booking(quantity=5, status="Rejected")
        self.assertEqual(self.item.available_quantity(self.start_date, self.end_date), 10)

    def test_available_quantity_never_negative(self):
        self.create_booking(quantity=25, status="Approved")
        self.assertEqual(self.item.available_quantity(self.start_date, self.end_date), 0)


class DepotBookingTestCase(DepotTestMixin, TestCase):
    """Test cases for DepotBooking."""

    def test_booking_creation(self):
        booking = self.create_booking(quantity=5, status="Pending")
        self.assertEqual(booking.quantity, 5)
        self.assertEqual(booking.status, "Pending")

    def test_booking_str(self):
        booking = self.create_booking(quantity=5, status="Pending")
        self.assertEqual(str(booking), f"{self.item.name} - {self.team.name} (Pending)")

    def test_booking_status_color(self):
        booking = self.create_booking(quantity=5, status="Approved")
        self.assertEqual(booking.get_status_display_color(), "success")

    def test_is_overbooked(self):
        # 8 approved + another 5 overlapping exceeds the 10 in stock.
        self.create_booking(quantity=8, status="Approved")
        overlapping = self.create_booking(quantity=5, status="Pending")
        self.assertTrue(overlapping.is_overbooked())

    def test_is_not_overbooked_when_within_stock(self):
        self.create_booking(quantity=2, status="Approved")
        overlapping = self.create_booking(quantity=3, status="Pending")
        self.assertFalse(overlapping.is_overbooked())
