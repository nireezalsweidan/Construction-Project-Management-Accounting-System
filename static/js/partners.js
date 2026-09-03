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
      <tr data-partner-row${r.type === "client" ? ` class="row-click" data-client-id="${r.id}"` : ""}>
        <td><strong>${esc(r.name)}</strong><span>${esc(r.company || r.label)}</span></td>
        <td><span class="partner-type">${r.label}</span></td>
        <td>${esc(r.contact || "—")}</td>
        <td class="partner-balance" data-id="${r.type}:${r.id}">…</td>
        <td>${statusPill(r.type, r.detail)}</td>
      </tr>`).join("");

    // Fetch open balances for the visible rows only (avoids N+1 over the whole dataset).
    const visible = [...list].slice(0, 60);
    visible.forEach(r => loadBalance(r.type, r.id));

    // Clients are the only type with a detail view so far (see openClientDetail) --
    // Suppliers/Contractors already have their own dedicated pages.
    $$("[data-client-id]", tbody).forEach(row => {
      row.addEventListener("click", () => openClientDetail(row.dataset.clientId));
    });
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

  /* ---- Client detail dialog ---- */
  const clientDialog = $("[data-client-dialog]");
  let detailClientId = null;

  async function openClientDetail(id) {
    detailClientId = id;
    try {
      const [detail, balance] = await Promise.all([
        api(`${API.clients}${id}/`),
        api(`${API.clients}${id}/balance/`),
      ]);
      $("[data-client-detail-name]").textContent = detail.name || "—";
      $("[data-client-detail-company]").textContent = detail.company_name || "";
      $("[data-client-detail-phone]").textContent = detail.phone || "—";
      $("[data-client-detail-email]").textContent = detail.email || "—";
      $("[data-client-detail-tax]").textContent = detail.tax_id || "—";
      $("[data-client-detail-address]").textContent = detail.address || "—";
      $("[data-client-detail-notes]").textContent = detail.notes || "—";
      $("[data-client-detail-outstanding]").textContent = fmtMoney(balance.outstanding_balance);
      clientDialog.showModal();
      loadClientTab("projects");
    } catch (e) {
      alert("Could not load client: " + e.message);
    }
  }

  const clientTabMeta = {
    projects: {
      label: "Projects",
      cols: ["Code", "Name", "Status", "Contract value", "Start date"],
      get: p => [{ v: esc(p.code) }, { v: esc(p.name) }, { v: esc(p.status) }, { v: fmtMoney(p.contract_value) }, { v: esc(p.start_date || "—") }],
    },
    invoices: {
      label: "Invoices",
      cols: ["Invoice #", "Date", "Due", "Total", "Status"],
      get: i => [{ v: esc(i.invoice_number) }, { v: esc(i.invoice_date) }, { v: esc(i.due_date || "—") }, { v: fmtMoney(i.total_amount) }, { v: esc(i.status) }],
    },
    payments: {
      label: "Payments",
      cols: ["Payment #", "Date", "Method", "Amount", "Reference"],
      get: p => [{ v: esc(p.payment_number) }, { v: esc(p.payment_date) }, { v: esc(p.payment_method) }, { v: fmtMoney(p.amount) }, { v: esc(p.reference || "—") }],
    },
  };

  async function loadClientTab(tab) {
    const panel = $("[data-client-tab-panel]");
    const meta = clientTabMeta[tab];
    panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>Loading ${meta.label.toLowerCase()}…</strong></td></tr></tbody></table>`;
    try {
      const rows = await api(`${API.clients}${detailClientId}/${tab}/`);
      if (!rows.length) {
        panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>No ${meta.label.toLowerCase()} recorded for this client.</strong></td></tr></tbody></table>`;
        return;
      }
      panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${meta.get(r).map(c => `<td>${c.v}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    } catch (e) {
      panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>Error: ${esc(e.message)}</strong></td></tr></tbody></table>`;
    }
  }

  function bindClientDialog() {
    $("[data-client-close]").addEventListener("click", () => clientDialog.close());
    clientDialog.addEventListener("click", e => { if (e.target === clientDialog) clientDialog.close(); });
    $$("[data-client-tab]").forEach(btn => {
      btn.addEventListener("click", () => {
        $$("[data-client-tab]").forEach(b => b.classList.toggle("active", b === btn));
        loadClientTab(btn.dataset.clientTab);
      });
    });
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
    bindClientDialog();
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

      // Deep link from the global search overlay (?open_client=<id>) --
      // open that client's detail dialog, then drop the param so a
      // manual refresh doesn't keep reopening it.
      const openClientId = new URLSearchParams(location.search).get("open_client");
      if (openClientId) {
        openClientDetail(openClientId);
        history.replaceState(null, "", location.pathname);
      }
    } catch (e) {
      $("[data-partner-rows]").innerHTML = `<tr><td><strong>Could not load partners</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();
