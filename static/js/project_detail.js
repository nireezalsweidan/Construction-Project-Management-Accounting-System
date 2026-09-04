(() => {
  const root = document.querySelector("[data-project-detail]");
  if (!root) return;

  const id = root.dataset.projectId;
  const $ = s => root.querySelector(s);
  const dialog = document.querySelector("[data-detail-dialog]");
  const form = dialog.querySelector("form");

  // Utility functions
  const esc = v => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
  const formValue = v => esc(v === null || v === undefined ? "" : v);
  const label = v => String(v || "—").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
  const statusClass = v => String(v || "").toLowerCase().replaceAll("_", "-");
  const money = v => new Intl.NumberFormat(undefined, {style:"currency", currency:"USD", maximumFractionDigits:0}).format(Number(v || 0));
  const csrf = () => decodeURIComponent(document.cookie.split("; ").find(c => c.startsWith("csrftoken="))?.split("=")[1] || "");

  // Dynamically-injected [data-lucide] icons (table action buttons, budget
  // card actions, ...) don't exist as SVGs until lucide.createIcons() runs
  // against the current DOM -- the static icons in the page shell get that
  // for free from base_dashboard.html's own load, but anything we render
  // ourselves needs a fresh call or the icon slot just stays empty.
  const refreshIcons = () => { if (window.lucide?.createIcons) window.lucide.createIcons(); };

  // Per-status action buttons for a budget card. Mirrors
  // Budget.ALLOWED_TRANSITIONS on the backend for the status-changing
  // actions, plus "edit" (not a transition itself -- editing an APPROVED
  // budget's name/total is what implicitly moves it to REVISED, handled
  // in the submit handler). The server re-validates every status change
  // regardless, so this config is only ever a UI convenience.
  const BUDGET_ACTIONS = {
    DRAFT: [
      { type: "transition", target: "APPROVED", label: "Approve", icon: "check" },
    ],
    APPROVED: [
      { type: "edit", label: "Edit", icon: "pencil" },
      { type: "transition", target: "CLOSED", label: "Close", icon: "lock" },
    ],
    REVISED: [
      { type: "edit", label: "Edit", icon: "pencil" },
      { type: "transition", target: "APPROVED", label: "Approve", icon: "check" },
      { type: "transition", target: "CLOSED", label: "Close", icon: "lock" },
    ],
    CLOSED: [],
  };
  const BUDGET_ITEM_CATEGORIES = ["MATERIALS", "LABOR", "CONTRACTORS", "EQUIPMENT", "OTHER"];

  let project, phases = [], budgets = [], changeOrders = [];
  // Per-budget Budget-vs-Actual breakdown (get_budget_summary), keyed by
  // budget id -- fetched once per load() alongside everything else and
  // reused both for each card's category table and for the aggregated
  // hero figures below.
  let budgetSummaries = new Map();

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

  function renderBudgets() {
    const container = $("[data-project-budgets]");
    if (!container) return;

    if (!budgets.length) {
      container.innerHTML = `<p class="budget-empty">No budgets yet for this project. Create one to start allocating cost categories.</p>`;
      return;
    }

    const phaseName = id => phases.find(p => p.id === id)?.name;

    container.innerHTML = budgets.map(budget => {
      const items = budget.items || [];
      const allocated = items.reduce((n, item) => n + Number(item.budgeted_amount || 0), 0);
      const unallocated = Number(budget.total_budget || 0) - allocated;
      const editable = budget.status === "DRAFT" || budget.status === "REVISED";

      const actions = (BUDGET_ACTIONS[budget.status] || []).map(a => {
        if (a.type === "edit") {
          return `<button class="quiet-button" type="button" data-action-edit-budget>
            <i data-lucide="${a.icon}"></i>${a.label}
          </button>`;
        }
        return `<button class="quiet-button" type="button" data-action-transition-budget data-target-status="${a.target}">
          <i data-lucide="${a.icon}"></i>${a.label}
        </button>`;
      }).join("");

      const itemRows = items.map(item => `<tr>
        <td>${esc(label(item.category))}</td>
        <td>${esc(phaseName(item.phase_id) || "—")}</td>
        <td>${esc(item.description || "—")}</td>
        <td>${money(item.budgeted_amount)}</td>
      </tr>`).join("");

      return `<article class="budget-card" data-budget-id="${budget.id}">
        <header class="budget-card-head">
          <div class="budget-card-title">
            <h3>${esc(budget.name)}</h3>
            <span class="status ${statusClass(budget.status)}"><i></i>${esc(label(budget.status))}</span>
          </div>
          <div class="budget-card-figures">
            <div class="figure figure-total"><strong>${money(budget.total_budget)}</strong><span>Total</span></div>
            <div class="figure figure-allocated"><strong>${money(allocated)}</strong><span>Allocated</span></div>
            <div class="figure figure-unallocated"><strong>${money(unallocated)}</strong><span>Unallocated</span></div>
          </div>
          <div class="budget-card-actions">
            ${editable ? `<button class="quiet-button" type="button" data-action-add-budget-item><i data-lucide="plus"></i>Add item</button>` : ""}
            ${actions}
          </div>
        </header>

        <div class="responsive-table">
          <table>
            <thead><tr><th>Category</th><th>Phase</th><th>Description</th><th>Amount</th></tr></thead>
            <tbody>${itemRows || `<tr><td colspan="4"><strong>No items allocated yet.</strong></td></tr>`}</tbody>
          </table>
        </div>
      </article>`;
    }).join("");
  }

  async function load() {
    const [p, phaseData, ordersData, docs, budgetData] = await Promise.all([
      request(`projects/${id}/`),
      request(`projects/${id}/phases/`),
      request(`change-orders/?project=${id}`),
      request(`projects/${id}/documents/`),
      request(`budgets/?project=${id}`)
    ]);

    project = p;
    phases = result(phaseData);
    budgets = result(budgetData);
    changeOrders = result(ordersData);

    // One Budget-vs-Actual summary per budget, fetched together. Used for
    // each card's category table and for the aggregated hero figures
    // below -- both need the same per-category budgeted/actual numbers.
    const summaries = await Promise.all(
      budgets.map(b => request(`projects/${id}/budget-summary/?budget=${b.id}`, {}, true))
    );
    budgetSummaries = new Map(budgets.map((b, i) => [b.id, summaries[i]]));

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

    // Approved budget = sum of every budget's total that's actually been
    // approved (DRAFT budgets don't count yet -- they're still proposals).
    // Actual/Remaining follow the same non-draft set, so all three stay
    // consistent with each other.
    const countedBudgets = budgets.filter(b => b.status !== "DRAFT");
    const approvedTotal = countedBudgets.reduce((n, b) => n + Number(b.total_budget || 0), 0);
    const actualTotal = countedBudgets.reduce((n, b) => n + Number(budgetSummaries.get(b.id)?.totals?.actual || 0), 0);
    const remainingTotal = approvedTotal - actualTotal;
    const variance = approvedTotal > 0 ? ((approvedTotal - actualTotal) / approvedTotal * 100).toFixed(1) : 0;

    $("[data-budget-total]").textContent = money(approvedTotal);
    $("[data-actual-total]").textContent = money(actualTotal);
    $("[data-remaining-total]").textContent = money(remainingTotal);

    $("[data-budget-hero-total]").textContent = money(approvedTotal);
    $("[data-budget-hero-actual]").textContent = money(actualTotal);
    $("[data-budget-hero-remaining]").textContent = money(remainingTotal);
    $("[data-budget-hero-variance]").textContent = `${variance > 0 ? "+" : ""}${variance}%`;

    table("[data-project-phases]",
      ["Phase","Status","Progress","Start","End","Actions"],
      phases.map(x => {
        const pct = Math.max(0, Math.min(100, Number(x.progress_percentage) || 0));
        return `<tr>
          <td><strong>${esc(x.name)}</strong></td>
          <td><span class="status ${statusClass(x.status)}"><i></i>${esc(label(x.status))}</span></td>
          <td><div class="progress-cell"><div><div style="width:${pct}%"></div></div><b>${pct}%</b></div></td>
          <td>${esc(x.start_date || "—")}</td>
          <td>${esc(x.end_date || "—")}</td>
          <td class="row-actions">
            <button class="quiet-button" type="button" data-action-edit-phase title="Edit phase" aria-label="Edit phase"><i data-lucide="pencil"></i></button>
            <button class="quiet-button" type="button" data-action-update-progress title="Update progress" aria-label="Update progress"><i data-lucide="percent"></i></button>
          </td>
        </tr>`;
      })
    );

    renderBudgets();

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

    refreshIcons();
  }

  const fields = ({title, action, html, submit="Save"}) => {
    form.dataset.action = action;
    dialog.querySelector("[data-dialog-title]").textContent = title;
    dialog.querySelector("[data-dialog-fields]").innerHTML = html;
    dialog.querySelector("[data-dialog-submit]").textContent = submit;
    dialog.querySelector("[data-dialog-error]").textContent = "";
    dialog.showModal();
  };

  const input = (name, text, type = "text", value = "", required = false, extra = {}) => {
    const attrs = Object.entries(extra).map(([k, v]) => `${k}="${esc(v)}"`).join(" ");
    return `<label>${text} <input name="${name}" type="${type}" value="${formValue(value)}" ${required ? "required" : ""} ${attrs}></label>`;
  };

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
        html: input("name","Phase name","text","",true,{placeholder:"e.g. Foundation"})
          + input("sequence_number","Order","number",String(phases.length+1),true,{min:"1",step:"1"})
          + input("start_date","Start date","date")
          + input("end_date","End date","date")
          + `<label class="span-2">Description <textarea name="description" placeholder="Optional notes about this phase"></textarea></label>`
      });
    } else if (action === "edit-phase") {
      const phase = context;
      if (!phase) return;
      fields({
        title: `Edit phase: ${phase.name}`,
        action: "edit-phase",
        submit: "Save changes",
        html: input("name","Phase name","text",phase.name,true)
          + input("sequence_number","Order","number",String(phase.sequence_number),true,{min:"1",step:"1"})
          + input("start_date","Start date","date",phase.start_date)
          + input("end_date","End date","date",phase.end_date)
          + `<label>Status <select name="status">${["NOT_STARTED","IN_PROGRESS","ON_HOLD","COMPLETED"].map(s=>`<option value="${s}" ${phase.status===s?"selected":""}>${label(s)}</option>`).join("")}</select></label>`
          + input("progress_percentage","Progress (%)","number",String(phase.progress_percentage),true,{min:"0",max:"100",step:"1"})
          + `<label class="span-2">Description <textarea name="description" placeholder="Optional notes about this phase">${esc(phase.description||"")}</textarea></label>`
      });
      form.dataset.phaseId = phase.id;
    } else if (action === "update-phase-progress") {
      const phase = context;
      if (!phase) return;
      fields({
        title: `Update progress: ${phase.name}`,
        action: "update-phase-progress",
        submit: "Update",
        html: input("progress_percentage","Progress (%)","number",phase.progress_percentage,true,{min:"0",max:"100",step:"1"})
      });
      form.dataset.phaseId = phase.id;
    } else if (action === "new-budget") {
      fields({
        title:"New budget",
        action,
        submit:"Create budget",
        html: input("name","Budget name","text","",true,{placeholder:"e.g. Materials"})
          + input("total_budget","Total budget","number","",true,{min:"0",step:"0.01",placeholder:"0.00"})
      });
    } else if (action === "edit-budget") {
      const budget = context;
      if (!budget) return;
      fields({
        title: `Edit budget: ${budget.name}`,
        action: "edit-budget",
        submit: "Save changes",
        html: input("name","Budget name","text",budget.name,true)
          + input("total_budget","Total budget","number",budget.total_budget,true,{min:"0",step:"0.01"})
          + (budget.status === "APPROVED"
              ? `<p class="dialog-hint span-2">This budget is currently Approved — saving changes will mark it as Revised.</p>`
              : "")
      });
      form.dataset.budgetId = budget.id;
      form.dataset.wasApproved = budget.status === "APPROVED" ? "true" : "";
    } else if (action === "add-budget-item") {
      const budget = context;
      if (!budget) return;

      const items = budget.items || [];
      const allocated = items.reduce((n, item) => n + Number(item.budgeted_amount || 0), 0);
      const remaining = Number(budget.total_budget || 0) - allocated;

      const categoryOptions = BUDGET_ITEM_CATEGORIES
        .map(c => `<option value="${c}">${label(c)}</option>`).join("")
        + `<option value="__custom__">Other (specify)…</option>`;

      const phaseOptions = `<option value="">No specific phase</option>`
        + phases.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("");

      fields({
        title: `Add item to ${budget.name}`,
        action,
        submit: "Add item",
        html: `<p class="dialog-hint span-2">Remaining to allocate: <strong>${money(remaining)}</strong> of ${money(budget.total_budget)}</p>`
          + `<label>Category <select name="category" data-category-select>${categoryOptions}</select></label>`
          + `<label data-custom-category hidden>Custom category <input name="category_custom" placeholder="e.g. Permits"></label>`
          + `<label>Phase <select name="phase_id">${phaseOptions}</select></label>`
          + input("budgeted_amount","Amount","number","",true,{min:"0",step:"0.01",placeholder:"0.00"})
          + `<label class="span-2">Description <input name="description" placeholder="e.g. Cement for foundation"></label>`
      });
      form.dataset.budgetId = budget.id;

      const categorySelect = dialog.querySelector("[data-category-select]");
      const customField = dialog.querySelector("[data-custom-category]");
      categorySelect?.addEventListener("change", () => {
        const isCustom = categorySelect.value === "__custom__";
        customField.hidden = !isCustom;
        customField.querySelector("input").required = isCustom;
      });
    } else if (action === "transition-budget") {
      const { budget, targetStatus } = context;
      if (!budget || !targetStatus) return;
      const verb = targetStatus === "APPROVED" ? "Approve" : targetStatus === "REVISED" ? "Mark as revised" : "Close";
      fields({
        title: `${verb} budget: ${budget.name}`,
        action: "transition-budget",
        submit: verb,
        html: `<p class="span-2">This will ${verb.toLowerCase()} <strong>${esc(budget.name)}</strong> — status changes from ${label(budget.status)} to ${label(targetStatus)}.`
          + (targetStatus === "CLOSED" ? " No further items can be added once closed." : "") + `</p>`
      });
      form.dataset.budgetId = budget.id;
      form.dataset.targetStatus = targetStatus;
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

    // Handle budget card clicks: add item / approve / mark revised / close.
    // Delegated (rather than bound per-card) since renderBudgets() replaces
    // this container's contents on every load().
    const budgetsPanel = root.querySelector("[data-project-budgets]");
    if (budgetsPanel) {
      budgetsPanel.addEventListener("click", (e) => {
        const card = e.target.closest("[data-budget-id]");
        if (!card) return;
        const budget = budgets.find(b => b.id === card.dataset.budgetId);
        if (!budget) return;

        if (e.target.closest("[data-action-add-budget-item]")) {
          open("add-budget-item", budget);
        } else if (e.target.closest("[data-action-edit-budget]")) {
          open("edit-budget", budget);
        } else if (e.target.closest("[data-action-transition-budget]")) {
          const targetStatus = e.target.closest("[data-action-transition-budget]").dataset.targetStatus;
          open("transition-budget", { budget, targetStatus });
        }
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
      } else if (action === "edit-budget") {
        path = `budgets/${form.dataset.budgetId}/`;
        method = "PATCH";
        // Editing an Approved budget is what marks it Revised -- editing
        // a Draft or already-Revised one just updates the fields.
        if (form.dataset.wasApproved === "true") data.status = "REVISED";
      } else if (action === "add-budget-item") {
        path = "budget-items/";
        data.budget_id = form.dataset.budgetId;
        // A custom category name replaces the "__custom__" sentinel value;
        // normalized the same way as the fixed choices (upper snake case)
        // so it reads consistently anywhere category is displayed.
        if (data.category === "__custom__") {
          data.category = (data.category_custom || "").trim().toUpperCase().replace(/\s+/g, "_");
        }
        delete data.category_custom;
      } else if (action === "transition-budget") {
        path = `budgets/${form.dataset.budgetId}/`;
        method = "PATCH";
        data.status = form.dataset.targetStatus;
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