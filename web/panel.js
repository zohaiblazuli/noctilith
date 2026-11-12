// Side panel: details of the clicked spot.
const $ = (id) => document.getElementById(id);

const fmtDeg = (v, d = 5) => v.toFixed(d) + "°";

export function showSpot({ x, y, ra, dec, value, bad, known, frameLabel }) {
  let verdict;
  if (bad) {
    verdict = `<div class="verdict">This pixel is <b>flagged</b> in this frame (a detector glitch, cosmic ray or saturated star). Its value can't be trusted. Try another frame.</div>`;
  } else if (known && known.name) {
    verdict = `<div class="verdict known"><b>Known:</b> ${known.name}<br><span class="muted">${known.cls || "solar-system object"}${known.vmag ? ` · V ≈ ${known.vmag}` : ""}</span><br>It's a catalogued asteroid or comet, already in the books.</div>`;
  } else if (known) {
    verdict = `<div class="verdict star"><b>Gaia star</b> · G = ${known.gmag.toFixed(1)}<br><span class="muted">Gaia DR3 ${known.source_id}</span></div>`;
  } else {
    verdict = `<div class="verdict cand"><b>Not in Gaia or the known-asteroid lists</b>, so it's a <b>candidate</b>. Before getting excited, check that it shows up in more than one frame and isn't flagged. Many candidates are faint galaxies or noise.</div>`;
  }
  $("spot").classList.remove("muted");
  $("spot").innerHTML = `
    <dl>
      <dt>RA</dt><dd>${fmtDeg(ra)}</dd>
      <dt>Dec</dt><dd>${dec >= 0 ? "+" : ""}${fmtDeg(dec)}</dd>
      <dt>Pixel</dt><dd>${x}, ${y}</dd>
      <dt>Brightness</dt><dd>${Number.isFinite(value) ? value.toFixed(3) + " MJy/sr" : "n/a"} <span class="muted">(above background)</span></dd>
      <dt>Frame</dt><dd>${frameLabel}</dd>
    </dl>${verdict}`;
}

export function drawSpectrum(points) {
  const box = $("spectrumBox"), cv = $("spectrum");
  box.hidden = false;
  const dpr = window.devicePixelRatio || 1;
  const w = (cv.width = cv.clientWidth * dpr), h = (cv.height = cv.clientHeight * dpr);
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement);
  ctx.font = `${10 * dpr}px Inter, system-ui, sans-serif`;
  ctx.fillStyle = css.getPropertyValue("--muted");
  if (points.length < 2) {
    ctx.textAlign = "center";
    ctx.fillText(`Only ${points.length} usable visit(s) loaded so far…`, w / 2, h / 2);
    return;
  }
  const pad = { l: 38 * dpr, r: 8 * dpr, t: 8 * dpr, b: 22 * dpr };
  const xs = points.map((p) => p.um), ys = points.map((p) => p.value);
  const x0 = Math.min(0.75, ...xs), x1 = Math.max(5.0, ...xs);
  let y0 = Math.min(0, ...ys), y1 = Math.max(...ys);
  if (y1 - y0 < 1e-6) y1 = y0 + 1;
  const X = (v) => pad.l + ((v - x0) / (x1 - x0)) * (w - pad.l - pad.r);
  const Y = (v) => h - pad.b - ((v - y0) / (y1 - y0)) * (h - pad.t - pad.b);
  ctx.strokeStyle = css.getPropertyValue("--line"); ctx.lineWidth = dpr;
  ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, h - pad.b); ctx.lineTo(w - pad.r, h - pad.b); ctx.stroke();
  if (y0 < 0) { ctx.setLineDash([3 * dpr, 3 * dpr]); ctx.beginPath(); ctx.moveTo(pad.l, Y(0)); ctx.lineTo(w - pad.r, Y(0)); ctx.stroke(); ctx.setLineDash([]); }
  ctx.textAlign = "center";
  for (let t = 1; t <= 5; t++) ctx.fillText(`${t}`, X(t), h - 6 * dpr);
  ctx.fillText("µm", w - 14 * dpr, h - 6 * dpr);
  ctx.textAlign = "right";
  ctx.fillText(y1.toPrecision(2), pad.l - 4 * dpr, pad.t + 8 * dpr);
  ctx.fillText(y0.toPrecision(2), pad.l - 4 * dpr, h - pad.b);
  for (const p of points) {
    ctx.fillStyle = `hsl(${Math.round(240 - 240 * Math.min(1, Math.max(0, (p.um - 0.75) / 4.25)))}, 75%, 60%)`;
    ctx.beginPath(); ctx.arc(X(p.um), Y(p.value), 2.6 * dpr, 0, Math.PI * 2); ctx.fill();
  }
}
