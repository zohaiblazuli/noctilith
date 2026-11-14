// Wide view: one whole SPHEREx image (~3.5°) around the spot, shown zoomed out first.
// Zooming keeps full quality (the PNG has every pixel). The yellow box is the area that
// "Play this area over time" loads from every frame (the flipbook in app.js).
import { state, on, loadTarget, cancelLoads, syncUrl, showFrame } from "./app.js";
import { Viewer } from "./viewer.js";
import { gridToSky, skyToGrid, flipbookFov } from "./logic.js";

const $ = (id) => document.getElementById(id);
const DEFAULT_FOV = 0.1;   // box size before the user zooms: quick to load (~2 min for a new spot)
const MIN_VISIBLE_PX = 40; // deepest zoom: ~40 SPHEREx pixels across the screen

export const wideViewer = new Viewer($("wideCanvas"));
let setModeFn = () => {};
let pending = null; // {ra, dec} asked for but not opened yet
let token = 0;

export function initWide(setMode) { setModeFn = setMode; }

on("onWideRequest", (ra, dec) => {
  pending = { ra, dec };
  setModeFn("wide");
});

const same = (a, b) => a && b && Math.abs(a.ra - b.ra) < 1e-6 && Math.abs(a.dec - b.dec) < 1e-6;

// Called by features.js setMode() when the Wide tab becomes visible.
export function onWideShown() {
  const t = pending ?? (state.wide ? null : state.target && { ra: state.target.ra, dec: state.target.dec });
  pending = null;
  if (t && !same(t, state.wide)) openWide(t.ra, t.dec);
  else { wideViewer.draw(); setLabel(); }
}

// Called when the Play tab becomes visible: if the user moved to a new spot in the wide view
// but hasn't loaded it yet, load the boxed area now instead of showing the old spot.
export function onPlayShown() {
  if (state.wideNewer && state.wide?.info) playArea();
  else if (state.current) showFrame(state.current);
}

async function openWide(ra, dec) {
  const my = ++token;
  if (!same({ ra, dec }, state.target)) { cancelLoads(); state.wideNewer = true; }
  state.wide = { ra, dec, info: null };
  syncUrl();
  wideViewer.resetView();
  wideViewer.setOverlays({});
  $("playArea").disabled = true;
  $("frameLabel").textContent = "";
  wideViewer.setMessage("Downloading one whole SPHEREx image of this area (10–20 s the first time)…");
  try {
    const r = await fetch(`/api/overview?ra=${ra}&dec=${dec}`);
    if (my !== token) return;
    if (r.status === 404) { wideViewer.setMessage("No SPHEREx images cover this spot yet. Try a demo spot."); return; }
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    const info = await r.json();
    const img = new Image();
    img.src = info.png;
    await img.decode();
    if (my !== token) return;
    state.wide.info = info;
    wideViewer.maxZoom = Math.max(12, info.n / MIN_VISIBLE_PX);
    wideViewer.setImage(img, info.n);
    updateBox();
    setLabel();
    $("playArea").disabled = false;
  } catch (e) {
    if (my !== token) return;
    wideViewer.setMessage("Couldn't download the wide image. Try again in a moment.");
    $("formError").textContent = String(e.message || e);
  }
}

function setLabel() {
  const i = state.wide?.info;
  if (!i || state.mode !== "wide") return;
  $("frameLabel").textContent =
    `Wide view · ${i.iso.replace("T", " ").slice(0, 16)} UTC · λ ≈ ${i.wavelength_um.toFixed(2)} µm · detector D${i.detector} · one whole SPHEREx image, about 3.5° across`;
}

// The area that will play: your target until you zoom, then the middle of the screen.
function playRegion() {
  const info = state.wide?.info;
  if (!info) return null;
  if (wideViewer.view.zoom <= 1) {
    const [x, y] = skyToGrid(info, state.wide.ra, state.wide.dec);
    return { ra: state.wide.ra, dec: state.wide.dec, fov: DEFAULT_FOV, x, y };
  }
  const v = wideViewer.visibleRegion();
  const [ra, dec] = gridToSky(info, v.x, v.y);
  return { ra, dec, fov: flipbookFov(v.size * info.pixel_deg), x: v.x, y: v.y };
}

function updateBox() {
  const info = state.wide?.info;
  const p = playRegion();
  if (!p) return;
  const [tx, ty] = skyToGrid(info, state.wide.ra, state.wide.dec);
  wideViewer.setOverlays({
    rect: { x: p.x, y: p.y, size: p.fov / info.pixel_deg, label: `plays ${p.fov}°` },
    marker: { x: tx, y: ty },
  });
  $("playArea").textContent = `▶ Play this area over time (${p.fov}°)`;
}
wideViewer.onViewChange(updateBox);

function playArea() {
  const p = playRegion();
  if (!p) return;
  $("ra").value = p.ra.toFixed(5);
  $("dec").value = p.dec.toFixed(5);
  $("fov").value = String(p.fov);
  const t = state.target;
  const loaded = t && Math.abs(t.ra - p.ra) < 1e-5 && Math.abs(t.dec - p.dec) < 1e-5 && t.fov === p.fov;
  state.wideNewer = false;
  setModeFn("play");
  if (!loaded) loadTarget(p.ra, p.dec, p.fov);
}
$("playArea").addEventListener("click", playArea);
