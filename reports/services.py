import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from inventory.models import Product
from stock.models import StockMovement, StockMovementType

User = get_user_model()


class ReportPeriodOption:
    TODAY = 'today'
    SPECIFIC_DATE = 'specific_date'
    THIS_WEEK = 'this_week'
    SPECIFIC_WEEK = 'specific_week'
    THIS_MONTH = 'this_month'
    SPECIFIC_MONTH = 'specific_month'
    THIS_YEAR = 'this_year'
    SPECIFIC_YEAR = 'specific_year'
    CUSTOM = 'custom'

    CHOICES = [
        (TODAY, 'Today'),
        (SPECIFIC_DATE, 'Specific Date'),
        (THIS_WEEK, 'This Week'),
        (SPECIFIC_WEEK, 'Specific Week'),
        (THIS_MONTH, 'This Month'),
        (SPECIFIC_MONTH, 'Specific Month'),
        (THIS_YEAR, 'This Year'),
        (SPECIFIC_YEAR, 'Specific Year'),
        (CUSTOM, 'Custom Date Range'),
    ]


class TransactionReportService:
    """
    Service responsible for calculating timezone-aware period ranges,
    filtering StockMovement transactions, and calculating comprehensive aggregations.
    """

    @staticmethod
    def resolve_period_range(
        period=ReportPeriodOption.TODAY,
        specific_date=None,
        specific_week=None,
        specific_month=None,
        specific_year=None,
        start_date=None,
        end_date=None,
        tz=None
    ):
        """
        Calculates (start_datetime, end_datetime, display_label, period_type) in a timezone-aware manner.
        start_datetime is set to 00:00:00 of the starting day.
        end_datetime is set to 23:59:59.999999 of the ending day.
        """
        current_tz = tz or timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), current_tz)
        today = now.date()

        period = (period or ReportPeriodOption.TODAY).strip().lower()

        # 1. TODAY
        if period == ReportPeriodOption.TODAY:
            d_start = today
            d_end = today
            label = f"Today ({today.strftime('%d %B %Y')})"

        # 2. SPECIFIC DATE
        elif period == ReportPeriodOption.SPECIFIC_DATE:
            if isinstance(specific_date, str) and specific_date.strip():
                try:
                    d_start = datetime.strptime(specific_date.strip(), '%Y-%m-%d').date()
                except ValueError:
                    d_start = today
            elif isinstance(specific_date, (date, datetime)):
                d_start = specific_date if isinstance(specific_date, date) else specific_date.date()
            else:
                d_start = today
            d_end = d_start
            label = f"Date: {d_start.strftime('%d %B %Y')}"

        # 3. THIS WEEK (Monday to Sunday)
        elif period == ReportPeriodOption.THIS_WEEK:
            d_start = today - timedelta(days=today.weekday())
            d_end = d_start + timedelta(days=6)
            label = f"This Week ({d_start.strftime('%d %b %Y')} – {d_end.strftime('%d %b %Y')})"

        # 4. SPECIFIC WEEK (e.g. "2026-W38" or date within the week)
        elif period == ReportPeriodOption.SPECIFIC_WEEK:
            d_target = today
            if isinstance(specific_week, str) and specific_week.strip():
                val = specific_week.strip()
                if '-W' in val:
                    try:
                        # ISO week format: YYYY-Www
                        year_str, week_str = val.split('-W')
                        d_target = date.fromisocalendar(int(year_str), int(week_str), 1)
                    except (ValueError, TypeError):
                        d_target = today
                else:
                    try:
                        d_target = datetime.strptime(val, '%Y-%m-%d').date()
                    except ValueError:
                        d_target = today
            elif isinstance(specific_week, (date, datetime)):
                d_target = specific_week if isinstance(specific_week, date) else specific_week.date()

            d_start = d_target - timedelta(days=d_target.weekday())
            d_end = d_start + timedelta(days=6)
            iso_year, iso_week, _ = d_start.isocalendar()
            label = f"Week {iso_week}, {iso_year} ({d_start.strftime('%d %b %Y')} – {d_end.strftime('%d %b %Y')})"

        # 5. THIS MONTH
        elif period == ReportPeriodOption.THIS_MONTH:
            d_start = date(today.year, today.month, 1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            d_end = date(today.year, today.month, last_day)
            label = f"This Month ({today.strftime('%B %Y')})"

        # 6. SPECIFIC MONTH (e.g. month=9, year=2026 or "2026-09")
        elif period == ReportPeriodOption.SPECIFIC_MONTH:
            target_year = today.year
            target_month = today.month

            if specific_month:
                if isinstance(specific_month, str) and '-' in specific_month:
                    parts = specific_month.split('-')
                    try:
                        target_year = int(parts[0])
                        target_month = int(parts[1])
                    except (ValueError, IndexError):
                        pass
                else:
                    try:
                        target_month = int(specific_month)
                    except (ValueError, TypeError):
                        pass

            if specific_year:
                try:
                    target_year = int(specific_year)
                except (ValueError, TypeError):
                    pass

            target_month = max(1, min(12, target_month))
            last_day = calendar.monthrange(target_year, target_month)[1]
            d_start = date(target_year, target_month, 1)
            d_end = date(target_year, target_month, last_day)
            month_name = calendar.month_name[target_month]
            label = f"{month_name} {target_year}"

        # 7. THIS YEAR
        elif period == ReportPeriodOption.THIS_YEAR:
            d_start = date(today.year, 1, 1)
            d_end = date(today.year, 12, 31)
            label = f"Year {today.year}"

        # 8. SPECIFIC YEAR
        elif period == ReportPeriodOption.SPECIFIC_YEAR:
            target_year = today.year
            if specific_year:
                try:
                    target_year = int(specific_year)
                except (ValueError, TypeError):
                    pass
            d_start = date(target_year, 1, 1)
            d_end = date(target_year, 12, 31)
            label = f"Year {target_year}"

        # 9. CUSTOM RANGE
        elif period == ReportPeriodOption.CUSTOM:
            d_start = today
            d_end = today
            if start_date:
                if isinstance(start_date, str) and start_date.strip():
                    try:
                        d_start = datetime.strptime(start_date.strip(), '%Y-%m-%d').date()
                    except ValueError:
                        d_start = today
                elif isinstance(start_date, (date, datetime)):
                    d_start = start_date if isinstance(start_date, date) else start_date.date()

            if end_date:
                if isinstance(end_date, str) and end_date.strip():
                    try:
                        d_end = datetime.strptime(end_date.strip(), '%Y-%m-%d').date()
                    except ValueError:
                        d_end = d_start
                elif isinstance(end_date, (date, datetime)):
                    d_end = end_date if isinstance(end_date, date) else end_date.date()

            # Ensure d_start <= d_end
            if d_start > d_end:
                d_start, d_end = d_end, d_start

            label = f"{d_start.strftime('%d %b %Y')} – {d_end.strftime('%d %b %Y')}"

        else:
            d_start = today
            d_end = today
            label = f"Today ({today.strftime('%d %B %Y')})"

        # Convert date range to boundary datetimes in local timezone
        naive_start = datetime.combine(d_start, datetime.min.time())
        naive_end = datetime.combine(d_end, datetime.max.time())
        aware_start = timezone.make_aware(naive_start, current_tz)
        aware_end = timezone.make_aware(naive_end, current_tz)

        return {
            'period': period,
            'start_date': d_start,
            'end_date': d_end,
            'start_datetime': aware_start,
            'end_datetime': aware_end,
            'label': label,
        }

    @classmethod
    def get_filtered_movements(
        cls,
        shop=None,
        period=ReportPeriodOption.TODAY,
        specific_date=None,
        specific_week=None,
        specific_month=None,
        specific_year=None,
        start_date=None,
        end_date=None,
        user_id=None,
        movement_type=None,
        product_id=None,
        search_query=None,
        tz=None
    ):
        """
        Builds the filtered StockMovement queryset with select_related joins.
        """
        period_data = cls.resolve_period_range(
            period=period,
            specific_date=specific_date,
            specific_week=specific_week,
            specific_month=specific_month,
            specific_year=specific_year,
            start_date=start_date,
            end_date=end_date,
            tz=tz
        )

        qs = StockMovement.objects.select_related(
            'product',
            'product__category',
            'user',
            'location',
            'destination_location',
            'shop'
        ).filter(
            created_at__gte=period_data['start_datetime'],
            created_at__lte=period_data['end_datetime']
        )

        if shop:
            qs = qs.filter(shop=shop)

        # User filter
        if user_id:
            qs = qs.filter(user_id=user_id)

        # Movement type filter
        if movement_type and movement_type.upper() != 'ALL':
            qs = qs.filter(type=movement_type.upper())

        # Product filter
        if product_id:
            qs = qs.filter(product_id=product_id)

        # Free text search
        if search_query and search_query.strip():
            q = search_query.strip()
            qs = qs.filter(
                Q(product__name__icontains=q) |
                Q(product__sku__icontains=q) |
                Q(reason__icontains=q) |
                Q(reference__icontains=q) |
                Q(user__username__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q)
            )

        return qs.order_by('-created_at'), period_data

    @classmethod
    def calculate_summary(cls, queryset, period_data=None):
        """
        Calculates comprehensive summary metrics for a queryset of StockMovement records.
        """
        total_count = queryset.count()

        in_movements = queryset.filter(type=StockMovementType.IN)
        out_movements = queryset.filter(type=StockMovementType.OUT)
        adjust_movements = queryset.filter(type=StockMovementType.ADJUSTMENT)
        transfer_movements = queryset.filter(type__in=[
            StockMovementType.TRANSFER,
            StockMovementType.TRANSFER_IN,
            StockMovementType.TRANSFER_OUT
        ])

        in_count = in_movements.count()
        in_units = in_movements.aggregate(total=Sum('quantity'))['total'] or 0

        out_count = out_movements.count()
        out_units = out_movements.aggregate(total=Sum('quantity'))['total'] or 0

        adjust_count = adjust_movements.count()
        adjust_units = adjust_movements.aggregate(total=Sum('quantity'))['total'] or 0

        transfer_count = transfer_movements.count()
        transfer_units = transfer_movements.aggregate(total=Sum('quantity'))['total'] or 0

        # Unique products affected
        unique_products_count = queryset.values('product_id').distinct().count()

        # Unique operators involved
        unique_users_count = queryset.exclude(user__isnull=True).values('user_id').distinct().count()

        # Most active operator
        most_active_user_row = (
            queryset.exclude(user__isnull=True)
            .values('user__id', 'user__username', 'user__first_name', 'user__last_name', 'user__role')
            .annotate(tx_count=Count('id'))
            .order_by('-tx_count')
            .first()
        )

        # Products with the highest throughput
        top_products = (
            queryset.values('product__id', 'product__name', 'product__sku')
            .annotate(
                total_qty=Sum('quantity'),
                total_tx=Count('id')
            )
            .order_by('-total_qty')[:5]
        )

        # Period chronological breakdown (for monthly/yearly views)
        period_type = period_data.get('period') if period_data else None
        timeline_breakdown = []

        if period_type in [ReportPeriodOption.THIS_YEAR, ReportPeriodOption.SPECIFIC_YEAR]:
            # 12-month breakdown
            for m in range(1, 13):
                m_qs = queryset.filter(created_at__month=m)
                m_in = m_qs.filter(type=StockMovementType.IN).aggregate(u=Sum('quantity'))['u'] or 0
                m_out = m_qs.filter(type=StockMovementType.OUT).aggregate(u=Sum('quantity'))['u'] or 0
                m_adj = m_qs.filter(type=StockMovementType.ADJUSTMENT).count()
                m_tx = m_qs.count()
                if m_tx > 0:
                    timeline_breakdown.append({
                        'label': calendar.month_name[m],
                        'short_label': calendar.month_abbr[m],
                        'tx_count': m_tx,
                        'in_units': m_in,
                        'out_units': m_out,
                        'adj_count': m_adj,
                    })

        elif period_type in [ReportPeriodOption.THIS_MONTH, ReportPeriodOption.SPECIFIC_MONTH, ReportPeriodOption.THIS_WEEK, ReportPeriodOption.SPECIFIC_WEEK]:
            # Day-by-day breakdown
            start_date = period_data['start_date']
            end_date = period_data['end_date']
            cur_date = end_date
            while cur_date >= start_date:
                d_qs = queryset.filter(created_at__date=cur_date)
                d_tx = d_qs.count()
                if d_tx > 0:
                    d_in = d_qs.filter(type=StockMovementType.IN).aggregate(u=Sum('quantity'))['u'] or 0
                    d_out = d_qs.filter(type=StockMovementType.OUT).aggregate(u=Sum('quantity'))['u'] or 0
                    timeline_breakdown.append({
                        'label': cur_date.strftime('%a, %d %b %Y'),
                        'short_label': cur_date.strftime('%d %b'),
                        'tx_count': d_tx,
                        'in_units': d_in,
                        'out_units': d_out,
                    })
                cur_date -= timedelta(days=1)

        return {
            'total_transactions': total_count,
            'stock_in_count': in_count,
            'stock_in_units': in_units,
            'stock_out_count': out_count,
            'stock_out_units': out_units,
            'adjust_count': adjust_count,
            'adjust_units': adjust_units,
            'transfer_count': transfer_count,
            'transfer_units': transfer_units,
            'unique_products_count': unique_products_count,
            'unique_users_count': unique_users_count,
            'most_active_user': most_active_user_row,
            'top_products': top_products,
            'timeline_breakdown': timeline_breakdown,
        }
