// Rooms & devices: add, edit, archive and restore; per-device schedule editor.
import { api } from "../api.js";
import { busy, empty, errorBox, field, fmt, formValues, h, hourAxis, hourStrip, scheduleText, select, tag, toast } from "../ui.js";

export async function render(root, ctx) {
  const showArchived = ctx.params.get("archived") === "1";
  const [rooms, devices] = await Promise.all([
    api.get(`/rooms${showArchived ? "?archived=1" : ""}`),
    api.get(`/devices${showArchived ? "?archived=1" : ""}`),
  ]);
  const types = ctx.meta.device_types;
  const settings = ctx.meta.settings;

  const toggle = h("label", { class: "choice" },
    h("input", { type: "checkbox", checked: showArchived, onchange: (e) => ctx.navigate("home", e.target.checked ? { archived: 1 } : {}) }),
    "Show archived");
  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Rooms & devices"),
      h("p", {}, "Each room has one motion sensor (readings are entered or imported per room). Devices are virtual: there is no hardware connection.")),
    toggle));

  // Add room
  const roomError = h("div");
  const roomForm = h("form", { class: "row", novalidate: true },
    h("input", { name: "name", placeholder: "Room name, e.g. Kitchen", "aria-label": "New room name", maxlength: 60, style: "max-width:320px" }),
    h("button", { class: "btn primary", type: "submit" }, "Add room"));
  roomForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    roomError.replaceChildren();
    try {
      const room = await api.post("/rooms", { name: roomForm.elements.name.value });
      toast(`Room “${room.name}” added`);
      ctx.rerender();
    } catch (error) { roomError.append(errorBox(error)); }
  });
  root.append(h("section", { class: "card" }, h("h2", {}, "Add a room"), roomForm, roomError));

  // Device editor (shared for create and edit)
  const editorSlot = h("div");
  root.append(editorSlot);
  const openEditor = (device, roomId) => {
    editorSlot.replaceChildren(deviceEditor({ device, roomId, rooms: rooms.filter((r) => !r.archived), types, settings, ctx, close: () => editorSlot.replaceChildren() }));
    editorSlot.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  if (ctx.params.get("new") === "device" && rooms.some((r) => !r.archived)) openEditor(null, null);

  if (!rooms.length) {
    root.append(h("div", { class: "card" }, empty("No rooms yet", "Add a room above, then add devices to it.")));
    return;
  }
  for (const room of rooms) {
    root.append(roomCard(room, devices.filter((d) => d.room_id === room.id), openEditor, ctx, settings));
  }
}

function roomCard(room, devices, openEditor, ctx, settings) {
  const error = h("div");
  const nameInput = h("input", { value: room.name, "aria-label": "Room name", maxlength: 60, style: "max-width:260px" });
  const head = h("div", { class: "room-head" }, h("h2", {}, room.name),
    room.archived ? tag("archived", "warn") : null,
    room.last_reading ? h("span", { class: "muted small" }, `last reading ${fmt.ts(room.last_reading)}`) : h("span", { class: "muted small" }, "no readings yet"));
  const actions = h("div", { class: "row" });
  if (!room.archived) {
    actions.append(
      h("button", { class: "btn small primary", onclick: () => openEditor(null, room.id) }, "Add device"),
      h("button", { class: "btn small", onclick: () => {
        const save = h("button", { class: "btn small primary" }, "Save");
        const cancel = h("button", { class: "btn small", onclick: () => ctx.rerender() }, "Cancel");
        save.addEventListener("click", async () => {
          error.replaceChildren();
          try { await busy(save, "Saving…", () => api.put(`/rooms/${room.id}`, { name: nameInput.value })); toast("Room renamed"); ctx.rerender(); }
          catch (err) { error.append(errorBox(err)); }
        });
        head.replaceChildren(nameInput, save, cancel);
        nameInput.focus();
      } }, "Rename"),
      h("button", { class: "btn small danger", onclick: async (e) => {
        if (!confirm(`Archive “${room.name}” and its ${devices.length} device(s)? History is kept; you can restore it later.`)) return;
        try { await busy(e.target, "…", () => api.post(`/rooms/${room.id}/archive`)); toast("Room archived"); ctx.rerender(); }
        catch (err) { error.append(errorBox(err)); }
      } }, "Archive"));
  } else {
    actions.append(h("button", { class: "btn small", onclick: async (e) => {
      try { await busy(e.target, "…", () => api.post(`/rooms/${room.id}/restore`)); toast("Room restored (devices stay archived until you restore them)"); ctx.rerender(); }
      catch (err) { error.append(errorBox(err)); }
    } }, "Restore room"));
  }

  const body = devices.length
    ? h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Device"), h("th", { class: "num" }, "Power"), h("th", { class: "hide-sm" }, "Schedule"),
        h("th", { class: "hide-sm" }, "Mode"), h("th", {}, ""))),
      h("tbody", {}, devices.map((d) => h("tr", {},
        h("td", {}, h("strong", {}, d.name), " ", d.archived ? tag("archived", "warn") : null,
          h("div", { class: "muted small" }, `${d.type} · comfort ${fmt.num(d.comfort_value_per_hour)} ${settings.currency}/h · start ${fmt.num(d.startup_cost)}`)),
        h("td", { class: "num" }, `${d.power_w} W`),
        h("td", { class: "hide-sm", style: "min-width:220px" }, hourStrip(d.schedule, d.name), h("div", { class: "muted small" }, scheduleText(d.schedule))),
        h("td", { class: "hide-sm" }, tag(d.mode === "auto" ? "Auto (AI)" : `Manual ${d.manual_state}`, d.mode === "auto" ? "on" : "warn")),
        h("td", {}, h("div", { class: "row" }, d.archived
          ? h("button", { class: "btn small", onclick: async (e) => {
            try { await busy(e.target, "…", () => api.post(`/devices/${d.id}/restore`)); toast("Device restored"); ctx.rerender(); }
            catch (err) { error.append(errorBox(err)); }
          } }, "Restore")
          : [h("button", { class: "btn small", onclick: () => openEditor(d, d.room_id) }, "Edit"),
            h("a", { class: "btn small", href: `#/optimizer?device=${d.id}` }, "Optimise"),
            h("button", { class: "btn small danger", onclick: async (e) => {
              if (!confirm(`Archive “${d.name}”? Its decision history is kept.`)) return;
              try { await busy(e.target, "…", () => api.post(`/devices/${d.id}/archive`)); toast("Device archived"); ctx.rerender(); }
              catch (err) { error.append(errorBox(err)); }
            } }, "Archive")])))))))
    : h("p", { class: "muted small" }, room.archived ? "No devices." : "No devices in this room yet.");

  return h("section", { class: "card room" }, head, actions, error, body);
}

function deviceEditor({ device, roomId, rooms, types, settings, ctx, close }) {
  const isNew = !device;
  const start = device || { name: "", type: "fan", room_id: roomId ?? rooms[0]?.id, ...types.fan, schedule: Array(24).fill(0) };
  const schedule = [...start.schedule];
  const error = h("div");
  const info = h("p", { class: "muted small" });

  const form = h("form", { class: "form", novalidate: true });
  const typeSelect = select("type", Object.entries(types).map(([key, t]) => [key, t.label]), start.type);
  const power = h("input", { name: "power_w", type: "number", min: 1, max: 10000, step: "any", value: start.power_w, required: true });
  const comfort = h("input", { name: "comfort_value_per_hour", type: "number", min: 0, step: "any", value: start.comfort_value_per_hour, required: true });
  const startup = h("input", { name: "startup_cost", type: "number", min: 0, step: "any", value: start.startup_cost, required: true });
  typeSelect.addEventListener("change", () => {
    const preset = types[typeSelect.value];
    power.value = preset.power_w; comfort.value = preset.comfort_value_per_hour; startup.value = preset.startup_cost;
    updateInfo();
  });

  const hourButtons = schedule.map((on, hour) => {
    const button = h("button", { type: "button", class: on ? "on" : "", "aria-pressed": String(Boolean(on)), title: fmt.hourRange(hour) }, String(hour));
    button.addEventListener("click", () => { schedule[hour] = schedule[hour] ? 0 : 1; paint(); });
    return button;
  });
  const scheduleLabel = h("span", { class: "muted small" });
  const paint = () => {
    hourButtons.forEach((button, hour) => {
      button.classList.toggle("on", Boolean(schedule[hour]));
      button.setAttribute("aria-pressed", String(Boolean(schedule[hour])));
    });
    scheduleLabel.textContent = `ON hours: ${scheduleText(schedule)}`;
  };
  const preset = (from, to) => () => { for (let hour = 0; hour < 24; hour += 1) schedule[hour] = from <= to ? (hour >= from && hour < to ? 1 : 0) : (hour >= from || hour < to ? 1 : 0); paint(); };

  // Display-only helper: what the entered numbers mean at the current tariff.
  function updateInfo() {
    const energyPerHour = (Number(power.value) / 1000) * settings.tariff_per_kwh;
    const value = Number(comfort.value);
    info.textContent = `At ${settings.tariff_per_kwh} ${settings.currency}/kWh this device costs ${fmt.num(energyPerHour)} ${settings.currency} per hour ON. `
      + (value > 0 ? `In a single interval the AI prefers ON when P(occupied) ≥ ${fmt.num(Math.min(1, energyPerHour / value))} (energy cost ÷ comfort value).` : "With comfort value 0 the AI will always switch it off when allowed.");
  }
  power.addEventListener("input", updateInfo);
  comfort.addEventListener("input", updateInfo);

  form.append(
    h("div", { class: "form-grid" },
      field("Name", h("input", { name: "name", value: start.name, maxlength: 60, required: true, placeholder: "e.g. Desk fan" })),
      field("Room", select("room_id", rooms.map((r) => [r.id, r.name]), start.room_id)),
      field("Type", typeSelect, "Choosing a type fills typical values"),
      field("Rated power (W)", power, "From the device label"),
      field(`Comfort value (${settings.currency}/h)`, comfort, "What one hour without the device is worth when someone is present"),
      field(`Start-up cost (${settings.currency})`, startup, "Assumed cost of each OFF→ON switch")),
    info,
    h("fieldset", {}, h("legend", {}, "Schedule (hours when the device should normally run)"),
      h("div", { class: "hours", role: "group", "aria-label": "Hourly schedule" }, hourButtons),
      h("div", { class: "row", style: "margin-top:8px" }, scheduleLabel, h("span", { class: "spacer" }),
        h("button", { type: "button", class: "btn small", onclick: preset(0, 24) }, "All day"),
        h("button", { type: "button", class: "btn small", onclick: preset(8, 18) }, "08–18"),
        h("button", { type: "button", class: "btn small", onclick: preset(18, 23) }, "18–23"),
        h("button", { type: "button", class: "btn small", onclick: preset(22, 7) }, "22–07"),
        h("button", { type: "button", class: "btn small", onclick: preset(0, 0) }, "Clear"))),
    error,
    h("div", { class: "row" },
      h("button", { class: "btn primary", type: "submit" }, isNew ? "Add device" : "Save changes"),
      h("button", { class: "btn", type: "button", onclick: close }, "Cancel")));
  paint();
  updateInfo();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.replaceChildren();
    const values = formValues(form);
    const body = {
      name: values.name, type: values.type, room_id: Number(values.room_id),
      power_w: Number(values.power_w), comfort_value_per_hour: Number(values.comfort_value_per_hour),
      startup_cost: Number(values.startup_cost), schedule,
    };
    for (const key of ["power_w", "comfort_value_per_hour", "startup_cost"]) {
      if (values[key] === "" || Number.isNaN(body[key])) body[key] = null;
    }
    const submit = form.querySelector("button[type=submit]");
    try {
      await busy(submit, "Saving…", () => (isNew ? api.post("/devices", body) : api.put(`/devices/${device.id}`, body)));
      toast(isNew ? "Device added" : "Device saved");
      ctx.rerender();
    } catch (err) { error.append(errorBox(err)); }
  });

  return h("section", { class: "card" }, h("h2", {}, isNew ? "New virtual device" : `Edit ${device.name}`), form);
}
