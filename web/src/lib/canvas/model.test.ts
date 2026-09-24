import { describe, expect, it } from 'vitest';
import { AnnotationModel, HISTORY_LIMIT, History, invert, type Change } from './model';
import type { Shape } from './types';

function box(id: string, x = 0.1): Shape {
  return {
    id,
    type: 'box',
    classId: 'car',
    geometry: { x, y: 0.1, w: 0.2, h: 0.2 },
    attrs: {},
    version: 1,
  };
}

describe('invert', () => {
  it('swaps create and delete and reverses updates', () => {
    const s = box('a');
    expect(invert({ kind: 'create', shape: s })).toEqual({ kind: 'delete', shape: s });
    expect(invert({ kind: 'delete', shape: s })).toEqual({ kind: 'create', shape: s });
    expect(
      invert({ kind: 'update', id: 'a', before: { classId: 'x' }, after: { classId: 'y' } }),
    ).toEqual({ kind: 'update', id: 'a', before: { classId: 'y' }, after: { classId: 'x' } });
  });
});

describe('History', () => {
  it('undoes in reverse order and redoes in order', () => {
    const h = new History();
    const first: Change[] = [{ kind: 'create', shape: box('a') }];
    const second: Change[] = [{ kind: 'create', shape: box('b') }];
    h.push(first);
    h.push(second);
    expect(h.undo()).toEqual([{ kind: 'delete', shape: box('b') }]);
    expect(h.canRedo).toBe(true);
    expect(h.redo()).toEqual(second);
  });

  it('drops the redo stack after a new edit', () => {
    const h = new History();
    h.push([{ kind: 'create', shape: box('a') }]);
    h.undo();
    h.push([{ kind: 'create', shape: box('b') }]);
    expect(h.canRedo).toBe(false);
  });

  it('keeps at most the limit', () => {
    const h = new History();
    for (let i = 0; i < HISTORY_LIMIT + 20; i++) h.push([{ kind: 'create', shape: box(`s${i}`) }]);
    let count = 0;
    while (h.undo()) count++;
    expect(count).toBe(HISTORY_LIMIT);
  });

  it('reverses a batch with its inverse in reverse order', () => {
    const h = new History();
    h.push([
      { kind: 'create', shape: box('a') },
      { kind: 'update', id: 'a', before: { classId: 'car' }, after: { classId: 'bus' } },
    ]);
    const undo = h.undo() as Change[];
    expect(undo[0]?.kind).toBe('update');
    expect(undo[1]?.kind).toBe('delete');
  });
});

describe('AnnotationModel', () => {
  it('applies commits, undo and redo, and reports each to listeners', () => {
    const model = new AnnotationModel();
    const seen: string[] = [];
    model.onChange((changes, origin) =>
      seen.push(`${origin}:${changes.map((c) => c.kind).join(',')}`),
    );

    model.commit([{ kind: 'create', shape: box('a') }]);
    expect(model.shapes.map((s) => s.id)).toEqual(['a']);
    model.commit([{ kind: 'update', id: 'a', before: { classId: 'car' }, after: { classId: 'bus' } }]);
    expect(model.get('a')?.classId).toBe('bus');

    expect(model.undo()).toBe(true);
    expect(model.get('a')?.classId).toBe('car');
    expect(model.undo()).toBe(true);
    expect(model.shapes).toEqual([]);
    expect(model.undo()).toBe(false);
    expect(model.redo()).toBe(true);
    expect(model.shapes.map((s) => s.id)).toEqual(['a']);
    expect(seen).toEqual([
      'edit:create',
      'edit:update',
      'undo:update',
      'undo:delete',
      'redo:create',
    ]);
  });

  it('removes a deleted shape from the selection', () => {
    const model = new AnnotationModel();
    model.commit([{ kind: 'create', shape: box('a') }]);
    model.select(['a']);
    model.commit([{ kind: 'delete', shape: box('a') }]);
    expect(model.selection.size).toBe(0);
  });

  it('shows preview geometry without touching history', () => {
    const model = new AnnotationModel();
    model.commit([{ kind: 'create', shape: box('a') }]);
    model.setPreview('a', { x: 0.5, y: 0.5, w: 0.2, h: 0.2 });
    expect(model.visible()[0]?.geometry).toEqual({ x: 0.5, y: 0.5, w: 0.2, h: 0.2 });
    expect(model.shapes[0]?.geometry).toEqual({ x: 0.1, y: 0.1, w: 0.2, h: 0.2 });
    model.clearPreview();
    expect(model.visible()[0]?.geometry).toEqual({ x: 0.1, y: 0.1, w: 0.2, h: 0.2 });
  });

  it('ignores a duplicate create so retries stay harmless', () => {
    const model = new AnnotationModel();
    model.commit([{ kind: 'create', shape: box('a') }]);
    model.applyRemote([{ kind: 'create', shape: box('a') }]);
    expect(model.shapes).toHaveLength(1);
    expect(model.canUndo).toBe(true);
  });

  it('starts with a clean history when a new image loads', () => {
    const model = new AnnotationModel();
    model.commit([{ kind: 'create', shape: box('a') }]);
    model.load([box('z')]);
    expect(model.canUndo).toBe(false);
    expect(model.shapes.map((s) => s.id)).toEqual(['z']);
  });
});
