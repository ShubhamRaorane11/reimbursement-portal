/**
 * Finance JavaScript — Payment processing helpers.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Set today's date as default for payment date
    const paymentDate = document.querySelector('input[name="payment_date"]');
    if (paymentDate && !paymentDate.value) {
        const today = new Date().toISOString().split('T')[0];
        paymentDate.value = today;
    }
});
