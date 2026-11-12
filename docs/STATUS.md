# Status: last updated 2026-11-12 (Day 1)

## Phase
Building on branch `feat/time-explorer`, following `docs/superpowers/plans/2026-11-12-spherex-time-explorer.md` (Native execution).
Ledger of done tasks and rulings: `.superpowers/sdd/2026-11-12-spherex-time-explorer/progress.md` (git-ignored).

## Done
- Tasks 1–7: backend (SIA search, cached cutouts, SkyBoT + Gaia), Play mode, timeline, URL sync, overlays, click panel, Compare mode. Browser-verified at RA 150, Dec 2.2.

## Next
1. Task 8: find demo spots (`scripts/find_demo_spots.py`) and pre-cache them (`scripts/precache.py`).
2. Task 9 (spectrum), Task 10 (candidate boxes), Task 11 (guide strip, Aladin): stretch goals.
3. Task 12: README, `run.ps1`, then the final whole-branch review.

## Run it
`python -m uvicorn server.app:app --port 8000`, then open http://localhost:8000/?ra=150&dec=2.2
Tests: `python -m pytest -q` and `node --test "web/*.test.mjs"`

## Open questions for the user
- Does the hackathon require a public URL, or is a local demo plus video enough?

## Blockers / risks
- A cold cutout takes about 15 s; a 200-frame spot takes about 10 min to fully load the first time. Mitigation: disk cache plus pre-cached demo spots.
- VizieR is unreachable from this machine, so Gaia comes from the ESA archive instead.
