"""
Reimbursement Service — Business logic for reimbursement operations.
"""
from datetime import datetime
from app import db
from app.models.reimbursement import Reimbursement
from app.models.approval_history import ApprovalHistory


def generate_request_number():
    """
    Generate a unique request number in format: REQ-YYYY-NNNNNN
    Example: REQ-2026-000007
    """
    year = datetime.now().year
    prefix = f'REQ-{year}-'

    # Find the latest request number for this year
    latest = Reimbursement.query.filter(
        Reimbursement.request_number.like(f'{prefix}%')
    ).order_by(Reimbursement.id.desc()).first()

    if latest:
        try:
            last_num = int(latest.request_number.split('-')[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1

    return f'{prefix}{next_num:06d}'


def create_reimbursement(employee, category_id, expense_date, amount,
                          payment_method, description, as_draft=False):
    """
    Create a new reimbursement request.

    Returns:
        Reimbursement: The created reimbursement object.
    """
    reimb = Reimbursement(
        request_number=generate_request_number(),
        employee_id=employee.id,
        department_id=employee.department_id,
        category_id=category_id,
        expense_date=expense_date,
        amount=amount,
        payment_method=payment_method,
        description=description,
        status='DRAFT' if as_draft else 'PENDING_APPROVAL',
    )

    if not as_draft:
        reimb.submitted_at = datetime.utcnow()

    db.session.add(reimb)
    db.session.flush()  # Get the ID

    if not as_draft:
        # Create approval history
        history = ApprovalHistory(
            reimbursement_id=reimb.id,
            action='SUBMITTED',
            performed_by=employee.id,
            comments='Request submitted for approval.',
        )
        db.session.add(history)

    return reimb


def submit_reimbursement(reimb, user_id):
    """
    Submit a DRAFT reimbursement for approval.

    Raises:
        ValueError: If reimbursement cannot be submitted.
    """
    if reimb.status not in ('DRAFT',):
        raise ValueError(f'Cannot submit a request with status: {reimb.status}')

    reimb.status = 'PENDING_APPROVAL'
    reimb.submitted_at = datetime.utcnow()

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='SUBMITTED',
        performed_by=user_id,
        comments='Request submitted for approval.',
    )
    db.session.add(history)


def approve_reimbursement(reimb, approver_id, comments=None):
    """
    Approve a pending reimbursement request.

    Raises:
        ValueError: If the status transition is invalid.
    """
    if not reimb.can_transition_to('APPROVED'):
        raise ValueError(f'Cannot approve request with status: {reimb.status}')

    reimb.transition_to('APPROVED')

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='APPROVED',
        performed_by=approver_id,
        comments=comments or 'Request approved.',
    )
    db.session.add(history)


def reject_reimbursement(reimb, approver_id, reason):
    """
    Reject a reimbursement request.

    Raises:
        ValueError: If reason is empty or status transition is invalid.
    """
    if not reason or not reason.strip():
        raise ValueError('Rejection reason is required.')

    if not reimb.can_transition_to('REJECTED'):
        raise ValueError(f'Cannot reject request with status: {reimb.status}')

    reimb.transition_to('REJECTED')
    reimb.rejection_reason = reason.strip()

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='REJECTED',
        performed_by=approver_id,
        comments=reason.strip(),
    )
    db.session.add(history)


def request_correction(reimb, approver_id, comment):
    """
    Request correction on a reimbursement.

    Raises:
        ValueError: If comment is empty or status transition is invalid.
    """
    if not comment or not comment.strip():
        raise ValueError('Correction comment is required.')

    if not reimb.can_transition_to('NEEDS_CORRECTION'):
        raise ValueError(f'Cannot request correction on request with status: {reimb.status}')

    reimb.transition_to('NEEDS_CORRECTION')
    reimb.correction_comment = comment.strip()

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='NEEDS_CORRECTION',
        performed_by=approver_id,
        comments=comment.strip(),
    )
    db.session.add(history)


def resubmit_reimbursement(reimb, user_id, comments=None):
    """
    Resubmit a corrected reimbursement.

    Raises:
        ValueError: If status transition is invalid.
    """
    if reimb.status != 'NEEDS_CORRECTION':
        raise ValueError(f'Cannot resubmit request with status: {reimb.status}')

    # First transition to RESUBMITTED
    reimb.transition_to('RESUBMITTED')

    history_resub = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='RESUBMITTED',
        performed_by=user_id,
        comments=comments or 'Request corrected and resubmitted.',
    )
    db.session.add(history_resub)

    # Then immediately to PENDING_APPROVAL
    reimb.transition_to('PENDING_APPROVAL')
    reimb.submitted_at = datetime.utcnow()


def start_processing(reimb, finance_user_id, comments=None):
    """
    Start payment processing for an approved request.
    """
    if not reimb.can_transition_to('PROCESSING'):
        raise ValueError(f'Cannot process request with status: {reimb.status}')

    reimb.transition_to('PROCESSING')

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='PROCESSING',
        performed_by=finance_user_id,
        comments=comments or 'Payment processing initiated.',
    )
    db.session.add(history)


def complete_reimbursement(reimb, finance_user_id, payment_data):
    """
    Complete the reimbursement by recording payment.

    Args:
        payment_data: dict with keys: amount, payment_date, payment_method,
                      transaction_reference, remarks
    """
    from app.models.payment import Payment

    if not reimb.can_transition_to('REIMBURSED'):
        raise ValueError(f'Cannot reimburse request with status: {reimb.status}')

    reimb.transition_to('REIMBURSED')

    payment = Payment(
        reimbursement_id=reimb.id,
        amount=payment_data['amount'],
        payment_date=payment_data['payment_date'],
        payment_method=payment_data['payment_method'],
        transaction_reference=payment_data.get('transaction_reference', ''),
        remarks=payment_data.get('remarks', ''),
        processed_by=finance_user_id,
    )
    db.session.add(payment)

    history = ApprovalHistory(
        reimbursement_id=reimb.id,
        action='REIMBURSED',
        performed_by=finance_user_id,
        comments=f'Payment completed. Ref: {payment_data.get("transaction_reference", "N/A")}',
    )
    db.session.add(history)
