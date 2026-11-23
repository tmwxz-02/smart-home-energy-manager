// Settings: tariff and model parameters (stored in SQLite per workspace), demo generation.
import { api, getWorkspace } from "../api.js";
import { busy, errorBox, field, h, toast } from "../ui.js";

const GROUPS = [
  ["Tariff", "Used for cost estimates and as the price of energy in the AI's rewards.", [
    ["tariff_per_kwh", "Tariff per kWh", { type: "number", min: 0, step: "any" }],
    ["currency", "Currency label", { type: "text", maxlength: 8 }],
  ]],
  ["Time", "Length of one decision interval. Fixed once readings exist.", [
    ["interval_minutes", "Interval (minutes)", { type: "select", options: [5, 10, 15, 20, 30, 60] }],
  ]],
  ["Sensor model (Bayes)", "How reliable the motion sensor is assumed to be.", [
    ["motion_if_occupied", "P(motion | occupied)", { type: "number", min: 0.5, max: 0.999, step: 0.01 }],
    ["motion_if_empty", "P(motion | empty)", { type: "number", min: 0.001, max: 0.5, step: 0.01 }],
    ["default_prior", "Default P(occupied) with no history", { type: "number", min: 0.01, max: 0.99, step: 0.01 }],
    ["min_history_readings", "Readings per hour needed to learn a prior", { type: "number", min: 1, max: 100, step: 1 }],
  ]],
  ["Occupancy transitions (Markov chain, per interval)", "Used by the Bayesian filter and the MDP.", [
    ["stay_occupied", "P(occupied next | occupied now)", { type: "number", min: 0, max: 1, step: 0.01 }],
    ["become_occupied", "P(occupied next | empty now)", { type: "number", min: 0, max: 1, step: 0.01 }],
  ]],
  ["MDP planning", "Horizon 1 = one-step decision; larger horizons plan ahead with value iteration.", [
    ["horizon", "Horizon H (intervals)", { type: "number", min: 1, max: 24, step: 1 }],
    ["discount", "Discount γ", { type: "number", min: 0.5, max: 1, step: 0.01 }],
  ]],
];

export async function render(root, ctx) {
  const settings = await api.get("/settings");
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Settings"),
      h("p", {}, `Model assumptions for the “${getWorkspace() === "demo" ? "Demo" : "My home"}” workspace. Changes apply to NEW decisions; stored decisions keep the parameters they were made with.`))));

  const error = h("div");
  const form = h("form", { class: "stack", novalidate: true });
  for (const [title, text, fields] of GROUPS) {
    form.append(h("fieldset", {}, h("legend", {}, title), h("p", { class: "muted small", style: "margin-bottom:8px" }, text),
      h("div", { class: "form-grid" }, fields.map(([key, label, opts]) => {
        let control;
        if (opts.type === "select") {
          control = h("select", { name: key }, opts.options.map((o) => h("option", { value: o, selected: o === settings[key] }, String(o))));
        } else {
          control = h("input", { name: key, ...opts, value: settings[key] });
        }
        return field(label, control);
      }))));
  }
  form.append(error, h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit" }, "Save settings")));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.replaceChildren();
    const body = {};
    for (const element of form.elements) {
      if (!element.name) continue;
      if (element.name === "currency") body.currency = element.value;
      else body[element.name] = element.value === "" ? null : Number(element.value);
    }
    for (const key of Object.keys(body)) if (body[key] === settings[key]) delete body[key];
    if (!Object.keys(body).length) { toast("Nothing changed"); return; }
    try {
      await busy(form.querySelector("button[type=submit]"), "Saving…", () => api.put("/settings", body));
      toast("Settings saved");
      await ctx.refreshMeta();
      ctx.rerender();
    } catch (err) { error.append(errorBox(err)); }
  });
  root.append(h("section", { class: "card" }, form));

  if (getWorkspace() === "demo") root.append(demoCard(ctx));
  else {
    root.append(h("section", { class: "card" }, h("h2", {}, "Where is my data?"),
      h("p", { class: "small" }, "Everything is stored locally in ", h("code", {}, "data/home.db"),
        " (SQLite) inside the project folder. Synthetic demo data is in a separate file, ", h("code", {}, "data/demo.db"),
        ", so the two are never mixed. Copy the data folder to back it up.")));
  }
}

function demoCard(ctx) {
  const meta = ctx.meta.demo;
  const out = h("div");
  const days = h("input", { type: "number", min: 1, max: 31, value: meta?.days ?? 7, name: "days" });
  const seed = h("input", { type: "number", min: 0, value: meta?.seed ?? 42, name: "seed" });
  const button = h("button", { class: "btn primary", type: "button" }, meta ? "Regenerate demo data" : "Generate demo data");
  button.addEventListener("click", async () => {
    out.replaceChildren();
    if (meta && !confirm("This deletes everything in the demo workspace (rooms, devices, readings, decisions, demo settings) and generates it again. My home is not touched. Continue?")) return;
    try {
      const result = await busy(button, "Generating…", () => api.post("/demo/reset", { days: Number(days.value), seed: Number(seed.value) }));
      toast(`Demo generated: ${result.readings} readings, ${result.decisions} decisions`);
      await ctx.refreshMeta();
      ctx.navigate("dashboard");
    } catch (error) { out.append(errorBox(error)); }
  });
  return h("section", { class: "card" }, h("h2", {}, "Demo data (synthetic)"),
    h("p", { class: "small muted" }, "Creates 3 rooms with 7 virtual devices and synthetic occupancy + motion readings starting 2026-11-02. "
      + "The same seed always produces the same data. Every reading carries a synthetic occupancy label, so comfort can be evaluated — on invented data."),
    h("div", { class: "form-grid", style: "margin-top:10px" }, field("Days", days), field("Seed", seed), h("div", {}, button)), out);
}
