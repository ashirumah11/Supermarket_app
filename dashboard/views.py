from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import render
from inventory.models import Category, Product, Supplier
from stock.forms import StockInForm, StockOutForm
from stock.models import StockMovement

@login_required
def dashboard_view(request):
    shop = getattr(request.user, 'shop', None)
    products = Product.objects.filter(shop=shop) if shop else Product.objects.all()
    movements = StockMovement.objects.filter(shop=shop) if shop else StockMovement.objects.all()
    categories = Category.objects.filter(shop=shop) if shop else Category.objects.all()
    suppliers = Supplier.objects.filter(shop=shop) if shop else Supplier.objects.all()

    # Core KPI Metrics (all real database calculations)
    total_products = products.count()
    total_stock = products.aggregate(total=Sum('quantity'))['total'] or 0
    out_of_stock_count = products.filter(quantity=0).count()
    low_stock_count = products.filter(quantity__gt=0, quantity__lte=F('minimum_stock')).count()
    in_stock_count = products.filter(quantity__gt=F('minimum_stock')).count()

    # Stock valuation is financial information available only to managers and admins.
    inventory_val = None
    if request.user.is_manager_user:
        inventory_val = products.aggregate(
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
    recent_movements = movements.select_related('product', 'user').order_by('-created_at')[:8]

    # Attention Required: Products that are OUT_OF_STOCK or LOW_STOCK
    attention_products = products.filter(
        quantity__lte=F('minimum_stock')
    ).select_related('category', 'supplier').order_by('quantity')[:8]

    context = {
        'total_products': total_products,
        'total_stock': total_stock,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
        'in_stock_count': in_stock_count,
        'in_stock_pct': in_stock_pct,
        'low_stock_pct': low_stock_pct,
        'out_of_stock_pct': out_of_stock_pct,
        'recent_movements': recent_movements,
        'attention_products': attention_products,
        'categories_count': categories.count(),
        'suppliers_count': suppliers.count(),
        'stock_in_form': StockInForm(),
        'stock_out_form': StockOutForm(),
    }
    if request.user.is_manager_user:
        context['inventory_value'] = inventory_val
    return render(request, 'dashboard/dashboard.html', context)
