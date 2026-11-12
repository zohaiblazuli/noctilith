# Verified research facts

Checked by running real requests on 2026-11-12 unless marked otherwise. Trust these; add one line when you verify something new.

## SPHEREx mission (short)
- Launched 2025-03-11. Low Earth orbit, about 650 km, polar. 20 cm telescope, 6 HgCdTe detectors (D1–D3 short wavelengths, D4–D6 long), 2040×2040 usable pixels, **6.15″/pixel**.
- 0.75–5.0 µm in 102 channels, using linear variable filters: **each pixel row sees a different wavelength**.
- Maps the whole sky every 6 months; 4 maps in the 2-year prime mission. First all-sky map completed late 2025.

## Finding images: IRSA SIA v2 (fast, about 0.5 s)
`https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr2&POS=circle+{ra}+{dec}+{radius_deg}&RESPONSEFORMAT=CSV`
- Useful columns: `obs_id`, `energy_bandpassname` (SPHEREx-D1..D6), `t_min`/`t_max` (MJD), `access_url`, `em_min`/`em_max` (m), `s_region`, `cloud_access` (S3 key).
- QR2 supersedes QR1. The collection name will change with future releases, so keep it in config.
- Coverage: RA 150 / Dec 2.2 → 213 frames over 21 distinct days (Apr 2025 to May 2026). RA 10.68 / Dec 41.27 → 305 frames. RA 270 / Dec 66.56 (north ecliptic pole) → 570 frames over 82 days. Frames arrive in bursts about 6 months apart. D1 and D4 (and so on) are exposed simultaneously.
- **No CORS headers**, so this can't be called from a browser.

## Cutouts
- `{access_url}?center={ra},{dec}&size={deg}deg`. Example: size 0.1deg gives about 58×58 px.
- **12–16 s per cutout, about 5 MB**: the PSF cube (101×101×121 float32, about 4.9 MB) is always included. No documented way to request only some extensions.
- Got an HTTP **503** after about 5 rapid sequential requests; retrying with backoff worked.
- Alternative not yet tested: the public S3 bucket `nasa-irsa-spherex` (key in `cloud_access`), with range reads.

## FITS file layout (Level 2 spectral image)
HDUs: `IMAGE` (MJy/sr, float32) · `FLAGS` (int32 bitmask; also marks known-source pixels, not only bad pixels) · `VARIANCE` · `ZODI` (background model) · `PSF` (cube) · `WCS-WAVE` (table).
- Sky WCS: `WCS(hdul["IMAGE"].header)`. Astropy warns about SIP without a `-SIP` suffix; this is harmless and can be silenced.
- Wavelength per pixel: `WCS(hdul["IMAGE"].header, fobj=hdul, key="W").pixel_to_world_values(x, y)` returns µm. Within a 0.1° cutout it varies only about 0.015 µm.
- Time: header `MJD-AVG` (or SIA `t_min`).
- Sample renders: `recon/render.py`.

## Known objects
- **SkyBoT** (IMCCE): `https://ssp.imcce.fr/webservices/skybot/api/conesearch.php?-ep={JD}&-ra={deg}&-dec={deg}&-rd={deg}&-mime=text&-output=basic&-loc=500`. Has **CORS: \***. Returns name, RA/Dec, V mag, dRA/dDec in arcsec/hr. Test spot: 5 known main-belt asteroids (V 20.5–23.4) within 0.5°.
- **Gaia DR3**: the VizieR TAP endpoints (cds.unistra.fr and u-strasbg.fr) **time out from this machine**. The **ESA Gaia archive works**: `https://gea.esac.esa.int/tap-server/tap/sync`, table `gaiadr3.gaia_source`, columns `source_id, ra, dec, phot_g_mean_mag`, about 2 s. At (150, 2.2), radius 0.075°, G<17 gives 11 stars. Aladin Lite can also show Gaia directly.
- SkyBoT live at (150, 2.2, 0.1°) at MJD 60998.4 gave 6 objects. Its `dRA` column is treated as already multiplied by cos(dec).

## Tools
- Python 3.12, astropy, numpy, matplotlib, reproject are installed locally.
- Aladin Lite (CDS): embeddable sky viewer with HiPS surveys (2MASS, WISE, Gaia).
- Full L2 images are mirrored publicly at `https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/` + the path after `/ibe/data/spherex/`. Uncompressed 2040×2040 float32; HDUs IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE. Range requests work. Cutout CRPIX keys to shift: CRPIX1/2, CRPIX1A/2A, CRPIX1W/2W.
- This machine's download tops out at ~3 MB/s total (1 conn ~0.4 MB/s, 18 conns ~2.9 MB/s).
