from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from accounts.models import StoreSetting
from .models import Category, InventoryLocation, Product, StockStatus, Supplier
from .forms import ProductForm
from .views import _assign_product_to_location

class ProductCatalogTests(TestCase):
    def setUp(self):
        self.shop = StoreSetting.get_settings()
        self.category = Category.objects.create(name='Groceries', description='Dry goods', shop=self.shop)
        self.supplier = Supplier.objects.create(name='Test Supplier', phone='+254700000000', shop=self.shop)
        self.location = InventoryLocation.objects.create(
            name='Main Store', code='MAIN', shop=self.shop, is_active=True
        )

    def test_product_form_limits_locations_to_the_current_shop(self):
        other_shop = StoreSetting.objects.create(name='Other Shop')
        other_location = InventoryLocation.objects.create(
            name='Other Store', code='OTHER', shop=other_shop, is_active=True
        )

        form = ProductForm(shop=self.shop)

        self.assertIn(self.location, form.fields['location'].queryset)
        self.assertNotIn(other_location, form.fields['location'].queryset)

    def test_product_form_requires_location_for_opening_stock(self):
        form = ProductForm(data={
            'name': 'Opening Stock Item',
            'sku': 'OPENING-STOCK-01',
            'price': '50.00',
            'quantity': 10,
            'minimum_stock': 2,
            'maximum_stock': 20,
        }, shop=self.shop)

        self.assertFalse(form.is_valid())
        self.assertIn('location', form.errors)

    def test_assigning_location_adds_legacy_product_to_location_stock(self):
        product = Product.objects.create(
            name='Legacy Product', sku='LEGACY-LOCATION-01', shop=self.shop,
            price=Decimal('100.00'), quantity=12, minimum_stock=2, maximum_stock=20,
        )

        _assign_product_to_location(product, self.location, user=None)

        location_stock = product.stocks.get(location=self.location)
        self.assertEqual(location_stock.quantity, 12)

    def test_product_creation(self):
        product = Product.objects.create(
            name='Test Sugar',
            sku='TST-SUG-01',
            shop=self.shop,
            category=self.category,
            supplier=self.supplier,
            price=Decimal('150.00'),
            quantity=25,
            minimum_stock=5,
            maximum_stock=50
        )
        self.assertEqual(product.name, 'Test Sugar')
        self.assertEqual(product.sku, 'TST-SUG-01')
        self.assertEqual(product.quantity, 25)
        self.assertEqual(product.stock_status, StockStatus.IN_STOCK)

    def test_duplicate_sku_rejected_by_db(self):
        Product.objects.create(
            name='First Item',
            sku='DUPLICATE-SKU',
            shop=self.shop,
            price=Decimal('100.00'),
            quantity=10,
            minimum_stock=5,
            maximum_stock=50
        )
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name='Second Item',
                sku='DUPLICATE-SKU',
                shop=self.shop,
                price=Decimal('120.00'),
                quantity=10,
                minimum_stock=5,
                maximum_stock=50
            )

    def test_duplicate_sku_rejected_by_form(self):
        Product.objects.create(
            name='Existing Product',
            sku='SKU-EXISTING',
            price=Decimal('200.00'),
            quantity=5,
            minimum_stock=2,
            maximum_stock=20
        )
        form = ProductForm(data={
            'name': 'New Product Same SKU',
            'sku': 'SKU-EXISTING',
            'price': '250.00',
            'quantity': 10,
            'minimum_stock': 5,
            'maximum_stock': 50
        })
        self.assertFalse(form.is_valid())
        self.assertIn('sku', form.errors)

    def test_stock_status_calculation(self):
        # 1. OUT OF STOCK (quantity == 0)
        p1 = Product.objects.create(
            name='Item Zero',
            sku='SKU-ZERO',
            price=Decimal('10.00'),
            quantity=0,
            minimum_stock=5,
            maximum_stock=50
        )
        self.assertEqual(p1.stock_status, StockStatus.OUT_OF_STOCK)
        self.assertEqual(p1.stock_status_display, 'Out of Stock')

        # 2. LOW STOCK (quantity > 0 and quantity <= minimum_stock)
        p2 = Product.objects.create(
            name='Item Low',
            sku='SKU-LOW',
            price=Decimal('10.00'),
            quantity=5,
            minimum_stock=5,
            maximum_stock=50
        )
        self.assertEqual(p2.stock_status, StockStatus.LOW_STOCK)
        self.assertEqual(p2.stock_status_display, 'Low Stock')

        # 3. IN STOCK (quantity > minimum_stock)
        p3 = Product.objects.create(
            name='Item Healthy',
            sku='SKU-HEALTHY',
            price=Decimal('10.00'),
            quantity=6,
            minimum_stock=5,
            maximum_stock=50
        )
        self.assertEqual(p3.stock_status, StockStatus.IN_STOCK)
        self.assertEqual(p3.stock_status_display, 'In Stock')

    def test_maximum_stock_validation(self):
        # Max stock must be >= min stock
        form = ProductForm(data={
            'name': 'Invalid Thresholds',
            'sku': 'SKU-INV-THRESH',
            'price': '50.00',
            'quantity': 10,
            'minimum_stock': 20,
            'maximum_stock': 10 # lower than minimum!
        })
        self.assertFalse(form.is_valid())
        self.assertIn('maximum_stock', form.errors)
