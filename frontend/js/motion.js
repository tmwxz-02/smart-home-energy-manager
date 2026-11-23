// Motion layer: everything here is decoration only (no data, no API calls).
// * the background moves opposite to the mouse (parallax, eased with requestAnimationFrame);
// * a particle network drifts and is gently attracted to the pointer;
// * buttons get a ripple, the sidebar a sliding active pill, the workspace switch a sliding thumb;
// * a thin bar at the top shows scroll progress.
// Users who ask the OS for reduced motion get a static background.

const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const root = document.documentElement;

// ---------------------------------------------------------------- parallax
let targetX = 0, targetY = 0, curX = 0, curY = 0;
let mouseX = innerWidth / 2, mouseY = innerHeight / 2;

function onPointer(event) {
  mouseX = event.clientX;
  mouseY = event.clientY;
  targetX = (event.clientX / innerWidth - 0.5) * 2;   // -1 … 1
  targetY = (event.clientY / innerHeight - 0.5) * 2;
}
addEventListener("pointermove", onPointer, { passive: true });
document.addEventListener("pointerleave", () => { targetX = 0; targetY = 0; });

// ---------------------------------------------------------------- particle field
const canvas = document.getElementById("field");
const ctx = canvas ? canvas.getContext("2d") : null;
const dpr = Math.min(devicePixelRatio || 1, 2);
let W = 0, H = 0, particles = [];

function size() {
  if (!canvas) return;
  const box = canvas.getBoundingClientRect();
  W = box.width; H = box.height;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const count = Math.min(85, Math.floor((W * H) / 18000));
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * W, y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.6 + 0.6,
  }));
}

function drawField() {
  ctx.clearRect(0, 0, W, H);
  // pointer position in canvas space (the canvas is offset by 90 px and by its own parallax shift)
  const shift = 70;
  const px = mouseX + 90 + curX * shift;
  const py = mouseY + 90 + curY * shift;
  for (const p of particles) {
    const dx = px - p.x, dy = py - p.y, d = Math.hypot(dx, dy) || 1;
    if (d < 170) { p.vx += (dx / d) * 0.01; p.vy += (dy / d) * 0.01; }
    p.vx *= 0.985; p.vy *= 0.985;
    p.x += p.vx; p.y += p.vy;
    if (p.x < 0 || p.x > W) p.vx *= -1;
    if (p.y < 0 || p.y > H) p.vy *= -1;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7);
    ctx.fillStyle = "rgba(11, 11, 12, 0.32)"; ctx.fill();
  }
  for (let i = 0; i < particles.length; i += 1) {
    for (let j = i + 1; j < particles.length; j += 1) {
      const a = particles[i], b = particles[j];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d < 120) {
        ctx.strokeStyle = `rgba(11, 11, 12, ${0.13 * (1 - d / 120)})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
  }
}

function tick() {
  curX += (targetX - curX) * 0.06;
  curY += (targetY - curY) * 0.06;
  root.style.setProperty("--px", curX.toFixed(4));
  root.style.setProperty("--py", curY.toFixed(4));
  if (ctx && !document.hidden) drawField();
  requestAnimationFrame(tick);
}

if (!reduce) {
  size();
  addEventListener("resize", size);
  requestAnimationFrame(tick);
} else if (ctx) {
  size();
  drawField();
}

// ---------------------------------------------------------------- scroll progress
const bar = document.getElementById("progress");
function onScroll() {
  if (!bar) return;
  const h = document.documentElement;
  const max = Math.max(1, h.scrollHeight - h.clientHeight);
  bar.style.transform = `scaleX(${h.scrollTop / max})`;
}
addEventListener("scroll", onScroll, { passive: true });

// ---------------------------------------------------------------- button ripple
document.addEventListener("pointerdown", (event) => {
  const button = event.target.closest(".btn");
  if (!button || button.disabled || reduce) return;
  const box = button.getBoundingClientRect();
  const size = Math.max(box.width, box.height) * 2.2;
  const ripple = document.createElement("span");
  ripple.className = "ripple";
  ripple.style.width = ripple.style.height = `${size}px`;
  ripple.style.left = `${event.clientX - box.left - size / 2}px`;
  ripple.style.top = `${event.clientY - box.top - size / 2}px`;
  button.append(ripple);
  setTimeout(() => ripple.remove(), 650);
});

// ---------------------------------------------------------------- sliding indicators
export function moveNavPill() {
  const sidebar = document.getElementById("sidebar");
  const pill = sidebar?.querySelector(".nav-pill");
  const active = sidebar?.querySelector('a[aria-current="page"]');
  if (!pill) return;
  if (!active) { pill.style.opacity = "0"; return; }
  pill.style.height = `${active.offsetHeight}px`;
  pill.style.transform = `translateY(${active.offsetTop}px)`;
  pill.style.opacity = "1";
}

export function moveWorkspaceThumb() {
  const group = document.querySelector(".workspace");
  const thumb = group?.querySelector(".thumb");
  const active = group?.querySelector('button[aria-pressed="true"]');
  if (!thumb || !active) return;
  thumb.style.width = `${active.offsetWidth}px`;
  thumb.style.transform = `translateX(${active.offsetLeft}px)`;
  group.classList.toggle("demo", active.dataset.ws === "demo");
}

addEventListener("resize", () => { moveNavPill(); moveWorkspaceThumb(); });
document.fonts?.ready.then(() => { moveNavPill(); moveWorkspaceThumb(); });

// ---------------------------------------------------------------- staggered entrance
export function stagger(container) {
  [...container.children].forEach((child, index) => child.style.setProperty("--i", index));
  container.querySelectorAll(".kpis").forEach((row) => {
    [...row.children].forEach((child, index) => child.style.setProperty("--k", index));
  });
}

export const prefersReducedMotion = reduce;
