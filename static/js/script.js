const publicThemeStorageKey = "finsight-public-theme";

function applyPublicTheme(theme) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = nextTheme;
  document.querySelectorAll("[data-public-theme-choice]").forEach((choice) => {
    const active = choice.dataset.publicThemeChoice === nextTheme;
    choice.classList.toggle("active", active);
    choice.setAttribute("aria-pressed", String(active));
  });
}

let publicTheme = "light";
try {
  publicTheme = window.localStorage.getItem(publicThemeStorageKey) === "dark" ? "dark" : "light";
} catch (error) {
  publicTheme = "light";
}
applyPublicTheme(publicTheme);

document.querySelectorAll("[data-public-theme-choice]").forEach((choice) => {
  choice.addEventListener("click", () => {
    const nextTheme = choice.dataset.publicThemeChoice === "dark" ? "dark" : "light";
    try {
      window.localStorage.setItem(publicThemeStorageKey, nextTheme);
    } catch (error) {
      // Keep the selected theme active for the current page if storage is unavailable.
    }
    applyPublicTheme(nextTheme);
  });
});

const publicAuthMode = window.location.hash === "#signup" ? "signup" : "signin";
document.querySelectorAll("[data-public-nav-link]").forEach((link) => {
  const active = document.body.classList.contains("auth-page") && link.dataset.publicNavLink === publicAuthMode;
  link.classList.toggle("is-active", active);
  if (active) link.setAttribute("aria-current", "page");
});

const container = document.getElementById('authContainer');
const signInPanel = document.getElementById('signInPanel');
const signUpPanel = document.getElementById('signUpPanel');
function setPanel(which){
  if(!container || !signInPanel || !signUpPanel) return;
  const showSignUp = which === 'signup';
  container.classList.toggle('active', showSignUp);
  signInPanel.hidden = showSignUp;
  signUpPanel.hidden = !showSignUp;
}
setPanel(window.location.hash === '#signup' ? 'signup' : 'signin');
document.querySelectorAll('[data-switch]').forEach(el=>{
  el.addEventListener('click', () => {
    const which = el.getAttribute('data-switch');
    setPanel(which);
  });
});

// Password visibility toggles
document.querySelectorAll('.toggle-visibility').forEach(btn=>{
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    btn.textContent = isPassword ? 'Hide' : 'Show';
    btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
  });
});

// Keep the native submit flow intact while giving the button immediate feedback.
document.querySelectorAll('form').forEach(form=>{
  form.addEventListener('submit', () => {
    const button = form.querySelector('.submit-btn');
    if (!button) return;
    button.disabled = true;
    button.classList.add('is-loading');
    button.querySelector('span').textContent = 'Please wait…';
  });
});

document.querySelectorAll('[data-dismiss-auth-alert]').forEach(button=>{
  button.addEventListener('click', () => button.closest('.auth-alert')?.remove());
});


