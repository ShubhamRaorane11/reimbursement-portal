"""
Approver Blueprint — Department approval workflow.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, abort, jsonify)
from sqlalchemy import func

from app import db
from app.models.reimbursement import Reimbursement
from app.models.department import Department
from app.models.document import Document
from app.models.ocr_result import OcrResult
from app.models.notification import Notification
from app.routes.auth import login_required, role_required
from app.services import reimbursement_service, notification_service

approver_bp = Blueprint('approver', __name__)


def _get_department(user):
    """Get the department this approver is responsible for."""
    dept = Department.query.filter_by(approver_id=user.id, status='ACTIVE').first()
    return dept


# ── Dashboard ────────────────────────────────────────────────

@approver_bp.route('/dashboard')
@login_required
@role_required('APPROVER', 'ADMIN')
def dashboard():
    """Approver dashboard with department KPIs."""
    user = g.user
    dept = _get_department(user)

    if not dept:
        flash('You are not assigned as an approver for any department.', 'warning')
        pending = approved = rejected = needs_corr = 0
        total_amount = 0
        pending_requests = []
    else:
        pending = Reimbursement.query.filter_by(department_id=dept.id, status='PENDING_APPROVAL').count()
        approved = Reimbursement.query.filter_by(department_id=dept.id, status='APPROVED').count()
        rejected = Reimbursement.query.filter_by(department_id=dept.id, status='REJECTED').count()
        needs_corr = Reimbursement.query.filter_by(department_id=dept.id, status='NEEDS_CORRECTION').count()

        total_amount = db.session.query(func.sum(Reimbursement.amount)).filter(
            Reimbursement.department_id == dept.id,
            Reimbursement.status.in_(['APPROVED', 'PROCESSING', 'REIMBURSED'])
        ).scalar() or 0

        pending_requests = Reimbursement.query.filter(
            Reimbursement.department_id == dept.id,
            Reimbursement.status.in_(['PENDING_APPROVAL', 'RESUBMITTED'])
        ).order_by(Reimbursement.submitted_at.desc()).limit(10).all()

    return render_template('approver/dashboard.html',
                           dept=dept, pending=pending, approved=approved,
                           rejected=rejected, needs_corr=needs_corr,
                           total_amount=total_amount,
                           pending_requests=pending_requests)


# ── Pending Requests ─────────────────────────────────────────

@approver_bp.route('/requests/pending')
@login_required
@role_required('APPROVER', 'ADMIN')
def pending_requests():
    """List pending department requests."""
    user = g.user
    dept = _get_department(user)
    if not dept:
        flash('No department assigned.', 'warning')
        return redirect(url_for('approver.dashboard'))

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Reimbursement.query.filter(
        Reimbursement.department_id == dept.id,
        Reimbursement.status.in_(['PENDING_APPROVAL', 'RESUBMITTED'])
    )

    if search:
        query = query.filter(
            (Reimbursement.request_number.ilike(f'%{search}%')) |
            (Reimbursement.description.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Reimbursement.submitted_at.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('approver/requests.html',
                           requests=pagination.items, pagination=pagination,
                           dept=dept, title='Pending Requests',
                           status_filter='pending', search=search)


# ── All Requests ─────────────────────────────────────────────

@approver_bp.route('/requests')
@login_required
@role_required('APPROVER', 'ADMIN')
def all_requests():
    """List all department requests."""
    user = g.user
    dept = _get_department(user)
    if not dept:
        flash('No department assigned.', 'warning')
        return redirect(url_for('approver.dashboard'))

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '').strip()

    query = Reimbursement.query.filter_by(department_id=dept.id)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            (Reimbursement.request_number.ilike(f'%{search}%')) |
            (Reimbursement.description.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Reimbursement.updated_at.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('approver/requests.html',
                           requests=pagination.items, pagination=pagination,
                           dept=dept, title='All Department Requests',
                           status_filter=status_filter, search=search)


# ── Review Request ───────────────────────────────────────────

@approver_bp.route('/requests/<int:req_id>')
@login_required
@role_required('APPROVER', 'ADMIN')
def review_request(req_id):
    """Review a specific request."""
    user = g.user
    reimb = Reimbursement.query.get_or_404(req_id)

    # Authorization: only own department
    dept = _get_department(user)
    if not dept or reimb.department_id != dept.id:
        abort(403)

    documents = Document.query.filter_by(reimbursement_id=reimb.id).all()
    ocr_results = OcrResult.query.filter_by(reimbursement_id=reimb.id).all()

    return render_template('approver/review_request.html',
                           reimb=reimb, documents=documents,
                           ocr_results=ocr_results, dept=dept)


# ── Approve ──────────────────────────────────────────────────

@approver_bp.route('/requests/<int:req_id>/approve', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def approve(req_id):
    """Approve a reimbursement request."""
    user = g.user
    reimb = Reimbursement.query.get_or_404(req_id)

    dept = _get_department(user)
    if not dept or reimb.department_id != dept.id:
        abort(403)

    comments = request.form.get('comments', '').strip()

    try:
        reimbursement_service.approve_reimbursement(reimb, user.id, comments)
        notification_service.notify_approval(reimb)
        db.session.commit()
        flash(f'Request {reimb.request_number} has been approved.', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('approver.review_request', req_id=reimb.id))


# ── Reject ───────────────────────────────────────────────────

@approver_bp.route('/requests/<int:req_id>/reject', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def reject(req_id):
    """Reject a reimbursement request."""
    user = g.user
    reimb = Reimbursement.query.get_or_404(req_id)

    dept = _get_department(user)
    if not dept or reimb.department_id != dept.id:
        abort(403)

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Rejection reason is required.', 'danger')
        return redirect(url_for('approver.review_request', req_id=reimb.id))

    try:
        reimbursement_service.reject_reimbursement(reimb, user.id, reason)
        notification_service.notify_rejection(reimb)
        db.session.commit()
        flash(f'Request {reimb.request_number} has been rejected.', 'info')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('approver.review_request', req_id=reimb.id))


# ── Request Correction ───────────────────────────────────────

@approver_bp.route('/requests/<int:req_id>/correction', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def request_correction(req_id):
    """Request correction on a reimbursement."""
    user = g.user
    reimb = Reimbursement.query.get_or_404(req_id)

    dept = _get_department(user)
    if not dept or reimb.department_id != dept.id:
        abort(403)

    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Correction comment is required.', 'danger')
        return redirect(url_for('approver.review_request', req_id=reimb.id))

    try:
        reimbursement_service.request_correction(reimb, user.id, comment)
        notification_service.notify_correction_needed(reimb)
        db.session.commit()
        flash(f'Correction requested for {reimb.request_number}.', 'info')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('approver.review_request', req_id=reimb.id))


# ── Notifications ────────────────────────────────────────────

@approver_bp.route('/notifications')
@login_required
@role_required('APPROVER', 'ADMIN')
def notifications():
    page = request.args.get('page', 1, type=int)
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('employee/notifications.html', notifications=notifs)


@approver_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def mark_notifications_read():
    notification_service.mark_all_read(g.user.id)
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('approver.notifications'))


@approver_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def mark_notification_read(notif_id):
    notification_service.mark_as_read(notif_id, g.user.id)
    db.session.commit()
    return jsonify({'success': True})
