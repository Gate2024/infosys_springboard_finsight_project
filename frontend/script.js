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
  el.addEventListener('click', () => setMobilePanel(el.getAttribute('data-switch')));
});

// Password visibility toggles
document.querySelectorAll('.toggle-visibility').forEach(btn=>{
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    btn.textContent = isPassword ? 'Hide' : 'Show';
  });
});

// Form submits (hook up to your backend)
document.getElementById('signInForm').addEventListener('submit', e => { e.preventDefault(); console.log('sign in submitted'); });
document.getElementById('signUpForm').addEventListener('submit', e => { e.preventDefault(); console.log('sign up submitted'); });
