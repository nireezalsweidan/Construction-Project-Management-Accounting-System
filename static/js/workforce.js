/* Workforce page.
   A single view of the team pulled from the employees API: employee
   profiles plus their active project assignments and labor rates. Rendered
   as live metrics + a table instead of mock rows. */
(() => {
  "use strict";

  const API = "/api/employees/";
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = { employees: [], assignments: [], statusFilter: "all", search: "" };

  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function api(url, options = {}) {
    const opts = { credentials: "same-origin", headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options };
    if (options.method && !["GET", "HEAD"].includes(options.method)) {
      opts.headers["X-CSRFToken"] = getCookie("csrftoken");
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = JSON.stringify(await res.json()); } catch (e) { /* ignore */ }
      throw new Error(`${res.status}: ${detail}`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  async function fetchAll(url) {
    const rows = [];
    let next = url;
    while (next) {
      const data = await api(next);
      rows.push(...(data.results || []));
      next = data.next;
    }
    return rows;
  }

  const fmtMoney = v => {
    const n = Number(v);
    return Number.isFinite(n)
      ? n.toLocaleString("en-US", { style: "currency", currency: CURRENCY, minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : `${CURRENCY} ${v || "0.00"}`;
  };

  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const statusPill = s => {
    const safe = s || "ACTIVE";
    const cls = safe === "ACTIVE" ? " active" : (safe === "TERMINATED" ? " warning" : "");
    return `<span class="status${cls}"><i></i>${esc(safe)}</span>`;
  };

  function activeProject(assignments) {
    const active = assignments.find(a => !a.released_at) || assignments[assignments.length - 1] || null;
    if (!active) return "—";
    return `${esc(active.project.name)}<span>${esc(active.project.code)}</span>`;
  }

  function renderRows() {
    const tbody = $("[data-workforce-rows]");
    let list = state.employees;
    if (state.statusFilter !== "all") list = list.filter(e => e.employment_status === state.statusFilter);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(e => [e.name, e.employee_number, e.position, e.department, e.email].some(v => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      tbody.innerHTML = `<tr><td><strong>No team members found</strong><span>Try adjusting the search or status filter.</span></td><td>—</td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(e => {
      const assigns = state.assignments[e.id] || [];
      return `
        <tr>
          <td><strong>${esc(e.name)}</strong><span>${esc(e.employee_number)}</span></td>
          <td>${esc(e.position || "—")}</td>
          <td>${esc(e.department || "—")}</td>
          <td>${activeProject(assigns)}</td>
          <td>${e.labor_rate != null ? fmtMoney(e.labor_rate) : "—"}</td>
          <td>${statusPill(e.employment_status)}</td>
        </tr>`;
    }).join("");
  }

  async function renderMetrics() {
    const employees = state.employees;
    $("[data-metric=active]").textContent = employees.filter(e => e.employment_status === "ACTIVE").length;
    $("[data-metric=onleave]").textContent = employees.filter(e => e.employment_status === "ON_LEAVE").length;
    const assignmentList = Object.values(state.assignments).flat();
    $("[data-metric=assignments]").textContent = assignmentList.length;
    const staffed = new Set(assignmentList.filter(a => !a.released_at).map(a => a.project.id));
    $("[data-metric=projects]").textContent = staffed.size;
  }

  function bindFilters() {
    $$("[data-status-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.statusFilter = btn.dataset.statusFilter;
        $$("[data-status-filter]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderRows();
      });
    });
    const searchInput = $("#workforce-search-input");
    searchInput.addEventListener("input", () => { state.search = searchInput.value; renderRows(); });
  }

  async function loadAssignments(employee) {
    try {
      const data = await api(`${API}${employee.id}/projects/`);
      return data;
    } catch (e) {
      return [];
    }
  }

  async function loadEmployee(employee) {
    try {
      const detail = await api(`${API}${employee.id}/`);
      const assigns = await loadAssignments(employee);
      return { ...detail, assignments: assigns };
    } catch (e) {
      return { ...employee, labor_rate: null, assignments: [] };
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindFilters();
    try {
      const list = await fetchAll(API);
      const loaded = await Promise.all(list.map(loadEmployee));
      state.employees = loaded;
      state.assignments = {};
      loaded.forEach(e => { state.assignments[e.id] = e.assignments || []; });
      await renderMetrics();
      renderRows();
    } catch (e) {
      $("[data-workforce-rows]").innerHTML = `<tr><td><strong>Could not load workforce</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();
