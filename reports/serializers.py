from rest_framework import serializers
from stock.models import StockMovement


class StockMovementReportSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_category = serializers.CharField(source='product.category.name', default='—', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    receipt_number = serializers.CharField(read_only=True)
    badge_class = serializers.CharField(read_only=True)
    operator_username = serializers.CharField(source='user.username', default='System', read_only=True)
    operator_full_name = serializers.SerializerMethodField()
    operator_role = serializers.CharField(source='user.role', default='—', read_only=True)
    location_name = serializers.CharField(source='location.name', default='—', read_only=True)
    destination_location_name = serializers.CharField(source='destination_location.name', default='—', read_only=True)
    created_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'receipt_number',
            'product',
            'product_name',
            'product_sku',
            'product_category',
            'type',
            'type_display',
            'badge_class',
            'quantity',
            'previous_quantity',
            'new_quantity',
            'reason',
            'reference',
            'operator_username',
            'operator_full_name',
            'operator_role',
            'location_name',
            'destination_location_name',
            'created_at',
            'created_at_formatted',
        ]

    def get_operator_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System Operator'

    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
