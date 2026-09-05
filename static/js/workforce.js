/* Workforce: employee profiles and project assignments from the existing APIs. */
(() => {
  "use strict";
  const EMPLOYEES_API = "/api/employees/";
  const PROJECTS_API = "/api/projects/projects/";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const state = { employees: [], assignments: {}, assignmentErrors: new Set(), projects: null, selected: null, editAssignment: null, statusFilter: "all", search: "" };
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => Number(v || 0).toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

  class ApiError extends Error { constructor(message, status, body) { super(message); this.status = status; this.body = body; } }
  function cookie(name) { const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)")); return m ? decodeURIComponent(m[2]) : ""; }
  function errorText(body, fallback) {
    if (!body) return fallback;
    if (typeof body === "string") return body;
    if (body.detail) return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    return Object.entries(body).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(" ") : value}`).join(" ") || fallback;
  }
  async function api(url, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.body) headers["Content-Type"] = "application/json";
    if (options.method && !["GET", "HEAD"].includes(options.method)) headers["X-CSRFToken"] = cookie("csrftoken");
    const response = await fetch(url, { credentials: "same-origin", ...options, headers });
    let body = null;
    if (response.status !== 204) { try { body = await response.json(); } catch (_) { /* non-JSON */ } }
    if (!response.ok) throw new ApiError(errorText(body, response.statusText || `Request failed (${response.status})`), response.status, body);
    return body;
  }
  async function all(url) { const rows = []; while (url) { const data = await api(url); if (Array.isArray(data)) return data; rows.push(...(data.results || [])); url = data.next; } return rows; }
  function setText(sel, value) { const el = $(sel); if (el) el.textContent = value; }
  function status(value) { const s = value || "ACTIVE"; return `<span class="status${s === "ACTIVE" ? " active" : s === "TERMINATED" ? " warning" : ""}"><i></i>${esc(s.replace("_", " "))}</span>`; }
  function setMetricsLoading() { ["active", "onleave", "assignments", "projects"].forEach(key => setText(`[data-metric=${key}]`, "—")); }
  function renderMetrics() {
    setText("[data-metric=active]", state.employees.filter(x => x.employment_status === "ACTIVE").length);
    setText("[data-metric=onleave]", state.employees.filter(x => x.employment_status === "ON_LEAVE").length);
    if (state.assignmentErrors.size) { setText("[data-metric=assignments]", "—"); setText("[data-metric=projects]", "—"); return; }
    const assignments = Object.values(state.assignments).flat().filter(a => !a.released_at);
    setText("[data-metric=assignments]", assignments.length);
    setText("[data-metric=projects]", new Set(assignments.map(a => a.project.id)).size);
  }
  function projectCell(id) {
    if (state.assignmentErrors.has(id)) return '<span class="workforce-unavailable">Unavailable</span>';
    const list = state.assignments[id] || [], active = list.find(a => !a.released_at);
    return active ? `${esc(active.project.name)}<span>${esc(active.project.code)}</span>` : "—";
  }
  function render() {
    let list = state.employees;
    if (state.statusFilter !== "all") list = list.filter(x => x.employment_status === state.statusFilter);
    const q = state.search.toLowerCase().trim();
    if (q) list = list.filter(x => [x.name, x.employee_number, x.position, x.department, x.email].some(v => (v || "").toLowerCase().includes(q)));
    const body = $("[data-workforce-rows]");
    if (!list.length) {
      const filtered = state.employees.length > 0;
      body.innerHTML = `<tr><td colspan="6"><strong>${filtered ? "No matching employees" : "No employees yet"}</strong><span>${filtered ? "Adjust the search or status filter." : "Create an employee to start building the workforce."}</span></td></tr>`;
    } else {
      body.innerHTML = list.map(x => `<tr><td><button class="workforce-name" type="button" data-workforce-detail="${x.id}"><strong>${esc(x.name)}</strong><span>${esc(x.employee_number)}</span></button></td><td>${esc(x.position || "—")}</td><td>${esc(x.department || "—")}</td><td>${projectCell(x.id)}</td><td>${x.labor_rate != null ? money(x.labor_rate) : "—"}</td><td>${status(x.employment_status)} <button class="quiet-button" type="button" data-workforce-edit="${x.id}">Edit</button></td></tr>`).join("");
    }
    renderMetrics();
  }
  function showPageError(message) { const el = $("[data-workforce-page-error]"); el.hidden = false; el.innerHTML = `${esc(message)} <button type="button" data-workforce-retry>Retry</button>`; $("[data-workforce-retry]", el).onclick = reload; }
  function hidePageError() { $("[data-workforce-page-error]").hidden = true; }
  async function loadAssignmentsFor(employee) {
    try { state.assignments[employee.id] = await api(`${EMPLOYEES_API}${employee.id}/projects/`); state.assignmentErrors.delete(employee.id); }
    catch (_) { delete state.assignments[employee.id]; state.assignmentErrors.add(employee.id); }
  }
  async function reload() {
    hidePageError(); setMetricsLoading();
    $("[data-workforce-rows]").innerHTML = '<tr><td colspan="6"><strong>Loading workforce…</strong><span>Fetching live employees and assignments</span></td></tr>';
    try {
      state.employees = await all(EMPLOYEES_API); state.assignments = {}; state.assignmentErrors.clear();
      await Promise.all(state.employees.map(loadAssignmentsFor)); render();
      if (state.assignmentErrors.size) showPageError(`Assignments could not be loaded for ${state.assignmentErrors.size} employee(s). Assignment metrics are unavailable.`);
    } catch (error) {
      state.employees = []; setMetricsLoading();
      $("[data-workforce-rows]").innerHTML = '<tr><td colspan="6"><strong>Could not load workforce</strong><span>Use Retry to request the employee list again.</span></td></tr>';
      showPageError(error.message);
    }
  }

  const employeeDialog = $("[data-employee-form-dialog]"), employeeForm = $("[data-employee-form]");
  function clearErrors(form, general) { general.hidden = true; general.textContent = ""; $$('[data-field-error]', form).forEach(x => x.textContent = ""); }
  function showFormErrors(form, general, error) {
    clearErrors(form, general); let fieldShown = false;
    if (error.body && typeof error.body === "object") Object.entries(error.body).forEach(([key, value]) => { const el = $(`[data-field-error="${key}"]`, form); if (el) { el.textContent = Array.isArray(value) ? value.join(" ") : String(value); fieldShown = true; } });
    if (!fieldShown || error.body?.detail || error.body?.non_field_errors) { general.textContent = error.message; general.hidden = false; }
  }
  function employeePayload(form) { const data = Object.fromEntries(new FormData(form).entries()); ["phone", "email", "position", "department", "labor_rate"].forEach(key => { if (data[key] === "") data[key] = null; }); return data; }
  function openEmployeeForm(employee = null) {
    employeeForm.reset(); clearErrors(employeeForm, $("[data-employee-form-error]")); employeeForm.dataset.employeeId = employee?.id || "";
    setText("[data-employee-form-title]", employee ? "Edit employee" : "New employee");
    if (employee) Object.entries(employee).forEach(([key, value]) => { const control = employeeForm.elements.namedItem(key); if (control) control.value = value ?? ""; });
    employeeDialog.showModal();
  }
  async function saveEmployee(event) {
    event.preventDefault(); clearErrors(employeeForm, $("[data-employee-form-error]"));
    if (!employeeForm.reportValidity()) return;
    const button = $("[data-employee-save]"), id = employeeForm.dataset.employeeId; button.disabled = true; button.textContent = "Saving…";
    try { await api(id ? `${EMPLOYEES_API}${id}/` : EMPLOYEES_API, { method: id ? "PATCH" : "POST", body: JSON.stringify(employeePayload(employeeForm)) }); employeeDialog.close(); employeeForm.reset(); await reload(); if (id && state.selected?.id === id) await openDetail(id); }
    catch (error) { showFormErrors(employeeForm, $("[data-employee-form-error]"), error); }
    finally { button.disabled = false; button.textContent = "Save employee"; }
  }

  const detailDialog = $("[data-employee-detail-dialog]");
  async function openDetail(id) {
    if (!detailDialog.open) detailDialog.showModal(); $("[data-assignment-state]").innerHTML = '<p class="workforce-state">Loading assignments…</p>';
    try {
      state.selected = await api(`${EMPLOYEES_API}${id}/`);
      setText("[data-detail-name]", state.selected.name); setText("[data-detail-number]", state.selected.employee_number); setText("[data-detail-phone]", state.selected.phone || "—"); setText("[data-detail-email]", state.selected.email || "—"); setText("[data-detail-position]", state.selected.position || "—"); setText("[data-detail-department]", state.selected.department || "—"); setText("[data-detail-rate]", state.selected.labor_rate != null ? money(state.selected.labor_rate) : "—"); setText("[data-detail-status]", state.selected.employment_status.replace("_", " "));
      await loadSelectedAssignments();
    } catch (error) { showDetailMessage(error.message); $("[data-assignment-state]").innerHTML = '<p class="workforce-state error">Employee details could not be loaded.</p>'; }
  }
  function showDetailMessage(message) { const el = $("[data-detail-message]"); el.textContent = message; el.hidden = false; }
  function clearDetailMessage() { const el = $("[data-detail-message]"); el.hidden = true; el.textContent = ""; }
  async function loadSelectedAssignments() {
    const area = $("[data-assignment-state]"); area.innerHTML = '<p class="workforce-state">Loading assignments…</p>'; clearDetailMessage();
    try { const rows = await api(`${EMPLOYEES_API}${state.selected.id}/projects/`); state.assignments[state.selected.id] = rows; state.assignmentErrors.delete(state.selected.id); renderAssignments(rows); renderMetrics(); }
    catch (error) { state.assignmentErrors.add(state.selected.id); renderMetrics(); area.innerHTML = `<div class="workforce-state error">${esc(error.message)} <button class="quiet-button" type="button" data-assignment-retry>Retry</button></div>`; $("[data-assignment-retry]").onclick = loadSelectedAssignments; }
  }
  function renderAssignments(rows) {
    const area = $("[data-assignment-state]");
    if (!rows.length) { area.innerHTML = '<p class="workforce-state">No project assignments for this employee.</p>'; return; }
    area.innerHTML = `<div class="responsive-table"><table><thead><tr><th>Project</th><th>Role</th><th>Assigned</th><th>Released</th><th>Actions</th></tr></thead><tbody>${rows.map(a => `<tr><td><strong>${esc(a.project.name)}</strong><span>${esc(a.project.code)}</span></td><td>${esc(a.role_on_project || "—")}</td><td>${esc(a.assigned_at)}</td><td>${esc(a.released_at || "—")}</td><td><button class="quiet-button" type="button" data-assignment-edit="${a.id}">Edit</button> ${a.released_at ? "" : `<button class="quiet-button" type="button" data-assignment-release="${a.id}">Release</button>`} <button class="quiet-button danger" type="button" data-assignment-remove="${a.id}">Remove</button></td></tr>`).join("")}</tbody></table></div>`;
  }

  const assignmentDialog = $("[data-assignment-dialog]"), assignmentForm = $("[data-assignment-form]");
  async function loadProjects() { if (state.projects === null) state.projects = await all(PROJECTS_API); return state.projects; }
  async function openAssignmentForm(assignment = null) {
    state.editAssignment = assignment; assignmentForm.reset(); clearErrors(assignmentForm, $("[data-assignment-error]"));
    setText("[data-assignment-title]", assignment ? "Edit assignment" : "Assign project"); $("[data-project-field]").hidden = !!assignment; $("[data-assigned-field]").hidden = !!assignment; $("[data-release-field]").hidden = !assignment;
    assignmentForm.elements.project_id.disabled = !!assignment; assignmentForm.elements.assigned_at.disabled = !!assignment; assignmentForm.elements.released_at.disabled = !assignment;
    if (assignment) { assignmentForm.elements.role_on_project.value = assignment.role_on_project || ""; assignmentForm.elements.released_at.value = assignment.released_at || ""; assignmentDialog.showModal(); return; }
    assignmentDialog.showModal();
    try { const projects = await loadProjects(); const used = new Set((state.assignments[state.selected.id] || []).map(a => a.project.id)); $("[data-assignment-project]").innerHTML = '<option value="">Select project…</option>' + projects.map(p => `<option value="${p.id}" ${used.has(p.id) ? "disabled" : ""}>${esc(p.code)} — ${esc(p.name)}</option>`).join(""); }
    catch (error) { const el = $("[data-assignment-error]"); el.textContent = `Could not load projects: ${error.message}`; el.hidden = false; }
  }
  async function saveAssignment(event) {
    event.preventDefault(); clearErrors(assignmentForm, $("[data-assignment-error]")); if (!assignmentForm.reportValidity()) return;
    const button = $("[data-assignment-save]"), editing = state.editAssignment; button.disabled = true; button.textContent = "Saving…";
    const raw = Object.fromEntries(new FormData(assignmentForm).entries()); const payload = editing ? { role_on_project: raw.role_on_project || null, released_at: raw.released_at || null } : { project_id: raw.project_id, assigned_at: raw.assigned_at, role_on_project: raw.role_on_project || null };
    try { await api(editing ? `${EMPLOYEES_API}${state.selected.id}/projects/${editing.id}/` : `${EMPLOYEES_API}${state.selected.id}/projects/`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) }); assignmentDialog.close(); await loadSelectedAssignments(); render(); }
    catch (error) { showFormErrors(assignmentForm, $("[data-assignment-error]"), error); }
    finally { button.disabled = false; button.textContent = "Save assignment"; }
  }
  async function mutateAssignment(id, method, payload, progress) {
    const area = $("[data-assignment-state]"); area.classList.add("loading"); clearDetailMessage();
    try { await api(`${EMPLOYEES_API}${state.selected.id}/projects/${id}/`, { method, ...(payload ? { body: JSON.stringify(payload) } : {}) }); await loadSelectedAssignments(); render(); }
    catch (error) { showDetailMessage(`${progress} failed: ${error.message}`); }
    finally { area.classList.remove("loading"); }
  }

  const deleteDialog = $("[data-delete-dialog]");
  async function deleteEmployee() { const button = $("[data-delete-confirm]"), errorEl = $("[data-delete-error]"); button.disabled = true; button.textContent = "Deleting…"; errorEl.hidden = true; try { await api(`${EMPLOYEES_API}${state.selected.id}/`, { method: "DELETE" }); deleteDialog.close(); detailDialog.close(); state.selected = null; await reload(); } catch (error) { errorEl.textContent = error.status === 409 || error.status >= 500 ? "This employee cannot be deleted because another record still references them." : error.message; errorEl.hidden = false; } finally { button.disabled = false; button.textContent = "Delete employee"; } }
  function close(dialog) { if (dialog.open) dialog.close(); }
  function bind() {
    $("[data-workforce-add]").onclick = () => openEmployeeForm(); employeeForm.onsubmit = saveEmployee;
    $$('[data-employee-form-close],[data-employee-form-cancel]').forEach(b => b.onclick = () => close(employeeDialog));
    $$('[data-detail-close]').forEach(b => b.onclick = () => close(detailDialog));
    $("[data-employee-edit]").onclick = () => openEmployeeForm(state.selected); $("[data-employee-delete]").onclick = () => { $("[data-delete-error]").hidden = true; deleteDialog.showModal(); };
    $$('[data-delete-cancel]').forEach(b => b.onclick = () => close(deleteDialog)); $("[data-delete-confirm]").onclick = deleteEmployee;
    $("[data-assignment-new]").onclick = () => openAssignmentForm(); assignmentForm.onsubmit = saveAssignment; $$('[data-assignment-close],[data-assignment-cancel]').forEach(b => b.onclick = () => close(assignmentDialog));
    $("[data-workforce-rows]").onclick = e => { const detail = e.target.closest("[data-workforce-detail]"), edit = e.target.closest("[data-workforce-edit]"); if (detail) openDetail(detail.dataset.workforceDetail); if (edit) { const employee = state.employees.find(x => x.id === edit.dataset.workforceEdit); openEmployeeForm(employee); } };
    $("[data-assignment-state]").onclick = e => { const edit = e.target.closest("[data-assignment-edit]"), release = e.target.closest("[data-assignment-release]"), remove = e.target.closest("[data-assignment-remove]"); const rows = state.assignments[state.selected?.id] || []; if (edit) openAssignmentForm(rows.find(a => a.id === edit.dataset.assignmentEdit)); if (release) mutateAssignment(release.dataset.assignmentRelease, "PATCH", { released_at: new Date().toISOString().slice(0, 10) }, "Release"); if (remove && window.confirm("Remove this project assignment?")) mutateAssignment(remove.dataset.assignmentRemove, "DELETE", null, "Removal"); };
    $$('[data-status-filter]').forEach(b => b.onclick = () => { state.statusFilter = b.dataset.statusFilter; $$('[data-status-filter]').forEach(x => x.classList.remove("active")); b.classList.add("active"); render(); });
    $("#workforce-search-input").oninput = e => { state.search = e.target.value; render(); };
  }
  document.addEventListener("DOMContentLoaded", () => { bind(); reload(); });
})();
