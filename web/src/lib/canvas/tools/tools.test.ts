import { describe, expect, it } from 'vitest';
import { AnnotationModel } from '../model';
import type { ClassStyle, Shape, ToolEvent } from '../types';
import { Viewport } from '../viewport';
import { BoxTool } from './box';
import { PolygonTool } from './polygon';
import { SelectTool } from './select';
import type { ToolContext } from './tool';

const W = 1000;
const H = 500;

function setup(active: string | null = 'car') {
  const viewport = new Viewport(W, H, W, H);
  viewport.scale = 1;
  const model = new AnnotationModel();
  const styles = new Map<string, ClassStyle>([
    ['car', { name: 'car', color: '#4c8df6', hidden: false, locked: false, dash: [] }],
    ['bus', { name: 'bus', color: '#8b6cf0', hidden: false, locked: true, dash: [] }],
  ]);
  const hints: string[] = [];
  let needed = 0;
  let counter = 0;
  const ctx: ToolContext = {
    model,
    viewport,
    activeClassId: () => active,
    classStyle: (id) => styles.get(id),
    requestRender: () => {},
    hint: (t) => hints.push(t),
    needClass: () => needed++,
    newId: () => `id${++counter}`,
    accent: () => '#2fa366',
    pixels: () => null,
  };
  return { ctx, model, viewport, hints, needed: () => needed };
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

function drag(tool: { pointerDown(e: ToolEvent): void; pointerMove(e: ToolEvent): void; pointerUp(e: ToolEvent): void }, from: [number, number], to: [number, number], extra: Partial<ToolEvent> = {}) {
  tool.pointerDown(ev(from[0], from[1], extra));
  tool.pointerMove(ev((from[0] + to[0]) / 2, (from[1] + to[1]) / 2, extra));
  tool.pointerMove(ev(to[0], to[1], extra));
  tool.pointerUp(ev(to[0], to[1], extra));
}

function shape(id: string, x: number, y: number, w = 0.2, h = 0.2, classId = 'car'): Shape {
  return { id, type: 'box', classId, geometry: { x, y, w, h }, attrs: {}, version: 1 };
}

describe('BoxTool', () => {
  it('creates a box on drag and selects it', () => {
    const { ctx, model } = setup();
    const tool = new BoxTool(ctx);
    drag(tool, [0.6, 0.5], [0.2, 0.1]);
    expect(model.shapes).toHaveLength(1);
    const created = model.shapes[0] as Shape;
    expect(created.classId).toBe('car');
    expect(created.geometry).toEqual({ x: 0.2, y: 0.1, w: 0.6 - 0.2, h: 0.5 - 0.1 });
    expect([...model.selection]).toEqual([created.id]);
  });

  it('discards a drag that is too small', () => {
    const { ctx, model } = setup();
    const tool = new BoxTool(ctx);
    drag(tool, [0.5, 0.5], [0.502, 0.502]);
    expect(model.shapes).toHaveLength(0);
  });

  it('asks for a class instead of drawing without one', () => {
    const { ctx, model, needed } = setup(null);
    const tool = new BoxTool(ctx);
    drag(tool, [0.1, 0.1], [0.5, 0.5]);
    expect(model.shapes).toHaveLength(0);
    expect(needed()).toBe(1);
  });

  it('cancels with Escape and clamps to the image', () => {
    const { ctx, model } = setup();
    const tool = new BoxTool(ctx);
    tool.pointerDown(ev(0.1, 0.1));
    expect(tool.key({ key: 'Escape', shift: false, ctrl: false })).toBe(true);
    tool.pointerUp(ev(0.5, 0.5));
    expect(model.shapes).toHaveLength(0);
    drag(tool, [0.8, 0.8], [1.5, 1.5]);
    const g = (model.shapes[0] as Shape).geometry as { x: number; w: number };
    expect(g.x + g.w).toBeCloseTo(1);
  });

  it('undoes the creation', () => {
    const { ctx, model } = setup();
    drag(new BoxTool(ctx), [0.1, 0.1], [0.4, 0.4]);
    model.undo();
    expect(model.shapes).toHaveLength(0);
  });
});

describe('PolygonTool', () => {
  it('closes on the first vertex', () => {
    const { ctx, model } = setup();
    let t = 0;
    const tool = new PolygonTool(ctx, () => (t += 1000));
    for (const [x, y] of [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]] as const) {
      tool.pointerDown(ev(x, y));
    }
    tool.pointerDown(ev(0.1, 0.1));
    expect(model.shapes).toHaveLength(1);
    const g = (model.shapes[0] as Shape).geometry as { points: number[][] };
    expect(g.points).toHaveLength(3);
  });

  it('closes with Enter and needs three points', () => {
    const { ctx, model } = setup();
    const tool = new PolygonTool(ctx, () => 0);
    tool.pointerDown(ev(0.1, 0.1));
    tool.pointerDown(ev(0.5, 0.1));
    tool.key({ key: 'Enter', shift: false, ctrl: false });
    expect(model.shapes).toHaveLength(0);
    tool.pointerDown(ev(0.1, 0.1));
    tool.pointerDown(ev(0.5, 0.1));
    tool.pointerDown(ev(0.3, 0.6));
    tool.key({ key: 'Enter', shift: false, ctrl: false });
    expect(model.shapes).toHaveLength(1);
  });

  it('closes on double click without adding a duplicate point', () => {
    const { ctx, model } = setup();
    let t = 0;
    const tool = new PolygonTool(ctx, () => (t += 100));
    tool.pointerDown(ev(0.1, 0.1));
    tool.pointerDown(ev(0.5, 0.1));
    tool.pointerDown(ev(0.3, 0.6));
    tool.pointerDown(ev(0.3, 0.6));
    const g = (model.shapes[0] as Shape).geometry as { points: number[][] };
    expect(g.points).toHaveLength(3);
  });

  it('removes the last point with Backspace and cancels with Escape', () => {
    const { ctx, model } = setup();
    const tool = new PolygonTool(ctx, () => 0);
    tool.pointerDown(ev(0.1, 0.1));
    tool.pointerDown(ev(0.5, 0.1));
    tool.pointerDown(ev(0.3, 0.6));
    tool.key({ key: 'Backspace', shift: false, ctrl: false });
    tool.key({ key: 'Enter', shift: false, ctrl: false });
    expect(model.shapes).toHaveLength(0);
    tool.pointerDown(ev(0.1, 0.1));
    expect(tool.key({ key: 'Escape', shift: false, ctrl: false })).toBe(true);
    expect(tool.key({ key: 'Enter', shift: false, ctrl: false })).toBe(false);
  });
});

describe('SelectTool', () => {
  it('selects the smallest shape under the pointer', () => {
    const { ctx, model } = setup();
    model.load([shape('big', 0.1, 0.1, 0.6, 0.6), shape('small', 0.3, 0.3, 0.1, 0.1)]);
    const tool = new SelectTool(ctx);
    tool.pointerDown(ev(0.35, 0.35));
    tool.pointerUp(ev(0.35, 0.35));
    expect([...model.selection]).toEqual(['small']);
  });

  it('adds to the selection with shift and clears on empty space', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1), shape('b', 0.5, 0.5)]);
    const tool = new SelectTool(ctx);
    tool.pointerDown(ev(0.15, 0.15));
    tool.pointerUp(ev(0.15, 0.15));
    tool.pointerDown(ev(0.55, 0.55, { shift: true }));
    tool.pointerUp(ev(0.55, 0.55, { shift: true }));
    expect(model.selection.size).toBe(2);
    tool.pointerDown(ev(0.9, 0.05));
    tool.pointerUp(ev(0.9, 0.05));
    expect(model.selection.size).toBe(0);
  });

  it('moves a shape with one history entry', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1)]);
    const tool = new SelectTool(ctx);
    drag(tool, [0.2, 0.2], [0.4, 0.3]);
    const g = (model.shapes[0] as Shape).geometry as { x: number; y: number };
    expect(g.x).toBeCloseTo(0.3);
    expect(g.y).toBeCloseTo(0.2);
    expect(model.undo()).toBe(true);
    expect(((model.shapes[0] as Shape).geometry as { x: number }).x).toBeCloseTo(0.1);
    expect(model.undo()).toBe(false);
  });

  it('does not treat a click as a move', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1)]);
    const tool = new SelectTool(ctx);
    tool.pointerDown(ev(0.2, 0.2));
    tool.pointerUp(ev(0.2, 0.2));
    expect(model.canUndo).toBe(false);
  });

  it('resizes from a corner handle', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.2, 0.2, 0.4, 0.4)]);
    model.select(['a']);
    const tool = new SelectTool(ctx);
    drag(tool, [0.6, 0.6], [0.8, 0.9]);
    const g = (model.shapes[0] as Shape).geometry as { x: number; y: number; w: number; h: number };
    expect(g.x).toBeCloseTo(0.2);
    expect(g.w).toBeCloseTo(0.6);
    expect(g.h).toBeCloseTo(0.7);
  });

  it('selects shapes inside a marquee', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1, 0.1, 0.1), shape('b', 0.6, 0.6, 0.1, 0.1)]);
    const tool = new SelectTool(ctx);
    drag(tool, [0.05, 0.05], [0.3, 0.3]);
    expect([...model.selection]).toEqual(['a']);
  });

  it('ignores locked classes for editing', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1, 0.2, 0.2, 'bus')]);
    const tool = new SelectTool(ctx);
    drag(tool, [0.2, 0.2], [0.5, 0.5]);
    expect(model.canUndo).toBe(false);
    model.select(['a']);
    expect(tool.key({ key: 'Delete', shift: false, ctrl: false })).toBe(false);
    expect(model.shapes).toHaveLength(1);
  });

  it('deletes the selection and nudges by pixels', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1)]);
    model.select(['a']);
    const tool = new SelectTool(ctx);
    tool.key({ key: 'ArrowRight', shift: false, ctrl: false });
    expect(((model.shapes[0] as Shape).geometry as { x: number }).x).toBeCloseTo(0.1 + 1 / W);
    tool.key({ key: 'ArrowDown', shift: true, ctrl: false });
    expect(((model.shapes[0] as Shape).geometry as { y: number }).y).toBeCloseTo(0.1 + 10 / H);
    expect(tool.key({ key: 'Delete', shift: false, ctrl: false })).toBe(true);
    expect(model.shapes).toHaveLength(0);
    expect(tool.key({ key: 'ArrowLeft', shift: false, ctrl: false })).toBe(false);
  });

  it('duplicates with Ctrl+D and cycles with Tab', () => {
    const { ctx, model } = setup();
    model.load([shape('a', 0.1, 0.1), shape('b', 0.5, 0.5)]);
    const tool = new SelectTool(ctx);
    tool.key({ key: 'Tab', shift: false, ctrl: false });
    expect([...model.selection]).toEqual(['a']);
    tool.key({ key: 'Tab', shift: false, ctrl: false });
    expect([...model.selection]).toEqual(['b']);
    tool.key({ key: 'Tab', shift: true, ctrl: false });
    expect([...model.selection]).toEqual(['a']);
    tool.key({ key: 'd', shift: false, ctrl: true });
    expect(model.shapes).toHaveLength(3);
    expect(model.selection.size).toBe(1);
  });

  it('inserts a vertex by dragging a polygon edge, and removes one with Delete', () => {
    const { ctx, model } = setup();
    const poly: Shape = {
      id: 'p',
      type: 'polygon',
      classId: 'car',
      geometry: {
        points: [
          [0.2, 0.2],
          [0.6, 0.2],
          [0.4, 0.6],
        ],
      },
      attrs: {},
      version: 1,
    };
    model.load([poly]);
    model.select(['p']);
    const tool = new SelectTool(ctx);
    drag(tool, [0.4, 0.2], [0.4, 0.05]);
    const g = (model.shapes[0] as Shape).geometry as { points: number[][] };
    expect(g.points).toHaveLength(4);
    expect(g.points[1]?.[1]).toBeCloseTo(0.05);

    tool.pointerMove(ev(0.4, 0.05));
    expect(tool.key({ key: 'Delete', shift: false, ctrl: false })).toBe(true);
    const after = (model.shapes[0] as Shape).geometry as { points: number[][] };
    expect(after.points).toHaveLength(3);
  });
});
