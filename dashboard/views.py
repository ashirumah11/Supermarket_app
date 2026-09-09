from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import render
from inventory.models import Category, Product, Supplier
from stock.forms import StockInForm, StockOutForm
from stock.models import StockMovement

@login_required
def dashboard_view(request):
    # Core KPI Metrics (all real database calculations)
    total_products = Product.objects.count()
    total_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0
    out_of_stock_count = Product.objects.filter(quantity=0).count()
    low_stock_count = Product.objects.filter(quantity__gt=0, quantity__lte=F('minimum_stock')).count()
    in_stock_count = Product.objects.filter(quantity__gt=F('minimum_stock')).count()

    # Total inventory valuation: sum(price * quantity)
    inventory_val = Product.objects.aggregate(
        total_val=Sum(F('price') * F('quantity'))
    )['total_val'] or Decimal('0.00')

    # Calculate inventory health percentages for visual bars
    if total_products > 0:
        in_stock_pct = round((in_stock_count / total_products) * 100, 1)
        low_stock_pct = round((low_stock_count / total_products) * 100, 1)
        out_of_stock_pct = round((out_of_stock_count / total_products) * 100, 1)
    else:
        in_stock_pct = 0
        low_stock_pct = 0
        out_of_stock_pct = 0

    # Recent stock activity (audit trail)
    recent_movements = StockMovement.objects.select_related('product', 'user').order_by('-created_at')[:8]

    # Attention Required: Products that are OUT_OF_STOCK or LOW_STOCK
    attention_products = Product.objects.filter(
        quantity__lte=F('minimum_stock')
    ).select_related('category', 'supplier').order_by('quantity')[:8]

    context = {
        'total_products': total_products,
        'total_stock': total_stock,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
        'in_stock_count': in_stock_count,
        'inventory_value': inventory_val,
        'in_stock_pct': in_stock_pct,
        'low_stock_pct': low_stock_pct,
        'out_of_stock_pct': out_of_stock_pct,
        'recent_movements': recent_movements,
        'attention_products': attention_products,
        'categories_count': Category.objects.count(),
        'suppliers_count': Supplier.objects.count(),
        'stock_in_form': StockInForm(),
        'stock_out_form': StockOutForm(),
    }
    return render(request, 'dashboard/dashboard.html', context)
