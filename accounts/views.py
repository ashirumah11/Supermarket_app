from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .decorators import admin_required
from .forms import CustomLoginForm, StoreSettingForm, UserCreateForm, UserProfileUpdateForm, UserUpdateForm
from .models import StoreSetting, User, UserRole

def home_view(request):
    return render(request, 'home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Remember me handling
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0) # expires when browser closes
            else:
                request.session.set_expiry(1209600) # 2 weeks
                
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = CustomLoginForm(request)
    
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.info(request, f"You have been successfully logged out.")
    return redirect('login')


@admin_required
def user_list_view(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users = User.objects.all().order_by('-date_joined')

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

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'roles': UserRole.choices,
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
    }
    return render(request, 'users/user_list.html', context)


@admin_required
def user_create_view(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            messages.success(request, f"User '{new_user.username}' created successfully as {new_user.get_role_display()}.")
            return redirect('user_list')
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = UserCreateForm()

    return render(request, 'users/user_form.html', {
        'form': form,
        'title': 'Add New Team Member',
        'is_create': True,
    })


@admin_required
def user_edit_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=target_user)
        if form.is_valid():
            # Prevent demoting the logged-in superadmin if they are the only admin
            if target_user == request.user and form.cleaned_data['role'] != UserRole.ADMIN:
                admin_count = User.objects.filter(role=UserRole.ADMIN, is_active=True).count()
                if admin_count <= 1:
                    messages.error(request, "Cannot demote your own account when you are the sole active Administrator.")
                    return redirect('user_edit', pk=pk)

            form.save()
            messages.success(request, f"User '{target_user.username}' updated successfully.")
            return redirect('user_list')
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = UserUpdateForm(instance=target_user)

    return render(request, 'users/user_form.html', {
        'form': form,
        'target_user': target_user,
        'title': f"Edit User: {target_user.username}",
        'is_create': False,
    })


@admin_required
def user_toggle_status_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_list')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.success(request, f"User '{target_user.username}' has been {status_str}.")
    return redirect('user_list')


@login_required
def settings_view(request):
    store_setting = StoreSetting.get_settings()
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
                store_form.save()
                messages.success(
                    request,
                    f"Supermarket facility identity updated: '{store_setting.name} ({store_setting.branch_name})'."
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
