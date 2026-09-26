"""
Admin Blueprint — Organization-wide management.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, abort, jsonify)
from sqlalchemy import func, extract
from datetime import datetime

from app import db
from app.models.user import User
from app.models.department import Department
from app.models.expense_category import ExpenseCategory
from app.models.reimbursement import Reimbursement
from app.models.notification import Notification
from app.routes.auth import login_required, role_required
from app.services import notification_service

admin_bp = Blueprint('admin', __name__)


# ── Dashboard ────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@login_required
@role_required('ADMIN')
def dashboard():
    """Organization-wide admin dashboard."""
    total = Reimbursement.query.count()
    pending = Reimbursement.query.filter_by(status='PENDING_APPROVAL').count()
    approved = Reimbursement.query.filter_by(status='APPROVED').count()
    rejected = Reimbursement.query.filter_by(status='REJECTED').count()
    needs_corr = Reimbursement.query.filter_by(status='NEEDS_CORRECTION').count()
    processing = Reimbursement.query.filter_by(status='PROCESSING').count()
    reimbursed = Reimbursement.query.filter_by(status='REIMBURSED').count()

    total_requested = db.session.query(func.sum(Reimbursement.amount)).scalar() or 0
    total_reimbursed = db.session.query(func.sum(Reimbursement.amount)).filter_by(status='REIMBURSED').scalar() or 0

    # Monthly reimbursement data (current year)
    year = datetime.now().year
    monthly_data = db.session.query(
        extract('month', Reimbursement.submitted_at).label('month'),
        func.sum(Reimbursement.amount).label('amount')
    ).filter(
        extract('year', Reimbursement.submitted_at) == year,
        Reimbursement.status.in_(['APPROVED', 'PROCESSING', 'REIMBURSED'])
    ).group_by('month').all()

    monthly_amounts = {int(m): float(a) for m, a in monthly_data if m}

    # Category-wise spending
    category_data = [
        [str(row[0]), float(row[1] or 0)]
        for row in db.session.query(
            ExpenseCategory.name,
            func.sum(Reimbursement.amount)
        ).join(Reimbursement, Reimbursement.category_id == ExpenseCategory.id).filter(
            Reimbursement.status.in_(['APPROVED', 'PROCESSING', 'REIMBURSED'])
        ).group_by(ExpenseCategory.name).all()
    ]

    # Department-wise spending
    dept_data = [
        [str(row[0]), float(row[1] or 0)]
        for row in db.session.query(
            Department.name,
            func.sum(Reimbursement.amount)
        ).join(Reimbursement, Reimbursement.department_id == Department.id).filter(
            Reimbursement.status.in_(['APPROVED', 'PROCESSING', 'REIMBURSED'])
        ).group_by(Department.name).all()
    ]

    # Status distribution
    status_data = [
        [str(row[0]), int(row[1] or 0)]
        for row in db.session.query(
            Reimbursement.status, func.count(Reimbursement.id)
        ).group_by(Reimbursement.status).all()
    ]

    return render_template('admin/dashboard.html',
                           total=total, pending=pending, approved=approved,
                           rejected=rejected, needs_corr=needs_corr,
                           processing=processing, reimbursed=reimbursed,
                           total_requested=total_requested,
                           total_reimbursed=total_reimbursed,
                           monthly_amounts=monthly_amounts,
                           category_data=category_data,
                           dept_data=dept_data,
                           status_data=status_data)


# ── All Requests ─────────────────────────────────────────────

@admin_bp.route('/requests')
@login_required
@role_required('ADMIN')
def all_requests():
    """View all organization requests."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '').strip()

    query = Reimbursement.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            (Reimbursement.request_number.ilike(f'%{search}%')) |
            (Reimbursement.description.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Reimbursement.updated_at.desc()).paginate(
        page=page, per_page=15, error_out=False)

    return render_template('admin/requests.html',
                           requests=pagination.items, pagination=pagination,
                           status_filter=status_filter, search=search)


# ── Employee Management ──────────────────────────────────────

@admin_bp.route('/employees')
@login_required
@role_required('ADMIN')
def employees():
    """List all employees."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    query = User.query
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) |
            (User.employee_id.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    if role_filter:
        query = query.filter_by(role=role_filter)

    pagination = query.order_by(User.employee_id).paginate(
        page=page, per_page=15, error_out=False)

    departments = Department.query.filter_by(status='ACTIVE').order_by(Department.name).all()

    return render_template('admin/employees.html',
                           employees=pagination.items, pagination=pagination,
                           departments=departments, search=search,
                           role_filter=role_filter)


@admin_bp.route('/employees/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_employee():
    """Add a new employee."""
    employee_id = request.form.get('employee_id', '').strip()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    department_id = request.form.get('department_id', type=int)
    designation = request.form.get('designation', '').strip()
    role = request.form.get('role', 'EMPLOYEE')

    # Validation
    if not all([employee_id, name, email, password]):
        flash('All required fields must be filled.', 'danger')
        return redirect(url_for('admin.employees'))

    if User.query.filter_by(employee_id=employee_id).first():
        flash(f'Employee ID {employee_id} already exists.', 'danger')
        return redirect(url_for('admin.employees'))

    if User.query.filter_by(email=email).first():
        flash(f'Email {email} already exists.', 'danger')
        return redirect(url_for('admin.employees'))

    user = User(
        employee_id=employee_id,
        name=name,
        email=email,
        department_id=department_id,
        designation=designation,
        role=role,
        status='ACTIVE',
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f'Employee {name} ({employee_id}) added successfully.', 'success')
    return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def edit_employee(user_id):
    """Edit an employee."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form.get('name', '').strip() or user.name
        user.email = request.form.get('email', '').strip() or user.email
        user.department_id = request.form.get('department_id', type=int)
        user.designation = request.form.get('designation', '').strip()
        user.role = request.form.get('role', user.role)

        db.session.commit()
        flash(f'Employee {user.name} updated.', 'success')
        return redirect(url_for('admin.employees'))

    departments = Department.query.filter_by(status='ACTIVE').order_by(Department.name).all()
    return render_template('admin/edit_employee.html', user=user, departments=departments)


@admin_bp.route('/employees/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_employee(user_id):
    """Activate/deactivate an employee."""
    user = User.query.get_or_404(user_id)

    if user.id == g.user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.employees'))

    user.status = 'INACTIVE' if user.status == 'ACTIVE' else 'ACTIVE'
    db.session.commit()

    action = 'activated' if user.status == 'ACTIVE' else 'deactivated'
    flash(f'{user.name} has been {action}.', 'success')
    return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/<int:user_id>/reset-password', methods=['POST'])
@login_required
@role_required('ADMIN')
def reset_password(user_id):
    """Reset an employee's password."""
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('password', '').strip()

    if not new_password or len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin.employees'))

    user.set_password(new_password)
    db.session.commit()

    flash(f'Password reset for {user.name}.', 'success')
    return redirect(url_for('admin.employees'))


# ── Department Management ────────────────────────────────────

@admin_bp.route('/departments')
@login_required
@role_required('ADMIN')
def departments():
    """List all departments."""
    depts = Department.query.order_by(Department.name).all()
    users = User.query.filter_by(status='ACTIVE').order_by(User.name).all()
    return render_template('admin/departments.html', departments=depts, users=users)


@admin_bp.route('/departments/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_department():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    approver_id = request.form.get('approver_id', type=int)

    if not name:
        flash('Department name is required.', 'danger')
        return redirect(url_for('admin.departments'))

    if Department.query.filter_by(name=name).first():
        flash(f'Department "{name}" already exists.', 'danger')
        return redirect(url_for('admin.departments'))

    dept = Department(name=name, description=description, approver_id=approver_id)
    db.session.add(dept)
    db.session.commit()

    flash(f'Department "{name}" created.', 'success')
    return redirect(url_for('admin.departments'))


@admin_bp.route('/departments/<int:dept_id>/edit', methods=['POST'])
@login_required
@role_required('ADMIN')
def edit_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    dept.name = request.form.get('name', '').strip() or dept.name
    dept.description = request.form.get('description', '').strip()
    dept.approver_id = request.form.get('approver_id', type=int)
    db.session.commit()
    flash(f'Department "{dept.name}" updated.', 'success')
    return redirect(url_for('admin.departments'))


@admin_bp.route('/departments/<int:dept_id>/toggle', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    dept.status = 'INACTIVE' if dept.status == 'ACTIVE' else 'ACTIVE'
    db.session.commit()
    action = 'activated' if dept.status == 'ACTIVE' else 'deactivated'
    flash(f'Department "{dept.name}" {action}.', 'success')
    return redirect(url_for('admin.departments'))


# ── Category Management ──────────────────────────────────────

@admin_bp.route('/categories')
@login_required
@role_required('ADMIN')
def categories():
    cats = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_category():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('admin.categories'))

    if ExpenseCategory.query.filter_by(name=name).first():
        flash(f'Category "{name}" already exists.', 'danger')
        return redirect(url_for('admin.categories'))

    cat = ExpenseCategory(name=name, description=description)
    db.session.add(cat)
    db.session.commit()

    flash(f'Category "{name}" created.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
@login_required
@role_required('ADMIN')
def edit_category(cat_id):
    cat = ExpenseCategory.query.get_or_404(cat_id)
    cat.name = request.form.get('name', '').strip() or cat.name
    cat.description = request.form.get('description', '').strip()
    db.session.commit()
    flash(f'Category "{cat.name}" updated.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/toggle', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_category(cat_id):
    cat = ExpenseCategory.query.get_or_404(cat_id)
    cat.status = 'INACTIVE' if cat.status == 'ACTIVE' else 'ACTIVE'
    db.session.commit()
    action = 'activated' if cat.status == 'ACTIVE' else 'deactivated'
    flash(f'Category "{cat.name}" {action}.', 'success')
    return redirect(url_for('admin.categories'))


# ── Settings ─────────────────────────────────────────────────

@admin_bp.route('/settings')
@login_required
@role_required('ADMIN')
def settings():
    return render_template('admin/settings.html')


# ── Notifications ────────────────────────────────────────────

@admin_bp.route('/notifications')
@login_required
@role_required('ADMIN')
def notifications():
    page = request.args.get('page', 1, type=int)
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('employee/notifications.html', notifications=notifs)


@admin_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('ADMIN')
def mark_notifications_read():
    notification_service.mark_all_read(g.user.id)
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('admin.notifications'))


@admin_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required('ADMIN')
def mark_notification_read(notif_id):
    notification_service.mark_as_read(notif_id, g.user.id)
    db.session.commit()
    return jsonify({'success': True})
