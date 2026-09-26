"""User model — employees, approvers, finance, admins."""
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    role = db.Column(db.Enum('EMPLOYEE', 'APPROVER', 'FINANCE', 'ADMIN', name='user_role'),
                     nullable=False, default='EMPLOYEE')
    status = db.Column(db.Enum('ACTIVE', 'INACTIVE', name='user_status'),
                       nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(),
                           onupdate=db.func.now())

    # Relationships
    department = db.relationship('Department', foreign_keys=[department_id], backref='members')
    reimbursements = db.relationship('Reimbursement', backref='employee', lazy='dynamic',
                                     foreign_keys='Reimbursement.employee_id')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def set_password(self, password):
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    def __repr__(self):
        return f'<User {self.employee_id} — {self.name}>'
