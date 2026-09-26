"""
Flask Application Factory.
Creates and configures the Flask application instance.
"""
import os
from flask import Flask, redirect, url_for, session, g, request
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    # Configure session
    import datetime
    lifetime = app.config.get('PERMANENT_SESSION_LIFETIME', 28800)
    if isinstance(lifetime, datetime.timedelta):
        app.permanent_session_lifetime = lifetime
    else:
        app.permanent_session_lifetime = datetime.timedelta(seconds=int(lifetime))

    # ── Register Blueprints ──────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.employee import employee_bp
    from app.routes.approver import approver_bp
    from app.routes.finance import finance_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(approver_bp, url_prefix='/approver')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # ── Before Request: Load current user ────────────────────
    @app.before_request
    def load_current_user():
        """Load the current user from session before each request."""
        g.user = None
        g.unread_notifications = 0

        # Allow static files without auth
        if request.endpoint and request.endpoint.startswith('static'):
            return

        user_id = session.get('user_id')
        if user_id:
            from app.models.user import User
            user = db.session.get(User, user_id)
            if user and user.status == 'ACTIVE':
                g.user = user
                # Get unread notification count
                from app.models.notification import Notification
                g.unread_notifications = Notification.query.filter_by(
                    user_id=user_id, is_read=False
                ).count()
            else:
                # User deactivated or not found — clear session
                session.clear()

    # ── Context Processors ───────────────────────────────────
    @app.context_processor
    def inject_globals():
        """Inject global variables into all templates."""
        return {
            'current_user': g.get('user'),
            'unread_notifications': g.get('unread_notifications', 0),
        }

    # ── Root Redirect ────────────────────────────────────────
    @app.route('/')
    def index():
        """Redirect to appropriate dashboard or login."""
        if g.user:
            return _redirect_by_role(g.user.role)
        return redirect(url_for('auth.login'))

    # ── Error Handlers ───────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return _render_error(400, 'Bad Request',
                             'The server could not understand your request. Please check your input and try again.'), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return _render_error(401, 'Unauthorized',
                             'You must be logged in to access this page.'), 401

    @app.errorhandler(403)
    def forbidden(e):
        return _render_error(403, 'Access Denied',
                             'You do not have permission to access this resource.'), 403

    @app.errorhandler(404)
    def not_found(e):
        return _render_error(404, 'Page Not Found',
                             'The page you are looking for does not exist or has been moved.'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return _render_error(500, 'Internal Server Error',
                             'An unexpected error occurred. Please try again later or contact your system administrator.'), 500

    return app


def _redirect_by_role(role):
    """Redirect user to their role-specific dashboard."""
    role_routes = {
        'EMPLOYEE': 'employee.dashboard',
        'APPROVER': 'approver.dashboard',
        'FINANCE': 'finance.dashboard',
        'ADMIN': 'admin.dashboard',
    }
    endpoint = role_routes.get(role, 'employee.dashboard')
    return redirect(url_for(endpoint))


def _render_error(code, title, message):
    """Render a professional error page."""
    from flask import render_template_string
    return render_template_string(ERROR_TEMPLATE, code=code, title=title, message=message)


ERROR_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ code }} — {{ title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: #f1f5f9;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; color: #334155;
        }
        .error-container {
            text-align: center; padding: 3rem; max-width: 480px;
        }
        .error-code {
            font-size: 6rem; font-weight: 700; color: #3b82f6;
            line-height: 1; margin-bottom: 0.5rem;
        }
        .error-title {
            font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem; color: #1e293b;
        }
        .error-message {
            font-size: 0.95rem; color: #64748b; line-height: 1.6; margin-bottom: 2rem;
        }
        .error-actions a {
            display: inline-block; padding: 0.7rem 1.5rem;
            background: #3b82f6; color: #fff; text-decoration: none;
            border-radius: 8px; font-weight: 500; font-size: 0.9rem;
            transition: background 0.2s;
        }
        .error-actions a:hover { background: #2563eb; }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-code">{{ code }}</div>
        <h1 class="error-title">{{ title }}</h1>
        <p class="error-message">{{ message }}</p>
        <div class="error-actions">
            <a href="/">← Go to Dashboard</a>
        </div>
    </div>
</body>
</html>'''
