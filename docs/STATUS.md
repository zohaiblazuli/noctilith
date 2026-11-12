# Status: last updated 2026-11-12 (Day 1)

## Phase
Design and plan done → **next: build, starting at Task 1** of `docs/superpowers/plans/2026-11-12-spherex-time-explorer.md`. The execution method is not chosen yet.

## Done
- Research on SPHEREx and its data access (see RESEARCH.md).
- Sample data pulled and rendered: `recon/sample_grid.png`, `recon/sample_flipbook.gif`, `recon/sample_layers.png`.
- Main-screen layout agreed: A (big viewer + timeline) as the base, plus B (compare mode) and C (guide strip).
- Design written: `docs/superpowers/specs/2026-11-12-spherex-time-explorer-design.md`.

## Next
1. Plan written: 12 tasks, of which Tasks 1–8 and 12 are core and 9–11 are stretch.
2. Backend: `/api/frames` → `/api/frame` with disk cache → `/api/known`.
3. Frontend: Play mode → Compare mode → overlays → side panel.
4. Pick and pre-cache the demo spots.
5. Stretch goals: spectrum, auto change-boxes, guide strip, Aladin background.

## Open questions for the user
- Does the hackathon require a public URL, or is a local demo plus video enough?

## Blockers / risks
- IRSA cutouts are slow (12–16 s each, 5 MB) and sometimes return 503. Mitigation: cache, parallel fetches, burst-at-a-time loading, pre-cached demo spots.
