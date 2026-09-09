/**
 * StockFlow Core Application JavaScript
 */

// Helper to get CSRF token from cookies
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener('DOMContentLoaded', function () {
  // Mobile Sidebar Toggle
  const sidebar = document.getElementById('sidebar-wrapper');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const backdrop = document.getElementById('sidebar-backdrop');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      if (backdrop) backdrop.classList.toggle('show');
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', function () {
      if (sidebar) sidebar.classList.remove('show');
      backdrop.classList.remove('show');
    });
  }

  // Auto-dismiss Django flash alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 6000);
  });

  // Global Quick Stock Modal Initializer
  const quickStockModal = document.getElementById('quickStockModal');
  if (quickStockModal) {
    quickStockModal.addEventListener('show.bs.modal', function (event) {
      const button = event.relatedTarget;
      if (!button) return;

      const productId = button.getAttribute('data-product-id');
      const productName = button.getAttribute('data-product-name');
      const productSku = button.getAttribute('data-product-sku');
      const currentStock = button.getAttribute('data-product-stock');
      const actionType = button.getAttribute('data-action-type') || 'in';

      const titleElem = document.getElementById('quickStockModalTitle');
      const nameElem = document.getElementById('quickStockProductName');
      const skuElem = document.getElementById('quickStockProductSku');
      const stockElem = document.getElementById('quickStockCurrentQty');
      const formElem = document.getElementById('quickStockForm');
      const actionTypeInput = document.getElementById('quickStockActionType');
      const submitBtn = document.getElementById('quickStockSubmitBtn');

      if (nameElem) nameElem.textContent = productName;
      if (skuElem) skuElem.textContent = productSku;
      if (stockElem) stockElem.textContent = currentStock;
      if (actionTypeInput) actionTypeInput.value = actionType;

      if (actionType === 'out') {
        if (titleElem) titleElem.textContent = 'Record Stock OUT (Dispatch / Sale)';
        if (formElem) formElem.action = `/stock-movements/out/${productId}/`;
        if (submitBtn) {
          submitBtn.textContent = 'Confirm Stock OUT';
          submitBtn.className = 'btn btn-danger';
        }
      } else {
        if (titleElem) titleElem.textContent = 'Record Stock IN (Restock / Delivery)';
        if (formElem) formElem.action = `/stock-movements/in/${productId}/`;
        if (submitBtn) {
          submitBtn.textContent = 'Confirm Stock IN';
          submitBtn.className = 'btn btn-success';
        }
      }
    });
  }
});
