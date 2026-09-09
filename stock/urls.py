from django.urls import path
from . import views

urlpatterns = [
    # Stock Movement Ledger
    path('', views.movement_list_view, name='stock_movements'),
    path('record/', views.stock_movement_create_view, name='stock_movement_create'),
    path('<int:pk>/receipt/', views.movement_receipt_view, name='movement_receipt'),
    path('in/<int:product_id>/', views.stock_in_view, name='stock_in'),
    path('out/<int:product_id>/', views.stock_out_view, name='stock_out'),
    path('adjust/<int:product_id>/', views.stock_adjustment_view, name='stock_adjust'),

    # Stock Transfers
    path('transfers/', views.transfer_list_view, name='transfer_list'),
    path('transfers/create/', views.transfer_create_view, name='transfer_create'),
    path('transfers/<int:pk>/', views.transfer_detail_view, name='transfer_detail'),
    path('transfers/<int:pk>/receipt/', views.transfer_receipt_view, name='transfer_receipt'),

    # API Utilities
    path('api/location-stock/', views.location_stock_api, name='location_stock_api'),
]
