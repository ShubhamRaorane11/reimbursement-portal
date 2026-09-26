"""Reimbursement model — core business entity."""
from app import db


# Valid status transitions
VALID_TRANSITIONS = {
    'DRAFT':              ['PENDING_APPROVAL'],
    'PENDING_APPROVAL':   ['APPROVED', 'REJECTED', 'NEEDS_CORRECTION'],
    'NEEDS_CORRECTION':   ['RESUBMITTED'],
    'RESUBMITTED':        ['PENDING_APPROVAL'],
    'APPROVED':           ['PROCESSING'],
    'PROCESSING':         ['REIMBURSED'],
    'REIMBURSED':         [],
    'REJECTED':           [],
}


class Reimbursement(db.Model):
    __tablename__ = 'reimbursements'

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(20), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    expense_date = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    payment_method = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum('DRAFT', 'PENDING_APPROVAL', 'NEEDS_CORRECTION', 'RESUBMITTED',
                'APPROVED', 'PROCESSING', 'REIMBURSED', 'REJECTED',
                name='reimb_status'),
        nullable=False, default='DRAFT'
    )
    rejection_reason = db.Column(db.Text, nullable=True)
    correction_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(),
                           onupdate=db.func.now())
    submitted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    department = db.relationship('Department', backref='reimbursements')
    category = db.relationship('ExpenseCategory', backref='reimbursements')
    documents = db.relationship('Document', backref='reimbursement', lazy='dynamic',
                                cascade='all, delete-orphan')
    ocr_results = db.relationship('OcrResult', backref='reimbursement', lazy='dynamic',
                                   cascade='all, delete-orphan')
    approval_history = db.relationship('ApprovalHistory', backref='reimbursement',
                                        order_by='ApprovalHistory.created_at',
                                        cascade='all, delete-orphan')
    payment = db.relationship('Payment', backref='reimbursement', uselist=False,
                               cascade='all, delete-orphan')

    def can_transition_to(self, new_status):
        """Check if the status transition is valid."""
        return new_status in VALID_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status):
        """Transition to a new status if valid. Raises ValueError if invalid."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f'Invalid status transition: {self.status} → {new_status}'
            )
        self.status = new_status

    @property
    def is_editable(self):
        """Check if the reimbursement can be edited by the employee."""
        return self.status in ('DRAFT', 'NEEDS_CORRECTION')

    @property
    def status_label(self):
        """Human-readable status label."""
        labels = {
            'DRAFT': 'Draft',
            'PENDING_APPROVAL': 'Pending Approval',
            'NEEDS_CORRECTION': 'Needs Correction',
            'RESUBMITTED': 'Resubmitted',
            'APPROVED': 'Approved',
            'PROCESSING': 'Processing',
            'REIMBURSED': 'Reimbursed',
            'REJECTED': 'Rejected',
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        """CSS class for status badge color."""
        colors = {
            'DRAFT': 'secondary',
            'PENDING_APPROVAL': 'warning',
            'NEEDS_CORRECTION': 'warning',
            'RESUBMITTED': 'info',
            'APPROVED': 'success',
            'PROCESSING': 'info',
            'REIMBURSED': 'success',
            'REJECTED': 'danger',
        }
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Reimbursement {self.request_number}>'
