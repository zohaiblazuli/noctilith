# Decisions log

Append-only. Format: date · decision · why · who decided (user / Claude).

- 2026-11-12 · Focus on **general change/motion discovery**, not asteroids only · the user wants people to be able to "discover something new" · user
- 2026-11-12 · Core flow: flipbook → compare → "is it known?" (SkyBoT + Gaia) → share link · this turns "I see something" into "is it new?", which is the discovery story · Claude proposed, user agreed
- 2026-11-12 · **Small Python backend + web page** (not browser-only) · IRSA has no CORS; cutouts are slow and heavy, so they need a cache and need trimming · Claude proposed, user agreed
- 2026-11-12 · Layout = **A base + B compare mode + C optional guide** · user's pick from the mockups · user
- 2026-11-12 · FastAPI + plain JS, own canvas viewer, Aladin Lite optional · fastest to build in 48 h; frames are reprojected server-side so overlays are simple · Claude
- 2026-11-12 · Pre-cached demo spots · the demo must not wait on IRSA · Claude
- 2026-11-12 · Compare mode pairs frames of similar wavelength by default · each frame sees a different colour; a raw difference would show colour, not change · Claude
