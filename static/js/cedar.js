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
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const buttons = [...workflow.querySelectorAll("[data-step]")];
    const indicator = workflow.querySelector(".step-indicator");
    const list = workflow.querySelector(".cedar-steps ol");
    const pauseButton = workflow.querySelector("[data-pause]");
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
    const selectStep = button => {
      buttons.forEach(item => {
        const active = item === button;
        item.classList.toggle("active", active);
        if (active) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
      moveIndicator(button);
      if (!reduceMotion) gsap.fromTo(button, { scale: 0.96 }, { scale: 1, duration: 0.35, ease: "back.out(2)" });
    };
    buttons.forEach(button => button.addEventListener("click", () => selectStep(button)));
    workflow.querySelectorAll(".procure-card").forEach(card => {
      card.addEventListener("mouseenter", () => { if (!reduceMotion) gsap.to(card, { y: -4, scale: 1.015, duration: 0.2 }); });
      card.addEventListener("mouseleave", () => { if (!reduceMotion) gsap.to(card, { y: 0, scale: 1, duration: 0.2 }); });
    });
    pauseButton.addEventListener("click", () => {
      const paused = pauseButton.getAttribute("aria-pressed") === "true";
      pauseButton.setAttribute("aria-pressed", String(!paused));
      pauseButton.textContent = paused ? "Pause" : "Resume";
      if (paused) gsap.globalTimeline.resume();
      else gsap.globalTimeline.pause();
    });
    const positionActive = () => moveIndicator(workflow.querySelector("[data-step].active"), false);
    window.addEventListener("resize", positionActive);
    requestAnimationFrame(positionActive);
  }

  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      document.querySelector(".topbar .search")?.classList.add("focused");
    }
    if (event.key === "Escape") document.body.classList.remove("sidebar-open");
  });
});
