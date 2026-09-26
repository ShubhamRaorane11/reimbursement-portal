# ReimbursePro — Internal Corporate Employee Reimbursement Management Portal

A full-stack, internal corporate employee reimbursement management system built with Python, Flask, Jinja2, SQLAlchemy, and MySQL, featuring automated OCR receipt extraction via Tesseract, multi-tier approval workflows, and role-based access control.

---

## Architecture & Workflow

The portal enforces a strict internal organization business workflow:

```
[Employee] ──(Submits Request + Receipts)──► [Department Approver]
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
                     [Needs Correction]                                  [Approve]
                             │                                               │
                             └────────► (Resubmit)                           ▼
                                                                     [Finance Team]
                                                                             │
                                                                 ┌───────────┴───────────┐
                                                                 ▼                       ▼
                                                            [Processing]          [Reimbursed]
                                                                                  (Payment logged)
```

### Core Roles
- **Employee**: Create, save drafts, upload bills/receipts, auto-extract bill data via OCR, review, submit, track timelines, and resubmit if corrections are requested.
- **Department Approver**: Review department requests, inspect itemized expenses and uploaded proof documents, approve, reject with reason, or request corrections with notes.
- **Finance**: View approved reimbursements, initiate processing, record payment disbursements (mode, transaction reference, date, notes), and mark requests as reimbursed.
- **Admin**: System-wide dashboard with KPIs & Chart.js analytics, employee lifecycle management (add, edit, toggle status, reset password), department setup & approver assignment, expense categories CRUD, and org-wide audit view.

---

## Tech Stack

- **Backend**: Python 3.10+, Flask 3.1, Jinja2, Flask-SQLAlchemy 3.1, PyMySQL 1.1, Werkzeug (scrypt password hashing)
- **Database**: MySQL 8.0+ (InnoDB, `utf8mb4_unicode_ci`)
- **Frontend**: HTML5, Responsive CSS3 design system, Vanilla JavaScript (ES6+), Chart.js, Font Awesome 6
- **OCR Engine**: Tesseract OCR via `pytesseract`, `pdf2image`, Pillow (with regex-based field parsing for vendors, dates, amounts, taxes)

---

## Directory Structure

```
reimbursement-project/
├── MYSQL_DATABASE_SCRIPTS/
│   ├── 01_create_database.sql       # Database creation with UTF-8 encoding
│   ├── 02_create_tables.sql         # 9 relational tables with indexes & foreign keys
│   └── 03_seed_data.sql             # Demo departments, categories, users & requests
│
└── reimbursement_portal/
    ├── app/
    │   ├── __init__.py              # Flask app factory (create_app) & error handlers
    │   ├── models/                  # 9 SQLAlchemy models
    │   │   ├── user.py
    │   │   ├── department.py
    │   │   ├── expense_category.py
    │   │   ├── reimbursement.py
    │   │   ├── document.py
    │   │   ├── ocr_result.py
    │   │   ├── approval_history.py
    │   │   ├── payment.py
    │   │   └── notification.py
    │   ├── routes/                  # Blueprints
    │   │   ├── auth.py              # Login, logout, role-based redirection
    │   │   ├── employee.py          # Employee dashboard, new requests, OCR upload
    │   │   ├── approver.py          # Approver dashboard, review, approve/reject/correction
    │   │   ├── finance.py           # Finance dashboard, processing & payment logging
    │   │   └── admin.py             # Admin dashboard, user/dept/category CRUD
    │   ├── services/                # Business logic
    │   │   ├── ocr_service.py       # Tesseract OCR engine + regex extractor
    │   │   ├── reimbursement_service.py # Workflow state machine & numbering
    │   │   └── notification_service.py  # In-app notification dispatcher
    │   ├── static/                  # CSS stylesheets & client JavaScript
    │   │   ├── css/                 # main.css, auth.css, dashboard.css
    │   │   └── js/                  # main.js, employee.js, ocr.js, approver.js, finance.js
    │   └── templates/               # Jinja2 templates (role-based directories)
    ├── uploads/                     # Protected receipt uploads directory
    ├── config.py                    # Environment & database configuration
    ├── run.py                       # Application entry point
    ├── requirements.txt             # Python dependencies
    ├── .env.example                 # Example configuration
    └── README.md
```

---

## Prerequisites & Installation

### 1. Database Setup (MySQL)
Execute the SQL scripts in order using MySQL Workbench or MySQL CLI:

```bash
mysql -u root -p < ../MYSQL_DATABASE_SCRIPTS/01_create_database.sql
mysql -u root -p < ../MYSQL_DATABASE_SCRIPTS/02_create_tables.sql
mysql -u root -p < ../MYSQL_DATABASE_SCRIPTS/03_seed_data.sql
```

### 2. Python Environment & Dependencies
Create and activate a virtual environment:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. OCR Setup (Optional but Recommended)
The application works fully without OCR installed (manual entry fallback is built-in). For automatic bill scanning:
1. **Tesseract OCR**:
   - **Windows**: Download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`).
   - **Linux**: `sudo apt-get install tesseract-ocr`
   - **macOS**: `brew install tesseract`
2. **Poppler (for PDF receipt conversion)**:
   - **Windows**: Download poppler binary and add `bin/` to system `PATH`.
   - **Linux**: `sudo apt-get install poppler-utils`
   - **macOS**: `brew install poppler`

### 4. Configuration (`.env`)
Copy `.env.example` to `.env` and set your credentials:

```ini
DB_HOST=localhost
DB_PORT=3306
DB_NAME=reimbursement_portal
DB_USER=root
DB_PASSWORD=your_mysql_password
SECRET_KEY=generate-a-secure-random-secret-key
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## Running the Application

Start the Flask development server:

```bash
python run.py
```

The portal will be accessible at: **`http://localhost:5000`**

---

## Development Test Accounts

The seed script initializes accounts for every corporate role (passwords hashed with Werkzeug `scrypt`):

| Role | Employee ID | Email | Password | Department |
|:-----|:------------|:------|:---------|:-----------|
| **ADMIN** | `EMP001` | `admin@company.com` | `admin123` | Administration |
| **EMPLOYEE** | `EMP002` | `rohan.sharma@company.com` | `employee123` | Information Technology |
| **APPROVER** | `EMP003` | `priya.patel@company.com` | `approver123` | Information Technology |
| **FINANCE** | `EMP004` | `vikram.finance@company.com` | `finance123` | Finance |
| **EMPLOYEE** | `EMP005` | `ananya.ops@company.com` | `employee123` | Operations |

---

## OCR Processing & Fallback

- Supported formats: `.jpg`, `.jpeg`, `.png`, `.pdf`
- Extracted attributes: Vendor Name, Invoice/Bill Number, Transaction Date, Tax Amounts (GST/VAT/CGST/SGST), Total Amount
- Confidence Scoring: High (>80%) highlighted in green, Medium (50-80%) in yellow, Low (<50%) in orange.
- **Graceful degradation**: If OCR is unavailable or an unreadable document is uploaded, an error banner is shown, and the user can type values directly into the editable form without interruption.

---

## Security Features

- **Authentication**: Session-based authentication with Werkzeug password hashing.
- **Authorization**: Role-based access control (`@login_required`, `@role_required`).
- **File Upload Protection**: UUID file renaming to prevent collisions and path traversal, MIME type validation, file size cap (16 MB).
- **Document Access Control**: Documents are served through authenticated Flask routes that verify ownership or role permissions; files cannot be accessed directly via static paths.
- **SQL Injection Prevention**: All queries utilize SQLAlchemy ORM with parameterized queries.
