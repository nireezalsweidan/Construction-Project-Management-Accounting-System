// Company settings page: tab switching and the logo file picker.
(function () {
  const tabs = Array.prototype.slice.call(document.querySelectorAll("[data-settings-tab]"));
  const panes = Array.prototype.slice.call(document.querySelectorAll("[data-settings-pane]"));
  const logoInput = document.getElementById("settings-logo-input");
  const logoReplace = document.querySelector("[data-logo-replace]");
  const logoPreview = document.getElementById("settings-logo-preview");

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
      if (!logoInput.files.length) {
        return;
      }
      var file = logoInput.files[0];
      logoReplace.textContent = file.name;
      if (logoPreview) {
        var objectUrl = URL.createObjectURL(file);
        var img = document.createElement("img");
        img.className = "brand-logo";
        img.src = objectUrl;
        img.alt = "Company logo";
        img.onload = function () { URL.revokeObjectURL(objectUrl); };
        logoPreview.textContent = "";
        logoPreview.appendChild(img);
      }
    });
  }

  /* ---- Users & roles pane ---- */
  // The Users & roles tab talks to the OWNER-only /api/auth/users/ endpoints.
  // It authenticates via the browser session + CSRF cookie (the DRF pipeline
  // accepts both JWT and session auth). Only load when the page renders the
  // pane and the caller is an Owner (only Owners see the Settings nav).
  var usersPane = document.querySelector('[data-settings-pane="users"]');
  if (!usersPane) { return; }
  initUsersPane();

  var taxesPane = document.querySelector('[data-settings-pane="taxes"]');
  if (taxesPane) { initTaxesPane(); }
})();

function initTaxesPane() {
  "use strict";
  var API = "/api/taxes/tax-rates/";
  var state = { rates: [], query: "" };

  var el = function (sel, root) { return (root || document).querySelector(sel); };
  var els = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var banner = el("[data-taxes-banner]");
  var body = el("[data-taxes-body]");
  var empty = el("[data-taxes-empty]");
  var loading = el("[data-taxes-loading]");
  var count = el("[data-taxes-count]");
  var search = el("[data-taxes-search]");
  var modal = el("[data-taxes-modal]");
  var form = el("[data-taxes-form]");
  var modalTitle = el("[data-taxes-modal-title]");

  var dateInput = el("[data-taxes-date-input]");
  var dateValue = form.elements["effective_date"];
  var dateToggle = el("[data-taxes-date-toggle]");
  var calendar = el("[data-taxes-calendar]");

  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function api(url, options) {
    options = options || {};
    var opts = {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    };
    if (options.method && !["GET", "HEAD"].includes(options.method)) {
      opts.headers["X-CSRFToken"] = getCookie("csrftoken");
    }
    var res = await fetch(url, opts);
    if (!res.ok) {
      var detail = res.statusText;
      try { detail = JSON.stringify(await res.json()); } catch (e) { /* ignore */ }
      throw new Error(detail || ("HTTP " + res.status));
    }
    if (res.status === 204) { return null; }
    return res.json();
  }

  function showBanner(text, type) {
    banner.textContent = text;
    banner.className = "users-banner" + (type ? " " + type : "");
    banner.hidden = false;
    clearTimeout(banner._t);
    banner._t = setTimeout(function () { banner.hidden = true; }, 5000);
  }

  function hideBanner() { banner.hidden = true; }

  function statusWord(isActive) {
    return isActive ? "active" : "inactive";
  }

  function fmtRate(rate) {
    var n = Number(rate);
    if (isNaN(n)) { return rate; }
    var s = n.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    return s + "%";
  }

  /* ---- Custom calendar (Effective date) ---- */
  var calView = (function () {
    var now = new Date();
    var year = now.getFullYear();
    var month = now.getMonth(); // 0-based
    var selected = ""; // "YYYY-MM-DD"

    var MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    var DOWS = ["Su","Mo","Tu","We","Th","Fr","Sa"];

    function fmt(d) {
      var m = String(d.getMonth() + 1).padStart(2, "0");
      var day = String(d.getDate()).padStart(2, "0");
      return d.getFullYear() + "-" + m + "-" + day;
    }
    function display(d) {
      return !!d ? d : "Select date";
    }

    function renderCal() {
      var first = new Date(year, month, 1);
      var startDow = first.getDay();
      var daysInMonth = new Date(year, month + 1, 0).getDate();
      var todayStr = fmt(new Date());

      var cells = DOWS.map(function (d) { return '<span class="users-cal-dow">' + d + '</span>'; }).join("");

      var dayCells = "";
      for (var i = 0; i < startDow; i++) {
        dayCells += '<span></span>';
      }
      for (var d = 1; d <= daysInMonth; d++) {
        var ds = year + "-" + String(month + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
        var cls = "users-cal-day";
        if (ds === todayStr) { cls += " today"; }
        if (ds === selected) { cls += " sel"; }
        dayCells += '<button type="button" class="' + cls + '" data-date="' + ds + '">' + d + '</button>';
      }

      calendar.innerHTML =
          '<div class="users-cal-head">'
        +   '<button type="button" class="users-cal-nav" data-cal-prev>‹</button>'
        +   '<span class="users-cal-title">' + MONTHS[month] + ' ' + year + '</span>'
        +   '<button type="button" class="users-cal-nav" data-cal-next>›</button>'
        + '</div>'
        + '<div class="users-cal-grid">' + cells + dayCells + '</div>';
    }

    function show() {
      if (selected) {
        var parts = selected.split("-");
        year = Number(parts[0]);
        month = Number(parts[1]) - 1;
      } else {
        var nowD = new Date();
        year = nowD.getFullYear();
        month = nowD.getMonth();
      }
      renderCal();
      document.body.appendChild(calendar);
      calendar.hidden = false;
      position();
    }

    function position() {
      var rect = dateInput.getBoundingClientRect();
      var calW = calendar.offsetWidth || 264;
      var calH = calendar.offsetHeight || 250;
      var left = Math.min(Math.max(rect.left, 8), window.innerWidth - calW - 8);
      var below = rect.bottom + 6 + calH <= window.innerHeight - 8;
      var top = below ? rect.bottom + 6 : Math.max(8, rect.top - calH - 6);
      calendar.style.left = left + "px";
      calendar.style.top = top + "px";
      calendar.style.maxHeight = (window.innerHeight - 16) + "px";
      calendar.style.overflowY = "auto";
    }

    function hide() { calendar.hidden = true; }

    function select(ds) {
      selected = ds;
      dateValue.value = ds;
      dateInput.value = display(ds);
      hide();
    }

    function init() {
      dateToggle.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (calendar.hidden) { show(); } else { hide(); }
      });
      dateInput.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (calendar.hidden) { show(); } else { hide(); }
      });
      document.addEventListener("click", function (ev) {
        if (calendar.hidden) { return; }
        if (!calendar.contains(ev.target) && !dateToggle.contains(ev.target) && !dateInput.contains(ev.target)) {
          hide();
        }
      });
      calendar.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var prev = ev.target.closest("[data-cal-prev]");
        if (prev) {
          month -= 1;
          if (month < 0) { month = 11; year -= 1; }
          renderCal();
          return;
        }
        var next = ev.target.closest("[data-cal-next]");
        if (next) {
          month += 1;
          if (month > 11) { month = 0; year += 1; }
          renderCal();
          return;
        }
        var day = ev.target.closest("[data-date]");
        if (day) { select(day.getAttribute("data-date")); }
      });
    }

    return { init: init, show: show, hide: hide, setSelected: function (ds) { selected = ds || ""; } };
  })();

  function render() {
    var q = state.query.toLowerCase();
    var list = state.rates.filter(function (t) {
      if (!q) { return true; }
      return (t.name || "").toLowerCase().indexOf(q) !== -1
        || (t.tax_type || "").toLowerCase().indexOf(q) !== -1;
    });

    count.textContent = list.length + " of " + state.rates.length + " tax rates";
    empty.classList.toggle("visible", list.length === 0);
    loading.style.display = "none";

    body.innerHTML = list.map(function (t) {
      var type = t.tax_type || "—";
      return ''
        + '<tr data-id="' + t.id + '">'
        +   '<td><span class="users-name">' + t.name + '</span></td>'
        +   '<td class="users-rate">' + fmtRate(t.rate) + '</td>'
        +   '<td class="users-email">' + type + '</td>'
        +   '<td class="users-lastlogin">' + (t.effective_date || "—") + '</td>'
        +   '<td><span class="users-dot ' + statusWord(t.is_active) + '"></span><span class="users-status ' + statusWord(t.is_active) + '">' + (t.is_active ? "Active" : "Inactive") + '</span></td>'
        +   '<td class="users-actions">'
        +     (t.is_active
        ? '<button type="button" class="users-link" data-taxes-act="deactivate" data-id="' + t.id + '">Deactivate</button>'
        : '<button type="button" class="users-link" data-taxes-act="activate" data-id="' + t.id + '">Activate</button>')
        +     '<button type="button" class="users-link" data-taxes-act="edit" data-id="' + t.id + '">Edit</button>'
        +     '<button type="button" class="users-link danger" data-taxes-act="delete" data-id="' + t.id + '">Delete</button>'
        +   '</td>'
        + '</tr>';
    }).join("");
  }

  async function loadRates() {
    loading.style.display = "block";
    try {
      var data = await api(API + "?page_size=100");
      state.rates = data.results || data;
      render();
    } catch (err) {
      loading.style.display = "none";
      body.innerHTML = "";
      empty.classList.remove("visible");
      showBanner("Could not load tax rates: " + err.message, "error");
    }
  }

  function showModal() {
    document.body.appendChild(modal);
    modal.hidden = false;
    calView.hide();
  }

  function openAdd() {
    modalTitle.textContent = "Add tax rate";
    form.reset();
    form.elements["id"].value = "";
    form.elements["is_active"].value = "true";
    el('[data-taxes-save]').textContent = "Create tax rate";
    dateInput.value = "Select date";
    dateValue.value = "";
    calView.setSelected("");
    showModal();
    form.elements["name"].focus();
  }

  function openEdit(tax) {
    modalTitle.textContent = "Edit tax rate";
    form.reset();
    form.elements["id"].value = tax.id;
    form.elements["name"].value = tax.name || "";
    form.elements["rate"].value = Number(tax.rate);
    form.elements["tax_type"].value = tax.tax_type || "";
    form.elements["effective_date"].value = tax.effective_date || "";
    form.elements["is_active"].value = tax.is_active ? "true" : "false";
    el('[data-taxes-save]').textContent = "Save changes";
    var ed = tax.effective_date || "";
    dateValue.value = ed;
    dateInput.value = ed || "Select date";
    calView.setSelected(ed);
    showModal();
  }

  function closeModal() { modal.hidden = true; calView.hide(); }

  async function submitForm(ev) {
    ev.preventDefault();
    hideBanner();

    var id = form.elements["id"].value;
    var payload = {
      name: form.elements["name"].value.trim(),
      rate: form.elements["rate"].value,
      tax_type: form.elements["tax_type"].value.trim(),
      effective_date: form.elements["effective_date"].value,
      is_active: form.elements["is_active"].value === "true",
    };

    try {
      if (id) {
        await api(API + id + "/", { method: "PATCH", body: JSON.stringify(payload) });
        showBanner("Tax rate updated.", "success");
      } else {
        await api(API, { method: "POST", body: JSON.stringify(payload) });
        showBanner("Tax rate created.", "success");
      }
      closeModal();
      loadRates();
    } catch (err) {
      showBanner("Could not save tax rate: " + err.message, "error");
    }
  }

  async function toggleStatus(id, activate) {
    hideBanner();
    try {
      await api(API + id + "/" + (activate ? "activate" : "deactivate") + "/", { method: "POST" });
      showBanner(activate ? "Tax rate activated." : "Tax rate deactivated.", "success");
      loadRates();
    } catch (err) {
      showBanner("Could not change status: " + err.message, "error");
    }
  }

  var deleteModal = el("[data-taxes-delete-modal]");
  var deleteName = el("[data-taxes-delete-name]");
  var deletingId = null;

  function showDeleteConfirm(id) {
    var tax = state.rates.find(function (t) { return t.id === id; });
    deletingId = id;
    deleteName.textContent = tax ? tax.name : "this tax rate";
    document.body.appendChild(deleteModal);
    deleteModal.hidden = false;
  }
  function hideDeleteConfirm() {
    deleteModal.hidden = true;
    deletingId = null;
  }

  async function removeTax(id) {
    hideBanner();
    try {
      await api(API + id + "/", { method: "DELETE" });
      showBanner("Tax rate deleted.", "success");
      loadRates();
    } catch (err) {
      showBanner("Could not delete tax rate: " + err.message, "error");
    }
  }

  body.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-taxes-act]");
    if (!btn) { return; }
    var act = btn.getAttribute("data-taxes-act");
    var id = btn.getAttribute("data-id");
    var tax = state.rates.find(function (t) { return t.id === id; });
    if (act === "deactivate") { toggleStatus(id, false); }
    else if (act === "activate") { toggleStatus(id, true); }
    else if (act === "edit" && tax) { openEdit(tax); }
    else if (act === "delete") { showDeleteConfirm(id); }
  });

  search.addEventListener("input", function () {
    state.query = this.value.trim();
    render();
  });

  el('[data-taxes-open-add]').addEventListener("click", openAdd);
  els("[data-taxes-modal-close]").forEach(function (b) {
    b.addEventListener("click", closeModal);
  });
  modal.addEventListener("click", function (ev) { if (ev.target === modal) { closeModal(); } });
  form.addEventListener("submit", submitForm);

  calView.init();

  els("[data-taxes-delete-close]").forEach(function (b) {
    b.addEventListener("click", hideDeleteConfirm);
  });
  el("[data-taxes-delete-confirm]").addEventListener("click", function () {
    var id = deletingId;
    hideDeleteConfirm();
    if (id) { removeTax(id); }
  });
  deleteModal.addEventListener("click", function (ev) {
    if (ev.target === deleteModal) { hideDeleteConfirm(); }
  });

  loadRates();
}

function initUsersPane() {
  "use strict";
  var API = "/api/auth/users/";
  var currentUserInput = document.getElementById("current-user-id");
  var CURRENT_USER_ID = currentUserInput ? currentUserInput.value : "";

  var state = { users: [], search: "", query: "" };

  var el = function (sel, root) { return (root || document).querySelector(sel); };
  var els = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  var banner = el("[data-users-banner]");
  var body = el("[data-users-body]");
  var empty = el("[data-users-empty]");
  var loading = el("[data-users-loading]");
  var count = el("[data-users-count]");
  var search = el("[data-users-search]");
  var modal = el("[data-users-modal]");
  var form = el("[data-users-form]");
  var modalTitle = el("[data-users-modal-title]");
  var createHint = el("[data-users-create-hint]");

  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function api(url, options) {
    options = options || {};
    var opts = {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    };
    if (options.method && !["GET", "HEAD"].includes(options.method)) {
      opts.headers["X-CSRFToken"] = getCookie("csrftoken");
    }
    var res = await fetch(url, opts);
    if (!res.ok) {
      var detail = res.statusText;
      try { detail = JSON.stringify(await res.json()); } catch (e) { /* ignore */ }
      throw new Error(detail || ("HTTP " + res.status));
    }
    if (res.status === 204) { return null; }
    return res.json();
  }

  function initials(u) {
    return ((u.first_name || "?")[0] + (u.last_name || "?")[0]).toUpperCase();
  }

  function initialsName(u) {
    return (u.first_name || "") + " " + (u.last_name || "");
  }

  function roleWord(role) {
    return role === "OWNER" ? "owner" : role === "ACCOUNTANT" ? "accountant" : "user";
  }

  function statusWord(isActive) {
    return isActive ? "active" : "inactive";
  }

  function lastLogin(u) {
    if (!u.last_login) { return "Never"; }
    return new Date(u.last_login).toLocaleString();
  }

  function showBanner(text, type) {
    banner.textContent = text;
    banner.className = "users-banner" + (type ? " " + type : "");
    banner.hidden = false;
    clearTimeout(banner._t);
    banner._t = setTimeout(function () { banner.hidden = true; }, 5000);
  }

  function hideBanner() { banner.hidden = true; }

  function render() {
    var q = state.query.toLowerCase();
    var list = state.users.filter(function (u) {
      if (!q) { return true; }
      return (u.first_name || "").toLowerCase().indexOf(q) !== -1
        || (u.last_name || "").toLowerCase().indexOf(q) !== -1
        || (u.username || "").toLowerCase().indexOf(q) !== -1
        || (u.email || "").toLowerCase().indexOf(q) !== -1
        || (u.role || "").toLowerCase().indexOf(q) !== -1;
    });

    count.textContent = list.length + " of " + state.users.length + " users";
    empty.classList.toggle("visible", list.length === 0);
    loading.style.display = "none";

    body.innerHTML = list.map(function (u) {
      var isSelf = CURRENT_USER_ID && u.id === CURRENT_USER_ID;
      var roleLabel = u.role_display || u.role;
      var actions = "";
      if (isSelf) {
        actions = '<span class="users-self">You</span>';
      } else {
        actions = ''
          + (u.is_active
            ? '<button type="button" class="users-link" data-users-act="deactivate" data-id="' + u.id + '">Deactivate</button>'
            : '<button type="button" class="users-link" data-users-act="activate" data-id="' + u.id + '">Activate</button>')
          + '<button type="button" class="users-link" data-users-act="edit" data-id="' + u.id + '">Edit</button>'
          + '<button type="button" class="users-link danger" data-users-act="delete" data-id="' + u.id + '">Delete</button>';
      }
      return ''
        + '<tr data-id="' + u.id + '">'
        +   '<td><div class="users-identity">'
        +     '<span class="users-avatar">' + initials(u) + '</span>'
        +     '<div><div class="users-name">' + (u.first_name || "") + ' ' + (u.last_name || "") + '</div>'
        +     '<div class="users-username">@' + (u.username || "") + '</div></div>'
        +   '</div></td>'
        +   '<td class="users-email">' + (u.email || "") + '</td>'
        +   '<td><span class="users-badge ' + roleWord(u.role) + '">' + roleLabel + '</span></td>'
        +   '<td><span class="users-dot ' + statusWord(u.is_active) + '"></span><span class="users-status ' + statusWord(u.is_active) + '">' + (u.is_active ? "Active" : "Inactive") + '</span></td>'
        +   '<td class="users-lastlogin">' + lastLogin(u) + '</td>'
        +   '<td class="users-actions">' + actions + '</td>'
        + '</tr>';
    }).join("");
  }

  async function loadUsers() {
    loading.style.display = "block";
    try {
      var data = await api(API + "?page_size=100");
      state.users = data.results || data;
      render();
    } catch (err) {
      loading.style.display = "none";
      body.innerHTML = "";
      empty.classList.remove("visible");
      showBanner("Could not load users: " + err.message, "error");
    }
  }

  function openAdd() {
    modalTitle.textContent = "Add user";
    createHint.style.display = "block";
    form.reset();
    form.elements["id"].value = "";
    form.elements["is_active"].value = "true";
    var saveBtn = el('[data-users-save]');
    saveBtn.textContent = "Create user";
    modal.hidden = false;
    form.elements["first_name"].focus();
  }

  function openEdit(user) {
    modalTitle.textContent = "Edit user";
    createHint.style.display = "none";
    form.reset();
    form.elements["id"].value = user.id;
    form.elements["first_name"].value = user.first_name || "";
    form.elements["last_name"].value = user.last_name || "";
    form.elements["email"].value = user.email || "";
    form.elements["phone"].value = user.phone || "";
    form.elements["role"].value = user.role;
    form.elements["is_active"].value = user.is_active ? "true" : "false";
    var saveBtn = el('[data-users-save]');
    saveBtn.textContent = "Save changes";
    modal.hidden = false;
  }

  function closeModal() { modal.hidden = true; }

  async function submitForm(ev) {
    ev.preventDefault();
    hideBanner();

    var id = form.elements["id"].value;
    var payload = {
      first_name: form.elements["first_name"].value.trim(),
      last_name: form.elements["last_name"].value.trim(),
      email: form.elements["email"].value.trim(),
      phone: form.elements["phone"].value.trim(),
      role: form.elements["role"].value,
      is_active: form.elements["is_active"].value === "true",
    };

    try {
      if (id) {
        await api(API + id + "/", { method: "PATCH", body: JSON.stringify(payload) });
        showBanner("User updated.", "success");
      } else {
        await api(API, { method: "POST", body: JSON.stringify({
          first_name: payload.first_name,
          last_name: payload.last_name,
          email: payload.email,
          role: payload.role,
          phone: payload.phone || undefined,
        }) });
        showBanner("User created. Their login credentials were emailed.", "success");
      }
      closeModal();
      loadUsers();
    } catch (err) {
      showBanner("Could not save user: " + err.message, "error");
    }
  }

  async function toggleStatus(id, activate) {
    hideBanner();
    try {
      await api(API + id + "/" + (activate ? "activate" : "deactivate") + "/", { method: "POST" });
      showBanner(activate ? "User activated." : "User deactivated.", "success");
      loadUsers();
    } catch (err) {
      showBanner("Could not change status: " + err.message, "error");
    }
  }

  async function removeUser(id) {
    hideBanner();
    if (!confirm("Delete this user? This cannot be undone.")) { return; }
    try {
      await api(API + id + "/", { method: "DELETE" });
      showBanner("User deleted.", "success");
      loadUsers();
    } catch (err) {
      showBanner("Could not delete user: " + err.message, "error");
    }
  }

  body.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-users-act]");
    if (!btn) { return; }
    var act = btn.getAttribute("data-users-act");
    var id = btn.getAttribute("data-id");
    var user = state.users.find(function (u) { return u.id === id; });
    if (act === "deactivate") { toggleStatus(id, false); }
    else if (act === "activate") { toggleStatus(id, true); }
    else if (act === "edit" && user) { openEdit(user); }
    else if (act === "delete") { removeUser(id); }
  });

  search.addEventListener("input", function () {
    state.query = this.value.trim();
    render();
  });

  el('[data-users-open-add]').addEventListener("click", openAdd);
  els("[data-users-modal-close]").forEach(function (b) {
    b.addEventListener("click", closeModal);
  });
  modal.addEventListener("click", function (ev) { if (ev.target === modal) { closeModal(); } });
  form.addEventListener("submit", submitForm);

  loadUsers();
}
