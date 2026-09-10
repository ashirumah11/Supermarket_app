from django.core.exceptions import ValidationError
from django.db import transaction
from inventory.models import InventoryLocation, InventoryStock, Product
from notifications.services import NotificationService
from .models import StockMovement, StockMovementType, StockTransfer

class StockMovementService:
    @staticmethod
    def record_movement(product, movement_type, quantity, user, reason, reference='', new_target_quantity=None, location=None):
        """
        Atomically updates product quantity and creates an audit movement record.
        Strictly prevents negative inventory and triggers transition notifications.
        """
        if not reason or not reason.strip():
            raise ValidationError("A clear operational reason is required for every stock operation.")
        if location and product.shop_id and location.shop_id != product.shop_id:
            raise ValidationError("The selected location does not belong to this product's shop.")

        with transaction.atomic():
            # Lock the product row to ensure atomic, concurrency-safe inventory calculations
            locked_product = Product.objects.select_for_update().get(pk=product.pk)
            previous_quantity = locked_product.quantity
            previous_status = locked_product.stock_status

            if movement_type == StockMovementType.IN:
                if quantity is None or quantity <= 0:
                    raise ValidationError("Stock IN quantity must be a positive integer greater than zero.")
                new_quantity = previous_quantity + quantity
                movement_delta = quantity

            elif movement_type == StockMovementType.OUT:
                if quantity is None or quantity <= 0:
                    raise ValidationError("Stock OUT quantity must be a positive integer greater than zero.")
                if quantity > previous_quantity:
                    raise ValidationError(
                        f"Stock OUT of {quantity} units exceeds available inventory. "
                        f"Currently in stock: {previous_quantity} units."
                    )
                new_quantity = previous_quantity - quantity
                movement_delta = quantity

            elif movement_type == StockMovementType.ADJUSTMENT:
                if new_target_quantity is not None:
                    if new_target_quantity < 0:
                        raise ValidationError("Stock quantity cannot be adjusted to a negative value.")
                    new_quantity = new_target_quantity
                    movement_delta = max(1, abs(new_quantity - previous_quantity))
                else:
                    if quantity is None:
                        raise ValidationError("Adjustment value must be specified.")
                    new_quantity = previous_quantity + quantity
                    if new_quantity < 0:
                        raise ValidationError("Adjustment would result in negative inventory.")
                    movement_delta = max(1, abs(quantity))
            else:
                raise ValidationError(f"Invalid movement type: {movement_type}")

            # Persist the updated stock count
            locked_product.quantity = new_quantity
            locked_product.save(update_fields=['quantity', 'updated_at'])

            # Determine new status for state transition alerts
            new_status = locked_product.stock_status

            # Record immutable audit movement
            shop = locked_product.shop or getattr(user, 'shop', None)
            movement = StockMovement.objects.create(
                product=locked_product,
                shop=shop,
                location=location,
                type=movement_type,
                quantity=movement_delta,
                previous_quantity=previous_quantity,
                new_quantity=new_quantity,
                reason=reason.strip(),
                reference=reference.strip() if reference else '',
                user=user
            )

            # Check and trigger notifications if crossing low or out-of-stock thresholds
            NotificationService.trigger_stock_alert(locked_product, previous_status, new_status)

            return movement, locked_product


class StockTransferService:
    @staticmethod
    def execute_transfer(product, source_location, destination_location, quantity, user, reason, reference=''):
        """
        Atomically transfers stock from one InventoryLocation to another.
        - Validates sufficient stock at source
        - Deducts from source InventoryStock
        - Adds to destination InventoryStock (creates record if needed)
        - Syncs the parent Product.quantity to sum of all locations
        - Creates StockTransfer and paired StockMovement audit records
        - Triggers notifications for status transitions
        """
        if not reason or not reason.strip():
            raise ValidationError("A transfer reason is required.")
        if quantity is None or quantity <= 0:
            raise ValidationError("Transfer quantity must be at least 1 unit.")
        if source_location == destination_location:
            raise ValidationError("Source and destination locations must be different.")

        with transaction.atomic():
            # Lock source inventory stock
            source_stock = (
                InventoryStock.objects
                .select_for_update()
                .filter(product=product, location=source_location)
                .first()
            )

            if not source_stock or source_stock.quantity < quantity:
                available = source_stock.quantity if source_stock else 0
                raise ValidationError(
                    f"Insufficient stock at '{source_location.name}'. "
                    f"Requested: {quantity}, Available: {available} units."
                )

            # Deduct from source
            source_prev_qty = source_stock.quantity
            source_stock.quantity -= quantity
            source_stock.save(update_fields=['quantity', 'updated_at'])

            # Add to destination (create InventoryStock if not yet assigned)
            dest_stock, _ = InventoryStock.objects.get_or_create(
                product=product,
                location=destination_location,
                defaults={
                    'quantity': 0,
                    'minimum_stock': product.minimum_stock,
                    'maximum_stock': product.maximum_stock,
                }
            )
            dest_stock = InventoryStock.objects.select_for_update().get(pk=dest_stock.pk)
            dest_prev_qty = dest_stock.quantity
            dest_stock.quantity += quantity
            dest_stock.save(update_fields=['quantity', 'updated_at'])

            # Sync product total quantity from all location stocks
            product.sync_total_quantity()
            product.refresh_from_db()

            # Get product status before/after for notification triggers
            previous_status = product.stock_status

            # Create StockTransfer record
            shop = product.shop or getattr(user, 'shop', None)
            transfer = StockTransfer.objects.create(
                product=product,
                shop=shop,
                source_location=source_location,
                destination_location=destination_location,
                quantity=quantity,
                reason=reason.strip(),
                reference=reference.strip() if reference else '',
                user=user
            )

            # Create paired StockMovement audit records
            StockMovement.objects.create(
                product=product,
                shop=shop,
                location=source_location,
                destination_location=destination_location,
                transfer=transfer,
                type=StockMovementType.TRANSFER_OUT,
                quantity=quantity,
                previous_quantity=source_prev_qty,
                new_quantity=source_stock.quantity,
                reason=f"Transfer OUT → {destination_location.name}: {reason.strip()}",
                reference=transfer.receipt_number,
                user=user
            )

            StockMovement.objects.create(
                product=product,
                shop=shop,
                location=destination_location,
                destination_location=None,
                transfer=transfer,
                type=StockMovementType.TRANSFER_IN,
                quantity=quantity,
                previous_quantity=dest_prev_qty,
                new_quantity=dest_stock.quantity,
                reason=f"Transfer IN ← {source_location.name}: {reason.strip()}",
                reference=transfer.receipt_number,
                user=user
            )

            # Check stock status change and trigger notifications
            new_status = product.stock_status
            NotificationService.trigger_stock_alert(product, previous_status, new_status)

            return transfer
