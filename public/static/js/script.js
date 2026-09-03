const container = document.getElementById('authContainer');
document.getElementById('toSignUp').addEventListener('click', () => container.classList.add('active'));
document.getElementById('toSignIn').addEventListener('click', () => container.classList.remove('active'));

// Mobile fallback switch (no overlay animation below 760px)
const signInPanel = document.getElementById('signInPanel');
const signUpPanel = document.getElementById('signUpPanel');
function setMobilePanel(which){
  if(which === 'signup'){
    signUpPanel.classList.add('mobile-active');
    signInPanel.classList.remove('mobile-active');
  } else {
    signInPanel.classList.add('mobile-active');
    signUpPanel.classList.remove('mobile-active');
  }
}
setMobilePanel('signin');
document.querySelectorAll('[data-switch]').forEach(el=>{
  el.addEventListener('click', () => {
    const which = el.getAttribute('data-switch');
    if(which === 'signup'){
      container.classList.add('active');
    } else {
      container.classList.remove('active');
    }
    setMobilePanel(which);
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


