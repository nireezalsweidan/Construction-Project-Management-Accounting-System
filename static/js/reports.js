/* Reports / Decision Intelligence page.
   Consumes authenticated DRF endpoints under /api/accounting/, /api/clients/,
   /api/projects/ using the dashboard session (SessionAuthentication + CSRF).
   Read-only: no write operations from this page. */
(() => {
  "use strict";

  const E = {
    profitLoss: "/api/accounting/reports/profit-loss/",
    trend: "/api/accounting/reports/trend/",
    aging: "/api/clients/clients/aging/",
    portfolioBudget: "/api/projects/budgets/portfolio-summary/",
    transactions: "/api/accounting/financial-transactions/",
  };

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => Number(v || 0).toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

  const state = {
    dateFrom: "",
    dateTo: "",
    activePanel: null,
    ledgerPage: 1,
    ledgerNext: null,
    ledgerPrev: null,
    ledgerCount: 0,
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
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : (typeof v === "object" ? JSON.stringify(v) : v)}`)
            .join("\n");
        } else if (body) {
          message = String(body);
        }
      } catch (_) { /* non-JSON / network body */ }
      throw new Error(message || `Request failed (${response.status})`);
    }
    return response.status === 204 ? null : response.json();
  }

  function buildParams() {
    const p = new URLSearchParams();
    if (state.dateFrom) p.set("date_from", state.dateFrom);
    if (state.dateTo) p.set("date_to", state.dateTo);
    return p.toString();
  }

  /* ---- Loading states ---- */
  function setLoading(panel, loading) {
    const el = $(`[data-panel="${panel}"]`);
    if (!el) return;
    if (loading) el.classList.add("loading");
    else el.classList.remove("loading");
  }

  function showError(panel, msg) {
    const el = $(`[data-panel="${panel}"]`);
    if (!el) return;
    const existing = el.querySelector(".panel-error");
    if (existing) existing.remove();
    const div = document.createElement("div");
    div.className = "panel-error";
    div.style.cssText = "border-radius:7px;background:#f7d7d1;color:#7f2018;padding:10px;margin-bottom:14px;font-size:11px";
    div.textContent = msg;
    el.querySelector(".panel-head").after(div);
  }

  /* ---- Stat cards ---- */
  function renderStats(plData, agingData, budgetData) {
    const revenue = Number(plData.revenue?.total || 0);
    const expenses = Number(plData.expenses?.total || 0);
    const netProfit = Number(plData.net_profit || 0);
    const receivables = Number(agingData.total_outstanding || 0);
    const underBudget = (budgetData.projects || []).filter((r) => Number(r.variance) >= 0).length;

    $("[data-metric=revenue]").textContent = money(revenue);
    $("[data-metric=expenses]").textContent = money(expenses);
    $("[data-metric=net_profit]").textContent = money(netProfit);
    $("[data-metric=receivables]").textContent = money(receivables);
    $("[data-metric=under_budget]").textContent = underBudget;
  }

  /* ---- Report card quick values ---- */
  function renderCardValues(plData, agingData, budgetData, ledgerCount) {
    const $v = (sel, val) => { const el = $(sel); if (el) el.textContent = val; };
    $v("[data-card-value=pnl-profit]", money(plData.net_profit || 0));
    $v("[data-card-value=aging-overdue]", money(agingData.total_outstanding || 0));
    const underBudget = (budgetData.projects || []).filter((r) => Number(r.variance) >= 0).length;
    const totalProjects = (budgetData.projects || []).length;
    $v("[data-card-value=budget-variance]", `${underBudget}/${totalProjects}`);
    $v("[data-card-value=ledger-count]", ledgerCount.toLocaleString());
  }

  /* ---- P&L panel ---- */
  function renderPL(data) {
    $("[data-pnl-period]").textContent = data.date_from || data.date_to
      ? `${data.date_from || 'Start'} – ${data.date_to || 'End'}`
      : "Full period";
    $("[data-pnl-revenue]").textContent = money(data.revenue?.total);
    $("[data-pnl-expenses]").textContent = money(data.expenses?.total);
    $("[data-pnl-net]").textContent = money(data.net_profit);

    function renderAccounts(container, accounts) {
      const el = $(container);
      if (!accounts || !accounts.length) { el.innerHTML = '<span style="font-size:11px;color:#607b76">No accounts</span>'; return; }
      el.innerHTML = accounts.map((a) =>
        `<div class="pnl-account-row"><span>${esc(a.code)} ${esc(a.name)}</span><strong>${money(a.amount)}</strong></div>`
      ).join("");
    }
    renderAccounts("[data-pnl-revenue-accounts]", data.revenue?.accounts);
    renderAccounts("[data-pnl-expense-accounts]", data.expenses?.accounts);
  }

  /* ---- Trend bar chart ---- */
  function renderTrend(series) {
    const container = $("[data-trend-chart]");
    if (!series || !series.length) {
      container.innerHTML = '<div class="empty-chart">No trend data available. Post transactions to see monthly trends.</div>';
      return;
    }
    const maxVal = Math.max(...series.flatMap((r) => [Number(r.revenue), Number(r.expense)]), 1);

    container.innerHTML = series.map((r) => {
      const revH = Math.max((Number(r.revenue) / maxVal) * 100, 2);
      const expH = Math.max((Number(r.expense) / maxVal) * 100, 2);
      const label = r.month?.slice(5) || r.month;
      return `<div class="bar-group"><div class="bars"><span class="bar revenue" style="height:${revH}%" title="Revenue: ${money(r.revenue)}"></span><span class="bar expense" style="height:${expH}%" title="Expense: ${money(r.expense)}"></span></div><span class="bar-label">${esc(label)}</span></div>`;
    }).join("");
  }

  /* ---- Aging panel ---- */
  function renderAging(data) {
    $("[data-aging-as-of]").textContent = `As of ${data.as_of || "today"}`;
    const buckets = data.buckets || [];
    const bucketEls = $$("[data-aging-buckets] .aging-bucket");
    buckets.forEach((b, i) => {
      if (bucketEls[i]) {
        bucketEls[i].querySelector("strong").textContent = money(b.total);
      }
    });

    const allInvoices = buckets.flatMap((b) => (b.invoices || []).map((inv) => ({ ...inv, bucket_label: b.label })));
    const tbody = $("[data-aging-rows]");
    if (!allInvoices.length) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="6"><b>No outstanding invoices</b></td></tr>';
      return;
    }
    allInvoices.sort((a, b) => b.days_overdue - a.days_overdue);
    tbody.innerHTML = allInvoices.map((inv) =>
      `<tr><td>${esc(inv.invoice_number)}</td><td>${esc(inv.client_name || "—")}</td><td>${esc(inv.project || "—")}</td><td>${esc(inv.due_date)}</td><td>${inv.days_overdue}</td><td>${money(inv.outstanding_balance)}</td></tr>`
    ).join("");
  }

  /* ---- Budget panel ---- */
  function renderBudget(data) {
    const rows = data.projects || [];
    const totals = data.totals || {};
    const tbody = $("[data-budget-rows]");
    if (!rows.length) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="6"><b>No projects with active budgets</b></td></tr>';
    } else {
      tbody.innerHTML = rows.map((r) => {
        const varianceClass = Number(r.variance) >= 0 ? "" : " style=\"color:#a23a31\"";
        return `<tr><td>${esc(r.project_name)} <span style="color:#607b76;font-size:10px">(${esc(r.project_code)})</span></td><td>${money(r.total_budget_header)}</td><td>${money(r.budgeted)}</td><td>${money(r.actual)}</td><td${varianceClass}>${money(r.variance)}</td><td>${money(r.remaining)}</td></tr>`;
      }).join("");
    }

    const setT = (sel, val) => { const el = $(sel); if (el) el.textContent = money(val); };
    setT("[data-budget-total-budgeted]", totals.budgeted);
    setT("[data-budget-total-actual]", totals.actual);
    setT("[data-budget-total-variance]", totals.variance);
    setT("[data-budget-total-remaining]", totals.remaining);
  }

  /* ---- Ledger panel ---- */
  async function loadLedger(page = 1) {
    state.ledgerPage = page;
    const p = new URLSearchParams();
    p.set("page", page);
    if (state.dateFrom) p.set("transaction_date_after", state.dateFrom);
    if (state.dateTo) p.set("transaction_date_before", state.dateTo);
    p.set("status", "POSTED");
    p.set("ordering", "-transaction_date");

    try {
      const data = await api(`${E.transactions}?${p}`);
      const rows = data.results || [];
      state.ledgerNext = data.next;
      state.ledgerPrev = data.previous;
      state.ledgerCount = data.count || 0;

      const tbody = $("[data-ledger-rows]");
      if (!rows.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6"><b>No posted transactions</b></td></tr>';
      } else {
        tbody.innerHTML = rows.map((t) =>
          `<tr><td>${esc(t.transaction_number)}</td><td>${esc(t.transaction_date)}</td><td>${esc(t.description || "—")}</td><td>${esc(t.project_name || "—")}</td><td>${money(t.total_debit)}</td><td>${money(t.total_credit)}</td></tr>`
        ).join("");
      }

      $("[data-ledger-page-info]").textContent = `Page ${state.ledgerPage}`;
      const prevBtn = $("[data-ledger-prev]");
      const nextBtn = $("[data-ledger-next]");
      prevBtn.disabled = !state.ledgerPrev;
      nextBtn.disabled = !state.ledgerNext;
    } catch (err) {
      showError("ledger", err.message);
    }
  }

  /* ---- Panel navigation ---- */
  function openPanel(name) {
    if (state.activePanel === name) {
      $$("[data-panel]").forEach((el) => el.hidden = true);
      state.activePanel = null;
      return;
    }
    $$("[data-panel]").forEach((el) => el.hidden = true);
    const panel = $(`[data-panel="${name}"]`);
    if (panel) panel.hidden = false;
    state.activePanel = name;
  }

  /* ---- Full load ---- */
  async function loadAll() {
    const params = buildParams();
    try {
      const [plData, agingData, budgetData] = await Promise.all([
        api(`${E.profitLoss}?${params}`),
        api(E.aging),
        api(E.portfolioBudget),
      ]);

      renderStats(plData, agingData, budgetData);
      renderCardValues(plData, agingData, budgetData, state.ledgerCount);

      renderPL(plData);

      const trendData = await api(`${E.trend}?${params}`);
      renderTrend(trendData);
      $("[data-card-value=trend-months]").textContent = `${trendData.length} month${trendData.length !== 1 ? "s" : ""}`;

      renderAging(agingData);
      renderBudget(budgetData);
      await loadLedger(state.ledgerPage);
    } catch (err) {
      console.error("Reports load error:", err);
    }
  }

  /* ---- Init ---- */
  function init() {
    /* Report card navigation */
    $$(".report-card[data-report-nav]").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.tagName === "BUTTON" && e.target.disabled) return;
        openPanel(card.dataset.reportNav);
      });
    });

    /* Date filter changes */
    $("[data-date-from]").addEventListener("change", (e) => {
      state.dateFrom = e.target.value;
      loadAll();
    });
    $("[data-date-to]").addEventListener("change", (e) => {
      state.dateTo = e.target.value;
      loadAll();
    });

    /* Ledger pagination */
    $("[data-ledger-prev]").addEventListener("click", () => { if (state.ledgerPrev) loadLedger(state.ledgerPage - 1); });
    $("[data-ledger-next]").addEventListener("click", () => { if (state.ledgerNext) loadLedger(state.ledgerPage + 1); });

    loadAll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
