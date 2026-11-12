# SPHEREx Time Explorer

Web tool for the NASA Space Apps hackathon (48 h, started 2026-11-12). The user types RA/Dec and sees every SPHEREx image of that patch as a flipbook to spot moving or changing objects, then checks whether they're already known. The user relies on Claude to build; explain choices in plain English.

## Where we are
@docs/STATUS.md

## Where things live
- `docs/STATUS.md`: now / next / blockers. **Always current.** Keep it under about 40 lines.
- `docs/DECISIONS.md`: append-only log of decisions and why. Check it before reopening a settled question.
- `docs/RESEARCH.md`: verified facts about the IRSA / SkyBoT / FITS data. Use it instead of searching the web again.
- `docs/superpowers/specs/`: the design. `docs/superpowers/plans/`: the implementation plan.
- `recon/`: throwaway exploration scripts and sample renders. The FITS files are git-ignored.

## Working rules (keep usage low without cutting quality)
1. **Start from STATUS.md.** Open the spec, plan or RESEARCH only for the section the current task needs. Use Grep or offset reads, not whole files.
2. **Never dump data into context.** No `cat` of FITS, CSVs or big JSON. Write a short script that prints a summary of a few lines instead.
3. **Don't re-research.** Facts in RESEARCH.md are trusted. If you verify something new, add one line there.
4. **Subagents only when they save context.** Use them for broad web or code sweeps whose raw output would be large, on a cheaper model (`haiku` for lookups, `sonnet` for routine code). Keep design and debugging in the main session.
5. **Batch tool calls** that don't depend on each other. Don't re-read a file you just wrote.
6. **Tests:** run only the relevant test file while iterating, and the full suite before a commit.
7. **End of each work chunk:** run `/handoff`. It updates STATUS and DECISIONS and commits. Small, frequent commits.
8. When the conversation gets long, run `/handoff` and then start a fresh session rather than dragging old context along.

## Tech
Python 3.12 · FastAPI · astropy · reproject · httpx · plain HTML/JS frontend (no build step). Run locally: see STATUS.md once the server exists.
