from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts import views as account_views
from inventory import views as inventory_views

urlpatterns = [
    # Public & Auth
    path('', account_views.home_view, name='home'),
    path('login/', account_views.login_view, name='login'),
    path('logout/', account_views.logout_view, name='logout'),

    # Executive Dashboard
    path('dashboard/', include('dashboard.urls')),

    # Inventory Catalog
    path('inventory/', include('inventory.urls')),

    # Categories (direct top-level URLs)
    path('categories/', inventory_views.category_list_view, name='category_list'),
    path('categories/create/', inventory_views.category_create_view, name='category_create'),
    path('categories/<int:pk>/edit/', inventory_views.category_edit_view, name='category_edit'),
    path('categories/<int:pk>/delete/', inventory_views.category_delete_view, name='category_delete'),

    # Suppliers (direct top-level URLs)
    path('suppliers/', inventory_views.supplier_list_view, name='supplier_list'),
    path('suppliers/create/', inventory_views.supplier_create_view, name='supplier_create'),
    path('suppliers/<int:pk>/', inventory_views.supplier_detail_view, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', inventory_views.supplier_edit_view, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', inventory_views.supplier_delete_view, name='supplier_delete'),

    # Stock Movements & Ledger
    path('stock-movements/', include('stock.urls')),

    # In-App Notifications
    path('notifications/', include('notifications.urls')),

    # Executive Reports & Valuation
    path('reports/', include('reports.urls')),

    # User Management (Admin only)
    path('users/', account_views.user_list_view, name='user_list'),
    path('users/create/', account_views.user_create_view, name='user_create'),
    path('users/<int:pk>/edit/', account_views.user_edit_view, name='user_edit'),
    path('users/<int:pk>/toggle-status/', account_views.user_toggle_status_view, name='user_toggle_status'),

    # Settings
    path('settings/', account_views.settings_view, name='settings'),

    # Django Admin (for developer convenience)
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
