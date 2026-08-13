document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".goal-delete-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Are you sure you want to delete this goal?\nThis action cannot be undone.")) {
        event.preventDefault();
      }
    });
  });
});
