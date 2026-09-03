/* Procurement page -- Purchase Orders + Goods Receiving (CPMAS-31).
   Consumes the authenticated DRF endpoints under /api/purchasing/ and
   /api/inventory/ using the dashboard session (SessionAuthentication +
   CSRF), same fetch/CSRF pattern as payments.js.

   Receiving is append-only: the page only lists and reads goods receipts
   and creates new ones -- there is no edit/delete UI and no PATCH/PUT/DELETE
   calls for receipts. The purchasing backend remains the final authority on
   validation (over-receiving, PO status, atomic stock updates). */
(() => {
  "use strict";

  const E = {
    pos: "/api/purchasing/purchase-orders/",
    goodsReceipts: "/api/purchasing/goods-receipts/",
    warehouses: "/api/inventory/warehouses/",
  };

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => Number(v || 0).toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
  const fmtQty = (v) => Number(v || 0).toLocaleString("en-US", { maximumFractionDigits: 3 });

  const state = {
    pos: [],             // full PO list (load-all)
    receipts: [],        // current page of goods receipts
    receiptPage: 1,
    receiptNext: null,
    receiptPrev: null,
    receiptTotal: 0,
    poSearch: "",
    poStatus: "",
    receiptSearch: "",
    receiptPoFilter: "",
    receivablePos: [],   // APPROVED + PARTIALLY_RECEIVED
    warehouses: [],
    currentPo: null,     // PO detail loaded into the receive dialog
  };

  function cookie(name) {
    const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function api(url, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.body) headers["Content-Type"] = "application/json";
    if (options.method && !["GET", "HEAD"].includes(options.method)) headers["X-CSRFToken"] = cookie("csrftoken");
    const response = await fetch(url, { credentials: "same-origin", ...options, headers });
    if (!response.ok) {
      let message = response.statusText || `Request failed (${response.status})`;
      try {
        const body = await response.json();
        if (body && typeof body === "object") {
          message = Object.entries(body)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
            .join("\n");
        } else if (body) {
          message = String(body);
        }
      } catch (_) { /* non-JSON / network body */ }
      throw new Error(message || `Request failed (${response.status})`);
    }
    return response.status === 204 ? null : response.json();
  }

  // Load a full list across all pages.
  async function all(url) {
    const rows = [];
    while (url) {
      const data = await api(url);
      if (Array.isArray(data)) return data;
      rows.push(...(data.results || []));
      url = data.next;
    }
    return rows;
  }

  // Load a single page of a paginated endpoint (returns the paginated wrapper).
  async function page(url) {
    return api(url);
  }

  /* ---- helpers ---- */
  const RECEIVABLE = ["APPROVED", "PARTIALLY_RECEIVED"];
  const CLOSED = ["CANCELLED", "RECEIVED"];

  function poReceived(po) {
    const items = po.items || [];
    const ordered = items.reduce((s, i) => s + Number(i.quantity || 0), 0);
    const received = items.reduce((s, i) => s + Number(i.quantity_received || 0), 0);
    return { received, ordered };
  }

  function poIsFullyReceived(po) {
    const { received, ordered } = poReceived(po);
    return ordered > 0 && received >= ordered;
  }

  const statusPill = (s) => {
    const map = {
      DRAFT: "", SUBMITTED: "", APPROVED: " active",
      PARTIALLY_RECEIVED: " active", RECEIVED: " active", CANCELLED: " warning",
    };
    return `<span class="status${map[s] || ""}"><i></i>${esc(s || "—")}</span>`;
  };

  /* ---- rendering: Purchase Orders ---- */
  function renderPos() {
    const body = $("[data-po-rows]");
    let list = state.pos;
    if (state.poStatus) list = list.filter((p) => p.status === state.poStatus);
    const q = state.poSearch.trim().toLowerCase();
    if (q) list = list.filter((p) => [p.po_number, p.supplier_name].some((v) => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="8"><b>No purchase orders found</b><span>Try adjusting the search or status filter.</span></td></tr>`;
      return;
    }
    body.innerHTML = list.map((p) => {
      const { received, ordered } = poReceived(p);
      const pct = ordered > 0 ? Math.round((received / ordered) * 100) : 0;
      const receivable = RECEIVABLE.includes(p.status);
      const action = receivable
        ? `<button type="button" class="quiet-button" data-receive="${p.id}">Receive goods</button>`
        : "";
      return `<tr>
        <td><strong>${esc(p.po_number)}</strong></td>
        <td>${esc(p.supplier_name || "—")}</td>
        <td>${esc(p.order_date || "—")}</td>
        <td>${esc(p.expected_delivery_date || "—")}</td>
        <td>${money(p.total_amount)}</td>
        <td>${pct}% <span class="received-note">${fmtQty(received)} / ${fmtQty(ordered)}</span></td>
        <td>${statusPill(p.status)}</td>
        <td><div class="payment-actions">${action}</div></td>
      </tr>`;
    }).join("");

    $$("[data-receive]", body).forEach((b) => (b.onclick = () => openReceiveDialog(b.dataset.receive)));
  }

  /* ---- rendering: Goods Receiving ---- */
  function renderReceipts() {
    const body = $("[data-receipt-rows]");
    if (!state.receipts.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="7"><b>No goods receipts found</b><span>Try adjusting the search or purchase order filter.</span></td></tr>`;
    } else {
      body.innerHTML = state.receipts.map((r) => `
        <tr>
          <td><strong>${esc(r.receipt_number)}</strong></td>
          <td>${esc(r.purchase_order_number || "—")}</td>
          <td>${esc(r.warehouse_name || "—")}</td>
          <td>${esc(r.received_date || "—")}</td>
          <td>${(r.items_detail || []).length}</td>
          <td>${esc(r.notes || "—")}</td>
          <td><div class="payment-actions"><button type="button" class="procurement-row-view" data-receipt-detail="${r.id}">View details</button></div></td>
        </tr>`).join("");
      $$("[data-receipt-detail]", body).forEach((b) => (b.onclick = () => openReceiptDetail(b.dataset.receiptDetail)));
    }
    // Pagination state
    $("[data-page-next]").disabled = !state.receiptNext;
    $("[data-page-prev]").disabled = !state.receiptPrev;
    $("[data-page-info]").textContent = `Page ${state.receiptPage}`;
  }

  /* ---- metrics ---- */
  function renderStats() {
    const openPos = state.pos.filter((p) => !CLOSED.includes(p.status)).length;
    const receivable = state.pos.filter((p) => RECEIVABLE.includes(p.status)).length;
    const awaiting = state.pos.filter((p) => p.status === "APPROVED" && !poIsFullyReceived(p)).length;
    $("[data-metric=open_pos]").textContent = openPos;
    $("[data-metric=receivable]").textContent = receivable;
    $("[data-metric=goods_received]").textContent = state.receiptTotal;
    $("[data-metric=awaiting_delivery]").textContent = awaiting;
  }

  /* ---- data loads ---- */
  function poSearchParams() {
    const p = new URLSearchParams();
    if (state.poSearch) p.set("search", state.poSearch);
    if (state.poStatus) p.set("status", state.poStatus);
    return p;
  }

  async function loadPos() {
    state.pos = await all(`${E.pos}?${poSearchParams().toString()}`);
    renderPos();
  }

  function receiptListUrl() {
    const p = new URLSearchParams({ page: String(state.receiptPage) });
    if (state.receiptSearch) p.set("search", state.receiptSearch);
    if (state.receiptPoFilter) p.set("purchase_order", state.receiptPoFilter);
    return `${E.goodsReceipts}?${p.toString()}`;
  }

  async function loadReceipts() {
    const data = await page(receiptListUrl());
    state.receipts = data.results || [];
    state.receiptNext = data.next;
    state.receiptPrev = data.previous;
    state.receiptTotal = data.count || 0;
    renderReceipts();
  }

  /* ---- Refresh everything (after load or after a successful receive) ---- */
  async function refreshAll() {
    try {
      await Promise.all([loadPos(), loadReceipts()]);
      renderStats();
    } catch (e) {
      $("[data-po-rows]").innerHTML = `<tr class="empty-row"><td colspan="8"><b>Could not load purchase orders</b><span>${esc(e.message)}</span></td></tr>`;
      $("[data-receipt-rows]").innerHTML = `<tr class="empty-row"><td colspan="7"><b>Could not load goods receipts</b><span>${esc(e.message)}</span></td></tr>`;
    }
  }

  /* ---- Receive Goods dialog ---- */
  const currentUser = () => document.querySelector(".topbar")?.dataset.appUserId || "";

  async function loadWarehouses() {
    if (state.warehouses.length) return;
    try {
      state.warehouses = await all(E.warehouses);
    } catch (e) {
      state.warehouses = [];
    }
  }

  function populateWarehouses() {
    const select = $("[data-warehouse-select]");
    const allWarehouses = [...state.warehouses].sort((a, b) => (Number(b.is_active) - Number(a.is_active)));
    select.innerHTML = '<option value="">Select warehouse…</option>' +
      allWarehouses.map((w) => `<option value="${w.id}">${esc(w.name)}${w.location ? ` — ${esc(w.location)}` : ""}${w.is_active ? "" : " (inactive)"}</option>`).join("");
  }

  async function loadReceivablePos() {
    const [a, p] = await Promise.all([
      all(`${E.pos}?status=APPROVED`),
      all(`${E.pos}?status=PARTIALLY_RECEIVED`),
    ]);
    const seen = new Set();
    const merged = [];
    [...a, ...p].forEach((po) => {
      if (!seen.has(po.id)) { seen.add(po.id); merged.push(po); }
    });
    state.receivablePos = merged.sort((x, y) => x.po_number.localeCompare(y.po_number));
  }

  function populateReceivablePos() {
    const select = $("[data-receive-po-select]");
    select.innerHTML = '<option value="">Select purchase order…</option>' +
      state.receivablePos.map((po) => `<option value="${po.id}">${esc(po.po_number)} — ${esc(po.supplier_name || "")}</option>`).join("");
  }

  function populatePoFilter() {
    const select = $("[data-receipt-po-filter]");
    const opts = state.pos.slice().sort((a, b) => a.po_number.localeCompare(b.po_number));
    const current = select.value;
    select.innerHTML = '<option value="">Purchase order: All</option>' +
      opts.map((po) => `<option value="${po.id}">${esc(po.po_number)}</option>`).join("");
    select.value = current || "";
  }

  async function openReceiveDialog(preSelectedPoId) {
    const dialog = $("[data-receive-dialog]");
    const form = $("[data-receive-form]");
    form.reset();
    $("[data-receive-error]").hidden = true;
    form.elements.received_date.value = new Date().toISOString().slice(0, 10);

    // Pre-load warehouses and receivable POs.
    try {
      await Promise.all([loadWarehouses(), loadReceivablePos()]);
      populateWarehouses();
      populateReceivablePos();
      form.elements.purchase_order.value = preSelectedPoId || "";
      if (preSelectedPoId) {
        $("[data-receive-items]").innerHTML = `<tr class="empty-row"><td colspan="5">Loading items…</td></tr>`;
        await onPoSelected(preSelectedPoId);
      } else {
        $("[data-receive-items]").innerHTML = `<tr class="empty-row"><td colspan="5">Select a purchase order to load its items.</td></tr>`;
      }
    } catch (e) {
      showReceiveError(e);
    }
    dialog.showModal();
  }

  async function onPoSelected(poId) {
    const body = $("[data-receive-items]");
    if (!poId) {
      state.currentPo = null;
      body.innerHTML = `<tr class="empty-row"><td colspan="5">Select a purchase order to load its items.</td></tr>`;
      return;
    }
    body.innerHTML = `<tr class="empty-row"><td colspan="5"><b>Loading items…</b><span>Fetching PO lines.</span></td></tr>`;
    try {
      state.currentPo = await api(`${E.pos}${poId}/`);
      const items = state.currentPo.items || [];
      if (!items.length) {
        body.innerHTML = `<tr class="empty-row"><td colspan="5"><b>No line items on this purchase order.</b></td></tr>`;
        return;
      }
      body.innerHTML = items.map((it) => {
        const remaining = Number(it.quantity_remaining || 0);
        const disabled = remaining <= 0;
        return `<tr>
          <td><strong>${esc(it.material_name || "—")}</strong><span>${esc(it.material_sku || "")}</span></td>
          <td>${fmtQty(it.quantity)}</td>
          <td>${fmtQty(it.quantity_received)}</td>
          <td>${fmtQty(it.quantity_remaining)}</td>
          <td><input type="number" class="qty-input" name="qty_${it.id}" data-item="${it.id}" min="0" max="${remaining}" step="0.001" value="0" ${disabled ? "disabled" : ""}></td>
        </tr>`;
      }).join("");

      // Live clamp: keep 0 <= qty <= remaining (defense-in-depth; backend remains authoritative).
      $$("[data-item]", body).forEach((input) => {
        input.addEventListener("input", () => {
          const max = Number(input.max);
          const val = Number(input.value);
          if (Number.isFinite(val) && val > max) input.value = max;
          else if (Number.isFinite(val) && val < 0) input.value = 0;
        });
      });
    } catch (e) {
      body.innerHTML = `<tr class="empty-row"><td colspan="5"><b>Could not load items</b><span>${esc(e.message)}</span></td></tr>`;
    }
  }

  function showReceiveError(e) {
    const n = $("[data-receive-error]");
    n.textContent = e.message || "Something went wrong.";
    n.hidden = false;
  }

  async function submitReceive(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const errorEl = $("[data-receive-error]");
    errorEl.hidden = true;

    const userId = currentUser();
    if (!userId) {
      showReceiveError(new Error("No linked user account for recording this receipt."));
      return;
    }

    const values = Object.fromEntries(new FormData(form).entries());
    if (!values.notes) delete values.notes;

    // Build only the item rows with a received quantity > 0.
    const items = state.currentPo && state.currentPo.items ? state.currentPo.items
      .map((it) => {
        const qty = form.elements[`qty_${it.id}`];
        if (!qty || qty.disabled) return null;
        const q = Number(qty.value || 0);
        if (!(q > 0)) return null;
        return { purchase_order_item: it.id, quantity_received: String(q) };
      })
      .filter(Boolean) : [];

    if (!items.length) {
      showReceiveError(new Error("Enter a quantity greater than zero on at least one item."));
      return;
    }

    const payload = {
      purchase_order: values.purchase_order,
      receipt_number: values.receipt_number,
      received_date: values.received_date,
      warehouse: values.warehouse,
      recorded_by: userId,
      items,
    };

    try {
      await api(E.goodsReceipts, { method: "POST", body: JSON.stringify(payload) });
      form.closest("[data-receive-dialog]").close();
      $("[data-receive-items]").innerHTML = `<tr class="empty-row"><td colspan="5">Select a purchase order to load its items.</td></tr>`;
      state.currentPo = null;
      await refreshAll(); // re-fetch so PO status / received quantities reflect the backend transaction
    } catch (e) {
      // Keep the dialog open with entered values intact; surface the DRF error.
      showReceiveError(e);
    }
  }

  /* ---- Receipt detail (read-only) ---- */
  async function openReceiptDetail(id) {
    const dialog = $("[data-receipt-detail-dialog]");
    $("[data-receipt-detail-fields]").innerHTML = "<p>Loading receipt…</p>";
    $("[data-receipt-detail-items]").innerHTML = "";
    dialog.showModal();
    try {
      const r = await api(`${E.goodsReceipts}${id}/`);
      $("[data-receipt-detail-title]").textContent = r.receipt_number || "Receipt detail";
      const fields = [
        ["Receipt number", r.receipt_number],
        ["Purchase order", r.purchase_order_number],
        ["Warehouse", r.warehouse_name],
        ["Received date", r.received_date],
        ["Notes", r.notes || "—"],
      ];
      $("[data-receipt-detail-fields]").innerHTML = fields
        .map(([label, value]) => `<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
      const items = r.items_detail || [];
      $("[data-receipt-detail-items]").innerHTML = items.length
        ? items.map((it) => `<tr><td>${esc(it.material_name || "—")}</td><td>${fmtQty(it.quantity_received)}</td><td>${esc(it.notes || "—")}</td></tr>`).join("")
        : `<tr class="empty-row"><td colspan="3"><b>No items on this receipt.</b></td></tr>`;
    } catch (e) {
      $("[data-receipt-detail-fields]").innerHTML = `<p class="form-error">${esc(e.message)}</p>`;
    }
  }

  /* ---- events ---- */
  function bind() {
    $$("[data-open-receive]").forEach((b) => (b.onclick = () => openReceiveDialog()));
    $("[data-receive-po-select]").addEventListener("change", (e) => onPoSelected(e.target.value));
    $("[data-receive-form]").addEventListener("submit", submitReceive);

    $$("[data-receive-close]").forEach((b) => (b.onclick = () => $("[data-receive-dialog]").close()));
    $("[data-receipt-detail-close]").onclick = () => $("[data-receipt-detail-dialog]").close();
    $$(".procurement-dialog").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));

    let poTimer;
    $("#po-search-input").addEventListener("input", (e) => {
      state.poSearch = e.target.value.trim();
      clearTimeout(poTimer);
      poTimer = setTimeout(async () => { try { await loadPos(); } catch (err) { /* handled in render */ } }, 300);
    });
    $("[data-po-status]").addEventListener("change", async (e) => {
      state.poStatus = e.target.value;
      try { await loadPos(); } catch (err) { /* handled */ }
    });

    let rcTimer;
    $("#receipt-search-input").addEventListener("input", (e) => {
      state.receiptSearch = e.target.value.trim();
      state.receiptPage = 1;
      clearTimeout(rcTimer);
      rcTimer = setTimeout(async () => { try { await refreshAll(); } catch (err) { /* handled */ } }, 300);
    });
    $("[data-receipt-po-filter]").addEventListener("change", async (e) => {
      state.receiptPoFilter = e.target.value;
      state.receiptPage = 1;
      try { await refreshAll(); } catch (err) { /* handled */ }
    });
    $("[data-page-prev]").addEventListener("click", async () => {
      if (!state.receiptPrev) return;
      state.receiptPage -= 1;
      try { await refreshAll(); } catch (err) { /* handled */ }
    });
    $("[data-page-next]").addEventListener("click", async () => {
      if (!state.receiptNext) return;
      state.receiptPage += 1;
      try { await refreshAll(); } catch (err) { /* handled */ }
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bind();
    try {
      // Load POs first so the receipt PO filter and metrics can use them.
      await loadPos();
      populatePoFilter();
      await refreshAll();
    } catch (e) {
      $("[data-po-rows]").innerHTML = `<tr class="empty-row"><td colspan="8"><b>Could not load purchase orders</b><span>${esc(e.message)}</span></td></tr>`;
    }
  });
})();
