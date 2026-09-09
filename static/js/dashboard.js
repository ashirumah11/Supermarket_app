/**
 * StockFlow Dashboard & Notification Engine Client JS
 */

document.addEventListener('DOMContentLoaded', function () {
  const badgeCounter = document.getElementById('unread-badge-counter');

  function updateUnreadCount() {
    fetch('/notifications/api/unread-count/', {
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
      .then(response => response.json())
      .then(data => {
        if (badgeCounter) {
          if (data.unread_count > 0) {
            badgeCounter.textContent = data.unread_count;
            badgeCounter.style.display = 'flex';
          } else {
            badgeCounter.textContent = '0';
            badgeCounter.style.display = 'none';
          }
        }
      })
      .catch(err => console.debug("StockFlow notification check:", err));
  }

  // Poll for notification updates every 30 seconds
  if (badgeCounter) {
    setInterval(updateUnreadCount, 30000);
  }

  // Handle asynchronous mark as read for notification list items
  document.querySelectorAll('.btn-mark-read-async').forEach(button => {
    button.addEventListener('click', function (e) {
      e.preventDefault();
      const notifId = this.getAttribute('data-notif-id');
      const notifItem = document.getElementById(`notif-item-${notifId}`);

      fetch(`/notifications/${notifId}/read/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/json'
        }
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            if (notifItem) {
              notifItem.classList.remove('bg-light', 'border-primary');
              notifItem.classList.add('opacity-75');
              this.remove();
            }
            if (badgeCounter) {
              if (data.unread_count > 0) {
                badgeCounter.textContent = data.unread_count;
                badgeCounter.style.display = 'flex';
              } else {
                badgeCounter.style.display = 'none';
              }
            }
          }
        })
        .catch(err => console.error("Error marking notification read:", err));
    });
  });
});
