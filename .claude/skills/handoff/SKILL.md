---
name: handoff
description: End-of-chunk handoff for the SPHEREx project. Updates docs/STATUS.md and docs/DECISIONS.md, then commits, so the next session (or a fresh context) can pick up cheaply. Use when a task or milestone finishes, before starting a fresh session, or when the user says "handoff", "save progress" or "wrap up".
---

# Handoff

Goal: the next session should understand where we are by reading only `docs/STATUS.md`, which CLAUDE.md auto-loads.

1. **Update `docs/STATUS.md`** (rewrite, don't append; keep it under about 40 lines):
   - `# Status: last updated <YYYY-MM-DD> (Day N)` with absolute dates.
   - Phase · Done (only things that still matter) · Next (ordered, concrete, naming files) · Open questions for the user · Blockers / risks.
   - How to run it (commands), once that exists.
   - Move finished items out instead of letting the list grow.
2. **Append to `docs/DECISIONS.md`**: one line per new decision this chunk, in the format `date · decision · why · who`. Skip if there are none.
3. **Add to `docs/RESEARCH.md`**: any newly verified fact about the data or APIs, one line each.
4. If the plan in `docs/superpowers/plans/` has checkboxes, tick the finished ones.
5. `git add -A` and commit with a short message describing the chunk. If tests exist, run the full suite first and say in the commit body if anything is failing.
6. Tell the user in 2–3 plain sentences what was saved and what's next.

Don't paste large diffs or file contents into the conversation while doing this.
