/* 
  main.js - Global Application JavaScript
  Toast Notification Engine, Flash Auto-dismiss, Modal Helper Functions
*/

/**
  Displays a sleek, luxury toast notification on the bottom-right of the screen.
  @param {string} message - Notification text
  @param {string} type - 'success', 'danger', or 'info'
*/
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let iconClass = 'fa-circle-check';
  if (type === 'danger') iconClass = 'fa-circle-exclamation';
  if (type === 'info') iconClass = 'fa-circle-info';

  toast.innerHTML = `
    <i class="fa-solid ${iconClass}" style="font-size: 1.1rem;"></i>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  // Auto remove after 3.5 seconds
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(50px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Auto-dismiss Flash Alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  const flashAlerts = document.querySelectorAll('.flash-alert');
  flashAlerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.4s ease';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });
});
