/**
 * SepsisSense Core Frontend Script
 * Theme toggle, mobile navigation, real-time health polling, and toast messages.
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Theme Toggle Logic
  const themeToggle = document.getElementById("themeToggle");
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const activeTheme = document.documentElement.getAttribute("data-theme");
      const nextTheme = activeTheme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", nextTheme);
      localStorage.setItem("sepsissense_theme", nextTheme);
    });
  }

  // 2. Mobile Menu Toggle
  const menuToggle = document.getElementById("menuToggle");
  const primaryNav = document.getElementById("primaryNav");

  if (menuToggle && primaryNav) {
    menuToggle.addEventListener("click", () => {
      const expanded = menuToggle.getAttribute("aria-expanded") === "true";
      menuToggle.setAttribute("aria-expanded", !expanded);
      primaryNav.classList.toggle("is-open");
    });
  }

  // 3. System API Health Check
  const checkHealth = async () => {
    const footerDot = document.getElementById("footerDot");
    const footerText = document.getElementById("footerApiStatus");
    const heroDot = document.getElementById("siteApiDot");
    const heroText = document.getElementById("siteApiText");

    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        if (footerDot) {
          footerDot.className = "status-dot";
        }
        if (footerText) {
          footerText.textContent = "API Online · Model Loaded";
        }
        if (heroDot) {
          heroDot.className = "status-dot";
        }
        if (heroText) {
          heroText.textContent = "Live backend connected (ESP32 /api/readings active)";
        }
      } else {
        throw new Error("HTTP " + res.status);
      }
    } catch (err) {
      if (footerDot) footerDot.className = "status-dot offline";
      if (footerText) footerText.textContent = "API Offline";
      if (heroDot) heroDot.className = "status-dot offline";
      if (heroText) heroText.textContent = "Connecting to backend…";
    }
  };

  checkHealth();
  setInterval(checkHealth, 25000);

  // 4. Global Toast Notification Helper
  window.showToast = (message, type = "info") => {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${type === "error" ? "⚠️" : "✓"}</span> <div>${message}</div>`;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  };
});
