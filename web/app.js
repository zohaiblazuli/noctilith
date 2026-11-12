import { parseRA, parseDec, decodeF32, decodeU8, stretch, wavelengthColor, orderLoad } from "./logic.js";
import { Viewer } from "./viewer.js";

const $ = (id) => document.getElementById(id);
const LOAD_CONCURRENCY = 6;

export const state = {
  target: null,        // {ra, dec, fov, n}
  frames: [],          // FrameMeta dicts, time order
  bursts: [],
  payloads: new Map(), // id -> decoded payload
  status: new Map(),   // id -> loading | ready | failed | empty
  current: null,       // frame id
  mode: "play",
  playing: false,
  detector: "all",
  token: 0,            // bumps on every new target, cancels stale loads
};

const hooks = { onFrameShown: [], onTargetLoaded: [], onModeChange: [] };
export const on = (name, fn) => hooks[name].push(fn);
const emit = (name, ...a) => hooks[name].forEach((fn) => fn(...a));

export const mainViewer = new Viewer($("mainCanvas"));

// ---------- helpers ----------
export const frameById = (id) => state.frames.find((f) => f.id === id);
export const wavelengthOf = (f) => {
  const p = state.payloads.get(f.id);
  return p ? p.wavelength_um : (f.band_um[0] + f.band_um[1]) / 2;
};
export const visibleFrames = () =>
  state.frames.filter((f) => (state.detector === "all" || String(f.detector) === state.detector));
export const readyFrames = () => visibleFrames().filter((f) => state.status.get(f.id) === "ready");
const fmtTime = (iso) => iso.replace("T", " ").slice(0, 16) + " UTC";

function setError(msg) { $("formError").textContent = msg || ""; }

// ---------- URL ----------
function syncUrl() {
  const p = new URLSearchParams();
  if (state.target) {
    p.set("ra", String(+state.target.ra.toFixed(5)));
    p.set("dec", String(+state.target.dec.toFixed(5)));
    p.set("fov", String(state.target.fov));
  }
  if (state.mode !== "play") p.set("mode", state.mode);
  if (state.current) p.set("frame", state.current);
  history.replaceState(null, "", `${location.pathname}?${p}`);
}
export { syncUrl };

// ---------- loading ----------
async function loadTarget(ra, dec, fov, wantFrame = null) {
  const token = ++state.token;
  stopPlay();
  Object.assign(state, { frames: [], bursts: [], current: null });
  state.payloads.clear(); state.status.clear();
  mainViewer.setOverlays({});
  mainViewer.setMessage("Asking NASA's archive for SPHEREx images of this spot…");
  $("frameLabel").textContent = "";
  $("timeline").innerHTML = "";
  setError("");

  let body;
  try {
    const r = await fetch(`/api/frames?ra=${ra}&dec=${dec}&fov=${fov}`);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    body = await r.json();
  } catch (e) {
    if (token !== state.token) return;
    mainViewer.setMessage("Couldn't reach NASA's archive. Try again in a moment.");
    setError(String(e.message || e));
    return;
  }
  if (token !== state.token) return;
  state.target = body.target;
  state.frames = body.frames;
  state.bursts = body.bursts;
  syncUrl();

  if (!state.frames.length) {
    mainViewer.setMessage("No SPHEREx images cover this spot yet. Try a demo spot.");
    $("loadStatus").textContent = "";
    return;
  }
  buildBurstSelect();
  buildTimeline();
  emit("onTargetLoaded");
  mainViewer.setMessage(`Found ${state.frames.length} images. Loading the newest visit first…`);

  const order = orderLoad(state.frames, state.bursts);
  if (wantFrame && order.includes(wantFrame)) order.unshift(...order.splice(order.indexOf(wantFrame), 1));
  order.forEach((id) => state.status.set(id, "loading"));
  updateLoadStatus();
  const queue = [...order];
  const worker = async () => {
    while (queue.length && token === state.token) await loadFrame(queue.shift(), token, wantFrame);
  };
  await Promise.all(Array.from({ length: LOAD_CONCURRENCY }, worker));
}

async function loadFrame(id, token, wantFrame) {
  const t = state.target;
  setTile(id, "loading");
  try {
    const r = await fetch(`/api/frame?id=${encodeURIComponent(id)}&ra=${t.ra}&dec=${t.dec}&fov=${t.fov}`);
    if (token !== state.token) return;
    if (r.status === 404) { state.status.set(id, "empty"); setTile(id, "empty"); return; }
    if (!r.ok) throw new Error(r.statusText);
    const p = await r.json();
    if (token !== state.token) return;
    const img = decodeF32(p.image), bad = decodeU8(p.bad);
    state.payloads.set(id, { ...p, img, sig: decodeF32(p.sigma), badArr: bad, scale: stretch(img, bad) });
    state.status.set(id, "ready");
    setTile(id, "ready");
    if (!state.current || id === wantFrame) showFrame(id);
  } catch {
    if (token !== state.token) return;
    state.status.set(id, "failed");
    setTile(id, "failed");
  }
  updateLoadStatus();
}

function updateLoadStatus() {
  const c = { loading: 0, ready: 0, failed: 0, empty: 0 };
  state.status.forEach((s) => c[s]++);
  const parts = [`${c.ready} of ${state.frames.length} images ready`];
  if (c.loading) parts.push(`${c.loading} loading (each takes ~15 s from NASA the first time)`);
  if (c.failed) parts.push(`${c.failed} failed (click a grey tile to retry)`);
  if (c.empty) parts.push(`${c.empty} only clip the edge of this spot`);
  $("loadStatus").textContent = parts.join(" · ");
}

// ---------- timeline ----------
function buildBurstSelect() {
  const sel = $("burst");
  sel.innerHTML = `<option value="all">All visits</option>` + state.bursts.map((b) =>
    `<option value="${b.id}">${b.start_iso.slice(0, 10)} (${b.count})</option>`).join("");
}

function buildTimeline() {
  const tl = $("timeline");
  tl.innerHTML = "";
  for (const b of state.bursts) {
    const group = document.createElement("div");
    group.className = "burst";
    group.dataset.burst = b.id;
    const lab = document.createElement("span");
    lab.className = "burst-label";
    lab.textContent = b.start_iso.slice(0, 7);
    group.append(lab);
    for (const f of state.frames.filter((f) => f.burst === b.id)) {
      const t = document.createElement("button");
      t.type = "button";
      t.className = "tile loading";
      t.dataset.id = f.id;
      t.style.background = wavelengthColor(wavelengthOf(f));
      t.title = `${fmtTime(f.iso)} · D${f.detector}`;
      t.addEventListener("click", (e) => onTileClick(f.id, e));
      group.append(t);
    }
    tl.append(group);
  }
  applyDetectorFilter();
}

const tileEl = (id) => $("timeline").querySelector(`[data-id="${CSS.escape(id)}"]`);

function setTile(id, s) {
  const el = tileEl(id);
  if (!el) return;
  el.classList.remove("loading", "failed");
  if (s === "loading") el.classList.add("loading");
  if (s === "failed" || s === "empty") el.classList.add("failed");
  if (s === "empty") el.title += " · no usable pixels here";
  const f = frameById(id);
  if (s === "ready") {
    el.style.background = wavelengthColor(wavelengthOf(f));
    el.title = `${fmtTime(f.iso)} · λ ${wavelengthOf(f).toFixed(2)} µm · D${f.detector}`;
  }
}

function onTileClick(id, e) {
  const s = state.status.get(id);
  if (s === "failed") { state.status.set(id, "loading"); updateLoadStatus(); loadFrame(id, state.token); return; }
  if (s !== "ready") return;
  if (e.shiftKey && state.mode === "compare") { emit("onModeChange", "pin-before", id); return; }
  stopPlay();
  showFrame(id);
}

function applyDetectorFilter() {
  for (const el of $("timeline").querySelectorAll(".tile")) {
    const f = frameById(el.dataset.id);
    el.classList.toggle("hidden-det", state.detector !== "all" && String(f.detector) !== state.detector);
  }
}

// ---------- showing frames ----------
export function showFrame(id) {
  const f = frameById(id), p = state.payloads.get(id);
  if (!f || !p) return;
  state.current = id;
  mainViewer.setGray(p.img, p.badArr, p.n, p.scale.lo, p.scale.hi);
  const ready = readyFrames();
  const idx = ready.findIndex((r) => r.id === id);
  $("frameLabel").innerHTML =
    `Frame <b>${idx + 1}</b> of ${ready.length} ready · <b>${fmtTime(f.iso)}</b> · λ = <b>${p.wavelength_um.toFixed(2)} µm</b> · detector D${f.detector}`;
  $("timeline").querySelectorAll(".tile.current").forEach((el) => el.classList.remove("current"));
  const el = tileEl(id);
  if (el) { el.classList.add("current"); el.scrollIntoView({ block: "nearest", inline: "nearest" }); }
  if ($("burst").value !== "all" && String(f.burst) !== $("burst").value) $("burst").value = "all";
  syncUrl();
  emit("onFrameShown", f, p);
}

function playable() {
  const b = $("burst").value;
  return readyFrames().filter((f) => b === "all" || String(f.burst) === b);
}

function step(dir) {
  const list = playable();
  if (!list.length) return;
  const i = list.findIndex((f) => f.id === state.current);
  const next = list[(i + dir + list.length) % list.length] || list[0];
  showFrame(next.id);
}

let timer = null;
function startPlay() {
  if (timer) return;
  state.playing = true;
  $("play").textContent = "⏸";
  const tick = () => { step(1); timer = setTimeout(tick, 1000 / +$("speed").value); };
  tick();
}
export function stopPlay() {
  clearTimeout(timer); timer = null; state.playing = false;
  $("play").textContent = "▶";
}

// ---------- events ----------
$("search").addEventListener("submit", (e) => {
  e.preventDefault();
  const ra = parseRA($("ra").value), dec = parseDec($("dec").value);
  if (ra === null) return setError("RA should be 0–360 degrees (e.g. 150.0) or hours like 10h00m00s.");
  if (dec === null) return setError("Dec should be −90 to +90 degrees (e.g. +2.2 or +02:12:00).");
  loadTarget(ra, dec, +$("fov").value);
});
$("play").addEventListener("click", () => (state.playing ? stopPlay() : startPlay()));
$("prev").addEventListener("click", () => { stopPlay(); step(-1); });
$("next").addEventListener("click", () => { stopPlay(); step(1); });
$("speed").addEventListener("input", () => { $("speedVal").textContent = $("speed").value; });
$("burst").addEventListener("change", () => {
  const b = $("burst").value;
  if (b === "all") return;
  const first = playable()[0];
  if (first) showFrame(first.id);
  $("timeline").querySelector(`[data-burst="${b}"]`)?.scrollIntoView({ inline: "start", block: "nearest" });
});
$("detector").addEventListener("change", () => {
  state.detector = $("detector").value;
  applyDetectorFilter();
  const cur = frameById(state.current);
  if (cur && state.detector !== "all" && String(cur.detector) !== state.detector) step(1);
});
$("share").addEventListener("click", async () => {
  syncUrl();
  try { await navigator.clipboard.writeText(location.href); $("share").textContent = "Link copied ✓"; }
  catch { prompt("Copy this link:", location.href); }
  setTimeout(() => { $("share").textContent = "Share link"; }, 1800);
  document.dispatchEvent(new CustomEvent("tool:share"));
});
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (e.key === "ArrowRight") { stopPlay(); step(1); }
  else if (e.key === "ArrowLeft") { stopPlay(); step(-1); }
  else if (e.key === " ") { e.preventDefault(); state.playing ? stopPlay() : startPlay(); }
});

// demo spots
fetch("demo-spots.json").then((r) => r.json()).then((spots) => {
  const sel = $("demo");
  spots.forEach((s, i) => sel.add(new Option(s.label, i)));
  sel.addEventListener("change", () => {
    const s = spots[+sel.value];
    if (!s) return;
    $("ra").value = s.ra; $("dec").value = s.dec; $("fov").value = String(s.fov);
    loadTarget(s.ra, s.dec, s.fov);
    sel.value = "";
  });
}).catch(() => {});

// start from URL
const q = new URLSearchParams(location.search);
export const initialMode = q.get("mode") === "compare" ? "compare" : "play";
if (q.get("ra") && q.get("dec")) {
  const ra = parseRA(q.get("ra")), dec = parseDec(q.get("dec"));
  const fov = [0.05, 0.1, 0.2, 0.5].includes(+q.get("fov")) ? +q.get("fov") : 0.1;
  if (ra !== null && dec !== null) {
    $("ra").value = q.get("ra"); $("dec").value = q.get("dec"); $("fov").value = String(fov);
    queueMicrotask(() => loadTarget(ra, dec, fov, q.get("frame")));
  }
} else {
  mainViewer.setMessage("Enter RA/Dec above, or pick a demo spot.");
}
