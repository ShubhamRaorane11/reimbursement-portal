"""
Employee Blueprint — Dashboard, reimbursement requests, uploads, OCR, notifications.
"""
import os
import json
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, abort, current_app, send_file, jsonify)
from werkzeug.utils import secure_filename

from app import db
from app.models.user import User
from app.models.reimbursement import Reimbursement
from app.models.document import Document
from app.models.ocr_result import OcrResult
from app.models.expense_category import ExpenseCategory
from app.models.notification import Notification
from app.models.department import Department
from app.routes.auth import login_required, role_required
from app.services import reimbursement_service, notification_service

employee_bp = Blueprint('employee', __name__)


def _allowed_file(filename):
    """Check if file extension is allowed."""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'jpg', 'jpeg', 'png'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


# ── Dashboard ────────────────────────────────────────────────

@employee_bp.route('/dashboard')
@login_required
@role_required('EMPLOYEE')
def dashboard():
    """Employee dashboard with KPIs and recent requests."""
    user = g.user

    # KPI counts
    total = Reimbursement.query.filter_by(employee_id=user.id).count()
    pending = Reimbursement.query.filter_by(
        employee_id=user.id, status='PENDING_APPROVAL').count()
    approved = Reimbursement.query.filter(
        Reimbursement.employee_id == user.id,
        Reimbursement.status.in_(['APPROVED', 'PROCESSING', 'REIMBURSED'])
    ).count()
    rejected = Reimbursement.query.filter_by(
        employee_id=user.id, status='REJECTED').count()

    # Total reimbursed amount
    from sqlalchemy import func
    reimbursed_amount = db.session.query(func.sum(Reimbursement.amount)).filter(
        Reimbursement.employee_id == user.id,
        Reimbursement.status == 'REIMBURSED'
    ).scalar() or 0

    # Recent requests
    recent = Reimbursement.query.filter_by(employee_id=user.id).order_by(
        Reimbursement.updated_at.desc()
    ).limit(5).all()

    # Recent notifications
    notifications = Notification.query.filter_by(user_id=user.id).order_by(
        Notification.created_at.desc()
    ).limit(5).all()

    # Status distribution for chart
    status_counts = db.session.query(
        Reimbursement.status, func.count(Reimbursement.id)
    ).filter_by(employee_id=user.id).group_by(Reimbursement.status).all()

    chart_data = {s: c for s, c in status_counts}

    return render_template('employee/dashboard.html',
                           total=total, pending=pending, approved=approved,
                           rejected=rejected, reimbursed_amount=reimbursed_amount,
                           recent=recent, notifications=notifications,
                           chart_data=chart_data)


# ── My Reimbursements ────────────────────────────────────────

@employee_bp.route('/requests')
@login_required
@role_required('EMPLOYEE')
def my_requests():
    """List all reimbursement requests for the current employee."""
    user = g.user

    # Filters
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Reimbursement.query.filter_by(employee_id=user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category_id=int(category_filter))
    if search:
        query = query.filter(
            (Reimbursement.request_number.ilike(f'%{search}%')) |
            (Reimbursement.description.ilike(f'%{search}%'))
        )

    query = query.order_by(Reimbursement.updated_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    categories = ExpenseCategory.query.filter_by(status='ACTIVE').order_by(ExpenseCategory.name).all()

    return render_template('employee/requests.html',
                           requests=pagination.items, pagination=pagination,
                           categories=categories,
                           status_filter=status_filter,
                           category_filter=category_filter,
                           search=search)


# ── New Reimbursement Request ────────────────────────────────

@employee_bp.route('/requests/new', methods=['GET', 'POST'])
@login_required
@role_required('EMPLOYEE')
def new_request():
    """Create a new reimbursement request."""
    user = g.user
    categories = ExpenseCategory.query.filter_by(status='ACTIVE').order_by(ExpenseCategory.name).all()

    if request.method == 'POST':
        try:
            category_id = request.form.get('category_id', type=int)
            expense_date_str = request.form.get('expense_date', '')
            amount = request.form.get('amount', type=float)
            payment_method = request.form.get('payment_method', '').strip()
            description = request.form.get('description', '').strip()
            action = request.form.get('action', 'submit')  # 'submit' or 'draft'

            # Validation
            errors = []
            if not category_id:
                errors.append('Please select an expense category.')
            if not expense_date_str:
                errors.append('Please enter the expense date.')
            if not amount or amount <= 0:
                errors.append('Please enter a valid amount.')
            if not description:
                errors.append('Please provide a description.')

            if expense_date_str:
                try:
                    expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
                except ValueError:
                    errors.append('Invalid date format.')
                    expense_date = None
            else:
                expense_date = None

            if errors:
                for e in errors:
                    flash(e, 'danger')
                return render_template('employee/new_request.html',
                                       categories=categories, form=request.form)

            # Create reimbursement
            as_draft = (action == 'draft')
            reimb = reimbursement_service.create_reimbursement(
                employee=user,
                category_id=category_id,
                expense_date=expense_date,
                amount=amount,
                payment_method=payment_method,
                description=description,
                as_draft=as_draft,
            )

            # Handle file uploads
            files = request.files.getlist('documents')
            for f in files:
                if f and f.filename and _allowed_file(f.filename):
                    _save_document(f, reimb, user)

            # Handle OCR data if provided
            ocr_data_json = request.form.get('ocr_extracted_data', '')
            if ocr_data_json:
                try:
                    json.loads(ocr_data_json)  # Validate JSON
                except json.JSONDecodeError:
                    pass

            db.session.commit()

            # Notify approver if submitted
            if not as_draft and user.department:
                dept = Department.query.get(user.department_id)
                if dept and dept.approver_id:
                    notification_service.notify_submission(reimb, dept.approver_id)
                    db.session.commit()

            if as_draft:
                flash(f'Request {reimb.request_number} saved as draft.', 'success')
            else:
                flash(f'Request {reimb.request_number} submitted successfully.', 'success')

            return redirect(url_for('employee.request_detail', req_id=reimb.id))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('employee/new_request.html',
                                   categories=categories, form=request.form)

    return render_template('employee/new_request.html',
                           categories=categories, form={})


# ── Request Detail ───────────────────────────────────────────

@employee_bp.route('/requests/<int:req_id>')
@login_required
@role_required('EMPLOYEE')
def request_detail(req_id):
    """View reimbursement request details."""
    reimb = Reimbursement.query.get_or_404(req_id)

    # Authorization: only own requests
    if reimb.employee_id != g.user.id:
        abort(403)

    documents = Document.query.filter_by(reimbursement_id=reimb.id).all()
    ocr_results = OcrResult.query.filter_by(reimbursement_id=reimb.id).all()

    return render_template('employee/request_detail.html',
                           reimb=reimb, documents=documents,
                           ocr_results=ocr_results)


# ── Edit Request (Draft / Needs Correction) ──────────────────

@employee_bp.route('/requests/<int:req_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('EMPLOYEE')
def edit_request(req_id):
    """Edit a draft or needs-correction request."""
    reimb = Reimbursement.query.get_or_404(req_id)
    user = g.user

    if reimb.employee_id != user.id:
        abort(403)

    if not reimb.is_editable:
        flash('This request cannot be edited in its current status.', 'warning')
        return redirect(url_for('employee.request_detail', req_id=reimb.id))

    categories = ExpenseCategory.query.filter_by(status='ACTIVE').order_by(ExpenseCategory.name).all()

    if request.method == 'POST':
        try:
            reimb.category_id = request.form.get('category_id', type=int)
            expense_date_str = request.form.get('expense_date', '')
            reimb.amount = request.form.get('amount', type=float)
            reimb.payment_method = request.form.get('payment_method', '').strip()
            reimb.description = request.form.get('description', '').strip()
            action = request.form.get('action', 'submit')

            if expense_date_str:
                reimb.expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()

            # Handle new uploads
            files = request.files.getlist('documents')
            for f in files:
                if f and f.filename and _allowed_file(f.filename):
                    _save_document(f, reimb, user)

            if action == 'submit':
                if reimb.status == 'NEEDS_CORRECTION':
                    reimbursement_service.resubmit_reimbursement(reimb, user.id)
                    # Notify approver
                    dept = Department.query.get(user.department_id)
                    if dept and dept.approver_id:
                        notification_service.notify_resubmission(reimb, dept.approver_id)
                elif reimb.status == 'DRAFT':
                    reimbursement_service.submit_reimbursement(reimb, user.id)
                    dept = Department.query.get(user.department_id)
                    if dept and dept.approver_id:
                        notification_service.notify_submission(reimb, dept.approver_id)

            db.session.commit()

            if action == 'draft':
                flash('Changes saved.', 'success')
            else:
                flash(f'Request {reimb.request_number} submitted.', 'success')

            return redirect(url_for('employee.request_detail', req_id=reimb.id))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')

    documents = Document.query.filter_by(reimbursement_id=reimb.id).all()
    return render_template('employee/new_request.html',
                           categories=categories, reimb=reimb,
                           documents=documents, editing=True, form={})


# ── Submit Draft ─────────────────────────────────────────────

@employee_bp.route('/requests/<int:req_id>/submit', methods=['POST'])
@login_required
@role_required('EMPLOYEE')
def submit_request(req_id):
    """Submit a draft request."""
    reimb = Reimbursement.query.get_or_404(req_id)
    user = g.user

    if reimb.employee_id != user.id:
        abort(403)

    try:
        reimbursement_service.submit_reimbursement(reimb, user.id)

        dept = Department.query.get(user.department_id)
        if dept and dept.approver_id:
            notification_service.notify_submission(reimb, dept.approver_id)

        db.session.commit()
        flash(f'Request {reimb.request_number} submitted successfully.', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('employee.request_detail', req_id=reimb.id))


# ── File Upload with OCR ─────────────────────────────────────

@employee_bp.route('/upload', methods=['POST'])
@login_required
@role_required('EMPLOYEE')
def upload_file():
    """Upload a document and optionally process with OCR. Returns JSON."""
    user = g.user

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No file selected.'}), 400

    if not _allowed_file(f.filename):
        return jsonify({'error': 'File type not allowed. Use PDF, JPG, JPEG, or PNG.'}), 400

    reimb_id = request.form.get('reimbursement_id', type=int)
    reimb = None
    if reimb_id:
        reimb = Reimbursement.query.get(reimb_id)
        if not reimb or reimb.employee_id != user.id:
            return jsonify({'error': 'Request not found.'}), 404

    try:
        # If no reimbursement yet, create a temp one in DRAFT
        if not reimb:
            reimb = Reimbursement(
                request_number=reimbursement_service.generate_request_number(),
                employee_id=user.id,
                department_id=user.department_id,
                status='DRAFT',
            )
            db.session.add(reimb)
            db.session.flush()

        doc = _save_document(f, reimb, user)
        db.session.flush()

        # Run OCR
        ocr_data = _run_ocr(doc, reimb)
        db.session.commit()

        return jsonify({
            'success': True,
            'document': {
                'id': doc.id,
                'filename': doc.original_filename,
                'size': doc.size_display,
                'type': doc.file_type,
            },
            'reimbursement_id': reimb.id,
            'ocr': ocr_data,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


# ── Document Viewing ─────────────────────────────────────────

@employee_bp.route('/documents/<int:doc_id>')
@login_required
def view_document(doc_id):
    """Serve a protected document."""
    doc = Document.query.get_or_404(doc_id)
    reimb = Reimbursement.query.get_or_404(doc.reimbursement_id)

    # Authorization check
    user = g.user
    can_view = False
    if reimb.employee_id == user.id:
        can_view = True
    elif user.role == 'ADMIN':
        can_view = True
    elif user.role == 'APPROVER':
        dept = Department.query.get(reimb.department_id)
        if dept and dept.approver_id == user.id:
            can_view = True
    elif user.role == 'FINANCE':
        can_view = True

    if not can_view:
        abort(403)

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.filepath)
    if not os.path.exists(filepath):
        abort(404)

    return send_file(filepath, download_name=doc.original_filename)


# ── Delete Document ──────────────────────────────────────────

@employee_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@role_required('EMPLOYEE')
def delete_document(doc_id):
    """Remove an uploaded document."""
    doc = Document.query.get_or_404(doc_id)
    reimb = Reimbursement.query.get_or_404(doc.reimbursement_id)

    if reimb.employee_id != g.user.id or not reimb.is_editable:
        abort(403)

    # Remove file
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.filepath)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Remove OCR result if exists
    if doc.ocr_result:
        db.session.delete(doc.ocr_result)

    db.session.delete(doc)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    flash('Document removed.', 'success')
    return redirect(url_for('employee.edit_request', req_id=reimb.id))


# ── Notifications ────────────────────────────────────────────

@employee_bp.route('/notifications')
@login_required
@role_required('EMPLOYEE')
def notifications():
    """View all notifications."""
    page = request.args.get('page', 1, type=int)
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    return render_template('employee/notifications.html', notifications=notifs)


@employee_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('EMPLOYEE')
def mark_notifications_read():
    """Mark all notifications as read."""
    notification_service.mark_all_read(g.user.id)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    flash('All notifications marked as read.', 'success')
    return redirect(url_for('employee.notifications'))


@employee_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required('EMPLOYEE')
def mark_notification_read(notif_id):
    """Mark single notification as read."""
    notification_service.mark_as_read(notif_id, g.user.id)
    db.session.commit()
    return jsonify({'success': True})


# ── Helpers ──────────────────────────────────────────────────

def _save_document(file, reimb, user):
    """Save an uploaded file and create a Document record."""
    original_name = secure_filename(file.filename)
    ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''

    # Create directory: uploads/YYYY/REQ-NUMBER/
    year = str(datetime.now().year)
    req_dir = os.path.join(year, reimb.request_number)
    full_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], req_dir)
    os.makedirs(full_dir, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    stored_name = f'{timestamp}_{original_name}'
    filepath = os.path.join(req_dir, stored_name)
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filepath)

    file.save(full_path)
    file_size = os.path.getsize(full_path)

    doc = Document(
        reimbursement_id=reimb.id,
        original_filename=original_name,
        stored_filename=stored_name,
        filepath=filepath,
        file_type=ext,
        file_size=file_size,
        uploaded_by=user.id,
    )
    db.session.add(doc)
    db.session.flush()

    return doc


def _run_ocr(doc, reimb):
    """Run OCR on a document and return results."""
    ocr_result_data = {
        'status': 'FAILED',
        'extracted_data': {},
        'confidence_data': {},
        'error': None,
    }

    try:
        from app.services.ocr_service import OCRService
        ocr_svc = OCRService(tesseract_cmd=current_app.config.get('TESSERACT_CMD'))

        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.filepath)
        result = ocr_svc.process_document(full_path)

        ocr = OcrResult(
            document_id=doc.id,
            reimbursement_id=reimb.id,
            processing_status=result['status'],
            ocr_engine=result.get('engine', ''),
            extracted_text=result.get('raw_text', ''),
            extracted_data=result.get('extracted_data', {}),
            confidence_data=result.get('confidence_data', {}),
            processed_at=datetime.utcnow(),
            error_message=result.get('error'),
        )
        db.session.add(ocr)

        ocr_result_data = {
            'status': result['status'],
            'extracted_data': result.get('extracted_data', {}),
            'confidence_data': result.get('confidence_data', {}),
            'error': result.get('error'),
        }

    except Exception as e:
        # OCR failure should not block the upload
        ocr = OcrResult(
            document_id=doc.id,
            reimbursement_id=reimb.id,
            processing_status='FAILED',
            ocr_engine='Tesseract',
            error_message=str(e),
            processed_at=datetime.utcnow(),
        )
        db.session.add(ocr)
        ocr_result_data['error'] = str(e)

    return ocr_result_data
