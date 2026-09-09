from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Notification
from .services import NotificationService

@login_required
def notification_list_view(request):
    filter_state = request.GET.get('state', '').strip()
    notifications = Notification.objects.filter(user=request.user)

    if filter_state == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_state == 'read':
        notifications = notifications.filter(is_read=True)

    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'notifications': page_obj,
        'page_obj': page_obj,
        'filter_state': filter_state,
        'total_count': Notification.objects.filter(user=request.user).count(),
        'unread_count': NotificationService.get_unread_count(request.user),
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
@require_POST
def mark_notification_read_view(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'unread_count': NotificationService.get_unread_count(request.user)
        })

    messages.success(request, "Notification marked as read.")
    return redirect('notification_list')


@login_required
@require_POST
def mark_all_notifications_read_view(request):
    NotificationService.mark_all_as_read(request.user)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'unread_count': 0
        })

    messages.success(request, "All notifications marked as read.")
    return redirect('notification_list')


@login_required
def api_unread_count(request):
    return JsonResponse({
        'unread_count': NotificationService.get_unread_count(request.user)
    })
