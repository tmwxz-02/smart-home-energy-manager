// AI decision history: time, device, sensor reading, occupancy probability, action, explanation.
import { api, qs } from "../api.js";
import { actionTag, empty, field, fmt, formValues, h, select, tag } from "../ui.js";
import { pager } from "./readings.js";

const PAGE = 50;

export async function render(root, ctx) {
  const [rooms, devices] = await Promise.all([api.get("/rooms?archived=1"), api.get("/devices?archived=1")]);
  const p = ctx.params;
  const filters = { room: p.get("room") || "", device: p.get("device") || "", from: p.get("from") || "", to: p.get("to") || "", action: p.get("action") || "" };
  const offset = Number(p.get("offset") || 0);
  const data = await api.get(`/decisions${qs({ ...filters, limit: PAGE, offset })}`);
  const currency = ctx.meta.settings.currency;

  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "AI decisions"),
      h("p", {}, "Every stored decision with the sensor reading, the Bayesian occupancy estimate, the MDP values and a plain-language explanation. "
        + "“Schedule” shows what the plain schedule would have done for the same interval. Click a row for details."))));

  const form = h("form", { class: "form-grid" },
    field("Room", select("room", [["", "All rooms"], ...rooms.map((r) => [r.id, r.name])], filters.room)),
    field("Device", select("device", [["", "All devices"], ...devices.map((d) => [d.id, `${d.name} (${d.room_name})`])], filters.device)),
    field("From", h("input", { type: "date", name: "from", value: filters.from })),
    field("To", h("input", { type: "date", name: "to", value: filters.to })),
    field("Action", select("action", [["", "ON and OFF"], ["ON", "ON only"], ["OFF", "OFF only"]], filters.action)),
    h("div", {}, h("button", { class: "btn", type: "submit" }, "Filter")));
  form.addEventListener("submit", (event) => { event.preventDefault(); ctx.navigate("decisions", formValues(form)); });

  const card = h("section", { class: "card" }, form);
  root.append(card);
  if (!data.items.length) {
    card.append(empty("No decisions match", "Decisions are created when readings are entered or imported.",
      h("a", { class: "btn primary", href: "#/readings" }, "Add readings")));
    return;
  }
  card.append(h("p", { class: "muted small", style: "margin:10px 0" }, `${data.total} decisions`));
  const tbody = h("tbody");
  for (const d of data.items) {
    const detail = h("tr", { class: "detail", hidden: true }, h("td", { colspan: 8 },
      h("div", { class: "explain" }, d.explanation),
      h("div", { class: "muted small", style: "margin-top:6px" },
        `Mode: ${d.mode}. Previous state: ${d.previous_state}. `,
        d.q_on !== null ? `Q(ON) = ${fmt.num(d.q_on)} ${currency}, Q(OFF) = ${fmt.num(d.q_off)} ${currency}, horizon ${d.horizon}. ` : "",
        `Estimated energy: AI ${fmt.num(d.energy_wh, 1)} Wh vs schedule ${fmt.num(d.baseline_energy_wh, 1)} Wh. `,
        d.occupied === null ? "No occupancy label." : `Label: ${d.occupied ? "occupied" : "empty"} (used only for evaluation).`)));
    const row = h("tr", { class: "expandable", tabindex: 0, "aria-expanded": "false" },
      h("td", {}, h("span", { class: "mono" }, fmt.ts(d.ts))),
      h("td", {}, h("strong", {}, d.device_name), h("div", { class: "muted small" }, d.room_name)),
      h("td", { class: "hide-sm" }, d.motion ? "motion" : "none"),
      h("td", { class: "num" }, fmt.prob(d.posterior)),
      h("td", { class: "num hide-sm" }, fmt.prob(d.predicted)),
      h("td", {}, actionTag(d.action), d.mode === "manual" ? [" ", tag("manual", "warn")] : null),
      h("td", { class: "hide-sm" }, d.scheduled ? actionTag(d.baseline_action) : h("span", { class: "muted small" }, "off-schedule")),
      h("td", { class: "hide-sm small", style: "max-width:380px" }, d.explanation.length > 110 ? `${d.explanation.slice(0, 110)}…` : d.explanation));
    const toggle = () => {
      detail.hidden = !detail.hidden;
      row.setAttribute("aria-expanded", String(!detail.hidden));
    };
    row.addEventListener("click", toggle);
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); } });
    tbody.append(row, detail);
  }
  card.append(h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Time"), h("th", {}, "Device"), h("th", { class: "hide-sm" }, "Sensor"),
      h("th", { class: "num" }, "P(occ.) now"), h("th", { class: "num hide-sm" }, "P(occ.) interval"),
      h("th", {}, "AI action"), h("th", { class: "hide-sm" }, "Schedule"), h("th", { class: "hide-sm" }, "Explanation"))),
    tbody)));
  card.append(pager(data.total, offset, PAGE, (next) => ctx.navigate("decisions", { ...filters, offset: next })));
}
