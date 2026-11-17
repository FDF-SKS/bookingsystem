"""Tests for the dashboard feed and sidebar (``core.views.index``)."""
from datetime import time, timedelta

from constance.test import override_config
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.dashboard import build_sidebar

User = get_user_model()


class DashboardViewTests(TestCase):
    def test_dashboard_renders_for_authenticated_user(self):
        user = User.objects.create_user(
            username="dash-user",
            email="dash@example.com",
            password="pw-12345-xyz",
            first_name="Dash",
            last_name="Board",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("feed_items", response.context)
        self.assertEqual(list(response.context["feed_items"]), [])
        # The dashboard navbar is only the brand; navigation and the profile live
        # in the sidebar.
        self.assertContains(response, "dashboard-navbar")
        self.assertContains(response, "dashboard-navbar__tag")
        self.assertContains(response, "dashboard-shell")
        self.assertNotContains(response, "navbar-expand-lg")
        self.assertContains(response, "dashboard-user")
        self.assertContains(response, "Min profil")
        self.assertContains(response, "dashboard-nav-section__label")
        self.assertContains(response, "dashboard-nav-flat")
        sidebar = {
            section.title: section
            for section in response.context["sidebar_sections"]
        }
        self.assertContains(response, sidebar["Legeaftaler"].only_item.label)
        self.assertContains(response, "bi-grid-1x2")
        self.assertNotContains(response, "Tider er i dansk tid")

    def test_dashboard_only_includes_user_team_bookings(self):
        user = User.objects.create_user(
            username="dash-user2",
            email="dash2@example.com",
            password="pw-12345-xyz",
            first_name="Dash",
            last_name="Two",
        )
        self.client.force_login(user)

        # A booking belonging to a team the user is not a member of must not leak
        # into the dashboard.
        from organization.models import Team
        from Sjak.models import SjakBooking, SjakItem

        team = Team.objects.create(name="Other team", short_name="OT")
        item = SjakItem.objects.create(name="Item")
        tomorrow = timezone.localdate() + timedelta(days=1)
        SjakBooking.objects.create(
            team=team,
            item=item,
            team_contact=user,
            quantity=1,
            start_date=tomorrow,
            start_time=time(10, 0),
            end_date=tomorrow,
            end_time=time(12, 0),
            status="Pending",
        )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["feed_items"]), [])


class DashboardFeedTests(TestCase):
    def setUp(self):
        from organization.models import (
            Event,
            ProgramBlock,
            Team,
            TeamEventMembership,
            TeamMembership,
            Tjanse,
            TjanseOwnership,
        )
        from Sjak.models import SjakBooking, SjakItem

        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.user = User.objects.create_user(
            username="feed-user",
            email="feed@example.com",
            password="pw-12345-xyz",
            first_name="Feed",
            last_name="User",
        )
        self.team = Team.objects.create(name="Sjak", short_name="SJ")
        TeamMembership.objects.create(team=self.team, member=self.user)

        self.event = Event.objects.create(
            name="SKS E26",
            start_date=self.today,
            end_date=self.today + timedelta(days=5),
            deadline_sjak=self.tomorrow,
            deadline_teknik=self.tomorrow,
            deadline_mad=self.tomorrow,
            deadline_aktivitetsteam=self.tomorrow,
            deadline_foto=self.tomorrow,
            deadline_lokaler=self.tomorrow,
            deadline_sos=self.tomorrow,
        )
        TeamEventMembership.objects.create(team=self.team, event=self.event)

        self.item = SjakItem.objects.create(name="Telt")
        SjakBooking.objects.create(
            team=self.team,
            item=self.item,
            team_contact=self.user,
            event=self.event,
            quantity=2,
            start_date=self.tomorrow,
            start_time=time(12, 0),
            end_date=self.tomorrow,
            end_time=time(14, 0),
            status="Approved",
        )

        self.block = ProgramBlock.objects.create(
            event=self.event,
            team=self.team,
            category=ProgramBlock.CATEGORY_FIXED,
            title="Sjak-møde",
            day=self.tomorrow,
            start_time=time(10, 0),
            end_time=time(11, 0),
            content={
                "doc": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Husk vandflasker"}
                            ],
                        }
                    ],
                },
                "html": "",
            },
        )
        self.block.responsible.add(self.user)

        tjanse = Tjanse.objects.create(title="Opvask")
        TjanseOwnership.objects.create(
            tjanse=tjanse,
            event=self.event,
            team=self.team,
            due_date=self.tomorrow,
        )

    def test_feed_contains_dates_and_sources_in_order(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        items = response.context["feed_items"]
        kinds = {item.kind_label for item in items}
        self.assertTrue({"Sjak", "Rammeprogram", "Frist", "Opgave"} <= kinds)
        self.assertEqual(len(response.context["feed_days"]), 1)
        self.assertTrue(items[0].is_next)
        self.assertEqual(
            [item.starts_at for item in items],
            sorted(item.starts_at for item in items),
        )

        booking = next(item for item in items if item.kind_label == "Sjak")
        self.assertEqual(booking.title, "2 x Telt")
        self.assertEqual(booking.status, "Godkendt")
        self.assertEqual(booking.status_color, "success")
        # The agenda shows who is responsible instead of event/module details.
        self.assertEqual(booking.responsible, "Feed User")
        block = next(item for item in items if item.kind_label == "Rammeprogram")
        self.assertEqual(block.responsible, "Feed User")
        # Program blocks say whether they belong to a team or the shared plan.
        self.assertEqual(block.origin, "Sjak")
        self.assertFalse(block.is_preparation)
        # The block opens a modal with its content instead of navigating away.
        self.assertEqual(block.modal_id, f"program-block-{self.block.pk}")
        task = next(item for item in items if item.kind_label == "Opgave")
        self.assertEqual(task.responsible, "Sjak")
        # Deadlines are informational only and must not be clickable.
        deadline = next(item for item in items if item.kind_label == "Frist")
        self.assertFalse(deadline.linkable)
        self.assertEqual(
            next(item for item in items if item.title == "Sjak-frist").color,
            "warning",
        )
        self.assertEqual(
            next(item for item in items if item.title == "Teknik-frist").color,
            "tertiary",
        )

        # Agenda layout: date gutter, timeline items and clickable cards.
        self.assertContains(response, "agenda-day__date")
        self.assertContains(response, "agenda-item__card")
        self.assertContains(response, "agenda-item__card--static")
        self.assertContains(response, "Sjak-møde")
        self.assertContains(response, "agenda-item__meta")
        self.assertContains(response, "Feed User")
        self.assertContains(response, "feed-chip--origin")
        # Event details are scoped away; only the active event's data is shown.
        self.assertNotContains(response, "SKS E26")
        self.assertContains(response, "agenda-item__icon text-bg-warning")
        self.assertContains(response, "agenda-item__dot text-bg-warning")

        # The block card is a modal trigger; its content lives in the modal.
        self.assertContains(
            response, f'data-bs-target="#{block.modal_id}"'
        )
        self.assertContains(response, f'id="{block.modal_id}"')
        self.assertContains(response, "Husk vandflasker")
        self.assertContains(response, "Åbn i programmet")

    def test_program_block_without_content_shows_a_hint(self):
        self.block.content = {}
        self.block.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        block = next(
            item
            for item in response.context["feed_items"]
            if item.kind_label == "Rammeprogram"
        )
        self.assertIsNone(block.content)
        self.assertContains(
            response, "Der er endnu ikke skrevet en beskrivelse"
        )

    def test_preparation_blocks_are_labelled(self):
        from organization.models import ProgramBlock

        ProgramBlock.objects.create(
            event=self.event,
            category=ProgramBlock.CATEGORY_PREPARATION,
            title="Opstilling",
            day=self.tomorrow,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        block = next(
            item
            for item in response.context["feed_items"]
            if item.title == "Opstilling"
        )
        self.assertTrue(block.is_preparation)
        self.assertEqual(block.origin, "Fælles")
        self.assertContains(response, "feed-chip--prep")
        self.assertContains(response, "Forberedelse")

    def test_all_day_sources_are_marked(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        by_kind = {
            item.kind_label: item for item in response.context["feed_items"]
        }
        self.assertTrue(by_kind["Frist"].all_day)
        self.assertEqual(by_kind["Frist"].all_day_label, "Frist")
        self.assertTrue(by_kind["Opgave"].all_day)
        self.assertFalse(by_kind["Rammeprogram"].all_day)

    def test_overdue_deadlines_stay_visible_and_are_marked(self):
        from organization.models import Event

        Event.objects.filter(pk=self.event.pk).update(
            deadline_teknik=self.today - timedelta(days=1)
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        items = response.context["feed_items"]
        titles = [item.title for item in items]
        self.assertIn("Teknik-frist", titles)
        self.assertIn("Sjak-frist", titles)

        overdue = next(item for item in items if item.title == "Teknik-frist")
        self.assertTrue(overdue.is_overdue)
        self.assertEqual(overdue.status, "Overskredet")
        self.assertFalse(overdue.is_next)
        # The first item that is not overdue is still flagged as the next thing.
        self.assertTrue(next(item for item in items if not item.is_overdue).is_next)
        self.assertContains(response, "Overskredet")

    def test_feed_falls_back_to_the_active_event_without_membership(self):
        outsider = User.objects.create_user(
            username="uden-hold",
            email="uden-hold@example.com",
            password="pw-12345-xyz",
        )
        # Neither an event membership nor a team membership: event-wide
        # information such as the deadlines must still be shown.
        self.client.force_login(outsider)

        response = self.client.get(reverse("index"))

        titles = [item.title for item in response.context["feed_items"]]
        self.assertIn("Sjak-frist", titles)
        self.assertIn("Teknik-frist", titles)

    def test_ended_event_keeps_its_deadlines_on_the_dashboard(self):
        from organization.models import Event

        past = self.today - timedelta(days=10)
        Event.objects.update(
            start_date=past - timedelta(days=5),
            end_date=past,
            deadline_sjak=past,
            deadline_teknik=past,
            deadline_mad=past,
            deadline_aktivitetsteam=past,
            deadline_foto=past,
            deadline_lokaler=past,
            deadline_sos=past,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        items = response.context["feed_items"]
        # Only the deadlines survive; their dates are in the past but they are
        # still shown so the dashboard never goes blank by accident.
        deadlines = [item for item in items if item.kind_label == "Frist"]
        self.assertTrue(deadlines)
        self.assertTrue(all(item.is_overdue for item in deadlines))
        self.assertFalse(any(item.is_next for item in deadlines))
        self.assertNotContains(response, "Der er ikke planlagt noget endnu")

    def test_feed_picks_next_upcoming_event_among_several(self):
        from organization.models import Event, ProgramBlock, TeamEventMembership

        later = Event.objects.create(
            name="Senere event",
            start_date=self.today + timedelta(days=2),
            end_date=self.today + timedelta(days=7),
            deadline_sjak=self.today + timedelta(days=2),
            deadline_teknik=self.today + timedelta(days=2),
            deadline_mad=self.today + timedelta(days=2),
            deadline_aktivitetsteam=self.today + timedelta(days=2),
            deadline_foto=self.today + timedelta(days=2),
            deadline_lokaler=self.today + timedelta(days=2),
            deadline_sos=self.today + timedelta(days=2),
        )
        TeamEventMembership.objects.create(team=self.team, event=later)
        ProgramBlock.objects.create(
            event=later,
            team=self.team,
            category=ProgramBlock.CATEGORY_FIXED,
            title="Senere program",
            day=self.today + timedelta(days=2),
            start_time=time(15, 0),
            end_time=time(16, 0),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        titles = [item.title for item in response.context["feed_items"]]
        # The ongoing event wins over the one that starts later.
        self.assertIn("Sjak-møde", titles)
        self.assertNotIn("Senere program", titles)
        self.assertEqual(titles.count("Sjak-frist"), 1)

    def test_feed_ignores_events_the_user_does_not_take_part_in(self):
        from organization.models import Event, ProgramBlock

        unrelated = Event.objects.create(
            name="Fremmed event",
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=5),
            deadline_sjak=self.tomorrow,
            deadline_teknik=self.tomorrow,
            deadline_mad=self.tomorrow,
            deadline_aktivitetsteam=self.tomorrow,
            deadline_foto=self.tomorrow,
            deadline_lokaler=self.tomorrow,
            deadline_sos=self.tomorrow,
        )
        ProgramBlock.objects.create(
            event=unrelated,
            category=ProgramBlock.CATEGORY_FIXED,
            title="Fremmed program",
            day=self.tomorrow,
            start_time=time(15, 0),
            end_time=time(16, 0),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("index"))

        titles = [item.title for item in response.context["feed_items"]]
        self.assertIn("Sjak-møde", titles)
        self.assertNotIn("Fremmed program", titles)
        self.assertEqual(titles.count("Sjak-frist"), 1)

    def test_sidebar_links_list_and_create_views(self):
        sections = {
            section.title: section
            for section in build_sidebar(self.user, reverse("index"))
        }

        self.assertIn("Sjak", sections)
        self.assertIn("Organisation", sections)
        self.assertEqual(sections["Sjak"].icon, "bi-tools")
        booking = next(
            item for item in sections["Sjak"].items if item.label == "Bookinger"
        )
        self.assertTrue(booking.create_url)
        self.assertFalse(booking.active)

        # Catalog/item creation is admin-only, so there is no "+" here.
        catalogue = next(
            item for item in sections["Sjak"].items if item.label == "Sager"
        )
        self.assertIsNone(catalogue.create_url)

        # Telephone book and Wiki live in the overview section; single-entry
        # groups (Organisation) are flattened into a direct link.
        labels = {item.label for item in sections["Overblik"].items}
        self.assertIn("Telefonbog", labels)
        self.assertIn("Wiki", labels)
        self.assertNotIn("Wiki", sections)
        telefonbog = next(
            item for item in sections["Overblik"].items if item.label == "Telefonbog"
        )
        self.assertIsNone(telefonbog.create_url)

        self.assertTrue(sections["Organisation"].flat)
        self.assertEqual(sections["Organisation"].only_item.label, "Nøgler")
        self.assertFalse(sections["Sjak"].flat)
        self.assertTrue(sections["Legeaftaler"].flat)

        all_labels = {
            item.label for section in sections.values() for item in section.items
        }
        self.assertNotIn("Teams", all_labels)
        self.assertNotIn("Events", all_labels)

        # Notifications and Admin are not sidebar rows: notifications live in the
        # profile menu and the admin shortcut is in the navbar.
        all_labels = {
            item.label for section in sections.values() for item in section.items
        }
        self.assertNotIn("Notifikationer", all_labels)
        self.assertNotIn("Administrator", all_labels)

    def test_sidebar_marks_current_page(self):
        sections = build_sidebar(self.user, reverse("index"))

        feed = sections[0].items[0]
        self.assertEqual(feed.label, "Feed")
        self.assertTrue(feed.active)
        self.assertTrue(sections[0].default_open)
        self.assertEqual(sections[0].icon, "bi-grid-1x2")

    def test_sidebar_opens_the_section_containing_the_current_page(self):
        sections = build_sidebar(self.user, reverse("Sjak_SjakBooking_list"))

        sjak = next(section for section in sections if section.title == "Sjak")
        self.assertTrue(sjak.default_open)
        booking = next(item for item in sjak.items if item.label == "Bookinger")
        self.assertTrue(booking.active)

    def test_sidebar_and_slim_navbar_are_on_every_page(self):
        self.client.force_login(self.user)

        for url in (
            reverse("index"),
            reverse("Sjak_SjakBooking_list"),
            reverse("Wiki_WikiPage_list"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "dashboard-sidebar")
                self.assertContains(response, "dashboard-nav-section__label")
                self.assertContains(response, "dashboard-navbar__tag")
                # The old horizontal menu is gone everywhere.
                self.assertNotContains(response, "navbarNav")
                self.assertNotContains(response, "navbar-expand-lg")

    def test_anonymous_pages_have_the_navbar_but_no_sidebar(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dashboard-navbar__tag")
        self.assertNotContains(response, "dashboard-sidebar")
        self.assertNotContains(response, "navbarNav")
        self.assertNotContains(response, "dashboard-admin-btn")

    def test_admin_shortcut_is_only_in_the_navbar_for_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("index"))
        self.assertNotContains(response, "dashboard-admin-btn")

        staff = User.objects.create_superuser(
            username="dash-staff",
            email="dash-staff@example.com",
            password="pw-12345-xyz",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("index"))
        self.assertContains(response, "dashboard-admin-btn")
        self.assertContains(response, reverse("admin:index"))

        section_titles = {
            section.title
            for section in build_sidebar(staff, reverse("index"))
        }
        self.assertNotIn("Mere", section_titles)
        loeb = next(
            section
            for section in build_sidebar(staff, reverse("index"))
            if section.title == "Løb"
        )
        self.assertTrue(loeb.flat)

    @override_config(APP_ENABLE_SJAK=False, APP_ENABLE_CONTACTS=False)
    def test_disabled_modules_are_removed_from_sidebar_and_feed(self):
        section_titles = {
            section.title
            for section in build_sidebar(self.user, reverse("index"))
        }
        self.assertNotIn("Sjak", section_titles)
        self.assertNotIn("Organisation", section_titles)
        self.assertIn("Teknik", section_titles)

        self.client.force_login(self.user)
        response = self.client.get(reverse("index"))

        labels = {item.kind_label for item in response.context["feed_items"]}
        titles = {item.title for item in response.context["feed_items"]}
        self.assertNotIn("Sjak", labels)
        self.assertNotIn("Sjak-frist", titles)
        self.assertIn("Rammeprogram", labels)
