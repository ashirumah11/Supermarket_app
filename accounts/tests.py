from django.test import TestCase, Client
from django.urls import reverse
from .models import User, UserRole

class AccountsAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='test_admin',
            password='Password123!',
            email='admin@test.com',
            role=UserRole.ADMIN
        )
        self.manager_user = User.objects.create_user(
            username='test_manager',
            password='Password123!',
            email='manager@test.com',
            role=UserRole.MANAGER
        )
        self.staff_user = User.objects.create_user(
            username='test_staff',
            password='Password123!',
            email='staff@test.com',
            role=UserRole.STAFF
        )

    def test_login_works(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_admin',
            'password': 'Password123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_invalid_login_fails(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_admin',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_unauthorized_user_cannot_access_dashboard(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(reverse('login') in response.url)

    def test_admin_can_access_user_management(self):
        self.client.login(username='test_admin', password='Password123!')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_access_user_management(self):
        self.client.login(username='test_staff', password='Password123!')
        response = self.client.get(reverse('user_list'))
        # Redirected with access restriction
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_manager_cannot_access_user_management(self):
        self.client.login(username='test_manager', password='Password123!')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))
