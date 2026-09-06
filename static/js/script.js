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

document.querySelectorAll('[data-otp-countdown]').forEach(panel=>{
  const button = panel.querySelector('[data-otp-resend]');
  const label = panel.querySelector('[data-otp-resend-label]');
  if (!button || !label) return;

  let remaining = Math.max(
    0,
    Number.parseInt(panel.dataset.otpRemainingSeconds || '0', 10) || 0
  );
  const eligible = panel.dataset.otpResendEligible === 'true';
  const limitReached = panel.dataset.otpLimitReached === 'true';
  const readyLabel = button.dataset.readyLabel || 'Resend OTP';
  const countdownLabel = button.dataset.countdownLabel || 'Resend OTP in {seconds}s';

  const render = () => {
    const ready = eligible && remaining === 0;
    button.disabled = !ready;
    button.setAttribute('aria-disabled', String(!ready));
    if (limitReached) {
      label.textContent = 'Resend limit reached';
    } else if (ready) {
      label.textContent = readyLabel;
    } else if (remaining === 0) {
      label.textContent = readyLabel;
    } else {
      label.textContent = countdownLabel.replace('{seconds}', String(remaining));
    }
  };

  render();
  if (eligible && remaining > 0) {
    const timer = window.setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
      if (remaining === 0) window.clearInterval(timer);
    }, 1000);
  }
});


