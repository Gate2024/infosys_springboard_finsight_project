/* 
  form.js - Page 2: Create / Edit Budget Client-Side Form Logic
  Real-time input validation, date range check, and automatic error toasts
*/

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('budgetForm');
  const startDateInput = document.getElementById('start_date');
  const endDateInput = document.getElementById('end_date');

  if (form) {
    form.addEventListener('submit', (e) => {
      let isValid = true;
      let errorMessages = [];
      const tr = window.finSightTranslate || ((value) => value);

      const nameVal = document.getElementById('budget_name')?.value.trim();
      const catVal = document.getElementById('category')?.value;
      const amtVal = parseFloat(document.getElementById('budget_amount')?.value || 0);
      const spentVal = parseFloat(document.getElementById('spent_amount')?.value || 0);
      const startDate = startDateInput?.value;
      const endDate = endDateInput?.value;

      if (!nameVal) {
        isValid = false;
        errorMessages.push(tr("Budget Name is required."));
      }

      if (!catVal) {
        isValid = false;
        errorMessages.push(tr("Category selection is required."));
      }

      if (isNaN(amtVal) || amtVal < 0) {
        isValid = false;
        errorMessages.push(tr("Allocated Budget Amount must be 0 or greater."));
      }

      if (isNaN(spentVal) || spentVal < 0) {
        isValid = false;
        errorMessages.push(tr("Initial Spent Amount cannot be negative."));
      }

      if (!startDate || !endDate) {
        isValid = false;
        errorMessages.push(tr("Both Start Date and End Date are required."));
      } else if (startDate > endDate) {
        isValid = false;
        errorMessages.push(tr("Start Date cannot be later than End Date."));
      }

      if (!isValid) {
        e.preventDefault();
        errorMessages.forEach(msg => showToast(msg, 'danger'));
      }
    });
  }
});
