document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector("[data-profile-image-input]");
  const preview = document.querySelector("[data-profile-preview]");
  if (input && preview) {
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        if (typeof reader.result === "string") preview.src = reader.result;
      });
      reader.readAsDataURL(file);
    });
  }

  const modal = document.querySelector("[data-profile-logout-modal]");
  const openButton = document.querySelector("[data-profile-logout-open]");
  const cancelButton = document.querySelector("[data-profile-logout-cancel]");
  if (!modal || !openButton || !cancelButton) return;

  const closeModal = () => {
    modal.classList.remove("active");
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    openButton.focus();
  };
  openButton.addEventListener("click", () => {
    modal.hidden = false;
    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    cancelButton.focus();
  });
  cancelButton.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
});
