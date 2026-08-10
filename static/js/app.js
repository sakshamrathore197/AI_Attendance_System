/* -------------------------------------------------------------------
 * AI CCTV Attendance System - Client Application JavaScript
 * ------------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // Auto-highlight active navigation item
  const currentPath = window.location.pathname;
  document.querySelectorAll(".nav-item").forEach(item => {
    const href = item.getAttribute("href");
    if (href === currentPath || (href !== "/" && currentPath.startsWith(href))) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
});

// Toast notification helper
function showToast(message, type = "success") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  const bg = type === "success" ? "#10b981" : type === "error" ? "#f43f5e" : "#38bdf8";
  toast.style.cssText = `background: ${bg}; color: #000; padding: 12px 20px; border-radius: 10px; font-weight: 700; font-size: 0.88rem; box-shadow: 0 10px 25px rgba(0,0,0,0.3); transition: all 0.3s ease; opacity: 0; transform: translateY(20px);`;
  toast.innerText = message;

  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  }, 50);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Modal Toggle Helper
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("active");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("active");
}

// Image Lightbox Preview Helper
function showImagePreview(src, title = "Screenshot Proof") {
  let modal = document.getElementById("lightbox-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "lightbox-modal";
    modal.className = "modal-backdrop";
    modal.innerHTML = `
      <div class="modal-card" style="max-width: 700px; text-align: center;">
        <div style="display:flex; justify-between; align-items:center; margin-bottom: 16px;">
          <h3 id="lightbox-title" class="card-title">Image Proof</h3>
          <button class="btn btn-secondary" onclick="closeModal('lightbox-modal')" style="padding: 4px 10px;">✕</button>
        </div>
        <img id="lightbox-img" src="" style="width: 100%; max-height: 500px; object-fit: contain; border-radius: 12px; border: 1px solid var(--border-color);" />
      </div>
    `;
    document.body.appendChild(modal);
  }
  document.getElementById("lightbox-title").innerText = title;
  document.getElementById("lightbox-img").src = src;
  openModal("lightbox-modal");
}
