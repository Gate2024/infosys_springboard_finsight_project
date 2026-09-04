function showToast(message, category = "info") {
  const container = document.getElementById("toast-container");
  if (!container) {
    alert(message);
    return;
  }

  const toast = document.createElement("div");
  toast.className = `flash-alert flash-${category}`;
  toast.textContent = message;
  container.appendChild(toast);

  window.setTimeout(() => {
    toast.remove();
  }, 3500);
}

document.addEventListener("DOMContentLoaded", () => {
  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 768px)").matches) {
        document.body.classList.toggle("sidebar-open");
        return;
      }

      document.body.classList.toggle("sidebar-collapsed");
    });
  }

  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
    const select = document.querySelector("[data-theme-select]");
    if (select) select.value = document.documentElement.dataset.theme;
  };

  const themeSelect = document.querySelector("[data-theme-select]");
  if (themeSelect) {
    themeSelect.addEventListener("change", () => {
      applyTheme(themeSelect.value);
    });
  }

  const accountMenu = document.querySelector("[data-account-menu]");
  if (!accountMenu) return;

  const trigger = accountMenu.querySelector("[data-account-menu-trigger]");
  const panel = accountMenu.querySelector("[data-account-menu-panel]");
  if (!trigger || !panel) return;

  const closeAccountMenu = () => {
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;
  };

  const closeMenu = closeAccountMenu;

  trigger.addEventListener("click", () => {
    const isOpen = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", String(!isOpen));
    panel.hidden = isOpen;
  });

  document.addEventListener("click", (event) => {
    if (!accountMenu.contains(event.target)) closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
      trigger.focus();
    }
  });

  const notificationMenu = document.querySelector("[data-notification-menu]");
  if (!notificationMenu) return;
  const notificationTrigger = notificationMenu.querySelector("[data-notification-trigger]");
  const notificationPanel = notificationMenu.querySelector("[data-notification-panel]");
  if (!notificationTrigger || !notificationPanel) return;
  const closeNotifications = () => {
    notificationTrigger.setAttribute("aria-expanded", "false");
    notificationPanel.hidden = true;
  };
  notificationTrigger.addEventListener("click", (event) => {
    event.stopPropagation();
    closeAccountMenu();
    const isOpen = notificationTrigger.getAttribute("aria-expanded") === "true";
    notificationTrigger.setAttribute("aria-expanded", String(!isOpen));
    notificationPanel.hidden = isOpen;
  });

  const themeForm = document.querySelector("[data-notification-theme-form]");
  const themeValue = themeForm && themeForm.querySelector("[data-notification-theme-value]");
  const themeChoices = themeForm ? themeForm.querySelectorAll("[data-notification-theme-choice]") : [];
  const syncThemeChoices = () => {
    const currentTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    themeChoices.forEach((choice) => {
      const active = choice.dataset.notificationThemeChoice === currentTheme;
      choice.classList.toggle("active", active);
      choice.setAttribute("aria-pressed", String(active));
    });
  };
  themeChoices.forEach((choice) => {
    choice.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const nextTheme = choice.dataset.notificationThemeChoice;
      const previousTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
      applyTheme(nextTheme);
      syncThemeChoices();
      if (!themeForm || !themeValue) return;
      themeValue.value = nextTheme;
      try {
        const response = await fetch(themeForm.action, {
          method: "POST",
          body: new FormData(themeForm),
          credentials: "same-origin",
          redirect: "follow",
        });
        if (!response.ok) throw new Error("Theme preference could not be saved");
      } catch (error) {
        applyTheme(previousTheme);
        syncThemeChoices();
        showToast("Unable to save theme preference.", "danger");
      }
    });
  });
  document.addEventListener("click", (event) => {
    if (!notificationMenu.contains(event.target)) closeNotifications();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNotifications();
  });
});
