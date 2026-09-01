document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-sidebar-open]").forEach(button => button.addEventListener("click", () => document.body.classList.add("sidebar-open")));
  document.querySelectorAll("[data-sidebar-close]").forEach(button => button.addEventListener("click", () => document.body.classList.remove("sidebar-open")));

  const passwordToggle = document.querySelector("[data-password-toggle]");
  if (passwordToggle) passwordToggle.addEventListener("click", () => {
    const input = document.querySelector("#id_password");
    const visible = input.type === "text";
    input.type = visible ? "password" : "text";
    passwordToggle.textContent = visible ? "Show" : "Hide";
  });

  const loginForm = document.querySelector("[data-login-form]");
  if (loginForm) loginForm.addEventListener("submit", () => {
    const submit = document.querySelector("[data-submit]");
    submit.disabled = true;
    submit.textContent = "Securing workspace…";
  });

  const workflow = document.querySelector("[data-cedar-control]");
  if (workflow && window.gsap) {
    const scenes = [
      { name: "PLAN", color: "#10b981", tagline: "Turn the contract into a clear delivery plan.", description: "Create phases, milestones, responsibilities, and target dates before work begins.", metricOneLabel: "Project structure", metricOne: "6 phases", metricTwoLabel: "Milestone coverage", metricTwo: "18 milestones mapped", owner: "Cedar PMO", status: "Ready", review: "Today, 16:00" },
      { name: "BUDGET", color: "#f59e0b", tagline: "Give every dollar a purpose.", description: "Allocate labor, material, contractor, and equipment budgets against the approved contract.", metricOneLabel: "Approved budget", metricOne: "$1.84M", metricTwoLabel: "Cost coverage", metricTwo: "100% allocated", owner: "Rana K.", status: "Approved", review: "Tomorrow, 09:00" },
      { name: "PROCURE", color: "#38bdf8", tagline: "Move materials with confidence.", description: "Request, approve, order, receive, and track supplies without losing cost visibility.", metricOneLabel: "Purchase orders", metricOne: "14 POs", metricTwoLabel: "Delivery performance", metricTwo: "92% delivered on time", owner: "Mahmoud A.", status: "On track", review: "Today, 16:00" },
      { name: "BUILD", color: "#f97316", tagline: "Connect the office with the site.", description: "Field teams report progress, labor, material use, documents, and issues as work happens.", metricOneLabel: "Site progress", metricOne: "68%", metricTwoLabel: "Current activity", metricTwo: "Structural works", owner: "Karim S.", status: "Active", review: "Daily, 17:00" },
      { name: "CONTROL", color: "#a78bfa", tagline: "See risk before it becomes delay.", description: "Managers review approvals, cost variance, receivables, and project health from one view.", metricOneLabel: "Cost variance", metricOne: "6.2% under", metricTwoLabel: "Pending decisions", metricTwo: "3 approvals", owner: "Finance team", status: "Watching", review: "Friday, 11:00" },
      { name: "DELIVER", color: "#22c55e", tagline: "Close with proof and profit.", description: "Complete handover, close financial records, and preserve a traceable project history.", metricOneLabel: "Forecast margin", metricOne: "21.4%", metricTwoLabel: "Handover readiness", metricTwo: "94% complete", owner: "Cedar team", status: "On track", review: "Monday, 10:00" }
    ];
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const buttons = [...workflow.querySelectorAll("[data-step]")];
    const indicator = workflow.querySelector(".step-indicator");
    const progress = workflow.querySelector("[data-step-progress]");
    const list = workflow.querySelector(".cedar-steps ol");
    const pauseButton = workflow.querySelector("[data-pause]");
    const sceneElements = [workflow.querySelector("[data-scene-copy]"), workflow.querySelector("[data-scene-card]")];
    let currentIndex = 0;
    let playing = true;
    let timer;
    const entrance = gsap.timeline({ paused: reduceMotion });

    entrance
      .from(workflow.querySelector('[data-animate="header"]'), { opacity: 0, y: -20, duration: 0.4 })
      .from(workflow.querySelectorAll('[data-animate="title"]'), { opacity: 0, y: 30, duration: 0.6, stagger: 0.1 }, "-=0.1")
      .from(workflow.querySelectorAll(".procure-card"), { opacity: 0, scale: 0.95, duration: 0.5, stagger: 0.15 }, "-=0.3")
      .from(workflow.querySelector('[data-animate="step-bar"]'), { opacity: 0, y: 20, duration: 0.4 }, "-=0.2");
    if (!reduceMotion) entrance.play();

    const moveIndicator = (button, animate = true) => {
      const listBox = list.getBoundingClientRect();
      const buttonBox = button.getBoundingClientRect();
      gsap.to(indicator, { x: buttonBox.left - listBox.left, width: buttonBox.width, duration: animate && !reduceMotion ? 0.45 : 0, ease: "power3.inOut" });
    };
    const updateContent = scene => {
      workflow.querySelector("[data-step-badge]").textContent = `STEP ${String(currentIndex + 1).padStart(2, "0")} / 06`;
      workflow.querySelector("[data-phase-title]").textContent = scene.name;
      workflow.querySelector("[data-phase-tagline]").textContent = scene.tagline;
      workflow.querySelector("[data-phase-description]").textContent = scene.description;
      workflow.querySelector("[data-workspace-name]").textContent = scene.name[0] + scene.name.slice(1).toLowerCase();
      workflow.querySelector("[data-workspace-number]").textContent = String(currentIndex + 1).padStart(2, "0");
      workflow.querySelector("[data-metric-one-label]").textContent = scene.metricOneLabel;
      workflow.querySelector("[data-metric-one]").textContent = scene.metricOne;
      workflow.querySelector("[data-metric-two-label]").textContent = scene.metricTwoLabel;
      workflow.querySelector("[data-metric-two]").textContent = scene.metricTwo;
      workflow.querySelector("[data-owner]").textContent = scene.owner;
      workflow.querySelector("[data-status]").textContent = scene.status;
      workflow.querySelector("[data-review]").textContent = scene.review;
      workflow.style.setProperty("--phase-color", scene.color);
    };
    const selectStep = (button, animate = true) => {
      currentIndex = Number(button.dataset.step) - 1;
      buttons.forEach(item => {
        const active = item === button;
        item.classList.toggle("active", active);
        if (active) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
      moveIndicator(button, animate);
      gsap.to(progress, { width: `${currentIndex * 20}%`, duration: animate && !reduceMotion ? 0.65 : 0, ease: "power2.inOut" });
      if (animate && !reduceMotion) {
        gsap.to(sceneElements, { opacity: 0, y: 10, duration: 0.2, stagger: 0.03, onComplete: () => {
          updateContent(scenes[currentIndex]);
          gsap.to(sceneElements, { opacity: 1, y: 0, duration: 0.45, stagger: 0.07, ease: "power3.out" });
        }});
        gsap.fromTo(button, { scale: 0.96 }, { scale: 1, duration: 0.35, ease: "back.out(2)" });
      } else updateContent(scenes[currentIndex]);
    };
    const restart = () => {
      clearInterval(timer);
      if (playing) timer = setInterval(() => selectStep(buttons[(currentIndex + 1) % buttons.length]), 4300);
    };
    buttons.forEach(button => button.addEventListener("click", () => {
      playing = false;
      pauseButton.textContent = "Resume";
      pauseButton.setAttribute("aria-pressed", "true");
      selectStep(button);
      restart();
    }));
    workflow.querySelectorAll(".procure-card").forEach(card => {
      card.addEventListener("mouseenter", () => { if (!reduceMotion) gsap.to(card, { y: -4, scale: 1.015, duration: 0.2 }); });
      card.addEventListener("mouseleave", () => { if (!reduceMotion) gsap.to(card, { y: 0, scale: 1, duration: 0.2 }); });
    });
    pauseButton.addEventListener("click", () => {
      playing = !playing;
      pauseButton.setAttribute("aria-pressed", String(!playing));
      pauseButton.textContent = playing ? "Pause" : "Resume";
      restart();
    });
    const positionActive = () => moveIndicator(workflow.querySelector("[data-step].active"), false);
    window.addEventListener("resize", positionActive);
    requestAnimationFrame(() => { selectStep(buttons[0], false); restart(); });
  }

  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      document.querySelector(".topbar .search")?.classList.add("focused");
    }
    if (event.key === "Escape") document.body.classList.remove("sidebar-open");
  });
});
