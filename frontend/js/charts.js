// Small SVG charts drawn from backend data (no chart library, works offline).
import { h, svg } from "./ui.js";

function niceMax(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= step * power) return step * power;
  }
  return 10 * power;
}

// Grouped bar chart. series: [{name, cls, values}] ; labels: x labels.
// refLine: optional {value, label} horizontal reference line.
export function barChart({ labels, series, unit = "", height = 220, refLine = null, max = null, ariaLabel = "Bar chart", labelEvery = 1 }) {
  const n = labels.length;
  const left = 44, right = 8, top = 10, bottom = 26;
  const groupWidth = Math.max(18, Math.min(64, 640 / Math.max(n, 1)));
  const width = left + right + n * groupWidth;
  const plotH = height - top - bottom;
  const peak = max ?? niceMax(Math.max(0, ...series.flatMap((s) => s.values.map((v) => v ?? 0)), refLine?.value ?? 0));
  const y = (value) => top + plotH - (plotH * value) / peak;
  const parts = [];
  for (let i = 0; i <= 4; i += 1) {
    const value = (peak * i) / 4;
    parts.push(svg("line", { class: "grid", x1: left, x2: width - right, y1: y(value), y2: y(value) }));
    parts.push(svg("text", { x: left - 6, y: y(value) + 3, "text-anchor": "end" }, formatTick(value)));
  }
  const barGap = 2;
  const barWidth = Math.max(3, (groupWidth - 6) / series.length - barGap);
  labels.forEach((label, index) => {
    const x0 = left + index * groupWidth + 3;
    series.forEach((s, j) => {
      const value = s.values[index] ?? 0;
      const cls = typeof s.cls === "function" ? s.cls(index) : s.cls;
      parts.push(svg("rect", {
        class: cls, x: x0 + j * (barWidth + barGap), y: y(value), width: barWidth,
        height: Math.max(0, top + plotH - y(value)), rx: 1.5,
      }, svg("title", {}, `${label} · ${s.name}: ${formatTick(value, 3)} ${unit}`)));
    });
    if (index % labelEvery === 0) {
      parts.push(svg("text", { x: x0 + (groupWidth - 6) / 2, y: height - 8, "text-anchor": "middle" }, label));
    }
  });
  if (refLine) {
    parts.push(svg("line", { class: "ref", x1: left, x2: width - right, y1: y(refLine.value), y2: y(refLine.value) }));
    parts.push(svg("text", { x: width - right - 2, y: y(refLine.value) - 4, "text-anchor": "end" }, refLine.label));
  }
  if (unit) parts.push(svg("text", { x: 4, y: top + 2 }, unit));
  return svg("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": ariaLabel,
    style: `max-width:${Math.max(width, 320) * 1.6}px` }, parts);
}

// Line chart for a single series (e.g. hill-climbing cost per iteration).
export function lineChart({ values, unit = "", height = 160, ariaLabel = "Line chart", xLabel = "" }) {
  const left = 52, right = 10, top = 10, bottom = 24;
  const width = 420;
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || 1;
  const x = (i) => left + (values.length === 1 ? 0 : ((width - left - right) * i) / (values.length - 1));
  const y = (v) => top + (height - top - bottom) * (1 - (v - lo) / span);
  const parts = [];
  for (const value of [lo, (lo + hi) / 2, hi]) {
    parts.push(svg("line", { class: "grid", x1: left, x2: width - right, y1: y(value), y2: y(value) }));
    parts.push(svg("text", { x: left - 6, y: y(value) + 3, "text-anchor": "end" }, formatTick(value, 1)));
  }
  parts.push(svg("polyline", { class: "line", points: values.map((v, i) => `${x(i)},${y(v)}`).join(" ") }));
  values.forEach((v, i) => parts.push(svg("circle", { class: "dot", cx: x(i), cy: y(v), r: 3 },
    svg("title", {}, `iteration ${i}: ${formatTick(v, 2)} ${unit}`))));
  parts.push(svg("text", { x: (left + width) / 2, y: height - 4, "text-anchor": "middle" }, xLabel));
  return svg("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": ariaLabel, style: "max-width:640px" }, parts);
}

function formatTick(value, digits) {
  if (digits !== undefined) return Number(value).toFixed(digits);
  if (value === 0) return "0";
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 1) return value.toFixed(1);
  return value.toFixed(2);
}

export function legend(items) {
  return h("div", { class: "legend" }, items.map(([label, color]) =>
    h("span", {}, h("i", { style: `background:${color}` }), label)));
}
