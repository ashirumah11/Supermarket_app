from .services import NotificationService
from .models import Notification

def notification_context(request):
    """Context processor providing unread count and top 5 recent notifications."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'top_notifications': [],
        }
    
    user = request.user
    unread_count = NotificationService.get_unread_count(user)
    top_notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]
    
    return {
        'unread_notifications_count': unread_count,
        'top_notifications': top_notifications,
    }
