from datetime import date, datetime, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import StoreSetting, UserRole
from inventory.models import Category, InventoryLocation, Product
from stock.models import StockMovement, StockMovementType
from .services import ReportPeriodOption, TransactionReportService

User = get_user_model()


class TransactionReportsTestCase(TestCase):
    def setUp(self):
        # 1. Setup Store
        self.store = StoreSetting.objects.create(
            name="StockFlow Mega Supermarket",
            branch_name="Capital Branch",
            address="Nairobi, Kenya",
            tax_pin="P051234567Z",
            currency_symbol="KES"
        )

        # 2. Setup Users
        self.admin_user = User.objects.create_user(
            username="admin_alice",
            password="password123",
            role=UserRole.ADMIN,
            shop=self.store,
            first_name="Alice",
            last_name="Auditor"
        )
        self.manager_user = User.objects.create_user(
            username="manager_bob",
            password="password123",
            role=UserRole.MANAGER,
            shop=self.store,
            first_name="Bob",
            last_name="Manager"
        )
        self.staff_user = User.objects.create_user(
            username="staff_charlie",
            password="password123",
            role=UserRole.STAFF,
            shop=self.store,
            first_name="Charlie",
            last_name="Clerk"
        )

        # 3. Setup Inventory
        self.category = Category.objects.create(name="Dairy & Bakery", shop=self.store)
        self.location = InventoryLocation.objects.create(name="Central Floor", code="FL1", shop=self.store)

        self.milk = Product.objects.create(
            name="Fresh Whole Milk 1L",
            sku="MLK001",
            category=self.category,
            price=Decimal("120.00"),
            quantity=100,
            minimum_stock=10,
            shop=self.store
        )
        self.bread = Product.objects.create(
            name="Farm Bread 400g",
            sku="BRD001",
            category=self.category,
            price=Decimal("65.00"),
            quantity=50,
            minimum_stock=5,
            shop=self.store
        )

        # Base Reference Date
        self.tz = timezone.get_current_timezone()
        self.now = timezone.localtime(timezone.now(), self.tz)
        self.today = self.now.date()

        # 4. Create Historical and Today Transactions
        # Tx 1: Today, by Manager Bob, Stock IN Milk 50
        self.tx_today_in = StockMovement.objects.create(
            shop=self.store,
            product=self.milk,
            location=self.location,
            type=StockMovementType.IN,
            quantity=50,
            previous_quantity=50,
            new_quantity=100,
            reason="Supplier Delivery",
            reference="PO-2026-001",
            user=self.manager_user
        )

        # Tx 2: Today, by Staff Charlie, Stock OUT Milk 10
        self.tx_today_out = StockMovement.objects.create(
            shop=self.store,
            product=self.milk,
            location=self.location,
            type=StockMovementType.OUT,
            quantity=10,
            previous_quantity=100,
            new_quantity=90,
            reason="Customer Retail Sale",
            reference="POS-REC-101",
            user=self.staff_user
        )

        # Tx 3: Today, by Admin Alice, Stock Adjustment Bread 5
        self.tx_today_adj = StockMovement.objects.create(
            shop=self.store,
            product=self.bread,
            location=self.location,
            type=StockMovementType.ADJUSTMENT,
            quantity=5,
            previous_quantity=45,
            new_quantity=50,
            reason="Stock Audit Reconciliation",
            reference="AUDIT-2026-A",
            user=self.admin_user
        )

        # Tx 4: 10 Days Ago, by Manager Bob, Stock IN Bread 20
        ten_days_ago = timezone.make_aware(
            datetime.combine(self.today - timedelta(days=10), datetime.min.time().replace(hour=10)),
            self.tz
        )
        self.tx_past_in = StockMovement.objects.create(
            shop=self.store,
            product=self.bread,
            location=self.location,
            type=StockMovementType.IN,
            quantity=20,
            previous_quantity=25,
            new_quantity=45,
            reason="Supplier Restock",
            reference="PO-PAST-01",
            user=self.manager_user
        )
        StockMovement.objects.filter(pk=self.tx_past_in.pk).update(created_at=ten_days_ago)

        # Tx 5: 40 Days Ago (Previous Month), by Staff Charlie, Stock OUT Bread 8
        forty_days_ago = timezone.make_aware(
            datetime.combine(self.today - timedelta(days=40), datetime.min.time().replace(hour=14)),
            self.tz
        )
        self.tx_prev_month = StockMovement.objects.create(
            shop=self.store,
            product=self.bread,
            location=self.location,
            type=StockMovementType.OUT,
            quantity=8,
            previous_quantity=33,
            new_quantity=25,
            reason="Damaged Disposal",
            reference="DAM-001",
            user=self.staff_user
        )
        StockMovement.objects.filter(pk=self.tx_prev_month.pk).update(created_at=forty_days_ago)

        self.client = Client()

    # 1. Daily filtering
    def test_daily_filtering_today(self):
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.TODAY,
            tz=self.tz
        )
        self.assertEqual(qs.count(), 3)
        pks = [m.pk for m in qs]
        self.assertIn(self.tx_today_in.pk, pks)
        self.assertIn(self.tx_today_out.pk, pks)
        self.assertIn(self.tx_today_adj.pk, pks)
        self.assertNotIn(self.tx_past_in.pk, pks)

    def test_daily_filtering_specific_date(self):
        target_date = self.today - timedelta(days=10)
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.SPECIFIC_DATE,
            specific_date=target_date.strftime('%Y-%m-%d'),
            tz=self.tz
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.tx_past_in.pk)

    # 2. Weekly filtering
    def test_weekly_filtering(self):
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_WEEK,
            tz=self.tz
        )
        # Should include movements from this week
        for m in qs:
            self.assertGreaterEqual(m.created_at, period_data['start_datetime'])
            self.assertLessEqual(m.created_at, period_data['end_datetime'])

    # 3. Monthly filtering
    def test_monthly_filtering_this_month(self):
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_MONTH,
            tz=self.tz
        )
        # tx_prev_month occurred 40 days ago and should NOT be in this month
        self.assertNotIn(self.tx_prev_month.pk, [m.pk for m in qs])
        self.assertIn(self.tx_today_in.pk, [m.pk for m in qs])

    # 4. Yearly filtering
    def test_yearly_filtering(self):
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_YEAR,
            tz=self.tz
        )
        # Movements within the current year should be captured
        self.assertIn(self.tx_today_in.pk, [m.pk for m in qs])
        self.assertIn(self.tx_today_out.pk, [m.pk for m in qs])

    # 5. Custom date range
    def test_custom_date_range(self):
        start = self.today - timedelta(days=15)
        end = self.today - timedelta(days=5)
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.CUSTOM,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            tz=self.tz
        )
        # tx_past_in was 10 days ago -> fits in range
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.tx_past_in.pk)

    # 6. User filtering
    def test_user_filtering(self):
        # Filter for Manager Bob
        qs, _ = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_YEAR,
            user_id=self.manager_user.id,
            tz=self.tz
        )
        self.assertEqual(qs.count(), 2)
        for m in qs:
            self.assertEqual(m.user, self.manager_user)

        # Filter for Staff Charlie
        qs_charlie, _ = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_YEAR,
            user_id=self.staff_user.id,
            tz=self.tz
        )
        self.assertEqual(qs_charlie.count(), 2)
        for m in qs_charlie:
            self.assertEqual(m.user, self.staff_user)

    # 7. Transaction type filtering
    def test_transaction_type_filtering(self):
        qs_out, _ = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_YEAR,
            movement_type=StockMovementType.OUT,
            tz=self.tz
        )
        self.assertEqual(qs_out.count(), 2)
        for m in qs_out:
            self.assertEqual(m.type, StockMovementType.OUT)

        qs_in, _ = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.THIS_YEAR,
            movement_type=StockMovementType.IN,
            tz=self.tz
        )
        self.assertEqual(qs_in.count(), 2)
        for m in qs_in:
            self.assertEqual(m.type, StockMovementType.IN)

    # 8. Combined filtering
    def test_combined_filters(self):
        # Date: Today + User: Charlie + Type: OUT
        qs, _ = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.TODAY,
            user_id=self.staff_user.id,
            movement_type=StockMovementType.OUT,
            tz=self.tz
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.tx_today_out.pk)

    # 9. Admin transaction tracing & receipt number
    def test_transaction_traceability(self):
        self.assertEqual(self.tx_today_in.receipt_number, f"SF-REC-{self.tx_today_in.id:05d}")
        self.assertEqual(self.tx_today_in.user.get_role_display(), 'Manager')
        self.assertEqual(self.tx_today_in.product.sku, 'MLK001')
        self.assertEqual(self.tx_today_in.quantity, 50)
        self.assertEqual(self.tx_today_in.reason, "Supplier Delivery")

    # 10. Receipt generation views
    def test_receipt_generation_views(self):
        self.client.force_login(self.admin_user)
        # HTML Receipt
        res_receipt = self.client.get(reverse('transaction_receipt'), {'period': 'today'})
        self.assertEqual(res_receipt.status_code, 200)
        self.assertContains(res_receipt, "INVENTORY TRANSACTION RECEIPT")
        self.assertContains(res_receipt, "MLK001")
        self.assertContains(res_receipt, "Fresh Whole Milk 1L")

        # PDF Receipt Export
        res_pdf = self.client.get(reverse('export_receipt_pdf'), {'period': 'today'})
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')

    # 11. Empty report periods
    def test_empty_report_period(self):
        # Far future date
        future_date = self.today + timedelta(days=365)
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.SPECIFIC_DATE,
            specific_date=future_date.strftime('%Y-%m-%d'),
            tz=self.tz
        )
        self.assertEqual(qs.count(), 0)
        summary = TransactionReportService.calculate_summary(qs, period_data)
        self.assertEqual(summary['total_transactions'], 0)
        self.assertEqual(summary['stock_in_units'], 0)
        self.assertEqual(summary['stock_out_units'], 0)

        # Web page with empty results
        self.client.force_login(self.manager_user)
        res = self.client.get(reverse('transaction_reports'), {
            'period': 'specific_date',
            'specific_date': future_date.strftime('%Y-%m-%d')
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "No stock movements found")

    # 12. Permission restrictions
    def test_permission_restrictions(self):
        # Unauthenticated user redirected to login
        res_anon = self.client.get(reverse('transaction_reports'))
        self.assertEqual(res_anon.status_code, 302)

        # Staff user redirected to dashboard when accessing manager-only views
        self.client.force_login(self.staff_user)
        res_staff = self.client.get(reverse('transaction_reports'))
        self.assertEqual(res_staff.status_code, 302)
        self.assertRedirects(res_staff, reverse('dashboard'))

        # Manager user permitted
        self.client.force_login(self.manager_user)
        res_manager = self.client.get(reverse('transaction_reports'))
        self.assertEqual(res_manager.status_code, 200)

        # Admin user permitted
        self.client.force_login(self.admin_user)
        res_admin = self.client.get(reverse('transaction_reports'))
        self.assertEqual(res_admin.status_code, 200)

    # 13. Correct transaction totals
    def test_correct_transaction_totals(self):
        qs, period_data = TransactionReportService.get_filtered_movements(
            shop=self.store,
            period=ReportPeriodOption.TODAY,
            tz=self.tz
        )
        summary = TransactionReportService.calculate_summary(qs, period_data)
        self.assertEqual(summary['total_transactions'], 3)
        self.assertEqual(summary['stock_in_count'], 1)
        self.assertEqual(summary['stock_in_units'], 50)
        self.assertEqual(summary['stock_out_count'], 1)
        self.assertEqual(summary['stock_out_units'], 10)
        self.assertEqual(summary['adjust_count'], 1)
        self.assertEqual(summary['adjust_units'], 5)
        self.assertEqual(summary['unique_products_count'], 2)  # Milk & Bread
        self.assertEqual(summary['unique_users_count'], 3)

    # 14. Correct date boundaries
    def test_date_boundaries(self):
        period_data = TransactionReportService.resolve_period_range(
            period=ReportPeriodOption.SPECIFIC_DATE,
            specific_date="2026-09-24",
            tz=self.tz
        )
        # Check start time is 00:00:00
        self.assertEqual(period_data['start_datetime'].hour, 0)
        self.assertEqual(period_data['start_datetime'].minute, 0)
        self.assertEqual(period_data['start_datetime'].second, 0)

        # Check end time is 23:59:59.999999
        self.assertEqual(period_data['end_datetime'].hour, 23)
        self.assertEqual(period_data['end_datetime'].minute, 59)
        self.assertEqual(period_data['end_datetime'].second, 59)

    # 15. Existing reports still work
    def test_existing_reports_still_work(self):
        self.client.force_login(self.manager_user)
        res = self.client.get(reverse('reports'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Store Inventory Report & Valuation Audit")
        self.assertContains(res, "Fresh Whole Milk 1L")

        # CSV export still works
        res_csv = self.client.get(reverse('reports'), {'export': 'csv'})
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
        self.assertIn(b"Fresh Whole Milk 1L", res_csv.content)

    # DRF API endpoint test
    def test_api_reports_transactions(self):
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse('api_transaction_reports'), {'period': 'today'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('summary', data)
        self.assertIn('transactions', data)
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['transactions'][0]['product_sku'], 'MLK001')
