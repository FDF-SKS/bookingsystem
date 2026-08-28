from django.test import TestCase
from django.urls import reverse

from .models import Hold, Loeb, PhysicalStation, Task, TaskSubmission
from organization.models import Event, Team, TeamMembership, Volunteer


class LoebModelTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team', short_name='TT')
        self.user = Volunteer.objects.create_user(
            username='testvolunteer',
            email='volunteer@example.com',
            password='secure-password-123',
            first_name='Test',
            last_name='Volunteer',
        )
        TeamMembership.objects.create(team=self.team, member=self.user, role='lead')
        self.event = Event.objects.create(
            name='Spring Event',
            start_date='2026-01-01',
            end_date='2026-01-10',
            deadline_sjak='2026-01-02',
            deadline_teknik='2026-01-03',
            deadline_mad='2026-01-04',
            deadline_aktivitetsteam='2026-01-05',
            deadline_lokaler='2026-01-06',
            deadline_sos='2026-01-07',
            deadline_foto='2026-01-08',
        )
        self.loeb = Loeb.objects.create(
            name='Test Løb',
            team=self.team,
            event=self.event,
            show_map=True,
            show_points=True,
        )
        self.station = PhysicalStation.objects.create(name='Main Station', qr_code='station-1')

    def test_loeb_creation(self):
        self.assertEqual(self.loeb.name, 'Test Løb')

    def test_task_submission_unique_constraint(self):
        hold = Hold.objects.create(loeb=self.loeb, name='Alpha Hold', pin_code='ALPHA1')
        task = Task.objects.create(loeb=self.loeb, title='Task One', task_type='physical', station=self.station)
        TaskSubmission.objects.create(hold=hold, task=task, state='UNLOCKED')

        duplicate = TaskSubmission.objects.filter(hold=hold, task=task).count()
        self.assertEqual(duplicate, 1)

    def test_published_task_defaults(self):
        task = Task.objects.create(loeb=self.loeb, title='Published Task', task_type='physical', station=self.station)
        self.assertFalse(task.is_published)

    def test_task_reordering(self):
        self.client.force_login(self.user)
        first = Task.objects.create(loeb=self.loeb, title='First Task', task_type='physical', station=self.station, order=1)
        second = Task.objects.create(loeb=self.loeb, title='Second Task', task_type='physical', station=self.station, order=2)

        response = self.client.get(reverse('Loeb_Task_move_up', args=[second.pk]))
        self.assertEqual(response.status_code, 302)
        second.refresh_from_db()
        self.assertEqual(second.order, 1)
        first.refresh_from_db()
        self.assertEqual(first.order, 2)

    def test_loeb_detail_dashboard_context(self):
        self.client.force_login(self.user)
        task = Task.objects.create(loeb=self.loeb, title='Pinned Task', task_type='virtual', station=self.station, order=1)
        hold = Hold.objects.create(loeb=self.loeb, name='Alpha Hold', pin_code='ALPHA1')
        TaskSubmission.objects.create(hold=hold, task=task, state='GRADED', points_awarded=25)

        response = self.client.get(reverse('Loeb_Loeb_detail', args=[self.loeb.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('task_progress', response.context)
        self.assertIn('holds', response.context)
        self.assertNotIn('todo_items', response.context)

    def test_hold_can_be_created_for_loeb(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('Loeb_Hold_create'),
            {
                'loeb': self.loeb.pk,
                'name': 'Bravo Hold',
                'pin_code': 'BRAVO1',
                'is_active': 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Hold.objects.filter(loeb=self.loeb, name='Bravo Hold', pin_code='BRAVO1').exists())

    def test_hold_pin_login_page_and_session_flow(self):
        self.client.force_login(self.user)
        hold = Hold.objects.create(loeb=self.loeb, name='Bravo Hold', pin_code='BRAVO1')
        task = Task.objects.create(loeb=self.loeb, title='Login Task', task_type='virtual', station=self.station, order=1)
        TaskSubmission.objects.create(hold=hold, task=task, state='UNLOCKED')

        response = self.client.get(reverse('Loeb_Hold_login', args=[self.loeb.pk]))
        self.assertEqual(response.status_code, 200)

        login_response = self.client.post(
            reverse('Loeb_Hold_login', args=[self.loeb.pk]),
            {'pin_code': 'BRAVO1'},
            follow=True,
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(self.client.session.get('loeb_hold_id'), hold.pk)
        self.assertContains(login_response, 'Bravo Hold')

    def test_station_qr_page_shows_task_for_matching_hold(self):
        self.client.force_login(self.user)
        hold = Hold.objects.create(loeb=self.loeb, name='Bravo Hold', pin_code='BRAVO1')
        task = Task.objects.create(
            loeb=self.loeb,
            title='Station Task',
            task_type='qr',
            station=self.station,
            input_mode='text',
            order=1,
        )
        session = self.client.session
        session['loeb_hold_id'] = hold.pk
        session['loeb_id'] = self.loeb.pk
        session.save()

        response = self.client.get(reverse('Loeb_Station_qr', kwargs={'qr_code': self.station.qr_code}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Station Task')
        self.assertContains(response, 'submit')

        post_response = self.client.post(
            reverse('Loeb_Station_qr', kwargs={'qr_code': self.station.qr_code}),
            {'submitted_answer': 'Svar fra holdet'},
            follow=True,
        )
        self.assertEqual(post_response.status_code, 200)
        submission = TaskSubmission.objects.get(hold=hold, task=task)
        self.assertEqual(submission.submitted_answer, 'Svar fra holdet')

    def test_station_qr_page_shows_no_post_message_for_unrelated_hold(self):
        self.client.force_login(self.user)
        other_loeb = Loeb.objects.create(
            name='Andet Løb',
            team=self.team,
            event=self.event,
            show_map=True,
            show_points=True,
        )
        other_hold = Hold.objects.create(loeb=other_loeb, name='Fejlt Hold', pin_code='FEJL1')
        session = self.client.session
        session['loeb_hold_id'] = other_hold.pk
        session['loeb_id'] = other_loeb.pk
        session.save()

        response = self.client.get(reverse('Loeb_Station_qr', kwargs={'qr_code': self.station.qr_code}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bare ærgeligt - ingen post her')

    def test_physical_station_auto_generates_qr_code_and_detail_url(self):
        self.client.force_login(self.user)
        station = PhysicalStation.objects.create(name='Auto QR Station')

        self.assertTrue(station.qr_code)
        self.assertEqual(station.get_absolute_url(), reverse('Loeb_PhysicalStation_detail', args=[station.pk]))

        response = self.client.get(station.get_absolute_url())
        self.assertEqual(response.status_code, 200)
