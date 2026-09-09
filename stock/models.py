from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

class StockMovementType(models.TextChoices):
    IN = 'IN', 'Stock In'
    OUT = 'OUT', 'Stock Out'
    ADJUSTMENT = 'ADJUSTMENT', 'Stock Adjustment'
    TRANSFER = 'TRANSFER', 'Stock Transfer'
    TRANSFER_OUT = 'TRANSFER_OUT', 'Transfer Out'
    TRANSFER_IN = 'TRANSFER_IN', 'Transfer In'


class StockTransfer(models.Model):
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        related_name='transfers',
        help_text="Product being transferred between inventory locations"
    )
    source_location = models.ForeignKey(
        'inventory.InventoryLocation',
        on_delete=models.CASCADE,
        related_name='transfers_out',
        help_text="Location dispatching the inventory"
    )
    destination_location = models.ForeignKey(
        'inventory.InventoryLocation',
        on_delete=models.CASCADE,
        related_name='transfers_in',
        help_text="Location receiving the inventory"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of units transferred"
    )
    reason = models.CharField(max_length=255, help_text="Transfer justification or requisition note")
    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Requisition note or transfer order reference e.g. TR-2026-001"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transfers_authorized',
        help_text="User who authorized or performed the transfer"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Transfer'
        verbose_name_plural = 'Stock Transfers'

    def __str__(self):
        return f"Transfer #{self.id}: {self.quantity}x {self.product.name} ({self.source_location.code} -> {self.destination_location.code})"

    @property
    def receipt_number(self):
        return f"TR-{self.id:05d}"


class StockMovement(models.Model):
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        related_name='movements',
        help_text="Product affected by this inventory operation"
    )
    location = models.ForeignKey(
        'inventory.InventoryLocation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='movements',
        help_text="Specific physical inventory location affected"
    )
    destination_location = models.ForeignKey(
        'inventory.InventoryLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_movements',
        help_text="Destination location if this is a transfer movement"
    )
    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        help_text="Associated stock transfer if applicable"
    )
    type = models.CharField(
        max_length=20,
        choices=StockMovementType.choices,
        help_text="Nature of the stock operation"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Units added, removed, or changed"
    )
    previous_quantity = models.IntegerField(help_text="Inventory count before this operation")
    new_quantity = models.IntegerField(help_text="Inventory count after this operation")
    reason = models.CharField(max_length=255, help_text="Operational justification (e.g. Purchase order, Retail sale, Spoilage, Physical count)")
    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Document reference (e.g., PO-4920, INV-1029, AUDIT-2026)"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_movements',
        help_text="Staff or manager who authorized/executed this change"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        loc_str = f" @ {self.location.name}" if self.location else ""
        return f"{self.get_type_display()} - {self.product.name}{loc_str} ({self.quantity} units) by {self.user.username if self.user else 'System'}"

    @property
    def receipt_number(self):
        return f"SF-REC-{self.id:05d}"

    @property
    def badge_class(self):
        badges = {
            StockMovementType.IN: 'badge-stock-in',
            StockMovementType.OUT: 'badge-stock-out',
            StockMovementType.ADJUSTMENT: 'badge-stock-adjust',
            StockMovementType.TRANSFER: 'badge-stock-transfer',
            StockMovementType.TRANSFER_OUT: 'badge-stock-out',
            StockMovementType.TRANSFER_IN: 'badge-stock-in',
        }
        return badges.get(self.type, 'badge-secondary')

    @property
    def icon_class(self):
        icons = {
            StockMovementType.IN: 'bi-arrow-down-left text-success',
            StockMovementType.OUT: 'bi-arrow-up-right text-danger',
            StockMovementType.ADJUSTMENT: 'bi-sliders text-info',
            StockMovementType.TRANSFER: 'bi-arrow-left-right text-primary',
            StockMovementType.TRANSFER_OUT: 'bi-box-arrow-right text-warning',
            StockMovementType.TRANSFER_IN: 'bi-box-arrow-in-left text-success',
        }
        return icons.get(self.type, 'bi-record-circle text-muted')
