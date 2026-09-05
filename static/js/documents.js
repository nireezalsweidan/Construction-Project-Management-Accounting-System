/* Document Management page (CPMAS-25). Consumes the DRF endpoints served
   by DocumentViewSet under /api/documents/documents/ using the
   authenticated session (SessionAuthentication) -- same fetch/CSRF
   pattern as suppliers.js/procurement.js. uploaded_by is derived
   server-side from the session, never sent by this page. */
(() => {
  "use strict";

  const API = "/api/documents/documents/";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const state = { docs: [], search: "", entityType: "" };

  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }

  async function api(url, options = {}) {
    const opts = { credentials: "same-origin", ...options };
    opts.headers = { ...(options.headers || {}) };
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

  async function fetchAllDocs() {
    const params = new URLSearchParams();
    if (state.search) params.set("search", state.search);
    if (state.entityType) params.set("entity_type", state.entityType);

    const rows = [];
    let url = `${API}?${params.toString()}`;
    while (url) {
      const data = await api(url);
      rows.push(...(data.results || []));
      url = data.next;
    }
    return rows;
  }

  const ENTITY_LABELS = {
    client: "Client", supplier: "Supplier", contractor: "Contractor", project: "Project",
    purchase_order: "Purchase order", expense: "Expense", client_invoice: "Client invoice",
    supplier_invoice: "Supplier invoice", change_order: "Change order",
  };

  function fmtSize(bytes) {
    const n = Number(bytes);
    if (!Number.isFinite(n) || n <= 0) return "—";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }

  function renderRows() {
    const tbody = $("[data-doc-rows]");
    if (!state.docs.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7"><b>No documents found</b><span>Try adjusting the search or entity filter.</span></td></tr>`;
      return;
    }
    tbody.innerHTML = state.docs.map((d) => `
      <tr data-doc-id="${d.id}">
        <td><strong>${esc(d.file_name)}</strong></td>
        <td><span class="doc-entity-badge">${esc(ENTITY_LABELS[d.entity_type] || d.entity_type)}</span></td>
        <td>${esc(d.document_type || "—")}</td>
        <td>${fmtSize(d.file_size)}</td>
        <td>${esc(d.uploaded_by_name || "—")}</td>
        <td>${esc((d.uploaded_at || "").slice(0, 10))}</td>
        <td class="doc-row-actions">
          <a href="${d.file_url}" target="_blank" rel="noopener">Download</a>
          <button type="button" class="quiet-button" data-doc-delete="${d.id}">Delete</button>
        </td>
      </tr>`).join("");

    $$("[data-doc-delete]", tbody).forEach((btn) => {
      btn.addEventListener("click", () => deleteDoc(btn.dataset.docDelete));
    });
  }

  function renderMetrics() {
    $("[data-metric=total]").textContent = state.docs.length;
    const now = new Date();
    const thisMonth = state.docs.filter((d) => {
      const uploaded = new Date(d.uploaded_at);
      return uploaded.getUTCFullYear() === now.getUTCFullYear() && uploaded.getUTCMonth() === now.getUTCMonth();
    }).length;
    $("[data-metric=this-month]").textContent = thisMonth;
  }

  async function refresh() {
    try {
      state.docs = await fetchAllDocs();
      renderMetrics();
      renderRows();
    } catch (e) {
      $("[data-doc-rows]").innerHTML = `<tr class="empty-row"><td colspan="7"><b>Could not load documents</b><span>${esc(e.message)}</span></td></tr>`;
    }
  }

  async function deleteDoc(id) {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    try {
      await api(`${API}${id}/`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      alert("Could not delete document: " + e.message);
    }
  }

  function bindFilters() {
    let debounceTimer;
    $("#doc-search-input").addEventListener("input", (e) => {
      state.search = e.target.value;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(refresh, 300);
    });
    $("#doc-entity-filter").addEventListener("change", (e) => {
      state.entityType = e.target.value;
      refresh();
    });
  }

  function bindUpload() {
    const overlay = $("[data-doc-upload]");
    const form = $("[data-doc-upload-form]");
    $("[data-doc-new]").addEventListener("click", () => { overlay.hidden = false; });
    $("[data-doc-upload-close]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-doc-upload-cancel]").addEventListener("click", () => { overlay.hidden = true; });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      try {
        await api(API, { method: "POST", body: formData });
        overlay.hidden = true;
        form.reset();
        await refresh();
      } catch (err) {
        alert("Could not upload document: " + err.message);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindFilters();
    bindUpload();
    refresh();
  });
})();
