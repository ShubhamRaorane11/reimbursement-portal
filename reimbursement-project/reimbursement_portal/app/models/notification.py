"""Notification model — in-app notifications for users."""
from app import db


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reimbursement_id = db.Column(db.Integer, db.ForeignKey('reimbursements.id'), nullable=True)
    message = db.Column(db.String(500), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False, default='INFO')
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    @property
    def type_icon(self):
        """Icon class based on notification type."""
        icons = {
            'APPROVED': 'fa-check-circle',
            'REJECTED': 'fa-times-circle',
            'NEEDS_CORRECTION': 'fa-exclamation-triangle',
            'NEW_REQUEST': 'fa-file-alt',
            'PROCESSING': 'fa-cog',
            'REIMBURSED': 'fa-money-bill-wave',
            'RESUBMITTED': 'fa-redo',
            'INFO': 'fa-info-circle',
        }
        return icons.get(self.notification_type, 'fa-bell')

    @property
    def type_color(self):
        """Color class based on notification type."""
        colors = {
            'APPROVED': 'success',
            'REJECTED': 'danger',
            'NEEDS_CORRECTION': 'warning',
            'NEW_REQUEST': 'info',
            'PROCESSING': 'info',
            'REIMBURSED': 'success',
            'RESUBMITTED': 'info',
            'INFO': 'secondary',
        }
        return colors.get(self.notification_type, 'secondary')

    def __repr__(self):
        return f'<Notification user={self.user_id} type={self.notification_type}>'
