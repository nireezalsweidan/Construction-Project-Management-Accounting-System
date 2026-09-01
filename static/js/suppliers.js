/* Supplier Management page.
   Consumes the DRF endpoints served by SupplierViewSet under
   /api/suppliers/ using the authenticated session (SessionAuthentication).
   No supplier login/role here -- the endpoint only lets authenticated
   internal users (Owner/Accountant) through, enforced server-side. */
(() => {
  "use strict";

  const API = "/api/suppliers/suppliers/";
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = { suppliers: [], statusFilter: "all", search: "" };

  /* ---- CSRF token for unsafe methods (SessionAuthentication + CSRF) ---- */
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
    return res.json();
  }

  async function fetchAllSuppliers() {
    const rows = [];
    let url = API;
    while (url) {
      const data = await api(url);
      rows.push(...(data.results || []));
      url = data.next;
    }
    return rows;
  }

  const fmtMoney = v => {
    const n = Number(v);
    return Number.isFinite(n) ? n.toLocaleString("en-US", { style: "currency", currency: CURRENCY, minimumFractionDigits: 2 }) : CURRENCY + " " + (v == null ? "0.00" : v);
  };

  const statusPill = s => {
    if (s === "DRAFT" || s === "CANCELLED") return `<span class="status warning">${s}</span>`;
    if (s === "PAID" || s === "RECEIVED") return `<span class="status">${s}</span>`;
    if (s === "OVERDUE") return `<span class="status warning">${s}</span>`;
    return `<span class="status">${s}</span>`;
  };

  /* ---- Table rendering ---- */
  function renderRows() {
    const tbody = $("[data-supplier-rows]");
    let list = state.suppliers;
    if (state.statusFilter === "active") list = list.filter(s => s.is_active);
    if (state.statusFilter === "inactive") list = list.filter(s => !s.is_active);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(s => [s.name, s.company_name, s.email, s.tax_number].some(v => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7"><b>No suppliers found</b><span>Try adjusting the search or status filter.</span></td></tr>`;
      return;
    }
    tbody.innerHTML = list.map(s => `
      <tr class="row-click" data-supplier-id="${s.id}">
        <td><b>${esc(s.name)}</b>${s.company_name ? `<small>${esc(s.company_name)}</small>` : ""}</td>
        <td><b>${esc(s.phone || "—")}</b>${s.email ? `<small>${esc(s.email)}</small>` : ""}</td>
        <td>${esc(s.payment_terms || "—")}</td>
        <td>${CURRENCY}</td>
        <td data-balance="${s.id}">—</td>
        <td>${s.is_active ? `<span class="status">Active</span>` : `<span class="status warning">Inactive</span>`}</td>
        <td>→</td>
      </tr>`).join("");

    $$("[data-supplier-id]", tbody).forEach(row => {
      row.addEventListener("click", () => openDetail(row.dataset.supplierId));
    });

    // Populate per-row outstanding balance lazily.
    list.forEach(async s => {
      try {
        const b = await api(`${API}${s.id}/balance/`);
        const cell = $(`[data-balance="${s.id}"]`, tbody);
        if (cell) cell.textContent = fmtMoney(b.outstanding_balance);
      } catch (e) { /* leave placeholder */ }
    });
  }

  function renderMetrics() {
    const active = state.suppliers.filter(s => s.is_active).length;
    $("[data-metric=total]").textContent = state.suppliers.length;
    $("[data-metric=active]").textContent = active;
    $("[data-metric=invoiced]").textContent = "…";
    $("[data-metric=outstanding]").textContent = "…";
    (async () => {
      let invoiced = 0, outstanding = 0;
      await Promise.all(state.suppliers.map(async s => {
        try {
          const b = await api(`${API}${s.id}/balance/`);
          invoiced += Number(b.total_invoiced || 0);
          outstanding += Number(b.outstanding_balance || 0);
        } catch (e) { /* skip */ }
      }));
      $("[data-metric=invoiced]").textContent = fmtMoney(invoiced);
      $("[data-metric=outstanding]").textContent = fmtMoney(outstanding);
    })();
  }

  /* ---- Detail dialog ---- */
  const dialog = $("[data-supplier-dialog]");
  let detailSupplierId = null;
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function openDetail(id) {
    detailSupplierId = id;
    try {
      const [detail, balance] = await Promise.all([api(`${API}${id}/`), api(`${API}${id}/balance/`)]);
      $("[data-detail-name]").textContent = detail.name || "—";
      $("[data-detail-company]").textContent = detail.company_name || "";
      $("[data-detail-phone]").textContent = detail.phone || "—";
      $("[data-detail-email]").textContent = detail.email || "—";
      $("[data-detail-address]").textContent = detail.address || "—";
      $("[data-detail-tax]").textContent = detail.tax_number || "—";
      $("[data-detail-terms]").textContent = detail.payment_terms || "—";
      $("[data-detail-notes]").textContent = detail.notes || "—";
      $("[data-detail-status]").textContent = detail.is_active ? "Active" : "Inactive";
      $("[data-detail-currency]").textContent = detail.currency || CURRENCY;
      $("[data-detail-invoiced]").textContent = fmtMoney(balance.total_invoiced);
      $("[data-detail-paid]").textContent = fmtMoney(balance.total_paid);
      $("[data-detail-outstanding]").textContent = fmtMoney(balance.outstanding_balance);
      dialog.showModal();
      loadTab("purchase_orders");
    } catch (e) {
      alert("Could not load supplier: " + e.message);
    }
  }

  const tabMeta = {
    purchase_orders: {
      label: "Purchase orders",
      cols: ["Reference", "Order date", "Due", "Total", "Status"],
      get: s => [{ v: s.po_number }, { v: s.order_date }, { v: s.expected_delivery_date || "—" }, { v: fmtMoney(s.total_amount) }, { v: statusPill(s.status) }],
    },
    invoices: {
      label: "Invoices",
      cols: ["Invoice #", "Date", "Due", "Total", "Status"],
      get: s => [{ v: s.invoice_number }, { v: s.invoice_date }, { v: s.due_date || "—" }, { v: fmtMoney(s.total_amount) }, { v: statusPill(s.status) }],
    },
    payments: {
      label: "Payments",
      cols: ["Payment #", "Date", "Method", "Amount", "Reference"],
      get: s => [{ v: s.payment_number }, { v: s.payment_date }, { v: s.payment_method }, { v: fmtMoney(s.amount) }, { v: s.reference || "—" }],
    },
  };

  async function loadTab(tab) {
    const panel = $("[data-tab-panel]");
    panel.innerHTML = `<div class="supplier-empty">Loading ${tabMeta[tab].label.toLowerCase()}…</div>`;
    try {
      const rows = await api(`${API}${detailSupplierId}/${tab}/`);
      if (!rows.length) {
        panel.innerHTML = `<div class="supplier-empty">No ${tabMeta[tab].label.toLowerCase()} recorded for this supplier.</div>`;
        return;
      }
      const head = tabMeta[tab].cols.map(c => `<th>${c}</th>`).join("");
      const body = rows.map(r => `<tr>${tabMeta[tab].get(r).map(c => `<td>${c.v}</td>`).join("")}</tr>`).join("");
      panel.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    } catch (e) {
      panel.innerHTML = `<div class="supplier-empty">Error: ${esc(e.message)}</div>`;
    }
  }

  function bindDialog() {
    $("[data-supplier-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); });
    $$("[data-tab]").forEach(btn => {
      btn.addEventListener("click", () => {
        $$("[data-tab]").forEach(b => b.classList.toggle("active", b === btn));
        loadTab(btn.dataset.tab);
      });
    });
  }

  /* ---- Create supplier ---- */
  function bindCreate() {
    const overlay = $("[data-supplier-create]");
    $("[data-supplier-new]").addEventListener("click", () => { overlay.hidden = false; });
    $("[data-supplier-create-close]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-supplier-create-cancel]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-supplier-form]").addEventListener("submit", async e => {
      e.preventDefault();
      const form = e.currentTarget;
      const payload = Object.fromEntries(new FormData(form).entries());
      try {
        await api(API, { method: "POST", body: JSON.stringify(payload) });
        overlay.hidden = true;
        form.reset();
        await refresh();
      } catch (err) {
        alert("Could not create supplier: " + err.message);
      }
    });
  }

  /* ---- Filters & search ---- */
  function bindFilters() {
    $$("[data-status-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.statusFilter = btn.dataset.statusFilter;
        $$("[data-status-filter]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderRows();
      });
    });
    const searchInput = $("#supplier-search-input");
    searchInput.addEventListener("input", () => { state.search = searchInput.value; renderRows(); });
  }

  async function refresh() {
    state.suppliers = await fetchAllSuppliers();
    renderMetrics();
    renderRows();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindDialog();
    bindCreate();
    bindFilters();
    try {
      await refresh();
    } catch (e) {
      $("[data-supplier-rows]").innerHTML = `<tr class="empty-row"><td colspan="7"><b>Could not load suppliers</b><span>${esc(e.message)}</span></td></tr>`;
    }
  });
})();
