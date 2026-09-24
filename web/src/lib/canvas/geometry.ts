import type { BoxGeometry, Point, PolygonGeometry, Shape } from './types';
import { isBox } from './types';
import { clamp } from './viewport';

/** Shapes smaller than this fraction of the image on a side are discarded (DESIGN.md section 8). */
export const MIN_SIZE = 0.006;

export type BoxHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

export const clamp01 = (v: number): number => clamp(v, 0, 1);

export function boundsOf(shape: Shape): BoxGeometry {
  const g = shape.geometry;
  if (isBox(g)) return g;
  const xs = g.points.map((p) => p[0]);
  const ys = g.points.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

/** Box from two corner points in any order, clamped to the image. */
export function boxFromPoints(a: Point, b: Point): BoxGeometry {
  const x0 = clamp01(Math.min(a.x, b.x));
  const y0 = clamp01(Math.min(a.y, b.y));
  const x1 = clamp01(Math.max(a.x, b.x));
  const y1 = clamp01(Math.max(a.y, b.y));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

export function isBigEnough(box: BoxGeometry): boolean {
  return box.w >= MIN_SIZE && box.h >= MIN_SIZE;
}

/** Drag one handle of a box to `p`. The box never flips or shrinks below the minimum size. */
export function resizeBox(box: BoxGeometry, handle: BoxHandle, p: Point): BoxGeometry {
  let left = box.x;
  let right = box.x + box.w;
  let top = box.y;
  let bottom = box.y + box.h;
  if (handle.includes('w')) left = clamp01(p.x);
  if (handle.includes('e')) right = clamp01(p.x);
  if (handle.includes('n')) top = clamp01(p.y);
  if (handle.includes('s')) bottom = clamp01(p.y);
  if (left > right) [left, right] = [right, left];
  if (top > bottom) [top, bottom] = [bottom, top];
  if (right - left < MIN_SIZE) {
    if (handle.includes('w')) left = right - MIN_SIZE;
    else right = left + MIN_SIZE;
  }
  if (bottom - top < MIN_SIZE) {
    if (handle.includes('n')) top = bottom - MIN_SIZE;
    else bottom = top + MIN_SIZE;
  }
  return { x: left, y: top, w: right - left, h: bottom - top };
}

/** Move a shape's geometry by (dx, dy), stopping at the image edge instead of squashing. */
export function translate(
  geometry: BoxGeometry | PolygonGeometry,
  dx: number,
  dy: number,
): BoxGeometry | PolygonGeometry {
  if (isBox(geometry)) {
    return {
      x: clamp(geometry.x + dx, 0, 1 - geometry.w),
      y: clamp(geometry.y + dy, 0, 1 - geometry.h),
      w: geometry.w,
      h: geometry.h,
    };
  }
  const xs = geometry.points.map((p) => p[0]);
  const ys = geometry.points.map((p) => p[1]);
  const safeDx = clamp(dx, -Math.min(...xs), 1 - Math.max(...xs));
  const safeDy = clamp(dy, -Math.min(...ys), 1 - Math.max(...ys));
  return { points: geometry.points.map(([x, y]) => [x + safeDx, y + safeDy] as [number, number]) };
}

export function polygonArea(points: [number, number][]): number {
  let total = 0;
  points.forEach(([x1, y1], i) => {
    const [x2, y2] = points[(i + 1) % points.length] as [number, number];
    total += x1 * y2 - x2 * y1;
  });
  return Math.abs(total) / 2;
}

export function shapeArea(shape: Shape): number {
  const g = shape.geometry;
  return isBox(g) ? g.w * g.h : polygonArea(g.points);
}

export function pointInPolygon(p: Point, points: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i] as [number, number];
    const [xj, yj] = points[j] as [number, number];
    if (yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function distanceToSegment(p: Point, a: Point, b: Point): { distance: number; t: number } {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSq = dx * dx + dy * dy;
  const t = lengthSq === 0 ? 0 : clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSq, 0, 1);
  return { distance: Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy)), t };
}
