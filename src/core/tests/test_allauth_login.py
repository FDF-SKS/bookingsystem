from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organization.adapters import AccountAdapter
from organization.models import Team, TeamMembership

User = get_user_model()


class AllauthLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='old_name', email='Anna@Example.com', password='pw-12345-xyz',
            first_name='Anna', last_name='A',
        )

    def test_login_with_email_case_insensitive(self):
        response = self.client.post(
            reverse('account_login'), {'login': 'anna@example.com', 'password': 'pw-12345-xyz'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_with_username_fails(self):
        self.client.post(reverse('account_login'), {'login': 'old_name', 'password': 'pw-12345-xyz'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_password_fails(self):
        self.client.post(reverse('account_login'), {'login': 'anna@example.com', 'password': 'nope'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_email_change_syncs_email_address(self):
        self.user.email = 'Anna.New@Example.com'
        self.user.save()
        self.assertEqual(
            list(EmailAddress.objects.filter(user=self.user).values_list('email', 'primary')),
            [('anna.new@example.com', True)],
        )

    def test_old_verified_alias_removed_on_email_change(self):
        # A verified secondary alias must not linger as a login identity.
        EmailAddress.objects.create(
            user=self.user, email='old-alias@example.com', verified=True, primary=False
        )

        self.user.email = 'Anna.Changed@Example.com'
        self.user.save()

        aliases = EmailAddress.objects.filter(user=self.user)
        self.assertEqual(aliases.count(), 1)
        address = aliases.get()
        self.assertEqual(address.email, 'anna.changed@example.com')
        self.assertTrue(address.primary)
        self.assertTrue(address.verified)

    def test_legacy_urls_redirect(self):
        self.assertRedirects(
            self.client.get(reverse('login_user')), reverse('account_login'), fetch_redirect_response=False
        )
        self.assertRedirects(
            self.client.get(reverse('register_user')), reverse('account_signup'), fetch_redirect_response=False
        )

    def test_login_by_code(self):
        with mock.patch.object(AccountAdapter, 'send_mail') as send_mail:
            response = self.client.post(reverse('account_request_login_code'), {'email': 'anna@example.com'})
        self.assertEqual(response.status_code, 302)
        send_mail.assert_called_once()
        code = send_mail.call_args.args[2]['code']

        self.client.post(reverse('account_confirm_login_code'), {'code': 'WRONG1'})
        self.assertNotIn('_auth_user_id', self.client.session)

        self.client.post(reverse('account_confirm_login_code'), {'code': code})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_unknown_email_code_request_sends_no_login_code(self):
        with mock.patch.object(AccountAdapter, 'send_mail') as send_mail:
            self.client.post(reverse('account_request_login_code'), {'email': 'nobody@example.com'})
        for call in send_mail.call_args_list:
            self.assertNotIn('code', call.args[2])


class AllauthSignupTests(TestCase):
    def test_signup_creates_inactive_user_in_unassigned_team(self):
        team = Team.objects.create(name='Unassigned users')
        response = self.client.post(reverse('account_signup'), {
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'Person',
            'password1': 'Str0ng-pass-word',
            'password2': 'Str0ng-pass-word',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.is_active)
        self.assertTrue(user.username)
        self.assertTrue(TeamMembership.objects.filter(team=team, member=user).exists())
        # An inactive user must not be signed in before an admin approves them.
        self.assertNotIn('_auth_user_id', self.client.session)


class PasskeyTemplateTests(TestCase):
    def test_login_page_renders_passkey_form(self):
        response = self.client.get(reverse('account_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="passkey_login"')
        self.assertContains(response, 'id="mfa_login"')
        self.assertContains(response, 'mfa/js/webauthn.js')
        self.assertNotContains(response, '<bs_icon')

    def test_mfa_management_uses_project_layout(self):
        user = User.objects.create_user(
            username='mfa-user', email='mfa@example.com', password='pw-12345-xyz',
            first_name='Mfa', last_name='User',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('mfa_index'))
        self.assertEqual(response.status_code, 200)
        # Rendered inside the project chrome rather than allauth's bare layout.
        self.assertContains(response, 'Det nye booking system')
        self.assertContains(response, 'card shadow-sm')
        self.assertNotContains(response, '<bs_icon')


class EmailAuthenticationTests(TestCase):
    """The user model authenticates with e-mail rather than username."""

    PASSWORD = 'pw-12345-xyz'

    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_model_backend_authenticates_by_email_case_insensitively(self):
        from django.contrib.auth import authenticate

        User.objects.create_user(
            username='legacy-name', email='Case@Test.com', password=self.PASSWORD,
            first_name='Case', last_name='Test',
        )

        self.assertTrue(authenticate(username='case@test.com', password=self.PASSWORD))
        self.assertTrue(authenticate(username='CASE@TEST.COM', password=self.PASSWORD))
        self.assertFalse(authenticate(username='legacy-name', password=self.PASSWORD))
        self.assertFalse(authenticate(username='case@test.com', password='wrong'))

    def test_django_admin_login_accepts_email(self):
        User.objects.create_superuser(
            username='admin-user', email='admin@example.com', password=self.PASSWORD,
            first_name='Admin', last_name='User',
        )

        response = self.client.post(
            reverse('admin:login'),
            {'username': 'admin@example.com', 'password': self.PASSWORD},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)


class ProfileSecurityLinkTests(TestCase):
    def test_own_profile_links_to_security_settings(self):
        user = User.objects.create_user(
            username='profile-user', email='profile@example.com', password='pw-12345-xyz',
            first_name='Profile', last_name='User',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('organization_Volunteer_detail', args=[user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'To-faktor-godkendelse')
        self.assertContains(response, 'Administrer')

    def test_other_users_profile_does_not_show_security_settings(self):
        owner = User.objects.create_user(
            username='profile-owner', email='owner@example.com', password='pw-12345-xyz',
            first_name='Owner', last_name='User',
        )
        viewer = User.objects.create_user(
            username='profile-viewer', email='viewer@example.com', password='pw-12345-xyz',
            first_name='Viewer', last_name='User',
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse('organization_Volunteer_detail', args=[owner.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'To-faktor-godkendelse')
