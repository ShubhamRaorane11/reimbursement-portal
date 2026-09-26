"""
Auth Blueprint — Login, logout, and authentication decorators.
"""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, abort

from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)


# ── Decorators ───────────────────────────────────────────────

def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator to require specific role(s)."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not g.user:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if g.user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Routes ───────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication."""
    # If already logged in, redirect
    if g.user:
        return _redirect_by_role(g.user.role)

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()

        if not login_id or not password:
            flash('Please enter your Employee ID or Email and password.', 'danger')
            return render_template('auth/login.html')

        # Find user by employee_id or email
        user = User.query.filter(
            (User.employee_id == login_id) | (User.email == login_id)
        ).first()

        if user and user.check_password(password):
            if user.status != 'ACTIVE':
                flash('Your account has been deactivated. Please contact your administrator.', 'danger')
                return render_template('auth/login.html')

            # Set session
            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            session['user_role'] = user.role
            session['user_name'] = user.name

            flash(f'Welcome, {user.name}!', 'success')
            return _redirect_by_role(user.role)
        else:
            flash('Invalid credentials. Please check your Employee ID/Email and password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Log out and clear session."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


# ── Helpers ──────────────────────────────────────────────────

def _redirect_by_role(role):
    """Redirect to the appropriate dashboard based on role."""
    routes = {
        'EMPLOYEE': 'employee.dashboard',
        'APPROVER': 'approver.dashboard',
        'FINANCE': 'finance.dashboard',
        'ADMIN': 'admin.dashboard',
    }
    return redirect(url_for(routes.get(role, 'employee.dashboard')))
