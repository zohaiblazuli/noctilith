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
  return { lo: med - 2 * mad, hi: med + 20 * mad };
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
