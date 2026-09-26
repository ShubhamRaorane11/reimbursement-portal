"""
OCR Service — Abstracted OCR engine for bill/receipt processing.

Architecture:
    OCR Engine (Tesseract) → OCR Service → Field Extraction → Reimbursement Form

The OCR engine is replaceable via the abstract base class.
"""
import os
import re
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines. Implement this to swap engines."""

    @abstractmethod
    def extract_text(self, filepath):
        """
        Extract raw text from a document.

        Args:
            filepath: Absolute path to the document file.

        Returns:
            dict: {
                'text': str,           # Extracted raw text
                'confidence': float,   # Overall confidence (0-100), or None
                'engine': str,         # Engine name
                'error': str or None,  # Error message if failed
            }
        """
        pass

    @abstractmethod
    def get_engine_name(self):
        """Return the name of this OCR engine."""
        pass


class TesseractEngine(BaseOCREngine):
    """Tesseract OCR engine implementation."""

    def __init__(self, tesseract_cmd=None):
        """Initialize Tesseract engine."""
        try:
            import pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self.pytesseract = pytesseract
            self._available = True
        except ImportError:
            logger.warning('pytesseract is not installed. OCR will be unavailable.')
            self._available = False

    def get_engine_name(self):
        return 'Tesseract'

    @property
    def is_available(self):
        return self._available

    def extract_text(self, filepath):
        """Extract text from image or PDF using Tesseract."""
        if not self._available:
            return {
                'text': '',
                'confidence': None,
                'engine': self.get_engine_name(),
                'error': 'Tesseract OCR is not installed or configured.',
            }

        try:
            from PIL import Image
            ext = os.path.splitext(filepath)[1].lower()

            if ext == '.pdf':
                return self._process_pdf(filepath)
            elif ext in ('.jpg', '.jpeg', '.png'):
                return self._process_image(filepath)
            else:
                return {
                    'text': '',
                    'confidence': None,
                    'engine': self.get_engine_name(),
                    'error': f'Unsupported file type: {ext}',
                }
        except Exception as e:
            logger.exception(f'OCR processing failed for {filepath}')
            return {
                'text': '',
                'confidence': None,
                'engine': self.get_engine_name(),
                'error': str(e),
            }

    def _process_image(self, filepath):
        """Process a single image file."""
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(filepath)

        # Preprocess: convert to grayscale, enhance contrast
        if img.mode != 'L':
            img = img.convert('L')
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        # Extract text
        text = self.pytesseract.image_to_string(img, lang='eng')

        # Get confidence data
        try:
            data = self.pytesseract.image_to_data(img, output_type=self.pytesseract.Output.DICT)
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        except Exception:
            avg_confidence = None

        return {
            'text': text.strip(),
            'confidence': round(avg_confidence, 1) if avg_confidence else None,
            'engine': self.get_engine_name(),
            'error': None,
        }

    def _process_pdf(self, filepath):
        """Process a PDF file — convert pages to images then OCR."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            return {
                'text': '',
                'confidence': None,
                'engine': self.get_engine_name(),
                'error': 'pdf2image is not installed. Cannot process PDFs.',
            }

        try:
            # Try to extract text from PDF directly first (for text-based PDFs)
            text_from_pdf = self._extract_pdf_text(filepath)
            if text_from_pdf and len(text_from_pdf.strip()) > 50:
                return {
                    'text': text_from_pdf.strip(),
                    'confidence': 95.0,  # High confidence for text-based PDFs
                    'engine': f'{self.get_engine_name()} (PDF Text)',
                    'error': None,
                }

            # For scanned PDFs, convert to images and OCR
            images = convert_from_path(filepath, dpi=300)
            all_text = []
            confidences = []

            for i, img in enumerate(images):
                page_result = self._process_pil_image(img)
                if page_result['text']:
                    all_text.append(f'--- Page {i+1} ---\n{page_result["text"]}')
                if page_result.get('confidence'):
                    confidences.append(page_result['confidence'])

            combined_text = '\n\n'.join(all_text)
            avg_conf = sum(confidences) / len(confidences) if confidences else None

            return {
                'text': combined_text,
                'confidence': round(avg_conf, 1) if avg_conf else None,
                'engine': self.get_engine_name(),
                'error': None if combined_text else 'No text could be extracted from the PDF.',
            }
        except Exception as e:
            logger.exception(f'PDF processing failed: {filepath}')
            return {
                'text': '',
                'confidence': None,
                'engine': self.get_engine_name(),
                'error': f'PDF processing failed: {str(e)}',
            }

    def _extract_pdf_text(self, filepath):
        """Try to extract text directly from a text-based PDF."""
        try:
            # Simple text extraction attempt
            import subprocess
            result = subprocess.run(
                ['pdftotext', filepath, '-'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return ''

    def _process_pil_image(self, img):
        """Process a PIL Image object."""
        from PIL import ImageEnhance

        if img.mode != 'L':
            img = img.convert('L')
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

        text = self.pytesseract.image_to_string(img, lang='eng')

        try:
            data = self.pytesseract.image_to_data(img, output_type=self.pytesseract.Output.DICT)
            confs = [int(c) for c in data['conf'] if int(c) > 0]
            avg = sum(confs) / len(confs) if confs else 0
        except Exception:
            avg = None

        return {'text': text.strip(), 'confidence': avg}


class OCRService:
    """
    High-level OCR service that processes documents and extracts structured data.
    Uses a pluggable OCR engine underneath.
    """

    def __init__(self, engine=None, tesseract_cmd=None):
        """Initialize with an OCR engine (defaults to Tesseract)."""
        if engine:
            self.engine = engine
        else:
            self.engine = TesseractEngine(tesseract_cmd=tesseract_cmd)

    def process_document(self, filepath):
        """
        Process a document and extract structured invoice/receipt data.

        Args:
            filepath: Path to the uploaded document.

        Returns:
            dict: {
                'status': 'COMPLETED' | 'FAILED',
                'engine': str,
                'raw_text': str,
                'extracted_data': {
                    'vendor_name': str,
                    'invoice_number': str,
                    'invoice_date': str,
                    'subtotal': str,
                    'tax_amount': str,
                    'tax_details': str,
                    'total_amount': str,
                    'currency': str,
                    'description': str,
                },
                'confidence_data': {
                    'overall': float,
                    'vendor_name': float,
                    ...
                },
                'error': str or None,
            }
        """
        # Step 1: Extract raw text
        result = self.engine.extract_text(filepath)

        if result.get('error') or not result.get('text'):
            return {
                'status': 'FAILED',
                'engine': result.get('engine', 'Unknown'),
                'raw_text': result.get('text', ''),
                'extracted_data': {},
                'confidence_data': {},
                'error': result.get('error', 'No text could be extracted.'),
            }

        # Step 2: Extract structured fields from raw text
        raw_text = result['text']
        extracted = self._extract_fields(raw_text)
        overall_confidence = result.get('confidence')

        # Step 3: Build confidence data
        confidence_data = self._build_confidence(extracted, overall_confidence)

        return {
            'status': 'COMPLETED',
            'engine': result.get('engine', 'Unknown'),
            'raw_text': raw_text,
            'extracted_data': extracted,
            'confidence_data': confidence_data,
            'error': None,
        }

    def _extract_fields(self, text):
        """
        Extract structured invoice/receipt fields from raw OCR text.
        Uses flexible regex patterns to handle varied document layouts.
        """
        extracted = {
            'vendor_name': '',
            'invoice_number': '',
            'invoice_date': '',
            'subtotal': '',
            'tax_amount': '',
            'tax_details': '',
            'total_amount': '',
            'currency': '₹',
            'description': '',
        }

        if not text:
            return extracted

        lines = text.strip().split('\n')

        # ── Vendor / Merchant Name ───────────────────────────
        # Usually the first non-empty, non-numeric line
        vendor_patterns = [
            r'(?:vendor|merchant|seller|company|from|billed\s*by|supplier)\s*[:\-]?\s*(.+)',
            r'(?:name)\s*[:\-]\s*(.+)',
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['vendor_name'] = match.group(1).strip()
                break

        if not extracted['vendor_name'] and lines:
            # Use the first substantial line as vendor name
            for line in lines[:5]:
                line = line.strip()
                if line and len(line) > 3 and not re.match(r'^[\d\s\.\-\/]+$', line):
                    # Skip lines that look like addresses, dates, or invoice info
                    if not re.search(r'(?:invoice|bill|receipt|date|gst|tax|no\.|#|phone|tel|email|address|pin)', line, re.IGNORECASE):
                        extracted['vendor_name'] = line
                        break

        # ── Invoice Number ───────────────────────────────────
        invoice_patterns = [
            r'(?:invoice|inv|bill|receipt|voucher|ref|reference|order)\s*(?:no|number|num|#|id)?\.?\s*[:\-]?\s*([A-Za-z0-9\-\/]+)',
            r'(?:#)\s*([A-Za-z0-9\-\/]+)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['invoice_number'] = match.group(1).strip()
                break

        # ── Invoice Date ─────────────────────────────────────
        date_patterns = [
            r'(?:date|dated|invoice\s*date|bill\s*date|receipt\s*date)\s*[:\-]?\s*(\d{1,2}[\.\-\/]\d{1,2}[\.\-\/]\d{2,4})',
            r'(?:date|dated)\s*[:\-]?\s*(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4})',
            r'(\d{1,2}[\.\-\/]\d{1,2}[\.\-\/]\d{2,4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['invoice_date'] = match.group(1).strip()
                break

        # ── Amount Extraction ────────────────────────────────
        # Helper to extract amount value
        def extract_amount(pattern_text):
            amount_match = re.search(
                r'[₹$€£]?\s*([\d,]+\.?\d*)',
                pattern_text
            )
            if amount_match:
                return amount_match.group(1).replace(',', '')
            return ''

        # Total Amount
        total_patterns = [
            r'(?:grand\s*total|total\s*amount|net\s*total|total\s*payable|amount\s*due|total)\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)',
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['total_amount'] = match.group(1).replace(',', '')
                break

        # Subtotal
        subtotal_patterns = [
            r'(?:sub\s*total|subtotal|base\s*amount|taxable\s*amount|amount\s*before\s*tax)\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)',
        ]
        for pattern in subtotal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['subtotal'] = match.group(1).replace(',', '')
                break

        # ── Tax Information ──────────────────────────────────
        tax_details = []
        tax_total = 0.0

        # CGST + SGST
        cgst_match = re.search(r'CGST\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        sgst_match = re.search(r'SGST\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)

        if cgst_match:
            val = float(cgst_match.group(1).replace(',', ''))
            tax_details.append(f'CGST: {val}')
            tax_total += val

        if sgst_match:
            val = float(sgst_match.group(1).replace(',', ''))
            tax_details.append(f'SGST: {val}')
            tax_total += val

        # IGST
        igst_match = re.search(r'IGST\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if igst_match:
            val = float(igst_match.group(1).replace(',', ''))
            tax_details.append(f'IGST: {val}')
            tax_total += val

        # GST (generic)
        if not tax_details:
            gst_match = re.search(r'GST\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
            if gst_match:
                val = float(gst_match.group(1).replace(',', ''))
                tax_details.append(f'GST: {val}')
                tax_total += val

        # VAT
        vat_match = re.search(r'VAT\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if vat_match:
            val = float(vat_match.group(1).replace(',', ''))
            tax_details.append(f'VAT: {val}')
            tax_total += val

        # Generic tax
        if not tax_details:
            tax_match = re.search(r'(?:tax|service\s*tax)\s*(?:@\s*[\d.]+%?)?\s*[:\-]?\s*[₹$€£]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
            if tax_match:
                val = float(tax_match.group(1).replace(',', ''))
                tax_details.append(f'Tax: {val}')
                tax_total += val

        if tax_total > 0:
            extracted['tax_amount'] = str(tax_total)
        extracted['tax_details'] = '; '.join(tax_details) if tax_details else ''

        # ── Currency Detection ───────────────────────────────
        if '₹' in text or 'INR' in text or 'Rs' in text:
            extracted['currency'] = '₹'
        elif '$' in text or 'USD' in text:
            extracted['currency'] = '$'
        elif '€' in text or 'EUR' in text:
            extracted['currency'] = '€'
        elif '£' in text or 'GBP' in text:
            extracted['currency'] = '£'

        # ── Description ──────────────────────────────────────
        desc_patterns = [
            r'(?:description|particulars|items?|details?|for)\s*[:\-]\s*(.+)',
        ]
        for pattern in desc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted['description'] = match.group(1).strip()[:200]
                break

        return extracted

    def _build_confidence(self, extracted, overall_confidence):
        """Build field-level confidence estimates."""
        confidence = {'overall': overall_confidence or 0}

        for field, value in extracted.items():
            if field == 'currency':
                confidence[field] = 90 if value else 50
            elif value:
                # Base confidence on overall OCR confidence and field extraction
                base = overall_confidence or 50
                confidence[field] = min(base, 85)  # Cap at 85 since regex can mis-extract
            else:
                confidence[field] = 0

        return confidence
