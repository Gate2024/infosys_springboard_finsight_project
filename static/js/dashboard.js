/* 
  dashboard.js - Page 1: Budget Dashboard Interactive JavaScript
  Real-time Search, Multi-parameter Filtering, Dynamic Sorting & Modal Viewing
*/

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('search-input');
  const filterCategory = document.getElementById('filter-category');
  const filterStatus = document.getElementById('filter-status');
  const filterPriority = document.getElementById('filter-priority');
  const filterSort = document.getElementById('filter-sort');
  initializeDeleteConfirmation();

  // Register Event Listeners for Instant Client-Side Search & Filter
  if (searchInput) {
    searchInput.addEventListener('input', triggerSearchAndFilter);
  }
  if (filterCategory) filterCategory.addEventListener('change', triggerSearchAndFilter);
  if (filterStatus) filterStatus.addEventListener('change', triggerSearchAndFilter);
  if (filterPriority) filterPriority.addEventListener('change', triggerSearchAndFilter);
  if (filterSort) filterSort.addEventListener('change', triggerSearchAndFilter);
});

/**
  Performs real-time filtering and sorting on budget cards.
*/
function triggerSearchAndFilter() {
  const query = document.getElementById('search-input')?.value.toLowerCase().trim() || '';
  const selectedCat = document.getElementById('filter-category')?.value || 'All';
  const selectedStatus = document.getElementById('filter-status')?.value || 'All';
  const selectedPriority = document.getElementById('filter-priority')?.value || 'All';
  const selectedSort = document.getElementById('filter-sort')?.value || 'newest';

  const cards = Array.from(document.querySelectorAll('.budget-card'));
  let visibleCount = 0;

  cards.forEach(card => {
    const cardSearch = card.dataset.search || '';
    const cardTitle = card.querySelector('.card-title')?.innerText.toLowerCase() || '';
    const cardCat = card.querySelector('.card-category-badge')?.innerText.trim() || '';
    const cardPriority = card.querySelector('.card-priority-badge')?.innerText.trim() || '';
    const cardStatus = card.querySelector('.card-actions .card-category-badge')?.innerText.replace('Status:', '').trim() || '';

    // Matching Logic
    const matchesSearch = !query || cardSearch.includes(query) || cardTitle.includes(query) || cardCat.toLowerCase().includes(query);
    const matchesCat = (selectedCat === 'All') || cardCat.includes(selectedCat);
    const matchesStatus = (selectedStatus === 'All') || cardStatus.toLowerCase() === selectedStatus.toLowerCase();
    const matchesPriority = (selectedPriority === 'All') || cardPriority.toLowerCase() === selectedPriority.toLowerCase();

    if (matchesSearch && matchesCat && matchesStatus && matchesPriority) {
      card.style.display = 'flex';
      visibleCount++;
    } else {
      card.style.display = 'none';
    }
  });

  // Re-sort visible cards in DOM
  const container = document.querySelector('.budgets-grid');
  if (container) {
    const visibleCards = cards.filter(card => card.style.display !== 'none');
    visibleCards.sort((a, b) => {
      if (selectedSort === 'amount_desc' || selectedSort === 'amount_asc') {
        const amtA = parseFloat(a.dataset.budgetAmount || 0);
        const amtB = parseFloat(b.dataset.budgetAmount || 0);
        return selectedSort === 'amount_desc' ? amtB - amtA : amtA - amtB;
      }
      if (selectedSort === 'oldest' || selectedSort === 'newest') {
        const dateA = Date.parse(a.dataset.created || '') || 0;
        const dateB = Date.parse(b.dataset.created || '') || 0;
        return selectedSort === 'oldest' ? dateA - dateB : dateB - dateA;
      }
      return 0;
    });
    visibleCards.forEach(card => container.appendChild(card));
  }
}

/**
  Opens View Detail Modal and populates budget data from API endpoint.
  @param {number} budgetId 
*/
async function openViewModal(budgetId) {
  const modal = document.getElementById('viewModal');
  const modalBody = document.getElementById('modal-body-content');
  if (!modal || !modalBody) return;

  modalBody.innerHTML = `
    <div style="text-align: center; padding: 2rem;">
      <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2rem; color: var(--emerald-green);"></i>
      <p style="margin-top: 1rem; color: var(--text-muted);">Fetching luxury budget details...</p>
    </div>
  `;
  modal.classList.add('active');

  try {
    const response = await fetch(`/budget/view/${budgetId}`);
    const data = await response.json();

    if (data.success && data.budget) {
      const b = data.budget;
      const spent = parseFloat(b.spent_amount || 0);
      const total = parseFloat(b.budget_amount || 0);
      const rem = parseFloat(b.remaining_amount || (total - spent));
      const pct = total > 0 ? ((spent / total) * 100).toFixed(1) : 0;

      modalBody.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 1rem;">
          <div style="width: 48px; height: 48px; border-radius: 12px; background: ${b.color_label || '#0E5A4E'}; color: white; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
            <i class="fa-solid ${b.budget_icon || 'fa-wallet'}"></i>
          </div>
          <div>
            <h2 style="font-size: 1.5rem; color: var(--navy-dark);">${b.budget_name}</h2>
            <span style="font-size: 0.82rem; color: var(--text-muted);">${b.category} • ${b.currency}</span>
          </div>
        </div>

        <p style="color: var(--text-main); font-size: 0.95rem; margin-bottom: 1.5rem;">${b.description || 'No detailed description provided.'}</p>

        <div class="amounts-row" style="margin-bottom: 1.5rem;">
          <div class="amount-box">
            <span class="amount-label">Allocated</span>
            <span class="amount-val">$${total.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
          </div>
          <div class="amount-box">
            <span class="amount-label">Spent</span>
            <span class="amount-val" style="color: #B91C1C;">$${spent.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
          </div>
          <div class="amount-box">
            <span class="amount-label">Remaining</span>
            <span class="amount-val" style="color: #059669;">$${rem.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
          </div>
        </div>

        <div style="background: rgba(17, 24, 32, 0.04); border-radius: 14px; padding: 1.2rem; margin-bottom: 1.5rem;">
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 8px;">
            <strong>Duration Window</strong>
            <span>${b.start_date} to ${b.end_date}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 8px;">
            <strong>Priority Level</strong>
            <span class="card-priority-badge priority-${b.priority}">${b.priority}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 8px;">
            <strong>Status</strong>
            <span>${b.status}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
            <strong>Recurring Monthly</strong>
            <span>${b.is_recurring ? 'Yes' : 'No'}</span>
          </div>
        </div>

        ${b.notes ? `
          <div style="font-size: 0.88rem; color: var(--text-muted); background: #FFF; border: 1px solid var(--border-subtle); padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem;">
            <strong>Notes:</strong> ${b.notes}
          </div>
        ` : ''}

        <div style="display: flex; justify-content: flex-end; gap: 10px;">
          <a href="/budget/edit/${b.budget_id}" class="btn btn-emerald">
            <i class="fa-regular fa-pen-to-square"></i> Edit Budget
          </a>
          <button type="button" class="btn btn-outline" onclick="closeViewModal()">Close</button>
        </div>
      `;
    } else {
      modalBody.innerHTML = `<p style="color: #DC2626;">Error loading budget details.</p>`;
    }
  } catch (err) {
    modalBody.innerHTML = `<p style="color: #DC2626;">Failed to connect to server.</p>`;
  }
}

function closeViewModal() {
  const modal = document.getElementById('viewModal');
  if (modal) modal.classList.remove('active');
}

function closeViewModalOnBackground(event) {
  if (event.target.id === 'viewModal') {
    closeViewModal();
  }
}

function initializeDeleteConfirmation() {
  const modal = document.getElementById('deleteConfirmModal');
  const cancelButton = document.getElementById('cancelDeleteBudget');
  const confirmButton = document.getElementById('confirmDeleteBudget');
  const forms = document.querySelectorAll('.delete-budget-form');
  let pendingForm = null;

  if (!modal || !cancelButton || !confirmButton || forms.length === 0) return;

  const closeModal = () => {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    pendingForm = null;
  };

  forms.forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      pendingForm = form;
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      confirmButton.focus();
    });
  });

  cancelButton.addEventListener('click', closeModal);

  confirmButton.addEventListener('click', () => {
    if (!pendingForm) return;
    confirmButton.disabled = true;
    pendingForm.submit();
  });

  modal.addEventListener('click', event => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && modal.classList.contains('active')) {
      closeModal();
    }
  });
}
