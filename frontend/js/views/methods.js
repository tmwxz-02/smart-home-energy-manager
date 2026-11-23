// How the AI works: the three methods, their formal models and a live calculator.
import { api } from "../api.js";
import { errorBox, field, fmt, h, select, tableWrap, td, th } from "../ui.js";

export async function render(root, ctx) {
  const s = ctx.meta.settings;
  const devices = await api.get("/devices");
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "How the AI works"),
      h("p", {}, "Three course methods solve three different problems inside the app. The values below are the current settings of this workspace."))));

  root.append(h("section", { class: "card prose" },
    h("h2", {}, "Pipeline"),
    h("div", { class: "formula" },
      "stored motion readings ──► hour-of-day priors ──► (1) HILL CLIMBING ──► daily schedule per device\n"
      + "new reading ──► (2) BAYES filter ──► P(occupied during the interval)\n"
      + "            ──► (3) MDP value iteration (QMDP) ──► ON / OFF inside the schedule ──► SQLite history\n"
      + "history ──► analytics: AI vs schedule-only on identical readings"),
    h("p", {}, "The agent is the controller of virtual devices. It perceives one motion reading per room per interval, cannot see true occupancy, and acts by switching devices ON or OFF. Its goal is to minimise expected electricity cost plus the user’s stated cost of discomfort.")));

  root.append(h("details", { class: "card prose", open: true },
    h("summary", {}, "1 · Hill climbing — choosing a device’s daily schedule (local search)"),
    h("ul", {},
      h("li", {}, h("strong", {}, "State: "), "24 hourly slots, each ON or OFF (2²⁴ ≈ 16.8 million schedules)."),
      h("li", {}, h("strong", {}, "Objective (minimise): "), "expected daily cost in money."),
      h("li", {}, h("strong", {}, "Neighbours: "), "all schedules that differ in exactly one hour (24)."),
      h("li", {}, h("strong", {}, "Move: "), "steepest ascent — to the cheapest neighbour, only if strictly cheaper."),
      h("li", {}, h("strong", {}, "Stop: "), "no neighbour is cheaper (local optimum), or 200 iterations."),
      h("li", {}, h("strong", {}, "Restarts: "), "from the current schedule and seeded random schedules; best result wins.")),
    h("div", { class: "formula" }, "cost(s) = Σh [ s_h · P_kW · tariff + (1 − s_h) · P(occ | hour h) · comfort_value ]\n        + startup_cost · #(OFF→ON switches)"),
    h("p", {}, "Without the start-up cost every hour would be independent and greedy search would be exact. The start-up cost links neighbouring hours, so local optima appear. The app therefore also computes the exact optimum by dynamic programming and reports the gap, so the quality of hill climbing is measured, not assumed."),
    h("p", {}, "P(occ | hour) comes from the room’s motion readings (method of moments: p = (motion rate − P(m|empty)) / (P(m|occ) − P(m|empty)), Laplace-smoothed, clipped to [0.02, 0.98]). Occupancy labels are never used here."),
    h("a", { href: "#/optimizer" }, "Open the optimizer →")));

  root.append(h("details", { class: "card prose", open: true },
    h("summary", {}, "2 · Bayesian inference — is anyone in the room? (HMM filtering)"),
    h("div", { class: "formula" },
      `P(occ | reading) = P(reading | occ) · P(occ) / P(reading)\n`
      + `P(reading) = P(reading | occ) · P(occ) + P(reading | empty) · P(empty)\n\n`
      + `Sensor model:  P(motion | occ) = ${s.motion_if_occupied}   P(motion | empty) = ${s.motion_if_empty}\n`
      + `Transition:    P(occ next | occ) = ${s.stay_occupied}   P(occ next | empty) = ${s.become_occupied}\n`
      + `Prediction:    P(occ next) = P(occ) · ${s.stay_occupied} + (1 − P(occ)) · ${s.become_occupied}`),
    h("p", {}, "Prior for a reading: if the room has a reading exactly one interval earlier, the prior is the prediction from that reading’s posterior (the HMM forward algorithm: predict → update). Otherwise it is the hour-of-day prior learned from earlier days only (no look-ahead), or the default prior when there is not enough history."),
    h("p", {}, "“No motion” does not mean “empty”: the sensor misses still people with probability 1 − P(motion | occ), so the posterior drops but rarely reaches zero.")));

  root.append(h("details", { class: "card prose", open: true },
    h("summary", {}, "3 · Markov decision process — switch ON or OFF? (value iteration)"),
    h("ul", {},
      h("li", {}, h("strong", {}, "States: "), "(occupancy during the interval, device state in the previous interval) — 4 states."),
      h("li", {}, h("strong", {}, "Actions: "), "ON or OFF inside the schedule; only OFF outside it (auto mode never starts a device outside its schedule)."),
      h("li", {}, h("strong", {}, "Transitions: "), "occupancy follows the Markov chain above (independent of the action); the device state becomes the action taken."),
      h("li", {}, h("strong", {}, "Rewards (money, negative = cost): "), "ON: −P_kW·Δt·tariff, plus −start-up cost if it was OFF; OFF while occupied: −comfort_value·Δt; OFF while empty: 0."),
      h("li", {}, h("strong", {}, "Solution: "), `finite-horizon value iteration (backward induction) over H = ${s.horizon} interval(s), γ = ${s.discount}.`)),
    h("div", { class: "formula" },
      "V_H(s) = 0\nQ_k(s, a) = r(s, a) + γ · Σ_s' T(s' | s, a) · V_{k+1}(s')\nV_k(s) = max_a Q_k(s, a)\n\n"
      + "Belief (occupancy is hidden):  Q(b, a) = b · Q_0(occ, d, a) + (1 − b) · Q_0(empty, d, a)   [QMDP]"),
    h("p", {}, h("strong", {}, "Honest scope. "), "This is a real multi-step plan only because the start-up cost makes today’s action change tomorrow’s state. Occupancy is not observed, so the belief is handled with the QMDP approximation, which assumes occupancy becomes known after the current step. It is an approximation of the partially observable problem (POMDP), not an exact solution. With H = 1 (or start-up cost 0) the rule reduces exactly to the prototype’s one-step comparison: ON if P(occ) ≥ energy cost ÷ comfort value. Unit tests check both facts.")));

  // Calculator
  const out = h("div");
  const prior = h("input", { type: "range", min: 0, max: 1, step: 0.01, value: 0.75, "aria-label": "Prior" });
  const priorText = h("output", {}, "0.75");
  const deviceSel = select("device", [["", "Prototype: 48 W fan"], ...devices.map((d) => [d.id, `${d.name} (${d.room_name})`])], "");
  const motionSel = select("motion", [["0", "No motion"], ["1", "Motion detected"]], "0");
  const wasOn = select("was_on", [["1", "Device was ON"], ["0", "Device was OFF"]], "1");
  let timer = null;
  const calc = async () => {
    try {
      const data = await api.post("/explain", { prior: Number(prior.value), motion: motionSel.value === "1", was_on: wasOn.value === "1", device_id: deviceSel.value ? Number(deviceSel.value) : null });
      out.replaceChildren(calcResult(data));
    } catch (error) { out.replaceChildren(errorBox(error)); }
  };
  prior.addEventListener("input", () => { priorText.textContent = Number(prior.value).toFixed(2); clearTimeout(timer); timer = setTimeout(calc, 150); });
  for (const el of [deviceSel, motionSel, wasOn]) el.addEventListener("change", calc);
  root.append(h("section", { class: "card" }, h("h2", {}, "Try it: one decision step by step"),
    h("p", { class: "muted small", style: "margin-bottom:10px" }, "All numbers are computed by the Python backend with the current settings."),
    h("div", { class: "form-grid" }, field(h("span", {}, "Prior P(occupied) = ", priorText), prior), field("Device", deviceSel), field("Reading", motionSel), field("Before this interval", wasOn)),
    h("div", { style: "margin-top:12px" }, out)));
  calc();
}

function calcResult(d) {
  const cur = d.settings.currency;
  const b = d.bayes;
  return h("div", { class: "stack" },
    tableWrap(["Step", "Calculation", th("Result", "num")], [
      h("tr", {}, td("P(reading)"), td(`${fmt.num(b.likelihood_occupied, 3)} × ${fmt.num(b.prior, 3)} + ${fmt.num(b.likelihood_empty, 3)} × ${fmt.num(1 - b.prior, 3)}`), td(fmt.num(b.evidence, 3), "num")),
      h("tr", {}, td("Posterior P(occ | reading)"), td(`${fmt.num(b.likelihood_occupied * b.prior, 4)} / ${fmt.num(b.evidence, 4)}`), td(fmt.num(b.posterior, 3), "num")),
      h("tr", {}, td("P(occ during interval)"), td(`${fmt.num(b.posterior, 3)} × ${d.settings.stay_occupied} + ${fmt.num(1 - b.posterior, 3)} × ${d.settings.become_occupied}`), td(fmt.num(d.predicted, 3), "num")),
      h("tr", {}, td("Energy cost / interval"), td(`${d.device.power_w} W × ${d.settings.interval_minutes} min × ${d.settings.tariff_per_kwh} ${cur}/kWh`), td(`${fmt.num(d.costs.energy, 3)} ${cur}`, "num")),
      h("tr", {}, td("Discomfort if OFF and occupied"), td(`${d.device.comfort_value_per_hour} ${cur}/h × ${d.settings.interval_minutes} min`), td(`${fmt.num(d.costs.comfort, 3)} ${cur}`, "num")),
      h("tr", {}, td("Break-even probability"), td("energy cost ÷ discomfort"), td(fmt.num(d.break_even, 3), "num")),
    ]),
    tableWrap(["Method", th("Q(ON)", "num"), th("Q(OFF)", "num"), "Decision"], [
      h("tr", {}, td("One-step rule (prototype, no start-up cost)"), td(fmt.num(d.one_step.q.ON, 3), "num"), td(fmt.num(d.one_step.q.OFF, 3), "num"), td(h("strong", {}, d.one_step.action))),
      h("tr", {}, td(`Value iteration, H = ${d.mdp.horizon}, start-up ${d.device.startup_cost} ${cur}`), td(fmt.num(d.mdp.q.ON, 3), "num"), td(fmt.num(d.mdp.q.OFF, 3), "num"), td(h("strong", {}, d.mdp.action))),
    ]),
    h("p", { class: "muted small" }, "Q values are expected rewards in money (negative = expected cost); the larger one wins, ties go to ON. In this calculator every future interval is assumed to be inside the schedule."));
}
