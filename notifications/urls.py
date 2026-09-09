from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list_view, name='notification_list'),
    path('<int:pk>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('read-all/', views.mark_all_notifications_read_view, name='mark_all_notifications_read'),
    path('api/unread-count/', views.api_unread_count, name='api_notification_unread_count'),
]
