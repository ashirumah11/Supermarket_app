from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import UserRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Login Form
# ---------------------------------------------------------------------------
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

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            lookup_username = username
            if '@' in username or not User.objects.filter(username=username).exists():
                user_match = User.objects.filter(email__iexact=username).first()
                if user_match:
                    lookup_username = user_match.username

            self.user_cache = authenticate(self.request, username=lookup_username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


# ---------------------------------------------------------------------------
# User Registration Form
# ---------------------------------------------------------------------------
class UserRegistrationForm(forms.Form):
    shop_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. Westlands Supermarket (Optional)',
            'id': 'id_shop_name',
        }),
        label="Shop / Supermarket Name",
        help_text="Leave blank to use your name automatically."
    )
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. John',
            'id': 'id_first_name',
            'autocomplete': 'given-name',
        }),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. Kamau',
            'id': 'id_last_name',
            'autocomplete': 'family-name',
        }),
        label="Last Name"
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'john.kamau@yourstore.com',
            'id': 'id_email',
            'autocomplete': 'email',
        }),
        label="Email / Username",
        help_text="Used as your login email or username."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Minimum 8 characters',
            'id': 'id_password',
            'autocomplete': 'new-password',
        }),
        label="Password",
        help_text="Must be at least 8 characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Re-enter your password',
            'id': 'id_confirm_password',
            'autocomplete': 'new-password',
        }),
        label="Confirm Password"
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise forms.ValidationError(list(e.messages))
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match. Please try again.")
        return cleaned_data

    def save(self):
        """Create a brand-new Admin user and a brand-new isolated Shop."""
        data = self.cleaned_data
        email = data['email'].strip().lower()
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        raw_shop_name = data.get('shop_name', '').strip()
        shop_name = raw_shop_name if raw_shop_name else f"{first_name}'s Supermarket"

        # 1. Create the brand-new StoreSetting / Shop for this tenant
        from .models import StoreSetting
        shop = StoreSetting.objects.create(
            name=shop_name,
            branch_name="Main Branch",
            email=email,
            phone="",
            address="",
            tax_pin="",
            currency_symbol="KES",
            receipt_footer_note="Official Inventory Movement Record. Generated by StockFlow Smart Management System."
        )

        # 2. Derive unique username from email
        base_username = email.split('@')[0].replace('.', '_').replace('-', '_')
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        # 3. Create the user as the Admin / Owner of the shop
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            shop=shop,
        )
        user.set_password(data['password'])
        user.save()

        # 4. Bind owner to the shop
        shop.owner = user
        shop.save(update_fields=['owner'])

        return user


# Backwards-compatible alias for existing imports
AdminRegistrationForm = UserRegistrationForm


# ---------------------------------------------------------------------------
# Forgot Password Form
# ---------------------------------------------------------------------------
class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your account email address',
            'id': 'id_forgot_email',
            'autocomplete': 'email',
        }),
        label="Email Address"
    )


# ---------------------------------------------------------------------------
# Admin Creates User Form (MANAGER / STAFF only — ADMIN excluded)
# ---------------------------------------------------------------------------
# Restrict selectable roles to non-admin roles for security.
NON_ADMIN_ROLE_CHOICES = [
    (UserRole.MANAGER, UserRole.MANAGER.label),
    (UserRole.STAFF, UserRole.STAFF.label),
]


class UserCreateForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=NON_ADMIN_ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="System Role",
        help_text="MANAGER: Inventory, stock & reports. STAFF: Operational stock tasks."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters'
        }),
        help_text="Password must meet the system strength requirements."
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
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, creator=None, **kwargs):
        self.creator = creator
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise forms.ValidationError(list(e.messages))
        return password

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
        if self.creator and getattr(self.creator, 'shop', None):
            user.shop = self.creator.shop
        if commit:
            user.save()
        return user


# ---------------------------------------------------------------------------
# Admin Edit User Form
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# User Profile Update Form (own profile, used in settings page)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Store Setting Form
# ---------------------------------------------------------------------------
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
