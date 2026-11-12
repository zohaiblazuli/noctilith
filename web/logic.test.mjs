import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseRA, parseDec, stretch, orderLoad, decodeF32, wavelengthColor,
  ssoAt, pairFor, diffSigma, nearestKnown, spectrumAt,
} from "./logic.js";

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
