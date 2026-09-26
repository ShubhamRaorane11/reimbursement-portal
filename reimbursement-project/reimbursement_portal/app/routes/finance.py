"""
Finance Blueprint — Payment processing workflow.
"""
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, abort, jsonify)
from sqlalchemy import func

from app import db
from app.models.reimbursement import Reimbursement
from app.models.document import Document
from app.models.ocr_result import OcrResult
from app.models.notification import Notification
from app.routes.auth import login_required, role_required
from app.services import reimbursement_service, notification_service

finance_bp = Blueprint('finance', __name__)


# ── Dashboard ────────────────────────────────────────────────

@finance_bp.route('/dashboard')
@login_required
@role_required('FINANCE', 'ADMIN')
def dashboard():
    """Finance dashboard with KPIs."""
    approved_count = Reimbursement.query.filter_by(status='APPROVED').count()
    processing_count = Reimbursement.query.filter_by(status='PROCESSING').count()
    reimbursed_count = Reimbursement.query.filter_by(status='REIMBURSED').count()

    approved_amount = db.session.query(func.sum(Reimbursement.amount)).filter_by(status='APPROVED').scalar() or 0
    processing_amount = db.session.query(func.sum(Reimbursement.amount)).filter_by(status='PROCESSING').scalar() or 0
    reimbursed_amount = db.session.query(func.sum(Reimbursement.amount)).filter_by(status='REIMBURSED').scalar() or 0

    approved_requests = Reimbursement.query.filter_by(status='APPROVED').order_by(
        Reimbursement.updated_at.desc()).limit(10).all()

    return render_template('finance/dashboard.html',
                           approved_count=approved_count,
                           processing_count=processing_count,
                           reimbursed_count=reimbursed_count,
                           approved_amount=approved_amount,
                           processing_amount=processing_amount,
                           reimbursed_amount=reimbursed_amount,
                           approved_requests=approved_requests)


# ── Approved List ────────────────────────────────────────────

@finance_bp.route('/approved')
@login_required
@role_required('FINANCE', 'ADMIN')
def approved_list():
    """List approved requests awaiting payment."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Reimbursement.query.filter_by(status='APPROVED')
    if search:
        query = query.filter(Reimbursement.request_number.ilike(f'%{search}%'))

    pagination = query.order_by(Reimbursement.updated_at.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('finance/approved.html',
                           requests=pagination.items, pagination=pagination,
                           title='Approved — Awaiting Payment', search=search,
                           status='APPROVED')


# ── Processing List ──────────────────────────────────────────

@finance_bp.route('/processing')
@login_required
@role_required('FINANCE', 'ADMIN')
def processing_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Reimbursement.query.filter_by(status='PROCESSING')
    if search:
        query = query.filter(Reimbursement.request_number.ilike(f'%{search}%'))

    pagination = query.order_by(Reimbursement.updated_at.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('finance/approved.html',
                           requests=pagination.items, pagination=pagination,
                           title='Currently Processing', search=search,
                           status='PROCESSING')


# ── Reimbursed List ──────────────────────────────────────────

@finance_bp.route('/reimbursed')
@login_required
@role_required('FINANCE', 'ADMIN')
def reimbursed_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Reimbursement.query.filter_by(status='REIMBURSED')
    if search:
        query = query.filter(Reimbursement.request_number.ilike(f'%{search}%'))

    pagination = query.order_by(Reimbursement.updated_at.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('finance/approved.html',
                           requests=pagination.items, pagination=pagination,
                           title='Reimbursed', search=search,
                           status='REIMBURSED')


# ── Payment View ─────────────────────────────────────────────

@finance_bp.route('/requests/<int:req_id>')
@login_required
@role_required('FINANCE', 'ADMIN')
def payment_view(req_id):
    """View request for payment processing."""
    reimb = Reimbursement.query.get_or_404(req_id)
    documents = Document.query.filter_by(reimbursement_id=reimb.id).all()
    ocr_results = OcrResult.query.filter_by(reimbursement_id=reimb.id).all()

    return render_template('finance/payment.html',
                           reimb=reimb, documents=documents,
                           ocr_results=ocr_results)


# ── Start Processing ─────────────────────────────────────────

@finance_bp.route('/requests/<int:req_id>/process', methods=['POST'])
@login_required
@role_required('FINANCE', 'ADMIN')
def start_processing(req_id):
    """Start payment processing."""
    reimb = Reimbursement.query.get_or_404(req_id)

    try:
        reimbursement_service.start_processing(reimb, g.user.id)
        notification_service.notify_processing(reimb)
        db.session.commit()
        flash(f'Processing started for {reimb.request_number}.', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('finance.payment_view', req_id=reimb.id))


# ── Complete Payment ─────────────────────────────────────────

@finance_bp.route('/requests/<int:req_id>/reimburse', methods=['POST'])
@login_required
@role_required('FINANCE', 'ADMIN')
def complete_payment(req_id):
    """Complete the reimbursement payment."""
    reimb = Reimbursement.query.get_or_404(req_id)

    amount = request.form.get('amount', type=float)
    payment_date_str = request.form.get('payment_date', '')
    payment_method = request.form.get('payment_method', '').strip()
    transaction_ref = request.form.get('transaction_reference', '').strip()
    remarks = request.form.get('remarks', '').strip()

    # Validation
    if not amount or amount <= 0:
        flash('Please enter a valid payment amount.', 'danger')
        return redirect(url_for('finance.payment_view', req_id=reimb.id))
    if not payment_date_str:
        flash('Payment date is required.', 'danger')
        return redirect(url_for('finance.payment_view', req_id=reimb.id))
    if not payment_method:
        flash('Payment method is required.', 'danger')
        return redirect(url_for('finance.payment_view', req_id=reimb.id))

    try:
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()

        payment_data = {
            'amount': amount,
            'payment_date': payment_date,
            'payment_method': payment_method,
            'transaction_reference': transaction_ref,
            'remarks': remarks,
        }

        reimbursement_service.complete_reimbursement(reimb, g.user.id, payment_data)
        notification_service.notify_reimbursed(reimb, amount)
        db.session.commit()
        flash(f'{reimb.request_number} has been reimbursed successfully.', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('finance.payment_view', req_id=reimb.id))


# ── Notifications ────────────────────────────────────────────

@finance_bp.route('/notifications')
@login_required
@role_required('FINANCE', 'ADMIN')
def notifications():
    page = request.args.get('page', 1, type=int)
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('employee/notifications.html', notifications=notifs)


@finance_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('FINANCE', 'ADMIN')
def mark_notifications_read():
    notification_service.mark_all_read(g.user.id)
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('finance.notifications'))


@finance_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required('FINANCE', 'ADMIN')
def mark_notification_read(notif_id):
    notification_service.mark_as_read(notif_id, g.user.id)
    db.session.commit()
    return jsonify({'success': True})
