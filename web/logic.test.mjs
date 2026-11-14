import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseRA, parseDec, stretch, orderLoad, decodeF32, wavelengthColor,
  ssoAt, pairFor, diffSigma, nearestKnown, spectrumAt, findChanges, isAppearance, isPointLike,
  esc, endOfLoadMessage, onImage, brightest,
} from "./logic.js";

test("esc neutralises HTML", () => {
  assert.equal(esc('<img src=x onerror="a">&'), "&lt;img src=x onerror=&quot;a&quot;&gt;&amp;");
  assert.equal(esc(null), "");
  assert.equal(esc(14.3), "14.3");
});

test("endOfLoadMessage only when nothing is usable", () => {
  assert.equal(endOfLoadMessage({ ready: 3, empty: 1, failed: 0 }), null);
  assert.match(endOfLoadMessage({ ready: 0, empty: 5, failed: 0 }), /edge/);
  assert.match(endOfLoadMessage({ ready: 0, empty: 0, failed: 5 }), /NASA/);
  assert.match(endOfLoadMessage({ ready: 0, empty: 2, failed: 3 }), /NASA/);
});

test("isPointLike rejects tiny sharp spikes (cosmic rays)", () => {
  assert.equal(isPointLike({ pixels: 2, peak: 8 }), false);
  assert.equal(isPointLike({ pixels: 3, peak: 40 }), false);
  assert.equal(isPointLike({ pixels: 3, peak: 9 }), true);
  assert.equal(isPointLike({ pixels: 6, peak: -60 }), true);
});

test("isAppearance: present in one frame only", () => {
  const n = 5, one = new Float32Array(n * n).fill(1);
  const a = new Float32Array(n * n), b = new Float32Array(n * n);
  a[2 * n + 2] = 10;                                  // new source in "after"
  assert.equal(isAppearance({ x: 2, y: 2, peak: 8 }, n, a, one, b, one), true);
  b[2 * n + 3] = 10;                                  // a static source next door in "before" too
  assert.equal(isAppearance({ x: 2, y: 2, peak: 8 }, n, a, one, b, one), false);
  // negative change: was there before, gone now
  const a2 = new Float32Array(n * n), b2 = new Float32Array(n * n); b2[0] = 10;
  assert.equal(isAppearance({ x: 0, y: 0, peak: -8 }, n, a2, one, b2, one), true);
});

test("findChanges boxes a 2-pixel blob but not a single spike", () => {
  const n = 10, d = new Float32Array(n * n);
  d[3 * n + 4] = 8; d[3 * n + 5] = 7;   // blob at y=3, x=4..5
  d[8 * n + 8] = 50;                     // lone spike (cosmic-ray-like)
  const out = findChanges(d, n);
  assert.equal(out.length, 1);
  near(out[0].x, 4.5); near(out[0].y, 3); assert.equal(out[0].peak, 8);
});

test("findChanges treats negative blobs too and ignores NaN", () => {
  const n = 6, d = new Float32Array(n * n).fill(NaN);
  d[0] = -9; d[1] = -6;
  const out = findChanges(d, n);
  assert.equal(out.length, 1);
  assert.equal(out[0].peak, -9);
});

test("spectrumAt skips bad pixels and sorts by wavelength", () => {
  const frames = [{ id: "a" }, { id: "b" }, { id: "c" }];
  const mk = (um, v, bad) => ({ n: 2, wavelength_um: um, mjd: 1, img: new Float32Array([v, 0, 0, 0]), badArr: new Uint8Array([bad, 0, 0, 0]) });
  const payloads = new Map([["a", mk(2.0, 5, 0)], ["b", mk(1.0, 3, 0)], ["c", mk(1.5, 9, 1)]]);
  const s = spectrumAt(0, 0, frames, payloads);
  assert.deepEqual(s.map((p) => p.um), [1.0, 2.0]);
  assert.deepEqual(s.map((p) => p.value), [3, 5]);
});

test("ssoAt moves linearly", () => {
  const o = { x: 5, y: 5, dx_per_hr: 10, dy_per_hr: -2 };
  const p = ssoAt(o, 100, 100 + 1 / 24);
  near(p.x, 15); near(p.y, 3);
});

test("pairFor picks closest wavelength at least 1 h apart", () => {
  const frames = [{ id: "cur" }, { id: "a" }, { id: "b" }, { id: "soon" }];
  const payloads = new Map([
    ["cur", { wavelength_um: 1.40, mjd: 100 }],
    ["a", { wavelength_um: 1.41, mjd: 101 }],
    ["b", { wavelength_um: 1.60, mjd: 102 }],
    ["soon", { wavelength_um: 1.40, mjd: 100.01 }], // < 1 h apart
  ]);
  const r = pairFor("cur", frames, payloads);
  assert.equal(r.before, "a");
  near(r.deltaUm, 0.01);
  assert.equal(r.warn, false);
});

test("pairFor warns when only distant colours exist", () => {
  const frames = [{ id: "cur" }, { id: "b" }];
  const payloads = new Map([["cur", { wavelength_um: 1.4, mjd: 100 }], ["b", { wavelength_um: 1.6, mjd: 102 }]]);
  const r = pairFor("cur", frames, payloads);
  assert.equal(r.before, "b");
  assert.equal(r.warn, true);
});

test("pairFor returns null with nothing to pair", () => {
  assert.equal(pairFor("cur", [{ id: "cur" }], new Map([["cur", { wavelength_um: 1, mjd: 1 }]])), null);
});

test("diffSigma zero for identical, NaN on bad", () => {
  const a = new Float32Array([1, 2, 3]), s = new Float32Array([1, 1, 1]);
  const badA = new Uint8Array([0, 1, 0]), badB = new Uint8Array(3);
  const d = diffSigma(a, a, s, s, badA, badB);
  assert.equal(d[0], 0); assert.ok(Number.isNaN(d[1])); assert.equal(d[2], 0);
  const d2 = diffSigma(new Float32Array([4]), new Float32Array([1]), new Float32Array([2]), new Float32Array([1]), new Uint8Array(1), new Uint8Array(1));
  near(d2[0], 3 / Math.sqrt(5));
});

test("nearestKnown within radius only", () => {
  const sso = [{ name: "rock", x: 10, y: 10 }];
  const stars = [{ source_id: "s", x: 20, y: 20 }];
  assert.equal(nearestKnown(11, 10, sso, stars).name, "rock");
  assert.equal(nearestKnown(20, 21, sso, stars).source_id, "s");
  assert.equal(nearestKnown(15, 15, sso, stars), null);
});

const near = (a, b, tol = 1e-3) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b}`);

test("parseRA", () => {
  assert.equal(parseRA("150"), 150);
  near(parseRA("10h00m00s"), 150);
  near(parseRA("10:00:00"), 150);
  near(parseRA("10 00 00"), 150);
  assert.equal(parseRA("abc"), null);
  assert.equal(parseRA("361"), null);
  assert.equal(parseRA(""), null);
});

test("parseDec", () => {
  near(parseDec("+02:12:00"), 2.2);
  near(parseDec("-41d38m"), -41.6333);
  near(parseDec("-00:30:00"), -0.5);
  assert.equal(parseDec("2.2"), 2.2);
  assert.equal(parseDec("91"), null);
  assert.equal(parseDec("north"), null);
});

test("stretch ignores bad pixels", () => {
  const img = Float32Array.from({ length: 100 }, (_, i) => i);
  const bad = new Uint8Array(100);
  const a = stretch(img, bad);
  assert.ok(a.lo < 50 && 50 < a.hi);
  img[0] = 1e9; bad[0] = 1;
  const b = stretch(img, bad);
  assert.ok(b.hi < 1e6);
});

test("stretch keeps a bright galaxy core inside the range", () => {
  // noisy sky (values ~0..1) with a smooth bright core peaking at 200 over ~4% of pixels
  const n = 50, img = new Float32Array(n * n), bad = new Uint8Array(n * n);
  for (let i = 0; i < n * n; i++) {
    const x = i % n - 25, y = Math.floor(i / n) - 25;
    img[i] = ((i * 7919) % 100) / 100 + 200 * Math.exp(-(x * x + y * y) / 8);
  }
  const s = stretch(img, bad);
  assert.ok(s.hi > 100, `core should not clip: hi=${s.hi}`);
  assert.ok(s.soft > 0 && s.soft < 2, `knee near the noise level: soft=${s.soft}`);
});

test("orderLoad newest burst first, time order within", () => {
  const frames = [
    { id: "a", burst: 0, mjd: 1 }, { id: "b", burst: 0, mjd: 2 },
    { id: "c", burst: 1, mjd: 200 }, { id: "d", burst: 1, mjd: 199 },
  ];
  assert.deepEqual(orderLoad(frames, [{ id: 0 }, { id: 1 }]), ["d", "c", "a", "b"]);
});

test("decodeF32 roundtrip", () => {
  const b64 = Buffer.from(new Float32Array([1.5, -2]).buffer).toString("base64");
  assert.deepEqual(Array.from(decodeF32(b64)), [1.5, -2]);
});

test("wavelengthColor ends", () => {
  assert.equal(wavelengthColor(0.75), "hsl(240, 70%, 50%)");
  assert.equal(wavelengthColor(5.0), "hsl(0, 70%, 50%)");
});

test("onImage drops markers that sit outside the image or on blank (NaN) pixels", () => {
  const n = 3, img = new Float32Array([1, 1, NaN, 1, 1, NaN, 1, 1, NaN]); // right column blank
  const objs = [{ x: 0, y: 0 }, { x: 2, y: 1 }, { x: 1.4, y: 2.2 }, { x: -2, y: 1 }, { x: 1, y: 7 }];
  assert.deepEqual(onImage(objs, img, n), [{ x: 0, y: 0 }, { x: 1.4, y: 2.2 }]);
});

test("brightest keeps the N lowest-magnitude stars", () => {
  const s = [{ gmag: 14 }, { gmag: 9 }, { gmag: 12 }];
  assert.deepEqual(brightest(s, 2).map((x) => x.gmag), [9, 12]);
});

import { gridToSky, skyToGrid, flipbookFov } from "./logic.js";

test("wide-view grid <-> sky matches astropy", () => {
  const g = { ra0: 10.485246, dec0: 41.483455, n: 2797, pixel_deg: 6.15 / 3600 };
  const ref = [[100, 2500, 13.530863, 43.324937], [1398, 1398, 10.485246, 41.483455], [2700, 50, 7.620486, 39.146777]];
  for (const [x, y, ra, dec] of ref) {
    const [r, d] = gridToSky(g, x, y);
    assert.ok(Math.abs(r - ra) < 1e-5 && Math.abs(d - dec) < 1e-5, `${x},${y} -> ${r},${d}`);
    const [bx, by] = skyToGrid(g, ra, dec);
    assert.ok(Math.abs(bx - x) < 0.01 && Math.abs(by - y) < 0.01, `round trip ${bx},${by}`);
  }
});

test("gridToSky wraps RA across 0", () => {
  const g = { ra0: 0.1, dec0: 0, n: 101, pixel_deg: 0.01 };
  const [ra] = gridToSky(g, 100, 50); // 50 px west of centre = 0.5 deg lower RA
  assert.ok(Math.abs(ra - 359.6) < 1e-4, String(ra));
});

test("flipbookFov picks the largest size that fits on screen, capped at 0.5", () => {
  assert.equal(flipbookFov(0.02), 0.05); // never smaller than the smallest choice
  assert.equal(flipbookFov(0.12), 0.1);
  assert.equal(flipbookFov(0.24), 0.2);
  assert.equal(flipbookFov(0.45), 0.2);  // 0.5 would spill off screen
  assert.equal(flipbookFov(3.5), 0.5);
});

import { visitGroups, stackPayloads } from "./logic.js";

test("visitGroups splits on 12 h gaps and caps a visit at 1 day", () => {
  const fr = (id, mjd) => ({ id, mjd });
  // a: two frames 1 h apart; gap of 2 days; b: continuous deep-style frames every 6 h for 2.5 days
  const frames = [fr("a1", 100), fr("a2", 100.04), ...[0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5].map((d, i) => fr(`b${i}`, 102 + d))];
  const g = visitGroups(frames);
  assert.deepEqual(g.map((x) => x.ids.length), [2, 5, 5, 1]); // 1-day cap is inclusive
  assert.equal(g[0].key, "a1"); // stable key = first frame
});

test("stackPayloads is a noise-weighted mean that skips bad pixels", () => {
  const P = (img, sig, bad) => ({ n: 2, img: Float32Array.from(img), sig: Float32Array.from(sig), badArr: Uint8Array.from(bad), wavelength_um: 1, mjd: 5 });
  const s = stackPayloads([
    P([10, 10, 1, 7], [1, 1, 1, 1], [0, 0, 0, 1]),
    P([20, 20, 3, 9], [1, 2, 1, 1], [0, 0, 0, 1]),
  ]);
  assert.equal(s.img[0], 15);                         // equal noise -> plain mean
  assert.ok(Math.abs(s.img[1] - 12) < 1e-6);          // 2nd frame 4x noisier variance -> weight 1/4
  assert.ok(Math.abs(s.sig[0] - Math.SQRT1_2) < 1e-6); // noise drops by sqrt(2)
  assert.equal(s.badArr[3], 1);                        // bad everywhere stays bad...
  assert.equal(s.img[3], 8);                           // ...but still drawn (plain mean)
});

import { withRawPatch } from "./logic.js";

test("withRawPatch restores NASA's original values without touching the clean image", () => {
  const clean = Float32Array.from([1, 2, 3, 4]);
  const raw = withRawPatch(clean, Int32Array.from([1, 3]), Float32Array.from([900, -50]));
  assert.deepEqual([...raw], [1, 900, 3, -50]);
  assert.deepEqual([...clean], [1, 2, 3, 4]);
});
