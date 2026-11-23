// Schedule optimizer: hill climbing over 24-hour schedules for one device,
// compared with the exact optimum (dynamic programming).
import { api } from "../api.js";
import { barChart, legend, lineChart } from "../charts.js";
import { busy, empty, errorBox, field, fmt, h, hourAxis, hourStrip, scheduleText, select, tableWrap, td, th, toast } from "../ui.js";

export async function render(root, ctx) {
  const devices = await api.get("/devices");
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Schedule optimizer (hill climbing)"),
      h("p", {}, "Searches for the daily schedule with the lowest expected cost for one device, using the hour-of-day occupancy probabilities learned from the room’s readings."))));
  if (!devices.length) {
    root.append(h("div", { class: "card" }, empty("No devices", "Add a device first.", h("a", { class: "btn primary", href: "#/home" }, "Rooms & devices"))));
    return;
  }
  const chosen = ctx.params.get("device") || devices[0].id;
  const output = h("div", { class: "stack" });
  const form = h("form", { class: "form-grid" },
    field("Device", select("device_id", devices.map((d) => [d.id, `${d.name} (${d.room_name})`]), chosen)),
    field("Random restarts", h("input", { name: "restarts", type: "number", min: 0, max: 50, value: 5 }), "Extra random starting schedules"),
    field("Seed", h("input", { name: "seed", type: "number", min: 0, value: 42 }), "Same seed → same result"),
    h("div", {}, h("button", { class: "btn primary", type: "submit" }, "Run hill climbing")));
  root.append(h("section", { class: "card" },
    h("details", {}, h("summary", { class: "small" }, "What is optimised?"),
      h("div", { class: "prose small", style: "margin-top:8px" },
        h("div", { class: "formula" }, "cost(s) = Σh [ s_h · energy_cost_h + (1 − s_h) · P(occupied at h) · comfort_value ]\n        + start-up cost × number of OFF→ON switches"),
        h("p", {}, "State: 24 hourly ON/OFF slots. Neighbours: schedules that differ in exactly one hour. Move: to the cheapest neighbour if it is strictly cheaper. Stop: no neighbour is cheaper (local optimum). Restarts from random schedules reduce the risk of a poor local optimum; the exact optimum from dynamic programming shows how good the result really is."))),
    form), output);

  const run = async (button) => {
    output.replaceChildren();
    const values = Object.fromEntries(new FormData(form));
    try {
      const data = await busy(button, "Searching…", () => api.post("/optimize", {
        device_id: Number(values.device_id), restarts: Number(values.restarts), seed: Number(values.seed),
      }));
      output.append(...result(data, ctx));
    } catch (error) { output.append(errorBox(error)); }
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); run(form.querySelector("button[type=submit]")); });
  run(form.querySelector("button[type=submit]"));
}

function result(data, ctx) {
  const cur = data.currency;
  const p = data.parameters;
  const blocks = [];
  if (data.warning) blocks.push(h("div", { class: "banner demo" }, h("strong", {}, "Limited history. "), data.warning));

  const priorsChart = barChart({
    labels: data.priors.map((x) => String(x.hour)),
    series: [{ name: "P(occupied)", values: data.priors.map((x) => x.prior), cls: (i) => (data.priors[i].source === "learned" ? "s-learned" : "s-default") }],
    max: 1, height: 190, labelEvery: 2, ariaLabel: "Hour-of-day occupancy prior",
    refLine: data.break_even !== null && data.break_even <= 1 ? { value: data.break_even, label: `break-even ${fmt.num(data.break_even)}` } : null,
  });
  blocks.push(h("section", { class: "card" },
    h("h2", {}, `Occupancy by hour — ${data.device.room_name}`),
    h("p", { class: "muted small" }, `Learned from motion readings (${data.learned_hours}/24 hours with enough data). Above the dashed line, running the device for that hour costs less than the expected discomfort of leaving it off (ignoring start-up cost).`),
    priorsChart, legend([["learned from readings", "var(--info)"], ["default prior (too few readings)", "var(--border-strong)"], ["break-even probability", "var(--warn)"]])));

  const rowsSchedule = [
    ["Current schedule", data.current],
    [`Hill climbing (best: ${data.best.label})`, data.best],
    ["Exact optimum (dynamic programming)", data.exact],
  ];
  const verdict = data.found_exact
    ? "Hill climbing found the exact optimum."
    : `Hill climbing stopped ${fmt.num(data.gap_to_exact)} ${cur}/day above the exact optimum (local optimum).`;
  const saving = data.current.total - data.best.total;
  const apply = h("button", { class: "btn primary", disabled: Math.abs(saving) < 1e-9 }, "Apply hill-climbing schedule");
  const applyMsg = h("div");
  apply.addEventListener("click", async () => {
    try {
      await busy(apply, "Applying…", () => api.put(`/devices/${data.device.id}/schedule`, { schedule: data.best.schedule, optimization_id: data.optimization_id }));
      toast(`New schedule saved for ${data.device.name}`);
      applyMsg.replaceChildren(h("div", { class: "banner virtual" }, "Saved. Future readings use the new schedule. Use Analytics → “Compare strategies” to replay stored readings with it."));
    } catch (error) { applyMsg.replaceChildren(errorBox(error)); }
  });
  blocks.push(h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", {}, "Schedules compared"), h("strong", {}, verdict)),
    h("div", { class: "stack" }, rowsSchedule.map(([label, s]) => h("div", {},
      h("div", { class: "row small" }, h("strong", {}, label), h("span", { class: "muted" }, scheduleText(s.schedule)), h("span", { class: "spacer" }),
        h("span", {}, `${fmt.num(s.total)} ${cur}/day`)),
      hourStrip(s.schedule, label)))), hourAxis(),
    h("div", { style: "margin-top:12px" }, tableWrap(
      ["Schedule", th(`Energy (${cur})`, "num"), th(`Expected discomfort (${cur})`, "num"), th("Starts", "num"), th(`Start-up (${cur})`, "num"), th(`Total (${cur}/day)`, "num")],
      rowsSchedule.map(([label, s]) => h("tr", {}, td(label), td(fmt.num(s.energy), "num"), td(fmt.num(s.discomfort), "num"),
        td(String(s.starts), "num"), td(fmt.num(s.startup), "num"), td(h("strong", {}, fmt.num(s.total)), "num"))))),
    h("p", { class: "small muted", style: "margin-top:8px" },
      `Parameters: energy ${fmt.num(p.energy_cost_h)} ${cur} per ON hour, comfort value ${fmt.num(p.comfort_cost_h)} ${cur}/h, start-up ${fmt.num(p.startup_cost)} ${cur}. `
      + `Expected change vs current: ${saving >= 0 ? "−" : "+"}${fmt.num(Math.abs(saving))} ${cur}/day (model estimate, not a measurement).`),
    h("div", { class: "row", style: "margin-top:8px" }, apply), applyMsg));

  const best = data.runs.find((run) => run.label === data.best.label);
  blocks.push(h("section", { class: "card" },
    h("h2", {}, "Search runs"),
    h("p", { class: "muted small" }, `${data.runs.length} starts, ${data.distinct_local_optima} distinct local optimum/optima, ${data.evaluations} cost evaluations in total.`),
    tableWrap(["Start", th("Start cost", "num"), th("Final cost", "num"), th("Moves", "num"), "Stopped because"],
      data.runs.map((run) => h("tr", {}, td(run.label), td(fmt.num(run.start_cost), "num"), td(fmt.num(run.final_cost), "num"),
        td(String(run.iterations), "num"), td(run.stop_reason === "local_optimum" ? "no single-hour change is cheaper" : "iteration limit")))),
    h("h3", { style: "margin-top:14px" }, `Trace of the best run (${best.label})`),
    best.steps.length > 1 ? lineChart({ values: best.steps.map((s) => s.cost), unit: cur, xLabel: "iteration", ariaLabel: "Cost per iteration" }) : h("p", { class: "muted small" }, "The start was already a local optimum."),
    h("ol", { class: "small" }, best.steps.slice(1).map((s) => h("li", {},
      `Switch ${fmt.hourRange(s.flipped_hour)} ${s.now_on ? "ON" : "OFF"}: cost ${fmt.num(s.cost)} ${cur} (−${fmt.num(s.improvement)})`)))));
  return blocks;
}

