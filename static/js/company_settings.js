// Company settings page: tab switching and the logo file picker.
(function () {
  const tabs = Array.prototype.slice.call(document.querySelectorAll("[data-settings-tab]"));
  const panes = Array.prototype.slice.call(document.querySelectorAll("[data-settings-pane]"));
  const logoInput = document.getElementById("settings-logo-input");
  const logoReplace = document.querySelector("[data-logo-replace]");

  function showTab(name) {
    tabs.forEach(function (tab) {
      tab.classList.toggle("active", tab.getAttribute("data-settings-tab") === name);
    });
    panes.forEach(function (pane) {
      pane.classList.toggle("active", pane.getAttribute("data-settings-pane") === name);
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      showTab(tab.getAttribute("data-settings-tab"));
    });
  });

  var cancel = document.querySelector("[data-settings-cancel]");
  if (cancel) {
    cancel.addEventListener("click", function () {
      window.location.reload();
    });
  }

  if (logoReplace && logoInput) {
    logoReplace.addEventListener("click", function () {
      logoInput.click();
    });
    logoInput.addEventListener("change", function () {
      if (logoInput.files.length) {
        logoReplace.textContent = logoInput.files[0].name;
      }
    });
  }
})();