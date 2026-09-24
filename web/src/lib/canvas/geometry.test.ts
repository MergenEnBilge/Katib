import { describe, expect, it } from 'vitest';
import {
  boxFromPoints,
  distanceToSegment,
  isBigEnough,
  MIN_SIZE,
  pointInPolygon,
  polygonArea,
  resizeBox,
  translate,
} from './geometry';

const square: [number, number][] = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
];

describe('boxFromPoints', () => {
  it('accepts corners in any order and clamps to the image', () => {
    const box = boxFromPoints({ x: 0.5, y: 0.6 }, { x: 0.2, y: 0.1 });
    expect(box.x).toBeCloseTo(0.2);
    expect(box.y).toBeCloseTo(0.1);
    expect(box.w).toBeCloseTo(0.3);
    expect(box.h).toBeCloseTo(0.5);
    const clipped = boxFromPoints({ x: -0.3, y: 0.2 }, { x: 1.4, y: 0.4 });
    expect(clipped.x).toBe(0);
    expect(clipped.x + clipped.w).toBe(1);
  });

  it('flags boxes under the minimum size', () => {
    expect(isBigEnough({ x: 0, y: 0, w: MIN_SIZE / 2, h: 0.3 })).toBe(false);
    expect(isBigEnough({ x: 0, y: 0, w: 0.1, h: 0.1 })).toBe(true);
  });
});

describe('resizeBox', () => {
  const box = { x: 0.2, y: 0.2, w: 0.4, h: 0.4 };

  it('moves only the edges a handle touches', () => {
    const r = resizeBox(box, 'e', { x: 0.9, y: 0.0 });
    expect(r.x).toBeCloseTo(0.2);
    expect(r.w).toBeCloseTo(0.7);
    expect(r.y).toBeCloseTo(0.2);
    expect(r.h).toBeCloseTo(0.4);
  });

  it('resizes from a corner', () => {
    const r = resizeBox(box, 'nw', { x: 0.1, y: 0.05 });
    expect(r.x).toBeCloseTo(0.1);
    expect(r.y).toBeCloseTo(0.05);
    expect(r.x + r.w).toBeCloseTo(0.6);
    expect(r.y + r.h).toBeCloseTo(0.6);
  });

  it('flips instead of going negative', () => {
    const r = resizeBox(box, 'e', { x: 0.05, y: 0 });
    expect(r.x).toBeCloseTo(0.05);
    expect(r.w).toBeCloseTo(0.15);
  });

  it('never drops below the minimum size or leaves the image', () => {
    const tiny = resizeBox(box, 'w', { x: 0.6, y: 0 });
    expect(tiny.w).toBeGreaterThanOrEqual(MIN_SIZE - 1e-12);
    const out = resizeBox(box, 'se', { x: 4, y: 4 });
    expect(out.x + out.w).toBeLessThanOrEqual(1);
    expect(out.y + out.h).toBeLessThanOrEqual(1);
  });
});

describe('translate', () => {
  it('stops a box at the image edge without changing its size', () => {
    const moved = translate({ x: 0.8, y: 0.1, w: 0.15, h: 0.2 }, 0.5, -0.5);
    expect(moved).toEqual({ x: 0.85, y: 0, w: 0.15, h: 0.2 });
  });

  it('moves a polygon as a whole and stops at the edge', () => {
    const poly = {
      points: [
        [0.1, 0.1],
        [0.5, 0.1],
        [0.3, 0.5],
      ] as [number, number][],
    };
    const moved = translate(poly, 0.8, 0) as typeof poly;
    expect(Math.max(...moved.points.map((p) => p[0]))).toBeCloseTo(1);
    expect(moved.points[0]?.[0]).toBeCloseTo(0.6);
    expect(moved.points[0]?.[1]).toBe(0.1);
  });
});

describe('polygon math', () => {
  it('computes area', () => {
    expect(polygonArea(square)).toBeCloseTo(1);
    expect(
      polygonArea([
        [0, 0],
        [1, 0],
        [0, 1],
      ]),
    ).toBeCloseTo(0.5);
  });

  it('tests containment, including concave shapes', () => {
    expect(pointInPolygon({ x: 0.5, y: 0.5 }, square)).toBe(true);
    expect(pointInPolygon({ x: 1.5, y: 0.5 }, square)).toBe(false);
    const concave: [number, number][] = [
      [0, 0],
      [1, 0],
      [1, 1],
      [0.5, 0.2],
      [0, 1],
    ];
    expect(pointInPolygon({ x: 0.5, y: 0.6 }, concave)).toBe(false);
    expect(pointInPolygon({ x: 0.9, y: 0.5 }, concave)).toBe(true);
  });

  it('measures distance to a segment', () => {
    const r = distanceToSegment({ x: 5, y: 3 }, { x: 0, y: 0 }, { x: 10, y: 0 });
    expect(r.distance).toBeCloseTo(3);
    expect(r.t).toBeCloseTo(0.5);
    const beyond = distanceToSegment({ x: -4, y: 3 }, { x: 0, y: 0 }, { x: 10, y: 0 });
    expect(beyond.distance).toBeCloseTo(5);
  });
});
