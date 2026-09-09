from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.models import User, UserRole
from inventory.models import Product, StockStatus
from .models import StockMovement, StockMovementType
from .services import StockMovementService

class StockMovementEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='stock_tester',
            password='Password123!',
            role=UserRole.MANAGER
        )
        self.product = Product.objects.create(
            name='Test Flour',
            sku='TST-FLR-01',
            price=Decimal('120.00'),
            quantity=20,
            minimum_stock=5,
            maximum_stock=100
        )

    def test_stock_in_increases_quantity_and_creates_movement(self):
        # Current = 20, IN = 10 -> New = 30
        movement, updated_product = StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.IN,
            quantity=10,
            user=self.user,
            reason="Supplier shipment receipt",
            reference="PO-1001"
        )
        self.assertEqual(updated_product.quantity, 30)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 30)

        self.assertEqual(movement.type, StockMovementType.IN)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.previous_quantity, 20)
        self.assertEqual(movement.new_quantity, 30)
        self.assertEqual(movement.user, self.user)
        self.assertEqual(movement.reference, "PO-1001")

    def test_stock_out_decreases_quantity(self):
        # Current = 20, OUT = 5 -> New = 15
        movement, updated_product = StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.OUT,
            quantity=5,
            user=self.user,
            reason="Customer sale dispatch"
        )
        self.assertEqual(updated_product.quantity, 15)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 15)
        self.assertEqual(movement.previous_quantity, 20)
        self.assertEqual(movement.new_quantity, 15)

    def test_stock_out_exceeding_available_stock_is_prevented(self):
        # Current = 20, Request OUT = 25 -> Must raise ValidationError
        with self.assertRaises(ValidationError) as context:
            StockMovementService.record_movement(
                product=self.product,
                movement_type=StockMovementType.OUT,
                quantity=25,
                user=self.user,
                reason="Excessive dispatch attempt"
            )
        self.assertIn("exceeds available inventory", str(context.exception))
        # Ensure quantity remains unchanged at 20
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 20)

    def test_stock_adjustment_updates_quantity(self):
        # Reconcile physical inventory from 20 to 18
        movement, updated_product = StockMovementService.record_movement(
            product=self.product,
            movement_type=StockMovementType.ADJUSTMENT,
            quantity=None,
            user=self.user,
            reason="Monthly physical stocktake correction",
            reference="AUDIT-2026-01",
            new_target_quantity=18
        )
        self.assertEqual(updated_product.quantity, 18)
        self.assertEqual(movement.previous_quantity, 20)
        self.assertEqual(movement.new_quantity, 18)
        self.assertEqual(movement.type, StockMovementType.ADJUSTMENT)

    def test_empty_reason_is_rejected(self):
        with self.assertRaises(ValidationError):
            StockMovementService.record_movement(
                product=self.product,
                movement_type=StockMovementType.IN,
                quantity=5,
                user=self.user,
                reason=""
            )


from inventory.models import InventoryLocation, InventoryStock
from .services import StockTransferService
from .models import StockTransfer

class StockTransferEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='transfer_tester',
            password='Password123!',
            role=UserRole.MANAGER
        )
        self.product = Product.objects.create(
            name='Test Maize Flour',
            sku='TST-MZ-01',
            price=Decimal('150.00'),
            quantity=50,
            minimum_stock=10,
            maximum_stock=200
        )
        self.loc_shelf = InventoryLocation.objects.create(
            name='Store Shelf A1',
            code='LOC-SH-A1',
            location_type='STORE_SHELF',
            is_active=True
        )
        self.loc_wh = InventoryLocation.objects.create(
            name='Back Warehouse',
            code='LOC-WH-02',
            location_type='WAREHOUSE',
            is_active=True
        )
        # Assign 30 units to shelf
        self.stock_shelf = InventoryStock.objects.create(
            product=self.product,
            location=self.loc_shelf,
            quantity=30,
            minimum_stock=5,
            maximum_stock=100
        )

    def test_successful_transfer_moves_stock_and_creates_records(self):
        transfer = StockTransferService.execute_transfer(
            product=self.product,
            source_location=self.loc_shelf,
            destination_location=self.loc_wh,
            quantity=10,
            user=self.user,
            reason="Replenish warehouse reserve",
            reference="TR-TEST-100"
        )
        self.assertIsNotNone(transfer.pk)
        self.assertTrue(transfer.receipt_number.startswith('TR-'))
        self.assertEqual(transfer.quantity, 10)

        # Source stock deducted from 30 to 20
        self.stock_shelf.refresh_from_db()
        self.assertEqual(self.stock_shelf.quantity, 20)

        # Destination stock created and has 10 units
        stock_wh = InventoryStock.objects.get(product=self.product, location=self.loc_wh)
        self.assertEqual(stock_wh.quantity, 10)

        # Check paired movements created
        self.assertEqual(StockMovement.objects.filter(transfer=transfer).count(), 2)

    def test_transfer_insufficient_stock_fails(self):
        with self.assertRaises(ValidationError) as ctx:
            StockTransferService.execute_transfer(
                product=self.product,
                source_location=self.loc_shelf,
                destination_location=self.loc_wh,
                quantity=40, # only 30 available
                user=self.user,
                reason="Excess transfer"
            )
        self.assertIn("Insufficient stock", str(ctx.exception))

    def test_transfer_same_location_fails(self):
        with self.assertRaises(ValidationError) as ctx:
            StockTransferService.execute_transfer(
                product=self.product,
                source_location=self.loc_shelf,
                destination_location=self.loc_shelf,
                quantity=5,
                user=self.user,
                reason="Same location transfer"
            )
        self.assertIn("Source and destination locations must be different", str(ctx.exception))
