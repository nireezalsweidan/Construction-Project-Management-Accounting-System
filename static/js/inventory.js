/* Inventory page (1B-1). Consumes the DRF endpoints served by the
   inventory app under /api/inventory/ using the authenticated session
   (SessionAuthentication) -- same fetch/CSRF/escape conventions as
   expenses.js / receipts.js / contractors.js.

   Data model: each stock balance row is one (material x warehouse) pair
   ("Portland Cement @ Beirut Site Store"). The table renders those stock
   rows, and material metadata (unit + standard_cost) is merged client-
   side from the materials endpoint by material id -- the stock payload
   deliberately carries no unit/cost, so the merge avoids a second backend
   round-trip per row.

   Filters map 1:1 to existing API capabilities:
     search   -> ?search=         (material name, material sku, warehouse)
     store    -> ?warehouse=<id>  (from the warehouses endpoint)
     status   -> client-side All / Healthy / Low via is_low_stock
                 (the flag already ships in every stock row)

   The API paginates (PageNumberPagination, 25/page); the list walks the
   `next` links so the rendered dataset -- and tiles 1-3 computed from it
   -- always cover the whole filtered result set, not just page 1.

   Tile 4 "Site transfers today" is global: it counts DISTINCT transfer
   `reference` values among today's TRANSFER ledger rows. One transfer
   operation writes two rows (OUT at source + IN at destination) sharing a
   reference, so counting rows would double the true number. Note
   USE_TZ=False: movement dates and date_from/date_to are naive local
   datetimes (no "Z" suffix).

   Stale-request protection: every refresh() captures a monotonically
   increasing sequence token. Only the refresh that issued the LATEST
   token is allowed to render rows/metrics, so a slow older request can
   never overwrite the results of a newer filter selection. */
(() => {
  "use strict";

  const STOCKS_API = "/api/inventory/stocks/";
  const MATERIALS_API = "/api/inventory/materials/";
  const WAREHOUSES_API = "/api/inventory/warehouses/";
  const MOVEMENTS_API = "/api/inventory/stock-movements/";
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    rows: [],            // stock rows merged with material unit/cost
    statusFilter: "all", // all | healthy | low
    warehouse: "",
    search: "",
    materials: new Map(), // material id -> { unit, standard_cost }
    materialsLoaded: false,
    // Cached lookup lists for the Record movement dialog.
    movement: { materials: [], warehouses: [] },
  };

  // Monotonic guard against stale responses overwriting newer ones.
  let requestSeq = 0;

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

  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const fmtMoney = v => {
    const n = Number(v);
    return Number.isFinite(n)
      ? n.toLocaleString("en-US", { style: "currency", currency: CURRENCY, minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : (v == null || v === "" ? `${CURRENCY} 0.00` : `${CURRENCY} ${v}`);
  };

  // "480.000" + "bag" -> "480 bags"; "2.400" + "ton" -> "2.4 tons".
  const fmtQty = (quantity, unit) => {
    const n = parseFloat(quantity);
    const num = Number.isFinite(n) ? String(n) : "0";
    return unit ? `${num} ${unit}` : num;
  };

  const stockStatusPill = isLow =>
    `<span class="status ${isLow ? "at-risk" : "active"}"><i></i>${esc(isLow ? "Low stock" : "Healthy")}</span>`;

  function buildParams() {
    const params = new URLSearchParams();
    if (state.search.trim()) params.set("search", state.search.trim());
    if (state.warehouse) params.set("warehouse", state.warehouse);
    return params;
  }

  const movementLabel = m => {
    const cls = m.movement_type === "TRANSFER" ? " on-hold" : (m.quantity < 0 ? " at-risk" : " active");
    return `<span class="status${cls}"><i></i>${esc(m.movement_type)}</span>`;
  };

  function rowActions(r) {
    return `<button class="quiet-button" data-stock-action="movements" data-id="${esc(r.id)}">Movements</button>`;
  }

  function renderRows() {
    const tbody = $("[data-inventory-rows]");
    if (!tbody) return;
    if (!state.rows.length) {
      tbody.innerHTML = `
        <tr class="empty-row">
          <td colspan="7"><strong>No stock found</strong><span>Try adjusting the search or filters.</span></td>
        </tr>`;
      return;
    }
    tbody.innerHTML = state.rows.map(r => {
      const mat = state.materials.get(r.material) || {};
      const unit = mat.unit || "";
      const cost = mat.standard_cost != null ? mat.standard_cost : null;
      const reorderNote = Number(r.minimum_stock_level) > 0
        ? `<span>Reorder at ${fmtQty(r.minimum_stock_level, unit)}</span>` : "";
      const costCell = cost != null ? fmtMoney(cost) : "—";
      return `
      <tr>
        <td><strong>${esc(r.material_name || "—")}</strong>${reorderNote}</td>
        <td>${esc(r.material_sku || "—")}</td>
        <td>${esc(r.warehouse_name || "—")}</td>
        <td>${fmtQty(r.quantity, unit)}</td>
        <td>${costCell}</td>
        <td>${stockStatusPill(r.is_low_stock)}</td>
        <td class="inventory-row-actions">${rowActions(r)}</td>
      </tr>`;
    }).join("");
  }

  function renderMetrics() {
    const low = state.rows.filter(r => r.is_low_stock).length;
    const value = state.rows.reduce((acc, r) => {
      const mat = state.materials.get(r.material);
      const cost = mat && mat.standard_cost != null ? Number(mat.standard_cost) : 0;
      return acc + Number(r.quantity || 0) * cost;
    }, 0);

    $("[data-metric=stock]").textContent = state.rows.length;
    $("[data-metric=low]").textContent = low;
    $("[data-metric=value]").textContent = fmtMoney(value);
  }

  async function ensureMaterials() {
    if (state.materialsLoaded) return;
    state.materialsLoaded = true; // attempt once (success or failure)
    try {
      const materials = await fetchAll(MATERIALS_API);
      state.materials = new Map(materials.map(m => [m.id, m]));
    } catch (e) { /* degrade: unit/cost fall back to empty/"—" */ }
  }

  async function refresh() {
    const seq = ++requestSeq;
    const params = buildParams();
    const tbody = $("[data-inventory-rows]");
    if (tbody) {
      tbody.innerHTML = `
        <tr class="empty-row">
          <td colspan="7"><strong>Loading inventory…</strong><span>Fetching from the inventory API.</span></td>
        </tr>`;
    }
    try {
      await ensureMaterials();
      const stocks = await fetchAll(`${STOCKS_API}?${params.toString()}`);
      if (seq !== requestSeq) return; // stale response -- a newer filter is in flight
      let rows = stocks;
      if (state.statusFilter === "healthy") rows = rows.filter(r => !r.is_low_stock);
      if (state.statusFilter === "low") rows = rows.filter(r => r.is_low_stock);
      state.rows = rows;
      renderMetrics();
      renderRows();
    } catch (e) {
      if (seq !== requestSeq) return; // stale failure -- ignore
      state.rows = [];
      renderMetrics();
      if (tbody) {
        tbody.innerHTML = `
          <tr class="empty-row">
            <td colspan="7"><strong>Could not load inventory</strong><span>${esc(e.message)}</span></td>
          </tr>`;
      }
    }
  }

  // USE_TZ=False: the movement ledger stores naive local datetimes, so the
  // tile-4 window is naive too -- no "Z" suffix (aware values 500 on the
  // SQLite comparison in the view's date_from/date_to filter).
  function todayNaive() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return { from: `${y}-${m}-${day}T00:00:00`, to: `${y}-${m}-${day}T23:59:59.999999` };
  }

  async function loadTransfersToday() {
    const tile = $("[data-metric=transfers]");
    if (!tile) return;
    try {
      const { from, to } = todayNaive();
      const params = new URLSearchParams({ movement_type: "TRANSFER", date_from: from, date_to: to });
      const rows = await fetchAll(`${MOVEMENTS_API}?${params.toString()}`);
      const operations = new Set(rows.map(m => m.reference).filter(Boolean)).size;
      tile.textContent = operations;
    } catch (e) {
      tile.textContent = "—";
    }
  }

  function bindSearch() {
    let debounceTimer;
    const input = $("#inventory-search-input");
    if (!input) return;
    input.addEventListener("input", e => {
      state.search = e.target.value;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(refresh, 300);
    });
  }

  function bindStatusFilters() {
    $$("[data-status-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.statusFilter = btn.dataset.statusFilter;
        $$("[data-status-filter]").forEach(b => b.classList.toggle("active", b === btn));
        refresh();
      });
    });
  }

  async function bindWarehouseDropdown() {
    const select = $("#inventory-warehouse-filter");
    if (!select) return;
    try {
      const warehouses = await fetchAll(WAREHOUSES_API);
      const fragment = document.createDocumentFragment();
      for (const w of warehouses) {
        const opt = document.createElement("option");
        opt.value = w.id;
        opt.textContent = w.name;
        fragment.appendChild(opt);
      }
      select.appendChild(fragment);
    } catch (e) { /* leave "Store: All" -- the list must still work */ }
    select.addEventListener("change", () => { state.warehouse = select.value; refresh(); });
  }

  /* ---- Record movement workflow (1B-2) ---- */

  // The movement ledger requires `user` (users.User UUID); the dashboard
  // topbar already exposes the current user id on every dashboard page.
  const currentUserId = () => {
    const header = document.querySelector(".topbar");
    return (header && header.dataset.appUserId) || "";
  };

  // USE_TZ=False: movement dates are naive local datetimes, and Django's
  // parse_datetime requires seconds -- datetime-local inputs omit them, so
  // pad ":00".
  const nowNaiveLocal = () => {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
  };

  const formatApiError = err => {
    const match = err.message.match(/^(\d+):\s*(.*)$/s);
    if (!match) return err.message;
    try {
      const data = JSON.parse(match[2]);
      const lines = [];
      for (const [key, value] of Object.entries(data)) {
        lines.push(`${key}: ${Array.isArray(value) ? value.join(" ") : String(value)}`);
      }
      return lines.length ? lines.join("\n") : err.message;
    } catch (e) {
      return err.message;
    }
  };

  function fillSelect(select, items, { text } = {}) {
    select.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Select…";
    select.appendChild(blank);
    for (const item of items || []) {
      const opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = text ? text(item) : (item.name || item.id);
      select.appendChild(opt);
    }
  }

  async function ensureMovementChoices() {
    const tasks = [];
    if (!state.movement.materials.length) {
      tasks.push(fetchAll(MATERIALS_API).then(r => { state.movement.materials = r; }).catch(() => {}));
    }
    if (!state.movement.warehouses.length) {
      tasks.push(fetchAll(WAREHOUSES_API).then(r => { state.movement.warehouses = r; }).catch(() => {}));
    }
    await Promise.all(tasks);
  }

  // Only the fields relevant to the selected movement type are shown:
  // IN/OUT/RETURN/ADJUSTMENT use a single Warehouse; TRANSFER uses
  // From/To; ADJUSTMENT adds an Increase/Decrease direction.
  function updateMovementFields() {
    const form = $("[data-movement-form]");
    if (!form) return;
    const type = form.elements.movement_type.value;
    const isTransfer = type === "TRANSFER";
    const isAdjustment = type === "ADJUSTMENT";
    const whRow = $("[data-movement-warehouse-row]", form);
    const fromRow = $("[data-movement-from-row]", form);
    const toRow = $("[data-movement-to-row]", form);
    const dirRow = $("[data-movement-direction-row]", form);
    if (whRow) whRow.hidden = isTransfer;
    if (fromRow) fromRow.hidden = !isTransfer;
    if (toRow) toRow.hidden = !isTransfer;
    if (dirRow) dirRow.hidden = !isAdjustment;
    const setRequired = (el, req) => { if (el) el.required = req; };
    setRequired(form.elements.warehouse, !isTransfer);
    setRequired(form.elements.from_warehouse, isTransfer);
    setRequired(form.elements.to_warehouse, isTransfer);
  }

  async function openMovementDialog() {
    const dialog = $("[data-movement-dialog]");
    const form = $("[data-movement-form]");
    if (!dialog || !form) return;
    const errorBox = $("[data-movement-error]", form);
    errorBox.hidden = true;
    form.reset();
    $("[data-movement-form-title]").textContent = "Record movement";
    await ensureMovementChoices();
    fillSelect(form.elements.material, state.movement.materials, { text: m => `${m.name} (${m.sku})` });
    fillSelect(form.elements.warehouse, state.movement.warehouses);
    fillSelect(form.elements.from_warehouse, state.movement.warehouses);
    fillSelect(form.elements.to_warehouse, state.movement.warehouses);
    form.elements.movement_date.value = nowNaiveLocal();
    form.elements.movement_type.value = "IN";
    updateMovementFields();
    dialog.showModal();
  }

  let savingMovement = false;

  // Mirrors the backend contract exactly: IN/RETURN are stored positive,
  // OUT negative, ADJUSTMENT positive or negative, and TRANSFER posts a
  // positive magnitude to the dedicated transfer action.
  function buildMovementPayload(form, type) {
    const value = parseFloat(form.elements.quantity.value);
    if (!(value > 0)) {
      throw new Error("Quantity must be a positive number.");
    }
    const user = currentUserId();
    if (!user) {
      throw new Error("Current user is not available. Please log in again and retry.");
    }
    const common = {
      material: form.elements.material.value,
      user,
      reference: form.elements.reference.value.trim(),
      notes: form.elements.notes.value.trim(),
    };
    if (type === "TRANSFER") {
      return {
        ...common,
        from_warehouse: form.elements.from_warehouse.value,
        to_warehouse: form.elements.to_warehouse.value,
        quantity: String(value),
      };
    }
    let signed;
    if (type === "OUT") signed = -value;
    else if (type === "ADJUSTMENT") signed = form.elements.adjust_direction.value === "decrease" ? -value : value;
    else signed = value; // IN, RETURN
    const payload = {
      ...common,
      warehouse: form.elements.warehouse.value,
      quantity: String(signed),
      movement_type: type,
    };
    let dateValue = form.elements.movement_date.value;
    if (dateValue) {
      if (dateValue.length === 16) dateValue += ":00"; // datetime-local omits seconds
      payload.movement_date = dateValue;
    }
    return payload;
  }

  async function saveMovement(ev) {
    ev.preventDefault();
    const form = $("[data-movement-form]");
    const dialog = $("[data-movement-dialog]");
    if (!form || savingMovement) return;
    const errorBox = $("[data-movement-error]", form);
    const saveBtn = $('footer .primary-button', form);
    savingMovement = true;
    saveBtn.disabled = true;
    errorBox.hidden = true;

    const type = form.elements.movement_type.value;
    if (!type || !form.elements.material.value) {
      errorBox.textContent = "Movement type and material are required.";
      errorBox.hidden = false;
      savingMovement = false;
      saveBtn.disabled = false;
      return;
    }

    let payload;
    try {
      payload = buildMovementPayload(form, type);
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.hidden = false;
      savingMovement = false;
      saveBtn.disabled = false;
      return;
    }

    try {
      const url = type === "TRANSFER" ? `${MOVEMENTS_API}transfer/` : MOVEMENTS_API;
      await api(url, { method: "POST", body: JSON.stringify(payload) });
      dialog.close();
      refresh();            // stock rows + tiles 1-3
      loadTransfersToday(); // tile 4 (a transfer today increments it)
    } catch (err) {
      errorBox.textContent = formatApiError(err);
      errorBox.hidden = false;
    } finally {
      savingMovement = false;
      saveBtn.disabled = false;
    }
  }

  /* ---- Movement history (1B-2) ---- */

  const movementDateLabel = v => String(v || "").replace("T", " ");

  async function openMovementHistory(row) {
    const dialog = $("[data-movement-history-dialog]");
    const tbody = $("[data-movement-history-rows]");
    if (!dialog || !tbody) return;
    $("[data-movement-history-title]").textContent = `Movement history — ${row.material_name || "Material"} @ ${row.warehouse_name || "Warehouse"}`;
    tbody.innerHTML = `
      <tr class="empty-row"><td colspan="5"><strong>Loading history…</strong><span>Fetching movement records.</span></td></tr>`;
    dialog.showModal();
    try {
      const params = new URLSearchParams({ material: row.material, warehouse: row.warehouse });
      const rows = await fetchAll(`${MOVEMENTS_API}?${params.toString()}`);
      const mat = state.materials.get(row.material) || {};
      const unit = mat.unit || "";
      if (!rows.length) {
        tbody.innerHTML = `
          <tr class="empty-row"><td colspan="5"><strong>No movements recorded</strong><span>Nothing has been moved for this stock row yet.</span></td></tr>`;
        return;
      }
      tbody.innerHTML = rows.map(m => `
        <tr>
          <td>${esc(movementDateLabel(m.movement_date))}</td>
          <td>${movementLabel(m)}</td>
          <td>${fmtQty(m.quantity, unit)}</td>
          <td>${esc(m.reference || "—")}</td>
          <td>${esc(m.notes || "—")}</td>
        </tr>`).join("");
    } catch (e) {
      tbody.innerHTML = `
        <tr class="empty-row"><td colspan="5"><strong>Could not load history</strong><span>${esc(e.message)}</span></td></tr>`;
    }
  }

  function bindInventoryActions() {
    const tbody = $("[data-inventory-rows]");
    if (!tbody) return;
    tbody.addEventListener("click", e => {
      const btn = e.target.closest("[data-stock-action]");
      if (!btn || btn.dataset.stockAction !== "movements") return;
      const row = state.rows.find(x => String(x.id) === String(btn.dataset.id));
      if (row) openMovementHistory(row);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindSearch();
    bindStatusFilters();
    bindWarehouseDropdown();
    bindInventoryActions();
    refresh();
    loadTransfersToday();

    const newBtn = $("[data-movement-new]");
    if (newBtn) newBtn.addEventListener("click", () => openMovementDialog());

    const moveType = $("[data-movement-type]");
    if (moveType) moveType.addEventListener("change", updateMovementFields);

    const moveForm = $("[data-movement-form]");
    if (moveForm) moveForm.addEventListener("submit", saveMovement);

    $$("[data-movement-close]").forEach(btn =>
      btn.addEventListener("click", () => btn.closest("dialog")?.close())
    );
    $$("[data-movement-history-close]").forEach(btn =>
      btn.addEventListener("click", () => btn.closest("dialog")?.close())
    );

    const movementDialog = $("[data-movement-dialog]");
    if (movementDialog) {
      movementDialog.addEventListener("click", e => { if (e.target === movementDialog) movementDialog.close(); });
    }
    const historyDialog = $("[data-movement-history-dialog]");
    if (historyDialog) {
      historyDialog.addEventListener("click", e => { if (e.target === historyDialog) historyDialog.close(); });
    }
  });
})();