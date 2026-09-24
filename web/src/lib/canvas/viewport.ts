import type { Point } from './types';

export const ZOOM_STEPS = [0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 3, 4, 6, 8];
const MIN_SCALE = 0.02;
const MAX_SCALE = 32;
const FIT_PADDING = 32;

/**
 * Maps between screen pixels (CSS pixels on the canvas) and image pixels.
 * screen = image * scale + offset.
 */
export class Viewport {
  scale = 1;
  offsetX = 0;
  offsetY = 0;

  constructor(
    public viewW = 0,
    public viewH = 0,
    public imageW = 0,
    public imageH = 0,
  ) {}

  setView(width: number, height: number): void {
    this.viewW = width;
    this.viewH = height;
  }

  setImage(width: number, height: number): void {
    this.imageW = width;
    this.imageH = height;
  }

  /** Fit the whole image in view with padding, centered. */
  fit(padding = FIT_PADDING): void {
    if (!this.imageW || !this.imageH || !this.viewW || !this.viewH) return;
    const availW = Math.max(1, this.viewW - 2 * padding);
    const availH = Math.max(1, this.viewH - 2 * padding);
    this.scale = clamp(Math.min(availW / this.imageW, availH / this.imageH), MIN_SCALE, MAX_SCALE);
    this.offsetX = (this.viewW - this.imageW * this.scale) / 2;
    this.offsetY = (this.viewH - this.imageH * this.scale) / 2;
  }

  imageToScreen(p: Point): Point {
    return { x: p.x * this.scale + this.offsetX, y: p.y * this.scale + this.offsetY };
  }

  screenToImage(p: Point): Point {
    return { x: (p.x - this.offsetX) / this.scale, y: (p.y - this.offsetY) / this.scale };
  }

  normToScreen(p: Point): Point {
    return this.imageToScreen({ x: p.x * this.imageW, y: p.y * this.imageH });
  }

  screenToNorm(p: Point): Point {
    const i = this.screenToImage(p);
    return { x: i.x / this.imageW, y: i.y / this.imageH };
  }

  /** Multiply the scale by `factor`, keeping the point under `anchor` fixed. */
  zoomBy(factor: number, anchor: Point = { x: this.viewW / 2, y: this.viewH / 2 }): void {
    const next = clamp(this.scale * factor, MIN_SCALE, MAX_SCALE);
    const ratio = next / this.scale;
    this.offsetX = anchor.x - (anchor.x - this.offsetX) * ratio;
    this.offsetY = anchor.y - (anchor.y - this.offsetY) * ratio;
    this.scale = next;
  }

  /** Move to the next preset zoom level above or below the current one. */
  zoomStep(direction: 1 | -1, anchor?: Point): void {
    const current = this.scale;
    const target =
      direction === 1
        ? ZOOM_STEPS.find((s) => s > current * 1.001)
        : [...ZOOM_STEPS].reverse().find((s) => s < current / 1.001);
    if (target === undefined) return;
    this.zoomBy(target / current, anchor);
  }

  panBy(dx: number, dy: number): void {
    this.offsetX += dx;
    this.offsetY += dy;
  }

  get percent(): number {
    return Math.round(this.scale * 100);
  }
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
