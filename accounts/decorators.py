from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from .models import UserRole

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_admin_user:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted: Administrator privileges required.")
        return redirect('dashboard')
    return _wrapped_view

def manager_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_manager_user:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted: Manager or Administrator privileges required.")
        return redirect('dashboard')
    return _wrapped_view

def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return _wrapped_view
