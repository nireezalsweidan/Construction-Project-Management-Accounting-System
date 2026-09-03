(() => {
  const root = document.querySelector("[data-project-detail]");
  if (!root) return;

  const id = root.dataset.projectId;
  const $ = s => root.querySelector(s);
  const dialog = document.querySelector("[data-detail-dialog]");
  const form = dialog.querySelector("form");

  // Utility functions
  const esc = v => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
  const label = v => String(v || "—").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
  const money = v => new Intl.NumberFormat(undefined, {style:"currency", currency:"USD", maximumFractionDigits:0}).format(Number(v || 0));
  const csrf = () => decodeURIComponent(document.cookie.split("; ").find(c => c.startsWith("csrftoken="))?.split("=")[1] || "");

  let project, phases = [], budgets = [], changeOrders = [];

  async function request(path, options = {}, optional = false) {
    const r = await fetch(`/api/projects/${path}`, {
      credentials:"same-origin",
      ...options,
      headers:{
        Accept:"application/json",
        ...(options.method ? {"Content-Type":"application/json", "X-CSRFToken":csrf()} : {}),
        ...options.headers
      }
    });
    const data = await r.json().catch(() => ({}));
    if (optional && r.status === 404) return null;
    if (!r.ok) throw new Error(data.detail || Object.values(data).flat().join(" ") || `Request failed (${r.status})`);
    return data;
  }

  const result = data => Array.isArray(data) ? data : data.results || [];

  function table(target, headers, rows) {
    $(target).innerHTML = `<table><thead><tr>${headers.map(x => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}"><strong>No records found.</strong></td></tr>`}</tbody></table>`;
  }

  async function load() {
    const [p, phaseData, summary, ordersData, docs, budgetData] = await Promise.all([
      request(`projects/${id}/`),
      request(`projects/${id}/phases/`),
      request(`projects/${id}/budget-summary/`, {}, true),
      request(`change-orders/?project=${id}`),
      request(`projects/${id}/documents/`),
      request(`budgets/?project=${id}`)
    ]);

    project = p;
    phases = result(phaseData);
    budgets = result(budgetData);
    changeOrders = result(ordersData);

    $("[data-project-code]").textContent = p.code;
    $("[data-project-name]").textContent = p.name;
    $("[data-project-initials]").textContent = p.name.split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase();
    $("[data-project-meta]").textContent = [p.code, p.location, label(p.project_type)].filter(Boolean).join(" · ");

    const status = $("[data-project-status]");
    status.className = `status ${p.status.toLowerCase().replaceAll("_","-")}`;
    status.innerHTML = `<i></i>${esc(label(p.status))}`;
    $("[data-contract-value]").textContent = money(p.contract_value);

    const progress = phases.length ? phases.reduce((n,x)=>n+Number(x.progress_percentage||0),0)/phases.length : 0;
    $("[data-project-progress]").textContent = `${Math.round(progress)}%`;
    $("[data-project-progress-bar]").style.width = `${progress}%`;

    $("[data-budget-total]").textContent = summary ? money(summary.totals.budgeted) : "—";
    $("[data-actual-total]").textContent = summary ? money(summary.totals.actual) : "—";
    $("[data-remaining-total]").textContent = summary ? money(summary.totals.remaining) : "—";

    // Update budget hero section
    if (summary) {
      $("[data-budget-hero-total]").textContent = money(summary.totals.budgeted);
      $("[data-budget-hero-actual]").textContent = money(summary.totals.actual);
      $("[data-budget-hero-remaining]").textContent = money(summary.totals.remaining);
      const variance = summary.totals.budgeted > 0 ? ((summary.totals.budgeted - summary.totals.actual) / summary.totals.budgeted * 100).toFixed(1) : 0;
      $("[data-budget-hero-variance]").textContent = `${variance > 0 ? "+" : ""}${variance}%`;
    }

    table("[data-project-phases]",
      ["Phase","Status","Progress","Start","End","Actions"],
      phases.map(x=>`<tr><td><strong>${esc(x.name)}</strong></td><td><span class="status ${esc(String(x.status).toLowerCase())}">${esc(label(x.status))}</span></td><td><div class="progress-cell"><div><div style="width:${x.progress_percentage}%"></div></div><b>${x.progress_percentage}%</b></div></td><td>${esc(x.start_date || "—")}</td><td>${esc(x.end_date || "—")}</td><td><button class="quiet-button" data-action-edit-phase title="Edit"><i data-lucide="edit"></i></button><button class="quiet-button" data-action-update-progress title="Progress"><i data-lucide="percent"></i></button></td></tr>`)
    );

    table("[data-project-budget]",
      ["Category","Budgeted","Actual","Remaining"],
      (summary?.categories||[]).map(x=>`<tr><td>${esc(x.category_display)}</td><td>${money(x.budgeted)}</td><td>${money(x.actual)}</td><td>${money(x.remaining)}</td></tr>`)
    );

    table("[data-project-change-orders]",
      ["Number","Description","Amount","Date","Status","Actions"],
      changeOrders.map(x => {
        let actions = "";
        if (x.status === "PENDING") {
          actions = `<button class="quiet-button" data-action-approve title="Approve"><i data-lucide="check"></i></button><button class="quiet-button" data-action-reject title="Reject"><i data-lucide="x"></i></button>`;
        }
        if (x.status === "PENDING" || x.status === "APPROVED") {
          actions += `<button class="quiet-button" data-action-cancel title="Cancel"><i data-lucide="trash-2"></i></button>`;
        }
        return `<tr><td><strong>${esc(x.number)}</strong></td><td>${esc(x.description)}</td><td>${money(x.amount)}</td><td>${esc(x.date)}</td><td><span class="status ${esc(String(x.status).toLowerCase())}">${esc(label(x.status))}</span></td><td>${actions || "—"}</td></tr>`;
      })
    );

    table("[data-project-documents]",
      ["File","Type","Uploaded"],
      result(docs).map(x=>`<tr><td><a href="${esc(x.file_path)}" target="_blank" rel="noopener">${esc(x.file_name)}</a></td><td>${esc(x.document_type||x.file_type)}</td><td>${esc(x.uploaded_at)}</td></tr>`)
    );
  }

  const fields = ({title, action, html, submit="Save"}) => {
    form.dataset.action = action;
    dialog.querySelector("[data-dialog-title]").textContent = title;
    dialog.querySelector("[data-dialog-fields]").innerHTML = html;
    dialog.querySelector("[data-dialog-submit]").textContent = submit;
    dialog.querySelector("[data-dialog-error]").textContent = "";
    dialog.showModal();
  };

  const input = (name,text,type="text",value="",required=false) => `<label>${text} <input name="${name}" type="${type}" value="${esc(value)}" ${required?"required":""}></label>`;

  function open(action, context) {
    if (action === "edit-project") {
      fields({
        title:"Edit project",
        action,
        html: input("name","Name","text",project.name,true)
          + input("code","Code","text",project.code,true)
          + `<label>Type <select name="project_type"><option value="WHOLE_BUILDING" ${project.project_type==="WHOLE_BUILDING"?"selected":""}>Whole Building</option><option value="MULTI_UNIT" ${project.project_type==="MULTI_UNIT"?"selected":""}>Multi Unit</option></select></label>`
          + input("start_date","Start date","date",project.start_date,true)
          + input("expected_completion_date","Expected completion","date",project.expected_completion_date||"")
          + input("contract_value","Contract value","number",project.contract_value,true)
          + `<label>Location <input name="location" value="${esc(project.location||"")}"></label><label>Description <textarea name="description">${esc(project.description||"")}</textarea></label>`
      });
    } else if (action === "add-phase") {
      fields({
        title:"Add phase",
        action,
        submit:"Add phase",
        html: input("name","Phase name","text","",true)
          + input("sequence_number","Sequence","number",String(phases.length+1),true)
          + input("start_date","Start date","date")
          + input("end_date","End date","date")
          + input("progress_percentage","Progress (%)","number","0",true)
          + `<label>Description <textarea name="description"></textarea></label>`
      });
    } else if (action === "edit-phase") {
      const phase = context;
      if (!phase) return;
      fields({
        title: `Edit phase: ${phase.name}`,
        action: "edit-phase",
        submit: "Update phase",
        html: input("name","Phase name","text",phase.name,true)
          + input("sequence_number","Sequence","number",String(phase.sequence_number),true)
          + input("start_date","Start date","date",phase.start_date)
          + input("end_date","End date","date",phase.end_date)
          + input("progress_percentage","Progress (%)","number",String(phase.progress_percentage),true)
          + `<label>Description <textarea name="description">${esc(phase.description||"")}</textarea></label>`
      });
      form.dataset.phaseId = phase.id;
    } else if (action === "update-phase-progress") {
      const phase = context;
      if (!phase) return;
      fields({
        title: `Update phase progress: ${phase.name}`,
        action: "update-phase-progress",
        submit: "Update",
        html: input("progress_percentage","Progress (%)","number",phase.progress_percentage,true)
          + input("status","Status","text",phase.status)
      });
      form.dataset.phaseId = phase.id;
    } else if (action === "new-budget") {
      fields({
        title:"New budget",
        action,
        submit:"Create budget",
        html: input("name","Budget name","text","",true)
          + input("total_budget","Total budget","number","",true)
      });
    } else if (action === "add-budget-item") {
      if (!budgets.length) return open("new-budget");
      fields({
        title:"Add budget item",
        action,
        submit:"Add budget item",
        html: `<label>Budget <select name="budget_id">${budgets.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join("")}</select></label>`
          + `<label>Category <select name="category"><option value="MATERIALS">Materials</option><option value="LABOR">Labor</option><option value="CONTRACTORS">Contractors</option><option value="EQUIPMENT">Equipment</option><option value="OTHER">Other</option></select></label>`
          + input("description","Description","text","")
          + input("budgeted_amount","Amount","number","",true)
      });
    } else if (action === "approve-budget") {
      const budget = context;
      if (!budget) return;
      fields({
        title: `Approve budget: ${budget.name}`,
        action: "approve-budget",
        submit: "Approve",
        html: `<p><strong>${esc(budget.name)}</strong></p><p>Total budget: ${money(budget.total_budget)}</p><p>Status will change from ${label(budget.status)} to APPROVED.</p>`
      });
      form.dataset.budgetId = budget.id;
    } else if (action === "add-change-order") {
      fields({
        title:"Create change order",
        action,
        submit:"Create",
        html: input("number","CO Number","text","",true)
          + input("description","Description","text","",true)
          + input("reason","Reason","text","")
          + input("amount","Amount","number","",true)
          + input("date","Date","date",new Date().toISOString().split('T')[0],true)
      });
    } else if (action === "approve-change-order") {
      const order = context;
      if (!order) return;
      fields({
        title: `Approve change order ${order.number}`,
        action: "approve-change-order",
        submit: "Approve",
        html: `<p><strong>${esc(order.description)}</strong></p><p>Amount: ${money(order.amount)}</p><label>Approved by (optional): <input name="approved_by" type="text"></label>`
      });
      form.dataset.orderId = order.id;
    } else if (action === "reject-change-order") {
      const order = context;
      if (!order) return;
      fields({
        title: `Reject change order ${order.number}`,
        action: "reject-change-order",
        submit: "Reject",
        html: `<p><strong>${esc(order.description)}</strong></p><p>Amount: ${money(order.amount)}</p><p>This change order will be marked as rejected.</p>`
      });
      form.dataset.orderId = order.id;
    } else if (action === "cancel-change-order") {
      const order = context;
      if (!order) return;
      fields({
        title: `Cancel change order ${order.number}`,
        action: "cancel-change-order",
        submit: "Cancel",
        html: `<p><strong>${esc(order.description)}</strong></p><p>Amount: ${money(order.amount)}</p><p>This change order will be marked as cancelled.</p>`
      });
      form.dataset.orderId = order.id;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      await load();
    } catch(e) {
      $("[data-project-detail-error]").textContent = `Could not load this project: ${e.message}`;
    }

    // Handle all action buttons
    [...root.querySelectorAll("[data-action]")].forEach(button => {
      button.addEventListener("click", () => {
        const action = button.dataset.action;
        if (action === "add-record") {
          open("add-change-order");
        } else {
          open(action);
        }
      });
    });

    const approveBtn = root.querySelector("[data-approve-btn]");
    if (approveBtn) {
      approveBtn.addEventListener("click", () => {
        const draftBudget = budgets.find(b => b.status === "DRAFT");
        if (draftBudget) open("approve-budget", draftBudget);
      });
    }

    // Handle change order row clicks for approve/reject/cancel
    const procurementPanel = root.querySelector('[data-project-panel="procurement"]');
    if (procurementPanel) {
      procurementPanel.addEventListener("click", (e) => {
        const row = e.target.closest("tr");
        if (!row) return;
        const orderNumber = row.querySelector("strong")?.textContent;
        const order = changeOrders.find(o => o.number === orderNumber);
        if (!order) return;

        if (e.target.closest("[data-action-approve]")) {
          open("approve-change-order", order);
        } else if (e.target.closest("[data-action-reject]")) {
          open("reject-change-order", order);
        } else if (e.target.closest("[data-action-cancel]")) {
          open("cancel-change-order", order);
        }
      });
    }

    // Handle phase row clicks for progress update
    const phasesPanel = root.querySelector('[data-project-panel="phases"]');
    if (phasesPanel) {
      phasesPanel.addEventListener("click", (e) => {
        const button = e.target.closest("button");
        if (!button) return;
        const row = button.closest("tr");
        if (!row) return;
        const phaseName = row.querySelector("strong")?.textContent;
        const phase = phases.find(p => p.name === phaseName);
        if (!phase) return;
        if (button.matches("[data-action-edit-phase]")) open("edit-phase", phase);
        if (button.matches("[data-action-update-progress]")) open("update-phase-progress", phase);
      });
    }

    document.querySelector("[data-dialog-close]").addEventListener("click", () => dialog.close());

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const submit = dialog.querySelector("[data-dialog-submit]");
      const error = dialog.querySelector("[data-dialog-error]");
      const data = Object.fromEntries(new FormData(form));
      Object.keys(data).forEach(k => { if (data[k] === "") delete data[k]; });

      let path, method = "POST";
      const action = form.dataset.action;

      if (action === "edit-project") {
        path = `projects/${id}/`;
        method = "PATCH";
      } else if (action === "add-phase") {
        path = "phases/";
        data.project_id = id;
      } else if (action === "edit-phase") {
        path = `phases/${form.dataset.phaseId}/`;
        method = "PATCH";
      } else if (action === "update-phase-progress") {
        path = `phases/${form.dataset.phaseId}/`;
        method = "PATCH";
      } else if (action === "new-budget") {
        path = "budgets/";
        data.project_id = id;
      } else if (action === "add-budget-item") {
        path = "budget-items/";
      } else if (action === "approve-budget") {
        path = `budgets/${form.dataset.budgetId}/`;
        method = "PATCH";
        data.status = "APPROVED";
      } else if (action === "add-change-order") {
        path = "change-orders/";
        data.project_id = id;
      } else if (action === "approve-change-order") {
        path = `change-orders/${form.dataset.orderId}/approve/`;
        delete data.approved_by; // Remove if empty
      } else if (action === "reject-change-order") {
        path = `change-orders/${form.dataset.orderId}/reject/`;
      } else if (action === "cancel-change-order") {
        path = `change-orders/${form.dataset.orderId}/cancel/`;
      } else {
        path = "change-orders/";
        data.project_id = id;
      }

      submit.disabled = true;
      error.textContent = "";

      try {
        await request(path, { method, body: JSON.stringify(data) });
        dialog.close();
        form.reset();
        await load();
      } catch (e) {
        error.textContent = e.message;
      } finally {
        submit.disabled = false;
      }
    });

    // Tab switching
    const tabs = [...root.querySelectorAll("[data-project-tab]")];
    const panels = [...root.querySelectorAll("[data-project-panel]")];
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(x => x.classList.toggle("active", x === tab));
        panels.forEach(x => x.hidden = x.dataset.projectPanel !== tab.dataset.projectTab);
      });
    });
  });
})();
