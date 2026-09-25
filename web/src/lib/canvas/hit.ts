import {
  distanceToSegment,
  obbContains,
  obbCorners,
  pointInPolygon,
  shapeArea,
} from './geometry';
import type { BoxHandle } from './geometry';
import { maskCells, maskContains } from './mask';
import type { Point, Shape } from './types';
import { isBox, isDrawn, isKeypoints, isMask, isObb, isPolygon } from './types';
import type { Viewport } from './viewport';

export const HANDLE_RADIUS = 8;
const EDGE_HANDLE_MIN_SIZE = 80;
/** How far above a rotated box's top edge its rotate handle sits, in screen pixels. */
export const ROTATE_HANDLE_OFFSET = 26;
/** A landmark counts as hit when the pointer is this close, in screen pixels. */
const LANDMARK_REACH = 10;

export interface Handle {
  /** "nw", "e" and so on for boxes, "v0" for polygon vertices, "c0" for rotated box corners,
   * "rot" for the rotate handle and "k0" for landmarks. */
  id: string;
  /** Position in screen pixels. */
  screen: Point;
}

function hits(shape: Shape, norm: Point, vp: Viewport): boolean {
  const g = shape.geometry;
  const tolX = 3 / (vp.scale * vp.imageW);
  const tolY = 3 / (vp.scale * vp.imageH);
  if (isBox(g)) {
    return (
      norm.x >= g.x - tolX &&
      norm.x <= g.x + g.w + tolX &&
      norm.y >= g.y - tolY &&
      norm.y <= g.y + g.h + tolY
    );
  }
  if (isPolygon(g)) return pointInPolygon(norm, g.points);
  if (isObb(g)) return obbContains(g, norm, vp.imageW, vp.imageH, 3 / vp.scale);
  if (isKeypoints(g)) {
    const at = vp.normToScreen(norm);
    return g.points.some((p) => {
      if (p.v === 0) return false;
      const s = vp.normToScreen(p);
      return Math.hypot(s.x - at.x, s.y - at.y) <= LANDMARK_REACH;
    });
  }
  if (isMask(g)) {
    const cells = maskCells(g);
    return !!cells && maskContains(cells, g.size[0], g.size[1], norm.x, norm.y);
  }
  return false;
}

/** Top-most shape under a point. Smaller shapes win so shapes nested in others stay selectable. */
export function hitShape(
  shapes: Shape[],
  norm: Point,
  vp: Viewport,
  skip: (s: Shape) => boolean = () => false,
): Shape | null {
  let best: Shape | null = null;
  let bestArea = Infinity;
  for (let i = shapes.length - 1; i >= 0; i--) {
    const s = shapes[i] as Shape;
    if (!isDrawn(s) || skip(s) || !hits(s, norm, vp)) continue;
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
  if (isKeypoints(g)) {
    return g.points.flatMap((p, i) =>
      p.v === 0 ? [] : [{ id: `k${i}`, screen: vp.normToScreen(p) }],
    );
  }
  if (isObb(g)) {
    const corners = obbCorners(g, vp.imageW, vp.imageH).map(
      ([x, y], i): Handle => ({ id: `c${i}`, screen: vp.normToScreen({ x, y }) }),
    );
    const top = midpoint(corners[0] as Handle, corners[1] as Handle);
    const center = vp.normToScreen({ x: g.cx, y: g.cy });
    const away = Math.hypot(top.x - center.x, top.y - center.y) || 1;
    const rot = {
      x: top.x + ((top.x - center.x) / away) * ROTATE_HANDLE_OFFSET,
      y: top.y + ((top.y - center.y) / away) * ROTATE_HANDLE_OFFSET,
    };
    return [...corners, { id: 'rot', screen: rot }];
  }
  if (isPolygon(g)) {
    return g.points.map(([x, y], i) => ({ id: `v${i}`, screen: vp.normToScreen({ x, y }) }));
  }
  if (!isBox(g)) return [];
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

function midpoint(a: Handle, b: Handle): Point {
  return { x: (a.screen.x + b.screen.x) / 2, y: (a.screen.y + b.screen.y) / 2 };
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
  if (!isPolygon(g)) return null;
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
