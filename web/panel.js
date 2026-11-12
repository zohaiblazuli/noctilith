// Side panel: details of the clicked spot.
const $ = (id) => document.getElementById(id);

const fmtDeg = (v, d = 5) => v.toFixed(d) + "°";

export function showSpot({ x, y, ra, dec, value, bad, known, frameLabel }) {
  let verdict;
  if (bad) {
    verdict = `<div class="verdict">This pixel is <b>flagged</b> in this frame (a detector glitch, cosmic ray or saturated star). Its value can't be trusted. Try another frame.</div>`;
  } else if (known && known.name) {
    verdict = `<div class="verdict known"><b>Known:</b> ${known.name}<br><span class="muted">${known.cls || "solar-system object"}${known.vmag ? ` · V ≈ ${known.vmag}` : ""}</span><br>It's a catalogued asteroid or comet, already in the books.</div>`;
  } else if (known) {
    verdict = `<div class="verdict star"><b>Gaia star</b> · G = ${known.gmag.toFixed(1)}<br><span class="muted">Gaia DR3 ${known.source_id}</span></div>`;
  } else {
    verdict = `<div class="verdict cand"><b>Not in Gaia or the known-asteroid lists</b>, so it's a <b>candidate</b>. Before getting excited, check that it shows up in more than one frame and isn't flagged. Many candidates are faint galaxies or noise.</div>`;
  }
  $("spot").classList.remove("muted");
  $("spot").innerHTML = `
    <dl>
      <dt>RA</dt><dd>${fmtDeg(ra)}</dd>
      <dt>Dec</dt><dd>${dec >= 0 ? "+" : ""}${fmtDeg(dec)}</dd>
      <dt>Pixel</dt><dd>${x}, ${y}</dd>
      <dt>Brightness</dt><dd>${Number.isFinite(value) ? value.toFixed(3) + " MJy/sr" : "n/a"} <span class="muted">(above background)</span></dd>
      <dt>Frame</dt><dd>${frameLabel}</dd>
    </dl>${verdict}`;
}
