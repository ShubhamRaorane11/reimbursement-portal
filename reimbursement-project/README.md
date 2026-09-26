# Corporate Employee Reimbursement Management Portal

This repository contains the complete full-stack implementation of the **Internal Corporate Employee Reimbursement Management Portal**.

## Repository Structure

- [`MYSQL_DATABASE_SCRIPTS/`](file:///MYSQL_DATABASE_SCRIPTS): MySQL database creation, schema tables, and seed dataset scripts.
  - `01_create_database.sql`: Creates `reimbursement_portal` database with UTF-8 character set.
  - `02_create_tables.sql`: Defines the 9 relational tables, constraints, foreign keys, and indexes.
  - `03_seed_data.sql`: Populates initial departments, categories, sample requests, and 5 development user accounts.
- [`reimbursement_portal/`](file:///reimbursement_portal): Complete Flask application.
  - `app/models/`: 9 SQLAlchemy data models.
  - `app/routes/`: Flask Blueprints for Auth, Employee, Approver, Finance, and Admin workflows.
  - `app/services/`: OCR extraction, reimbursement state transitions, and in-app notifications.
  - `app/templates/`: Modern Jinja2 templates for all roles and actions.
  - `app/static/`: Vanilla CSS design system, responsive layouts, and interactive client JavaScript.
  - `run.py`: Application startup script.
  - `config.py`: Environment-driven configuration.
  - `requirements.txt`: Python package requirements.

## Quick Start Guide

1. **Set up MySQL Database:**
   ```bash
   mysql -u root -p < MYSQL_DATABASE_SCRIPTS/01_create_database.sql
   mysql -u root -p < MYSQL_DATABASE_SCRIPTS/02_create_tables.sql
   mysql -u root -p < MYSQL_DATABASE_SCRIPTS/03_seed_data.sql
   ```

2. **Configure Environment:**
   In `reimbursement_portal/`, copy `.env.example` to `.env` and set your MySQL password.

3. **Install Dependencies and Launch:**
   ```bash
   cd reimbursement_portal
   pip install -r requirements.txt
   python run.py
   ```

4. **Sign In:**
   Navigate to `http://localhost:5000` and use any of the demo accounts:
   - Admin: `admin@company.com` / `admin123`
   - Employee: `rohan.sharma@company.com` / `employee123`
   - Approver: `priya.patel@company.com` / `approver123`
   - Finance: `vikram.finance@company.com` / `finance123`

For detailed configuration, OCR setup, and architectural guidelines, see [`reimbursement_portal/README.md`](file:///reimbursement_portal/README.md).
