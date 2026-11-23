// Topic 12 walkthrough: the course brief's exact small-scale setup, step by step.
// input -> key calculation -> output -> one-sentence explanation for each method.
import { api } from "../api.js";
import { actionTag, errorBox, field, fmt, h, kpi, select, tableWrap, tag, td, th } from "../ui.js";

const ACTION_TAG = (name) => actionTag(name === "Keep On" || name === "ON" ? "ON" : "OFF");

export async function render(root) {
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Topic 12 walkthrough"),
      h("p", {}, "The course brief exactly as written: one device, 5 operating schedules, 2 occupancy states. Hill climbing → Bayesian inference → MDP. Every number is computed by the Python backend; all inputs are stated assumptions."))));

  const out = h("div", { class: "stack" });
  const start = select("start", [1, 2, 3, 4, 5].map((n) => [String(n), `Schedule ${n}`]), "1");
  const focus = select("focus", [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [String(n), `Interval ${n}`]), "5");
  const motion = select("motion", [["", "As recorded today"], ["1", "Motion detected"], ["0", "No motion"]], "");
  const run = async () => {
    try {
      const body = { start: Number(start.value), focus: Number(focus.value) };
      if (motion.value !== "") body.motion = motion.value === "1";
      out.replaceChildren(view(await api.post("/brief", body)));
    } catch (error) { out.replaceChildren(errorBox(error, "The walkthrough could not be computed.")); }
  };
  for (const el of [start, focus, motion]) el.addEventListener("change", run);
  root.append(h("section", { class: "card" },
    h("h2", {}, "Change the inputs"),
    h("div", { class: "form-grid" },
      field("Hill climbing starts from", start, "Any start reaches the same optimum here."),
      field("Interval for the Bayes + MDP step", focus),
      field("Sensor reading in that interval", motion))));
  root.append(out);
  await run();
}

function view(d) {
  const a = d.assumptions;
  const cur = a.currency;
  const o = d.output;
  const hc = d.hill_climbing;
  const b = d.bayes;
  const m = d.mdp;
  const best = d.candidates[o.best_schedule - 1];

  const result = h("div", { class: "kpis" },
    kpi("Best schedule", `#${o.best_schedule} · ${o.best_schedule_times}`, `expected cost ${fmt.num(best.total, 4)} ${cur}`, "good"),
    kpi("Occupancy estimate", fmt.num(o.occupancy_estimate, 3), `interval ${b.interval} (${b.time}), ${b.motion ? "motion" : "no motion"}`),
    kpi("Action (one-step MDP)", o.action, `planner H = 4: ${m.planner.action}`, o.action === "Keep On" ? "good" : ""));

  const assumptions = h("details", { class: "card prose" },
    h("summary", {}, "Inputs and assumptions"),
    h("ul", {},
      h("li", {}, `${a.device.name}, ${a.device.power_w} W; ${a.intervals} intervals × ${a.interval_minutes} min from ${a.start_time}; tariff ${a.tariff} ${cur}/kWh.`),
      h("li", {}, `Energy cost of one ON interval = ${a.device.power_w / 1000} kW × ${a.interval_minutes / 60} h × ${a.tariff} = ${fmt.num(a.costs.energy, 3)} ${cur}.`),
      h("li", {}, `Discomfort of OFF while someone is present = ${a.comfort_per_hour} ${cur}/h × ${a.interval_minutes / 60} h = ${fmt.num(a.costs.comfort, 3)} ${cur}; start-up = ${a.startup_cost} ${cur}.`),
      h("li", {}, `Sensor: P(motion | occupied) = ${a.motion_if_occupied}, P(motion | empty) = ${a.motion_if_empty}. Transitions: stay occupied ${a.stay_occupied}, become occupied ${a.become_occupied}.`),
      h("li", {}, `Priors P(occupied) per interval: ${a.priors.join(", ")}.`),
      h("li", {}, `Today's readings: ${a.readings.map((r) => (r ? "M" : "–")).join(" ")}  ·  true occupancy (scoring only): ${a.truth.map((r) => (r ? "O" : "–")).join(" ")}.`)));

  const hill = h("section", { class: "card" },
    h("h2", {}, "1 · Hill climbing: the lowest-cost of 5 operating schedules"),
    h("p", { class: "muted small" }, "cost = Σ ON intervals × energy + Σ OFF intervals × P(occupied) × discomfort + start-up × starts. Neighbours = adjacent candidates (one interval added or removed)."),
    tableWrap(["#", "Times", "Intervals", th("Energy", "num"), th("Discomfort", "num"), th("Start-up", "num"), th("Total", "num"), ""],
      d.candidates.map((c) => h("tr", {},
        td(String(c.number)), td(c.times), td(c.intervals.join(", ")),
        td(fmt.num(c.energy, 4), "num"), td(fmt.num(c.discomfort, 4), "num"), td(fmt.num(c.startup, 4), "num"),
        td(h("strong", {}, fmt.num(c.total, 4)), "num"),
        td(c.number === o.best_schedule ? tag("best", "on") : hc.path.includes(c.number) ? tag("visited", "info") : "")))),
    h("ol", { class: "small" }, hc.steps.map((s) => h("li", {}, `At schedule ${s.at}: `, s.explanation))),
    h("p", {}, h("strong", {}, "Output: "), `schedule ${hc.best} (path ${hc.path.join(" → ")}, ${hc.evaluations} cost evaluations). Exhaustive check over all 5 candidates also gives ${hc.exhaustive_best}${hc.is_global_optimum ? ", so this local optimum is the global one." : " — the search stopped in a local optimum."}`),
    h("p", { class: "muted small" }, "Why: each move keeps a strictly cheaper neighbour, so the search stops where adding or removing one interval no longer lowers the expected cost."));

  const bayes = h("section", { class: "card" },
    h("h2", {}, "2 · Bayesian inference: is the room occupied?"),
    tableWrap(["Step", "Calculation", th("Result", "num")], [
      h("tr", {}, td("Input"), td(`interval ${b.interval} (${b.time}), prior ${fmt.num(b.prior, 2)}, reading: ${b.motion ? "motion" : "no motion"}`), td("")),
      h("tr", {}, td("P(reading)"), td(`${fmt.num(b.likelihood_occupied, 2)} × ${fmt.num(b.prior, 2)} + ${fmt.num(b.likelihood_empty, 2)} × ${fmt.num(1 - b.prior, 2)}`), td(fmt.num(b.evidence, 4), "num")),
      h("tr", {}, td("P(occupied | reading)"), td(`${fmt.num(b.likelihood_occupied * b.prior, 4)} ÷ ${fmt.num(b.evidence, 4)}`), td(h("strong", {}, fmt.num(b.posterior, 4)), "num")),
      h("tr", {}, td("P(occupied during the interval)"), td(`${fmt.num(b.posterior, 4)} × ${a.stay_occupied} + ${fmt.num(1 - b.posterior, 4)} × ${a.become_occupied}`), td(fmt.num(b.predicted, 4), "num")),
    ]),
    h("p", { class: "muted small" }, b.motion
      ? "Why: motion is 4.5 times more likely when someone is present than when the room is empty, so the belief rises sharply."
      : "Why: the sensor misses a still person 10% of the time, so “no motion” lowers the belief but does not make it zero."));

  const mdp = h("section", { class: "card" },
    h("h2", {}, "3 · MDP: Keep On or Turn Off (2 states × 2 actions)"),
    h("div", { class: "grid-2" },
      tableWrap(["Reward R(s, a)", th("occupied", "num"), th("empty", "num")], m.actions.map((name) =>
        h("tr", {}, td(name), td(fmt.num(m.rewards[name].occupied, 3), "num"), td(fmt.num(m.rewards[name].empty, 3), "num")))),
      tableWrap(["Transition", th("→ occupied", "num"), th("→ empty", "num")], m.states.map((s) =>
        h("tr", {}, td(s), td(fmt.num(m.transitions[s].occupied, 2), "num"), td(fmt.num(m.transitions[s].empty, 2), "num"))))),
    tableWrap(["Method", th("Q(Keep On)", "num"), th("Q(Turn Off)", "num"), "Decision"], [
      h("tr", {}, td(`One-step expected reward, P(occ) = ${fmt.num(m.belief, 4)}`), td(fmt.num(m.q["Keep On"], 4), "num"), td(fmt.num(m.q["Turn Off"], 4), "num"), td(ACTION_TAG(m.action))),
      h("tr", {}, td(`Application planner: value iteration H = ${m.planner.horizon}, start-up ${m.planner.startup_cost} ${cur}, fan was ${m.planner.was_on ? "ON" : "OFF"}`), td(fmt.num(m.planner.q["Keep On"], 4), "num"), td(fmt.num(m.planner.q["Turn Off"], 4), "num"), td(ACTION_TAG(m.planner.action))),
    ]),
    h("p", { class: "muted small" }, `Why: Keep On wins when P(occupied) ≥ energy ÷ discomfort = ${fmt.num(m.break_even, 2)}. `
      + (m.action !== m.planner.action ? "The planner disagrees because switching off now would probably mean paying the start-up cost again soon." : "Here the planner agrees with the one-step rule.")));

  const labels = { schedule: "Schedule only", one_step: "AI, one-step MDP", planner: "AI, planner H = 4" };
  const totals = d.evaluation.totals;
  const bestCost = Math.min(...Object.values(totals).map((t) => t.cost));
  const evaluation = h("section", { class: "card" },
    h("h2", {}, "Result: the same evening three ways"),
    h("p", { class: "muted small" }, "Same readings, same chosen schedule. The true occupancy is used only for scoring, never for deciding."),
    tableWrap(["Strategy", th("Energy", "num"), th("Starts", "num"), th("Occupied but OFF", "num"), th("ON while empty", "num"), th(`Total cost, ${cur}`, "num")],
      Object.entries(totals).map(([key, t]) => h("tr", {},
        td(labels[key]), td(`${fmt.num(t.wh, 0)} Wh`, "num"), td(String(t.starts), "num"),
        td(fmt.minutes(t.missed_min), "num"), td(fmt.minutes(t.wasted_min), "num"),
        td(t.cost === bestCost ? h("strong", {}, fmt.num(t.cost, 3)) : fmt.num(t.cost, 3), "num")))),
    tableWrap(["Interval", "Motion", "Truth", th("P(occ)", "num"), "Schedule", "One-step", "Planner"],
      d.evaluation.rows.map((r) => h("tr", {},
        td(`${r.interval} · ${r.time}`), td(r.motion ? "yes" : "—"), td(r.truth ? "occupied" : "empty"),
        td(fmt.num(r.belief, 3), "num"), td(ACTION_TAG(r.schedule_action)), td(ACTION_TAG(r.one_step_action)), td(ACTION_TAG(r.planner_action))))),
    h("p", { class: "muted small" }, "Total cost = electricity + start-ups + discomfort (occupied minutes without the fan × comfort value). The full app applies the same methods to many rooms and devices over 24-hour schedules: see Analytics."));

  return h("div", { class: "stack" }, result, assumptions, hill, bayes, mdp, evaluation);
}
