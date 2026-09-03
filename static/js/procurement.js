/* Purchase Order Management page (CPMAS-42).
   Consumes the DRF endpoints served under /api/purchasing/ (PurchaseOrder,
   PurchaseOrderItem, GoodsReceipt) plus /api/suppliers/, /api/inventory/
   materials/ and /api/inventory/warehouses/ for the create/receive forms'
   dropdowns. Follows the same fetch-all-then-filter-client-side pattern as
   suppliers.js. */
(() => {
  "use strict";

  const PO_API = "/api/purchasing/purchase-orders/";
  const ITEM_API = "/api/purchasing/purchase-order-items/";
  const RECEIPT_API = "/api/purchasing/goods-receipts/";
  const SUPPLIER_API = "/api/suppliers/suppliers/";
  const MATERIAL_API = "/api/inventory/materials/";
  const WAREHOUSE_API = "/api/inventory/warehouses/";
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const state = { pos: [], suppliers: [], materials: [], warehouses: [], statusFilter: "all", search: "", dateFrom: "", dateTo: "" };

  const appUserId = () => document.querySelector(".topbar")?.dataset.appUserId || "";

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

  const STATUS_LABELS = {
    DRAFT: "Draft", SUBMITTED: "Submitted", APPROVED: "Approved",
    PARTIALLY_RECEIVED: "Partially received", RECEIVED: "Received", CANCELLED: "Cancelled",
  };
  const OPEN_STATUSES = ["SUBMITTED", "APPROVED", "PARTIALLY_RECEIVED"];

  const statusPill = s => {
    const cls = s === "CANCELLED" ? "warning" : (s === "PARTIALLY_RECEIVED" ? "partially-received" : (s === "SUBMITTED" ? "in-progress" : ""));
    return `<span class="status ${cls}"><i></i>${STATUS_LABELS[s] || s}</span>`;
  };

  /* ---- Reference data for dropdowns ---- */
  async function loadReferenceData() {
    const [suppliers, materials, warehouses] = await Promise.all([
      fetchAll(SUPPLIER_API), fetchAll(MATERIAL_API), fetchAll(WAREHOUSE_API),
    ]);
    state.suppliers = suppliers;
    state.materials = materials;
    state.warehouses = warehouses;
  }

  function fillSelect(select, items, labelFn, placeholder) {
    select.innerHTML = `<option value="">${placeholder}</option>` + items.map(i => `<option value="${i.id}">${esc(labelFn(i))}</option>`).join("");
  }

  /* ---- List + metrics ---- */
  function withinNextWeek(dateStr) {
    if (!dateStr) return false;
    const target = new Date(dateStr + "T00:00:00");
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const in7 = new Date(today); in7.setDate(in7.getDate() + 7);
    return target >= today && target <= in7;
  }

  function renderMetrics() {
    const pos = state.pos;
    const open = pos.filter(p => OPEN_STATUSES.includes(p.status)).length;
    const awaiting = pos.filter(p => p.status === "SUBMITTED").length;
    const committed = pos.filter(p => !["DRAFT", "CANCELLED"].includes(p.status))
      .reduce((sum, p) => sum + Number(p.total_amount || 0), 0);
    const due = pos.filter(p => !["RECEIVED", "CANCELLED"].includes(p.status) && withinNextWeek(p.expected_delivery_date)).length;
    $("[data-metric=open]").textContent = open;
    $("[data-metric=awaiting]").textContent = awaiting;
    $("[data-metric=committed]").textContent = fmtMoney(committed);
    $("[data-metric=due]").textContent = due;
  }

  function filteredPos() {
    let list = state.pos;
    if (state.statusFilter !== "all") list = list.filter(p => p.status === state.statusFilter);
    if (state.dateFrom) list = list.filter(p => p.order_date >= state.dateFrom);
    if (state.dateTo) list = list.filter(p => p.order_date <= state.dateTo);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(p => [p.po_number, p.supplier_name].some(v => (v || "").toLowerCase().includes(q)));
    return list;
  }

  function renderRows() {
    const tbody = $("[data-po-rows]");
    const list = filteredPos();
    if (!list.length) {
      tbody.innerHTML = `<tr><td><strong>No purchase orders found</strong><span>Try adjusting the search, status, or date filters.</span></td><td>—</td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
      return;
    }
    tbody.innerHTML = list.map(p => `
      <tr class="row-click" data-po-id="${p.id}">
        <td><strong>${esc(p.po_number)}</strong><span>View details</span></td>
        <td>${esc(p.supplier_name || "—")}</td>
        <td>${esc(p.order_date)}</td>
        <td>${esc(p.expected_delivery_date || "—")}</td>
        <td>${fmtMoney(p.total_amount)}</td>
        <td>${statusPill(p.status)}</td>
      </tr>`).join("");
    $$("[data-po-id]", tbody).forEach(row => row.addEventListener("click", () => openDetail(row.dataset.poId)));
  }

  async function refreshPos() {
    state.pos = await fetchAll(PO_API);
    renderMetrics();
    renderRows();
  }

  /* ---- Detail dialog ---- */
  const dialog = $("[data-po-dialog]");
  let detailPo = null;

  const ACTIONS = {
    DRAFT: [{ action: "submit", label: "Submit for approval" }, { action: "cancel", label: "Cancel" }],
    SUBMITTED: [{ action: "approve", label: "Approve" }, { action: "cancel", label: "Cancel" }],
    APPROVED: [{ action: "cancel", label: "Cancel" }],
  };

  function renderActionBar(po) {
    const bar = $("[data-po-actionbar]");
    const actions = ACTIONS[po.status] || [];
    bar.innerHTML = actions.map(a =>
      `<button type="button" class="${a.action === 'cancel' ? 'quiet-button' : 'primary-button'}" data-po-transition="${a.action}">${a.label}</button>`
    ).join("") || "<p>No status actions available.</p>";
    $$("[data-po-transition]", bar).forEach(btn => {
      btn.addEventListener("click", () => runTransition(btn.dataset.poTransition));
    });
  }

  async function runTransition(action) {
    if (action === "cancel" && !confirm("Cancel this purchase order?")) return;
    try {
      const updated = await api(`${PO_API}${detailPo.id}/${action}/`, { method: "POST" });
      detailPo = updated;
      await refreshPos();
      renderDetailHeader(updated);
      renderActionBar(updated);
      renderReceiveSection(updated);
      renderAddItemVisibility(updated);
    } catch (e) {
      alert("Could not update status: " + e.message);
    }
  }

  function renderDetailHeader(po) {
    $("[data-detail-number]").textContent = po.po_number;
    $("[data-detail-supplier]").textContent = po.supplier_name || "";
    const status = $("[data-detail-status]");
    status.className = "status";
    status.innerHTML = `<i></i>${STATUS_LABELS[po.status] || po.status}`;
    $("[data-detail-subtotal]").textContent = fmtMoney(po.subtotal);
    $("[data-detail-tax]").textContent = fmtMoney(po.tax_amount);
    $("[data-detail-total]").textContent = fmtMoney(po.total_amount);
    $("[data-detail-delivery]").textContent = po.expected_delivery_date || "—";
    $("[data-detail-order-date]").textContent = po.order_date;
  }

  function renderItems(po) {
    const tbody = $("[data-po-items]");
    if (!po.items || !po.items.length) {
      tbody.innerHTML = `<tr><td colspan="7"><strong>No line items yet.</strong></td></tr>`;
      return;
    }
    tbody.innerHTML = po.items.map(i => `
      <tr>
        <td><strong>${esc(i.material_name)}</strong><span>${esc(i.material_sku || "")}</span></td>
        <td>${i.quantity}</td>
        <td>${fmtMoney(i.unit_price)}</td>
        <td>${fmtMoney(i.tax_amount)}</td>
        <td>${fmtMoney(i.total_amount)}</td>
        <td>${i.quantity_received}</td>
        <td>${i.quantity_remaining}</td>
      </tr>`).join("");
  }

  function renderAddItemVisibility(po) {
    const isDraft = po.status === "DRAFT";
    $("[data-po-add-item]").hidden = !isDraft;
    if (!isDraft) $("[data-po-item-form]").hidden = true;
  }

  function renderReceiveSection(po) {
    const section = $("[data-po-receive-section]");
    const remaining = (po.items || []).filter(i => Number(i.quantity_remaining) > 0);
    const receivable = ["APPROVED", "PARTIALLY_RECEIVED"].includes(po.status) && remaining.length > 0;
    section.hidden = !receivable;
    if (!receivable) return;
    fillSelect($("select[name=warehouse]", section), state.warehouses, w => w.name, "Select warehouse…");
    $("[data-receive-lines]", section).innerHTML = remaining.map(i => `
      <label>${esc(i.material_name)} (remaining: ${i.quantity_remaining})
        <input type="number" data-receive-item="${i.id}" min="0" max="${i.quantity_remaining}" step="0.001" placeholder="0">
      </label>`).join("");
  }

  async function openDetail(id) {
    try {
      const po = await api(`${PO_API}${id}/`);
      detailPo = po;
      renderDetailHeader(po);
      renderActionBar(po);
      renderItems(po);
      renderAddItemVisibility(po);
      renderReceiveSection(po);
      dialog.showModal();
    } catch (e) {
      alert("Could not load purchase order: " + e.message);
    }
  }

  function bindDialog() {
    $("[data-po-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); });
  }

  /* ---- Add line item (DRAFT only) ---- */
  function bindAddItem() {
    const form = $("[data-po-item-form]");
    $("[data-po-add-item]").addEventListener("click", () => {
      fillSelect($("select[name=material]", form), state.materials, m => `${m.name} (${m.sku})`, "Select material…");
      form.hidden = false;
    });
    $("[data-po-item-cancel]").addEventListener("click", () => { form.hidden = true; form.reset(); });
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());
      payload.purchase_order = detailPo.id;
      try {
        await api(ITEM_API, { method: "POST", body: JSON.stringify(payload) });
        form.reset();
        form.hidden = true;
        const po = await api(`${PO_API}${detailPo.id}/`);
        detailPo = po;
        renderDetailHeader(po);
        renderItems(po);
        renderReceiveSection(po);
        await refreshPos();
      } catch (err) {
        alert("Could not add line item: " + err.message);
      }
    });
  }

  /* ---- Receive goods ---- */
  function bindReceive() {
    const form = $("[data-po-receive-form]");
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const warehouse = form.warehouse.value;
      const items = $$("[data-receive-item]", form)
        .map(input => ({ purchase_order_item: input.dataset.receiveItem, quantity_received: input.value }))
        .filter(i => Number(i.quantity_received) > 0);
      if (!warehouse || !items.length) {
        alert("Select a warehouse and enter at least one received quantity.");
        return;
      }
      const uid = appUserId();
      if (!uid) {
        alert("No linked account for recording receipts -- please log in again.");
        return;
      }
      const receiptNumber = `GR-${Date.now()}`;
      const payload = {
        purchase_order: detailPo.id,
        receipt_number: receiptNumber,
        received_date: new Date().toISOString().slice(0, 10),
        warehouse,
        recorded_by: uid,
        items,
      };
      try {
        await api(RECEIPT_API, { method: "POST", body: JSON.stringify(payload) });
        const po = await api(`${PO_API}${detailPo.id}/`);
        detailPo = po;
        renderDetailHeader(po);
        renderActionBar(po);
        renderItems(po);
        renderAddItemVisibility(po);
        renderReceiveSection(po);
        await refreshPos();
        form.reset();
      } catch (err) {
        alert("Could not record receipt: " + err.message);
      }
    });
  }

  /* ---- Create purchase order ---- */
  function bindCreate() {
    const overlay = $("[data-po-create]");
    const form = $("[data-po-create-form]");
    $("[data-po-new]").addEventListener("click", () => {
      fillSelect($("select[name=supplier]", form), state.suppliers, s => s.name, "Select supplier…");
      overlay.hidden = false;
    });
    $("[data-po-create-close]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-po-create-cancel]").addEventListener("click", () => { overlay.hidden = true; });
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const uid = appUserId();
      if (!uid) {
        alert("No linked account for creating purchase orders -- please log in again.");
        return;
      }
      const payload = Object.fromEntries(new FormData(form).entries());
      if (!payload.expected_delivery_date) delete payload.expected_delivery_date;
      payload.created_by = uid;
      try {
        const po = await api(PO_API, { method: "POST", body: JSON.stringify(payload) });
        overlay.hidden = true;
        form.reset();
        await refreshPos();
        openDetail(po.id);
      } catch (err) {
        alert("Could not create purchase order: " + err.message);
      }
    });
  }

  /* ---- Filters & search ---- */
  function bindFilters() {
    $("#po-status-filter").addEventListener("change", e => { state.statusFilter = e.target.value; renderRows(); });
    $("#po-search-input").addEventListener("input", e => { state.search = e.target.value; renderRows(); });
    $("#po-date-from").addEventListener("change", e => { state.dateFrom = e.target.value; renderRows(); });
    $("#po-date-to").addEventListener("change", e => { state.dateTo = e.target.value; renderRows(); });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindDialog();
    bindAddItem();
    bindReceive();
    bindCreate();
    bindFilters();
    try {
      await loadReferenceData();
      await refreshPos();
    } catch (e) {
      $("[data-po-rows]").innerHTML = `<tr><td><strong>Could not load purchase orders</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();
