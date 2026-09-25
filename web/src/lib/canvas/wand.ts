/**
 * Magic wand: click inside an object and get an outline of the area around the click that has a
 * similar color. It needs no model. It works best on objects that stand out from their background.
 */

export interface Pixels {
  /** RGBA, four bytes per pixel, row by row. */
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

/** The largest side of the copy of the picture the wand looks at. Bigger pictures are shrunk. */
export const WORKING_SIDE = 512;

function distance(data: Uint8ClampedArray, i: number, r: number, g: number, b: number): number {
  return Math.max(
    Math.abs((data[i] as number) - r),
    Math.abs((data[i + 1] as number) - g),
    Math.abs((data[i + 2] as number) - b),
  );
}

/**
 * Cells connected to the seed whose color is within `tolerance` (0 to 255) of the seed's color on
 * every channel. Returns 1 for cells in the region.
 */
export function floodRegion(pixels: Pixels, seedX: number, seedY: number, tolerance: number): Uint8Array {
  const { data, width, height } = pixels;
  const region = new Uint8Array(width * height);
  const sx = Math.floor(seedX);
  const sy = Math.floor(seedY);
  if (sx < 0 || sy < 0 || sx >= width || sy >= height) return region;
  const seed = (sy * width + sx) * 4;
  const r = data[seed] as number;
  const g = data[seed + 1] as number;
  const b = data[seed + 2] as number;
  const similar = (x: number, y: number): boolean =>
    !region[y * width + x] && distance(data, (y * width + x) * 4, r, g, b) <= tolerance;

  const stack: [number, number][] = [[sx, sy]];
  while (stack.length > 0) {
    const [x, y] = stack.pop() as [number, number];
    if (!similar(x, y)) continue;
    // Fill the whole run to the left and right, then look at the rows above and below it.
    let left = x;
    let right = x;
    while (left > 0 && similar(left - 1, y)) left--;
    while (right < width - 1 && similar(right + 1, y)) right++;
    for (let i = left; i <= right; i++) region[y * width + i] = 1;
    for (const ny of [y - 1, y + 1]) {
      if (ny < 0 || ny >= height) continue;
      let inRun = false;
      for (let i = left; i <= right; i++) {
        const ok = similar(i, ny);
        if (ok && !inRun) stack.push([i, ny]);
        inRun = ok;
      }
    }
  }
  return region;
}

const NEIGHBORS: [number, number][] = [
  [1, 0],
  [1, 1],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [-1, -1],
  [0, -1],
  [1, -1],
];

/** Outer boundary of the region that contains the first marked cell, walked clockwise. */
export function traceOutline(region: Uint8Array, width: number, height: number): [number, number][] {
  const on = (x: number, y: number): boolean =>
    x >= 0 && y >= 0 && x < width && y < height && region[y * width + x] === 1;
  let start = -1;
  for (let i = 0; i < region.length; i++) {
    if (region[i]) {
      start = i;
      break;
    }
  }
  if (start < 0) return [];
  const startX = start % width;
  const startY = Math.floor(start / width);

  const outline: [number, number][] = [[startX, startY]];
  let x = startX;
  let y = startY;
  // The cell above the first marked cell is empty, so the search begins by looking west of it.
  let from = 4;
  for (let guard = 0; guard < region.length * 4; guard++) {
    let moved = false;
    for (let step = 1; step <= 8; step++) {
      const dir = (from + step) % 8;
      const [dx, dy] = NEIGHBORS[dir] as [number, number];
      if (on(x + dx, y + dy)) {
        x += dx;
        y += dy;
        from = (dir + 4) % 8;
        moved = true;
        break;
      }
    }
    if (!moved || (x === startX && y === startY)) break;
    outline.push([x, y]);
  }
  return outline;
}

/** Douglas-Peucker: drop points that lie within `epsilon` of the line between their neighbors. */
export function simplify(points: [number, number][], epsilon: number): [number, number][] {
  if (points.length < 4) return points;
  const keep = new Uint8Array(points.length);
  keep[0] = 1;
  keep[points.length - 1] = 1;
  const stack: [number, number][] = [[0, points.length - 1]];
  while (stack.length > 0) {
    const [first, last] = stack.pop() as [number, number];
    const [ax, ay] = points[first] as [number, number];
    const [bx, by] = points[last] as [number, number];
    const length = Math.hypot(bx - ax, by - ay) || 1;
    let far = -1;
    let farDistance = epsilon;
    for (let i = first + 1; i < last; i++) {
      const [px, py] = points[i] as [number, number];
      const d = Math.abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / length;
      if (d > farDistance) {
        far = i;
        farDistance = d;
      }
    }
    if (far >= 0) {
      keep[far] = 1;
      stack.push([first, far], [far, last]);
    }
  }
  return points.filter((_, i) => keep[i]);
}

/**
 * A polygon around the area of similar color at the click, as fractions of the picture.
 * Returns null when the area is too small to be an outline.
 */
export function wandPolygon(
  pixels: Pixels,
  x: number,
  y: number,
  tolerance: number,
): [number, number][] | null {
  const region = floodRegion(pixels, x * pixels.width, y * pixels.height, tolerance);
  const ring = simplify(traceOutline(region, pixels.width, pixels.height), 1.2);
  if (ring.length < 3) return null;
  // Each cell is a square, so the outline runs through cell centers. Shift by half a cell to
  // put it on the cell edges the region really covers.
  return ring.map(([px, py]) => [
    Math.min(1, Math.max(0, (px + 0.5) / pixels.width)),
    Math.min(1, Math.max(0, (py + 0.5) / pixels.height)),
  ]);
}
