/**
 * Approver JavaScript — Review action modals.
 */

// Modal functions are inline in the review template.
// This file is reserved for additional approver-specific logic.

document.addEventListener('DOMContentLoaded', function () {
    // Auto-focus rejection reason textarea when reject modal opens
    const rejectModal = document.getElementById('rejectModal');
    if (rejectModal) {
        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (rejectModal.classList.contains('active')) {
                    const textarea = rejectModal.querySelector('textarea');
                    if (textarea) setTimeout(function () { textarea.focus(); }, 100);
                }
            });
        });
        observer.observe(rejectModal, { attributes: true, attributeFilter: ['class'] });
    }
});
