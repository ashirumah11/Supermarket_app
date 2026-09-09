from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Notification, NotificationType

User = get_user_model()

class NotificationService:
    @staticmethod
    def trigger_stock_alert(product, old_status, new_status):
        """
        Creates alerts for Admins and Managers when a product transitions into
        LOW_STOCK or OUT_OF_STOCK. Avoids spamming duplicate unread alerts.
        """
        from inventory.models import StockStatus

        if new_status not in [StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK]:
            return []

        if old_status == new_status:
            return []

        alert_type = (
            NotificationType.OUT_OF_STOCK
            if new_status == StockStatus.OUT_OF_STOCK
            else NotificationType.LOW_STOCK
        )

        if alert_type == NotificationType.OUT_OF_STOCK:
            title = f"OUT OF STOCK: {product.name}"
            message = (
                f"Product '{product.name}' (SKU: {product.sku}) is now depleted (0 units remaining). "
                f"Immediate supplier reorder is required."
            )
        else:
            title = f"LOW STOCK: {product.name}"
            message = (
                f"Product '{product.name}' (SKU: {product.sku}) has dropped to {product.quantity} units, "
                f"which is below or at the minimum threshold of {product.minimum_stock}."
            )

        # Notify active Admins and Managers
        recipients = User.objects.filter(
            is_active=True,
            role__in=['ADMIN', 'MANAGER']
        )

        notifications_created = []
        for user in recipients:
            # Check if an unread notification of this type already exists for this product to prevent duplicate spam
            duplicate_exists = Notification.objects.filter(
                user=user,
                product=product,
                type=alert_type,
                is_read=False,
                created_at__gte=timezone.now() - timedelta(hours=6)
            ).exists()

            if not duplicate_exists:
                notification = Notification.objects.create(
                    user=user,
                    product=product,
                    title=title,
                    message=message,
                    type=alert_type
                )
                notifications_created.append(notification)

        return notifications_created

    @staticmethod
    def mark_as_read(notification_id, user):
        return Notification.objects.filter(id=notification_id, user=user).update(is_read=True)

    @staticmethod
    def mark_all_as_read(user):
        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    @staticmethod
    def get_unread_count(user):
        if not user or not user.is_authenticated:
            return 0
        return Notification.objects.filter(user=user, is_read=False).count()
