// Canvas viewer for one N×N grid image (row 0 = bottom, north up, east left).
// Supports zoom (wheel), pan (drag), overlays, click → grid pixel.

export class Viewer {
  constructor(canvas, { linkGroup = null } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.off = document.createElement("canvas");
    this.n = 0;
    this.overlays = { sso: [], stars: [], boxes: [] };
    this.view = linkGroup ? linkGroup.view : { zoom: 1, panX: 0, panY: 0 };
    this.linkGroup = linkGroup;
    if (linkGroup) linkGroup.members.push(this);
    this.clickCb = null;
    this.message = "";
    this._bindEvents();
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  // Flagged (bad) pixels are drawn with their real value like the raw image; the flags only
  // keep them out of the stretch, spectrum and change detection. `bad` is unused here on purpose.
  setGray(img, bad, n, lo, hi, soft = (hi - lo) / 3) {
    this._ensure(n);
    const id = this.offCtx.createImageData(n, n);
    const k = soft > 0 ? soft : (hi - lo) / 3 || 1;
    const norm = Math.asinh((hi - lo) / k) || 1;
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const src = y * n + x;
        const dst = ((n - 1 - y) * n + x) * 4;
        const v = img[src];
        if (!Number.isFinite(v)) {
          // this frame doesn't reach here: faint blue-grey
          id.data[dst] = 16; id.data[dst + 1] = 20; id.data[dst + 2] = 30;
        } else {
          // asinh stretch: linear near the sky level, logarithmic for bright cores and stars
          const t = Math.max(0, Math.min(1, Math.asinh(Math.max(0, v - lo) / k) / norm));
          const g = Math.round(t * 255);
          id.data[dst] = g; id.data[dst + 1] = g; id.data[dst + 2] = g;
        }
        id.data[dst + 3] = 255;
      }
    }
    this.offCtx.putImageData(id, 0, 0);
    this.message = "";
    this.draw();
  }

  // Diverging map for difference images in σ units, clamped at ±lim. Red = brighter now.
  setDiverging(arr, n, lim = 5) {
    this._ensure(n);
    const id = this.offCtx.createImageData(n, n);
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const v = arr[y * n + x];
        const dst = ((n - 1 - y) * n + x) * 4;
        if (!Number.isFinite(v)) {
          id.data[dst] = 40; id.data[dst + 1] = 40; id.data[dst + 2] = 40;
        } else {
          const t = Math.max(-1, Math.min(1, v / lim));
          const base = 18;
          if (t >= 0) { id.data[dst] = base + t * 237; id.data[dst + 1] = base + t * 60; id.data[dst + 2] = base + t * 40; }
          else { id.data[dst] = base - t * 40; id.data[dst + 1] = base - t * 120; id.data[dst + 2] = base - t * 237; }
        }
        id.data[dst + 3] = 255;
      }
    }
    this.offCtx.putImageData(id, 0, 0);
    this.message = "";
    this.draw();
  }

  setMessage(msg) { this.message = msg; this.draw(); }
  setOverlays(o) { this.overlays = { sso: [], stars: [], boxes: [], ...o }; this.draw(); }
  onPixelClick(cb) { this.clickCb = cb; }
  resetView() { Object.assign(this.view, { zoom: 1, panX: 0, panY: 0 }); this._redrawGroup(); }

  _ensure(n) {
    if (this.n !== n) {
      this.n = n; this.off.width = n; this.off.height = n;
      this.offCtx = this.off.getContext("2d");
    }
  }

  _geom() {
    const r = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h; }
    const fit = Math.min(w, h) / (this.n || 1);
    const scale = fit * this.view.zoom;
    const ox = (w - this.n * scale) / 2 + this.view.panX * dpr;
    const oy = (h - this.n * scale) / 2 + this.view.panY * dpr;
    return { w, h, dpr, scale, ox, oy };
  }

  // grid (x, y-up) → canvas px
  toCanvas(x, y, g = this._geom()) {
    return [g.ox + (x + 0.5) * g.scale, g.oy + (this.n - 1 - y + 0.5) * g.scale];
  }

  draw() {
    const ctx = this.ctx;
    const g = this._geom();
    ctx.fillStyle = getComputedStyle(this.canvas).getPropertyValue("--viewer-bg") || "#05070d";
    ctx.fillRect(0, 0, g.w, g.h);
    if (this.n) {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(this.off, g.ox, g.oy, this.n * g.scale, this.n * g.scale);
      this._drawOverlays(g);
    }
    if (this.message) {
      ctx.fillStyle = "rgba(5,7,13,0.75)";
      ctx.fillRect(0, g.h / 2 - 28 * g.dpr, g.w, 56 * g.dpr);
      ctx.fillStyle = "#cfd8ea";
      ctx.font = `${14 * g.dpr}px system-ui, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(this.message, g.w / 2, g.h / 2);
    }
  }

  _drawOverlays(g) {
    const ctx = this.ctx;
    const r = Math.max(6 * g.dpr, g.scale * 1.6);
    ctx.lineWidth = 1.5 * g.dpr;
    ctx.font = `${11 * g.dpr}px system-ui, sans-serif`;
    ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    const ring = (cx, cy, rad, color) => {
      // dark halo underneath keeps the ring visible on top of bright stars
      ctx.strokeStyle = "rgba(0,0,0,0.7)"; ctx.lineWidth = 3.5 * g.dpr;
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = color; ctx.lineWidth = 1.6 * g.dpr;
      ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.stroke();
    };
    for (const s of this.overlays.stars) {
      const [cx, cy] = this.toCanvas(s.x, s.y, g);
      ring(cx, cy, r * 1.3, "#6eaaff");
    }
    for (const o of this.overlays.sso) {
      const [cx, cy] = this.toCanvas(o.x, o.y, g);
      ring(cx, cy, r * 1.5, "#ffa23a");
      ctx.fillStyle = "#ffa23a";
      ctx.fillText(o.name, cx + r * 1.6, cy - r * 0.6);
    }
    for (const b of this.overlays.boxes) {
      const [cx, cy] = this.toCanvas(b.x, b.y, g);
      ctx.strokeStyle = "#ff3b5c"; ctx.fillStyle = "#ff3b5c"; ctx.lineWidth = 1.8 * g.dpr;
      ctx.strokeRect(cx - r * 1.3, cy - r * 1.3, r * 2.6, r * 2.6);
      ctx.fillText("candidate", cx + r * 1.4, cy - r * 1.3);
    }
    if (this.overlays.marker) {
      const [cx, cy] = this.toCanvas(this.overlays.marker.x, this.overlays.marker.y, g);
      ctx.strokeStyle = "#7dffb0"; ctx.lineWidth = 1.5 * g.dpr;
      ctx.beginPath();
      ctx.moveTo(cx - r * 2, cy); ctx.lineTo(cx - r * 0.8, cy);
      ctx.moveTo(cx + r * 0.8, cy); ctx.lineTo(cx + r * 2, cy);
      ctx.moveTo(cx, cy - r * 2); ctx.lineTo(cx, cy - r * 0.8);
      ctx.moveTo(cx, cy + r * 0.8); ctx.lineTo(cx, cy + r * 2);
      ctx.stroke();
    }
  }

  _redrawGroup() {
    if (this.linkGroup) this.linkGroup.members.forEach((m) => m.draw()); else this.draw();
  }

  _bindEvents() {
    const c = this.canvas;
    let drag = null;
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      const f = e.deltaY < 0 ? 1.2 : 1 / 1.2;
      this.view.zoom = Math.max(1, Math.min(12, this.view.zoom * f));
      if (this.view.zoom === 1) { this.view.panX = 0; this.view.panY = 0; }
      this._redrawGroup();
    }, { passive: false });
    c.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, y: e.clientY, px: this.view.panX, py: this.view.panY, moved: false };
      c.setPointerCapture(e.pointerId);
    });
    c.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.moved && this.view.zoom > 1) {
        this.view.panX = drag.px + dx; this.view.panY = drag.py + dy; this._redrawGroup();
      }
    });
    c.addEventListener("pointerup", (e) => {
      const wasDrag = drag && drag.moved;
      drag = null;
      if (wasDrag || !this.clickCb || !this.n) return;
      const rect = c.getBoundingClientRect();
      const g = this._geom();
      const px = (e.clientX - rect.left) * g.dpr, py = (e.clientY - rect.top) * g.dpr;
      const x = Math.floor((px - g.ox) / g.scale);
      const row = Math.floor((py - g.oy) / g.scale);
      const y = this.n - 1 - row;
      if (x >= 0 && x < this.n && y >= 0 && y < this.n) this.clickCb(x, y);
    });
  }
}
