import csv
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from accounts.decorators import manager_required
from accounts.models import StoreSetting, UserRole
from inventory.models import Category, Product, StockStatus
from stock.models import StockMovement, StockMovementType
from .pdf import ReportPdfGenerator
from .services import ReportPeriodOption, TransactionReportService

User = get_user_model()


# ==============================================================================
# 1. EXISTING REPORT: Executive Stock Valuation & Inventory Health (PRESERVED)
# ==============================================================================
@login_required
@manager_required
def reports_view(request):
    """
    Original executive inventory valuation report.
    PRESERVED INTACT without modifying existing contract or behavior.
    """
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
        'active_tab': 'valuation',
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


# ==============================================================================
# 2. EXTENSION: Comprehensive Transaction Reports & Audit View
# ==============================================================================
@login_required
@manager_required
def transaction_reports_view(request):
    """
    Extended transaction reporting dashboard.
    Supports filtering by:
    - Period (Today, Specific Date, This Week, Specific Week, This Month, Specific Month, This Year, Specific Year, Custom Range)
    - User (Admin, Manager, Staff, or specific operator)
    - Transaction Type (IN, OUT, ADJUSTMENT, TRANSFER, or ALL)
    - Product
    - Search Keyword
    """
    user = request.user
    shop = getattr(user, 'shop', None)

    # Role enforcement: Staff can only filter their own transactions
    user_id = request.GET.get('user', '').strip()
    if not user.is_manager_user:
        user_id = str(user.id)

    period = request.GET.get('period', ReportPeriodOption.TODAY).strip()
    specific_date = request.GET.get('specific_date', '').strip()
    specific_week = request.GET.get('specific_week', '').strip()
    specific_month = request.GET.get('specific_month', '').strip()
    specific_year = request.GET.get('specific_year', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    movement_type = request.GET.get('type', '').strip()
    product_id = request.GET.get('product', '').strip()
    search_query = request.GET.get('q', '').strip()

    # Query filtered transactions
    queryset, period_data = TransactionReportService.get_filtered_movements(
        shop=shop,
        period=period,
        specific_date=specific_date,
        specific_week=specific_week,
        specific_month=specific_month,
        specific_year=specific_year,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        movement_type=movement_type,
        product_id=product_id,
        search_query=search_query,
    )

    summary = TransactionReportService.calculate_summary(queryset, period_data)

    # Pagination for transaction ledger
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Filter dropdown options
    products_qs = Product.objects.filter(shop=shop).order_by('name') if shop else Product.objects.all().order_by('name')
    users_qs = User.objects.filter(shop=shop).order_by('username') if shop else User.objects.all().order_by('username')

    # Available years list for year selector
    current_year = timezone.now().year
    years_list = list(range(current_year, current_year - 5, -1))

    # Months list for month selector
    months_list = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    store = shop or StoreSetting.get_settings(user)

    context = {
        'active_tab': 'transactions',
        'period_options': ReportPeriodOption.CHOICES,
        'selected_period': period,
        'selected_date': specific_date,
        'selected_week': specific_week,
        'selected_month': specific_month or str(timezone.now().month),
        'selected_year': specific_year or str(current_year),
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'selected_user': user_id,
        'selected_type': movement_type,
        'selected_product': product_id,
        'selected_query': search_query,
        'period_data': period_data,
        'summary': summary,
        'transactions': page_obj,
        'page_obj': page_obj,
        'products': products_qs,
        'users': users_qs,
        'movement_types': StockMovementType.choices,
        'years_list': years_list,
        'months_list': months_list,
        'store': store,
        'now': timezone.now(),
    }
    return render(request, 'reports/transaction_reports.html', context)


# ==============================================================================
# 3. EXTENSION: Transaction Period Receipt / Document
# ==============================================================================
@login_required
@manager_required
def transaction_receipt_view(request):
    """
    Generates an official printable Stock Transaction Receipt summarizing
    all transactions matching the selected period and filters.
    """
    user = request.user
    shop = getattr(user, 'shop', None)

    user_id = request.GET.get('user', '').strip()
    if not user.is_manager_user:
        user_id = str(user.id)

    period = request.GET.get('period', ReportPeriodOption.TODAY).strip()
    specific_date = request.GET.get('specific_date', '').strip()
    specific_week = request.GET.get('specific_week', '').strip()
    specific_month = request.GET.get('specific_month', '').strip()
    specific_year = request.GET.get('specific_year', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    movement_type = request.GET.get('type', '').strip()
    product_id = request.GET.get('product', '').strip()

    queryset, period_data = TransactionReportService.get_filtered_movements(
        shop=shop,
        period=period,
        specific_date=specific_date,
        specific_week=specific_week,
        specific_month=specific_month,
        specific_year=specific_year,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        movement_type=movement_type,
        product_id=product_id,
    )

    summary = TransactionReportService.calculate_summary(queryset, period_data)
    store = shop or StoreSetting.get_settings(user)

    # For receipt document, fetch all movements in chronological order
    transactions = list(queryset.order_by('created_at'))

    context = {
        'store': store,
        'period_data': period_data,
        'summary': summary,
        'transactions': transactions,
        'generated_by': user.get_full_name() or user.username,
        'user_role': user.get_role_display(),
        'generated_at': timezone.now(),
        'period_options': ReportPeriodOption.CHOICES,
        'selected_period': period,
    }
    return render(request, 'reports/period_receipt.html', context)


# ==============================================================================
# 4. EXTENSION: Transaction Detail / Traceability API / View
# ==============================================================================
@login_required
def transaction_detail_modal_view(request, pk):
    """
    Renders an HTML snippet for modal or JSON for traceability audit.
    Shows who performed the movement, role, exact date/time, product, previous/new qty, and justification.
    """
    shop = getattr(request.user, 'shop', None)
    qs = StockMovement.objects.select_related(
        'product', 'product__category', 'user', 'location', 'destination_location', 'transfer'
    )
    if shop:
        movement = get_object_or_404(qs, pk=pk, shop=shop)
    else:
        movement = get_object_or_404(qs, pk=pk)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'id': movement.id,
            'receipt_number': movement.receipt_number,
            'product_name': movement.product.name,
            'product_sku': movement.product.sku,
            'type': movement.type,
            'type_display': movement.get_type_display(),
            'quantity': movement.quantity,
            'previous_quantity': movement.previous_quantity,
            'new_quantity': movement.new_quantity,
            'reason': movement.reason,
            'reference': movement.reference or '—',
            'user_name': movement.user.get_full_name() or movement.user.username if movement.user else 'System',
            'user_role': movement.user.get_role_display() if movement.user else '—',
            'date': movement.created_at.strftime('%d %B %Y'),
            'time': movement.created_at.strftime('%I:%M %p'),
            'location': movement.location.name if movement.location else '—',
        })

    return render(request, 'reports/transaction_detail_modal.html', {'movement': movement})


# ==============================================================================
# 5. EXTENSION: CSV & PDF Exports
# ==============================================================================
@login_required
@manager_required
def export_transactions_csv(request):
    """
    Exports filtered transaction records to a formatted CSV file.
    """
    shop = getattr(request.user, 'shop', None)
    period = request.GET.get('period', ReportPeriodOption.TODAY).strip()
    user_id = request.GET.get('user', '').strip()
    movement_type = request.GET.get('type', '').strip()
    product_id = request.GET.get('product', '').strip()

    queryset, period_data = TransactionReportService.get_filtered_movements(
        shop=shop,
        period=period,
        specific_date=request.GET.get('specific_date'),
        specific_week=request.GET.get('specific_week'),
        specific_month=request.GET.get('specific_month'),
        specific_year=request.GET.get('specific_year'),
        start_date=request.GET.get('start_date'),
        end_date=request.GET.get('end_date'),
        user_id=user_id,
        movement_type=movement_type,
        product_id=product_id,
        search_query=request.GET.get('q'),
    )

    filename = f"stockflow_transactions_{period}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Transaction ID', 'Receipt Number', 'Date', 'Time', 'Product Name', 'SKU',
        'Operation Type', 'Quantity', 'Previous Qty', 'New Qty', 'Reason',
        'Reference', 'Operator', 'Operator Role', 'Location'
    ])

    for m in queryset:
        writer.writerow([
            m.id,
            m.receipt_number,
            m.created_at.strftime('%Y-%m-%d'),
            m.created_at.strftime('%H:%M:%S'),
            m.product.name,
            m.product.sku,
            m.get_type_display(),
            m.quantity,
            m.previous_quantity,
            m.new_quantity,
            m.reason,
            m.reference or '',
            m.user.username if m.user else 'System',
            m.user.get_role_display() if m.user else 'System',
            m.location.name if m.location else 'Main Store',
        ])

    return response


@login_required
@manager_required
def export_transactions_pdf(request):
    """
    Exports filtered transaction report to a branded, professional PDF file.
    """
    user = request.user
    shop = getattr(user, 'shop', None)
    period = request.GET.get('period', ReportPeriodOption.TODAY).strip()

    queryset, period_data = TransactionReportService.get_filtered_movements(
        shop=shop,
        period=period,
        specific_date=request.GET.get('specific_date'),
        specific_week=request.GET.get('specific_week'),
        specific_month=request.GET.get('specific_month'),
        specific_year=request.GET.get('specific_year'),
        start_date=request.GET.get('start_date'),
        end_date=request.GET.get('end_date'),
        user_id=request.GET.get('user'),
        movement_type=request.GET.get('type'),
        product_id=request.GET.get('product'),
        search_query=request.GET.get('q'),
    )

    summary = TransactionReportService.calculate_summary(queryset, period_data)
    store = shop or StoreSetting.get_settings(user)

    filters_applied = {
        'Period': period_data.get('label'),
        'Type': request.GET.get('type') or 'All Operations',
    }

    pdf_bytes = ReportPdfGenerator.generate_transaction_report_pdf(
        store=store,
        period_data=period_data,
        summary=summary,
        transactions=list(queryset[:1000]),
        filters_applied=filters_applied,
        generated_by=user.get_full_name() or user.username
    )

    filename = f"stockflow_report_{period}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@manager_required
def export_receipt_pdf(request):
    """
    Exports the period transaction receipt as a downloadable/printable PDF document.
    """
    user = request.user
    shop = getattr(user, 'shop', None)
    period = request.GET.get('period', ReportPeriodOption.TODAY).strip()

    queryset, period_data = TransactionReportService.get_filtered_movements(
        shop=shop,
        period=period,
        specific_date=request.GET.get('specific_date'),
        specific_week=request.GET.get('specific_week'),
        specific_month=request.GET.get('specific_month'),
        specific_year=request.GET.get('specific_year'),
        start_date=request.GET.get('start_date'),
        end_date=request.GET.get('end_date'),
        user_id=request.GET.get('user'),
        movement_type=request.GET.get('type'),
        product_id=request.GET.get('product'),
    )

    summary = TransactionReportService.calculate_summary(queryset, period_data)
    store = shop or StoreSetting.get_settings(user)

    pdf_bytes = ReportPdfGenerator.generate_period_receipt_pdf(
        store=store,
        period_data=period_data,
        summary=summary,
        transactions=list(queryset.order_by('created_at')[:1000]),
        generated_by=user.get_full_name() or user.username
    )

    filename = f"stockflow_receipt_{period}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
