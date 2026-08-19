document.addEventListener("DOMContentLoaded", () => {
  initializeExpenseFilters();
  initializeExpenseDeleteConfirmation();
  initializeExpenseFormValidation();
});

function initializeExpenseFilters() {
  const searchInput = document.getElementById("expense-search-input");
  const categoryFilter = document.getElementById("expense-filter-category");
  const paymentFilter = document.getElementById("expense-filter-payment");
  const sortFilter = document.getElementById("expense-filter-sort");

  if (!searchInput && !categoryFilter && !paymentFilter && !sortFilter) return;

  [searchInput, categoryFilter, paymentFilter, sortFilter].forEach((control) => {
    if (!control) return;
    const eventName = control.tagName === "INPUT" ? "input" : "change";
    control.addEventListener(eventName, applyExpenseFilters);
  });
}

function applyExpenseFilters() {
  const query = document.getElementById("expense-search-input")?.value.toLowerCase().trim() || "";
  const category = document.getElementById("expense-filter-category")?.value || "All";
  const payment = document.getElementById("expense-filter-payment")?.value || "All";
  const sortBy = document.getElementById("expense-filter-sort")?.value || "newest";
  const rows = Array.from(document.querySelectorAll(".expense-row"));
  const tbody = document.querySelector(".expense-table tbody");

  rows.forEach((row) => {
    const matchesSearch = !query || (row.dataset.search || "").includes(query);
    const matchesCategory = category === "All" || row.dataset.category === category;
    const matchesPayment = payment === "All" || row.dataset.payment === payment;
    row.style.display = matchesSearch && matchesCategory && matchesPayment ? "" : "none";
  });

  const visibleRows = rows.filter((row) => row.style.display !== "none");
  visibleRows.sort((a, b) => {
    if (sortBy === "amount_asc" || sortBy === "amount_desc") {
      const amountA = parseFloat(a.dataset.amount || 0);
      const amountB = parseFloat(b.dataset.amount || 0);
      return sortBy === "amount_asc" ? amountA - amountB : amountB - amountA;
    }

    const dateA = Date.parse(a.dataset.date || "") || 0;
    const dateB = Date.parse(b.dataset.date || "") || 0;
    return sortBy === "oldest" ? dateA - dateB : dateB - dateA;
  });

  if (tbody) {
    visibleRows.forEach((row) => tbody.appendChild(row));
  }
}

async function openExpenseModal(transactionId) {
  const modal = document.getElementById("expenseViewModal");
  const modalBody = document.getElementById("expense-modal-body");
  if (!modal || !modalBody) return;

  modalBody.innerHTML = `
    <div style="text-align:center; padding:2rem;">
      <i class="fa-solid fa-circle-notch fa-spin" style="font-size:2rem; color:var(--emerald-green);"></i>
      <p style="margin-top:1rem; color:var(--text-muted);">Loading expense details...</p>
    </div>
  `;
  modal.classList.add("active");

  try {
    const response = await fetch(`/expense/view/${transactionId}`);
    const data = await response.json();

    if (!data.success || !data.expense) {
      modalBody.innerHTML = `<p style="color:#B91C1C;">Unable to load expense details.</p>`;
      return;
    }

    const expense = data.expense;
    const amount = Number.parseFloat(expense.amount || 0);
    modalBody.innerHTML = `
      <div class="expense-detail-head">
        <div class="expense-detail-icon">
          <i class="fa-solid fa-receipt"></i>
        </div>
        <div>
          <h2>${escapeHtml(expense.description || "Untitled expense")}</h2>
          <p>${escapeHtml(expense.category || "")} · Expense #${expense.id}</p>
        </div>
      </div>

      <div class="expense-detail-grid">
        <div class="expense-detail-item">
          <span>Amount</span>
          <strong>$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
        </div>
        <div class="expense-detail-item">
          <span>Date</span>
          <strong>${escapeHtml(expense.date || "")}</strong>
        </div>
        <div class="expense-detail-item">
          <span>Payment Mode</span>
          <strong>${escapeHtml(expense.payment_mode || "")}</strong>
        </div>
        <div class="expense-detail-item">
          <span>Category</span>
          <strong>${escapeHtml(expense.category || "")}</strong>
        </div>
      </div>

      <div style="display:flex; justify-content:flex-end; gap:10px;">
        <a href="/expense/edit/${expense.id}" class="btn btn-emerald">
          <i class="fa-regular fa-pen-to-square"></i> Edit Expense
        </a>
        <button type="button" class="btn btn-outline" onclick="closeExpenseModal()">Close</button>
      </div>
    `;
  } catch (error) {
    modalBody.innerHTML = `<p style="color:#B91C1C;">Failed to connect to the server.</p>`;
  }
}

function closeExpenseModal() {
  const modal = document.getElementById("expenseViewModal");
  if (modal) modal.classList.remove("active");
}

function closeExpenseModalOnBackground(event) {
  if (event.target.id === "expenseViewModal") {
    closeExpenseModal();
  }
}

function initializeExpenseDeleteConfirmation() {
  const modal = document.getElementById("expenseDeleteConfirmModal");
  const cancelButton = document.getElementById("cancelDeleteExpense");
  const confirmButton = document.getElementById("confirmDeleteExpense");
  const forms = document.querySelectorAll(".delete-expense-form");
  let pendingForm = null;

  if (!modal || !cancelButton || !confirmButton || forms.length === 0) return;

  const closeModal = () => {
    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
    pendingForm = null;
    confirmButton.disabled = false;
  };

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      pendingForm = form;
      modal.classList.add("active");
      modal.setAttribute("aria-hidden", "false");
      confirmButton.focus();
    });
  });

  cancelButton.addEventListener("click", closeModal);
  confirmButton.addEventListener("click", () => {
    if (!pendingForm) return;
    confirmButton.disabled = true;
    pendingForm.submit();
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("active")) {
      closeModal();
    }
  });
}

function initializeExpenseFormValidation() {
  const form = document.getElementById("expenseForm");
  if (!form) return;

  form.addEventListener("submit", (event) => {
    const amount = parseFloat(document.getElementById("amount")?.value || 0);
    const category = document.getElementById("category")?.value;
    const paymentMode = document.getElementById("payment_mode")?.value;
    const date = document.getElementById("date")?.value;
    const messages = [];

    if (Number.isNaN(amount) || amount <= 0) {
      messages.push("Amount must be greater than zero.");
    }

    if (!category) {
      messages.push("Category is required.");
    }

    if (!paymentMode) {
      messages.push("Payment mode is required.");
    }

    if (!date) {
      messages.push("Date is required.");
    } else {
      const selectedDate = new Date(`${date}T00:00:00`);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (selectedDate > today) {
        messages.push("Date cannot be in the future.");
      }
    }

    if (messages.length > 0) {
      event.preventDefault();
      messages.forEach((message) => showToast(message, "danger"));
    }
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
