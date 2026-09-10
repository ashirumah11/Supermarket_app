"""
StockFlow accounts test suite.

Covers:
  - Registration (initial admin flow + blocking subsequent registrations)
  - Login / logout
  - Admin user creation (Manager & Staff)
  - Role-based access permissions
  - Password reset (forgot password → email → reset confirm)
  - User activation / deactivation
  - Change password
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_user(username, email, password, role, is_active=True, is_superuser=False):
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        role=role,
        is_active=is_active,
        is_staff=(role == UserRole.ADMIN or is_superuser),
        is_superuser=is_superuser,
    )
    return user


# ---------------------------------------------------------------------------
# 1. Registration Tests
# ---------------------------------------------------------------------------
class RegistrationTests(TestCase):
    """Test user registration flow."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def _post(self, data):
        return self.client.post(self.url, data, follow=True)

    # ---- GET / page accessible when no admin exists ----------
    def test_register_page_accessible_when_no_admin(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')

    # ---- First user registered becomes Admin ------------------
    def test_first_user_can_register_as_admin(self):
        resp = self._post({
            'first_name': 'John',
            'last_name': 'Kamau',
            'email': 'john.admin@test.stockflow',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
        })
        # After registration: account saved, redirected to login with registered=true (NOT auto-logged in)
        self.assertTrue(resp.redirect_chain)
        self.assertIn(reverse('login'), resp.redirect_chain[-1][0])
        self.assertTrue(User.objects.filter(email='john.admin@test.stockflow').exists())
        user = User.objects.get(email='john.admin@test.stockflow')
        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        # Password must be hashed (never plaintext)
        self.assertTrue(user.password.startswith('pbkdf2'))
        # Success message shown
        self.assertContains(resp, 'Account created successfully')

    # ---- After admin exists, new user can still register -----
    def test_subsequent_user_can_register_when_admin_exists(self):
        make_user('existing_admin', 'exist@test.stockflow', 'Pass123!', UserRole.ADMIN, is_superuser=True)
        # GET is accessible
        get_resp = self.client.get(self.url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Create Account')

        # POST creates a new user with STAFF role
        resp = self._post({
            'first_name': 'Jane',
            'last_name': 'Wanjiku',
            'email': 'jane.staff@test.stockflow',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
        })
        self.assertTrue(resp.redirect_chain)
        self.assertIn(reverse('login'), resp.redirect_chain[-1][0])
        self.assertTrue(User.objects.filter(email='jane.staff@test.stockflow').exists())
        new_user = User.objects.get(email='jane.staff@test.stockflow')
        self.assertEqual(new_user.role, UserRole.ADMIN)
        self.assertTrue(new_user.is_superuser)
        self.assertTrue(new_user.is_active)
        self.assertIsNotNone(new_user.shop)
        self.assertContains(resp, 'Account created successfully')

    # ---- Duplicate email rejected ----------------------------
    def test_duplicate_email_rejected(self):
        make_user('other_user', 'dup@test.com', 'Pass123!', UserRole.STAFF)
        resp = self._post({
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'dup@test.com',
            'password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already exists')

    # ---- Password mismatch rejected --------------------------
    def test_password_mismatch_rejected(self):
        resp = self._post({
            'first_name': 'John',
            'last_name': 'Kamau',
            'email': 'john2@test.stockflow',
            'password': 'SecurePass123!',
            'confirm_password': 'Different123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'do not match')

    # ---- Registered user can log in with username or email ---
    def test_registered_user_can_login_with_username_and_email(self):
        self._post({
            'first_name': 'John',
            'last_name': 'Kamau',
            'email': 'john.login@test.stockflow',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
        })
        user = User.objects.get(email='john.login@test.stockflow')
        
        # Test 1: login with username
        c1 = Client()
        resp1 = c1.post(reverse('login'), {
            'username': user.username,
            'password': 'SecurePass123!',
        })
        self.assertEqual(resp1.status_code, 302)
        self.assertRedirects(resp1, reverse('dashboard'))

        # Test 2: login with email
        c2 = Client()
        resp2 = c2.post(reverse('login'), {
            'username': 'john.login@test.stockflow',
            'password': 'SecurePass123!',
        })
        self.assertEqual(resp2.status_code, 302)
        self.assertRedirects(resp2, reverse('dashboard'))


# ---------------------------------------------------------------------------
# 2. Login Tests
# ---------------------------------------------------------------------------
class LoginTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_user('test_admin', 'admin@test.com', 'Password123!', UserRole.ADMIN, is_superuser=True)
        self.manager = make_user('test_manager', 'manager@test.com', 'Password123!', UserRole.MANAGER)
        self.staff = make_user('test_staff', 'staff@test.com', 'Password123!', UserRole.STAFF)
        self.inactive = make_user('inactive_user', 'inactive@test.com', 'Password123!', UserRole.STAFF, is_active=False)
        self.url = reverse('login')

    def test_valid_credentials_redirect_to_dashboard(self):
        resp = self.client.post(self.url, {
            'username': 'test_admin',
            'password': 'Password123!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('dashboard'))

    def test_invalid_credentials_show_error(self):
        resp = self.client.post(self.url, {
            'username': 'test_admin',
            'password': 'WrongPassword!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid')

    def test_inactive_user_cannot_login(self):
        resp = self.client.post(self.url, {
            'username': 'inactive_user',
            'password': 'Password123!',
        })
        self.assertEqual(resp.status_code, 200)
        # Should not redirect to dashboard
        self.assertNotEqual(resp.get('Location', ''), reverse('dashboard'))

    def test_unauthenticated_user_cannot_access_dashboard(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp.url)

    def test_logout_clears_session(self):
        self.client.login(username='test_admin', password='Password123!')
        self.client.get(reverse('logout'))
        # Dashboard should redirect to login after logout
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# 3. Admin User Creation Tests
# ---------------------------------------------------------------------------
class AdminUserCreationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_user('admin_creator', 'creator@test.com', 'Password123!', UserRole.ADMIN, is_superuser=True)
        self.client.login(username='admin_creator', password='Password123!')
        self.create_url = reverse('user_create')

    def _post(self, data):
        return self.client.post(self.create_url, data, follow=True)

    def test_admin_can_create_manager(self):
        resp = self._post({
            'username': 'new_manager',
            'first_name': 'Mary',
            'last_name': 'Wanjiku',
            'email': 'mary@test.com',
            'phone': '',
            'role': UserRole.MANAGER,
            'password': 'ManagerPass123!',
            'confirm_password': 'ManagerPass123!',
            'is_active': True,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(email='mary@test.com').exists())
        user = User.objects.get(email='mary@test.com')
        self.assertEqual(user.role, UserRole.MANAGER)

    def test_admin_can_create_staff(self):
        resp = self._post({
            'username': 'new_staff',
            'first_name': 'Brian',
            'last_name': 'Otieno',
            'email': 'brian@test.com',
            'phone': '',
            'role': UserRole.STAFF,
            'password': 'StaffPass123!',
            'confirm_password': 'StaffPass123!',
            'is_active': True,
        })
        self.assertTrue(User.objects.filter(email='brian@test.com').exists())
        user = User.objects.get(email='brian@test.com')
        self.assertEqual(user.role, UserRole.STAFF)

    def test_created_user_can_login(self):
        self._post({
            'username': 'login_test_staff',
            'first_name': 'Test',
            'last_name': 'Staff',
            'email': 'logintest@test.com',
            'phone': '',
            'role': UserRole.STAFF,
            'password': 'StaffPass123!',
            'confirm_password': 'StaffPass123!',
            'is_active': True,
        })
        # New client to test login independently
        c = Client()
        logged_in = c.login(username='login_test_staff', password='StaffPass123!')
        self.assertTrue(logged_in)

    def test_duplicate_email_rejected(self):
        make_user('existing', 'exists@test.com', 'Pass123!', UserRole.STAFF)
        resp = self._post({
            'username': 'dupe_user',
            'first_name': 'Dupe',
            'last_name': 'User',
            'email': 'exists@test.com',
            'phone': '',
            'role': UserRole.STAFF,
            'password': 'StaffPass123!',
            'confirm_password': 'StaffPass123!',
            'is_active': True,
        })
        self.assertContains(resp, 'already exists')
        # Only one user with that email
        self.assertEqual(User.objects.filter(email='exists@test.com').count(), 1)

    def test_admin_role_not_in_create_form_choices(self):
        resp = self.client.get(self.create_url)
        self.assertEqual(resp.status_code, 200)
        # ADMIN option should not appear in the role select of the create form
        content = resp.content.decode()
        # The form only offers MANAGER / STAFF choices
        form = resp.context['form']
        role_choices = [choice[0] for choice in form.fields['role'].choices]
        self.assertNotIn(UserRole.ADMIN, role_choices)
        self.assertIn(UserRole.MANAGER, role_choices)
        self.assertIn(UserRole.STAFF, role_choices)

    def test_created_user_password_is_hashed(self):
        self._post({
            'username': 'hashcheck_staff',
            'first_name': 'Hash',
            'last_name': 'Check',
            'email': 'hashcheck@test.com',
            'phone': '',
            'role': UserRole.STAFF,
            'password': 'StaffPass123!',
            'confirm_password': 'StaffPass123!',
            'is_active': True,
        })
        user = User.objects.get(email='hashcheck@test.com')
        self.assertTrue(user.password.startswith('pbkdf2'))
        self.assertNotIn('StaffPass123!', user.password)


# ---------------------------------------------------------------------------
# 4. Permission / Access Control Tests
# ---------------------------------------------------------------------------
class PermissionTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_user('perm_admin', 'padmin@test.com', 'Password123!', UserRole.ADMIN, is_superuser=True)
        self.manager = make_user('perm_manager', 'pmanager@test.com', 'Password123!', UserRole.MANAGER)
        self.staff = make_user('perm_staff', 'pstaff@test.com', 'Password123!', UserRole.STAFF)
        self.protected_urls = [
            reverse('user_list'),
            reverse('user_create'),
        ]

    def test_admin_can_access_user_management(self):
        self.client.login(username='perm_admin', password='Password123!')
        for url in self.protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Admin should access {url}")

    def test_manager_cannot_access_user_management(self):
        self.client.login(username='perm_manager', password='Password123!')
        for url in self.protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"Manager should be denied {url}")
            self.assertRedirects(resp, reverse('dashboard'))

    def test_staff_cannot_access_user_management(self):
        self.client.login(username='perm_staff', password='Password123!')
        for url in self.protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, f"Staff should be denied {url}")
            self.assertRedirects(resp, reverse('dashboard'))

    def test_anonymous_redirected_from_protected_pages(self):
        for url in self.protected_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse('login'), resp.url)

    def test_register_page_remains_accessible_when_admin_exists(self):
        """Register page must remain accessible to new users even when an admin exists."""
        resp = self.client.get(reverse('register'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create Account')

    def test_staff_cannot_toggle_user_status(self):
        """Staff cannot POST to toggle-status endpoint."""
        self.client.login(username='perm_staff', password='Password123!')
        url = reverse('user_toggle_status', kwargs={'pk': self.manager.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        # Manager should still be active — staff was denied
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)


# ---------------------------------------------------------------------------
# 5. Password Reset Tests
# ---------------------------------------------------------------------------
class PasswordResetTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user('reset_user', 'reset@test.com', 'OldPass123!', UserRole.STAFF)

    def test_forgot_password_page_loads(self):
        resp = self.client.get(reverse('forgot_password'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Send Reset Link')

    def test_submitting_known_email_sends_email_and_shows_success(self):
        resp = self.client.post(reverse('forgot_password'), {
            'email': 'reset@test.com',
        })
        self.assertEqual(resp.status_code, 200)
        # The console backend captures outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset@test.com', mail.outbox[0].to)
        self.assertIn('StockFlow', mail.outbox[0].subject)
        # Generic success message shown (email_sent=True)
        self.assertTrue(resp.context.get('email_sent'))

    def test_submitting_unknown_email_still_shows_success(self):
        """Must not reveal whether email exists."""
        resp = self.client.post(reverse('forgot_password'), {
            'email': 'nobody@test.com',
        })
        self.assertEqual(resp.status_code, 200)
        # No email sent for unknown address
        self.assertEqual(len(mail.outbox), 0)
        # But still flips to success state
        self.assertTrue(resp.context.get('email_sent'))

    def test_valid_reset_token_page_loads(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context.get('token_valid'))

    def test_invalid_reset_token_shows_error(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': 'invalid-token'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context.get('token_valid'))

    def test_valid_token_allows_password_change(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        resp = self.client.post(url, {
            'new_password1': 'NewSecurePass456!',
            'new_password2': 'NewSecurePass456!',
        }, follow=True)
        self.assertRedirects(resp, reverse('login'))
        # New password works
        c = Client()
        logged_in = c.login(username='reset_user', password='NewSecurePass456!')
        self.assertTrue(logged_in)

    def test_used_token_cannot_be_reused(self):
        """After a reset, the token must be invalidated."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})

        # First use — should work
        self.client.post(url, {
            'new_password1': 'NewSecurePass456!',
            'new_password2': 'NewSecurePass456!',
        })

        # Second use with same token — should be invalid
        resp = self.client.get(url)
        self.assertFalse(resp.context.get('token_valid'))


# ---------------------------------------------------------------------------
# 6. Deactivation Tests
# ---------------------------------------------------------------------------
class DeactivationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_user('deact_admin', 'deact_admin@test.com', 'Password123!', UserRole.ADMIN, is_superuser=True)
        self.target = make_user('target_user', 'target@test.com', 'Password123!', UserRole.STAFF)
        self.client.login(username='deact_admin', password='Password123!')

    def test_admin_can_deactivate_user(self):
        url = reverse('user_toggle_status', kwargs={'pk': self.target.pk})
        self.client.post(url)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_deactivated_user_cannot_login(self):
        self.target.is_active = False
        self.target.save()
        c = Client()
        logged_in = c.login(username='target_user', password='Password123!')
        self.assertFalse(logged_in)

    def test_admin_can_reactivate_user(self):
        self.target.is_active = False
        self.target.save()
        url = reverse('user_toggle_status', kwargs={'pk': self.target.pk})
        self.client.post(url)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_reactivated_user_can_login(self):
        self.target.is_active = False
        self.target.save()
        url = reverse('user_toggle_status', kwargs={'pk': self.target.pk})
        self.client.post(url)
        c = Client()
        logged_in = c.login(username='target_user', password='Password123!')
        self.assertTrue(logged_in)

    def test_admin_cannot_deactivate_self(self):
        url = reverse('user_toggle_status', kwargs={'pk': self.admin.pk})
        self.client.post(url)
        self.admin.refresh_from_db()
        # Admin should remain active (self-deactivation is blocked)
        self.assertTrue(self.admin.is_active)

    def test_historical_records_remain_intact_after_deactivation(self):
        """
        Users referenced in StockMovement records must remain queryable
        even when their account is deactivated. We verify that deactivating
        a user does NOT delete them from the database.
        """
        self.target.is_active = False
        self.target.save()
        # User record must still exist
        still_exists = User.objects.filter(pk=self.target.pk).exists()
        self.assertTrue(still_exists)
        # Retrieve and confirm key fields intact
        user_from_db = User.objects.get(pk=self.target.pk)
        self.assertEqual(user_from_db.email, 'target@test.com')
        self.assertEqual(user_from_db.username, 'target_user')
        self.assertFalse(user_from_db.is_active)  # Still deactivated
        self.assertEqual(user_from_db.pk, self.target.pk)  # Same record, not deleted


# ---------------------------------------------------------------------------
# 7. Change Password Tests
# ---------------------------------------------------------------------------
class ChangePasswordTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user('chgpass_user', 'chgpass@test.com', 'OldPass123!', UserRole.STAFF)
        self.client.login(username='chgpass_user', password='OldPass123!')
        self.url = reverse('change_password')

    def test_change_password_page_loads_for_authenticated(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_change_password_redirects_unauthenticated(self):
        c = Client()
        resp = c.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp.url)

    def test_valid_password_change_succeeds(self):
        resp = self.client.post(self.url, {
            'old_password': 'OldPass123!',
            'new_password1': 'NewSecurePass789!',
            'new_password2': 'NewSecurePass789!',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        # New password works
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass789!'))

    def test_wrong_current_password_is_rejected(self):
        resp = self.client.post(self.url, {
            'old_password': 'WrongOldPass!',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        # Password unchanged
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass123!'))
