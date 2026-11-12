# SPHEREx Time Explorer

**Watch the infrared sky change. Find what moves.**

Type in a position on the sky (Right Ascension and Declination) and this tool plays every image NASA's **SPHEREx** telescope has taken of that patch, in time order, like a flipbook. Stars and galaxies stay put. Asteroids and comets drift. Anything that changes stands out.

Built for the NASA Space Apps Challenge.

## What you can do
- **Play**: step through every SPHEREx frame of a spot. The timeline is coloured by the infrared "colour" (wavelength) each frame saw, and grouped into visits.
- **Compare**: before / after / difference panels. It automatically pairs frames taken at the same colour, so the differences are real changes rather than colour effects. Red means brighter now; blue means brighter before.
- **Is it known?** Orange rings mark catalogued asteroids and comets at the exact time of each frame (IMCCE SkyBoT). Blue rings mark Gaia stars. Red boxes mark **candidates**: changes that no catalogue explains.
- **Click anything** to see its position, brightness and quality flags, plus a **spectrum** built from every visit. SPHEREx sees each spot in a different colour every time, so together the visits make a spectrum.
- **Share**: the URL holds the position, field size, mode and frame, e.g. `/?ra=150&dec=2.2&fov=0.1&mode=compare`, so you can link or embed any view.
- **Demo spots**: asteroids Abundantia, Menzel and De Sitter caught moving, plus the quiet COSMOS deep field.

## Run it
Requires Python 3.12+.

```bash
pip install -r requirements.txt
python scripts/precache.py        # optional but recommended before a demo (can take a while)
python -m uvicorn server.app:app --port 8000
```
Then open http://localhost:8000. On Windows, `./run.ps1` does the last two steps and opens the browser.

The first time a spot is opened, each image takes about 15 s to come from NASA's archive. After that it's served from the local `cache/` folder instantly.

## How it works
- `server/` (FastAPI) asks the NASA/IPAC archive (IRSA SIA) which SPHEREx images cover the spot. It downloads small cutouts (6 at a time, retrying when IRSA is busy), lines each one up north-up on a shared grid with astropy and reproject, marks bad pixels from the quality flags, and caches the result. It also looks up known asteroids (SkyBoT) and Gaia stars (ESA Gaia archive).
- `web/` is a plain HTML/JS page with no build step that draws the frames on `<canvas>`.
- New SPHEREx releases appear automatically: the archive is queried live, and the collection name lives in `server/config.py` (`SPHEREX_COLLECTION` env var).

## Tests
```bash
python -m pytest -q
node --test "web/*.test.mjs"
```

## Limits (honest list)
- A "candidate" is not a discovery. Many are faint galaxies, noise or detector glitches. Check several frames and the flags.
- Asteroid positions are straight-line extrapolations within roughly a day, from a geocentric SkyBoT query. SPHEREx orbits Earth, which matters slightly for very close asteroids.
- Pixels are 6.15″, so this is a survey telescope, not a zoom lens.

## Data credits
SPHEREx data: NASA/JPL-Caltech, via the NASA/IPAC Infrared Science Archive (SPHEREx Quick Release QR2). Known solar-system objects: IMCCE SkyBoT. Stars: ESA Gaia DR3 (gea.esac.esa.int).
