"""
Notification Service — Creates and manages in-app notifications.
"""
from app import db
from app.models.notification import Notification


def create_notification(user_id, message, notification_type='INFO', reimbursement_id=None):
    """Create a notification for a user."""
    notif = Notification(
        user_id=user_id,
        reimbursement_id=reimbursement_id,
        message=message,
        notification_type=notification_type,
        is_read=False,
    )
    db.session.add(notif)
    return notif


def notify_submission(reimbursement, approver_id):
    """Notify the department approver about a new submission."""
    create_notification(
        user_id=approver_id,
        message=f'New reimbursement request {reimbursement.request_number} '
                f'from {reimbursement.employee.name} requires your review.',
        notification_type='NEW_REQUEST',
        reimbursement_id=reimbursement.id,
    )


def notify_approval(reimbursement):
    """Notify the employee that their request was approved."""
    create_notification(
        user_id=reimbursement.employee_id,
        message=f'Your reimbursement {reimbursement.request_number} has been approved.',
        notification_type='APPROVED',
        reimbursement_id=reimbursement.id,
    )

    # Also notify finance users
    from app.models.user import User
    finance_users = User.query.filter_by(role='FINANCE', status='ACTIVE').all()
    for fu in finance_users:
        create_notification(
            user_id=fu.id,
            message=f'Reimbursement {reimbursement.request_number} has been approved '
                    f'and is ready for payment processing.',
            notification_type='APPROVED',
            reimbursement_id=reimbursement.id,
        )


def notify_rejection(reimbursement):
    """Notify the employee that their request was rejected."""
    create_notification(
        user_id=reimbursement.employee_id,
        message=f'Your reimbursement {reimbursement.request_number} has been rejected.',
        notification_type='REJECTED',
        reimbursement_id=reimbursement.id,
    )


def notify_correction_needed(reimbursement):
    """Notify the employee that their request needs correction."""
    create_notification(
        user_id=reimbursement.employee_id,
        message=f'Your reimbursement {reimbursement.request_number} requires correction.',
        notification_type='NEEDS_CORRECTION',
        reimbursement_id=reimbursement.id,
    )


def notify_resubmission(reimbursement, approver_id):
    """Notify the approver that a corrected request was resubmitted."""
    create_notification(
        user_id=approver_id,
        message=f'Reimbursement {reimbursement.request_number} has been '
                f'corrected and resubmitted by {reimbursement.employee.name}.',
        notification_type='RESUBMITTED',
        reimbursement_id=reimbursement.id,
    )


def notify_processing(reimbursement):
    """Notify the employee that payment processing has started."""
    create_notification(
        user_id=reimbursement.employee_id,
        message=f'Your reimbursement {reimbursement.request_number} is being '
                f'processed for payment.',
        notification_type='PROCESSING',
        reimbursement_id=reimbursement.id,
    )


def notify_reimbursed(reimbursement, amount):
    """Notify the employee that they have been reimbursed."""
    create_notification(
        user_id=reimbursement.employee_id,
        message=f'Your reimbursement {reimbursement.request_number} has been '
                f'reimbursed. Amount: ₹{amount:,.2f}',
        notification_type='REIMBURSED',
        reimbursement_id=reimbursement.id,
    )


def get_unread_count(user_id):
    """Get the count of unread notifications for a user."""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def mark_as_read(notification_id, user_id):
    """Mark a single notification as read."""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif:
        notif.is_read = True


def mark_all_read(user_id):
    """Mark all notifications as read for a user."""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
