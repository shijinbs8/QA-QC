/**
 * MEP QA/QC Engineering Dashboard - Angular SaaS Interactions
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Sidebar Toggle & State Persistence
  const sidebar = document.getElementById('appSidebar');
  const toggleBtn = document.getElementById('sidebarToggleBtn');
  const savedState = localStorage.getItem('mep_sidebar_collapsed');

  if (sidebar && savedState === 'true') {
    sidebar.classList.add('collapsed');
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      if (window.innerWidth <= 992) {
        sidebar.classList.toggle('mobile-open');
      } else {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('mep_sidebar_collapsed', isCollapsed ? 'true' : 'false');
      }
    });
  }

  // Close mobile sidebar when clicking outside
  document.addEventListener('click', function (e) {
    if (window.innerWidth <= 992 && sidebar && sidebar.classList.contains('mobile-open')) {
      if (!sidebar.contains(e.target) && (!toggleBtn || !toggleBtn.contains(e.target))) {
        sidebar.classList.remove('mobile-open');
      }
    }
  });

  // 2. Quick Status Changer (AJAX)
  const statusSelectors = document.querySelectorAll('.js-quick-status-change');
  statusSelectors.forEach(select => {
    select.addEventListener('change', async function () {
      const inspectionId = this.dataset.inspectionId;
      const newStatus = this.value;
      const badgeTarget = document.getElementById(`status-badge-${inspectionId}`);

      try {
        const response = await fetch(`/api/inspections/${inspectionId}/status/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ status: newStatus })
        });
        const result = await response.json();
        if (result.success) {
          if (badgeTarget) {
            badgeTarget.className = `badge-status ${result.badge_class}`;
            badgeTarget.textContent = result.status;
          }
          showToast(`Status updated to "${result.status}"`, 'success');
        } else {
          showToast(`Failed to update status: ${result.error}`, 'error');
        }
      } catch (err) {
        showToast('Network error while updating status', 'error');
      }
    });
  });

  // 3. Modals toggle
  window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('show');
  };

  window.closeModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('show');
  };

  document.querySelectorAll('.mep-modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', function (e) {
      if (e.target === this) {
        this.classList.remove('show');
      }
    });
  });
});

// CSRF helper
function getCsrfToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  if (cookieValue) return cookieValue;
  const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
  return csrfInput ? csrfInput.value : '';
}

// Simple Toast Notification
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('mepToastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'mepToastContainer';
    toastContainer.style.position = 'fixed';
    toastContainer.style.bottom = '20px';
    toastContainer.style.right = '20px';
    toastContainer.style.zIndex = '9999';
    toastContainer.style.display = 'flex';
    toastContainer.style.flexDirection = 'column';
    toastContainer.style.gap = '10px';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bg = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#2563eb';
  toast.style.background = bg;
  toast.style.color = '#fff';
  toast.style.padding = '10px 16px';
  toast.style.borderRadius = '8px';
  toast.style.fontSize = '0.85rem';
  toast.style.fontWeight = '600';
  toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
  toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
  toast.textContent = message;

  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
