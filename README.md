# StockFlow — Smart Inventory & Stock Management System

StockFlow is a production-quality Smart Inventory & Stock Management MVP web application engineered for retail supermarkets, mini-markets, convenience stores, and retail businesses.

Built with Python, Django 6, Bootstrap 5, and Vanilla JavaScript, StockFlow replaces paper ledger books and static spreadsheets with an authoritative stock status engine, atomic movement tracking, transition-triggered alert notifications, role-based access control, and executive analytics.

---

## Key Features

- **Authoritative Stock Status Engine**:
  - `OUT OF STOCK`: Quantity is exactly 0.
  - `LOW STOCK`: Quantity is greater than 0 and less than or equal to the minimum threshold.
  - `IN STOCK`: Quantity is safely above the minimum threshold.
- **Stock Movement Engine & Audit Trail**:
  - Every inventory addition (`IN`), dispatch/sale (`OUT`), or audit reconciliation (`ADJUSTMENT`) creates an immutable `StockMovement` audit record.
  - Uses `django.db.transaction.atomic()` and row-level locking (`select_for_update()`) to prevent race conditions.
  - Strictly prevents negative inventory (dispatches exceeding current stock are blocked).
  - Every action tracks user identity, quantity before/after, reason, and reference number.
- **Transition-Based Smart Alerts**:
  - Automatically generates in-app notifications for Admins and Managers only when a product *crosses* a threshold (`IN_STOCK` &rarr; `LOW_STOCK` or `LOW_STOCK` &rarr; `OUT_OF_STOCK`).
  - Prevents alert fatigue and duplicate spamming on routine page views.
  - Live notification bell with unread badge counter, popover preview, and asynchronous mark-as-read.
- **Executive KPI Dashboard**:
  - Real-time catalog counts, total units, low-stock count, out-of-stock count, and total retail inventory valuation (KES).
  - Visual segmented inventory health distribution bar.
  - Attention-required product list with 1-click quick restock triggers.
  - Recent stock movement audit stream.
- **Role-Based Access Control (RBAC)**:
  - **ADMIN**: Full system access, team member provisioning, role assignments, system settings, catalog, movements, reports.
  - **MANAGER**: Product CRUD, category & supplier management, stock movements, reports, alerts.
  - **STAFF / CASHIER**: Product search & browsing, permitted stock operations (Stock IN, Stock OUT). Restricted from administrative settings and deletion.
- **Inventory & Catalog Management**:
  - Instant live search by Product Name or SKU.
  - Multi-factor filtering by Category, Supplier, and Stock Status.
  - Sorting by Name, Price, or Stock level.
  - Product detail views with visual capacity gauges and movement history.
- **Suppliers & Categories Directory**:
  - Maintain vendor contacts, addresses, and see all items sourced from each supplier.
  - Categorize products with safe deletion checks.
- **Reports & Valuation**:
  - Store-wide valuation breakdown by department/category.
  - Throughput analysis (total units received vs dispatched vs reconciled).
  - 1-click CSV report export and printable layout.

---

## Technology Stack

- **Backend**: Python 3.12, Django 6.0, Django REST Framework
- **Database**: SQLite with relational schema, foreign key constraints, and unique indexes
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System tokens `#181d2e` and `#3c453e`), Bootstrap 5.3, Bootstrap Icons
- **Scripting**: Vanilla JavaScript, Fetch API (asynchronous notifications and modal operations)

---

## Project Structure

```
d:/Supermarket_app/
├── manage.py
├── requirements.txt
├── README.md
├── config/
│   ├── settings.py           # Application configuration, brand tokens, auth settings
│   ├── urls.py               # Top-level SaaS URL routing
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                 # Custom User model, RBAC decorators, authentication
│   ├── models.py             # User model with role choices (ADMIN, MANAGER, STAFF)
│   ├── forms.py              # Login, User CRUD, Profile & Password change forms
│   ├── views.py              # Auth views, user directory, settings
│   ├── decorators.py         # @admin_required, @manager_required, @staff_required
│   ├── context_processors.py # Global template role flags
│   └── management/commands/seed_data.py # Realistic supermarket demo seeder
├── inventory/                # Product, Category, and Supplier domain
│   ├── models.py             # Product, Category, Supplier models with StockStatus engine
│   ├── forms.py              # ProductForm, CategoryForm, SupplierForm
│   ├── views.py              # Catalog list, search, filter, CRUD, detail pages
│   └── urls.py
├── stock/                    # Transactional stock movements
│   ├── models.py             # StockMovement model (IN, OUT, ADJUSTMENT)
│   ├── services.py           # Atomic StockMovementService with concurrency locking
│   ├── forms.py              # StockInForm, StockOutForm, StockAdjustmentForm
│   └── views.py              # Audit ledger, stock in/out endpoints
├── notifications/            # In-app notifications
│   ├── models.py             # Notification model with types (LOW_STOCK, OUT_OF_STOCK)
│   ├── services.py           # State transition alert trigger service
│   ├── context_processors.py # Live unread count & topbar preview
│   └── views.py              # Notification list & AJAX mark-read endpoints
├── dashboard/                # Executive analytics dashboard
│   ├── views.py              # Real database aggregation calculations
│   └── urls.py
├── reports/                  # Valuation, throughput, and CSV export
│   ├── views.py              # Category breakdown, CSV export, date filters
│   └── urls.py
├── static/
│   ├── css/
│   │   ├── style.css         # Brand tokens (#181d2e, #3c453e), badges, buttons, tables
│   │   └── dashboard.css     # Responsive sidebar, topbar, KPI cards, health bars
│   └── js/
│       ├── app.js            # Mobile sidebar toggle, CSRF helpers, quick stock modals
│       └── dashboard.js      # Live polling for notifications unread count
└── templates/
    ├── base.html             # Public layout
    ├── base_app.html         # Authenticated SaaS app shell
    ├── home.html             # Public marketing landing page
    ├── auth/login.html       # Split-screen SaaS authentication page
    ├── dashboard/dashboard.html
    ├── inventory/            # Product list, form, detail, confirm delete
    ├── categories/           # Category directory, modal, edit, delete
    ├── suppliers/            # Supplier directory, detail, edit, delete
    ├── stock/                # Stock ledger audit stream and record form
    ├── notifications/        # Notification center
    ├── reports/              # Valuation reports and export
    ├── users/                # Team & role access management
    ├── settings/             # Personal profile & diagnostics
    └── components/           # Reusable sidebar, topbar, alerts, pagination, modals
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Git

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Seed Realistic Demo Data
Run the built-in management command to seed supermarket categories, suppliers, catalog products across diverse stock states, and demo accounts:
```bash
python manage.py seed_data
```

---

## Demo Credentials

The seed command creates three pre-configured accounts with distinct operational roles:

| Role | Username | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `AdminPass123!` | Full access: User management, settings, inventory, movements, reports |
| **Store Manager** | `manager` | `ManagerPass123!` | Products, categories, suppliers, stock movements, reports, notifications |
| **Staff / Cashier** | `staff` | `StaffPass123!` | Product search, view inventory, record Stock IN / OUT |

*Note: The login page at `/login/` features 1-click demo buttons to automatically populate these credentials for quick evaluation.*

---

## Running the Server

Start the Django development server:
```bash
python manage.py runserver
```

Open your browser and navigate to:
- **Public Homepage**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Sign In Page**: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- **Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Inventory Catalog**: [http://127.0.0.1:8000/inventory/](http://127.0.0.1:8000/inventory/)
- **Stock Movement Ledger**: [http://127.0.0.1:8000/stock-movements/](http://127.0.0.1:8000/stock-movements/)
- **Categories**: [http://127.0.0.1:8000/categories/](http://127.0.0.1:8000/categories/)
- **Suppliers**: [http://127.0.0.1:8000/suppliers/](http://127.0.0.1:8000/suppliers/)
- **Notifications Hub**: [http://127.0.0.1:8000/notifications/](http://127.0.0.1:8000/notifications/)
- **Executive Reports**: [http://127.0.0.1:8000/reports/](http://127.0.0.1:8000/reports/)
- **User Management (Admin)**: [http://127.0.0.1:8000/users/](http://127.0.0.1:8000/users/)
- **Settings**: [http://127.0.0.1:8000/settings/](http://127.0.0.1:8000/settings/)

---

## Running Automated Tests

Execute the test suite to verify all business rules:
```bash
python manage.py test
```
The test suite validates:
- Authentication & role access restriction enforcement
- Product creation, update, deletion, and SKU uniqueness
- Authoritative stock status transitions (`IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`)
- Atomic stock IN and OUT operations with non-negative stock enforcement
- Threshold crossing notifications to Admin and Manager accounts
- Notification mark-as-read and live unread counting

---

## Future Roadmap (Post-MVP)

- Barcode scanning via hardware scanners and mobile camera
- POS Cashier Terminal with offline receipt printing
- Multi-branch warehouse transfers and central distribution
- Automated reorder purchase orders generated directly to suppliers
- Customer loyalty and sales analytics
