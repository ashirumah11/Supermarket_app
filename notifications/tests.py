from decimal import Decimal
from django.test import TestCase
from accounts.models import User, UserRole
from inventory.models import Product, StockStatus
from stock.models import StockMovementType
from stock.services import StockMovementService
from .models import Notification, NotificationType
from .services import NotificationService

class NotificationEngineTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='alert_admin',
            password='Password123!',
            role=UserRole.ADMIN
        )
        self.manager = User.objects.create_user(
            username='alert_manager',
            password='Password123!',
            role=UserRole.MANAGER
        )
        self.staff = User.objects.create_user(
            username='alert_staff',
            password='Password123!',
            role=UserRole.STAFF
        )
        # Product starting IN_STOCK (qty 20 > min 5)
        self.product = Product.objects.create(
            name='Test Milk',
            sku='TST-MLK-01',
            price=Decimal('60.00'),
            quantity=20,
            minimum_stock=5,
            maximum_stock=50
        )

    def test_transition_in_stock_to_low_stock_generates_notification(self):
        # Stock OUT 16 units -> 20 - 16 = 4 units (<= 5 min stock => LOW_STOCK)
        StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.OUT,
            quantity=16,
            user=self.staff,
            reason="Bulk customer purchase"
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_status, StockStatus.LOW_STOCK)

        # Check notifications created for Admin and Manager
        admin_notifs = Notification.objects.filter(user=self.admin, type=NotificationType.LOW_STOCK)
        manager_notifs = Notification.objects.filter(user=self.manager, type=NotificationType.LOW_STOCK)

        self.assertEqual(admin_notifs.count(), 1)
        self.assertEqual(manager_notifs.count(), 1)
        self.assertIn("LOW STOCK", admin_notifs.first().title)

    def test_transition_low_stock_to_out_of_stock_generates_notification(self):
        # First reduce to low stock
        StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.OUT,
            quantity=16,
            user=self.staff,
            reason="Bulk purchase"
        )
        # Now dispatch the remaining 4 units -> 0 units (OUT_OF_STOCK)
        StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.OUT,
            quantity=4,
            user=self.staff,
            reason="Final clearance sale"
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_status, StockStatus.OUT_OF_STOCK)

        admin_out_notifs = Notification.objects.filter(user=self.admin, type=NotificationType.OUT_OF_STOCK)
        self.assertEqual(admin_out_notifs.count(), 1)
        self.assertIn("OUT OF STOCK", admin_out_notifs.first().title)

    def test_restocking_does_not_create_low_or_out_alert(self):
        # Start at 0
        self.product.quantity = 0
        self.product.save()

        notifs_before = Notification.objects.count()
        # Restock 50 units
        StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.IN,
            quantity=50,
            user=self.admin,
            reason="Fresh warehouse restock"
        )
        notifs_after = Notification.objects.count()
        # No alert should be generated for healthy restocking
        self.assertEqual(notifs_before, notifs_after)

    def test_mark_as_read_and_unread_count(self):
        # Trigger an alert
        StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.OUT,
            quantity=18,
            user=self.staff,
            reason="Sale"
        )
        self.assertTrue(NotificationService.get_unread_count(self.admin) > 0)
        
        # Mark all read
        NotificationService.mark_all_as_read(self.admin)
        self.assertEqual(NotificationService.get_unread_count(self.admin), 0)
