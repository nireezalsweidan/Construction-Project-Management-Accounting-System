document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-cedar-workflow]");
  if (!root) return;

  const scenes = [
    {key:"plan",name:"PLAN",title:"Turn the contract into a clear delivery plan.",copy:"Create phases, milestones, responsibilities, and target dates before work begins.",metric:"6 phases",sub:"18 milestones mapped"},
    {key:"budget",name:"BUDGET",title:"Give every dollar a purpose.",copy:"Allocate labor, material, contractor, and equipment budgets against the approved contract.",metric:"$1.84M",sub:"Approved project budget"},
    {key:"procure",name:"PROCURE",title:"Move materials with confidence.",copy:"Request, approve, order, receive, and track supplies without losing cost visibility.",metric:"14 POs",sub:"92% delivered on time"},
    {key:"build",name:"BUILD",title:"Connect the office with the site.",copy:"Field teams report progress, labor, material use, documents, and issues as work happens.",metric:"68%",sub:"Structural works on track"},
    {key:"control",name:"CONTROL",title:"See risk before it becomes delay.",copy:"Managers review approvals, cost variance, receivables, and project health from one view.",metric:"6.2%",sub:"Under planned cost curve"},
    {key:"deliver",name:"DELIVER",title:"Close with proof and profit.",copy:"Complete handover, close financial records, and preserve a traceable project history.",metric:"21.4%",sub:"Forecast project margin"}
  ];

  const stage = root.querySelector("[data-film-stage]");
  const controls = [...root.querySelectorAll("[data-film-scene]")];
  const play = root.querySelector("[data-film-play]");
  const pauseIcon = play.querySelector("[data-pause-icon]");
  const playIcon = play.querySelector("[data-play-icon]");
  let current = 0, playing = true, timer;

  const setText = (selector, value) => { root.querySelector(selector).textContent = value; };
  const render = index => {
    current = index; const scene = scenes[index]; const number = String(index + 1).padStart(2,"0");
    stage.className = `film-stage scene-${scene.key}`;
    setText("[data-film-step]", `STEP ${number} / 06`);
    setText("[data-film-name]", scene.name);
    setText("[data-film-title]", scene.title);
    setText("[data-film-copy]", scene.copy);
    setText("[data-film-card-name]", scene.name[0] + scene.name.slice(1).toLowerCase());
    setText("[data-film-number]", number);
    setText("[data-film-metric]", scene.metric);
    setText("[data-film-sub]", scene.sub);
    setText("[data-film-task]", scene.title);
    controls.forEach((button, i) => button.classList.toggle("active", i === index));
  };
  const schedule = () => { clearInterval(timer); if (playing) timer = setInterval(() => render((current + 1) % scenes.length), 4300); };
  controls.forEach(button => button.addEventListener("click", () => { render(Number(button.dataset.filmScene)); playing = false; updatePlay(); schedule(); }));
  const updatePlay = () => { play.querySelector("span").textContent = playing ? "Pause" : "Play"; pauseIcon.hidden = !playing; playIcon.hidden = playing; play.setAttribute("aria-label", playing ? "Pause workflow" : "Play workflow"); };
  play.addEventListener("click", () => { playing = !playing; updatePlay(); schedule(); });
  render(0); updatePlay(); schedule();
});
