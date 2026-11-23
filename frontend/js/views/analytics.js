// Analytics for a chosen period: estimated kWh, cost at a configurable tariff,
// AI vs schedule, comfort (only with labels), strategy replay and CSV export.
import { api, downloadUrl, qs } from "../api.js";
import { barChart, legend } from "../charts.js";
import { busy, empty, errorBox, field, fmt, formValues, h, kpi, select, tableWrap, td, th } from "../ui.js";

export async function render(root, ctx) {
  const p = ctx.params;
  const [rooms, devices] = await Promise.all([api.get("/rooms?archived=1"), api.get("/devices?archived=1")]);
  const filters = { from: p.get("from") || "", to: p.get("to") || "", room: p.get("room") || "", device: p.get("device") || "", tariff: p.get("tariff") || "" };
  const data = await api.get(`/analytics${qs(filters)}`);
  const cur = data.currency;
  const t = data.total;

  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Analytics"),
      h("p", {}, "Compares the decisions actually stored (AI, including manual overrides) with the plain schedule on the same readings. Leave the dates empty for the whole history."))));

  const form = h("form", { class: "form-grid" },
    field("From", h("input", { type: "date", name: "from", value: filters.from })),
    field("To", h("input", { type: "date", name: "to", value: filters.to })),
    field("Room", select("room", [["", "All rooms"], ...rooms.map((r) => [r.id, r.name])], filters.room)),
    field("Device", select("device", [["", "All devices"], ...devices.map((d) => [d.id, `${d.name} (${d.room_name})`])], filters.device)),
    field(`Tariff (${cur}/kWh)`, h("input", { type: "number", name: "tariff", min: 0, step: "any", value: filters.tariff, placeholder: String(ctx.meta.settings.tariff_per_kwh) }), "Empty = value from Settings"),
    h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit" }, "Update"),
      h("a", { class: "btn", href: downloadUrl("/analytics/report.csv", filters), download: true }, "Export CSV")));
  form.addEventListener("submit", (event) => { event.preventDefault(); ctx.navigate("analytics", formValues(form)); });
  root.append(h("section", { class: "card" }, form));

  if (!t.decisions) {
    root.append(h("div", { class: "card" }, empty("No decisions in this period", "Add readings, or widen the period.",
      h("a", { class: "btn primary", href: "#/readings" }, "Readings"))));
    return;
  }

  const saved = t.saved_kwh;
  root.append(h("div", { class: "kpis" },
    kpi("AI strategy", fmt.kwh(t.ai_kwh), `${fmt.money(t.ai_cost, cur)} · estimated`),
    kpi("Schedule only", fmt.kwh(t.base_kwh), `${fmt.money(t.base_cost, cur)} · estimated`),
    kpi(saved >= 0 ? "Saving" : "Overspend", fmt.kwh(Math.abs(saved)), `${fmt.money(Math.abs(t.saved_cost), cur)} · ${fmt.pct(t.saved_pct === null ? null : Math.abs(t.saved_pct))}`, saved >= 0 ? "good" : "bad"),
    kpi("Decisions", String(t.decisions), `${t.intervals} readings · ${t.ai_skipped} scheduled runs skipped · ${t.manual} manual`),
    kpi("Device starts", `${t.ai_starts} vs ${t.base_starts}`, "AI vs schedule (OFF→ON switches)"),
  ));
  root.append(h("p", { class: "muted small" }, `${fmt.ts(t.first_ts)} – ${fmt.ts(t.last_ts)} · tariff ${data.tariff} ${cur}/kWh. ${data.energy_note}`));

  // Daily chart
  const labels = data.daily.map((d) => d.day.slice(5));
  root.append(h("section", { class: "card" }, h("h2", {}, "Estimated energy per day"),
    barChart({ labels, unit: "kWh", ariaLabel: "Energy per day, AI vs schedule",
      series: [{ name: "AI", cls: "s-ai", values: data.daily.map((d) => d.ai_kwh) }, { name: "Schedule only", cls: "s-base", values: data.daily.map((d) => d.base_kwh) }] }),
    legend([["AI (stored decisions)", "var(--accent)"], ["Schedule only", "var(--base)"]])));

  // Hourly chart
  const hours = Array.from({ length: 24 }, (_, hour) => data.hourly.find((x) => x.hour === hour) || { hour, ai_kwh: 0, base_kwh: 0 });
  root.append(h("section", { class: "card" }, h("h2", {}, "Estimated energy by hour of day (whole period)"),
    barChart({ labels: hours.map((x) => String(x.hour)), unit: "kWh", labelEvery: 2, height: 190, ariaLabel: "Energy by hour",
      series: [{ name: "AI", cls: "s-ai", values: hours.map((x) => x.ai_kwh) }, { name: "Schedule only", cls: "s-base", values: hours.map((x) => x.base_kwh) }] }),
    legend([["AI", "var(--accent)"], ["Schedule only", "var(--base)"]])));

  // Comfort
  const comfort = h("section", { class: "card" }, h("h2", {}, "Comfort trade-off"));
  if (t.labelled) {
    comfort.append(tableWrap(["", th("AI", "num"), th("Schedule only", "num")], [
      h("tr", {}, td("Occupied but device OFF (in scheduled hours)"), td(fmt.minutes(t.ai_missed_min), "num"), td(fmt.minutes(t.base_missed_min), "num")),
      h("tr", {}, td("Device ON while the room was empty"), td(fmt.minutes(t.ai_wasted_min), "num"), td(fmt.minutes(t.base_wasted_min), "num")),
    ]));
    comfort.append(h("p", { class: "muted small", style: "margin-top:8px" },
      `Minutes are device-minutes, summed over devices. Labelled scheduled time: ${fmt.minutes(t.labelled_scheduled_min)}. `
      + "Energy saving and missed comfort are reported separately: whether the saving is worth the discomfort is the user’s value judgment (set by each device’s comfort value)."));
  }
  if (data.comfort_note) comfort.append(h("div", { class: "banner demo", style: "margin-top:8px" }, data.comfort_note));
  root.append(comfort);

  // Per device
  root.append(h("section", { class: "card" }, h("h2", {}, "Per device"),
    tableWrap(["Device", th("AI kWh", "num"), th("Schedule kWh", "num"), th("Saved", "num"), th(`Saved ${cur}`, "num"), th("Skipped runs", "num hide-sm"), th("Missed (occupied)", "num hide-sm")],
      data.per_device.map((d) => h("tr", {}, td([h("strong", {}, d.device_name), h("div", { class: "muted small" }, `${d.room_name} · ${d.power_w} W`)]),
        td(fmt.num(d.ai_kwh, 3), "num"), td(fmt.num(d.base_kwh, 3), "num"), td(fmt.pct(d.saved_pct), "num"), td(fmt.num(d.saved_cost), "num"),
        td(String(d.ai_skipped), "num hide-sm"), td(fmt.minutes(d.ai_missed_min), "num hide-sm"))))));

  // Strategy replay
  const replayOut = h("div");
  const replayBtn = h("button", { class: "btn primary" }, "Compare strategies on the same readings");
  replayBtn.addEventListener("click", async () => {
    replayOut.replaceChildren();
    try {
      const result = await busy(replayBtn, "Replaying…", () => api.get(`/analytics/compare${qs(filters)}`));
      replayOut.append(compareTable(result));
    } catch (error) { replayOut.append(errorBox(error)); }
  });
  root.append(h("section", { class: "card" }, h("h2", {}, "What-if: strategy comparison"),
    h("p", { class: "muted small" }, "Replays the stored readings of this period through each strategy with the CURRENT settings and schedules. Nothing is saved. This is the fair comparison: identical inputs for every strategy."),
    h("div", { class: "row", style: "margin:10px 0" }, replayBtn), replayOut));
}

function compareTable(result) {
  if (!result.strategies.length) return h("p", { class: "muted" }, result.note);
  const cur = result.currency;
  return h("div", { class: "stack" },
    tableWrap(["Strategy", th("Energy (est.)", "num"), th(`Cost (${cur})`, "num"), th("Saved vs schedule", "num"), th("Starts", "num"),
      th("Occupied, OFF", "num"), th("ON, empty", "num")],
    result.strategies.map((s) => h("tr", {}, td(h("strong", {}, s.label)), td(fmt.kwh(s.kwh), "num"), td(fmt.num(s.cost), "num"),
      td(fmt.pct(s.saved_pct), "num"), td(String(s.starts), "num"), td(fmt.minutes(s.missed_min), "num"), td(fmt.minutes(s.wasted_min), "num")))),
    h("p", { class: "muted small" }, `${result.readings} readings, ${result.devices} devices. ${result.note}`));
}
