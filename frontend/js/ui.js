// DOM helpers, formatting and shared UI states (loading, empty, error, toast).

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "value") el.value = value;
    else if (key === "checked" || key === "selected" || key === "disabled") el[key] = Boolean(value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function svg(tag, attrs = {}, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

// ---------------------------------------------------------------- formatting
export const fmt = {
  num(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  },
  kwh(value) { return `${fmt.num(value, value !== null && Math.abs(value) < 10 ? 3 : 2)} kWh`; },
  money(value, currency) { return `${fmt.num(value, 2)} ${currency || ""}`.trim(); },
  pct(value) { return value === null || value === undefined ? "—" : `${fmt.num(value, 1)}%`; },
  prob(value) { return value === null || value === undefined ? "—" : Number(value).toFixed(2); },
  ts(value) { return value ? value.replace("T", " ") : "—"; },
  minutes(value) {
    if (value === null || value === undefined) return "—";
    if (value < 60) return `${value} min`;
    return `${fmt.num(value / 60, 1)} h`;
  },
  hourRange(hour) { return `${String(hour).padStart(2, "0")}:00–${String((hour + 1) % 24).padStart(2, "0")}:00`; },
};

// Compact text of a 24-hour schedule, e.g. "08–12, 17–23".
export function scheduleText(schedule) {
  const blocks = [];
  let start = null;
  for (let hour = 0; hour <= 24; hour += 1) {
    const on = hour < 24 && schedule[hour];
    if (on && start === null) start = hour;
    if (!on && start !== null) { blocks.push([start, hour]); start = null; }
  }
  if (!blocks.length) return "never";
  if (blocks.length === 1 && blocks[0][0] === 0 && blocks[0][1] === 24) return "all day";
  return blocks.map(([a, b]) => `${String(a).padStart(2, "0")}–${String(b).padStart(2, "0")}`).join(", ");
}

// ---------------------------------------------------------------- states
export function loading(text = "Loading…") {
  return h("div", { class: "loading", role: "status" }, h("span", { class: "spinner", "aria-hidden": "true" }), text);
}

export function empty(title, text, ...actions) {
  return h("div", { class: "empty" }, h("strong", {}, title), text ? h("p", {}, text) : null,
    actions.length ? h("div", { class: "row" }, actions) : null);
}

export function errorBox(error, title) {
  const details = error?.details || [];
  return h("div", { class: "banner error", role: "alert" },
    h("strong", {}, title || error?.message || String(error)),
    title && error?.message ? h("div", {}, error.message) : null,
    details.length ? h("ul", {}, details.map((line) => h("li", {}, line))) : null);
}

export function toast(message, kind = "info") {
  const box = document.getElementById("toasts");
  const item = h("div", { class: `toast ${kind === "error" ? "error" : ""}` }, message);
  box.append(item);
  setTimeout(() => item.remove(), kind === "error" ? 6000 : 3500);
}

export function tag(text, kind = "") {
  return h("span", { class: `tag ${kind}` }, text);
}

export function actionTag(action) {
  return tag(action, action === "ON" ? "on" : "off");
}

export function kpi(label, value, sub, kind = "") {
  return h("div", { class: `kpi ${kind}` }, h("div", { class: "label" }, label),
    h("div", { class: "value" }, value), sub ? h("div", { class: "sub" }, sub) : null);
}

export function field(label, control, hint) {
  return h("label", { class: "field" }, label, control, hint ? h("span", { class: "hint" }, hint) : null);
}

export function tableWrap(headers, rowsEls) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, headers.map((head) => (head instanceof Node ? head : h("th", {}, head))))),
    h("tbody", {}, rowsEls)));
}

export function th(text, cls = "") { return h("th", { class: cls }, text); }
export function td(content, cls = "") { return h("td", { class: cls }, content); }

// Run an async action on a button: disable it and show progress text.
export async function busy(button, text, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = text;
  try {
    return await action();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

// Read a form into an object (only named controls).
export function formValues(form) {
  const values = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === "radio") { if (element.checked) values[element.name] = element.value; continue; }
    if (element.type === "checkbox") { values[element.name] = element.checked; continue; }
    values[element.name] = element.value;
  }
  return values;
}

export function select(name, options, value, attrs = {}) {
  return h("select", { name, ...attrs },
    options.map(([optionValue, label]) => h("option", { value: optionValue, selected: String(optionValue) === String(value ?? "") }, label)));
}

// Hour strip (read-only) for a 24-value schedule.
export function hourStrip(schedule, title) {
  return h("div", { class: "hours strip", role: "img", "aria-label": `${title || "Schedule"}: ${scheduleText(schedule)}` },
    schedule.map((on, hour) => h("span", { class: on ? "on" : "", title: `${fmt.hourRange(hour)}: ${on ? "ON" : "OFF"}` })));
}

export function hourAxis() {
  return h("div", { class: "hour-axis", "aria-hidden": "true" },
    Array.from({ length: 24 }, (_, hour) => h("span", {}, String(hour))));
}
