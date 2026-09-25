import { maskBounds, maskCells } from './mask';
import type {
  BoxGeometry,
  Geometry,
  KeypointsGeometry,
  ObbGeometry,
  Point,
  Shape,
} from './types';
import { isBox, isKeypoints, isMask, isObb, isPolygon } from './types';
import { clamp } from './viewport';

/** Shapes smaller than this fraction of the image on a side are discarded (DESIGN.md section 8). */
export const MIN_SIZE = 0.006;

export type BoxHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

export const clamp01 = (v: number): number => clamp(v, 0, 1);

const EMPTY: BoxGeometry = { x: 0, y: 0, w: 0, h: 0 };

/** The four corners of a rotated box as normalized points, in drawing order. */
export function obbCorners(g: ObbGeometry, imageW: number, imageH: number): [number, number][] {
  const cx = g.cx * imageW;
  const cy = g.cy * imageH;
  const halfW = (g.w * imageW) / 2;
  const halfH = (g.h * imageH) / 2;
  const cos = Math.cos(g.angle);
  const sin = Math.sin(g.angle);
  return (
    [
      [-halfW, -halfH],
      [halfW, -halfH],
      [halfW, halfH],
      [-halfW, halfH],
    ] as const
  ).map(([dx, dy]) => [(cx + dx * cos - dy * sin) / imageW, (cy + dx * sin + dy * cos) / imageH]);
}

/**
 * The rectangle around a shape. Rotated boxes need the image size, because they turn in pixel
 * space. Without it the image counts as square.
 */
export function boundsOf(shape: Shape, imageW = 1, imageH = 1): BoxGeometry {
  const g = shape.geometry;
  if (isBox(g)) return g;
  if (isMask(g)) {
    const cells = maskCells(g);
    return (cells && maskBounds(cells, g.size[0], g.size[1])) ?? EMPTY;
  }
  const points: [number, number][] = isObb(g)
    ? obbCorners(g, imageW, imageH)
    : isPolygon(g)
      ? g.points
      : isKeypoints(g)
        ? g.points.filter((p) => p.v > 0).map((p): [number, number] => [p.x, p.y])
        : [];
  if (points.length === 0) return EMPTY;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
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

/**
 * A rotated box from an edge (`a` to `b`) and a third point that says how far the box reaches to
 * one side of that edge. Returns null when the edge or the depth is too small to be deliberate.
 */
export function obbFromEdge(
  a: Point,
  b: Point,
  reach: Point,
  imageW: number,
  imageH: number,
): ObbGeometry | null {
  const ax = a.x * imageW;
  const ay = a.y * imageH;
  const ex = b.x * imageW - ax;
  const ey = b.y * imageH - ay;
  const length = Math.hypot(ex, ey);
  if (length < 1) return null;
  const ux = ex / length;
  const uy = ey / length;
  // Signed distance of the third point from the edge, along the edge's normal.
  const depth = (reach.x * imageW - ax) * -uy + (reach.y * imageH - ay) * ux;
  const cx = ax + ex / 2 + (-uy * depth) / 2;
  const cy = ay + ey / 2 + (ux * depth) / 2;
  const box: ObbGeometry = {
    cx: clamp01(cx / imageW),
    cy: clamp01(cy / imageH),
    w: Math.min(1, length / imageW),
    h: Math.min(1, Math.abs(depth) / imageH),
    angle: Math.atan2(ey, ex),
  };
  return box.w >= MIN_SIZE && box.h >= MIN_SIZE ? box : null;
}

/** Move one corner of a rotated box. The opposite corner stays where it is. */
export function resizeObbCorner(
  box: ObbGeometry,
  corner: number,
  p: Point,
  imageW: number,
  imageH: number,
): ObbGeometry {
  const corners = obbCorners(box, imageW, imageH);
  const opposite = corners[(corner + 2) % 4] as [number, number];
  const qx = opposite[0] * imageW;
  const qy = opposite[1] * imageH;
  const px = clamp01(p.x) * imageW;
  const py = clamp01(p.y) * imageH;
  const cos = Math.cos(box.angle);
  const sin = Math.sin(box.angle);
  const dx = px - qx;
  const dy = py - qy;
  const along = dx * cos + dy * sin;
  const across = -dx * sin + dy * cos;
  return {
    cx: clamp01((qx + px) / 2 / imageW),
    cy: clamp01((qy + py) / 2 / imageH),
    w: Math.min(1, Math.max(MIN_SIZE, Math.abs(along) / imageW)),
    h: Math.min(1, Math.max(MIN_SIZE, Math.abs(across) / imageH)),
    angle: box.angle,
  };
}

/** Turn a rotated box so its rotate handle (above the top edge) points at `p`. */
export function rotateObb(
  box: ObbGeometry,
  p: Point,
  imageW: number,
  imageH: number,
  snap = false,
): ObbGeometry {
  let angle = Math.atan2((p.y - box.cy) * imageH, (p.x - box.cx) * imageW) + Math.PI / 2;
  if (snap) {
    const step = Math.PI / 12;
    angle = Math.round(angle / step) * step;
  }
  // Keep the stored angle within one turn either way, which is all the server accepts.
  angle = Math.atan2(Math.sin(angle), Math.cos(angle));
  return { ...box, angle };
}

/** Is the normalized point inside a rotated box? `slack` widens it by that many pixels. */
export function obbContains(
  box: ObbGeometry,
  p: Point,
  imageW: number,
  imageH: number,
  slack = 0,
): boolean {
  const dx = (p.x - box.cx) * imageW;
  const dy = (p.y - box.cy) * imageH;
  const cos = Math.cos(box.angle);
  const sin = Math.sin(box.angle);
  const local = { x: dx * cos + dy * sin, y: -dx * sin + dy * cos };
  return (
    Math.abs(local.x) <= (box.w * imageW) / 2 + slack &&
    Math.abs(local.y) <= (box.h * imageH) / 2 + slack
  );
}

/** Move a shape's geometry by (dx, dy), stopping at the image edge instead of squashing. */
export function translate(geometry: Geometry, dx: number, dy: number): Geometry {
  if (isBox(geometry)) {
    return {
      x: clamp(geometry.x + dx, 0, 1 - geometry.w),
      y: clamp(geometry.y + dy, 0, 1 - geometry.h),
      w: geometry.w,
      h: geometry.h,
    };
  }
  if (isObb(geometry)) {
    return { ...geometry, cx: clamp01(geometry.cx + dx), cy: clamp01(geometry.cy + dy) };
  }
  if (isKeypoints(geometry)) return translatePoints(geometry, dx, dy);
  if (isPolygon(geometry)) {
    const xs = geometry.points.map((p) => p[0]);
    const ys = geometry.points.map((p) => p[1]);
    const safeDx = clamp(dx, -Math.min(...xs), 1 - Math.max(...xs));
    const safeDy = clamp(dy, -Math.min(...ys), 1 - Math.max(...ys));
    return {
      points: geometry.points.map(([x, y]) => [x + safeDx, y + safeDy] as [number, number]),
    };
  }
  // Masks are painted, not dragged. Tags have nowhere to go.
  return geometry;
}

function translatePoints(geometry: KeypointsGeometry, dx: number, dy: number): KeypointsGeometry {
  const xs = geometry.points.map((p) => p.x);
  const ys = geometry.points.map((p) => p.y);
  const safeDx = clamp(dx, -Math.min(...xs), 1 - Math.max(...xs));
  const safeDy = clamp(dy, -Math.min(...ys), 1 - Math.max(...ys));
  return {
    points: geometry.points.map((p) => ({ ...p, x: p.x + safeDx, y: p.y + safeDy })),
  };
}

export function polygonArea(points: [number, number][]): number {
  let total = 0;
  points.forEach(([x1, y1], i) => {
    const [x2, y2] = points[(i + 1) % points.length] as [number, number];
    total += x1 * y2 - x2 * y1;
  });
  return Math.abs(total) / 2;
}

/** Area in fractions of the image, used to pick the smaller shape when shapes overlap. */
export function shapeArea(shape: Shape): number {
  const g = shape.geometry;
  if (isBox(g)) return g.w * g.h;
  if (isPolygon(g)) return polygonArea(g.points);
  if (isObb(g)) return g.w * g.h;
  const bounds = boundsOf(shape);
  return bounds.w * bounds.h;
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
