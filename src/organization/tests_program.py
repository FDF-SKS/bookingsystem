import json
from datetime import date, time, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import Event, HistoricalProgramBlock, ProgramBlock, Team, TeamMembership

User = get_user_model()


def tiptap_content(text='Hej'):
    doc = {
        'type': 'doc',
        'content': [
            {
                'type': 'paragraph',
                'content': [{'type': 'text', 'text': text}],
            }
        ],
    }
    return json.dumps({'doc': doc, 'html': f'<p>{text}</p>'})


class ProgramTestBase(TestCase):
    def setUp(self):
        self.day = date(2026, 10, 9)
        self.event = Event.objects.create(
            name='SKS E26',
            start_date=self.day,
            end_date=self.day + timedelta(days=2),
            deadline_sjak=self.day,
            deadline_teknik=self.day,
            deadline_mad=self.day,
            deadline_aktivitetsteam=self.day,
            deadline_foto=self.day,
            deadline_lokaler=self.day,
            deadline_sos=self.day,
        )
        self.staff = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='test-password'
        )
        self.alice = User.objects.create_user(
            username='alice', email='alice@example.com', password='test-password'
        )
        self.bob = User.objects.create_user(
            username='bob', email='bob@example.com', password='test-password'
        )
        self.team_a = Team.objects.create(name='Sjak', short_name='Sjak')
        self.team_b = Team.objects.create(name='Teknik', short_name='Tek')
        TeamMembership.objects.create(team=self.team_a, member=self.alice)
        TeamMembership.objects.create(team=self.team_b, member=self.bob)

    def create_block(self, **overrides):
        data = {
            'event': self.event,
            'team': None,
            'category': ProgramBlock.CATEGORY_FIXED,
            'title': 'Morgenmad',
            'day': self.day,
            'start_time': time(8, 0),
            'end_time': time(9, 0),
            'created_by': self.staff,
        }
        data.update(overrides)
        return ProgramBlock.objects.create(**data)

    def post_payload(self, **overrides):
        data = {
            'scope': 'base',
            'team': '',
            'title': 'Fælles start',
            'category': ProgramBlock.CATEGORY_FIXED,
            'day': self.day.isoformat(),
            'start_time': '18:00',
            'end_time': '19:00',
            'content': tiptap_content('Fælles start'),
        }
        data.update(overrides)
        return data


class ProgramPermissionTests(ProgramTestBase):
    def test_staff_can_create_framework_block(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('organization_ProgramBlock_create', args=(self.event.pk,)),
            self.post_payload(),
        )

        self.assertRedirects(
            response,
            reverse('organization_Event_program', args=(self.event.pk,)),
        )
        block = ProgramBlock.objects.get(event=self.event)
        self.assertIsNone(block.team)
        self.assertEqual(block.created_by, self.staff)
        self.assertIn('<p>Fælles start</p>', str(block.content.html))

    def test_block_can_be_created_without_content(self):
        self.client.force_login(self.staff)
        payload = self.post_payload()
        payload['content'] = ''
        response = self.client.post(
            reverse('organization_ProgramBlock_create', args=(self.event.pk,)),
            payload,
        )

        self.assertRedirects(
            response,
            reverse('organization_Event_program', args=(self.event.pk,)),
        )
        block = ProgramBlock.objects.get(event=self.event)
        self.assertEqual(block.content.doc.get('type'), 'doc')

    def test_volunteer_cannot_create_framework_block(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('organization_ProgramBlock_create', args=(self.event.pk,)),
            self.post_payload(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProgramBlock.objects.exists())

    def test_team_member_can_create_own_team_block(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('organization_ProgramBlock_create', args=(self.event.pk,)),
            self.post_payload(
                scope=str(self.team_a.pk),
                team=str(self.team_a.pk),
                title='Sjak møde',
                responsible=[str(self.alice.pk)],
            ),
        )

        self.assertRedirects(
            response,
            f"{reverse('organization_Event_program', args=(self.event.pk,))}"
            f"?team={self.team_a.pk}",
        )
        block = ProgramBlock.objects.get(event=self.event)
        self.assertEqual(block.team, self.team_a)
        self.assertListEqual(list(block.responsible.all()), [self.alice])

    def test_outsider_cannot_create_team_block(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse('organization_ProgramBlock_create', args=(self.event.pk,)),
            self.post_payload(
                scope=str(self.team_a.pk),
                team=str(self.team_a.pk),
            ),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProgramBlock.objects.exists())

    def test_team_member_can_edit_own_block_but_not_another_teams(self):
        own_block = self.create_block(team=self.team_a, title='Eget')
        other_block = self.create_block(team=self.team_b, title='Andet')

        self.client.force_login(self.alice)
        response = self.client.post(
            reverse(
                'organization_ProgramBlock_update',
                args=(self.event.pk, own_block.pk),
            ),
            self.post_payload(
                scope=str(self.team_a.pk),
                team=str(self.team_a.pk),
                title='Eget (rettet)',
            ),
        )
        self.assertRedirects(
            response,
            f"{reverse('organization_Event_program', args=(self.event.pk,))}"
            f"?team={self.team_a.pk}",
        )
        own_block.refresh_from_db()
        self.assertEqual(own_block.title, 'Eget (rettet)')

        response = self.client.post(
            reverse(
                'organization_ProgramBlock_update',
                args=(self.event.pk, other_block.pk),
            ),
            self.post_payload(scope=str(self.team_b.pk), team=str(self.team_b.pk)),
        )
        self.assertEqual(response.status_code, 403)


class ProgramValidationTests(ProgramTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)
        self.url = reverse('organization_ProgramBlock_create', args=(self.event.pk,))

    def test_block_saved_without_content_gets_an_empty_document(self):
        block = self.create_block(title='Ingen indhold')
        block.refresh_from_db()

        self.assertEqual(block.content.doc.get('type'), 'doc')

    def test_end_time_must_be_after_start_time(self):
        response = self.client.post(
            self.url,
            self.post_payload(start_time='19:00', end_time='18:00'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sluttiden skal være efter starttiden')
        self.assertFalse(ProgramBlock.objects.exists())

    def test_day_must_lie_within_the_event(self):
        response = self.client.post(
            self.url,
            self.post_payload(day=(self.event.end_date + timedelta(days=1)).isoformat()),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dagen skal ligge inden for eventets periode')
        self.assertFalse(ProgramBlock.objects.exists())


class ProgramViewTests(ProgramTestBase):
    def test_program_page_renders_framework_and_team_blocks(self):
        self.create_block(title='Fælles morgenmad')
        self.create_block(team=self.team_a, title='Sjak opgave', start_time=time(10, 0), end_time=time(11, 0))
        self.client.force_login(self.alice)

        response = self.client.get(
            reverse('organization_Event_program', args=(self.event.pk,)),
            {'team': self.team_a.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fælles morgenmad')
        self.assertContains(response, 'Sjak opgave')
        self.assertContains(response, 'program-block--framework')
        self.assertContains(response, 'Stiplet kant = fælles rammeprogram')
        self.assertContains(response, 'data-program-calendar')
        self.assertContains(response, 'data-program-day')
        self.assertContains(response, 'id="program-block-data"')
        self.assertContains(response, 'program-block__title')
        self.assertContains(response, 'form="programBlockForm"')

    def test_block_geometry_uses_non_localized_decimals(self):
        # ``da-dk`` localizes floats to "12,5", which is invalid CSS. The view
        # therefore builds the style string with dot decimals.
        self.create_block(start_time=time(8, 15), end_time=time(9, 45))
        self.client.force_login(self.alice)

        response = self.client.get(
            reverse('organization_Event_program', args=(self.event.pk,))
        )

        self.assertContains(
            response,
            'style="top: 12.500%; height: 8.333%; '
            'left: 0.000%; width: 100.000%;"',
        )

    def test_team_member_can_view_another_teams_program_read_only(self):
        self.create_block(team=self.team_b, title='Tekniks plan')
        self.client.force_login(self.alice)

        response = self.client.get(
            reverse('organization_Event_program', args=(self.event.pk,)),
            {'team': self.team_b.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tekniks plan')
        self.assertContains(response, 'data-can-create="0"')

    def test_all_teams_overview_shows_every_team(self):
        self.create_block(title='Fælles')
        self.create_block(team=self.team_a, title='Sjak')
        self.create_block(team=self.team_b, title='Teknik')
        self.client.force_login(self.alice)

        response = self.client.get(
            reverse('organization_Event_program', args=(self.event.pk,)),
            {'team': 'all'},
        )

        self.assertEqual(response.status_code, 200)
        for title in ('Fælles', 'Sjak', 'Teknik'):
            self.assertContains(response, title)

    def test_program_event_list(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('organization_Program_event_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.name)

    def test_admin_pages_render(self):
        block = self.create_block()
        self.client.force_login(self.staff)

        for url in (
            reverse('admin:organization_event_change', args=(self.event.pk,)),
            reverse('admin:organization_programblock_changelist'),
            reverse('admin:organization_programblock_change', args=(block.pk,)),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class ProgramHistoryTests(ProgramTestBase):
    def test_base_history_is_staff_only_and_records_edits(self):
        block = self.create_block(title='Før')
        self.client.force_login(self.staff)
        self.client.post(
            reverse(
                'organization_ProgramBlock_update',
                args=(self.event.pk, block.pk),
            ),
            self.post_payload(title='Efter'),
        )

        self.assertEqual(
            HistoricalProgramBlock.objects.filter(
                event_id=self.event.pk, team__isnull=True
            ).count(),
            2,
        )
        response = self.client.get(
            reverse('organization_Event_program_history', args=(self.event.pk,))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Efter')

        self.client.force_login(self.alice)
        response = self.client.get(
            reverse('organization_Event_program_history', args=(self.event.pk,))
        )
        self.assertEqual(response.status_code, 403)

    def test_team_history_is_visible_to_team_members(self):
        block = self.create_block(team=self.team_a, title='Sjak-blok')
        block.save()
        url = reverse(
            'organization_Event_program_team_history',
            args=(self.event.pk, self.team_a.pk),
        )

        self.client.force_login(self.alice)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sjak-blok')

        self.client.force_login(self.bob)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_delete_is_recorded_in_history(self):
        block = self.create_block(team=self.team_a, title='Slettes')
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse(
                'organization_ProgramBlock_delete',
                args=(self.event.pk, block.pk),
            ),
            {'scope': str(self.team_a.pk)},
        )

        self.assertRedirects(
            response,
            f"{reverse('organization_Event_program', args=(self.event.pk,))}"
            f"?team={self.team_a.pk}",
        )
        self.assertFalse(ProgramBlock.objects.exists())
        self.assertTrue(
            HistoricalProgramBlock.objects.filter(
                event_id=self.event.pk, team_id=self.team_a.pk, history_type='-'
            ).exists()
        )


class ProgramExportTests(ProgramTestBase):
    def export_url(self):
        return reverse(
            'organization_Event_program_export', args=(self.event.pk,)
        )

    def get_export(self, scope='base'):
        return self.client.get(self.export_url(), {'team': scope})

    def parse_workbook(self, response):
        workbook = load_workbook(BytesIO(response.content))
        worksheet = workbook['Rammeprogram']
        cells = {}
        for row in worksheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cells.setdefault(cell.value, cell)
        return workbook, worksheet, cells

    def all_text(self, worksheet):
        return ' '.join(
            str(cell.value)
            for row in worksheet.iter_rows()
            for cell in row
            if cell.value is not None
        )

    def test_export_returns_xlsx_with_layout_and_legend(self):
        self.create_block(title='Fælles morgenmad')
        self.create_block(
            team=self.team_a,
            title='Sjak opgave',
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        self.client.force_login(self.alice)

        response = self.get_export(self.team_a.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('.xlsx', response['Content-Disposition'])
        self.assertEqual(response.content[:2], b'PK')

        _, worksheet, cells = self.parse_workbook(response)
        self.assertIn('Rammeprogram - SKS E26', cells)
        self.assertIn('Fælles morgenmad', cells)
        self.assertIn('Sjak opgave', cells)
        self.assertIn('Sjak - teamprogram (inkl. fælles program)', self.all_text(worksheet))
        self.assertRegex(
            self.all_text(worksheet),
            r'Eksporteret \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}',
        )

        # A one-hour block covers two 30-minute slots and is merged vertically.
        block_cell = cells['Fælles morgenmad']
        self.assertTrue(
            any(block_cell.coordinate in merged for merged in worksheet.merged_cells.ranges)
        )

        # Time bars on the left and merged date headers.
        self.assertEqual(worksheet['A4'].value, '06.00')
        self.assertTrue(
            any('A4' in merged for merged in worksheet.merged_cells.ranges)
        )
        self.assertIn('Fredag', worksheet['B3'].value)

        # Category colours and the legend.
        self.assertIn('FF733C', block_cell.fill.fgColor.rgb)
        for label in (
            'Fast program',
            'Anbefaling',
            'Plads til eget program',
            'Forberedelse',
            'Fælles program (stiplet kant)',
        ):
            self.assertIn(label, cells)

    def test_export_omits_block_content(self):
        block = self.create_block(title='Kun titel')
        block.content = {
            'doc': {
                'type': 'doc',
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [{'type': 'text', 'text': 'Hemmelig tekst'}],
                    }
                ],
            },
            'html': '<p>Hemmelig tekst</p>',
        }
        block.save()
        self.client.force_login(self.alice)

        response = self.get_export('base')

        _, worksheet, cells = self.parse_workbook(response)
        self.assertIn('Kun titel', cells)
        self.assertNotIn('Hemmelig tekst', self.all_text(worksheet))

    def test_all_teams_export_prefixes_team_names(self):
        self.create_block(title='Fælles')
        self.create_block(team=self.team_a, title='Sjak opgave')
        self.create_block(team=self.team_b, title='Teknik opgave')
        self.client.force_login(self.alice)

        response = self.get_export('all')

        _, _, cells = self.parse_workbook(response)
        self.assertIn('Sjak: Sjak opgave', cells)
        self.assertIn('Tek: Teknik opgave', cells)
        self.assertIn('Fælles', cells)

    def test_export_requires_login(self):
        response = self.client.get(self.export_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/', response['Location'])
