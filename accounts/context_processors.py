from .models import StoreSetting

def auth_context(request):
    """Context processor providing role-based flags and supermarket store identity to templates."""
    store_setting = StoreSetting.get_settings()
    
    base_context = {
        'store_setting': store_setting,
        'store_name': store_setting.name,
        'store_branch': store_setting.branch_name,
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        base_context.update({
            'is_admin': False,
            'is_manager': False,
            'is_staff_member': False,
            'user_role': None,
        })
        return base_context

    user = request.user
    base_context.update({
        'is_admin': getattr(user, 'is_admin_user', False),
        'is_manager': getattr(user, 'is_manager_user', False),
        'is_staff_member': True,
        'user_role': getattr(user, 'role', 'STAFF'),
    })
    return base_context
