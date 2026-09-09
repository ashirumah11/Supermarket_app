from django.urls import path
from . import views

urlpatterns = [
    # Products
    path('', views.product_list_view, name='product_list'),
    path('create/', views.product_create_view, name='product_create'),
    path('<int:pk>/', views.product_detail_view, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit_view, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete_view, name='product_delete'),

    # Categories
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete_view, name='category_delete'),

    # Suppliers
    path('suppliers/', views.supplier_list_view, name='supplier_list'),
    path('suppliers/create/', views.supplier_create_view, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail_view, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit_view, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete_view, name='supplier_delete'),

    # Inventory Locations
    path('locations/', views.location_list_view, name='location_list'),
    path('locations/create/', views.location_create_view, name='location_create'),
    path('locations/<int:pk>/', views.location_detail_view, name='location_detail'),
    path('locations/<int:pk>/edit/', views.location_edit_view, name='location_edit'),
    path('locations/<int:pk>/delete/', views.location_delete_view, name='location_delete'),
]
