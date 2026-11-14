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
- 2026-11-12 · Fetch frames as byte-range row slices from the public S3 mirror (`nasa-irsa-spherex`), IRSA cutout as fallback · cutouts always carry a 5 MB PSF cube; the link here caps at ~3 MB/s; slices are ~3x fewer bytes, no IRSA queue/503s; output identical (max diff 0.0) · user asked for speed, Claude chose
- 2026-11-12 · Overlay rings only where the frame has data; cap 150 brightest Gaia stars; star toggle · user saw rings over blank areas and clutter at 0.5° · user reported, Claude chose
- 2026-11-14 · Search `spherex_dr1,spherex_qr3` (comma-separated setting, one SIA request with repeated COLLECTION) · IRSA retired `spherex_qr2`, so every search came back empty and no images loaded; DR1 + QR3 together give the full time span · user reported, Claude chose
- 2026-11-14 · Slicer decompresses tile-compressed HDUs by fetching only the needed rows' tile pointers + heap and letting astropy decode a tiny in-memory FITS; frame cache key bumped to frame-v2 · DR1 compresses FLAGS, which we were reading as raw ints, so ~30% of pixels showed as random bad (red) and hid the image · user reported, Claude chose
- 2026-11-14 · Viewer draws flagged pixels with their real value (no red); flags still exclude them from stretch, spectrum and change detection. Stretch top = max(med+20·MAD, 99.8th pct) with asinh knee at 3·MAD · public viewer should look like the raw data; old curve clipped galaxy cores to flat white and solid-red overflow pixels looked like a bug · user decided, Claude chose the curve
- 2026-11-14 · Wide view first: Go opens one whole detector frame (best-centred, D1/D2, newest on ties) reprojected north-up as a full-res PNG; the user zooms in and plays the boxed area (box = largest of 0.05/0.1/0.2/0.5° that fits on screen; 0.1° on the target before zooming). Demo spots and links with fov/frame still open the flipbook · raw frames look zoomed-out and the old 0.1° default looked blown-up; loading every frame at full width would take ~1 h, one frame takes ~10–20 s · user asked, Claude designed
- 2026-11-14 · Bad-for-analysis bits += GHOST/GHOST_FPA/GHOST_EXT/STREAK/BLOOM/SNOWBALL/HALO (22-28), not CROSSTALK (20) · matches IRSA notebooks; crosstalk covers ~70% of pixels near bright objects · user approved, Claude chose bits
- 2026-11-14 · 'One image per visit' toggle: inverse-variance stack per visit (12 h gap, 1-day cap), client-side; Compare stays single-frame · WiseView's epoch coadds are what made faint movers visible; also removes SPHEREx's per-frame colour flicker · user approved
- 2026-11-14 · Search deep-survey collections; spots over 720 frames are sampled to 120 evenly spread days, one frame per detector per day; SIA answers reused for 12 h · NEP has 29k frames (40 GB) and a 27 MB / 73 s frame list · user approved, Claude chose budget
- 2026-11-14 · Wide view plays over time: one frame per visit (same detector where possible, best-centred), ~1° window cut on the wide view's own pixel grid and drawn as a layer, so zoom works while playing; Play renamed Detail; no stitching yet · user asked to combine wide + play; 1 frame per visit keeps it ~1 min instead of ~15 · user approved
- 2026-11-14 · Server stretch: black level = 2nd percentile, noise from neighbour differences (not median/MAD) · a 1° window full of M31 glow came out darker than the wide image around it · Claude
- 2026-11-14 · 'Hide NASA-flagged junk pixels' on by default: fill only NASA-flagged TRANSIENT, SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD with the 3x3 good-neighbour median on detector pixels; never OVERFLOW (cores) or OUTLIER (criteria unverified); raw values kept (Detail: sparse patch in the payload; wide/visits: second PNG) · lone white specks were mostly cosmic rays/dead pixels and read as false 'changes'; we only act on NASA's own labels · user decided
- 2026-11-14 · Black level ~3 sigma below sky (server: p2 - sigma; browser: median - 4.5 MAD) · old level clipped 2-10% of pixels to pure black, which read as specks · user asked
