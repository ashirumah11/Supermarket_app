from django import forms
from inventory.models import InventoryLocation, InventoryStock, Product
from .models import StockMovement, StockMovementType


class StockTransferForm(forms.Form):
    """Form to initiate a product transfer between two inventory locations."""
    product = forms.ModelChoiceField(
        queryset=Product.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select select2-enable', 'id': 'id_transfer_product'}),
        label="Product to Transfer"
    )
    source_location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_source_location'}),
        label="Source Location (Dispatch From)"
    )
    destination_location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_destination_location'}),
        label="Destination Location (Receive To)"
    )

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if self.shop:
            self.fields['product'].queryset = Product.objects.filter(shop=self.shop).order_by('name')
            self.fields['source_location'].queryset = InventoryLocation.objects.filter(shop=self.shop, is_active=True).order_by('name')
            self.fields['destination_location'].queryset = InventoryLocation.objects.filter(shop=self.shop, is_active=True).order_by('name')

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Number of units to transfer',
            'min': '1',
            'id': 'id_transfer_quantity'
        }),
        label="Quantity to Transfer"
    )
    reason = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Shelf replenishment, Branch restocking, Audit rebalancing'
        }),
        label="Transfer Reason"
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. TR-2026-001, REQ-123'
        }),
        label="Reference / Requisition #"
    )

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source_location')
        destination = cleaned_data.get('destination_location')
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')

        if source and destination and source == destination:
            raise forms.ValidationError(
                "Source and destination locations must be different."
            )

        if product and source and quantity:
            loc_stock = InventoryStock.objects.filter(product=product, location=source).first()
            available = loc_stock.quantity if loc_stock else 0
            if quantity > available:
                raise forms.ValidationError(
                    f"Insufficient stock. Only {available} unit(s) of '{product.name}' available at '{source.name}'."
                )

        return cleaned_data



class StockInForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Restock To Location",
        help_text="Choose the physical location receiving these units."
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter quantity to add',
            'min': '1'
        }),
        label="Quantity to Add",
        help_text="Number of units received into inventory."
    )
    reason = forms.CharField(
        max_length=255,
        initial="Restock / Supplier Delivery",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Weekly Restock, Purchase Order fulfillment'
        }),
        label="Reason"
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. PO-88421, Delivery Note #12'
        }),
        label="Reference / Document #"
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        locations = InventoryLocation.objects.filter(is_active=True)
        if shop:
            locations = locations.filter(shop=shop)
        self.fields['location'].queryset = locations.order_by('name')


class StockOutForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Dispatch From Location",
        help_text="Choose the physical location these units are leaving."
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter quantity to remove',
            'min': '1'
        }),
        label="Quantity to Remove",
        help_text="Number of units dispatched, sold, or written off."
    )
    reason = forms.CharField(
        max_length=255,
        initial="Retail Sale / Store Dispatch",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Over-the-counter sale, Damaged goods, Shelf replenishment'
        }),
        label="Reason"
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Receipt #44210, Dispatch Note'
        }),
        label="Reference / Document #"
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        locations = InventoryLocation.objects.filter(is_active=True)
        if shop:
            locations = locations.filter(shop=shop)
        self.fields['location'].queryset = locations.order_by('name')


class StockAdjustmentForm(forms.Form):
    new_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter actual counted stock quantity',
            'min': '0'
        }),
        label="Actual Physical Stock Count",
        help_text="Set the verified physical count on shelf/warehouse."
    )
    reason = forms.CharField(
        max_length=255,
        initial="Physical Inventory Audit Reconciliation",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Monthly stocktake count, Damaged box write-off'
        }),
        label="Reason for Adjustment"
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. AUDIT-2026-Q1'
        }),
        label="Audit Reference #"
    )


class StockMovementActionForm(forms.Form):
    """Generic form for recording stock movements from the dedicated movements page."""
    product = forms.ModelChoiceField(
        queryset=Product.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select select2-enable'})
    )
    movement_type = forms.ChoiceField(
        choices=StockMovementType.choices,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_movement_type'})
    )
    location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_movement_location'}),
        label="Location"
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity', 'id': 'id_movement_quantity'})
    )
    reason = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for stock change'})
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Invoice, PO, or note'})
    )

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if self.shop:
            self.fields['product'].queryset = Product.objects.filter(shop=self.shop).order_by('name')
        locations = InventoryLocation.objects.filter(is_active=True)
        if self.shop:
            locations = locations.filter(shop=self.shop)
        self.fields['location'].queryset = locations.order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        movement_type = cleaned_data.get('movement_type')
        location = cleaned_data.get('location')
        if movement_type in (StockMovementType.IN, StockMovementType.OUT) and not location:
            self.add_error('location', 'Select the physical location for this stock movement.')
        return cleaned_data
