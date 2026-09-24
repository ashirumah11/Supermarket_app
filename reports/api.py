from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import UserRole
from .serializers import StockMovementReportSerializer
from .services import ReportPeriodOption, TransactionReportService


class TransactionReportApiView(APIView):
    """
    REST API endpoint for querying StockFlow inventory transaction reports.
    Supports flexible combinable filters for period, user, transaction type, product, and search queries.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        shop = getattr(user, 'shop', None)

        # Role-based scoping: Staff can only query their own movements unless Manager/Admin
        user_param = request.GET.get('user') or request.GET.get('user_id')
        if not user.is_manager_user:
            user_param = str(user.id)

        period = request.GET.get('period', ReportPeriodOption.TODAY)
        specific_date = request.GET.get('date') or request.GET.get('specific_date')
        specific_week = request.GET.get('week') or request.GET.get('specific_week')
        specific_month = request.GET.get('month') or request.GET.get('specific_month')
        specific_year = request.GET.get('year') or request.GET.get('specific_year')
        start_date = request.GET.get('start_date') or request.GET.get('date_from')
        end_date = request.GET.get('end_date') or request.GET.get('date_to')
        movement_type = request.GET.get('type')
        product_id = request.GET.get('product') or request.GET.get('product_id')
        search_query = request.GET.get('q')

        # If date parameter is directly passed without period set, infer specific_date
        if specific_date and not request.GET.get('period'):
            period = ReportPeriodOption.SPECIFIC_DATE
        elif (start_date or end_date) and not request.GET.get('period'):
            period = ReportPeriodOption.CUSTOM

        queryset, period_data = TransactionReportService.get_filtered_movements(
            shop=shop,
            period=period,
            specific_date=specific_date,
            specific_week=specific_week,
            specific_month=specific_month,
            specific_year=specific_year,
            start_date=start_date,
            end_date=end_date,
            user_id=user_param,
            movement_type=movement_type,
            product_id=product_id,
            search_query=search_query,
        )

        summary = TransactionReportService.calculate_summary(queryset, period_data)
        serializer = StockMovementReportSerializer(queryset[:500], many=True)

        return Response({
            'period': period_data,
            'summary': summary,
            'count': queryset.count(),
            'transactions': serializer.data,
        }, status=status.HTTP_200_OK)
