from django.conf import settings
from django.db import models

class NotificationType(models.TextChoices):
    LOW_STOCK = 'LOW_STOCK', 'Low Stock Alert'
    OUT_OF_STOCK = 'OUT_OF_STOCK', 'Out of Stock Alert'
    STOCK_MOVEMENT = 'STOCK_MOVEMENT', 'Stock Movement'
    SYSTEM = 'SYSTEM', 'System Notification'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="Recipient of this alert"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    location = models.ForeignKey(
        'inventory.InventoryLocation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Location where threshold alert occurred"
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.title} - {self.user.username} ({'Read' if self.is_read else 'Unread'})"

    @property
    def icon_class(self):
        icons = {
            NotificationType.LOW_STOCK: 'bi-exclamation-triangle-fill text-warning',
            NotificationType.OUT_OF_STOCK: 'bi-x-octagon-fill text-danger',
            NotificationType.STOCK_MOVEMENT: 'bi-arrow-left-right text-info',
            NotificationType.SYSTEM: 'bi-info-circle-fill text-primary',
        }
        return icons.get(self.type, 'bi-bell-fill text-secondary')

    @property
    def badge_class(self):
        badges = {
            NotificationType.LOW_STOCK: 'bg-warning text-dark',
            NotificationType.OUT_OF_STOCK: 'bg-danger text-white',
            NotificationType.STOCK_MOVEMENT: 'bg-info text-dark',
            NotificationType.SYSTEM: 'bg-primary text-white',
        }
        return badges.get(self.type, 'bg-secondary text-white')
