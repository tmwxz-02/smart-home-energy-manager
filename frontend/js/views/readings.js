// Readings: manual entry, CSV import (with sample files) and the stored list.
import { api, downloadUrl, qs } from "../api.js";
import { actionTag, busy, empty, errorBox, field, fmt, formValues, h, select, tableWrap, tag, td, th, toast } from "../ui.js";

const PAGE = 50;

export async function render(root, ctx) {
  const rooms = await api.get("/rooms");
  const settings = ctx.meta.settings;
  const interval = settings.interval_minutes;

  root.append(h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Readings"),
      h("p", {}, `A reading is one motion-sensor observation for a room at the start of a ${interval}-minute interval. `
        + "Each new reading immediately runs the AI for every device in that room and stores the decisions."))));

  if (!rooms.length) {
    root.append(h("div", { class: "card" }, empty("Add a room first", "Readings belong to rooms.", h("a", { class: "btn primary", href: "#/home" }, "Rooms & devices"))));
    return;
  }

  root.append(h("div", { class: "grid-2" }, manualForm(rooms, interval, ctx), importCard(ctx)));
  root.append(await readingsTable(rooms, ctx));
}

function nowRounded(interval) {
  const now = new Date();
  now.setSeconds(0, 0);
  now.setMinutes(now.getMinutes() - (now.getMinutes() % interval));
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function manualForm(rooms, interval, ctx) {
  const result = h("div");
  const form = h("form", { class: "form", novalidate: true },
    h("div", { class: "form-grid" },
      field("Room", select("room_id", rooms.map((r) => [r.id, r.name]), ctx.params.get("room") || rooms[0].id)),
      field("Interval start", h("input", { name: "ts", type: "datetime-local", step: interval * 60, value: nowRounded(interval), required: true }),
        `Local time; minutes must be a multiple of ${interval}`)),
    h("fieldset", {}, h("legend", {}, "Motion sensor"),
      h("label", { class: "choice" }, h("input", { type: "radio", name: "motion", value: "1", checked: true }), "Motion detected"),
      h("label", { class: "choice" }, h("input", { type: "radio", name: "motion", value: "0" }), "No motion")),
    field("Was someone actually there? (optional label)", select("occupied", [["", "Unknown — don't evaluate comfort"], ["1", "Yes, occupied"], ["0", "No, empty"]], ""),
      "Labels are never shown to the AI; they are only used to evaluate comfort."),
    h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit" }, "Save reading and run AI")),
    result);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    result.replaceChildren();
    const values = formValues(form);
    const body = {
      room_id: Number(values.room_id), ts: values.ts, motion: values.motion === "1",
      occupied: values.occupied === "" ? null : values.occupied === "1",
    };
    try {
      const data = await busy(form.querySelector("button[type=submit]"), "Running AI…", () => api.post("/readings", body));
      toast("Reading stored and decisions saved");
      result.append(decisionResult(data, ctx));
    } catch (error) { result.append(errorBox(error)); }
  });
  return h("section", { class: "card" }, h("h2", {}, "Enter a reading"), form);
}

function decisionResult(data, ctx) {
  const r = data.reading;
  const box = h("div", { class: "banner virtual", role: "status" },
    h("strong", {}, `Stored: ${fmt.ts(r.ts)}, ${r.motion ? "motion" : "no motion"}. `),
    `Prior ${fmt.prob(r.prior)} (${r.prior_source}) → posterior ${fmt.prob(r.posterior)} → P(occupied during interval) ${fmt.prob(r.predicted)}.`);
  if (!data.decisions.length) {
    box.append(h("div", {}, "This room has no active devices, so no device decision was made."));
  } else {
    box.append(h("ul", {}, data.decisions.map((d) => h("li", {},
      h("strong", {}, d.device_name), " → ", actionTag(d.action), " ",
      d.mode === "manual" ? tag("manual", "warn") : null, " ",
      h("span", { class: "small" }, d.explanation)))));
    box.append(h("div", { class: "row", style: "margin-top:6px" },
      h("a", { href: "#/decisions" }, "See in AI decisions →"), h("button", { class: "btn small", onclick: () => ctx.rerender() }, "Refresh list")));
  }
  return box;
}

function importCard(ctx) {
  const result = h("div");
  const fileInput = h("input", { type: "file", accept: ".csv,text/csv", "aria-label": "CSV file" });
  const button = h("button", { class: "btn primary", type: "button" }, "Import CSV");
  button.addEventListener("click", async () => {
    result.replaceChildren();
    const file = fileInput.files[0];
    if (!file) { result.append(errorBox({ message: "Choose a CSV file first." })); return; }
    if (file.size > 2 * 1024 * 1024) { result.append(errorBox({ message: "The file is larger than 2 MB." })); return; }
    try {
      const content = await file.text();
      const data = await busy(button, "Importing…", () => api.post("/readings/import", { filename: file.name, content }));
      toast(`${data.rows} readings imported`);
      result.append(h("div", { class: "banner virtual", role: "status" },
        h("strong", {}, `Imported ${data.rows} readings from ${data.filename}. `),
        `${data.rooms} room(s), ${fmt.ts(data.from)} – ${fmt.ts(data.to)}, ${data.labelled} with occupancy labels. `,
        `The AI made ${data.decisions} device decisions (${data.ai_on} ON, ${data.ai_off} OFF).`,
        h("div", { class: "row", style: "margin-top:6px" }, h("button", { class: "btn small", onclick: () => ctx.rerender() }, "Refresh list"),
          h("a", { href: "#/analytics" }, "Open analytics →"))));
      fileInput.value = "";
    } catch (error) { result.append(errorBox(error, "Import failed — nothing was stored.")); }
  });
  return h("section", { class: "card" }, h("h2", {}, "Import readings from CSV"),
    h("div", { class: "form" },
      h("p", { class: "small" }, "Columns: ", h("code", {}, "timestamp,room,motion,occupied"),
        ". Timestamp ", h("code", {}, "YYYY-MM-DD HH:MM"), "; room must already exist; motion 1/0; occupied is optional (1/0/empty)."),
      h("p", { class: "small muted" }, "The import is all-or-nothing: if any line is invalid nothing is stored and every problem is listed with its line number."),
      h("div", { class: "row" },
        h("a", { class: "btn small", href: downloadUrl("/readings/sample.csv"), download: "readings_example.csv" }, "Download example file"),
        h("a", { class: "btn small", href: downloadUrl("/readings/sample.csv", { errors: 1 }), download: "readings_with_errors.csv" }, "Example with errors")),
      h("p", { class: "small muted" }, "The example uses rooms “Living room” and “Bedroom”; create them first."),
      fileInput, h("div", { class: "row" }, button), result));
}

async function readingsTable(rooms, ctx) {
  const card = h("section", { class: "card" });
  const filters = { room: ctx.params.get("room") || "", from: ctx.params.get("from") || "", to: ctx.params.get("to") || "", source: ctx.params.get("source") || "" };
  const offset = Number(ctx.params.get("offset") || 0);
  const form = h("form", { class: "form-grid" },
    field("Room", select("room", [["", "All rooms"], ...rooms.map((r) => [r.id, r.name])], filters.room)),
    field("From", h("input", { type: "date", name: "from", value: filters.from })),
    field("To", h("input", { type: "date", name: "to", value: filters.to })),
    field("Source", select("source", [["", "All"], ["manual", "Manual entry"], ["csv", "CSV import"], ["demo", "Demo (synthetic)"]], filters.source)),
    h("div", {}, h("button", { class: "btn", type: "submit" }, "Filter")));
  form.addEventListener("submit", (event) => { event.preventDefault(); ctx.navigate("readings", formValues(form)); });
  const data = await api.get(`/readings${qs({ ...filters, limit: PAGE, offset })}`);
  card.append(h("div", { class: "card-head" }, h("h2", {}, "Stored readings"), h("span", { class: "muted small" }, `${data.total} total`)), form);
  if (!data.items.length) {
    card.append(empty("No readings match", "Enter a reading or import a CSV file."));
    return card;
  }
  card.append(h("div", { style: "margin-top:12px" }, tableWrap(
    ["Time", "Room", "Motion", th("Label", "hide-sm"), th("Prior", "num"), th("Posterior", "num"), th("P(occ.) interval", "num"), th("Source", "hide-sm")],
    data.items.map((r) => h("tr", {},
      td(h("span", { class: "mono" }, fmt.ts(r.ts))), td(r.room_name), td(r.motion ? "motion" : "none"),
      td(r.occupied === null ? h("span", { class: "muted" }, "—") : r.occupied ? "occupied" : "empty", "hide-sm"),
      td(fmt.prob(r.prior), "num"), td(fmt.prob(r.posterior), "num"), td(fmt.prob(r.predicted), "num"),
      td(tag(r.source === "demo" ? "synthetic" : r.source, r.source === "demo" ? "warn" : ""), "hide-sm"))))));
  card.append(pager(data.total, offset, PAGE, (next) => ctx.navigate("readings", { ...filters, offset: next })));
  return card;
}

export function pager(total, offset, size, go) {
  if (total <= size) return null;
  const page = Math.floor(offset / size) + 1;
  const pages = Math.ceil(total / size);
  return h("div", { class: "row", style: "margin-top:10px" },
    h("button", { class: "btn small", disabled: offset === 0, onclick: () => go(Math.max(0, offset - size)) }, "← Newer"),
    h("span", { class: "muted small" }, `Page ${page} of ${pages}`),
    h("button", { class: "btn small", disabled: offset + size >= total, onclick: () => go(offset + size) }, "Older →"));
}
