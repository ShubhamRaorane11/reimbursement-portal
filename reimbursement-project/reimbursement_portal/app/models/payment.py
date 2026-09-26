"""Payment model — records payment information for reimbursed requests."""
from app import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    reimbursement_id = db.Column(db.Integer, db.ForeignKey('reimbursements.id'),
                                  unique=True, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    transaction_reference = db.Column(db.String(255), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    # Relationships
    processor = db.relationship('User', foreign_keys=[processed_by])

    def __repr__(self):
        return f'<Payment reimb={self.reimbursement_id} amount={self.amount}>'
