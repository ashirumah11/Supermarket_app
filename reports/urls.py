from django.urls import path
from . import api, views

urlpatterns = [
    # Existing Executive Inventory Valuation Report
    path('', views.reports_view, name='reports'),

    # Extended Transaction Reporting Dashboard
    path('transactions/', views.transaction_reports_view, name='transaction_reports'),
    path('transactions/<int:pk>/modal/', views.transaction_detail_modal_view, name='transaction_modal'),

    # Official Period Transaction Receipt
    path('receipt/', views.transaction_receipt_view, name='transaction_receipt'),
    path('receipt/pdf/', views.export_receipt_pdf, name='export_receipt_pdf'),

    # Data Exports
    path('export/csv/', views.export_transactions_csv, name='export_transactions_csv'),
    path('export/pdf/', views.export_transactions_pdf, name='export_transactions_pdf'),

    # DRF API Endpoint
    path('api/transactions/', api.TransactionReportApiView.as_view(), name='api_transaction_reports'),
]
