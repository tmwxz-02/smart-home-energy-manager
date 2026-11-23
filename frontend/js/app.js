// Entry point: hash router, workspace switch, banners, mobile navigation.
// Every number shown comes from the Python backend; the browser only displays it.
import { api, getWorkspace, hasStoredWorkspace, setWorkspace } from "./api.js";
import { clear, errorBox, h, loading } from "./ui.js";
import * as dashboard from "./views/dashboard.js";
import * as home from "./views/home.js";
import * as readings from "./views/readings.js";
import * as decisions from "./views/decisions.js";
import * as optimizer from "./views/optimizer.js";
import * as analytics from "./views/analytics.js";
import * as settings from "./views/settings.js";
import * as methods from "./views/methods.js";
import * as brief from "./views/brief.js";

const ROUTES = { dashboard, home, readings, decisions, optimizer, analytics, settings, methods, brief };
const TITLES = {
  dashboard: "Dashboard", home: "Rooms & devices", readings: "Readings", decisions: "AI decisions",
  optimizer: "Schedule optimizer", analytics: "Analytics", settings: "Settings", methods: "How the AI works", brief: "Topic 12 walkthrough",
};

const view = document.getElementById("view");
const sidebar = document.getElementById("sidebar");
const navToggle = document.getElementById("nav-toggle");
let renderId = 0;

export const ctx = {
  meta: null,
  async refreshMeta() {
    ctx.meta = await api.get("/meta");
    renderBanners();
    return ctx.meta;
  },
  navigate(route, params = {}) {
    const query = new URLSearchParams(params).toString();
    location.hash = `#/${route}${query ? `?${query}` : ""}`;
  },
  rerender: () => render(),
};

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [name, query = ""] = raw.split("?");
  return { name: ROUTES[name] ? name : "dashboard", params: new URLSearchParams(query) };
}

function renderBanners() {
  const box = clear(document.getElementById("banners"));
  if (getWorkspace() === "demo") {
    const demo = ctx.meta?.demo;
    box.append(h("div", { class: "banner demo", role: "note" },
      h("strong", {}, "Demo workspace: synthetic data. "),
      demo
        ? `Generated from seed ${demo.seed}, ${demo.days} days from ${demo.start_date}. Nothing here is a real measurement, and it is stored separately from "My home".`
        : "No demo data yet. Open Settings and press “Generate demo data”."));
  }
  if (ctx.meta?.read_only) {
    box.append(h("div", { class: "banner demo", role: "note" },
      h("strong", {}, "Read-only copy. "), "You can explore every page and use the calculators, but saving changes is disabled."));
  }
  box.append(h("div", { class: "banner virtual", role: "note" },
    h("strong", {}, "Virtual devices. "),
    "No hardware is connected: ON/OFF commands change only the simulated device state, and energy is estimated from rated power × ON time."));
}

function syncWorkspaceButtons() {
  for (const button of document.querySelectorAll(".workspace button")) {
    button.setAttribute("aria-pressed", String(button.dataset.ws === getWorkspace()));
  }
}

async function render() {
  const id = ++renderId;
  const { name, params } = parseHash();
  document.title = `${TITLES[name]} · Smart Home Energy Manager`;
  for (const link of sidebar.querySelectorAll("a[data-route]")) {
    if (link.dataset.route === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  closeNav();
  clear(view).append(loading());
  try {
    if (!ctx.meta || ctx.meta.workspace !== getWorkspace()) await ctx.refreshMeta();
    const container = h("div", { class: "stack" });
    await ROUTES[name].render(container, { ...ctx, params, isCurrent: () => id === renderId });
    if (id !== renderId) return;
    clear(view).append(container);
  } catch (error) {
    if (id !== renderId) return;
    clear(view).append(errorBox(error, "This page could not be loaded."),
      h("button", { class: "btn", onclick: () => render() }, "Try again"));
  }
}

function closeNav() {
  sidebar.classList.remove("open");
  navToggle.setAttribute("aria-expanded", "false");
}

navToggle.addEventListener("click", () => {
  const open = !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", open);
  navToggle.setAttribute("aria-expanded", String(open));
});
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeNav(); });

for (const button of document.querySelectorAll(".workspace button")) {
  button.addEventListener("click", () => {
    if (button.dataset.ws === getWorkspace()) return;
    setWorkspace(button.dataset.ws);
    syncWorkspaceButtons();
    ctx.meta = null;
    render();
  });
}

window.addEventListener("hashchange", render);

// A read-only (public) copy cannot fill "My home", so first-time visitors start in the demo.
async function start() {
  if (!hasStoredWorkspace()) {
    try {
      const meta = await api.get("/meta");
      if (meta.read_only) setWorkspace("demo");
    } catch { /* the page shows its own error below */ }
  }
  syncWorkspaceButtons();
  renderBanners();
  render();
}
start();
