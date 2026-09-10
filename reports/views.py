import csv
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from accounts.decorators import manager_required
from inventory.models import Category, Product, StockStatus
from stock.models import StockMovement, StockMovementType

@login_required
@manager_required
def reports_view(request):
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    export = request.GET.get('export', '').strip()

    shop = getattr(request.user, 'shop', None)

    # Base querysets
    products = Product.objects.select_related('category', 'supplier')
    movements = StockMovement.objects.all()

    if shop:
        products = products.filter(shop=shop)
        movements = movements.filter(shop=shop)

    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)

    # Core Summary
    total_products = products.count()
    total_stock = products.aggregate(total=Sum('quantity'))['total'] or 0
    total_inventory_value = products.aggregate(val=Sum(F('price') * F('quantity')))['val'] or Decimal('0.00')
    out_of_stock_count = products.filter(quantity=0).count()
    low_stock_count = products.filter(quantity__gt=0, quantity__lte=F('minimum_stock')).count()
    in_stock_count = products.filter(quantity__gt=F('minimum_stock')).count()

    # Movement summary during period
    in_movements = movements.filter(type=StockMovementType.IN)
    out_movements = movements.filter(type=StockMovementType.OUT)
    adjust_movements = movements.filter(type=StockMovementType.ADJUSTMENT)

    movement_summary = {
        'in_count': in_movements.count(),
        'in_units': in_movements.aggregate(total=Sum('quantity'))['total'] or 0,
        'out_count': out_movements.count(),
        'out_units': out_movements.aggregate(total=Sum('quantity'))['total'] or 0,
        'adjust_count': adjust_movements.count(),
        'adjust_units': adjust_movements.aggregate(total=Sum('quantity'))['total'] or 0,
    }

    # Category breakdown
    categories_qs = Category.objects.all()
    if shop:
        categories_qs = categories_qs.filter(shop=shop)
    categories = categories_qs.annotate(
        total_products=Count('products'),
        total_units=Sum('products__quantity'),
        category_value=Sum(F('products__price') * F('products__quantity'))
    ).order_by('-category_value')

    # Top valued items
    top_valued_products = products.order_by('-price')[:8]

    # Handle CSV Export
    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="stockflow_inventory_report_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product Name', 'SKU', 'Category', 'Supplier', 'Unit Price', 'Quantity', 'Min Stock', 'Total Valuation', 'Stock Status'])

        for p in products:
            writer.writerow([
                p.name,
                p.sku,
                p.category.name if p.category else 'Uncategorized',
                p.supplier.name if p.supplier else 'None',
                f"{p.price:.2f}",
                p.quantity,
                p.minimum_stock,
                f"{p.total_value:.2f}",
                p.stock_status_display
            ])
        return response

    context = {
        'total_products': total_products,
        'total_stock': total_stock,
        'total_inventory_value': total_inventory_value,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
        'in_stock_count': in_stock_count,
        'movement_summary': movement_summary,
        'categories': categories,
        'top_valued_products': top_valued_products,
        'date_from': date_from,
        'date_to': date_to,
        'generated_at': timezone.now(),
    }
    return render(request, 'reports/reports.html', context)
