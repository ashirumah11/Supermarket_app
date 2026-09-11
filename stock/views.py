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
    shop = getattr(request.user, 'shop', None)
    product_id = request.GET.get('product', '').strip()
    movement_type = request.GET.get('type', '').strip()
    user_id = request.GET.get('user', '').strip()
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    movements = StockMovement.objects.select_related('product', 'user')
    if shop:
        movements = movements.filter(shop=shop)
    else:
        movements = movements.all()

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

    products_qs = Product.objects.filter(shop=shop).order_by('name') if shop else Product.objects.all().order_by('name')
    users_qs = User.objects.filter(shop=shop).order_by('username') if shop else User.objects.all().order_by('username')
    total_count = StockMovement.objects.filter(shop=shop).count() if shop else StockMovement.objects.count()

    context = {
        'movements': page_obj,
        'page_obj': page_obj,
        'products': products_qs,
        'movement_types': StockMovementType.choices,
        'users': users_qs,
        'selected_product': product_id,
        'selected_type': movement_type,
        'selected_user': user_id,
        'selected_query': query,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
        'total_count': total_count,
    }
    return render(request, 'stock/movement_list.html', context)


@staff_required
@require_POST
def stock_in_view(request, product_id):
    shop = getattr(request.user, 'shop', None)
    if shop:
        product = get_object_or_404(Product, pk=product_id, shop=shop)
    else:
        product = get_object_or_404(Product, pk=product_id)
    form = StockInForm(request.POST, shop=shop)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_detail'

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        location = form.cleaned_data['location']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data.get('reference', '')

        try:
            StockMovementService.record_movement(
                product=product,
                movement_type=StockMovementType.IN,
                quantity=quantity,
                user=request.user,
                reason=reason,
                reference=reference,
                location=location,
            )
            messages.success(
                request,
                f"Stock IN recorded: Added {quantity} units to '{product.name}' at {location.name}. New total: {product.quantity} units."
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
    shop = getattr(request.user, 'shop', None)
    if shop:
        product = get_object_or_404(Product, pk=product_id, shop=shop)
    else:
        product = get_object_or_404(Product, pk=product_id)
    form = StockOutForm(request.POST, shop=shop)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'product_detail'

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        location = form.cleaned_data['location']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data.get('reference', '')

        try:
            StockMovementService.record_movement(
                product=product,
                movement_type=StockMovementType.OUT,
                quantity=quantity,
                user=request.user,
                reason=reason,
                reference=reference,
                location=location,
            )
            messages.success(
                request,
                f"Stock OUT recorded: Dispatched {quantity} units of '{product.name}' from {location.name}. Remaining: {product.quantity} units."
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
    shop = getattr(request.user, 'shop', None)
    if shop:
        product = get_object_or_404(Product, pk=product_id, shop=shop)
    else:
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
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = StockMovementActionForm(request.POST, shop=shop)
        if form.is_valid():
            product = form.cleaned_data['product']
            m_type = form.cleaned_data['movement_type']
            qty = form.cleaned_data['quantity']
            reason = form.cleaned_data['reason']
            ref = form.cleaned_data.get('reference', '')
            location = form.cleaned_data.get('location')

            try:
                if m_type == StockMovementType.ADJUSTMENT:
                    StockMovementService.record_movement(
                        product=product,
                        movement_type=m_type,
                        quantity=None,
                        user=request.user,
                        reason=reason,
                        reference=ref,
                        new_target_quantity=qty,
                    )
                else:
                    StockMovementService.record_movement(
                        product=product,
                        movement_type=m_type,
                        quantity=qty,
                        user=request.user,
                        reason=reason,
                        reference=ref,
                        location=location,
                    )
                messages.success(request, f"Successfully recorded {m_type} operation for '{product.name}'.")
                return redirect('stock_movements')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        initial_product = request.GET.get('product')
        form = StockMovementActionForm(initial={'product': initial_product} if initial_product else {}, shop=shop)

    return render(request, 'stock/stock_form.html', {'form': form, 'title': 'Record Stock Movement'})


# ==================== STOCK TRANSFER VIEWS ====================

@login_required
def transfer_list_view(request):
    """List all stock transfers with pagination and filters."""
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    product_id = request.GET.get('product', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    transfers = StockTransfer.objects.select_related(
        'product', 'source_location', 'destination_location', 'user'
    )
    if shop:
        transfers = transfers.filter(shop=shop)
    else:
        transfers = transfers.all()

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

    products_qs = Product.objects.filter(shop=shop).order_by('name') if shop else Product.objects.all().order_by('name')
    total_count = StockTransfer.objects.filter(shop=shop).count() if shop else StockTransfer.objects.count()

    context = {
        'transfers': page_obj,
        'page_obj': page_obj,
        'products': products_qs,
        'selected_product': product_id,
        'selected_query': query,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
        'total_count': total_count,
    }
    return render(request, 'stock/transfer_list.html', context)


@manager_required
def transfer_create_view(request):
    """Form to execute a stock transfer between locations."""
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, shop=shop)
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
        }, shop=shop)

    locations = InventoryLocation.objects.filter(is_active=True)
    if shop:
        locations = locations.filter(shop=shop)
    locations = locations.order_by('name')

    return render(request, 'stock/transfer_form.html', {
        'form': form,
        'locations': locations,
        'title': 'New Stock Transfer',
    })


@login_required
def transfer_detail_view(request, pk):
    """Detail view for a specific stock transfer, including receipt print."""
    shop = getattr(request.user, 'shop', None)
    qs = StockTransfer.objects.select_related(
        'product', 'source_location', 'destination_location', 'user'
    )
    if shop:
        transfer = get_object_or_404(qs, pk=pk, shop=shop)
    else:
        transfer = get_object_or_404(qs, pk=pk)
    return render(request, 'stock/transfer_detail.html', {'transfer': transfer})


@login_required
def transfer_receipt_view(request, pk):
    """Print-ready receipt for a stock transfer."""
    shop = getattr(request.user, 'shop', None)
    qs = StockTransfer.objects.select_related(
        'product', 'source_location', 'destination_location', 'user'
    )
    if shop:
        transfer = get_object_or_404(qs, pk=pk, shop=shop)
    else:
        transfer = get_object_or_404(qs, pk=pk)
    from accounts.models import StoreSetting
    store = shop or StoreSetting.get_settings(request.user)
    return render(request, 'stock/transfer_receipt.html', {
        'transfer': transfer,
        'store': store,
    })


@login_required
def location_stock_api(request):
    """JSON API: returns available stock of a product at a given location."""
    shop = getattr(request.user, 'shop', None)
    product_id = request.GET.get('product')
    location_id = request.GET.get('location')

    if not product_id or not location_id:
        return JsonResponse({'quantity': 0, 'error': 'Missing parameters'})

    try:
        qs = InventoryStock.objects.filter(product_id=product_id, location_id=location_id)
        if shop:
            qs = qs.filter(product__shop=shop)
        stock = qs.first()
        if stock:
            return JsonResponse({'quantity': stock.quantity})
        return JsonResponse({'quantity': 0})
    except Exception:
        return JsonResponse({'quantity': 0})


@login_required
def movement_receipt_view(request, pk):
    """Print-ready official audit receipt and voucher for any stock operation."""
    shop = getattr(request.user, 'shop', None)
    qs = StockMovement.objects.select_related('product', 'location', 'destination_location', 'user')
    if shop:
        movement = get_object_or_404(qs, pk=pk, shop=shop)
    else:
        movement = get_object_or_404(qs, pk=pk)
    from accounts.models import StoreSetting
    store = shop or StoreSetting.get_settings(request.user)
    return render(request, 'stock/movement_receipt.html', {
        'movement': movement,
        'store': store,
    })
