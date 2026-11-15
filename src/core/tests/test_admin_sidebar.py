"""The admin sidebar exposes Tjanser and Slutrengøring as their own sections."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse, reverse_lazy


class AdminSidebarTests(TestCase):
    def groups(self):
        return {
            str(group["title"]): group
            for group in settings.UNFOLD["SIDEBAR"]["navigation"]
        }

    def item_links(self, group_title):
        return [str(item["link"]) for item in self.groups()[group_title]["items"]]

    def test_tjanser_is_its_own_section_with_all_admin_pages(self):
        links = self.item_links("Tjanser")
        self.assertEqual(
            links,
            [
                str(reverse_lazy("admin:organization_tjanse_changelist")),
                str(reverse_lazy("admin:organization_tjanseownership_changelist")),
                str(reverse_lazy("admin:organization_tjanseswaprequest_changelist")),
                str(reverse_lazy("admin:organization_tjanseownership_overview")),
                str(
                    reverse_lazy(
                        "admin:organization_tjanseownership_status_overview"
                    )
                ),
            ],
        )

    def test_slutrengoring_section_links_to_the_board(self):
        links = self.item_links("Slutrengøring")
        self.assertIn(
            str(
                reverse_lazy(
                    "admin:organization_slutrengoringassignment_board"
                )
            ),
            links,
        )
        self.assertIn(
            str(
                reverse_lazy(
                    "admin:organization_slutrengoringassignment_changelist"
                )
            ),
            links,
        )
        self.assertIn(
            str(
                reverse_lazy(
                    "admin:organization_slutrengoringassignment_tools"
                )
            ),
            links,
        )

    def test_organization_section_no_longer_lists_tjanser(self):
        links = self.item_links("Organisering")
        self.assertNotIn(
            str(reverse_lazy("admin:organization_tjanse_changelist")), links
        )
        self.assertEqual(len(links), 4)
        self.assertIn(
            str(reverse_lazy("admin:organization_programblock_changelist")), links
        )

    def test_admin_index_renders_the_new_sections(self):
        user = get_user_model().objects.create_superuser(
            username="sidebar-admin",
            email="sidebar@example.com",
            password="pw-12345-xyz",
            first_name="Sidebar",
            last_name="Admin",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse_lazy("admin:organization_slutrengoringassignment_board"),
        )
        self.assertContains(response, "Slutrengøring")
        self.assertContains(response, "Tjanser")
