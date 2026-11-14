# Status: last updated 2026-11-14 (Day 3)

## Phase
All plan tasks built, reviewed and merged into `main`. Public repo: https://github.com/zohaiblazuli/noctilith (default branch `main`). The review's 4 Important findings are fixed; minors are deferred (see DECISIONS.md).

## Done
- Backend: SIA search, cached and reprojected cutouts (6 parallel requests, retries), SkyBoT and Gaia (ESA archive).
- Page: Play mode, timeline, URL sync, overlays, click panel, spectrum, Compare mode with candidate boxes, guide strip, demo spots.
- README, `run.ps1`, `setup.bat` (makes `.venv` + installs requirements; `start.bat` uses it). Tests: 40 pytest, 21 node.
- Speed: frames now come from NASA's AWS mirror via byte-range slices (~1.9 frames/s vs ~0.3), with the IRSA cutout as fallback. Concurrency 12.
- Data release fix (2026-11-14): IRSA retired `spherex_qr2`; now searches `spherex_dr1` (Jul 2025–Jan 2026) + `spherex_qr3` (Jul 2026). Demo spot 1 shows 321 frames over 5 visits. DR1 compresses FLAGS; slicer now decompresses it (fixed random red speckle). Flagged pixels now drawn with real values, gentler asinh stretch (M31 core no longer clips).
- Wide view (2026-11-14): Go opens a whole SPHEREx frame north-up (`server/overview.py`, `web/wide.js`); zoom keeps full quality; "Play this area over time" loads the yellow box as the flipbook. First build ~18 s, then cached in `cache/overview/`.
- Research pass (2026-11-14): ghost/streak/bloom/snowball/halo pixels now bad for analysis; "One image per visit" stacking (WiseView-style); deep-survey collections added, sampled to `frame_budget` 720 (120 days); frame lists reused 12 h (`sia_ttl_hours`). New demo spot: NEP deep field.
- Wide view plays over time (2026-11-14): ▶ animates ~1° around screen centre, one frame per visit on the wide grid (`server/visits.py`); ~30 s for M31's 34 visits. Play tab renamed Detail. Andromeda demo spot opens the wide view.
- Junk pixels (2026-11-14): `server/junk.py` paints NASA-flagged TRANSIENT/SUR_ERROR/NONFUNC/MISSING_DATA/HOT/COLD (not OVERFLOW/OUTLIER) on the detector before reprojection; toggle in the mode bar (URL `raw=1`). Black level lowered to ~3 sigma below sky (black pixels 9.9% -> 2.0%).
- Overlays: rings only drawn on real pixels; max 150 brightest stars; "known star (Gaia)" toggle; no-data area drawn dark, not red.

## Next
1. Re-run `python scripts/precache.py` for the 5 flipbook demo spots, and open the Andromeda demo once (builds its wide view + visit images) (incl. the new NEP deep field) (old cache was QR2 files; DR1/QR3 files are new downloads).
2. Check the 4 demo spots still show their asteroid on DR1 data (the `mjd` in `web/demo-spots.json` still matches DR1 dates).
3. Optional: Aladin background (CDS is unreachable from this machine), public hosting.

## Run it
First time: double-click `setup.bat`. Then double-click `start.bat` (or `python -m uvicorn server.app:app --port 8000`), then open http://localhost:8000
Tests: `python -m pytest -q` and `node --test "web/*.test.mjs"`

## Open questions for the user
- Does the hackathon require a public URL, or is a local demo plus video enough?

## Blockers / risks
- IRSA renames collections silently (empty results, no error). If nothing loads, check `SPHEREX_COLLECTION` first.
- A new spot still takes ~2 min to fully load (241 frames), limited by this machine's ~3 MB/s link. Pre-cache demo spots anyway.
- VizieR and Aladin (CDS) are unreachable from this machine; Gaia comes from the ESA archive.
