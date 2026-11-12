# Status: last updated 2026-11-12 (Day 1)

## Phase
All plan tasks built and reviewed on branch `feat/time-explorer` (not merged yet). The review's 4 Important findings are fixed; minors are deferred (see DECISIONS.md).

## Done
- Backend: SIA search, cached and reprojected cutouts (6 parallel requests, retries), SkyBoT and Gaia (ESA archive).
- Page: Play mode, timeline, URL sync, overlays, click panel, spectrum, Compare mode with candidate boxes, guide strip, demo spots.
- README, `run.ps1`. Tests: 40 pytest, 21 node.
- Speed: frames now come from NASA's AWS mirror via byte-range slices (~1.9 frames/s vs ~0.3), with the IRSA cutout as fallback. Concurrency 12.
- Overlays: rings only drawn on real pixels; max 150 brightest stars; "known star (Gaia)" toggle; no-data area drawn dark, not red.

## Next
1. Merge `feat/time-explorer` into `main` (waiting on the user).
2. Make sure `python scripts/precache.py` has finished for all 4 demo spots before demoing.
3. Optional: Aladin background (CDS is unreachable from this machine), public hosting.

## Run it
`python -m uvicorn server.app:app --port 8000` (or `./run.ps1`), then open http://localhost:8000
Tests: `python -m pytest -q` and `node --test "web/*.test.mjs"`

## Open questions for the user
- Does the hackathon require a public URL, or is a local demo plus video enough?

## Blockers / risks
- A new spot still takes ~2 min to fully load (241 frames), limited by this machine's ~3 MB/s link. Pre-cache demo spots anyway.
- VizieR and Aladin (CDS) are unreachable from this machine; Gaia comes from the ESA archive.
