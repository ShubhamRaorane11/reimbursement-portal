"""Document model — uploaded bills and receipts."""
from app import db


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    reimbursement_id = db.Column(db.Integer, db.ForeignKey('reimbursements.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    # Relationships
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    ocr_result = db.relationship('OcrResult', backref='document', uselist=False,
                                  cascade='all, delete-orphan')

    @property
    def size_display(self):
        """Human-readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    @property
    def is_image(self):
        return self.file_type.lower() in ('jpg', 'jpeg', 'png')

    @property
    def is_pdf(self):
        return self.file_type.lower() == 'pdf'

    def __repr__(self):
        return f'<Document {self.original_filename}>'
