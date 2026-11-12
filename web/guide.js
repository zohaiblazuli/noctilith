// Optional first-time guide strip: ① pick → ② watch → ③ click → ④ is it known? → ⑤ share.
import { on, state } from "./app.js";

const KEY = "spherex-guide-hidden";
const STEPS = [
  "Pick a spot (or a demo)",
  "Press ▶ and watch for a dot that jumps",
  "Click it",
  "Read the panel: is it known?",
  "Share the link",
];
const HINTS = [
  "Type RA/Dec above, or choose “Try a demo spot…”.",
  "Stars stay put. Asteroids drift between frames. Compare mode shows changes in red and blue.",
  "Click the moving dot (or a red “candidate” box) in the image.",
  "Orange = known asteroid. Blue = Gaia star. Neither = candidate. Check other frames before celebrating!",
  "“Share link” copies a URL that reopens this exact view.",
];

const el = document.getElementById("guide");
let step = 0;

function hidden() {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}

function render() {
  if (hidden()) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = STEPS.map((s, i) =>
    `<span class="step ${i < step ? "done" : i === step ? "now" : ""}">${i < step ? "✓" : "①②③④⑤"[i]} ${s}</span>`).join("")
    + `<span class="muted">${step < STEPS.length ? HINTS[step] : "You've got it. Happy hunting!"}</span>`
    + `<button type="button" class="close" aria-label="Hide guide">✕</button>`;
  el.querySelector(".close").addEventListener("click", () => {
    try { localStorage.setItem(KEY, "1"); } catch { /* private mode: hide for this visit only */ }
    el.hidden = true;
  });
}

const advance = (to) => { if (to > step) { step = to; render(); } };
on("onTargetLoaded", () => advance(1));
document.getElementById("play").addEventListener("click", () => { if (state.target) advance(2); });
document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { if (state.target) advance(2); }));
document.addEventListener("tool:spot", () => advance(4));
document.addEventListener("tool:share", () => advance(5));

render();
