# Decisions log

Append-only. Format: date · decision · why · who decided (user / Claude).

- 2026-11-12 · Focus on **general change/motion discovery**, not asteroids only · the user wants people to be able to "discover something new" · user
- 2026-11-12 · Core flow: flipbook → compare → "is it known?" (SkyBoT + Gaia) → share link · this turns "I see something" into "is it new?", which is the discovery story · Claude proposed, user agreed
- 2026-11-12 · **Small Python backend + web page** (not browser-only) · IRSA has no CORS; cutouts are slow and heavy, so they need a cache and need trimming · Claude proposed, user agreed
- 2026-11-12 · Layout = **A base + B compare mode + C optional guide** · user's pick from the mockups · user
- 2026-11-12 · FastAPI + plain JS, own canvas viewer, Aladin Lite optional · fastest to build in 48 h; frames are reprojected server-side so overlays are simple · Claude
- 2026-11-12 · Pre-cached demo spots · the demo must not wait on IRSA · Claude
- 2026-11-12 · Compare mode pairs frames of similar wavelength by default · each frame sees a different colour; a raw difference would show colour, not change · Claude
- 2026-11-12 · Frames are identified by `id` = obs_id + detector (obs_id is shared by all 6 detectors) · avoids frame collisions · Claude
- 2026-11-12 · Bad-pixel mask = FLAGS bits 0,1,2,4,5,6,9,10,11,15,17,19; source/dichroic/fullsample/phantom bits are not "bad" · from the FLAGS header · Claude
- 2026-11-12 · "No coverage" cutout results are cached too · avoids refetching 5 MB to learn a frame is empty · Claude
- 2026-11-12 · Gaia via the ESA Gaia archive, not VizieR · VizieR and Aladin (CDS) are unreachable from this machine · Claude
- 2026-11-12 · SkyBoT dRA treated as already ×cos(dec) · SkyBoT convention · Claude
- 2026-11-12 · Image stretch median−2·MAD … median+20·MAD with asinh(3t) · noise looked too bright at 10·MAD · Claude
- 2026-11-12 · Known-asteroid lookups per "epoch" (frames <0.5 d apart), not per visit · visits span up to 10 days; straight-line motion only holds for about a day · Claude
- 2026-11-12 · Candidate boxes need: |σ|>5 blob, present in one frame and absent in the other, ≥3 px and not a sharp spike, same-colour pair · cut false boxes from 1.19 to 0.13 per pair on COSMOS · Claude
- 2026-11-12 · Aladin background view skipped · CDS unreachable here, can't verify · Claude
- 2026-11-12 · SIA answers cached on disk as a fallback; cutout retries capped at 3 × 25 s; external text escaped · final review findings · Claude
- 2026-11-12 · Deferred minors (from final review): polar click-readout maths, NaN wavelength → 500, RA "10d30m" read as hours, Unicode minus, RA≈360 rounding in links, late frame jump, sync cache I/O, overlay requests queue behind cutouts · not demo-critical · Claude
