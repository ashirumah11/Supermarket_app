from django import forms
from .models import Category, InventoryLocation, InventoryStock, Product, Supplier

class ProductForm(forms.ModelForm):
    location = forms.ModelChoiceField(
        queryset=InventoryLocation.objects.none(),
        required=False,
        label="Location",
        help_text="Physical location that will receive the opening stock.",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'description', 'category', 'supplier',
            'price', 'quantity', 'minimum_stock', 'maximum_stock'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Premium White Sugar 1kg'}),
            'sku': forms.TextInput(attrs={'class': 'form-control font-monospace', 'placeholder': 'e.g. SUG-1001'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Product details, packaging, specifications...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.00', 'placeholder': '0.00'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '5'}),
            'maximum_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': '100'}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if self.shop:
            self.fields['category'].queryset = Category.objects.filter(shop=self.shop)
            self.fields['supplier'].queryset = Supplier.objects.filter(shop=self.shop)
            self.fields['location'].queryset = InventoryLocation.objects.filter(
                shop=self.shop, is_active=True
            ).order_by('name')
        else:
            self.fields['location'].queryset = InventoryLocation.objects.filter(
                is_active=True
            ).order_by('name')

        if self.instance.pk:
            assigned_location_ids = list(
                self.instance.stocks.values_list('location_id', flat=True).distinct()[:2]
            )
            if len(assigned_location_ids) == 1:
                self.initial['location'] = assigned_location_ids[0]

    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip().upper()
        if not sku:
            raise forms.ValidationError("SKU code is required.")
        qs = Product.objects.filter(sku__iexact=sku)
        if self.shop:
            qs = qs.filter(shop=self.shop)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"A product with SKU '{sku}' already exists.")
        return sku

    def clean(self):
        cleaned_data = super().clean()
        min_stock = cleaned_data.get('minimum_stock')
        max_stock = cleaned_data.get('maximum_stock')
        quantity = cleaned_data.get('quantity')
        location = cleaned_data.get('location')

        if min_stock is not None and max_stock is not None:
            if max_stock < min_stock:
                self.add_error('maximum_stock', "Maximum stock must be greater than or equal to minimum stock threshold.")
        if quantity is not None and quantity < 0:
            self.add_error('quantity', "Stock quantity cannot be negative.")
        if not self.instance.pk and quantity and not location:
            self.add_error('location', "Select the physical location for the opening stock.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.shop and not instance.shop_id:
            instance.shop = self.shop
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dairy & Bakery'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Category description...'}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Category.objects.filter(name__iexact=name)
        if self.shop:
            qs = qs.filter(shop=self.shop)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Category '{name}' already exists.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.shop and not instance.shop_id:
            instance.shop = self.shop
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Nairobi Wholesale Ltd'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. +254 712 345 678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'supplier@domain.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Warehouse or physical office location...'}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.shop and not instance.shop_id:
            instance.shop = self.shop
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class LocationForm(forms.ModelForm):
    class Meta:
        model = InventoryLocation
        fields = ['name', 'code', 'location_type', 'description', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Main Store, Back Stockroom, Central Warehouse'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control font-monospace text-uppercase',
                'placeholder': 'e.g. MAIN, BACK, WH1',
                'maxlength': '20'
            }),
            'location_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the purpose, layout, or capacity of this location...'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Section A, Ground Floor, Building 2'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise forms.ValidationError("A unique location code is required.")
        qs = InventoryLocation.objects.filter(code__iexact=code)
        if self.shop:
            qs = qs.filter(shop=self.shop)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Location code '{code}' is already in use.")
        return code

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.shop and not instance.shop_id:
            instance.shop = self.shop
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class InventoryStockForm(forms.ModelForm):
    """Form to set or update stock quantities for a product at a specific location."""
    class Meta:
        model = InventoryStock
        fields = ['product', 'location', 'quantity', 'minimum_stock', 'maximum_stock']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '5'}),
            'maximum_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': '100'}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if self.shop:
            self.fields['product'].queryset = Product.objects.filter(shop=self.shop)
            self.fields['location'].queryset = InventoryLocation.objects.filter(shop=self.shop)

    def clean(self):
        cleaned_data = super().clean()
        min_stock = cleaned_data.get('minimum_stock')
        max_stock = cleaned_data.get('maximum_stock')
        if min_stock is not None and max_stock is not None:
            if max_stock < min_stock:
                self.add_error('maximum_stock', "Maximum stock must be ≥ minimum stock.")
        return cleaned_data
