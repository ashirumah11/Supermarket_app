from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import admin_required, manager_required, staff_required
from stock.forms import StockAdjustmentForm, StockInForm, StockOutForm
from stock.models import StockMovement, StockMovementType
from stock.services import StockMovementService, StockTransferService
from .forms import CategoryForm, InventoryStockForm, LocationForm, ProductForm, SupplierForm
from .models import Category, InventoryLocation, InventoryStock, Product, StockStatus, Supplier

# ==================== PRODUCT VIEWS ====================

def _assign_product_to_location(product, location, user):
    """Place existing product stock at the selected physical location."""
    source_stocks = list(
        product.stocks.select_related('location').filter(quantity__gt=0).exclude(location=location)
    )

    if source_stocks:
        for source_stock in source_stocks:
            StockTransferService.execute_transfer(
                product=product,
                source_location=source_stock.location,
                destination_location=location,
                quantity=source_stock.quantity,
                user=user,
                reason="Product location updated",
                reference="SYS-LOCATION-UPDATE",
            )
        return

    # Products created before location tracking may have a total quantity but no
    # InventoryStock row. Add that historical stock to the selected location.
    location_stock, _ = InventoryStock.objects.get_or_create(
        product=product,
        location=location,
        defaults={
            'quantity': product.quantity,
            'minimum_stock': product.minimum_stock,
            'maximum_stock': product.maximum_stock,
        },
    )
    if location_stock.quantity != product.quantity:
        location_stock.quantity = product.quantity
        location_stock.minimum_stock = product.minimum_stock
        location_stock.maximum_stock = product.maximum_stock
        location_stock.save(update_fields=['quantity', 'minimum_stock', 'maximum_stock', 'updated_at'])

@login_required
def product_list_view(request):
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    supplier_id = request.GET.get('supplier', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort_by = request.GET.get('sort', 'name').strip()

    products = Product.objects.select_related('category', 'supplier')
    if shop:
        products = products.filter(shop=shop)
    else:
        products = products.all()

    # Search
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query)
        )

    # Category & Supplier filters
    if category_id:
        products = products.filter(category_id=category_id)
    if supplier_id:
        products = products.filter(supplier_id=supplier_id)

    # Authoritative stock status filtering
    if status_filter == StockStatus.OUT_OF_STOCK:
        products = products.filter(quantity=0)
    elif status_filter == StockStatus.LOW_STOCK:
        products = products.filter(quantity__gt=0, quantity__lte=F('minimum_stock'))
    elif status_filter == StockStatus.IN_STOCK:
        products = products.filter(quantity__gt=F('minimum_stock'))

    # Sorting
    sort_options = {
        'name': 'name',
        '-name': '-name',
        'price': 'price',
        '-price': '-price',
        'quantity': 'quantity',
        '-quantity': '-quantity',
        'created_at': '-created_at',
    }
    order_field = sort_options.get(sort_by, 'name')
    products = products.order_by(order_field)

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories_qs = Category.objects.filter(shop=shop) if shop else Category.objects.all()
    suppliers_qs = Supplier.objects.filter(shop=shop) if shop else Supplier.objects.all()
    total_count = Product.objects.filter(shop=shop).count() if shop else Product.objects.count()

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'categories': categories_qs,
        'suppliers': suppliers_qs,
        'stock_statuses': StockStatus.choices,
        'selected_q': query,
        'selected_category': category_id,
        'selected_supplier': supplier_id,
        'selected_status': status_filter,
        'selected_sort': sort_by,
        'total_count': total_count,
        'stock_in_form': StockInForm(),
        'stock_out_form': StockOutForm(),
    }
    return render(request, 'inventory/product_list.html', context)


@manager_required
def product_create_view(request):
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = ProductForm(request.POST, shop=shop)
        if form.is_valid():
            initial_qty = form.cleaned_data.get('quantity', 0)
            location = form.cleaned_data.get('location')
            with transaction.atomic():
                product = form.save(commit=False)
                product.quantity = 0
                if shop and not product.shop_id:
                    product.shop = shop
                product.save()

                if initial_qty > 0:
                    InventoryStock.objects.create(
                        product=product,
                        location=location,
                        quantity=initial_qty,
                        minimum_stock=product.minimum_stock,
                        maximum_stock=product.maximum_stock,
                    )
                    StockMovementService.record_movement(
                        product=product,
                        movement_type=StockMovementType.IN,
                        quantity=initial_qty,
                        user=request.user,
                        reason="Initial Product Opening Stock",
                        reference="SYS-INIT",
                        location=location,
                    )

            messages.success(request, f"Product '{product.name}' (SKU: {product.sku}) created successfully.")
            return redirect('product_detail', pk=product.pk)
        else:
            messages.error(request, "Please fix the errors in the form.")
    else:
        form = ProductForm(shop=shop)

    return render(request, 'inventory/product_form.html', {
        'form': form,
        'title': 'Add New Product',
        'is_create': True,
    })


@login_required
def product_detail_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    qs = Product.objects.select_related('category', 'supplier')
    if shop:
        product = get_object_or_404(qs, pk=pk, shop=shop)
    else:
        product = get_object_or_404(qs, pk=pk)

    recent_movements = product.movements.select_related('user').order_by('-created_at')[:10]

    stock_in_form = StockInForm()
    stock_out_form = StockOutForm()
    stock_adjust_form = StockAdjustmentForm(initial={'new_quantity': product.quantity})

    context = {
        'product': product,
        'movements': recent_movements,
        'stock_in_form': stock_in_form,
        'stock_out_form': stock_out_form,
        'stock_adjust_form': stock_adjust_form,
    }
    return render(request, 'inventory/product_detail.html', context)


@manager_required
def product_edit_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        product = get_object_or_404(Product, pk=pk, shop=shop)
    else:
        product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, shop=shop)
        if form.is_valid():
            location = form.cleaned_data.get('location')
            with transaction.atomic():
                product = form.save()
                if location:
                    _assign_product_to_location(product, location, request.user)
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect('product_detail', pk=product.pk)
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = ProductForm(instance=product, shop=shop)

    return render(request, 'inventory/product_form.html', {
        'form': form,
        'product': product,
        'title': f"Edit Product: {product.name}",
        'is_create': False,
    })


@manager_required
def product_delete_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        product = get_object_or_404(Product, pk=pk, shop=shop)
    else:
        product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product_name = product.name
        sku = product.sku
        product.delete()
        messages.success(request, f"Product '{product_name}' ({sku}) was deleted successfully.")
        return redirect('product_list')

    movement_count = product.movements.count()
    return render(request, 'inventory/product_confirm_delete.html', {
        'product': product,
        'movement_count': movement_count,
    })


# ==================== CATEGORY VIEWS ====================

@login_required
def category_list_view(request):
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    categories = Category.objects.annotate(total_products=Count('products'))
    if shop:
        categories = categories.filter(shop=shop)
    else:
        categories = categories.all()

    if query:
        categories = categories.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    categories = categories.order_by('name')
    paginator = Paginator(categories, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = CategoryForm(shop=shop)
    total_count = Category.objects.filter(shop=shop).count() if shop else Category.objects.count()

    context = {
        'categories': page_obj,
        'page_obj': page_obj,
        'query': query,
        'form': form,
        'total_count': total_count,
    }
    return render(request, 'categories/category_list.html', context)


@manager_required
def category_create_view(request):
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = CategoryForm(request.POST, shop=shop)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' created successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Failed to create category. Please review the errors.")
    else:
        form = CategoryForm(shop=shop)

    return render(request, 'categories/category_form.html', {
        'form': form,
        'title': 'Add New Category',
        'is_create': True,
    })


@manager_required
def category_edit_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        category = get_object_or_404(Category, pk=pk, shop=shop)
    else:
        category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = CategoryForm(instance=category, shop=shop)

    return render(request, 'categories/category_form.html', {
        'form': form,
        'category': category,
        'title': f"Edit Category: {category.name}",
        'is_create': False,
    })


@manager_required
def category_delete_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        category = get_object_or_404(Category, pk=pk, shop=shop)
    else:
        category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        cat_name = category.name
        # Check associated products
        prod_count = category.products.count()
        if prod_count > 0:
            messages.warning(
                request,
                f"Category '{cat_name}' has {prod_count} associated product(s). "
                f"Those products are now uncategorized."
            )
        category.delete()
        messages.success(request, f"Category '{cat_name}' has been deleted.")
        return redirect('category_list')

    return render(request, 'categories/category_confirm_delete.html', {'category': category})


# ==================== SUPPLIER VIEWS ====================

@login_required
def supplier_list_view(request):
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    suppliers = Supplier.objects.annotate(total_products=Count('products'))
    if shop:
        suppliers = suppliers.filter(shop=shop)
    else:
        suppliers = suppliers.all()

    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(address__icontains=query)
        )

    suppliers = suppliers.order_by('name')
    paginator = Paginator(suppliers, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_count = Supplier.objects.filter(shop=shop).count() if shop else Supplier.objects.count()

    context = {
        'suppliers': page_obj,
        'page_obj': page_obj,
        'query': query,
        'total_count': total_count,
    }
    return render(request, 'suppliers/supplier_list.html', context)


@login_required
def supplier_detail_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        supplier = get_object_or_404(Supplier, pk=pk, shop=shop)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)
    products = supplier.products.select_related('category')
    if shop:
        products = products.filter(shop=shop)
    products = products.all()

    context = {
        'supplier': supplier,
        'products': products,
    }
    return render(request, 'suppliers/supplier_detail.html', context)


@manager_required
def supplier_create_view(request):
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = SupplierForm(request.POST, shop=shop)
        if form.is_valid():
            sup = form.save()
            messages.success(request, f"Supplier '{sup.name}' created successfully.")
            return redirect('supplier_detail', pk=sup.pk)
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        form = SupplierForm(shop=shop)

    return render(request, 'suppliers/supplier_form.html', {
        'form': form,
        'title': 'Add New Supplier',
        'is_create': True,
    })


@manager_required
def supplier_edit_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        supplier = get_object_or_404(Supplier, pk=pk, shop=shop)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, f"Supplier '{supplier.name}' updated successfully.")
            return redirect('supplier_detail', pk=supplier.pk)
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        form = SupplierForm(instance=supplier, shop=shop)

    return render(request, 'suppliers/supplier_form.html', {
        'form': form,
        'supplier': supplier,
        'title': f"Edit Supplier: {supplier.name}",
        'is_create': False,
    })


@manager_required
def supplier_delete_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        supplier = get_object_or_404(Supplier, pk=pk, shop=shop)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        name = supplier.name
        prod_count = supplier.products.count()
        if prod_count > 0:
            messages.warning(
                request,
                f"Supplier '{name}' was linked to {prod_count} product(s). Those products now have no assigned supplier."
            )
        supplier.delete()
        messages.success(request, f"Supplier '{name}' has been deleted.")
        return redirect('supplier_list')

    return render(request, 'suppliers/supplier_confirm_delete.html', {'supplier': supplier})


# ==================== INVENTORY LOCATION VIEWS ====================

@login_required
def location_list_view(request):
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    location_type = request.GET.get('type', '').strip()

    locations = InventoryLocation.objects.annotate(
        stock_count=Count('stocks', distinct=True)
    )
    if shop:
        locations = locations.filter(shop=shop)
    else:
        locations = locations.all()

    if query:
        locations = locations.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )
    if location_type:
        locations = locations.filter(location_type=location_type)

    locations = locations.order_by('name')
    paginator = Paginator(locations, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    total_count = InventoryLocation.objects.filter(shop=shop).count() if shop else InventoryLocation.objects.count()
    active_count = (
        InventoryLocation.objects.filter(shop=shop, is_active=True).count()
        if shop else InventoryLocation.objects.filter(is_active=True).count()
    )

    from .models import LocationType
    context = {
        'locations': page_obj,
        'page_obj': page_obj,
        'query': query,
        'selected_type': location_type,
        'location_types': LocationType.choices,
        'total_count': total_count,
        'active_count': active_count,
    }
    return render(request, 'locations/location_list.html', context)


@login_required
def location_detail_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        location = get_object_or_404(InventoryLocation, pk=pk, shop=shop)
    else:
        location = get_object_or_404(InventoryLocation, pk=pk)
    stocks = location.stocks.select_related('product', 'product__category').order_by('product__name')
    recent_movements = location.movements.select_related('product', 'user').order_by('-created_at')[:10]

    context = {
        'location': location,
        'stocks': stocks,
        'recent_movements': recent_movements,
    }
    if request.user.is_manager_user:
        context['total_value'] = location.stocks.aggregate(
            val=Sum(F('quantity') * F('product__price'))
        )['val'] or 0
    return render(request, 'locations/location_detail.html', context)


@manager_required
def location_create_view(request):
    shop = getattr(request.user, 'shop', None)
    if request.method == 'POST':
        form = LocationForm(request.POST, shop=shop)
        if form.is_valid():
            loc = form.save()
            messages.success(request, f"Location '{loc.name}' ({loc.code}) created successfully.")
            return redirect('location_detail', pk=loc.pk)
        else:
            messages.error(request, "Please fix the errors in the form.")
    else:
        form = LocationForm(shop=shop)

    return render(request, 'locations/location_form.html', {
        'form': form,
        'title': 'Add New Inventory Location',
        'is_create': True,
    })


@manager_required
def location_edit_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        location = get_object_or_404(InventoryLocation, pk=pk, shop=shop)
    else:
        location = get_object_or_404(InventoryLocation, pk=pk)

    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, f"Location '{location.name}' updated successfully.")
            return redirect('location_detail', pk=location.pk)
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = LocationForm(instance=location, shop=shop)

    return render(request, 'locations/location_form.html', {
        'form': form,
        'location': location,
        'title': f"Edit Location: {location.name}",
        'is_create': False,
    })


@manager_required
def location_delete_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        location = get_object_or_404(InventoryLocation, pk=pk, shop=shop)
    else:
        location = get_object_or_404(InventoryLocation, pk=pk)

    if request.method == 'POST':
        if location.stocks.filter(quantity__gt=0).exists():
            messages.error(
                request,
                f"Cannot delete '{location.name}': it still holds active stock. Transfer all stock out first."
            )
            return redirect('location_detail', pk=location.pk)
        name = location.name
        location.delete()
        messages.success(request, f"Location '{name}' has been deleted.")
        return redirect('location_list')

    stock_count = location.stocks.count()
    active_stock = location.stocks.filter(quantity__gt=0).count()
    return render(request, 'locations/location_confirm_delete.html', {
        'location': location,
        'stock_count': stock_count,
        'active_stock': active_stock,
    })
