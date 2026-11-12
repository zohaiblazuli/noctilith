# SPHEREx Time Explorer: design

Status: approved in conversation 2026-11-12 (layout and direction); written up for planning.
Context: NASA Space Apps hackathon entry, about 48 hours to finish (started 2026-11-12).

## 1. Intent: what and why

A public web tool where anyone types a sky position (RA/Dec) and sees every SPHEREx image of that patch played in time order, like a flipbook, so anything that **moves or changes** stands out.

The emotional core is **discovery**: "could I, a student or amateur astronomer, find something new?" The tool is built around the path:

> see something change → click it → is it already known? → if not, it's a *candidate* → share a link

Audience: students and amateur astronomers. They roughly know what RA/Dec means. They should never need to download FITS files, install software, or understand the instrument.

Success = in a live demo, a judge picks a spot (or a demo spot), watches the flipbook within seconds, sees known objects labelled, clicks something, and gets a clear answer.

## 2. Goals, non-goals, anti-goals

**Goals (must)**
1. RA/Dec input, plus coordinates in the URL (`?ra=150&dec=2.2&fov=0.1`) so the tool can be linked and embedded.
2. Flipbook of all SPHEREx frames of the patch, in time order, grouped into visit "bursts".
3. Compare mode: before / after / difference panels.
4. "Is it known?" overlays: known asteroids and comets at each frame's time (SkyBoT) and Gaia stars.
5. Click a spot to see its info: position, brightness, known/unknown, quality flags.
6. Demo spots that have been checked in advance and pre-cached, so the demo never waits on NASA's servers.

**Goals (should, if time allows), in priority order**
7. Spectrum of the clicked spot: brightness against wavelength, from all visits.
8. Automatic "changed, not in any catalog" red boxes.
9. Optional guide strip (onboarding steps), closable, with closed state remembered.
10. Background survey layers (WISE / 2MASS / Gaia imagery) via Aladin Lite.
11. Field-of-view choice (0.05° to 0.5°).

**Non-goals:** user accounts; full-resolution all-sky mosaics; reporting finds to the Minor Planet Center; perfect mobile layout (it must be usable, not polished); astrometric precision beyond "which known object is this".

**Anti-goals (a failure even if it technically works)**
- The demo stalls on a spinner waiting for IRSA.
- The tool calls something a "discovery" when it's an artefact. Always say "candidate" and show the quality flags.
- Colour changes (each frame sees a different wavelength) are presented as if they were real changes in brightness.
- Astronomer jargon without a plain-English tooltip.

## 3. What the data is really like (verified 2026-11-12, see docs/RESEARCH.md)

- **Search:** IRSA SIA v2 returns every SPHEREx image covering a position, with time, detector (D1–D6) and the URL to download it, in about 0.5 s.
  `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr2&POS=circle+RA+DEC+R&RESPONSEFORMAT=CSV`
- **Coverage:** a typical spot has about 200–300 frames over about 20–30 days, in bursts about 6 months apart. Spots near the ecliptic poles have about 570.
- **Cutouts:** append `?center=RA,DEC&size=0.1deg` to the image URL. A cutout takes **12–16 s** and is about **5 MB**, because it includes a 4.9 MB PSF cube. We do not need the PSF cube. IRSA sometimes returns **503**, so retry with backoff.
- **No CORS on IRSA**, so a browser can't call it directly. **SkyBoT does send CORS headers.** Gaia via VizieR TAP was not verified.
- **Each frame is a different colour.** Every pixel has its own wavelength, via a spectral WCS with key `W` read through `astropy.wcs.WCS(hdr, fobj=hdul, key="W")`. Consecutive frames in a burst step through wavelengths, for example 1.14 → 1.60 → 1.22 µm.
- Pixels are about 6.15″, so images look blocky. The FLAGS layer marks known sources as well as bad pixels, so it needs a bit-level interpretation.

## 4. How it's built (decided)

**Shape:** a small Python backend plus a static web page served by that backend. The user agreed to this ("a small server plus a web page").

**Backend: Python, FastAPI**
- `GET /api/frames?ra&dec&fov` queries SIA and returns JSON: one entry per frame with obs_id, detector, time (MJD and ISO), wavelength at the target, and a burst id.
- `GET /api/frame/{obs_id}/{detector}?ra&dec&fov` fetches the cutout. It reprojects the cutout onto a shared north-up TAN grid centred on the target, subtracts the background (zodi layer or median), and returns a small payload: float32 image, flags, variance, wavelength. The format is the builder's call; small binary or base64 JSON are both fine.
- `GET /api/known?ra&dec&fov&mjd` proxies SkyBoT and Gaia. Results are cached.
- **Cache everything on disk**, keyed by obs_id + centre + fov. Fetch from IRSA with limited concurrency (about 6 parallel requests) and retry 503s.
- **Data updates:** the SIA collection name lives in config (`spherex_qr2` today). New releases show up automatically because we query live.

**Frontend: plain HTML + JS, no build step**
- The viewer is our own `<canvas>`. Because every frame is already on the same north-up grid, overlays are simple pixel maths.
- Frames stream in progressively: show the first frames as soon as they arrive, and load one burst at a time, newest burst first.
- Layout (agreed): **A as the base, with B's compare mode and C's guide.**
  - Top bar: RA/Dec, FOV, Go, "Try a demo spot", Share link.
  - Optional guide strip: ① pick a spot → ② watch → ③ click what moved → ④ is it known? → ⑤ share. It can be closed.
  - **Play mode:** large image with zoom/pan; overlays (orange = known solar-system object, blue = Gaia star, red box = changed and not catalogued); side panel showing the clicked spot and the spectrum.
  - **Compare mode:** before / after / difference panels. Frames are picked on the timeline, with "auto-pair similar colours" on by default.
  - Timeline strip: thumbnails tinted by wavelength, grouped by burst, current frame highlighted.
  - Detector filter (default: all).

**Demo safety:** a script pre-fetches and caches 3–5 demo spots, including at least one with a known asteroid visibly moving inside a burst. The demo runs from that cache.

## 5. Left to the builder

- Exact binary payload format, colour stretch (zscale/asinh), and colour scheme.
- How the brightness of different-wavelength frames is normalised for the flipbook (for example, per-frame median/MAD scaling).
- Change-detection method (for example, difference > 5σ using VARIANCE, excluding Gaia and SkyBoT matches and flagged pixels).
- Whether S3 range reads of the full files (`nasa-irsa-spherex` bucket, public) are faster than IRSA cutouts. Worth a 30-minute spike if cutouts make the demo too slow.
- SkyBoT observer location: geocentric (`-loc=500`) is fine for main-belt objects; SPHEREx is in low Earth orbit. The builder may refine this.
- Hosting: running locally for the demo is acceptable. A free public host is a bonus.
- Choosing the demo spots.

## 6. Calls I made (Claude), not confirmed by the user

- FastAPI + plain JS with no framework, for speed of building and an easy demo.
- Our own canvas viewer as the main view; Aladin Lite only as an optional background or context layer.
- Burst-at-a-time loading, newest burst first.
- Guide strip on by default for first-time visitors.
- Demo spots are the safety net for judging.
