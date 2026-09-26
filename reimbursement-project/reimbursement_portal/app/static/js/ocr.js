/**
 * OCR JavaScript — OCR result display and interaction.
 */

// ── Show OCR Results ────────────────────────────────────────
function showOcrResults(extractedData, confidenceData) {
    const panel = document.getElementById('ocrPanel');
    if (!panel) return;

    panel.style.display = 'block';

    // Map fields to inputs
    const fieldMap = {
        'vendor_name': 'ocr_vendor',
        'invoice_number': 'ocr_invoice_number',
        'invoice_date': 'ocr_invoice_date',
        'subtotal': 'ocr_subtotal',
        'tax_amount': 'ocr_tax',
        'tax_details': 'ocr_tax_details',
        'total_amount': 'ocr_total',
        'description': 'ocr_description',
    };

    for (const [field, inputId] of Object.entries(fieldMap)) {
        const input = document.getElementById(inputId);
        if (input) {
            input.value = extractedData[field] || '';

            // Apply confidence styling
            if (confidenceData && confidenceData[field] !== undefined) {
                const conf = confidenceData[field];
                input.classList.remove('low-confidence');

                // Remove old indicator
                const existingIndicator = input.parentElement.querySelector('.confidence-indicator');
                if (existingIndicator) existingIndicator.remove();

                if (conf > 0 && conf < 60) {
                    input.classList.add('low-confidence');
                    const indicator = document.createElement('div');
                    indicator.className = 'confidence-indicator confidence-low';
                    indicator.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Low confidence (' + Math.round(conf) + '%) — please verify';
                    input.parentElement.appendChild(indicator);
                } else if (conf >= 60 && conf < 80) {
                    const indicator = document.createElement('div');
                    indicator.className = 'confidence-indicator confidence-medium';
                    indicator.innerHTML = '<i class="fas fa-info-circle"></i> Medium confidence (' + Math.round(conf) + '%)';
                    input.parentElement.appendChild(indicator);
                }
            }
        }
    }

    // Store extracted data for form submission
    document.getElementById('ocrExtractedData').value = JSON.stringify(extractedData);
}

// ── Use OCR Data — Copy to Main Form ────────────────────────
function useOcrData() {
    const totalField = document.getElementById('ocr_total');
    const dateField = document.getElementById('ocr_invoice_date');
    const descField = document.getElementById('ocr_description');

    // Copy total to amount field
    if (totalField && totalField.value) {
        const amountInput = document.getElementById('amount');
        if (amountInput) {
            const numVal = parseFloat(totalField.value.replace(/[^0-9.]/g, ''));
            if (!isNaN(numVal) && numVal > 0) {
                amountInput.value = numVal.toFixed(2);
            }
        }
    }

    // Copy description
    if (descField && descField.value) {
        const descInput = document.getElementById('description');
        if (descInput && !descInput.value) {
            descInput.value = descField.value;
        }
    }

    // Try to set date
    if (dateField && dateField.value) {
        const dateInput = document.getElementById('expense_date');
        if (dateInput) {
            // Try to parse common date formats
            const dateStr = dateField.value;
            const parsed = tryParseDate(dateStr);
            if (parsed) {
                dateInput.value = parsed;
            }
        }
    }

    // Visual feedback
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-check"></i> Applied!';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-success');
    setTimeout(function () {
        btn.innerHTML = originalText;
        btn.classList.remove('btn-success');
        btn.classList.add('btn-primary');
    }, 2000);
}

// ── Clear OCR Data ──────────────────────────────────────────
function clearOcrData() {
    const inputs = document.querySelectorAll('#ocrFields input');
    inputs.forEach(function (input) {
        if (!input.readOnly) input.value = '';
        input.classList.remove('low-confidence');
    });

    // Remove confidence indicators
    document.querySelectorAll('.confidence-indicator').forEach(function (el) { el.remove(); });

    document.getElementById('ocrExtractedData').value = '';
}

// ── Date Parser ─────────────────────────────────────────────
function tryParseDate(str) {
    // Try common formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, MM/DD/YYYY, YYYY-MM-DD
    const formats = [
        /(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})/,      // DD/MM/YYYY or MM/DD/YYYY
        /(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})/,      // YYYY/MM/DD
    ];

    for (const fmt of formats) {
        const m = str.match(fmt);
        if (m) {
            let y, mo, d;
            if (m[1].length === 4) {
                y = parseInt(m[1]); mo = parseInt(m[2]); d = parseInt(m[3]);
            } else {
                // Assume DD/MM/YYYY for Indian format
                d = parseInt(m[1]); mo = parseInt(m[2]); y = parseInt(m[3]);
            }
            if (mo > 12) { const tmp = d; d = mo; mo = tmp; } // Swap if month > 12
            if (y > 1900 && y < 2100 && mo >= 1 && mo <= 12 && d >= 1 && d <= 31) {
                return y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
            }
        }
    }

    // Try month name: DD Mon YYYY
    const monthNames = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
    const nameMatch = str.match(/(\d{1,2})\s+(\w{3,})\s+(\d{4})/i);
    if (nameMatch) {
        const d = parseInt(nameMatch[1]);
        const mo = monthNames[nameMatch[2].substring(0, 3).toLowerCase()];
        const y = parseInt(nameMatch[3]);
        if (mo && y > 1900 && d >= 1 && d <= 31) {
            return y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
        }
    }

    return null;
}
