from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from accounts.decorators import manager_required, staff_required
from inventory.models import InventoryLocation, InventoryStock, Product
from .forms import StockAdjustmentForm, StockInForm, StockMovementActionForm, StockOutForm, StockTransferForm
from .models import StockMovement, StockMovementType, StockTransfer
from .services import StockMovementService, StockTransferService

User = get_user_model()

@login_required
def movement_list_view(request):
    product_id = request.GET.get('product', '').strip()
    movement_type = request.GET.get('type', '').strip()
    user_id = request.GET.get('user', '').strip()
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    movements = StockMovement.objects.select_related('product', 'user').all()

    if product_id:
        movements = movements.filter(product_id=product_id)
    if movement_type:
        movements = movements.filter(type=movement_type)
    if user_id:
        movements = movements.filter(user_id=user_id)
    if query:
        movements = movements.filter(
            Q(reason__icontains=query) |
            Q(reference__icontains=query) |
            Q(product__name__icontains=query) |
            Q(product__sku__icontains=query)
        )
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)

    paginator = Paginator(movements, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'movements': page_obj,
        'page_obj': page_obj,
        'products': Product.objects.all().order_by('name'),
        'movement_types': StockMovementType.choices,
        'users': User.objects.all().order_by('username'),
        'selected_product': product_id,
        'selected_type': movement_type,
        'selected_user': user_id,
        'selected_query': query,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
        'total_count': StockMovement.objects.count(),
    }
    return render(request, 'stock/movement_list.html', context)


@staff_required
@require_POST
def stock_in_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = StockInForm(request.POST)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_detail'

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data.get('reference', '')

        try:
            StockMovementService.record_movement(
                product=product,
                movement_type=StockMovementType.IN,
                quantity=quantity,
                user=request.user,
                reason=reason,
                reference=reference
            )
            messages.success(
                request,
                f"Stock IN recorded: Added {quantity} units to '{product.name}'. New total: {product.quantity} units."
            )
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        error_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        messages.error(request, f"Invalid Stock IN submission: {error_msg}")

    if next_url == 'product_detail':
        return redirect('product_detail', pk=product.pk)
    return redirect(next_url)


@staff_required
@require_POST
def stock_out_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = StockOutForm(request.POST)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_detail'

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data.get('reference', '')

        try:
            StockMovementService.record_movement(
                product=product,
                movement_type=StockMovementType.OUT,
                quantity=quantity,
                user=request.user,
                reason=reason,
                reference=reference
            )
            messages.success(
                request,
                f"Stock OUT recorded: Dispatched {quantity} units from '{product.name}'. Remaining: {product.quantity} units."
            )
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        error_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        messages.error(request, f"Invalid Stock OUT submission: {error_msg}")

    if next_url == 'product_detail':
        return redirect('product_detail', pk=product.pk)
    return redirect(next_url)


@manager_required
@require_POST
def stock_adjustment_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = StockAdjustmentForm(request.POST)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_detail'

    if form.is_valid():
        new_quantity = form.cleaned_data['new_quantity']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data.get('reference', '')

        try:
            movement, updated_product = StockMovementService.record_movement(
                product=product,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity=None,
                user=request.user,
                reason=reason,
                reference=reference,
                new_target_quantity=new_quantity
            )
            messages.success(
                request,
                f"Stock Adjustment recorded: '{product.name}' updated from {movement.previous_quantity} to {new_quantity} units."
            )
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        error_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        messages.error(request, f"Invalid Stock Adjustment submission: {error_msg}")

    if next_url == 'product_detail':
        return redirect('product_detail', pk=product.pk)
    return redirect(next_url)


@manager_required
def stock_movement_create_view(request):
    """Dedicated page to record a stock movement with product selector."""
    if request.method == 'POST':
        form = StockMovementActionForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            m_type = form.cleaned_data['movement_type']
            qty = form.cleaned_data['quantity']
            reason = form.cleaned_data['reason']
            ref = form.cleaned_data.get('reference', '')

            try:
                if m_type == StockMovementType.ADJUSTMENT:
                    StockMovementService.record_movement(
                        product=product,
                        movement_type=m_type,
                        quantity=None,
                        user=request.user,
                        reason=reason,
                        reference=ref,
                        new_target_quantity=qty
                    )
                else:
                    StockMovementService.record_movement(
                        product=product,
                        movement_type=m_type,
                        quantity=qty,
                        user=request.user,
                        reason=reason,
                        reference=ref
                    )
                messages.success(request, f"Successfully recorded {m_type} operation for '{product.name}'.")
                return redirect('stock_movements')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        initial_product = request.GET.get('product')
        form = StockMovementActionForm(initial={'product': initial_product} if initial_product else {})

    return render(request, 'stock/stock_form.html', {'form': form, 'title': 'Record Stock Movement'})


# ==================== STOCK TRANSFER VIEWS ====================

@login_required
def transfer_list_view(request):
    """List all stock transfers with pagination and filters."""
    query = request.GET.get('q', '').strip()
    product_id = request.GET.get('product', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    transfers = StockTransfer.objects.select_related(
        'product', 'source_location', 'destination_location', 'user'
    ).all()

    if query:
        transfers = transfers.filter(
            Q(reason__icontains=query) |
            Q(reference__icontains=query) |
            Q(product__name__icontains=query) |
            Q(product__sku__icontains=query) |
            Q(source_location__name__icontains=query) |
            Q(destination_location__name__icontains=query)
        )
    if product_id:
        transfers = transfers.filter(product_id=product_id)
    if date_from:
        transfers = transfers.filter(created_at__date__gte=date_from)
    if date_to:
        transfers = transfers.filter(created_at__date__lte=date_to)

    paginator = Paginator(transfers, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'transfers': page_obj,
        'page_obj': page_obj,
        'products': Product.objects.all().order_by('name'),
        'selected_product': product_id,
        'selected_query': query,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
        'total_count': StockTransfer.objects.count(),
    }
    return render(request, 'stock/transfer_list.html', context)


@manager_required
def transfer_create_view(request):
    """Form to execute a stock transfer between locations."""
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        if form.is_valid():
            try:
                transfer = StockTransferService.execute_transfer(
                    product=form.cleaned_data['product'],
                    source_location=form.cleaned_data['source_location'],
                    destination_location=form.cleaned_data['destination_location'],
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    reason=form.cleaned_data['reason'],
                    reference=form.cleaned_data.get('reference', ''),
                )
                messages.success(
                    request,
                    f"Transfer {transfer.receipt_number} executed: {transfer.quantity} × {transfer.product.name} "
                    f"from '{transfer.source_location.name}' → '{transfer.destination_location.name}'."
                )
                return redirect('transfer_detail', pk=transfer.pk)
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            for error_list in form.errors.values():
                for err in error_list:
                    messages.error(request, err)
    else:
        form = StockTransferForm(initial={
            'product': request.GET.get('product'),
            'source_location': request.GET.get('from'),
        })

    locations = InventoryLocation.objects.filter(is_active=True).order_by('name')
    return render(request, 'stock/transfer_form.html', {
        'form': form,
        'locations': locations,
        'title': 'New Stock Transfer',
    })


@login_required
def transfer_detail_view(request, pk):
    """Detail view for a specific stock transfer, including receipt print."""
    transfer = get_object_or_404(
        StockTransfer.objects.select_related(
            'product', 'source_location', 'destination_location', 'user'
        ),
        pk=pk
    )
    return render(request, 'stock/transfer_detail.html', {'transfer': transfer})


@login_required
def transfer_receipt_view(request, pk):
    """Print-ready receipt for a stock transfer."""
    transfer = get_object_or_404(
        StockTransfer.objects.select_related(
            'product', 'source_location', 'destination_location', 'user'
        ),
        pk=pk
    )
    from accounts.models import StoreSetting
    store = StoreSetting.get_settings()
    return render(request, 'stock/transfer_receipt.html', {
        'transfer': transfer,
        'store': store,
    })


@login_required
def location_stock_api(request):
    """JSON API: returns available stock of a product at a given location."""
    product_id = request.GET.get('product')
    location_id = request.GET.get('location')

    if not product_id or not location_id:
        return JsonResponse({'quantity': 0, 'error': 'Missing parameters'})

    try:
        stock = InventoryStock.objects.get(product_id=product_id, location_id=location_id)
        return JsonResponse({'quantity': stock.quantity})
    except InventoryStock.DoesNotExist:
        return JsonResponse({'quantity': 0})


@login_required
def movement_receipt_view(request, pk):
    """Print-ready official audit receipt and voucher for any stock operation."""
    movement = get_object_or_404(
        StockMovement.objects.select_related('product', 'location', 'destination_location', 'user'),
        pk=pk
    )
    from accounts.models import StoreSetting
    store = StoreSetting.get_settings()
    return render(request, 'stock/movement_receipt.html', {
        'movement': movement,
        'store': store,
    })
