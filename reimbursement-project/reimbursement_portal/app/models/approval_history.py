"""Approval History model — audit trail for reimbursement actions."""
from app import db


class ApprovalHistory(db.Model):
    __tablename__ = 'approval_history'

    id = db.Column(db.Integer, primary_key=True)
    reimbursement_id = db.Column(db.Integer, db.ForeignKey('reimbursements.id'), nullable=False)
    action = db.Column(
        db.Enum('SUBMITTED', 'APPROVED', 'REJECTED', 'NEEDS_CORRECTION',
                'RESUBMITTED', 'PROCESSING', 'REIMBURSED', name='approval_action'),
        nullable=False
    )
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    # Relationships
    performer = db.relationship('User', foreign_keys=[performed_by])

    @property
    def action_label(self):
        """Human-readable action label."""
        labels = {
            'SUBMITTED': 'Submitted',
            'APPROVED': 'Approved',
            'REJECTED': 'Rejected',
            'NEEDS_CORRECTION': 'Correction Requested',
            'RESUBMITTED': 'Resubmitted',
            'PROCESSING': 'Payment Processing',
            'REIMBURSED': 'Reimbursed',
        }
        return labels.get(self.action, self.action)

    @property
    def action_icon(self):
        """Icon class for timeline display."""
        icons = {
            'SUBMITTED': 'fa-paper-plane',
            'APPROVED': 'fa-check-circle',
            'REJECTED': 'fa-times-circle',
            'NEEDS_CORRECTION': 'fa-exclamation-circle',
            'RESUBMITTED': 'fa-redo',
            'PROCESSING': 'fa-cog',
            'REIMBURSED': 'fa-check-double',
        }
        return icons.get(self.action, 'fa-circle')

    @property
    def action_color(self):
        """CSS color class for timeline."""
        colors = {
            'SUBMITTED': 'info',
            'APPROVED': 'success',
            'REJECTED': 'danger',
            'NEEDS_CORRECTION': 'warning',
            'RESUBMITTED': 'info',
            'PROCESSING': 'info',
            'REIMBURSED': 'success',
        }
        return colors.get(self.action, 'secondary')

    def __repr__(self):
        return f'<ApprovalHistory {self.action} by user={self.performed_by}>'
