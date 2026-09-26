import { describe, expect, it } from 'vitest';
import { AnnotationModel } from '../model';
import type { ClassStyle, Shape, ToolEvent } from '../types';
import { Viewport } from '../viewport';
import { SmartTool } from './smart';
import type { SegmentClick, ToolContext } from './tool';

const W = 1000;
const H = 500;

const SQUARE: [number, number][] = [
  [0.3, 0.3],
  [0.7, 0.3],
  [0.7, 0.7],
  [0.3, 0.7],
];

function setup(segment?: ToolContext['segment']) {
  const viewport = new Viewport(W, H, W, H);
  viewport.scale = 1;
  const model = new AnnotationModel();
  const styles = new Map<string, ClassStyle>([
    ['person', { name: 'person', color: '#4c8df6', hidden: false, locked: false, dash: [] }],
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
    segment,
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

describe('SmartTool', () => {
  it('saves what the model outlined as a polygon', async () => {
    const asked: SegmentClick[][] = [];
    const { ctx, model } = setup(async (clicks) => {
      asked.push(clicks);
      return SQUARE;
    });
    const tool = new SmartTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();

    expect(asked).toEqual([[{ x: 0.5, y: 0.5, positive: true }]]);
    const made = model.shapes[0] as Shape;
    expect(made.type).toBe('polygon');
    expect((made.geometry as { points: [number, number][] }).points).toEqual(SQUARE);
  });

  it('adds a second click to the same outline rather than starting another shape', async () => {
    const asked: SegmentClick[][] = [];
    const { ctx, model } = setup(async (clicks) => {
      asked.push([...clicks]);
      return SQUARE;
    });
    const tool = new SmartTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();
    tool.pointerDown(ev(0.6, 0.6, { shift: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(model.shapes).toHaveLength(1);
    expect(asked[1]).toHaveLength(2);
    expect(asked[1]?.[1]).toEqual({ x: 0.6, y: 0.6, positive: true });
  });

  it('treats a ctrl-click as "not this"', async () => {
    const asked: SegmentClick[][] = [];
    const { ctx } = setup(async (clicks) => {
      asked.push([...clicks]);
      return SQUARE;
    });
    const tool = new SmartTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();
    tool.pointerDown(ev(0.2, 0.2, { ctrl: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(asked[1]?.[1]).toEqual({ x: 0.2, y: 0.2, positive: false });
  });

  it('starts again after a plain click', async () => {
    const asked: SegmentClick[][] = [];
    const { ctx, model } = setup(async (clicks) => {
      asked.push([...clicks]);
      return SQUARE;
    });
    const tool = new SmartTool(ctx);
    tool.pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();
    tool.pointerDown(ev(0.1, 0.1));
    await Promise.resolve();
    await Promise.resolve();

    expect(asked[1]).toHaveLength(1);
    expect(model.shapes).toHaveLength(2);
  });

  it('says so when the model finds nothing there', async () => {
    const { ctx, model, hints } = setup(async () => null);
    new SmartTool(ctx).pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();

    expect(model.shapes).toHaveLength(0);
    expect(hints.at(-1)).toContain('Nothing found');
  });

  it('reports what went wrong instead of leaving a half-drawn shape', async () => {
    const { ctx, model, hints } = setup(async () => {
      throw new Error('The model is not loaded.');
    });
    new SmartTool(ctx).pointerDown(ev(0.5, 0.5));
    await Promise.resolve();
    await Promise.resolve();

    expect(model.shapes).toHaveLength(0);
    expect(hints.at(-1)).toBe('The model is not loaded.');
  });

  it('does nothing when this Katib has no model', () => {
    const { ctx, model, hints } = setup(undefined);
    new SmartTool(ctx).pointerDown(ev(0.5, 0.5));
    expect(model.shapes).toHaveLength(0);
    expect(hints.at(-1)).toContain('no model');
  });
});
