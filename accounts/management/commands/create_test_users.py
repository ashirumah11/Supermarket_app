"""
Management command: create_test_users

Creates the three canonical StockFlow test accounts specified in the
project documentation. Designed for development and local testing ONLY.

Usage:
    python manage.py create_test_users

WARNING: This command creates users with development-only passwords.
         Do NOT run in production. Do NOT commit real secrets.
         Passwords are hardcoded here ONLY because they are test-only.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserRole

User = get_user_model()

# Development-only test credentials (NOT for production use)
TEST_USERS = [
    {
        'first_name': 'John',
        'last_name': 'Kamau',
        'email': 'john.admin@stockflow.test',
        'username': 'john_kamau',
        'password': 'AdminPass123!',
        'role': UserRole.ADMIN,
        'is_staff': True,
        'is_superuser': True,
        'phone': '+254 700 001 001',
    },
    {
        'first_name': 'Mary',
        'last_name': 'Wanjiku',
        'email': 'mary.manager@stockflow.test',
        'username': 'mary_wanjiku',
        'password': 'ManagerPass123!',
        'role': UserRole.MANAGER,
        'is_staff': True,
        'is_superuser': False,
        'phone': '+254 700 002 002',
    },
    {
        'first_name': 'Brian',
        'last_name': 'Otieno',
        'email': 'brian.staff@stockflow.test',
        'username': 'brian_otieno',
        'password': 'StaffPass123!',
        'role': UserRole.STAFF,
        'is_staff': False,
        'is_superuser': False,
        'phone': '+254 700 003 003',
    },
]


class Command(BaseCommand):
    help = (
        'Creates the three canonical StockFlow test users '
        '(John Kamau / Mary Wanjiku / Brian Otieno). '
        'Development use ONLY — do not run in production.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            default=False,
            help='Reset passwords on existing test accounts even if they already exist.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\n=== StockFlow Test User Setup ===\n'))

        for udata in TEST_USERS:
            user, created = User.objects.get_or_create(
                email=udata['email'],
                defaults={
                    'username': udata['username'],
                    'first_name': udata['first_name'],
                    'last_name': udata['last_name'],
                    'role': udata['role'],
                    'is_staff': udata['is_staff'],
                    'is_superuser': udata['is_superuser'],
                    'phone': udata['phone'],
                    'is_active': True,
                }
            )

            # Always sync role and flags in case they drifted
            user.role = udata['role']
            user.is_staff = udata['is_staff']
            user.is_superuser = udata['is_superuser']
            user.is_active = True

            if created or options['reset_passwords']:
                user.set_password(udata['password'])

            user.save()

            status = self.style.SUCCESS('Created') if created else self.style.WARNING('Already exists')
            self.stdout.write(
                f'  [{status}] {udata["first_name"]} {udata["last_name"]} '
                f'<{udata["email"]}> — Role: {user.get_role_display()}'
            )

        self.stdout.write('\n' + self.style.SUCCESS('Test users ready.'))
        self.stdout.write('-' * 60)
        self.stdout.write('  John Kamau   -> john.admin@stockflow.test   / AdminPass123!   (ADMIN)')
        self.stdout.write('  Mary Wanjiku -> mary.manager@stockflow.test / ManagerPass123! (MANAGER)')
        self.stdout.write('  Brian Otieno -> brian.staff@stockflow.test  / StaffPass123!   (STAFF)')
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.WARNING(
            '\n  [!] These are development-only accounts.\n'
            '    Do NOT run this command on a production server.\n'
        ))
