/* Contractor Management page.
   Consumes the DRF endpoints served by ContractorViewSet under
   /api/contractors/ using the authenticated session (SessionAuthentication).
   No contractor login/role here -- the endpoints only let authenticated
   internal users (Owner/Accountant) through, enforced server-side. */
(() => {
  "use strict";

  const API = "/api/contractors/";
  const PROJECTS_API = "/api/projects/projects/";
  const CURRENCY = "USD";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = { contractors: [], assignments: [], statusFilter: "all", search: "" };

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
      : (v == null || v === "" ? `${CURRENCY} 0.00` : `${CURRENCY} ${v}`);
  };

  const contractorStatusPill = s => {
    const safe = s || "ACTIVE";
    const cls = safe === "ACTIVE" ? " active" : (safe === "TERMINATED" ? " warning" : "");
    return `<span class="status${cls}"><i></i>${safe}</span>`;
  };

  const assignmentStatusPill = s => {
    const cls = s === "RELEASED" ? " warning" : (s === "COMPLETED" ? " active" : "");
    return `<span class="status${cls}"><i></i>${s}</span>`;
  };

  /* ---- Table rendering ---- */
  function renderRows() {
    const tbody = $("[data-contractor-rows]");
    let list = state.contractors;
    if (state.statusFilter !== "all") list = list.filter(c => c.status === state.statusFilter);
    const q = state.search.trim().toLowerCase();
    if (q) list = list.filter(c => [c.name, c.company_name, c.email, c.specialization].some(v => (v || "").toLowerCase().includes(q)));

    if (!list.length) {
      tbody.innerHTML = `<tr><td><strong>No contractors found</strong><span>Try adjusting the search or status filter.</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
      return;
    }
    tbody.innerHTML = list.map(c => `
      <tr class="row-click" data-contractor-id="${c.id}">
        <td><strong>${esc(c.name)}</strong><span>View details</span></td>
        <td><strong>${esc((c.company_name || c.phone) ? c.company_name : "—")}</strong><span>${esc(c.email || "")}</span></td>
        <td>${esc(c.specialization || "—")}</td>
        <td>${c.rate != null ? fmtMoney(c.rate) : "—"}</td>
        <td>${contractorStatusPill(c.status)}</td>
      </tr>`).join("");

    $$("[data-contractor-id]", tbody).forEach(row => {
      row.addEventListener("click", () => openDetail(row.dataset.contractorId));
    });
  }

  async function renderMetrics() {
    const contractors = state.contractors;
    const active = contractors.filter(c => c.status === "ACTIVE").length;
    const terminated = contractors.filter(c => c.status === "TERMINATED").length;
    $("[data-metric=total]").textContent = contractors.length;
    $("[data-metric=active]").textContent = active;
    $("[data-metric=terminated]").textContent = terminated;
    $("[data-metric=assignments]").textContent = state.assignments.length;
  }

  /* ---- Detail dialog ---- */
  const dialog = $("[data-contractor-dialog]");
  let detailContractorId = null;
  let activeTab = "assignments";
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function openDetail(id) {
    detailContractorId = id;
    try {
      const detail = await api(`${API}${id}/`);
      $("[data-detail-name]").textContent = detail.name || "—";
      $("[data-detail-company]").textContent = detail.company_name || "";
      $("[data-detail-phone]").textContent = detail.phone || "—";
      $("[data-detail-email]").textContent = detail.email || "—";
      $("[data-detail-specialization]").textContent = detail.specialization || "—";
      $("[data-detail-terms]").textContent = detail.payment_terms || "—";
      $("[data-detail-rate]").textContent = detail.rate != null ? fmtMoney(detail.rate) : "—";
      $("[data-detail-contract]").textContent = detail.contract_details || "—";
      const status = $("[data-detail-status]");
      status.className = "status" + (detail.status === "ACTIVE" ? " active" : (detail.status === "TERMINATED" ? " warning" : ""));
      status.innerHTML = `<i></i>${detail.status || "ACTIVE"}`;
      dialog.showModal();
      loadTab(activeTab);
    } catch (e) {
      alert("Could not load contractor: " + e.message);
    }
  }

  async function loadAssignments() {
    try {
      state.assignments = await api(`${API}${detailContractorId}/projects/`);
    } catch (e) {
      state.assignments = [];
    }
    await renderMetrics();
  }

  function assignmentTable() {
    const cols = ["Project", "Contract amount", "Assigned", "Released", "Status", ""];
    const head = `<table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>`;
    if (!state.assignments.length) {
      return `${head}<tbody><tr><td colspan="${cols.length}"><strong>No project assignments for this contractor.</strong></td></tr></tbody></table>`;
    }
    const rows = state.assignments.map(a => `
      <tr>
        <td><strong>${esc(a.project.name)}</strong><span>${esc(a.project.code)}</span></td>
        <td>${a.contract_amount != null ? fmtMoney(a.contract_amount) : "—"}</td>
        <td>${esc(a.assigned_at || "—")}</td>
        <td>${esc(a.released_at || "—")}</td>
        <td>${assignmentStatusPill(a.status)}</td>
        <td>
          <button type="button" class="tab-action" data-release="${a.id}" ${a.released_at ? "disabled" : ""}>Release</button>
          <button type="button" class="tab-action danger" data-unassign="${a.id}">Unassign</button>
        </td>
      </tr>`).join("");
    return `${head}<tbody>${rows}</tbody></table>`;
  }

  function documentTable() {
    const cols = ["File", "Type", "Size", "Uploaded"];
    const head = `<table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>`;
    const docs = state.documents || [];
    if (!docs.length) {
      return `${head}<tbody><tr><td colspan="${cols.length}"><strong>No documents linked to this contractor.</strong></td></tr></tbody></table>`;
    }
    const rows = docs.map(d => `
      <tr>
        <td><strong>${esc(d.file_name)}</strong></td>
        <td>${esc(d.document_type || "—")}</td>
        <td>${d.file_size != null ? Math.round(d.file_size / 1024) + " KB" : "—"}</td>
        <td>${esc(d.uploaded_at || "—")}</td>
      </tr>`).join("");
    return `${head}<tbody>${rows}</tbody></table>`;
  }

  function assignForm() {
    const options = (state.projects || []).map(p => `<option value="${p.id}">${esc(p.code)} — ${esc(p.name)}</option>`).join("");
    return `
      <form class="contractor-assign-form" data-assign-form>
        <label>Project *
          <select name="project_id" required>
            <option value="" disabled selected>Select project…</option>
            ${options}
          </select>
        </label>
        <label>Contract amount <input type="number" name="contract_amount" step="0.01" min="0" placeholder="0.00"></label>
        <label>Assigned date * <input type="date" name="assigned_at" required></label>
        <button type="submit" class="primary-button">Assign</button>
        <button type="button" class="quiet-button" data-assign-cancel>Cancel</button>
      </form>`;
  }

  async function loadTab(tab) {
    activeTab = tab;
    const panel = $("[data-tab-panel]");
    $$("[data-tab]").forEach(b => b.classList.toggle("active", b === tab || b.dataset.tab === tab));
    if (tab === "assignments") {
      await loadAssignments();
      panel.innerHTML = assignmentTable();
      bindAssignmentActions(panel);
    } else if (tab === "documents") {
      panel.innerHTML = `<table><thead><tr><th>Loading…</th></tr></thead><tbody><tr><td><strong>Loading documents…</strong></td></tr></tbody></table>`;
      try {
        state.documents = await api(`${API}${detailContractorId}/documents/`);
      } catch (e) {
        state.documents = [];
      }
      panel.innerHTML = documentTable();
    } else if (tab === "assign") {
      if (!state.projects) {
        try { state.projects = await fetchAll(PROJECTS_API); } catch (e) { state.projects = []; }
      }
      panel.innerHTML = assignForm();
      const form = $("[data-assign-form]");
      $("[data-assign-cancel]").addEventListener("click", () => loadTab("assignments"));
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        if (!payload.contract_amount) delete payload.contract_amount;
        try {
          await api(`${API}${detailContractorId}/projects/`, { method: "POST", body: JSON.stringify(payload) });
          loadTab("assignments");
        } catch (err) {
          alert("Could not assign project: " + err.message);
        }
      });
    }
  }

  function bindAssignmentActions(panel) {
    $$("[data-release]", panel).forEach(btn => {
      btn.addEventListener("click", async () => {
        const aid = btn.dataset.release;
        if (!confirm("Release this assignment?")) return;
        try {
          await api(`${API}${detailContractorId}/projects/${aid}/`, {
            method: "PATCH",
            body: JSON.stringify({ status: "RELEASED", released_at: new Date().toISOString().slice(0, 10) }),
          });
          loadTab("assignments");
        } catch (e) {
          alert("Could not release assignment: " + e.message);
        }
      });
    });
    $$("[data-unassign]", panel).forEach(btn => {
      btn.addEventListener("click", async () => {
        const aid = btn.dataset.unassign;
        if (!confirm("Remove this assignment entirely?")) return;
        try {
          await api(`${API}${detailContractorId}/projects/${aid}/`, { method: "DELETE" });
          loadTab("assignments");
        } catch (e) {
          alert("Could not unassign: " + e.message);
        }
      });
    });
  }

  function bindDialog() {
    $("[data-contractor-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", e => { if (e.target === dialog) dialog.close(); });
    $$("[data-tab]").forEach(btn => {
      btn.addEventListener("click", () => loadTab(btn.dataset.tab));
    });
  }

  /* ---- Create contractor ---- */
  function bindCreate() {
    const overlay = $("[data-contractor-create]");
    $("[data-contractor-new]").addEventListener("click", () => { overlay.hidden = false; });
    $("[data-contractor-create-close]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-contractor-create-cancel]").addEventListener("click", () => { overlay.hidden = true; });
    $("[data-contractor-form]").addEventListener("submit", async e => {
      e.preventDefault();
      const form = e.currentTarget;
      const payload = Object.fromEntries(new FormData(form).entries());
      if (!payload.rate) delete payload.rate;
      try {
        await api(API, { method: "POST", body: JSON.stringify(payload) });
        overlay.hidden = true;
        form.reset();
        await refresh();
      } catch (err) {
        alert("Could not create contractor: " + err.message);
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
    const searchInput = $("#contractor-search-input");
    searchInput.addEventListener("input", () => { state.search = searchInput.value; renderRows(); });
  }

  async function refresh() {
    state.contractors = await fetchAll(API);
    await renderMetrics();
    renderRows();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindDialog();
    bindCreate();
    bindFilters();
    try {
      await refresh();
      state.assignments = [];
      state.documents = [];
      state.projects = null;
    } catch (e) {
      $("[data-contractor-rows]").innerHTML = `<tr><td><strong>Could not load contractors</strong><span>${esc(e.message)}</span></td><td>—</td><td>—</td><td>—</td><td><span class="status"><i></i>—</span></td></tr>`;
    }
  });
})();