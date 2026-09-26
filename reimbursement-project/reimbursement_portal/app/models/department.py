"""Department model."""
from app import db


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.Enum('ACTIVE', 'INACTIVE', name='dept_status'),
                       nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(),
                           onupdate=db.func.now())

    # Relationships
    approver = db.relationship('User', foreign_keys=[approver_id],
                               backref=db.backref('approves_department', uselist=False))

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    def __repr__(self):
        return f'<Department {self.name}>'
