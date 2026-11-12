// Overlays (known objects), click panel and Compare mode, layered on top of app.js.
import { state, on, mainViewer, frameById, showFrame, stopPlay, syncUrl, initialMode, readyFrames } from "./app.js";
import { ssoAt, pairFor, diffSigma, nearestKnown, PAIR_WARN_UM } from "./logic.js";
import { Viewer } from "./viewer.js";
import { showSpot } from "./panel.js";

const $ = (id) => document.getElementById(id);
const STAR_GMAX_SHOWN = 15;

const known = { stars: [], sso: new Map() }; // sso: burst id -> {mjdRef, objs}
let token = 0;
let marker = null;
let pinnedBefore = null;

// ---------- known objects ----------
on("onTargetLoaded", async () => {
  const my = ++token;
  known.stars = []; known.sso.clear(); marker = null; pinnedBefore = null;
  const t = state.target;
  const q = `ra=${t.ra}&dec=${t.dec}&fov=${t.fov}`;
  fetch(`/api/known/stars?${q}`).then((r) => r.json()).then((s) => {
    if (my !== token) return;
    known.stars = s; refresh();
  }).catch(() => {});
  for (const b of state.bursts) {
    const fs = state.frames.filter((f) => f.burst === b.id);
    const mjdRef = fs.reduce((a, f) => a + f.mjd, 0) / fs.length;
    fetch(`/api/known/sso?${q}&mjd=${mjdRef.toFixed(4)}`).then((r) => r.json()).then((objs) => {
      if (my !== token) return;
      known.sso.set(b.id, { mjdRef, objs }); refresh();
    }).catch(() => {});
  }
});

function ssoFor(frame, mjd) {
  const k = known.sso.get(frame.burst);
  if (!k) return [];
  const n = state.target.n;
  return k.objs.map((o) => ({ ...o, ...ssoAt(o, k.mjdRef, mjd) }))
    .filter((o) => o.x > -3 && o.y > -3 && o.x < n + 2 && o.y < n + 2);
}
const starsShown = () => known.stars.filter((s) => s.gmag < STAR_GMAX_SHOWN);

function overlaysFor(id) {
  const f = frameById(id), p = state.payloads.get(id);
  if (!f || !p) return {};
  return { sso: ssoFor(f, p.mjd), stars: starsShown(), marker };
}

// ---------- compare ----------
const group = { view: { zoom: 1, panX: 0, panY: 0 }, members: [] };
const vBefore = new Viewer($("cBefore"), { linkGroup: group });
const vAfter = new Viewer($("cAfter"), { linkGroup: group });
const vDiff = new Viewer($("cDiff"), { linkGroup: group });
let currentPair = null;

function renderCompare() {
  const id = state.current;
  const after = state.payloads.get(id);
  if (!after) return;
  let pair = pinnedBefore && pinnedBefore !== id && state.payloads.has(pinnedBefore)
    ? { before: pinnedBefore, deltaUm: Math.abs(state.payloads.get(pinnedBefore).wavelength_um - after.wavelength_um) }
    : pairFor(id, readyFrames(), state.payloads);
  if (pair) pair.warn = pair.deltaUm > PAIR_WARN_UM;
  currentPair = pair;
  $("timeline").querySelectorAll(".tile.before").forEach((el) => el.classList.remove("before"));
  vAfter.setGray(after.img, after.badArr, after.n, after.scale.lo, after.scale.hi);
  vAfter.setOverlays(overlaysFor(id));
  const fa = frameById(id);
  $("capAfter").textContent = `After · ${fa.iso.slice(0, 16).replace("T", " ")} · λ ${after.wavelength_um.toFixed(2)} µm`;
  if (!pair) {
    vBefore.setMessage("Waiting for another frame to load…");
    vDiff.setMessage("");
    $("pairNote").textContent = "Need at least two frames taken an hour or more apart.";
    $("pairNote").classList.remove("warn");
    return;
  }
  const before = state.payloads.get(pair.before), fb = frameById(pair.before);
  vBefore.setGray(before.img, before.badArr, before.n, before.scale.lo, before.scale.hi);
  vBefore.setOverlays(overlaysFor(pair.before));
  $("capBefore").textContent = `Before · ${fb.iso.slice(0, 16).replace("T", " ")} · λ ${before.wavelength_um.toFixed(2)} µm`;
  vDiff.setDiverging(diffSigma(after.img, before.img, after.sig, before.sig, after.badArr, before.badArr), after.n, 5);
  vDiff.setOverlays({ sso: ssoFor(fa, after.mjd), marker });
  $(`timeline`).querySelector(`[data-id="${CSS.escape(pair.before)}"]`)?.classList.add("before");
  const hours = Math.abs(after.mjd - before.mjd) * 24;
  const gap = hours < 48 ? `${hours.toFixed(1)} hours` : `${(hours / 24).toFixed(0)} days`;
  $("pairNote").classList.toggle("warn", pair.warn);
  $("pairNote").textContent = pair.warn
    ? `⚠ Δλ = ${pair.deltaUm.toFixed(2)} µm: these frames saw quite different colours, so some differences are colour, not change. Wait for more frames, or shift-click a tile to choose the "before" frame.`
    : `Δλ = ${pair.deltaUm.toFixed(3)} µm (same colour) · ${gap} apart · red = brighter now, blue = brighter before. Shift-click a tile to choose the "before" frame.`;
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".seg button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
  $("playView").hidden = mode !== "play";
  $("compareView").hidden = mode !== "compare";
  if (mode === "compare") { stopPlay(); renderCompare(); }
  else refresh();
  syncUrl();
}
document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
on("onModeChange", (kind, id) => {
  if (kind === "pin-before") { pinnedBefore = id; renderCompare(); }
});

// ---------- refresh on every frame ----------
function refresh() {
  if (!state.current) return;
  if (state.mode === "compare") renderCompare();
  else mainViewer.setOverlays(overlaysFor(state.current));
}
on("onFrameShown", () => refresh());

// ---------- clicks ----------
function pixelToSky(x, y) {
  const t = state.target, p = 6.15 / 3600, c = (t.n - 1) / 2;
  const dec = t.dec + (y - c) * p;
  let ra = t.ra - ((x - c) * p) / Math.cos((t.dec * Math.PI) / 180);
  ra = ((ra % 360) + 360) % 360;
  return { ra, dec };
}

function onClick(frameId) {
  return (x, y) => {
    const id = frameId() || state.current;
    const f = frameById(id), pl = state.payloads.get(id);
    if (!f || !pl) return;
    marker = { x, y };
    const i = y * pl.n + x;
    const { ra, dec } = pixelToSky(x, y);
    const k = nearestKnown(x, y, ssoFor(f, pl.mjd), known.stars);
    showSpot({
      x, y, ra, dec, value: pl.img[i], bad: !!pl.badArr[i], known: k,
      frameLabel: `${f.iso.slice(0, 16).replace("T", " ")} · λ ${pl.wavelength_um.toFixed(2)} µm`,
    });
    document.dispatchEvent(new CustomEvent("tool:spot", { detail: { x, y } }));
    refresh();
  };
}
mainViewer.onPixelClick(onClick(() => state.current));
vAfter.onPixelClick(onClick(() => state.current));
vDiff.onPixelClick(onClick(() => state.current));
vBefore.onPixelClick(onClick(() => currentPair?.before));

if (initialMode === "compare") setMode("compare");
