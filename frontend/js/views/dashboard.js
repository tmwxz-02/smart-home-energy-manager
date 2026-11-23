// Dashboard: totals from the stored history, virtual device control, latest AI decisions.
import { api, getWorkspace, setWorkspace } from "../api.js";
import { actionTag, busy, empty, errorBox, fmt, h, kpi, scheduleText, tag, toast } from "../ui.js";

export async function render(root, ctx) {
  const data = await api.get("/dashboard");
  const cur = data.settings.currency;
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Dashboard"),
      h("p", {}, "Overview of the stored history and the present state of every virtual device."))));

  if (!data.rooms.length) {
    const actions = [h("a", { class: "btn primary", href: "#/home" }, "Add your first room")];
    if (getWorkspace() === "home") {
      actions.push(h("button", { class: "btn", onclick: () => { setWorkspace("demo"); location.reload(); } }, "Open the demo workspace"));
    } else {
      actions.splice(0, 1, h("a", { class: "btn primary", href: "#/settings" }, "Generate demo data"));
    }
    root.append(h("div", { class: "card" }, empty("Nothing set up yet",
      "Start by adding rooms and devices, then enter readings or import a CSV file. Or explore the demo workspace with synthetic data.", ...actions)));
    return;
  }

  const t = data.totals;
  const saved = t.base_wh - t.ai_wh;
  const pct = t.base_wh > 0 ? (100 * saved) / t.base_wh : null;
  const tariff = data.settings.tariff_per_kwh;
  root.append(h("div", { class: "kpis" },
    kpi("AI strategy (estimated)", fmt.kwh(t.ai_wh / 1000), t.first_ts ? `${fmt.ts(t.first_ts).slice(0, 10)} – ${fmt.ts(t.last_ts).slice(0, 10)}` : "no decisions yet"),
    kpi("Schedule only (estimated)", fmt.kwh(t.base_wh / 1000), "same readings, same devices"),
    kpi(saved >= 0 ? "Saving vs schedule" : "Overspend vs schedule", pct === null ? fmt.kwh(Math.abs(saved) / 1000) : fmt.pct(Math.abs(pct)),
      `${fmt.kwh(Math.abs(saved) / 1000)} · ${fmt.money(Math.abs(saved) / 1000 * tariff, cur)}`, saved >= 0 ? "good" : "bad"),
    kpi("Stored data", `${data.counts.readings} readings`, `${data.counts.decisions} decisions · ${data.counts.labelled} labelled`),
  ));
  if (data.latest_day) {
    root.append(h("p", { class: "muted small" },
      `Latest day with data (${data.latest_day.date}): AI ${fmt.kwh(data.latest_day.ai_wh / 1000)}, schedule ${fmt.kwh(data.latest_day.base_wh / 1000)}. `,
      h("a", { href: "#/analytics" }, "Open analytics →")));
  }

  // Device control
  const grid = h("div", { class: "device-grid" });
  const deviceCard = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", {}, "Devices (virtual control)"),
      h("a", { class: "btn small", href: "#/home" }, "Manage")),
    data.devices.length ? grid : empty("No devices yet", "Add devices to your rooms.", h("a", { class: "btn primary", href: "#/home" }, "Add a device")));
  root.append(deviceCard);
  for (const device of data.devices) grid.append(deviceTile(device, ctx));

  // Recent decisions
  const recent = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", {}, "Latest AI decisions"),
      h("a", { class: "btn small", href: "#/decisions" }, "Full history")));
  if (!data.recent_decisions.length) {
    recent.append(empty("No decisions yet", "Decisions appear when a reading is entered or imported.",
      h("a", { class: "btn primary", href: "#/readings" }, "Add a reading")));
  } else {
    recent.append(h("div", { class: "stack" }, data.recent_decisions.map((d) =>
      h("div", { class: "row small" }, h("span", { class: "mono" }, fmt.ts(d.ts)), h("strong", {}, d.device_name),
        h("span", { class: "muted" }, d.room_name), actionTag(d.action),
        d.mode === "manual" ? tag("manual", "warn") : null,
        h("span", { class: "muted" }, `P(occupied) ${fmt.prob(d.predicted)}`)))));
  }
  root.append(recent);
}

function deviceTile(device, ctx) {
  const tile = h("div", { class: `device ${device.state === "ON" ? "is-on" : ""}` });
  const error = h("div");
  const control = async (body, button) => {
    error.replaceChildren();
    try {
      await busy(button, "…", () => api.post(`/devices/${device.id}/control`, body));
      toast(body.mode === "auto" ? `${device.name}: back to AI control` : `${device.name}: virtual device set ${body.state}`);
      ctx.rerender();
    } catch (err) {
      error.append(errorBox(err));
    }
  };
  const modeAuto = h("button", { type: "button", "aria-pressed": String(device.mode === "auto") }, "Auto (AI)");
  const modeManual = h("button", { type: "button", "aria-pressed": String(device.mode === "manual") }, "Manual");
  modeAuto.addEventListener("click", () => device.mode !== "auto" && control({ mode: "auto" }, modeAuto));
  modeManual.addEventListener("click", () => device.mode !== "manual" && control({ mode: "manual", state: device.state }, modeManual));
  const onBtn = h("button", { type: "button", "aria-pressed": String(device.mode === "manual" && device.manual_state === "ON") }, "ON");
  const offBtn = h("button", { type: "button", class: "off-btn", "aria-pressed": String(device.mode === "manual" && device.manual_state === "OFF") }, "OFF");
  onBtn.addEventListener("click", () => control({ state: "ON" }, onBtn));
  offBtn.addEventListener("click", () => control({ state: "OFF" }, offBtn));
  tile.append(
    h("div", { class: "row" }, h("span", { class: "name" }, h("span", { class: "state-dot", "aria-hidden": "true" }), device.name),
      h("span", { class: "spacer" }), tag("virtual", "info")),
    h("div", { class: "muted small" }, `${device.room_name} · ${device.power_w} W · schedule ${scheduleText(device.schedule)}`),
    h("div", { class: "small" }, "State: ", h("strong", {}, device.state), h("span", { class: "muted" }, ` (${device.state_source})`)),
    h("div", { class: "row" },
      h("div", { class: "segmented", role: "group", "aria-label": `${device.name} control mode` }, modeAuto, modeManual),
      h("div", { class: "segmented", role: "group", "aria-label": `${device.name} manual override` }, onBtn, offBtn)),
    error);
  return tile;
}
