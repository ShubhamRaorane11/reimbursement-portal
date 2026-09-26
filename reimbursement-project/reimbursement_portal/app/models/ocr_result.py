"""OCR Result model — stores extracted data from documents."""
from app import db


class OcrResult(db.Model):
    __tablename__ = 'ocr_results'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    reimbursement_id = db.Column(db.Integer, db.ForeignKey('reimbursements.id'), nullable=True)
    processing_status = db.Column(
        db.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='ocr_status'),
        nullable=False, default='PENDING'
    )
    ocr_engine = db.Column(db.String(100), nullable=True)
    extracted_text = db.Column(db.Text, nullable=True)
    extracted_data = db.Column(db.JSON, nullable=True)
    confidence_data = db.Column(db.JSON, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    @property
    def is_completed(self):
        return self.processing_status == 'COMPLETED'

    @property
    def is_failed(self):
        return self.processing_status == 'FAILED'

    @property
    def has_low_confidence(self):
        """Check if any extracted field has low confidence."""
        if not self.confidence_data:
            return False
        for field, score in self.confidence_data.items():
            if isinstance(score, (int, float)) and score < 60:
                return True
        return False

    def __repr__(self):
        return f'<OcrResult doc={self.document_id} status={self.processing_status}>'
