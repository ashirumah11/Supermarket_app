from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserRole
from inventory.models import Category, Product, Supplier
from stock.models import StockMovementType
from stock.services import StockMovementService

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with realistic retail supermarket demo data, users, and audit trail.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding StockFlow demo dataset..."))

        # 1. Create Demo Users
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@stockflow.internal',
                'password': 'AdminPass123!',
                'first_name': 'Sarah',
                'last_name': 'Omondi',
                'role': UserRole.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'phone': '+254 711 100 200'
            },
            {
                'username': 'manager',
                'email': 'manager@stockflow.internal',
                'password': 'ManagerPass123!',
                'first_name': 'David',
                'last_name': 'Kiprono',
                'role': UserRole.MANAGER,
                'is_staff': True,
                'is_superuser': False,
                'phone': '+254 722 300 400'
            },
            {
                'username': 'staff',
                'email': 'staff@stockflow.internal',
                'password': 'StaffPass123!',
                'first_name': 'Grace',
                'last_name': 'Wanjiru',
                'role': UserRole.STAFF,
                'is_staff': False,
                'is_superuser': False,
                'phone': '+254 733 500 600'
            },
        ]

        created_users = {}
        for udata in users_data:
            user, created = User.objects.get_or_create(
                username=udata['username'],
                defaults={
                    'email': udata['email'],
                    'first_name': udata['first_name'],
                    'last_name': udata['last_name'],
                    'role': udata['role'],
                    'is_staff': udata['is_staff'],
                    'is_superuser': udata['is_superuser'],
                    'phone': udata['phone'],
                }
            )
            user.set_password(udata['password'])
            user.role = udata['role']
            user.save()
            created_users[udata['username']] = user
            status_text = "Created" if created else "Updated"
            self.stdout.write(f"  [{status_text}] User: {user.username} ({user.get_role_display()})")

        admin_user = created_users['admin']
        manager_user = created_users['manager']
        staff_user = created_users['staff']

        # 2. Create Categories
        categories_data = [
            ('Beverages', 'Cold refreshments, mineral water, juices, and hot tea/coffee blends'),
            ('Groceries', 'Dry pantry staples, grains, cooking fats, sugars, and flours'),
            ('Household', 'Cleaning chemicals, laundry detergents, surface disinfectants, and paper goods'),
            ('Personal Care', 'Skin care, soaps, shampoos, oral hygiene, and grooming'),
            ('Dairy & Bakery', 'Fresh pasteurized milk, butter, cheese, sliced bread, and baked pastries'),
            ('Snacks & Confectionery', 'Chocolates, biscuits, potato crisps, and sweets'),
        ]

        created_categories = {}
        for cat_name, cat_desc in categories_data:
            cat, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': cat_desc}
            )
            created_categories[cat_name] = cat
        self.stdout.write(self.style.SUCCESS(f"  Configured {len(created_categories)} product categories."))

        # 3. Create Suppliers
        suppliers_data = [
            (
                'Nairobi Wholesale Ltd',
                '+254 711 000 111',
                'orders@nairobiwholesale.co.ke',
                'Plot 42, Enterprise Road, Industrial Area, Nairobi'
            ),
            (
                'East Africa Distributors',
                '+254 722 000 222',
                'sales@eadistributors.com',
                'Gateway Park, Mombasa Road, Nairobi'
            ),
            (
                'Metro Supplies & Logistics',
                '+254 733 000 333',
                'contact@metrosupplies.ke',
                'North Airport Road, Embakasi, Nairobi'
            ),
            (
                'Highland Fresh Traders',
                '+254 744 000 444',
                'logistics@highlandfresh.co.ke',
                'Limuru Cold Storage Hub, Kiambu County'
            ),
        ]

        created_suppliers = {}
        for sup_name, sup_phone, sup_email, sup_addr in suppliers_data:
            sup, _ = Supplier.objects.get_or_create(
                name=sup_name,
                defaults={'phone': sup_phone, 'email': sup_email, 'address': sup_addr}
            )
            created_suppliers[sup_name] = sup
        self.stdout.write(self.style.SUCCESS(f"  Configured {len(created_suppliers)} retail suppliers."))

        # 4. Products Specification with diverse stock levels
        # (name, sku, category, supplier, price, target_qty, min_stock, max_stock)
        products_spec = [
            # In Stock
            ('Mumias Pure White Sugar 1kg', 'SUG-1001', 'Groceries', 'Nairobi Wholesale Ltd', Decimal('180.00'), 50, 10, 150),
            ('Fresh Fri Vegetable Cooking Oil 2L', 'OIL-2002', 'Groceries', 'East Africa Distributors', Decimal('640.00'), 32, 8, 80),
            ('Daawat Long Grain Basmati Rice 2kg', 'RIC-3003', 'Groceries', 'Nairobi Wholesale Ltd', Decimal('495.00'), 40, 10, 100),
            ('Keringet Natural Mineral Water 1L', 'WAT-4004', 'Beverages', 'Metro Supplies & Logistics', Decimal('85.00'), 65, 15, 120),
            ('Geisha Aloe Vera Beauty Soap 200g', 'SOP-5005', 'Personal Care', 'East Africa Distributors', Decimal('95.00'), 48, 12, 100),
            ('Omo Hand Washing Powder 1kg', 'DET-6006', 'Household', 'Metro Supplies & Logistics', Decimal('320.00'), 25, 8, 60),
            ('Dettol Antiseptic Disinfectant 500ml', 'CLN-7007', 'Household', 'Nairobi Wholesale Ltd', Decimal('450.00'), 18, 5, 40),
            ('Colgate Triple Action Toothpaste 140g', 'DEN-8008', 'Personal Care', 'East Africa Distributors', Decimal('190.00'), 35, 10, 80),
            
            # Low Stock (triggers LOW_STOCK status and alerts)
            ('Brookside Fresh Whole Milk 500ml', 'MLK-9009', 'Dairy & Bakery', 'Highland Fresh Traders', Decimal('65.00'), 4, 12, 60),
            ('Supa Loaf Sliced White Bread 400g', 'BRD-1010', 'Dairy & Bakery', 'Highland Fresh Traders', Decimal('65.00'), 3, 10, 50),
            ('Pembe All Purpose Baking Flour 2kg', 'FLR-1111', 'Groceries', 'Nairobi Wholesale Ltd', Decimal('195.00'), 2, 8, 40),

            # Out of Stock (depleted, triggers OUT_OF_STOCK alerts)
            ('Dormans Instant Blend Coffee 100g', 'COF-1212', 'Beverages', 'Metro Supplies & Logistics', Decimal('390.00'), 0, 5, 40),
            ('Cadbury Dairy Milk Chocolate 80g', 'CHO-1313', 'Snacks & Confectionery', 'East Africa Distributors', Decimal('160.00'), 0, 8, 50),
        ]

        for p_name, p_sku, cat_name, sup_name, price, target_qty, min_stk, max_stk in products_spec:
            product, created = Product.objects.get_or_create(
                sku=p_sku,
                defaults={
                    'name': p_name,
                    'category': created_categories[cat_name],
                    'supplier': created_suppliers[sup_name],
                    'price': price,
                    'quantity': 0, # initialize at 0, then record realistic movements
                    'minimum_stock': min_stk,
                    'maximum_stock': max_stk,
                    'description': f"Premium quality {p_name} packaged for retail."
                }
            )

            # Record stock movements to establish initial ledger and realistic state transitions
            if target_qty > 0:
                StockMovementService.record_movement(
                    product=product,
                    movement_type=StockMovementType.IN,
                    quantity=target_qty,
                    user=manager_user,
                    reason="Warehouse Opening Restock Delivery",
                    reference="PO-INIT-2026"
                )
            else:
                # To simulate an out-of-stock product with audit trail:
                # In 10, then Out 10 to trigger state transition to OUT_OF_STOCK
                StockMovementService.record_movement(
                    product=product,
                    movement_type=StockMovementType.IN,
                    quantity=10,
                    user=manager_user,
                    reason="Initial Shipment Receipt",
                    reference="PO-INIT-TEMP"
                )
                StockMovementService.record_movement(
                    product=product,
                    movement_type=StockMovementType.OUT,
                    quantity=10,
                    user=staff_user,
                    reason="Complete Stock Sellout / Retail Depletion",
                    reference="POS-BATCH-01"
                )

            self.stdout.write(f"  Configured Product: {product.name} (SKU: {product.sku}) - Status: {product.stock_status_display} ({product.quantity} in stock)")

        # Record a couple of customer dispatch sales for variety
        sugar = Product.objects.get(sku='SUG-1001')
        StockMovementService.record_movement(
            product=sugar,
            movement_type=StockMovementType.OUT,
            quantity=5,
            user=staff_user,
            reason="Retail Cashier Checkout - Register #1",
            reference="REC-90041"
        )

        milk = Product.objects.get(sku='MLK-9009')
        StockMovementService.record_movement(
            product=milk,
            movement_type=StockMovementType.OUT,
            quantity=2,
            user=staff_user,
            reason="Counter Sales Dispatch",
            reference="REC-90042"
        )

        self.stdout.write(self.style.SUCCESS("\nStockFlow database successfully seeded!"))
        self.stdout.write("--------------------------------------------------")
        self.stdout.write("Demo Credentials:")
        self.stdout.write("  Admin:   username=admin   password=AdminPass123!   (Role: ADMIN)")
        self.stdout.write("  Manager: username=manager password=ManagerPass123! (Role: MANAGER)")
        self.stdout.write("  Staff:   username=staff   password=StaffPass123!   (Role: STAFF)")
        self.stdout.write("--------------------------------------------------")
