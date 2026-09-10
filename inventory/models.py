from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum

class StockStatus(models.TextChoices):
    IN_STOCK = 'IN_STOCK', 'In Stock'
    LOW_STOCK = 'LOW_STOCK', 'Low Stock'
    OUT_OF_STOCK = 'OUT_OF_STOCK', 'Out of Stock'


class LocationType(models.TextChoices):
    STORE = 'STORE', 'Main Store / Sales Floor'
    STOCK_ROOM = 'STOCK_ROOM', 'Back Store / Stock Room'
    WAREHOUSE = 'WAREHOUSE', 'Warehouse Depot'
    BRANCH = 'BRANCH', 'Store Branch'
    DISTRIBUTION_CENTER = 'DISTRIBUTION_CENTER', 'Distribution Center'


class InventoryLocation(models.Model):
    shop = models.ForeignKey(
        'accounts.StoreSetting',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='locations',
        help_text="Shop or store organization this location belongs to"
    )
    name = models.CharField(max_length=100, help_text="e.g. Main Store, Back Store, Central Warehouse")
    code = models.CharField(max_length=20, db_index=True, help_text="Short identifier e.g. MAIN, BACK, WH1")
    location_type = models.CharField(
        max_length=30,
        choices=LocationType.choices,
        default=LocationType.STORE,
        help_text="Physical nature of this inventory location"
    )
    description = models.TextField(blank=True, help_text="Location details, purpose or notes")
    address = models.TextField(blank=True, help_text="Physical location or shelf section")
    is_active = models.BooleanField(default=True, help_text="Active locations can receive and dispatch stock")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Inventory Location'
        verbose_name_plural = 'Inventory Locations'
        unique_together = [('shop', 'code')]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def product_count(self):
        return self.stocks.count()

    @property
    def total_stock(self):
        return self.stocks.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def low_stock_count(self):
        return self.stocks.filter(quantity__gt=0, quantity__lte=F('minimum_stock')).count()

    @property
    def out_of_stock_count(self):
        return self.stocks.filter(quantity=0).count()

    @property
    def in_stock_count(self):
        return self.stocks.filter(quantity__gt=F('minimum_stock')).count()

    @property
    def total_valuation(self):
        return self.stocks.aggregate(
            val=Sum(F('quantity') * F('product__price'))
        )['val'] or Decimal('0.00')

    @property
    def type_badge_class(self):
        badges = {
            LocationType.STORE: 'bg-primary-subtle text-primary border border-primary-subtle',
            LocationType.STOCK_ROOM: 'bg-info-subtle text-info-emphasis border border-info-subtle',
            LocationType.WAREHOUSE: 'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
            LocationType.BRANCH: 'bg-success-subtle text-success border border-success-subtle',
            LocationType.DISTRIBUTION_CENTER: 'bg-dark-subtle text-dark border border-dark-subtle',
        }
        return badges.get(self.location_type, 'bg-secondary-subtle text-secondary')


class Category(models.Model):
    shop = models.ForeignKey(
        'accounts.StoreSetting',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories',
        help_text="Shop or store organization this category belongs to"
    )
    name = models.CharField(max_length=100, help_text="Category name")
    description = models.TextField(blank=True, help_text="Brief description of the category")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        unique_together = [('shop', 'name')]

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()


class Supplier(models.Model):
    shop = models.ForeignKey(
        'accounts.StoreSetting',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='suppliers',
        help_text="Shop or store organization this supplier belongs to"
    )
    name = models.CharField(max_length=150, help_text="Supplier business or individual name")
    phone = models.CharField(max_length=30, help_text="Primary phone contact")
    email = models.EmailField(blank=True, null=True, help_text="Contact email address")
    address = models.TextField(blank=True, help_text="Physical or postal address")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()


class Product(models.Model):
    shop = models.ForeignKey(
        'accounts.StoreSetting',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='products',
        help_text="Shop or store organization this product belongs to"
    )
    name = models.CharField(max_length=200, help_text="Product or item title")
    sku = models.CharField(max_length=50, db_index=True, help_text="Stock Keeping Unit code")
    description = models.TextField(blank=True, help_text="Detailed product description")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Product category"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Primary supplier"
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Unit selling price"
    )
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total in-stock inventory count (summed across all locations)"
    )
    minimum_stock = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Default low stock alert trigger threshold"
    )
    maximum_stock = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Default maximum capacity threshold"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        unique_together = [('shop', 'sku')]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def clean(self):
        super().clean()
        if self.maximum_stock is not None and self.minimum_stock is not None:
            if self.maximum_stock < self.minimum_stock:
                raise ValidationError({
                    'maximum_stock': "Maximum stock threshold must be greater than or equal to minimum stock threshold."
                })
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({
                'quantity': "Stock quantity cannot be negative."
            })

    def sync_total_quantity(self):
        """Synchronizes quantity field with the sum of all location stock quantities."""
        total = self.stocks.aggregate(total=Sum('quantity'))['total']
        if total is not None:
            self.quantity = total
            self.save(update_fields=['quantity', 'updated_at'])
        return self.quantity

    @property
    def total_stock(self):
        return self.quantity

    @property
    def stock_status(self):
        """Authoritative calculation of overall product stock status."""
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK
        elif self.quantity <= self.minimum_stock:
            return StockStatus.LOW_STOCK
        return StockStatus.IN_STOCK

    @property
    def stock_status_display(self):
        status_map = {
            StockStatus.OUT_OF_STOCK: 'Out of Stock',
            StockStatus.LOW_STOCK: 'Low Stock',
            StockStatus.IN_STOCK: 'In Stock',
        }
        return status_map.get(self.stock_status, 'Unknown')

    @property
    def status_badge_class(self):
        badges = {
            StockStatus.OUT_OF_STOCK: 'badge-out-of-stock',
            StockStatus.LOW_STOCK: 'badge-low-stock',
            StockStatus.IN_STOCK: 'badge-in-stock',
        }
        return badges.get(self.stock_status, 'badge-secondary')

    @property
    def status_bootstrap_color(self):
        colors = {
            StockStatus.OUT_OF_STOCK: 'danger',
            StockStatus.LOW_STOCK: 'warning',
            StockStatus.IN_STOCK: 'success',
        }
        return colors.get(self.stock_status, 'secondary')

    @property
    def total_value(self):
        return self.price * self.quantity

    @property
    def stock_percentage(self):
        if not self.maximum_stock or self.maximum_stock <= 0:
            return 0
        return min(100, int((self.quantity / self.maximum_stock) * 100))

    def get_stock_for_location(self, location):
        return self.stocks.filter(location=location).first()


class InventoryStock(models.Model):
    """
    Authoritative stock quantity of a specific Product at a specific physical Location.
    Enforces product + location uniqueness constraint.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stocks',
        help_text="Product item"
    )
    location = models.ForeignKey(
        InventoryLocation,
        on_delete=models.CASCADE,
        related_name='stocks',
        help_text="Physical inventory location"
    )
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Physical units in stock at this location"
    )
    minimum_stock = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Low stock alert trigger threshold for this location"
    )
    maximum_stock = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Maximum capacity threshold for this location"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['location__name', 'product__name']
        verbose_name = 'Inventory Stock'
        verbose_name_plural = 'Inventory Stocks'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'location'],
                name='unique_product_location'
            )
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.location.name}: {self.quantity} units"

    def clean(self):
        super().clean()
        if self.maximum_stock is not None and self.minimum_stock is not None:
            if self.maximum_stock < self.minimum_stock:
                raise ValidationError({
                    'maximum_stock': "Maximum stock must be greater than or equal to minimum stock."
                })
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({
                'quantity': "Location stock quantity cannot be negative."
            })

    @property
    def stock_status(self):
        """Authoritative calculation of stock status at this specific location."""
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK
        elif self.quantity <= self.minimum_stock:
            return StockStatus.LOW_STOCK
        return StockStatus.IN_STOCK

    @property
    def stock_status_display(self):
        status_map = {
            StockStatus.OUT_OF_STOCK: 'Out of Stock',
            StockStatus.LOW_STOCK: 'Low Stock',
            StockStatus.IN_STOCK: 'In Stock',
        }
        return status_map.get(self.stock_status, 'Unknown')

    @property
    def status_badge_class(self):
        badges = {
            StockStatus.OUT_OF_STOCK: 'badge-out-of-stock',
            StockStatus.LOW_STOCK: 'badge-low-stock',
            StockStatus.IN_STOCK: 'badge-in-stock',
        }
        return badges.get(self.stock_status, 'badge-secondary')

    @property
    def status_bootstrap_color(self):
        colors = {
            StockStatus.OUT_OF_STOCK: 'danger',
            StockStatus.LOW_STOCK: 'warning',
            StockStatus.IN_STOCK: 'success',
        }
        return colors.get(self.stock_status, 'secondary')

    @property
    def total_value(self):
        return self.product.price * self.quantity

    @property
    def stock_percentage(self):
        if not self.maximum_stock or self.maximum_stock <= 0:
            return 0
        return min(100, int((self.quantity / self.maximum_stock) * 100))
