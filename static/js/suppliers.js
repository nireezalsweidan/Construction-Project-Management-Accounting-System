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
    return Number.isFinite(n)
      ? n.toLocaleString("en-US", { style: "currency", currency: CURRENCY, minimumFractionDigits: 0, maximumFractionDigits: 0 })
      : v == null || v === "" ? "$0" : `${CURRENCY} ${v}`;
  };

  const statusPill = s => {
    if (s === "DRAFT" || s === "CANCELLED" || s === "OVERDUE") return `<span class="status warning"><i></i>${s}</span>`;
    return `<span class="status"><i></i>${s}</span>`;
  };

  const supplierStatusPill = active => active
    ? `<span class="status active"><i></i>Active</span>`
    : `<span class="status"><i></i>Inactive</span>`;

  /* ---- Table rendering ---- */
  function renderRows() {
    const tbody = $("[data-supplier-rows]");
    let list = state.suppliers;
    if (state.statusFilter === "active") list = list.filter(s => s.is_active);
    if (state.statusFilter === "inactive") list = list.filter(s => !s.is_active);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(s => [s.name, s.company_name, s.email, s.tax_number].some(v => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      tbody.innerHTML = `<tr><td><strong>No suppliers found</strong><span>Try adjusting the search or status filter.</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
      return;
    }
    tbody.innerHTML = list.map(s => `
      <tr class="row-click" data-supplier-id="${s.id}">
        <td><strong>${esc(s.name)}</strong><span>View details</span></td>
        <td><strong>${esc(s.phone || "—")}</strong><span>${esc(s.email || "")}</span></td>
        <td>${esc(s.payment_terms || "—")}</td>
        <td data-balance="${s.id}">—</td>
        <td>${supplierStatusPill(s.is_active)}</td>
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
    (async () => {
      try {
        const s = await api(`${API}summary/`);
        $("[data-metric=total]").textContent = s.total_suppliers;
        $("[data-metric=active]").textContent = s.active_suppliers;
        $("[data-metric=invoiced]").textContent = fmtMoney(s.total_invoiced);
        $("[data-metric=outstanding]").textContent = fmtMoney(s.outstanding_balance);
      } catch (e) {
        // Fall back to client-side totals from whatever is loaded.
        const active = state.suppliers.filter(s => s.is_active).length;
        $("[data-metric=total]").textContent = state.suppliers.length;
        $("[data-metric=active]").textContent = active;
      }
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
      const status = $("[data-detail-status]");
      status.className = "status" + (detail.is_active ? " active" : "");
      status.innerHTML = `<i></i>${detail.is_active ? "Active" : "Inactive"}`;
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
    const meta = tabMeta[tab];
    panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>Loading ${meta.label.toLowerCase()}…</strong></td></tr></tbody></table>`;
    try {
      const rows = await api(`${API}${detailSupplierId}/${tab}/`);
      if (!rows.length) {
        panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>No ${meta.label.toLowerCase()} recorded for this supplier.</strong></td></tr></tbody></table>`;
        return;
      }
      panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${meta.get(r).map(c => `<td>${c.v}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    } catch (e) {
      panel.innerHTML = `<table><thead><tr>${meta.cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${meta.cols.length}"><strong>Error: ${esc(e.message)}</strong></td></tr></tbody></table>`;
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
      // Deep link from the global search overlay (?open=<supplier-id>) --
      // open that supplier's detail dialog, then drop the param so a
      // manual refresh of the page doesn't keep reopening it.
      const openId = new URLSearchParams(location.search).get("open");
      if (openId) {
        openDetail(openId);
        history.replaceState(null, "", location.pathname);
      }
    } catch (e) {
      $("[data-supplier-rows]").innerHTML = `<tr><td><strong>Could not load suppliers</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();