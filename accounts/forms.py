from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import UserRole

User = get_user_model()

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your username or email',
            'id': 'username_field',
            'autocomplete': 'username',
            'autofocus': True,
        }),
        label="Username / Email"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
            'id': 'password_field',
            'autocomplete': 'current-password',
        }),
        label="Password"
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'rememberMeCheck'}),
        label="Remember this device"
    )


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 6 characters'
        }),
        min_length=6,
        help_text="Password must be at least 6 characters long."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm the password'
        }),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. john_doe'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. John'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'john@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 700 123456'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Another user is already registered with this email.")
        return email


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


from .models import StoreSetting

class StoreSettingForm(forms.ModelForm):
    class Meta:
        model = StoreSetting
        fields = [
            'name', 'branch_name', 'phone', 'email',
            'address', 'tax_pin', 'currency_symbol', 'receipt_footer_note'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. StockFlow Supermarket'}),
            'branch_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Westlands Branch'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 700 123 456'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'store@supermarket.com'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Physical street address / Mall location'}),
            'tax_pin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'KRA PIN or Business Registration #'}),
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'KES'}),
            'receipt_footer_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Note displayed at the bottom of all printed receipts and audit vouchers'}),
        }
