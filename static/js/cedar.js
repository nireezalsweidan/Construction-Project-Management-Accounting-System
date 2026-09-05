document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  document.querySelectorAll("[data-sidebar-open]").forEach(button => button.addEventListener("click", () => document.body.classList.add("sidebar-open")));
  document.querySelectorAll("[data-sidebar-close]").forEach(button => button.addEventListener("click", () => document.body.classList.remove("sidebar-open")));

  document.querySelectorAll("[data-password-toggle]").forEach(toggle => toggle.addEventListener("click", () => {
    const field = toggle.closest(".login-field");
    const input = field ? field.querySelector("input") : document.querySelector("#id_password");
    if (!input) return;
    const visible = input.type === "text";
    input.type = visible ? "password" : "text";
    toggle.textContent = visible ? "Show" : "Hide";
  }));

  const loginForm = document.querySelector("[data-login-form]");
  if (loginForm) loginForm.addEventListener("submit", () => {
    const submit = document.querySelector("[data-submit]");
    submit.disabled = true;
    submit.textContent = "Signing in to Cedar Construction…";
  });

  const settings = document.querySelector("[data-settings]");
  if (settings) {
    const tabs = [...settings.querySelectorAll("[data-settings-tab]")];
    const panels = [...settings.querySelectorAll("[data-settings-panel]")];
    tabs.forEach(tab => tab.addEventListener("click", () => {
      const target = tab.dataset.settingsTab;
      tabs.forEach(item => item.classList.toggle("active", item === tab));
      panels.forEach(panel => panel.classList.toggle("active", panel.dataset.settingsPanel === target));
    }));
    settings.querySelectorAll(".switch").forEach(toggle => toggle.addEventListener("click", () => {
      const enabled = toggle.classList.toggle("on");
      toggle.setAttribute("aria-pressed", String(enabled));
    }));
  }

  const workflow = document.querySelector("[data-workflow]");
  if (!workflow) return;
  const scenes = [
    { name:"PLAN", title:"Turn the contract into a clear delivery plan.", copy:"Create phases, milestones, responsibilities, and target dates before work begins.", metric:"6 phases", sub:"18 milestones mapped" },
    { name:"BUDGET", title:"Give every dollar a purpose.", copy:"Allocate labor, material, contractor, and equipment budgets against the approved contract.", metric:"$1.84M", sub:"Approved project budget" },
    { name:"PROCURE", title:"Move materials with confidence.", copy:"Request, approve, order, receive, and track supplies without losing cost visibility.", metric:"14 POs", sub:"92% delivered on time" },
    { name:"BUILD", title:"Connect the office with the site.", copy:"Field teams report progress, labor, material use, documents, and issues as work happens.", metric:"68%", sub:"Structural works on track" },
    { name:"CONTROL", title:"See risk before it becomes delay.", copy:"Managers review approvals, cost variance, receivables, and project health from one view.", metric:"6.2%", sub:"Under planned cost curve" },
    { name:"DELIVER", title:"Close with proof and profit.", copy:"Complete handover, close financial records, and preserve a traceable project history.", metric:"21.4%", sub:"Forecast project margin" }
  ];
  const controls = [...workflow.querySelectorAll("[data-scene]")];
  const playButton = workflow.querySelector("[data-play]");
  let index = 0, playing = true, timer;
  const render = next => {
    index = next; const scene = scenes[index];
    workflow.querySelector("[data-step]").textContent = `STEP ${String(index + 1).padStart(2,"0")} / 06`;
    workflow.querySelector("[data-icon]").textContent = String(index + 1).padStart(2,"0");
    workflow.querySelector("[data-name]").textContent = scene.name;
    workflow.querySelector("[data-title]").textContent = scene.title;
    workflow.querySelector("[data-copy]").textContent = scene.copy;
    workflow.querySelector("[data-card-name]").textContent = scene.name[0] + scene.name.slice(1).toLowerCase();
    workflow.querySelector("[data-metric]").textContent = scene.metric;
    workflow.querySelector("[data-sub]").textContent = scene.sub;
    workflow.querySelector("[data-task]").textContent = scene.title;
    controls.forEach((button, i) => button.classList.toggle("active", i === index));
  };
  const restart = () => { clearInterval(timer); if (playing) timer = setInterval(() => render((index + 1) % scenes.length), 4300); };
  controls.forEach(button => button.addEventListener("click", () => { playing = false; playButton.textContent = "Play"; render(Number(button.dataset.scene)); restart(); }));
  playButton.addEventListener("click", () => { playing = !playing; playButton.textContent = playing ? "Pause" : "Play"; restart(); });
  restart();

  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      document.querySelector(".topbar .search")?.classList.add("focused");
    }
    if (event.key === "Escape") document.body.classList.remove("sidebar-open");
  });
});
