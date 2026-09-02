/* Clients & Partners page.
   A single view of clients, suppliers, and contractors pulled from their
   DRF endpoints. The page is read-only: it renders the relationship
   directory (metrics + table) from live data instead of mock rows. */
(() => {
  "use strict";

  const API = {
    clients: "/api/clients/clients/",
    suppliers: "/api/suppliers/suppliers/",
    contractors: "/api/contractors/",
    supplierSummary: "/api/suppliers/suppliers/summary/",
  };
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = { clients: [], suppliers: [], contractors: [], typeFilter: "all", search: "" };

  /* ---- CSRF token (kept for completeness; this page only GETs) ---- */
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

  const statusPill = (type, row) => {
    if (type === "supplier") {
      const ok = row.is_active;
      return `<span class="status${ok ? " active" : ""}"><i></i>${ok ? "ACTIVE" : "INACTIVE"}</span>`;
    }
    if (type === "contractor") {
      const s = row.status || "ACTIVE";
      const cls = s === "ACTIVE" ? " active" : (s === "TERMINATED" ? " warning" : "");
      return `<span class="status${cls}"><i></i>${esc(s)}</span>`;
    }
    return `<span class="status active"><i></i>ACTIVE</span>`;
  };

  function mergeRows() {
    const rows = [];
    state.clients.forEach(c => rows.push({ type: "client", label: "Client", id: c.id, name: c.name, company: c.company_name, contact: c.email || c.phone, detail: c }));
    state.suppliers.forEach(s => rows.push({ type: "supplier", label: "Supplier", id: s.id, name: s.name, company: s.company_name, contact: s.email || s.phone, detail: s }));
    state.contractors.forEach(c => rows.push({ type: "contractor", label: "Contractor", id: c.id, name: c.name, company: c.company_name, contact: c.email || c.phone, detail: c }));
    return rows;
  }

  function renderRows() {
    const tbody = $("[data-partner-rows]");
    let list = mergeRows();
    if (state.typeFilter !== "all") list = list.filter(r => r.type === state.typeFilter);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(r => [r.name, r.company, r.contact].some(v => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      tbody.innerHTML = `<tr><td><strong>No partners found</strong><span>Try adjusting the search or type filter.</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(r => `
      <tr data-partner-row>
        <td><strong>${esc(r.name)}</strong><span>${esc(r.company || r.label)}</span></td>
        <td><span class="partner-type">${r.label}</span></td>
        <td>${esc(r.contact || "—")}</td>
        <td class="partner-balance" data-id="${r.type}:${r.id}">…</td>
        <td>${statusPill(r.type, r.detail)}</td>
      </tr>`).join("");

    // Fetch open balances for the visible rows only (avoids N+1 over the whole dataset).
    const visible = [...list].slice(0, 60);
    visible.forEach(r => loadBalance(r.type, r.id));
  }

  async function loadBalance(type, id) {
    const cell = $(`.partner-balance[data-id="${type}:${id}"]`);
    if (!cell) return;
    try {
      let url, value;
      if (type === "client") {
        const d = await api(`${API.clients}${id}/`);
        value = d.outstanding_balance;
      } else if (type === "supplier") {
        const d = await api(`${API.suppliers}${id}/`);
        value = d.outstanding_balance;
      } else {
        value = null;
      }
      cell.textContent = (value == null || value === "") ? "—" : fmtMoney(value);
    } catch (e) {
      cell.textContent = "—";
    }
  }

  async function renderMetrics() {
    $("[data-metric=clients]").textContent = state.clients.length;
    $("[data-metric=suppliers]").textContent = state.suppliers.length;
    $("[data-metric=contractors]").textContent = state.contractors.length;
    try {
      const s = await api(API.supplierSummary);
      $("[data-metric=balance]").textContent = fmtMoney(s.outstanding_balance);
    } catch (e) {
      $("[data-metric=balance]").textContent = fmtMoney(0);
    }
  }

  function bindFilters() {
    $$("[data-type-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.typeFilter = btn.dataset.typeFilter;
        $$("[data-type-filter]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderRows();
      });
    });
    const searchInput = $("#partner-search-input");
    searchInput.addEventListener("input", () => { state.search = searchInput.value; renderRows(); });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindFilters();
    try {
      const [clients, suppliers, contractors] = await Promise.all([
        fetchAll(API.clients),
        fetchAll(API.suppliers),
        fetchAll(API.contractors),
      ]);
      state.clients = clients;
      state.suppliers = suppliers;
      state.contractors = contractors;
      await renderMetrics();
      renderRows();
    } catch (e) {
      $("[data-partner-rows]").innerHTML = `<tr><td><strong>Could not load partners</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();
