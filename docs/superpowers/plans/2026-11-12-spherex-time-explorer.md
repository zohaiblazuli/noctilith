# SPHEREx Time Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A web tool where a user enters RA/Dec and plays every SPHEREx frame of that patch as a flipbook, compares frames, and checks whether anything that changed is already known.

**Architecture:** A FastAPI backend queries IRSA SIA for frames. It fetches cutouts (limited concurrency, retries, disk cache), reprojects each one onto a shared north-up grid centred on the target, and returns small JSON payloads. It also proxies SkyBoT and Gaia and converts their positions into grid pixels. A static, no-build HTML/JS frontend draws frames on `<canvas>`.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, httpx, astropy, reproject, numpy, scipy, pytest. Vanilla JS (ES modules); `node --test` for the pure-logic JS.

**Spec:** `docs/superpowers/specs/2026-11-12-spherex-time-explorer-design.md`. Verified API facts are in `docs/RESEARCH.md`.

## Global Constraints

- SIA collection name lives in config, default `spherex_qr2`; never hard-code it elsewhere.
- Pixel scale **6.15″**. Grid size `N = round(fov_deg*3600/6.15)`, north up, east left (RA increases to the left).
- Input limits: `0 ≤ ra < 360`, `-90 ≤ dec ≤ 90`, `0.02 ≤ fov ≤ 0.5` (degrees); default fov `0.1`. Out of range → HTTP 422.
- IRSA fetches: at most **6** concurrent, timeout 60 s, retry up to 4 times on 5xx/timeout with backoff 2/4/8 s.
- Everything fetched from outside goes through the disk cache in `cache/` (git-ignored).
- UI copy: plain English. Anything not in a catalog is called a **"candidate"**, never a "discovery".
- URL params: `?ra=&dec=&fov=&mode=play|compare&frame=<obs_id>`. Loading a URL with ra/dec auto-runs the search.

## Review Focus

1. **IRSA slow or down (503 / timeout) mid-load:** frames that did load keep playing; failed frames show as greyed timeline tiles with a retry option, never a frozen spinner. Test in Task 3.
2. **Spot with no SPHEREx coverage, or coverage only at the cutout edge:** a clear "no SPHEREx images here yet" message. Frames whose cutout is mostly NaN (more than 50%) are dropped. Tests in Tasks 2 and 3.
3. **Coordinates near RA 0/360 and near the poles:** the grid and overlays must stay correct (wrap-around and cos(dec)). Test in Task 4.
4. **Different wavelengths compared as if they were changes:** auto-pairing must never pair frames more than 0.03 µm apart without a visible warning. Test in Task 7.
5. **Users typing RA in h:m:s or Dec in d:m:s:** accept both sexagesimal and decimal input, and show a friendly error for anything else. Test in Task 6.

## File Structure

```
server/config.py        settings (collection, cache dir, concurrency, limits)
server/grid.py          shared target grid: make_grid_wcs, sky_to_pixel
server/sia.py           query + parse SIA, group into bursts
server/cache.py         disk JSON cache
server/cutout.py        fetch cutout (retry/limits) + process into FramePayload
server/known.py         SkyBoT + Gaia → grid pixels
server/app.py           FastAPI routes + static web/
web/index.html, web/style.css
web/logic.js            pure functions (parse coords, stretch, pairing, spectrum) – node-tested
web/app.js              state, API calls, URL sync, timeline, play loop
web/viewer.js           canvas drawing + overlays + click → pixel
web/panel.js            side panel, spectrum plot
web/guide.js            guide strip
web/demo-spots.json     demo menu entries
scripts/find_demo_spots.py, scripts/precache.py
tests/fixtures/         sia_sample.csv, cutout_small.fits (PSF stripped)
tests/test_*.py, web/logic.test.mjs
```

---

### Task 1: Scaffold, config, grid, fixtures

**Files:**
- Create: `server/__init__.py`, `server/config.py`, `server/grid.py`, `requirements.txt`, `tests/conftest.py`, `tests/test_grid.py`, `tests/fixtures/sia_sample.csv`, `tests/fixtures/cutout_small.fits`
- Modify: `.gitignore` (add `!tests/fixtures/*.fits`)

**Interfaces:**
- Produces: `config.SETTINGS` with `collection: str = "spherex_qr2"`, `cache_dir: Path = Path("cache")`, `max_concurrency: int = 6`, `pixel_arcsec: float = 6.15`, `fov_min=0.02`, `fov_max=0.5`; all overridable through `SPHEREX_*` env vars.
- Produces: `grid.make_grid_wcs(ra: float, dec: float, fov: float) -> tuple[astropy.wcs.WCS, int]` (WCS, N) and `grid.sky_to_pixel(wcs, ra: np.ndarray, dec: np.ndarray) -> tuple[np.ndarray, np.ndarray]` (0-based x, y; y up).

- [ ] **Step 1:** Create the fixtures. Copy `recon/sia.csv` to `tests/fixtures/sia_sample.csv`. Write `cutout_small.fits` from `recon/cut_test.fits` with every HDU except `PSF` (a one-off snippet; it should be under 100 KB).
- [ ] **Step 2:** Write the failing tests in `tests/test_grid.py`:
  - `test_grid_size`: `make_grid_wcs(150, 2.2, 0.1)[1] == 59` (`round(360/6.15)`).
  - `test_center_maps_to_middle`: `sky_to_pixel` of (150, 2.2) gives approximately ((N-1)/2, (N-1)/2), within 0.01.
  - `test_east_is_left`: RA + 0.01° gives a smaller x than the centre.
  - `test_ra_wrap`: grid at ra=359.99; a point at ra=0.005 gives x < centre and is inside the grid.
  - `test_near_pole`: grid at dec=89.9, fov 0.1; a point 0.02° north gives y > centre.
- [ ] **Step 3:** `pytest tests/test_grid.py -v` → FAIL (import error).
- [ ] **Step 4:** Implement `config.py` and `grid.py`: a TAN WCS with `cdelt = [-p, p]` in degrees and `crpix = (N+1)/2`; `sky_to_pixel` uses `wcs.world_to_pixel_values`. Write `requirements.txt`: fastapi, uvicorn[standard], httpx, astropy, reproject, numpy, scipy, pytest.
- [ ] **Step 5:** `pytest tests/test_grid.py -v` → 5 passed.
- [ ] **Step 6:** Commit: `feat: config, target grid, test fixtures`.

### Task 2: SIA query + bursts

**Files:** Create `server/sia.py`, `tests/test_sia.py`

**Interfaces:**
- Consumes: `SETTINGS.collection`.
- Produces: dataclass `FrameMeta(obs_id: str, detector: int, mjd: float, iso: str, access_url: str, band_um: tuple[float, float], burst: int)` with `.to_dict()`. Also `parse_sia_csv(text: str) -> list[FrameMeta]` (sorted by mjd, burst=-1), `assign_bursts(frames, gap_days=10.0) -> list[dict]` (sets `.burst`; returns `[{id, start_iso, end_iso, count}]`), and `async query_frames(client: httpx.AsyncClient, ra, dec, fov) -> list[FrameMeta]`.

- [ ] **Step 1:** Write the failing tests:
  - `test_parse_fixture`: 5 frames from the fixture, sorted by mjd; the first has `detector == 2`, an `access_url` starting with `https://irsa.ipac.caltech.edu/ibe/`, and `band_um ≈ (1.1033, 1.6499)`.
  - `test_bursts`: synthetic mjds `[0, 0.1, 1.5, 180, 181]` → bursts `[0, 0, 0, 1, 1]`, 2 burst dicts, counts `[3, 2]`.
  - `test_empty_csv`: header only → `[]`.
  - `test_query_url` (httpx `MockTransport`): the request URL contains `COLLECTION=spherex_qr2`, `POS=circle 150.0 2.2 0.001`, and `RESPONSEFORMAT=CSV`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with the csv module. `detector` comes from `energy_bandpassname` "SPHEREx-D2" → 2. `band_um` comes from em_min/em_max × 1e6. Use the search radius 0.001° (the frame must contain the centre).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat: SIA frame search and burst grouping`.

### Task 3: Cache + cutout fetch + processing

**Files:** Create `server/cache.py`, `server/cutout.py`, `tests/test_cutout.py`, `tests/test_cache.py`

**Interfaces:**
- Produces: `cache.key(*parts) -> str` (sha1 hex), `cache.get_json(key) -> dict | None`, `cache.put_json(key, obj) -> None` (atomic write: temp file, then rename).
- Produces: `async fetch_cutout(client, access_url, ra, dec, fov, sem: asyncio.Semaphore) -> bytes`, which requests `{access_url}?center={ra},{dec}&size={fov*1.5}deg` (the margin covers rotated frames). Raises `CutoutError` after retries.
- Produces: `process_cutout(fits_bytes: bytes, ra, dec, fov) -> dict | None` returning `{"n": N, "mjd": float, "wavelength_um": float, "image": b64 float32 LE (N*N, row 0 = bottom), "sigma": b64 float32 (sqrt variance, reprojected), "bad": b64 uint8 (1 = flagged or NaN), "coverage": float}`. Returns `None` when coverage < 0.5.
- Produces: `async get_frame(client, meta: FrameMeta, ra, dec, fov, sem) -> dict | None`, which checks the cache first. The cache key is `(obs_id, detector, round(ra,5), round(dec,5), fov)`.

- [ ] **Step 1:** Write the failing tests:
  - `test_process_fixture`: `process_cutout(fixture_bytes, 150.0, 2.2, 0.05)` gives `n == 29`, `1.1 < wavelength_um < 1.7`, `coverage > 0.9`, a decoded image of length 29*29, and a median of the finite image within ±1e-3 of 0 (background subtracted).
  - `test_low_coverage_returns_none`: the target is 0.1° off the fixture's footprint → `None`.
  - `test_retry_then_success`: MockTransport returns 503 twice, then 200 → bytes returned, 3 calls (patch the backoff sleep to 0).
  - `test_retry_exhausted`: always 503 → `CutoutError`.
  - `test_cache_roundtrip`: put then get gives an equal dict; a missing key gives `None`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Read the sky WCS from `IMAGE`, silencing the SIP and FITSFixed warnings. Get the wavelength at the target pixel from `WCS(hdr, fobj=hdul, key="W")` (see RESEARCH.md). Reproject IMAGE and VARIANCE with `reproject_interp` onto `make_grid_wcs`. Reproject FLAGS with nearest neighbour (`order=0`) and treat it as bad if `flags & BAD_MASK`, where `BAD_MASK` is a module constant. Read the flag bit names from the FLAGS header comments in the fixture; exclude source-mask bits so stars don't count as bad. Subtract the nanmedian.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat: cached cutout fetch and reprojection`.

### Task 4: Known objects (SkyBoT, Gaia)

**Files:** Create `server/known.py`, `tests/test_known.py`

**Interfaces:**
- Produces: `async known_sso(client, ra, dec, fov, mjd) -> list[dict]` with items `{name, cls, vmag, x, y, dx_per_hr, dy_per_hr}` (grid pixels at `mjd`; pixel rates from dRA·cos(dec) and dDec in arcsec/hr ÷ 6.15, with x negated for east-left). Search radius = `fov*0.75 + 0.1` (covers objects that drift into the field during a burst). Cached by `(round(ra,4), round(dec,4), fov, round(mjd,2))`.
- Produces: `async known_stars(client, ra, dec, fov, gmax=17.0) -> list[dict]` with items `{source_id, gmag, x, y}`, cached. If the TAP request fails, returns `[]` and logs a warning; it never raises to the route.
- Produces: `parse_skybot_text(text: str) -> list[dict]` (with ra/dec in degrees; the RA input is in hours h m s).

- [ ] **Step 1:** Write the failing tests:
  - `test_parse_skybot_fixture`: `recon/sk.txt` copied to `tests/fixtures/skybot_sample.txt` → 5+ objects; the first is named "2007 UK86", with ra ≈ 150.0092°, dec ≈ 2.2154°, vmag 23.4, dra 54.641.
  - `test_sso_pixels`: for the parsed first object with the grid at (150, 2.2, 0.1), x is less than the centre (it's east) and the rates match `dra/6.15` within 1e-6 (with the sign flipped for x).
  - `test_stars_failure_returns_empty`: MockTransport 500 → `[]`.
  - `test_wrap_ra_skybot`: a grid at ra=0.01 with an object at ra=359.995 lands inside the grid.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. SkyBoT URL as in RESEARCH.md, with `-ep` = JD = mjd + 2400000.5. Gaia: VizieR TAP sync, `FORMAT=csv`, ADQL `SELECT Source,RA_ICRS,DE_ICRS,Gmag FROM "I/355/gaiadr3" WHERE 1=CONTAINS(POINT('ICRS',RA_ICRS,DE_ICRS),CIRCLE('ICRS',{ra},{dec},{fov*0.75})) AND Gmag<{gmax}`, URL-encoded with httpx params, not by hand.
- [ ] **Step 4:** Run → PASS. Then run one live check, `python -c` calling `known_stars` for (150, 2.2, 0.1), and confirm it returns more than 0 stars. Record the result in RESEARCH.md (it is unverified there now).
- [ ] **Step 5:** Commit: `feat: SkyBoT and Gaia overlays in grid pixels`.

### Task 5: API routes + static serving

**Files:** Create `server/app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces these HTTP routes:
  - `GET /api/frames?ra&dec&fov=0.1` → `{"target": {ra, dec, fov, n}, "bursts": [...], "frames": [FrameMeta.to_dict()]}`
  - `GET /api/frame?obs_id&ra&dec&fov` → the `process_cutout` dict plus `obs_id`, or 404 `{"detail": "no coverage"}`, or 502 `{"detail": "IRSA unavailable, try again"}`
  - `GET /api/known/sso?ra&dec&fov&mjd` → list
  - `GET /api/known/stars?ra&dec&fov` → list
  - `/` → serves `web/` (StaticFiles, html=True)
- One shared `httpx.AsyncClient` and `asyncio.Semaphore(SETTINGS.max_concurrency)` live in the app lifespan. The frame list per target is cached in memory, so `/api/frame` looks up `access_url` by obs_id.

- [ ] **Step 1:** Write the failing tests (TestClient, with the module functions monkeypatched):
  - `test_frames_ok`: patched `query_frames` → 200 with the keys target/bursts/frames.
  - `test_bad_input`: `ra=400` → 422; `fov=1` → 422.
  - `test_frame_unavailable`: patched `get_frame` raises `CutoutError` → 502 with the exact detail text above.
  - `test_frame_no_coverage`: patched to return `None` → 404.
  - `test_index_served`: `/` → 200 and contains `<canvas`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Add a stub `web/index.html` containing a `<canvas>`; Task 6 replaces it.
- [ ] **Step 4:** Run → PASS. Live smoke test: `uvicorn server.app:app --port 8000`, then `curl "localhost:8000/api/frames?ra=150&dec=2.2"` should report about 213 frames. Fetch one `/api/frame` and check it returns in under 20 s.
- [ ] **Step 5:** Commit: `feat: API routes`. Run `/handoff`.

### Task 6: Frontend shell, Play mode, timeline, URL sync

**Files:** Create `web/index.html`, `web/style.css`, `web/logic.js`, `web/logic.test.mjs`, `web/app.js`, `web/viewer.js`

**Interfaces:**
- Produces (`logic.js`): `parseRA(str) -> number|null` (accepts `150.0`, `10h00m00s`, `10:00:00` → degrees); `parseDec(str) -> number|null` (`2.2`, `+02:12:00`, `-41d38m`); `decodeF32(b64) -> Float32Array`; `decodeU8(b64)`; `stretch(img, bad) -> {lo, hi}` (zscale-like: median − 2·MAD to median + 10·MAD over good pixels); `wavelengthColor(um) -> css string` (0.75 µm = blue … 5 µm = red, HSL 240→0); `orderLoad(frames, bursts) -> obs_id[]` (newest burst first, time order within a burst).
- Produces (`viewer.js`): `class Viewer(canvas)` with `.setFrame(frame, payload)`, `.setOverlays({sso:[], stars:[], boxes:[]})`, `.onPixelClick(cb(x, y))`, zoom (wheel) and pan (drag). Draws images N×N, scaled to fit with nearest-neighbour pixels (`imageSmoothingEnabled=false`).
- Produces (`app.js`): a global `state = {target, frames, bursts, payloads: Map, current, mode}`; `loadTarget(ra, dec, fov)`; a URL sync that writes the params from Global Constraints with `history.replaceState`.

- [ ] **Step 1:** Write the failing `web/logic.test.mjs` (`node --test web/`):
  - parseRA: `"150"`→150, `"10h00m00s"`→150, `"10:00:00"`→150, `"abc"`→null, `"361"`→null.
  - parseDec: `"+02:12:00"`→2.2, `"-41d38m"`→-41.6333 (±1e-3), `"91"`→null.
  - stretch: array 0..99 with no bad pixels → lo < 50 < hi; bad pixels are ignored (set index 0 to 1e9 and mark it bad → hi unchanged).
  - orderLoad: 2 bursts → every obs_id of burst 1 comes before burst 0.
  - decodeF32 roundtrip on `[1.5, -2]`.
- [ ] **Step 2:** `node --test web/` → FAIL.
- [ ] **Step 3:** Implement `logic.js` → tests PASS.
- [ ] **Step 4:** Build the page: top bar (RA, Dec, FOV select 0.05/0.1/0.2/0.5, Go, Share link that copies the URL, demo menu filled from `web/demo-spots.json`, empty array for now), the viewer canvas, controls (play/pause/prev/next, speed 1–8 fps, burst select, detector filter "All / D1…D6" that hides non-matching tiles from play), and the timeline strip with one tile per frame tinted by `wavelengthColor` (band midpoint until the payload arrives, then the exact value). Tile states: loading (pulsing), ready, failed (grey with ↻ to retry one frame). Load frames 6 at a time in `orderLoad` order. Show the first ready frame immediately. The play loop skips frames that aren't ready. With 0 frames, show: "No SPHEREx images cover this spot yet. Try a demo spot." The frame label shows the date/time and "λ = 1.41 µm".
- [ ] **Step 5:** Verify in the browser at `http://localhost:8000/?ra=150&dec=2.2`: the first frame appears within about 20 s, the tiles fill in, play animates, the URL updates, a reload restores the view, and the console shows no errors. At mobile width (375 px) there is no horizontal scroll.
- [ ] **Step 6:** Commit: `feat: play mode, timeline, URL sync`. Run `/handoff`.

### Task 7: Overlays, click panel, Compare mode

**Files:** Create `web/panel.js`. Modify `web/app.js`, `web/viewer.js`, `web/logic.js`, `web/logic.test.mjs`.

**Interfaces:**
- Consumes: `/api/known/*`, `Viewer.setOverlays`.
- Produces (`logic.js`): `ssoAt(obj, mjdRef, mjd) -> {x, y}` (linear motion: `x + dx_per_hr*(mjd-mjdRef)*24`); `pairFor(frame, frames, payloads) -> {before, deltaUm, warn}` (picks a ready frame ≥1 h apart with minimal |Δλ|, and sets `warn = deltaUm > 0.03`); `diffSigma(a, b, sa, sb, badA, badB) -> Float32Array` (`(a−b)/sqrt(sa²+sb²)`, NaN where either is bad); `nearestKnown(x, y, sso, stars, r=2) -> obj|null`.
- Produces (`panel.js`): `showSpot({x, y, ra, dec, value, bad, known})`.

- [ ] **Step 1:** Add failing tests: `ssoAt` moves 10 px in 1 h at 10 px/hr; `pairFor` picks λ 1.41 over 1.60 for a 1.40 frame and sets `warn=false`, and `warn=true` when the only candidate is 0.2 µm away; `diffSigma` of identical inputs is all zeros with NaN at bad pixels; `nearestKnown` returns null beyond r.
- [ ] **Step 2:** `node --test web/` → FAIL. Implement → PASS.
- [ ] **Step 3:** Overlays. Fetch SSO once per burst (mjd = burst midpoint) and stars once per target. Draw orange circles at `ssoAt` for the current frame's mjd with name labels, and blue circles for stars with G < 15 only (to avoid clutter), with a legend. A clicked pixel shows the panel: RA/Dec (pixel → sky via the target centre and 6.15″ TAN; a small-angle approximation is fine), the value, "flagged" if bad, and "Known: <name> (asteroid)" / "Gaia star G=…" / "Not in Gaia or known-asteroid lists → candidate. Check the flags and other frames before getting excited."
- [ ] **Step 4:** Compare mode. A Play | Compare toggle (it updates the `mode` URL param). In Compare, the main area shows three canvases: before, after (current), and difference. The difference uses `diffSigma`, a diverging colour map clamped at ±5σ, red = brighter now. The before frame comes from `pairFor` and can be overridden by shift-clicking a timeline tile. Show "Δλ = 0.01 µm" and a yellow warning when `warn` is true. Clicking any of the three panels feeds the same side panel.
- [ ] **Step 5:** Verify in the browser at the demo coordinates: SSO circles move between frames within a burst, the panel text is right for a star click and a blank-sky click, Compare shows the warning on a forced bad pair, and the console is clean.
- [ ] **Step 6:** Commit: `feat: known-object overlays, side panel, compare mode`. Run `/handoff`.

### Task 8: Demo spots + precache

**Files:** Create `scripts/find_demo_spots.py`, `scripts/precache.py`. Modify `web/demo-spots.json`.

**Interfaces:**
- Consumes: `server.sia`, `server.known`, `server.cutout.get_frame` (same cache).
- Produces: `demo-spots.json` entries `{label, ra, dec, fov, note}`; `python scripts/precache.py` warms the cache for every entry (all frames + known objects) and prints `label: X/Y frames cached`.

- [ ] **Step 1:** `find_demo_spots.py`: for 10–20 trial positions within 5° of the ecliptic, run `query_frames`, take each burst's midpoint, and call SkyBoT with radius 1° keeping V < 17. Keep (position, object) pairs where the object stays inside a 0.2° field during the burst and the burst has ≥ 6 frames. Print the top 5 by brightness. Also always include the north ecliptic pole (270, 66.56, many frames) and (150, 2.2).
- [ ] **Step 2:** Run it. Put 3–5 spots in `demo-spots.json` with plain-English notes (for example: "A main-belt asteroid crosses this field over 2 days in Nov 2025").
- [ ] **Step 3:** Run `precache.py` in the background (it can take a long time). Check that the summary shows ≥ 90% of frames cached per spot.
- [ ] **Step 4:** Verify in the browser that each demo spot loads fully within 3 s from cache, and that the asteroid is visibly moving in at least one of them.
- [ ] **Step 5:** Commit: `feat: demo spots`. Run `/handoff`.

### Task 9 (stretch): Spectrum of the clicked spot

**Files:** Modify `web/logic.js`, `web/logic.test.mjs`, `web/panel.js`.

**Interfaces:** `spectrumAt(x, y, frames, payloads) -> [{um, value, mjd}]` (good pixels only, sorted by um).

- [ ] **Step 1:** Failing test: two payloads, one bad at (x, y) → 1 point, with the correct um.
- [ ] **Step 2:** Implement → PASS. Draw it in the panel as a small canvas scatter plot (x = µm, y = MJy/sr) titled "Brightness vs colour (all visits)", with a one-line explanation.
- [ ] **Step 3:** Verify in the browser that a star click shows a spectrum with 20 or more points. Commit: `feat: spectrum on click`.

### Task 10 (stretch): Automatic candidate boxes

**Files:** Modify `web/logic.js`, `web/logic.test.mjs`, `web/app.js`.

**Interfaces:** `findChanges(diff: Float32Array, n, thresh=5, minPix=2) -> [{x, y, peak}]` (connected components on |σ| > thresh).

- [ ] **Step 1:** Failing tests: a synthetic 10×10 diff with one 2-pixel blob at σ = 8 → 1 box at its centre; a single-pixel spike → 0 boxes.
- [ ] **Step 2:** Implement → PASS. In Compare mode, draw red boxes for changes with no `nearestKnown` match within 2 px, labelled "candidate".
- [ ] **Step 3:** Verify on a demo spot that the known asteroid is *not* boxed (it's matched) and that boxes are rare on quiet fields. Commit: `feat: candidate change boxes`.

### Task 11 (stretch): Guide strip + Aladin background

**Files:** Create `web/guide.js`. Modify `web/index.html`, `web/app.js`.

- [ ] **Step 1:** Guide strip with steps ①–⑤ from the spec. Each step advances on its event (target loaded → played → pixel clicked → panel shown → share clicked). A ✕ hides it and stores that in `localStorage` (wrapped in try/catch). It is shown by default.
- [ ] **Step 2:** Under "Background layer", embed an Aladin Lite v3 view (pinned CDN version) centred on the target, with the same fov, synced on load. Offer the surveys 2MASS, AllWISE and Gaia DR3 density. It is optional and collapsed by default.
- [ ] **Step 3:** Verify in the browser. Commit: `feat: guide strip and Aladin context view`.

### Task 12: README, run script, final check

**Files:** Create `README.md`, `run.ps1`.

- [ ] **Step 1:** README in plain English: what it is, how to run it (`pip install -r requirements.txt`, `python scripts/precache.py`, `uvicorn server.app:app`), data credits (NASA/IPAC IRSA SPHEREx QR2, IMCCE SkyBoT, ESA Gaia via CDS VizieR, Aladin Lite), and known limits. `run.ps1` starts uvicorn and opens the browser.
- [ ] **Step 2:** `pytest -q` and `node --test web/` both pass. Do a full demo run-through on all demo spots.
- [ ] **Step 3:** Commit: `docs: README and run script`. Run `/handoff`.
