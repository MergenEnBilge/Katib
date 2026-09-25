import { describe, expect, it } from 'vitest';
import { polygonArea } from './geometry';
import { floodRegion, simplify, traceOutline, wandPolygon, type Pixels } from './wand';

/** A picture of `size` by `size` cells: blue, with red rectangles where `paint` says so. */
function picture(size: number, paint: (x: number, y: number) => boolean): Pixels {
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const red = paint(x, y);
      data[i] = red ? 220 : 20;
      data[i + 1] = 20;
      data[i + 2] = red ? 20 : 220;
      data[i + 3] = 255;
    }
  }
  return { data, width: size, height: size };
}

const square = (x: number, y: number) => x >= 6 && x < 14 && y >= 6 && y < 14;
const count = (region: Uint8Array) => region.reduce((sum, c) => sum + c, 0);

describe('floodRegion', () => {
  it('fills the area of one color and stops at the edge', () => {
    const region = floodRegion(picture(20, square), 10, 10, 30);
    expect(count(region)).toBe(64);
    expect(region[6 * 20 + 6]).toBe(1);
    expect(region[5 * 20 + 6]).toBe(0);
  });

  it('spreads everywhere when the tolerance is wide', () => {
    expect(count(floodRegion(picture(20, square), 10, 10, 255))).toBe(400);
  });

  it('does not jump to a separate patch of the same color', () => {
    const two = (x: number, y: number) => (x < 4 && y < 4) || (x >= 12 && y >= 12);
    expect(count(floodRegion(picture(20, two), 1, 1, 30))).toBe(16);
  });

  it('returns nothing for a click outside the picture', () => {
    expect(count(floodRegion(picture(20, square), -1, 4, 30))).toBe(0);
  });
});

describe('traceOutline', () => {
  it('walks around a square once', () => {
    const region = floodRegion(picture(20, square), 10, 10, 30);
    const ring = traceOutline(region, 20, 20);
    expect(ring).toHaveLength(28);
    const xs = ring.map((p) => p[0]);
    const ys = ring.map((p) => p[1]);
    expect([Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]).toEqual([6, 13, 6, 13]);
  });

  it('follows an L shape around its corner', () => {
    const shape = (x: number, y: number) => (x >= 4 && x < 8 && y >= 4 && y < 16) || (x >= 4 && x < 16 && y >= 12 && y < 16);
    const ring = traceOutline(floodRegion(picture(20, shape), 5, 5, 30), 20, 20);
    expect(ring.some(([x, y]) => x === 15 && y === 15)).toBe(true);
    expect(ring.some(([x, y]) => x === 4 && y === 4)).toBe(true);
  });

  it('returns nothing for an empty region', () => {
    expect(traceOutline(new Uint8Array(9), 3, 3)).toEqual([]);
  });
});

describe('simplify', () => {
  it('keeps the corners and drops points on straight lines', () => {
    const line: [number, number][] = [[0, 0], [1, 0], [2, 0], [3, 0], [3, 1], [3, 2], [3, 3]];
    expect(simplify(line, 0.5)).toEqual([[0, 0], [3, 0], [3, 3]]);
  });
});

describe('wandPolygon', () => {
  it('outlines an object with a handful of points', () => {
    const polygon = wandPolygon(picture(20, square), 0.5, 0.5, 30);
    expect(polygon).not.toBeNull();
    expect((polygon ?? []).length).toBeLessThanOrEqual(6);
    const area = polygonArea(polygon ?? []);
    // The square covers 8 by 8 of 20 cells, 16 percent of the picture.
    expect(area).toBeGreaterThan(0.1);
    expect(area).toBeLessThan(0.2);
  });

  it('gives up on a single cell', () => {
    const dot = (x: number, y: number) => x === 3 && y === 3;
    expect(wandPolygon(picture(20, dot), 3.5 / 20, 3.5 / 20, 30)).toBeNull();
  });
});
