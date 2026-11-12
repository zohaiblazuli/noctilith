import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseRA, parseDec, stretch, orderLoad, decodeF32, wavelengthColor,
} from "./logic.js";

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
