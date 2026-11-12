# Status: last updated 2026-11-12 (Day 1)

## Phase
All plan tasks built on branch `feat/time-explorer` (not merged). **Next: act on the final whole-branch review**, then merge.
Ledger with every ruling: `.superpowers/sdd/2026-11-12-spherex-time-explorer/progress.md` (git-ignored).

## Done
- Backend: SIA search, cached and reprojected cutouts (6 parallel requests, retries), SkyBoT and Gaia (ESA archive).
- Page: Play mode, timeline, URL sync, overlays, click panel, spectrum, Compare mode with candidate boxes, guide strip, demo spots.
- README, `run.ps1`. Tests: 31 pytest, 17 node.

## Next
1. Fix Critical/Important review findings (TDD), then merge to `main`.
2. Make sure `python scripts/precache.py` has finished for all 4 demo spots before demoing.
3. Optional: Aladin background (CDS is unreachable from this machine), public hosting.

## Run it
`python -m uvicorn server.app:app --port 8000` (or `./run.ps1`), then open http://localhost:8000
Tests: `python -m pytest -q` and `node --test "web/*.test.mjs"`

## Open questions for the user
- Does the hackathon require a public URL, or is a local demo plus video enough?

## Blockers / risks
- A cold cutout takes about 15 s, so a new spot takes several minutes to fully load. Demo spots must be pre-cached.
- VizieR and Aladin (CDS) are unreachable from this machine; Gaia comes from the ESA archive.
