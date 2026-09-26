/**
 * Employee JavaScript — File upload handling and form logic.
 */
/* global showOcrResults */

// ── Drag & Drop ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const uploadArea = document.getElementById('uploadArea');
    if (!uploadArea) return;

    uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', function () {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files);
        }
    });
});

// ── File Selection ──────────────────────────────────────────
function handleFileSelect(files) {
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    const maxSize = 16 * 1024 * 1024; // 16 MB

    for (let i = 0; i < files.length; i++) {
        const file = files[i];

        // Validate type
        if (!allowedTypes.includes(file.type)) {
            alert(`"${file.name}" is not a supported file type. Use PDF, JPG, JPEG, or PNG.`);
            continue;
        }

        // Validate size
        if (file.size > maxSize) {
            alert(`"${file.name}" exceeds the 16 MB size limit.`);
            continue;
        }

        // Upload the file
        uploadFile(file);
    }
}

// ── Upload File with OCR ────────────────────────────────────
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Get existing reimbursement_id if editing
    const reimbIdInput = document.querySelector('input[name="reimbursement_id"]');
    if (reimbIdInput) {
        formData.append('reimbursement_id', reimbIdInput.value);
    }

    // Show loading
    const ocrLoading = document.getElementById('ocrLoading');
    const ocrPanel = document.getElementById('ocrPanel');
    const ocrError = document.getElementById('ocrError');
    if (ocrLoading) ocrLoading.style.display = 'block';
    if (ocrPanel) ocrPanel.style.display = 'none';
    if (ocrError) ocrError.style.display = 'none';

    fetch('/employee/upload', {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (ocrLoading) ocrLoading.style.display = 'none';

        if (data.error) {
            if (ocrError) {
                document.getElementById('ocrErrorMsg').textContent = data.error;
                ocrError.style.display = 'block';
            }
            return;
        }

        // Add file to the file list
        if (data.document) {
            addFileToList(data.document);
        }

        // Update reimbursement_id for subsequent uploads
        if (data.reimbursement_id && !reimbIdInput) {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'reimbursement_id';
            hidden.value = data.reimbursement_id;
            document.getElementById('reimbursementForm').appendChild(hidden);
        }

        // Show OCR results
        if (data.ocr && data.ocr.status === 'COMPLETED' && data.ocr.extracted_data) {
            showOcrResults(data.ocr.extracted_data, data.ocr.confidence_data);
        } else if (data.ocr && data.ocr.error) {
            if (ocrError) {
                document.getElementById('ocrErrorMsg').textContent =
                    'Could not extract information from this document. Please enter details manually.';
                ocrError.style.display = 'block';
            }
        }
    })
    .catch(function (err) {
        if (ocrLoading) ocrLoading.style.display = 'none';
        if (ocrError) {
            document.getElementById('ocrErrorMsg').textContent = 'Upload failed. Please try again.';
            ocrError.style.display = 'block';
        }
        console.error('Upload error:', err);
    });
}

// ── Add File to Display List ────────────────────────────────
function addFileToList(doc) {
    const fileList = document.getElementById('fileList');
    if (!fileList) return;

    const isImage = ['jpg', 'jpeg', 'png'].includes(doc.type.toLowerCase());
    const iconClass = isImage ? 'fa-file-image' : 'fa-file-pdf';

    const item = document.createElement('div');
    item.className = 'file-item';
    item.dataset.docId = doc.id;
    item.innerHTML = `
        <i class="fas ${iconClass}" style="font-size: 1.2rem; color: var(--primary);"></i>
        <div class="file-item-info">
            <div class="file-item-name">${doc.filename}</div>
            <div class="file-item-size">${doc.size}</div>
        </div>
        <button type="button" class="file-item-remove" onclick="removeNewDoc(${doc.id}, this)" title="Remove">
            <i class="fas fa-times"></i>
        </button>
    `;
    fileList.appendChild(item);
}

// ── Remove Existing Document ────────────────────────────────
function removeExistingDoc(docId, btn) {
    if (!confirm('Remove this document?')) return;

    fetch('/employee/documents/' + docId + '/delete', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.success) {
            btn.closest('.file-item').remove();
        }
    });
}

// ── Remove Newly Uploaded Document ──────────────────────────
function removeNewDoc(docId, btn) {
    if (!confirm('Remove this document?')) return;

    fetch('/employee/documents/' + docId + '/delete', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.success) {
            btn.closest('.file-item').remove();
        }
    });
}
