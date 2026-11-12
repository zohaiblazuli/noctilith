"""Render SPHEREx sample cutouts: grid, flipbook GIF, difference, and per-pixel wavelength."""
import glob, warnings
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from astropy.time import Time
from astropy.visualization import ZScaleInterval
from reproject import reproject_interp

warnings.simplefilter("ignore", FITSFixedWarning)
files = sorted(glob.glob("samples/f*.fits"))
frames = []
for f in files:
    h = fits.open(f)
    img = h["IMAGE"].data.astype(float)
    flags = h["FLAGS"].data
    hdr = h["IMAGE"].header
    wcs = WCS(hdr)
    try:
        wave = WCS(hdr, fobj=h, key="W")
        ny, nx = img.shape
        lam = wave.pixel_to_world_values(nx / 2, ny / 2)
        lam = float(np.atleast_1d(lam)[0])
    except Exception as e:
        lam = np.nan
    mjd = hdr.get("MJD-AVG") or hdr.get("MJD-OBS")
    frames.append(dict(img=img, flags=flags, wcs=wcs, lam=lam, mjd=mjd, hdr=hdr))

# Put every frame on the same sky grid (north up), centred on the target
ref = WCS(naxis=2)
ref.wcs.ctype = ["RA---TAN", "DEC--TAN"]
ref.wcs.crval = [150.0, 2.2]
ref.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
N = 58
ref.wcs.crpix = [N / 2, N / 2]
for fr in frames:
    fr["sky"], _ = reproject_interp((fr["img"], fr["wcs"]), ref, shape_out=(N, N))
    fr["sky"] -= np.nanmedian(fr["sky"])  # remove the smooth background glow

def label(fr):
    t = Time(fr["mjd"], format="mjd").iso[:16] if fr["mjd"] else "?"
    lam = f"{fr['lam']:.2f} µm" if np.isfinite(fr["lam"]) else ""
    return f"{t}\n{lam}"

def show(ax, data):
    lo, hi = ZScaleInterval().get_limits(data[np.isfinite(data)])
    ax.imshow(data, origin="lower", cmap="gray", vmin=lo, vmax=hi)
    ax.set_xticks([]); ax.set_yticks([])

# 1) Grid of all frames
fig, axes = plt.subplots(3, 4, figsize=(12, 10), facecolor="black")
for ax, fr in zip(axes.flat, frames):
    show(ax, fr["sky"])
    ax.set_title(label(fr), color="white", fontsize=9)
fig.suptitle("SPHEREx: same 0.1° patch of sky (RA 150.0, Dec +2.2), 12 visits, detector 2",
             color="white")
fig.tight_layout(); fig.savefig("sample_grid.png", dpi=110, facecolor="black")

# 2) Flipbook GIF
fig, ax = plt.subplots(figsize=(5, 5.6), facecolor="black")
def draw(i):
    ax.clear(); show(ax, frames[i]["sky"])
    ax.set_title(f"frame {i+1}/{len(frames)}\n" + label(frames[i]), color="white", fontsize=10)
FuncAnimation(fig, draw, frames=len(frames)).save("sample_flipbook.gif", writer=PillowWriter(fps=2))

# 3) Raw single exposure (native orientation) + wavelength map + flags + difference
fr = frames[0]
fig, ax = plt.subplots(1, 4, figsize=(16, 4.5))
show(ax[0], fr["img"]); ax[0].set_title("Raw cutout (MJy/sr), as stored")
try:
    h = fits.open(files[0]); wave = WCS(h["IMAGE"].header, fobj=h, key="W")
    yy, xx = np.mgrid[0:fr["img"].shape[0], 0:fr["img"].shape[1]]
    lam = np.array(wave.pixel_to_world_values(xx, yy))
    lam = lam[0] if lam.ndim == 3 else lam
    im = ax[1].imshow(lam, origin="lower", cmap="turbo"); plt.colorbar(im, ax=ax[1], label="µm")
    ax[1].set_title("Wavelength seen by each pixel")
except Exception as e:
    ax[1].text(0.1, 0.5, f"wave WCS failed:\n{e}", fontsize=7)
ax[2].imshow(fr["flags"] > 0, origin="lower", cmap="Reds"); ax[2].set_title("Pixels with quality flags")
a, b = frames[2]["sky"], frames[3]["sky"]
d = a - b
lim = np.nanpercentile(np.abs(d), 99)
ax[3].imshow(d, origin="lower", cmap="RdBu_r", vmin=-lim, vmax=lim)
ax[3].set_title("Difference: frame 3 minus frame 4")
for x in ax: x.set_xticks([]); x.set_yticks([])
fig.tight_layout(); fig.savefig("sample_layers.png", dpi=100)

for i, fr in enumerate(frames):
    print(i + 1, label(fr).replace("\n", "  "))
