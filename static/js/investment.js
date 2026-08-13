document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".investment-delete-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Are you sure you want to delete this investment?\nThis action cannot be undone.")) {
        event.preventDefault();
      }
    });
  });
});