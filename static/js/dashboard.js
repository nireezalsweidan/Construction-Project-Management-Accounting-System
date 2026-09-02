document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  document.querySelectorAll("[data-sidebar-open]").forEach((button) =>
    button.addEventListener("click", () => sidebar?.classList.add("sidebar-open")),
  );
  document.querySelectorAll("[data-sidebar-close]").forEach((button) =>
    button.addEventListener("click", () => sidebar?.classList.remove("sidebar-open")),
  );
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") sidebar?.classList.remove("sidebar-open");
  });

  if (!window.lucide) return;
  const icon = (element, name) => {
    if (element) element.innerHTML = `<i data-lucide="${name}"></i>`;
  };

  icon(document.querySelector(".brand-mark"), "hard-hat");
  icon(document.querySelector(".menu-button"), "menu");
  icon(document.querySelector(".global-search > b"), "search");
  icon(document.querySelector(".icon-button"), "bell");
  icon(document.querySelector(".logout-icon"), "x");

  const navIcons = [
    "layout-dashboard", "folder-kanban", "clipboard-check", "briefcase-business",
    "package-check", "boxes", "users", "file-text", "wallet-cards",
    "circle-dollar-sign", "trending-up", "settings",
  ];
  document.querySelectorAll(".nav-item > b").forEach((node, index) => icon(node, navIcons[index]));

  icon(document.querySelector(".attention-icon"), "trending-down");
  ["folder-kanban", "building-2", "circle-dollar-sign", "file-text"].forEach((name, index) =>
    icon(document.querySelectorAll(".metric-top i")[index], name),
  );
  document.querySelectorAll(".primary-button").forEach((button) => {
    if (button.textContent.includes("＋")) {
      button.innerHTML = `<i data-lucide="plus"></i>${button.textContent.replace("＋", "").trim()}`;
    }
  });
  document.querySelectorAll(".milestone > b").forEach((node) => icon(node, "chevron-right"));
  window.lucide.createIcons({ attrs: { "aria-hidden": "true" } });
});
