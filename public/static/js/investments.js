document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("investmentDeleteConfirmModal");
  const cancelButton = document.getElementById("cancelDeleteInvestment");
  const confirmButton = document.getElementById("confirmDeleteInvestment");
  const forms = document.querySelectorAll(".investment-delete-form");
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
});
