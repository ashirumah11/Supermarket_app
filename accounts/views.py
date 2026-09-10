from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from .decorators import admin_required
from .forms import (
    AdminRegistrationForm,
    UserRegistrationForm,
    CustomLoginForm,
    ForgotPasswordForm,
    StoreSettingForm,
    UserCreateForm,
    UserProfileUpdateForm,
    UserUpdateForm,
)
from .models import StoreSetting, UserRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Public / Marketing Home
# ---------------------------------------------------------------------------
def home_view(request):
    return render(request, 'home.html')


# ---------------------------------------------------------------------------
# Account Registration
# ---------------------------------------------------------------------------
def register_view(request):
    """
    Account registration view for new StockFlow users.
    On success: saves account to DB, then redirects to the Sign In page with a
    clear 'Account created successfully' confirmation and 'Go to Sign In' button
    (does NOT auto-login — user must sign in manually).
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Account created successfully for {user.first_name} {user.last_name}! Please sign in below."
            )
            return redirect('/login/?registered=true')
        else:
            messages.error(request, "Please correct the errors below and try again.")
            referer = request.META.get('HTTP_REFERER', '')
            if 'register' in referer and 'login' not in referer:
                return render(request, 'auth/register.html', {'form': form})
            return render(request, 'auth/login.html', {
                'form': CustomLoginForm(request),
                'reg_form': form,
                'active_tab': 'signup',
            })
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})



# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    registered = request.GET.get('registered') == 'true'
    active_tab = request.GET.get('tab', 'signin')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Remember me handling
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)   # expires when browser closes
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid email or password. Please try again.")
    else:
        form = CustomLoginForm(request)

    return render(request, 'auth/login.html', {
        'form': form,
        'reg_form': UserRegistrationForm(),
        'registered': registered,
        'active_tab': active_tab,
    })


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been successfully signed out.")
    return redirect('login')


# ---------------------------------------------------------------------------
# Forgot Password
# ---------------------------------------------------------------------------
def forgot_password_view(request):
    """
    Step 1 of password recovery: user enters their email address.
    We always show a generic success message — never reveal whether the
    account exists (prevents email enumeration).
    """
    email_sent = False

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            # Look up user silently — do NOT reveal to client whether found
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                _send_password_reset_email(request, user)
            except User.DoesNotExist:
                pass  # Silently ignore — prevents email enumeration
            email_sent = True
        # Even on invalid form (bad email format), flip to success state
        # to avoid leaking info. In practice, the field validation is
        # structural only (valid email format), not existence-based.
        else:
            email_sent = False
    else:
        form = ForgotPasswordForm()

    return render(request, 'auth/forgot_password.html', {
        'form': form,
        'email_sent': email_sent,
    })


def _send_password_reset_email(request, user):
    """Generate a secure reset token and send it to the user's email."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    # Build absolute reset URL
    domain = request.get_host()
    protocol = 'https' if request.is_secure() else 'http'
    reset_url = f"{protocol}://{domain}/reset-password/{uid}/{token}/"

    subject = "StockFlow — Password Reset Request"
    body = render_to_string('auth/emails/password_reset_email.txt', {
        'user': user,
        'reset_url': reset_url,
        'domain': domain,
        'protocol': protocol,
    })

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
        recipient_list=[user.email],
        fail_silently=True,
    )


# ---------------------------------------------------------------------------
# Password Reset Confirm
# ---------------------------------------------------------------------------
def password_reset_confirm_view(request, uidb64, token):
    """
    Step 2: user clicks the link from their email.
    Validates the token and lets the user set a new password.
    """
    # Decode uid and fetch user
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_valid = user is not None and default_token_generator.check_token(user, token)

    if not token_valid:
        return render(request, 'auth/password_reset_confirm.html', {
            'token_valid': False,
        })

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your password has been reset successfully. You can now sign in with your new password."
            )
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SetPasswordForm(user)

    # Apply Bootstrap styling to the SetPasswordForm fields
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control form-control-lg'})

    return render(request, 'auth/password_reset_confirm.html', {
        'form': form,
        'token_valid': True,
        'uidb64': uidb64,
        'token': token,
    })


# ---------------------------------------------------------------------------
# Standalone Change Password (login required)
# ---------------------------------------------------------------------------
@login_required
def change_password_view(request):
    """
    Dedicated change-password page for logged-in users.
    Uses update_session_auth_hash to keep the session valid after change.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Prevent session invalidation
            messages.success(request, "Your password has been changed successfully.")
            return redirect('change_password')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(user=request.user)

    # Apply Bootstrap styling
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control'})

    return render(request, 'auth/change_password.html', {'form': form})


# ---------------------------------------------------------------------------
# User Management (Admin only)
# ---------------------------------------------------------------------------
@admin_required
def user_list_view(request):
    shop = getattr(request.user, 'shop', None)
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users = User.objects.all()
    if shop:
        users = users.filter(shop=shop)
    users = users.order_by('-date_joined')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    paginator = Paginator(users, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    stats_qs = User.objects.filter(shop=shop) if shop else User.objects.all()

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'roles': UserRole.choices,
        # Stats
        'total_users': stats_qs.count(),
        'active_users': stats_qs.filter(is_active=True).count(),
        'manager_count': stats_qs.filter(role=UserRole.MANAGER).count(),
        'staff_count': stats_qs.filter(role=UserRole.STAFF).count(),
        'admin_count': stats_qs.filter(role=UserRole.ADMIN).count(),
    }
    return render(request, 'users/user_list.html', context)


@admin_required
def user_create_view(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST, creator=request.user)
        if form.is_valid():
            new_user = form.save()
            messages.success(
                request,
                f"User '{new_user.get_full_name() or new_user.username}' created successfully as {new_user.get_role_display()}."
            )
            return redirect('user_list')
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = UserCreateForm(creator=request.user)

    return render(request, 'users/user_form.html', {
        'form': form,
        'title': 'Add New Team Member',
        'is_create': True,
    })


@admin_required
def user_edit_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        target_user = get_object_or_404(User, pk=pk, shop=shop)
    else:
        target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=target_user)
        if form.is_valid():
            # Prevent demoting the logged-in superadmin if they are the only admin
            if target_user == request.user and form.cleaned_data['role'] != UserRole.ADMIN:
                admin_qs = User.objects.filter(role=UserRole.ADMIN, is_active=True)
                if shop:
                    admin_qs = admin_qs.filter(shop=shop)
                if admin_qs.count() <= 1:
                    messages.error(
                        request,
                        "Cannot demote your own account when you are the sole active Administrator."
                    )
                    return redirect('user_edit', pk=pk)

            form.save()
            messages.success(request, f"User '{target_user.get_full_name() or target_user.username}' updated successfully.")
            return redirect('user_list')
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = UserUpdateForm(instance=target_user)

    return render(request, 'users/user_form.html', {
        'form': form,
        'target_user': target_user,
        'title': f"Edit User: {target_user.get_full_name() or target_user.username}",
        'is_create': False,
    })


@admin_required
def user_toggle_status_view(request, pk):
    shop = getattr(request.user, 'shop', None)
    if shop:
        target_user = get_object_or_404(User, pk=pk, shop=shop)
    else:
        target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_list')

    # Prevent deactivating the last active admin
    if target_user.role == UserRole.ADMIN or target_user.is_superuser:
        active_admins = User.objects.filter(
            Q(role=UserRole.ADMIN) | Q(is_superuser=True),
            is_active=True
        )
        if shop:
            active_admins = active_admins.filter(shop=shop)
        if active_admins.count() <= 1 and target_user.is_active:
            messages.error(request, "Cannot deactivate the sole active Administrator account.")
            return redirect('user_list')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.success(
        request,
        f"User '{target_user.get_full_name() or target_user.username}' has been {status_str}."
    )
    return redirect('user_list')


# ---------------------------------------------------------------------------
# Settings (Profile + Password Change + Store Settings)
# ---------------------------------------------------------------------------
@login_required
def settings_view(request):
    store_setting = getattr(request.user, 'shop', None) or StoreSetting.get_settings(request.user)
    profile_form = UserProfileUpdateForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)
    store_form = StoreSettingForm(instance=store_setting)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = UserProfileUpdateForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile details updated successfully.")
                return redirect('settings')
            else:
                messages.error(request, "Error updating profile details.")
        elif action == 'change_password':
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect('settings')
            else:
                messages.error(request, "Error changing password. Please review the requirements.")
        elif action == 'update_store':
            if not getattr(request.user, 'is_manager_user', False):
                messages.error(request, "Only managers or admins can modify supermarket facility settings.")
                return redirect('settings')
            store_form = StoreSettingForm(request.POST, instance=store_setting)
            if store_form.is_valid():
                saved_setting = store_form.save()
                if not getattr(request.user, 'shop', None):
                    request.user.shop = saved_setting
                    request.user.save(update_fields=['shop'])
                messages.success(
                    request,
                    f"Supermarket facility identity updated: '{saved_setting.name} ({saved_setting.branch_name})'."
                )
                return redirect('settings')
            else:
                messages.error(request, "Error updating supermarket store settings.")

    return render(request, 'settings/settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'store_form': store_form,
        'store_setting': store_setting,
    })
