"""Expense Category model."""
from app import db


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    status = db.Column(db.Enum('ACTIVE', 'INACTIVE', name='category_status'),
                       nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(),
                           onupdate=db.func.now())

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'
