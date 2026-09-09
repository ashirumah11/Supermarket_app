from django.contrib import admin
from .models import StockMovement

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'type', 'quantity', 'previous_quantity', 'new_quantity', 'user', 'created_at')
    list_filter = ('type', 'created_at', 'user')
    search_fields = ('product__name', 'product__sku', 'reason', 'reference')
    readonly_fields = ('created_at',)
