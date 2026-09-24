import { distanceToSegment, pointInPolygon, shapeArea } from './geometry';
import type { BoxHandle } from './geometry';
import type { Point, Shape } from './types';
import { isBox } from './types';
import type { Viewport } from './viewport';

export const HANDLE_RADIUS = 8;
const EDGE_HANDLE_MIN_SIZE = 80;

export interface Handle {
  /** "nw", "e" and so on for boxes, "v0", "v1"... for polygon vertices. */
  id: string;
  /** Position in screen pixels. */
  screen: Point;
}

/** Top-most shape under a point. Smaller shapes win so shapes nested in others stay selectable. */
export function hitShape(
  shapes: Shape[],
  norm: Point,
  vp: Viewport,
  skip: (s: Shape) => boolean = () => false,
): Shape | null {
  const tolX = 3 / (vp.scale * vp.imageW);
  const tolY = 3 / (vp.scale * vp.imageH);
  let best: Shape | null = null;
  let bestArea = Infinity;
  for (let i = shapes.length - 1; i >= 0; i--) {
    const s = shapes[i] as Shape;
    if (skip(s)) continue;
    const g = s.geometry;
    const hit = isBox(g)
      ? norm.x >= g.x - tolX &&
        norm.x <= g.x + g.w + tolX &&
        norm.y >= g.y - tolY &&
        norm.y <= g.y + g.h + tolY
      : pointInPolygon(norm, g.points);
    if (!hit) continue;
    const area = shapeArea(s);
    if (area < bestArea) {
      best = s;
      bestArea = area;
    }
  }
  return best;
}

export function handlesOf(shape: Shape, vp: Viewport): Handle[] {
  const g = shape.geometry;
  if (!isBox(g)) {
    return g.points.map(([x, y], i) => ({
      id: `v${i}`,
      screen: vp.normToScreen({ x, y }),
    }));
  }
  const tl = vp.normToScreen({ x: g.x, y: g.y });
  const br = vp.normToScreen({ x: g.x + g.w, y: g.y + g.h });
  const mx = (tl.x + br.x) / 2;
  const my = (tl.y + br.y) / 2;
  const corners: Handle[] = [
    { id: 'nw', screen: tl },
    { id: 'ne', screen: { x: br.x, y: tl.y } },
    { id: 'se', screen: br },
    { id: 'sw', screen: { x: tl.x, y: br.y } },
  ];
  if (br.x - tl.x < EDGE_HANDLE_MIN_SIZE && br.y - tl.y < EDGE_HANDLE_MIN_SIZE) return corners;
  return [
    ...corners,
    { id: 'n', screen: { x: mx, y: tl.y } },
    { id: 's', screen: { x: mx, y: br.y } },
    { id: 'e', screen: { x: br.x, y: my } },
    { id: 'w', screen: { x: tl.x, y: my } },
  ];
}

/** The handle within reach of a screen point. Touch gets a bigger target (DESIGN.md section 10). */
export function handleAt(
  shape: Shape,
  screen: Point,
  vp: Viewport,
  pointerType = 'mouse',
): Handle | null {
  const radius = pointerType === 'touch' ? 22 : HANDLE_RADIUS;
  let best: Handle | null = null;
  let bestDist = radius;
  for (const h of handlesOf(shape, vp)) {
    const d = Math.hypot(h.screen.x - screen.x, h.screen.y - screen.y);
    if (d <= bestDist) {
      best = h;
      bestDist = d;
    }
  }
  return best;
}

export function isBoxHandle(id: string): id is BoxHandle {
  return /^(nw|n|ne|e|se|s|sw|w)$/.test(id);
}

/** Polygon edge under a screen point, for inserting a vertex. `index` is the vertex before it. */
export function segmentAt(
  shape: Shape,
  screen: Point,
  vp: Viewport,
  tolerance = 6,
): { index: number; point: Point } | null {
  const g = shape.geometry;
  if (isBox(g)) return null;
  for (let i = 0; i < g.points.length; i++) {
    const a = g.points[i] as [number, number];
    const b = g.points[(i + 1) % g.points.length] as [number, number];
    const sa = vp.normToScreen({ x: a[0], y: a[1] });
    const sb = vp.normToScreen({ x: b[0], y: b[1] });
    const { distance, t } = distanceToSegment(screen, sa, sb);
    if (distance <= tolerance) {
      return { index: i, point: { x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t } };
    }
  }
  return null;
}
