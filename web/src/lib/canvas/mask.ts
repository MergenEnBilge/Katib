/**
 * Brush masks. A mask is a grid of on/off cells stretched over the whole image, saved as
 * run lengths that alternate between off and on, starting with off. The server checks the same
 * format (src/katib/core/rle.py).
 */

export const MAX_GRID_SIDE = 256;

/** Grid size for an image: the long side gets `MAX_GRID_SIDE` cells and the short side keeps the shape. */
export function gridFor(imageW: number, imageH: number): [number, number] {
  if (imageW <= 0 || imageH <= 0) return [1, 1];
  const scale = MAX_GRID_SIDE / Math.max(imageW, imageH);
  return [Math.max(1, Math.round(imageW * scale)), Math.max(1, Math.round(imageH * scale))];
}

export function encodeRuns(cells: Uint8Array): string {
  const runs: number[] = [];
  let current = 0;
  let count = 0;
  for (const cell of cells) {
    const on = cell ? 1 : 0;
    if (on === current) {
      count++;
    } else {
      runs.push(count);
      current = on;
      count = 1;
    }
  }
  runs.push(count);
  return runs.join(',');
}

/** Turn run lengths back into cells. Returns null when they do not fit the grid. */
export function decodeRuns(text: string, width: number, height: number): Uint8Array | null {
  const cells = new Uint8Array(width * height);
  let position = 0;
  let on = 0;
  for (const part of text.split(',')) {
    const run = Number(part);
    if (!Number.isInteger(run) || run < 0 || position + run > cells.length) return null;
    if (on) cells.fill(1, position, position + run);
    position += run;
    on = on ? 0 : 1;
  }
  return position === cells.length ? cells : null;
}

/** Set every cell within `radius` cells of (cx, cy). Returns true when something changed. */
export function paintDisc(
  cells: Uint8Array,
  width: number,
  height: number,
  cx: number,
  cy: number,
  radius: number,
  value: 0 | 1,
): boolean {
  let changed = false;
  const top = Math.max(0, Math.floor(cy - radius));
  const bottom = Math.min(height - 1, Math.ceil(cy + radius));
  const left = Math.max(0, Math.floor(cx - radius));
  const right = Math.min(width - 1, Math.ceil(cx + radius));
  for (let y = top; y <= bottom; y++) {
    for (let x = left; x <= right; x++) {
      const dx = x + 0.5 - cx;
      const dy = y + 0.5 - cy;
      if (dx * dx + dy * dy > radius * radius) continue;
      const i = y * width + x;
      if (cells[i] !== value) {
        cells[i] = value;
        changed = true;
      }
    }
  }
  return changed;
}

/** Paint along a line so a fast stroke leaves no gaps. */
export function paintLine(
  cells: Uint8Array,
  width: number,
  height: number,
  from: { x: number; y: number },
  to: { x: number; y: number },
  radius: number,
  value: 0 | 1,
): boolean {
  const distance = Math.hypot(to.x - from.x, to.y - from.y);
  const steps = Math.max(1, Math.ceil(distance / Math.max(0.5, radius / 2)));
  let changed = false;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const hit = paintDisc(
      cells,
      width,
      height,
      from.x + (to.x - from.x) * t,
      from.y + (to.y - from.y) * t,
      radius,
      value,
    );
    changed ||= hit;
  }
  return changed;
}

export function anyOn(cells: Uint8Array): boolean {
  return cells.some((c) => c !== 0);
}

/** Is the normalized point inside a marked cell? */
export function maskContains(cells: Uint8Array, width: number, height: number, x: number, y: number): boolean {
  if (x < 0 || y < 0 || x >= 1 || y >= 1) return false;
  return cells[Math.floor(y * height) * width + Math.floor(x * width)] === 1;
}

/** The rectangle around marked cells, as fractions of the image, or null when nothing is marked. */
export function maskBounds(
  cells: Uint8Array,
  width: number,
  height: number,
): { x: number; y: number; w: number; h: number } | null {
  let left = width;
  let right = -1;
  let top = height;
  let bottom = -1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (!cells[y * width + x]) continue;
      left = Math.min(left, x);
      right = Math.max(right, x);
      top = Math.min(top, y);
      bottom = Math.max(bottom, y);
    }
  }
  if (right < 0) return null;
  return { x: left / width, y: top / height, w: (right - left + 1) / width, h: (bottom - top + 1) / height };
}

/** Draw the marked cells into a small canvas in one color. Stretch it over the image to show it. */
export function maskToCanvas(cells: Uint8Array, width: number, height: number, color: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const g = canvas.getContext('2d');
  if (!g) return canvas;
  const [r, gr, b] = parseColor(color);
  const image = g.createImageData(width, height);
  for (let i = 0; i < cells.length; i++) {
    if (!cells[i]) continue;
    image.data[i * 4] = r;
    image.data[i * 4 + 1] = gr;
    image.data[i * 4 + 2] = b;
    image.data[i * 4 + 3] = 255;
  }
  g.putImageData(image, 0, 0);
  return canvas;
}

function parseColor(color: string): [number, number, number] {
  const hex = /^#([0-9a-f]{6})/i.exec(color);
  if (!hex) return [255, 255, 255];
  const value = parseInt(hex[1] as string, 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

const decoded = new Map<string, Uint8Array | null>();
const CACHE_LIMIT = 32;

/** Cells of a stored mask. Decoding is remembered, because drawing and hit tests ask often. */
export function maskCells(geometry: { rle: string; size: [number, number] }): Uint8Array | null {
  const key = `${geometry.size[0]}x${geometry.size[1]}:${geometry.rle}`;
  if (decoded.has(key)) return decoded.get(key) ?? null;
  const cells = decodeRuns(geometry.rle, geometry.size[0], geometry.size[1]);
  if (decoded.size >= CACHE_LIMIT) decoded.delete(decoded.keys().next().value as string);
  decoded.set(key, cells);
  return cells;
}
