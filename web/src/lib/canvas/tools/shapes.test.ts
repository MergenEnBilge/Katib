import { describe, expect, it } from 'vitest';
import {
  obbContains,
  obbCorners,
  obbFromEdge,
  resizeObbCorner,
  rotateObb,
} from '../geometry';
import { decodeRuns, encodeRuns, gridFor, maskCells, paintDisc } from '../mask';
import { AnnotationModel } from '../model';
import type { ClassStyle, ObbGeometry, Shape, ToolEvent } from '../types';
import { Viewport } from '../viewport';
import { BrushTool } from './brush';
import { KeypointsTool } from './keypoints';
import { ObbTool } from './obb';
import { SelectTool } from './select';
import { WandTool } from './wand';
import type { ToolContext } from './tool';

const W = 1000;
const H = 500;

function setup(withSkeleton = true) {
  const viewport = new Viewport(W, H, W, H);
  viewport.scale = 1;
  const model = new AnnotationModel();
  const styles = new Map<string, ClassStyle>([
    [
      'person',
      {
        name: 'person',
        color: '#4c8df6',
        hidden: false,
        locked: false,
        dash: [],
        skeleton: withSkeleton ? { names: ['head', 'hip', 'foot'], edges: [[0, 1], [1, 2]] } : null,
      },
    ],
  ]);
  const hints: string[] = [];
  let counter = 0;
  const ctx: ToolContext = {
    model,
    viewport,
    activeClassId: () => 'person',
    classStyle: (id) => styles.get(id),
    requestRender: () => {},
    hint: (t) => hints.push(t),
    needClass: () => {},
    newId: () => `id${++counter}`,
    accent: () => '#2fa366',
    pixels: () => null,
  };
  return { ctx, model, hints };
}

function ev(nx: number, ny: number, extra: Partial<ToolEvent> = {}): ToolEvent {
  return {
    screen: { x: nx * W, y: ny * H },
    norm: { x: nx, y: ny },
    shift: false,
    ctrl: false,
    button: 0,
    pointerType: 'mouse',
    ...extra,
  };
}

const key = (k: string) => ({ key: k, shift: false, ctrl: false });

describe('rotated box geometry', () => {
  it('builds a box from an edge and a reach point', () => {
    const box = obbFromEdge({ x: 0.2, y: 0.5 }, { x: 0.6, y: 0.5 }, { x: 0.4, y: 0.7 }, W, H);
    expect(box).not.toBeNull();
    expect(box?.angle).toBeCloseTo(0);
    expect(box?.w).toBeCloseTo(0.4);
    expect(box?.h).toBeCloseTo(0.2);
    expect(box?.cx).toBeCloseTo(0.4);
    expect(box?.cy).toBeCloseTo(0.6);
  });

  it('measures sides in pixels, so a turned box on a wide image stays rectangular', () => {
    // A vertical edge 200 px long with a reach of 100 px sideways.
    const box = obbFromEdge({ x: 0.5, y: 0.2 }, { x: 0.5, y: 0.6 }, { x: 0.6, y: 0.4 }, W, H) as ObbGeometry;
    expect(box.angle).toBeCloseTo(Math.PI / 2);
    expect(box.w * W).toBeCloseTo(200);
    expect(box.h * H).toBeCloseTo(100);
    const corners = obbCorners(box, W, H).map(([x, y]) => ({ x: x * W, y: y * H }));
    const side = (a: number, b: number) => {
      const from = corners[a] ?? { x: 0, y: 0 };
      const to = corners[b] ?? { x: 0, y: 0 };
      return Math.hypot(from.x - to.x, from.y - to.y);
    };
    expect(side(0, 1)).toBeCloseTo(200);
    expect(side(1, 2)).toBeCloseTo(100);
  });

  it('refuses an edge or a reach that is too small', () => {
    expect(obbFromEdge({ x: 0.5, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.6, y: 0.6 }, W, H)).toBeNull();
    expect(obbFromEdge({ x: 0.2, y: 0.5 }, { x: 0.6, y: 0.5 }, { x: 0.4, y: 0.5 }, W, H)).toBeNull();
  });

  it('tells inside from outside after turning', () => {
    const box: ObbGeometry = { cx: 0.5, cy: 0.5, w: 0.4, h: 0.1, angle: Math.PI / 2 };
    expect(obbContains(box, { x: 0.5, y: 0.5 }, W, H)).toBe(true);
    // Turned a quarter, the long side (400 px) runs up and down and the short one (50 px) across.
    expect(obbContains(box, { x: 0.5, y: 0.65 }, W, H)).toBe(true);
    expect(obbContains(box, { x: 0.5, y: 0.95 }, W, H)).toBe(false);
    expect(obbContains(box, { x: 0.52, y: 0.5 }, W, H)).toBe(true);
    expect(obbContains(box, { x: 0.55, y: 0.5 }, W, H)).toBe(false);
  });

  it('keeps the opposite corner in place when a corner moves', () => {
    const box: ObbGeometry = { cx: 0.5, cy: 0.5, w: 0.4, h: 0.4, angle: 0.4 };
    const before = obbCorners(box, W, H);
    const moved = resizeObbCorner(box, 2, { x: 0.8, y: 0.8 }, W, H);
    const after = obbCorners(moved, W, H);
    expect(after[0]?.[0]).toBeCloseTo(before[0]?.[0] ?? 0, 4);
    expect(after[0]?.[1]).toBeCloseTo(before[0]?.[1] ?? 0, 4);
  });

  it('points the rotate handle at the pointer', () => {
    const box: ObbGeometry = { cx: 0.5, cy: 0.5, w: 0.2, h: 0.2, angle: 0 };
    expect(rotateObb(box, { x: 0.5, y: 0.1 }, W, H).angle).toBeCloseTo(0);
    expect(rotateObb(box, { x: 0.9, y: 0.5 }, W, H).angle).toBeCloseTo(Math.PI / 2);
    expect(rotateObb(box, { x: 0.87, y: 0.1 }, W, H, true).angle % (Math.PI / 12)).toBeCloseTo(0);
  });
});

describe('mask cells', () => {
  it('matches the run lengths the server expects', () => {
    const cells = Uint8Array.from([0, 0, 1, 1, 1, 0, 1, 0, 0, 0]);
    expect(encodeRuns(cells)).toBe('2,3,1,1,3');
    expect([...(decodeRuns('2,3,1,1,3', 5, 2) ?? [])]).toEqual([...cells]);
  });

  it('starts with an empty run when the first cell is on', () => {
    expect(encodeRuns(Uint8Array.from([1, 1, 0]))).toBe('0,2,1');
  });

  it('rejects runs that do not fill the grid', () => {
    expect(decodeRuns('2,3', 5, 2)).toBeNull();
    expect(decodeRuns('a,b', 1, 1)).toBeNull();
    expect(maskCells({ rle: '1,1', size: [3, 3] })).toBeNull();
  });

  it('keeps the shape of the picture on a small grid', () => {
    expect(gridFor(2000, 1000)).toEqual([256, 128]);
    expect(gridFor(500, 1000)).toEqual([128, 256]);
  });

  it('paints a disc and reports whether anything changed', () => {
    const cells = new Uint8Array(100);
    expect(paintDisc(cells, 10, 10, 5, 5, 2, 1)).toBe(true);
    expect(cells[5 * 10 + 5]).toBe(1);
    expect(paintDisc(cells, 10, 10, 5, 5, 2, 1)).toBe(false);
    expect(paintDisc(cells, 10, 10, 5, 5, 2, 0)).toBe(true);
    expect(cells.every((c) => c === 0)).toBe(true);
  });
});

describe('ObbTool', () => {
  it('draws an edge, then a reach, and creates a rotated box', () => {
    const { ctx, model } = setup();
    const tool = new ObbTool(ctx);
    tool.pointerDown(ev(0.2, 0.5));
    tool.pointerMove(ev(0.6, 0.5));
    tool.pointerUp(ev(0.6, 0.5));
    expect(model.shapes).toHaveLength(0);
    tool.pointerMove(ev(0.4, 0.7));
    tool.pointerDown(ev(0.4, 0.7));
    tool.pointerUp(ev(0.4, 0.7));
    const made = model.shapes[0] as Shape;
    expect(made.type).toBe('obb');
    expect((made.geometry as ObbGeometry).w).toBeCloseTo(0.4);
  });

  it('goes back to the start on Escape without creating anything', () => {
    const { ctx, model } = setup();
    const tool = new ObbTool(ctx);
    tool.pointerDown(ev(0.2, 0.5));
    tool.pointerUp(ev(0.6, 0.5));
    expect(tool.key(key('Escape'))).toBe(true);
    tool.pointerDown(ev(0.4, 0.7));
    tool.pointerUp(ev(0.4, 0.7));
    expect(model.shapes).toHaveLength(0);
  });
});

describe('KeypointsTool', () => {
  it('places the landmarks in order and finishes on the last one', () => {
    const { ctx, model } = setup();
    const tool = new KeypointsTool(ctx);
    tool.pointerDown(ev(0.5, 0.2));
    tool.pointerDown(ev(0.5, 0.5, { shift: true }));
    expect(model.shapes).toHaveLength(0);
    tool.pointerDown(ev(0.5, 0.9));
    const made = model.shapes[0] as Shape;
    expect(made.type).toBe('keypoints');
    const points = (made.geometry as { points: { y: number; v: number }[] }).points;
    expect(points.map((p) => p.v)).toEqual([2, 1, 2]);
    expect(points[2]?.y).toBeCloseTo(0.9);
  });

  it('pads with unlabeled landmarks when finished early, and skips with N', () => {
    const { ctx, model } = setup();
    const tool = new KeypointsTool(ctx);
    tool.pointerDown(ev(0.5, 0.2));
    tool.key(key('n'));
    tool.key(key('Enter'));
    const points = (model.shapes[0]?.geometry as { points: { v: number }[] }).points;
    expect(points.map((p) => p.v)).toEqual([2, 0, 0]);
  });

  it('says what to do when the class has no landmarks', () => {
    const { ctx, model, hints } = setup(false);
    const tool = new KeypointsTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    expect(model.shapes).toHaveLength(0);
    expect(hints.at(-1)).toContain('no landmarks');
  });
});

describe('BrushTool', () => {
  function paint(tool: BrushTool, from: [number, number], to: [number, number]) {
    tool.pointerDown(ev(from[0], from[1]));
    tool.pointerMove(ev(to[0], to[1]));
    tool.pointerUp();
  }

  it('makes a mask from a stroke and selects it', () => {
    const { ctx, model } = setup();
    const tool = new BrushTool(ctx);
    paint(tool, [0.2, 0.5], [0.6, 0.5]);
    const made = model.shapes[0] as Shape;
    expect(made.type).toBe('mask');
    expect([...model.selection]).toEqual([made.id]);
    const geometry = made.geometry as { rle: string; size: [number, number] };
    expect(decodeRuns(geometry.rle, geometry.size[0], geometry.size[1])).not.toBeNull();
  });

  it('adds to the selected mask instead of making a second one', () => {
    const { ctx, model } = setup();
    const tool = new BrushTool(ctx);
    paint(tool, [0.2, 0.2], [0.3, 0.2]);
    paint(tool, [0.7, 0.8], [0.8, 0.8]);
    expect(model.shapes).toHaveLength(1);
    const g = model.shapes[0]?.geometry as { rle: string; size: [number, number] };
    const cells = decodeRuns(g.rle, g.size[0], g.size[1]) as Uint8Array;
    const on = (x: number, y: number) => cells[Math.floor(y * g.size[1]) * g.size[0] + Math.floor(x * g.size[0])];
    expect(on(0.25, 0.2)).toBe(1);
    expect(on(0.75, 0.8)).toBe(1);
    expect(on(0.5, 0.5)).toBe(0);
  });

  it('deletes the mask when everything is erased', () => {
    const { ctx, model } = setup();
    const tool = new BrushTool(ctx);
    tool.radius = 40;
    paint(tool, [0.5, 0.5], [0.5, 0.5]);
    expect(model.shapes).toHaveLength(1);
    tool.key(key('e'));
    tool.radius = 40;
    for (const x of [0.1, 0.3, 0.5, 0.7, 0.9]) paint(tool, [x, 0.5], [x, 0.5]);
    expect(model.shapes).toHaveLength(0);
  });

  it('can be undone like any other edit', () => {
    const { ctx, model } = setup();
    const tool = new BrushTool(ctx);
    paint(tool, [0.2, 0.5], [0.6, 0.5]);
    model.undo();
    expect(model.shapes).toHaveLength(0);
  });
});

describe('SelectTool with the new shapes', () => {
  it('turns a rotated box with the rotate handle', () => {
    const { ctx, model } = setup();
    const box: ObbGeometry = { cx: 0.5, cy: 0.5, w: 0.2, h: 0.2, angle: 0 };
    model.load([{ id: 'b', type: 'obb', classId: 'person', geometry: box, attrs: {}, version: 1 }]);
    model.select(['b']);
    const tool = new SelectTool(ctx);
    // The box is 100 px tall, so its top edge is 50 px above the center and the rotate handle
    // sits 26 px past that.
    tool.pointerDown(ev(0.5, 0.5 - (50 + 26) / H));
    tool.pointerMove(ev(0.9, 0.5));
    tool.pointerUp(ev(0.9, 0.5));
    expect((model.shapes[0]?.geometry as ObbGeometry).angle).toBeCloseTo(Math.PI / 2);
  });

  it('hides a landmark with V and removes it with Delete', () => {
    const { ctx, model } = setup();
    const points = [
      { x: 0.3, y: 0.3, v: 2 as const },
      { x: 0.6, y: 0.6, v: 2 as const },
    ];
    model.load([{ id: 'k', type: 'keypoints', classId: 'person', geometry: { points }, attrs: {}, version: 1 }]);
    model.select(['k']);
    const tool = new SelectTool(ctx);
    tool.pointerMove(ev(0.3, 0.3));
    expect(tool.key(key('v'))).toBe(true);
    expect((model.shapes[0]?.geometry as { points: { v: number }[] }).points[0]?.v).toBe(1);
    tool.pointerMove(ev(0.6, 0.6));
    expect(tool.key(key('Delete'))).toBe(true);
    expect((model.shapes[0]?.geometry as { points: { v: number }[] }).points[1]?.v).toBe(0);
  });

  it('never selects a tag from the canvas', () => {
    const { ctx, model } = setup();
    model.load([{ id: 't', type: 'tag', classId: 'person', geometry: {}, attrs: {}, version: 1 }]);
    const tool = new SelectTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    tool.pointerUp(ev(0.5, 0.5));
    expect(model.selection.size).toBe(0);
  });
});

describe('WandTool', () => {
  const size = 40;
  function world() {
    const base = setup();
    const data = new Uint8ClampedArray(size * size * 4);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const inside = x >= 10 && x < 30 && y >= 10 && y < 30;
        const i = (y * size + x) * 4;
        data[i] = inside ? 230 : 10;
        data[i + 1] = 10;
        data[i + 2] = inside ? 10 : 230;
        data[i + 3] = 255;
      }
    }
    return { ...base, ctx: { ...base.ctx, pixels: () => ({ data, width: size, height: size }) } };
  }

  it('outlines the object under the click as a polygon', () => {
    const { ctx, model } = world();
    const tool = new WandTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    const made = model.shapes[0] as Shape;
    expect(made.type).toBe('polygon');
    const points = (made.geometry as { points: [number, number][] }).points;
    const xs = points.map((p) => p[0]);
    expect(Math.min(...xs)).toBeCloseTo(0.26, 1);
    expect(Math.max(...xs)).toBeCloseTo(0.74, 1);
  });

  it('changes the color range with [ and ]', () => {
    const { ctx } = world();
    const tool = new WandTool(ctx);
    const before = tool.tolerance;
    tool.key(key(']'));
    expect(tool.tolerance).toBeGreaterThan(before);
    tool.key(key('['));
    tool.key(key('['));
    expect(tool.tolerance).toBeLessThan(before);
  });

  it('waits when the picture has not loaded', () => {
    const { ctx, model, hints } = setup();
    new WandTool(ctx).pointerDown(ev(0.5, 0.5));
    expect(model.shapes).toHaveLength(0);
    expect(hints.at(-1)).toContain('still loading');
  });
});
