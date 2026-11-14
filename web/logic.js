// Pure helpers (no DOM). Tested with: node --test "web/*.test.mjs"

function sexagesimal(str) {
  // "10h00m00s", "10:00:00", "10 00 00", "-41d38m" -> [sign, a, b, c] or null
  const s = str.trim().toLowerCase();
  const m = s.match(/^([+-]?)(\d+(?:\.\d+)?)\s*[hd:\s°]\s*(\d+(?:\.\d+)?)?\s*[m:'′\s]?\s*(\d+(?:\.\d+)?)?\s*[s"″]?$/);
  if (!m) return null;
  return [m[1] === "-" ? -1 : 1, +m[2], +(m[3] || 0), +(m[4] || 0)];
}

const isDecimal = (s) => /^[+-]?\d+(\.\d+)?$/.test(s.trim());

export function parseRA(str) {
  if (!str || !str.trim()) return null;
  let v;
  if (isDecimal(str)) v = parseFloat(str);
  else {
    const p = sexagesimal(str);
    if (!p || p[0] < 0 || p[2] >= 60 || p[3] >= 60) return null;
    v = 15 * (p[1] + p[2] / 60 + p[3] / 3600);
  }
  return v >= 0 && v < 360 ? v : null;
}

export function parseDec(str) {
  if (!str || !str.trim()) return null;
  let v;
  if (isDecimal(str)) v = parseFloat(str);
  else {
    const p = sexagesimal(str);
    if (!p || p[2] >= 60 || p[3] >= 60) return null;
    v = p[0] * (p[1] + p[2] / 60 + p[3] / 3600);
  }
  return v >= -90 && v <= 90 ? v : null;
}

export function decodeF32(b64) {
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return new Float32Array(u8.buffer);
}

export function decodeU8(b64) {
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return u8;
}

function median(sorted) {
  const n = sorted.length;
  return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
}

export function stretch(img, bad) {
  const good = [];
  for (let i = 0; i < img.length; i++) if (!bad[i] && Number.isFinite(img[i])) good.push(img[i]);
  if (!good.length) return { lo: 0, hi: 1 };
  good.sort((a, b) => a - b);
  const med = median(good);
  const dev = good.map((v) => Math.abs(v - med)).sort((a, b) => a - b);
  let mad = median(dev);
  if (!(mad > 0)) mad = (good[good.length - 1] - good[0]) / 20 || 1;
  // Top of the range = a near-brightest pixel, so galaxy cores and bright stars roll off
  // instead of clipping; `soft` is where the asinh curve starts compressing (~noise level).
  const p998 = good[Math.min(good.length - 1, Math.floor(good.length * 0.998))];
  return { lo: med - 2 * mad, hi: Math.max(med + 20 * mad, p998), soft: 3 * mad };
}

export function wavelengthColor(um) {
  const t = Math.min(1, Math.max(0, (um - 0.75) / (5.0 - 0.75)));
  return `hsl(${Math.round(240 - 240 * t)}, 70%, 50%)`;
}

export function orderLoad(frames, bursts) {
  const ids = bursts.map((b) => b.id).sort((a, b) => b - a);
  const out = [];
  for (const id of ids) {
    frames.filter((f) => f.burst === id).sort((a, b) => a.mjd - b.mjd).forEach((f) => out.push(f.id));
  }
  return out;
}

// ---------- Task 7 ----------
const HOUR = 1 / 24;
export const PAIR_WARN_UM = 0.03;

export function ssoAt(obj, mjdRef, mjd) {
  const h = (mjd - mjdRef) * 24;
  return { x: obj.x + obj.dx_per_hr * h, y: obj.y + obj.dy_per_hr * h };
}

// Pick the "before" frame for `id`: ready, ≥1 h apart, closest in wavelength.
export function pairFor(id, frames, payloads) {
  const cur = payloads.get(id);
  if (!cur) return null;
  let best = null;
  for (const f of frames) {
    const p = payloads.get(f.id);
    if (!p || f.id === id || Math.abs(p.mjd - cur.mjd) < HOUR) continue;
    const d = Math.abs(p.wavelength_um - cur.wavelength_um);
    if (!best || d < best.deltaUm) best = { before: f.id, deltaUm: d };
  }
  if (!best) return null;
  return { ...best, warn: best.deltaUm > PAIR_WARN_UM };
}

// (after − before) / combined noise; NaN where either pixel is bad.
export function diffSigma(a, b, sa, sb, badA, badB) {
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) {
    const s = Math.sqrt(sa[i] * sa[i] + sb[i] * sb[i]);
    out[i] = badA[i] || badB[i] || !(s > 0) ? NaN : (a[i] - b[i]) / s;
  }
  return out;
}

export function nearestKnown(x, y, sso, stars, r = 2) {
  let best = null, bestD = r;
  for (const o of [...sso, ...stars]) {
    const d = Math.hypot(o.x - x, o.y - y);
    if (d <= bestD) { best = o; bestD = d; }
  }
  return best;
}

// ---------- Task 9 ----------
export function spectrumAt(x, y, frames, payloads) {
  const out = [];
  for (const f of frames) {
    const p = payloads.get(f.id);
    if (!p) continue;
    const i = y * p.n + x;
    if (p.badArr[i] || !Number.isFinite(p.img[i]) || !Number.isFinite(p.wavelength_um)) continue;
    out.push({ um: p.wavelength_um, value: p.img[i], mjd: p.mjd });
  }
  return out.sort((a, b) => a.um - b.um);
}

// ---------- Task 10 ----------
// Connected groups (4-neighbour) of pixels with |σ| > thresh and at least minPix pixels.
export function findChanges(diff, n, thresh = 5, minPix = 2) {
  const seen = new Uint8Array(n * n);
  const out = [];
  for (let i = 0; i < n * n; i++) {
    if (seen[i] || !(Math.abs(diff[i]) > thresh)) continue;
    const sign = Math.sign(diff[i]);
    const stack = [i];
    seen[i] = 1;
    let sx = 0, sy = 0, count = 0, peak = 0;
    while (stack.length) {
      const j = stack.pop();
      const x = j % n, y = (j / n) | 0;
      sx += x; sy += y; count++;
      if (Math.abs(diff[j]) > Math.abs(peak)) peak = diff[j];
      for (const [nx, ny] of [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]]) {
        if (nx < 0 || ny < 0 || nx >= n || ny >= n) continue;
        const k = ny * n + nx;
        if (!seen[k] && Math.abs(diff[k]) > thresh && Math.sign(diff[k]) === sign) { seen[k] = 1; stack.push(k); }
      }
    }
    if (count >= minPix) out.push({ x: sx / count, y: sy / count, peak, pixels: count });
  }
  return out;
}

// A change is a candidate only if the source is clearly in one frame and absent (≤ absentSigma
// anywhere in the 3×3 neighbourhood) in the other. Static stars that merely subtract imperfectly
// (blur differs between visits) are present in both and get rejected.
export function isAppearance(c, n, a, sa, b, sb, presentSigma = 5, absentSigma = 3) {
  const [hasIn, missIn, sHas, sMiss] = c.peak > 0 ? [a, b, sa, sb] : [b, a, sb, sa];
  const x0 = Math.round(c.x), y0 = Math.round(c.y);
  let present = false, other = -Infinity;
  for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
    const x = x0 + dx, y = y0 + dy;
    if (x < 0 || y < 0 || x >= n || y >= n) continue;
    const i = y * n + x;
    if (sHas[i] > 0 && hasIn[i] / sHas[i] > presentSigma) present = true;
    if (sMiss[i] > 0 && Number.isFinite(missIn[i])) other = Math.max(other, missIn[i] / sMiss[i]);
  }
  return present && other <= absentSigma;
}

// Real sources are blurred by the telescope over several pixels; cosmic rays / hot pixels stay
// sharp even after reprojection spreads them over 2–3 grid pixels. Tuned on RA 150 Dec 2.2.
export function isPointLike(c, sharpPeak = 15) {
  return c.pixels >= 3 && !(Math.abs(c.peak) > sharpPeak && c.pixels < 5);
}

// ---------- review fixes ----------
export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Message for the viewer once loading has finished, or null if at least one frame is usable.
export function endOfLoadMessage({ ready, empty, failed }) {
  if (ready > 0) return null;
  if (failed > 0) return "NASA's archive isn't answering right now. Click a grey tile to retry, or try a demo spot.";
  if (empty > 0) return "SPHEREx only clipped the edge of this spot, so there are no usable images yet. Try a nearby position.";
  return "No SPHEREx images cover this spot yet. Try a demo spot.";
}

// Keep only markers that land on real image pixels (not off the edge, not in the blank,
// NaN area where this frame has no data).
export function onImage(objs, img, n) {
  return objs.filter((o) => {
    const x = Math.round(o.x), y = Math.round(o.y);
    return x >= 0 && y >= 0 && x < n && y < n && Number.isFinite(img[y * n + x]);
  });
}

export function brightest(stars, max) {
  return [...stars].sort((a, b) => a.gmag - b.gmag).slice(0, max);
}
