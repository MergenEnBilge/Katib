import { describe, expect, it } from 'vitest';
import { AnnotationModel } from '../canvas/model';
import type { Shape } from '../canvas/types';
import type { Annotation, BatchOp, OpResult } from '../api/types';
import { Autosave, type SaveApi, type SaveState } from './autosave';

function shape(id: string, x = 0.1): Shape {
  return {
    id,
    type: 'box',
    classId: 'car',
    geometry: { x, y: 0.1, w: 0.2, h: 0.2 },
    attrs: {},
    version: 0,
  };
}

function annotation(id: string, version: number, x = 0.1): Annotation {
  return {
    id,
    image_id: 'img',
    class_id: 'car',
    type: 'box',
    geometry: { x, y: 0.1, w: 0.2, h: 0.2 },
    attrs: {},
    source: 'manual',
    confidence: null,
    version,
  };
}

class FakeApi implements SaveApi {
  calls: BatchOp[][] = [];
  fail = false;
  respond: (ops: BatchOp[]) => OpResult[] = (ops) =>
    ops.map((op) => ({
      id: op.id,
      status: 'ok' as const,
      annotation: op.op === 'delete' ? null : annotation(op.id, 1),
      error: null,
    }));

  async batch(_image: string, ops: BatchOp[]): Promise<{ results: OpResult[] }> {
    if (this.fail) throw new Error('offline');
    this.calls.push(ops);
    return { results: this.respond(ops) };
  }
}

function setup(loaded: Annotation[] = []) {
  const model = new AnnotationModel();
  model.load(loaded.map((a) => ({ ...shape(a.id), version: a.version })));
  const api = new FakeApi();
  const states: [SaveState, number][] = [];
  const events = { conflicts: 0, rejected: [] as string[] };
  const timers: (() => void)[] = [];
  const autosave = new Autosave(
    'img',
    model,
    api,
    {
      onStatus: (s, n) => states.push([s, n]),
      onConflict: (n) => (events.conflicts += n),
      onRejected: (m) => events.rejected.push(m),
      schedule: (fn) => {
        timers.push(fn);
        return 0 as unknown as ReturnType<typeof setTimeout>;
      },
    },
    loaded,
  );
  return { model, api, autosave, states, events, timers };
}

describe('Autosave', () => {
  it('sends a create for a new shape with its current geometry', async () => {
    const { model, api, autosave } = setup();
    model.commit([{ kind: 'create', shape: shape('a') }]);
    model.commit([
      {
        kind: 'update',
        id: 'a',
        before: { geometry: shape('a').geometry },
        after: { geometry: { x: 0.5, y: 0.5, w: 0.2, h: 0.2 } },
      },
    ]);
    await autosave.flush();
    expect(api.calls).toHaveLength(1);
    const [op] = api.calls[0] as BatchOp[];
    expect(op?.op).toBe('create');
    expect((op?.geometry as { x: number }).x).toBe(0.5);
    expect(autosave.pending).toBe(0);
    expect(model.get('a')?.version).toBe(1);
  });

  it('sends no class for text that has none', async () => {
    const { model, api, autosave } = setup();
    model.commit([
      {
        kind: 'create',
        shape: { id: 't', type: 'text', classId: '', geometry: { text: 'A red door.' }, attrs: {}, version: 0 },
      },
    ]);
    await autosave.flush();
    const [op] = api.calls[0] as BatchOp[];
    expect(op?.class_id).toBeNull();
    expect(op?.geometry).toEqual({ text: 'A red door.' });
  });

  it('collapses create then delete into nothing', async () => {
    const { model, api, autosave, states } = setup();
    const s = shape('a');
    model.commit([{ kind: 'create', shape: s }]);
    model.commit([{ kind: 'delete', shape: s }]);
    await autosave.flush();
    expect(api.calls).toHaveLength(0);
    expect(states.at(-1)).toEqual(['saved', 0]);
  });

  it('sends updates with only the fields that changed and the known version', async () => {
    const { model, api, autosave } = setup([annotation('a', 3)]);
    model.commit([
      { kind: 'update', id: 'a', before: { classId: 'car' }, after: { classId: 'bus' } },
    ]);
    await autosave.flush();
    expect(api.calls[0]).toEqual([
      { op: 'update', id: 'a', if_version: 3, patch: { class_id: 'bus' } },
    ]);
    model.commit([
      { kind: 'update', id: 'a', before: { classId: 'bus' }, after: { classId: 'car' } },
    ]);
    await autosave.flush();
    expect((api.calls[1]?.[0] as BatchOp).if_version).toBe(1);
  });

  it('turns undo of a saved delete into a create', async () => {
    const { model, api, autosave } = setup([annotation('a', 2)]);
    const s = { ...shape('a'), version: 2 };
    model.commit([{ kind: 'delete', shape: s }]);
    await autosave.flush();
    expect(api.calls[0]?.[0]?.op).toBe('delete');
    model.undo();
    await autosave.flush();
    expect(api.calls[1]?.[0]?.op).toBe('create');
  });

  it('cancels a pending delete when it is undone before saving', async () => {
    const { model, api, autosave } = setup([annotation('a', 2)]);
    model.commit([{ kind: 'delete', shape: { ...shape('a'), version: 2 } }]);
    model.undo();
    await autosave.flush();
    expect(api.calls[0]?.[0]?.op).toBe('update');
  });

  it('keeps edits and retries after a network failure', async () => {
    const { model, api, autosave, states, timers } = setup();
    api.fail = true;
    model.commit([{ kind: 'create', shape: shape('a') }]);
    await autosave.flush();
    expect(states.at(-1)?.[0]).toBe('error');
    expect(autosave.pending).toBe(1);
    expect(timers.length).toBeGreaterThan(0);
    api.fail = false;
    await autosave.flush();
    expect(api.calls).toHaveLength(1);
    expect(autosave.pending).toBe(0);
    expect(states.at(-1)).toEqual(['saved', 0]);
  });

  it('resets a shape to the server copy on conflict and reports it', async () => {
    const { model, api, autosave, events } = setup([annotation('a', 1)]);
    api.respond = (ops) =>
      ops.map((op) => ({
        id: op.id,
        status: 'conflict' as const,
        annotation: annotation(op.id, 5, 0.7),
        error: 'changed',
      }));
    model.commit([
      {
        kind: 'update',
        id: 'a',
        before: { geometry: shape('a').geometry },
        after: { geometry: { x: 0.3, y: 0.3, w: 0.2, h: 0.2 } },
      },
    ]);
    await autosave.flush();
    expect(events.conflicts).toBe(1);
    expect((model.get('a')?.geometry as { x: number }).x).toBe(0.7);
    expect(model.get('a')?.version).toBe(5);
  });

  it('removes a shape the server rejects and says why', async () => {
    const { model, api, autosave, events } = setup();
    api.respond = (ops) =>
      ops.map((op) => ({
        id: op.id,
        status: 'invalid' as const,
        annotation: null,
        error: 'That class does not belong to this project.',
      }));
    model.commit([{ kind: 'create', shape: shape('a') }]);
    await autosave.flush();
    expect(model.shapes).toHaveLength(0);
    expect(events.rejected).toEqual(['That class does not belong to this project.']);
  });

  it('does not save changes that came from the server', async () => {
    const { model, api, autosave } = setup([annotation('a', 1)]);
    model.applyRemote([{ kind: 'update', id: 'a', before: {}, after: { classId: 'bus' } }]);
    await autosave.flush();
    expect(api.calls).toHaveLength(0);
  });

  it('reports saving with the pending count as edits arrive', () => {
    const { model, states } = setup();
    model.commit([{ kind: 'create', shape: shape('a') }]);
    model.commit([{ kind: 'create', shape: shape('b') }]);
    expect(states.at(-1)).toEqual(['saving', 2]);
  });
});

describe('Autosave while a save is in flight', () => {
  it('keeps an edit made during the request for the next flush', async () => {
    const { model, api, autosave } = setup([annotation('a', 1)]);
    let release: () => void = () => {};
    const original = api.batch.bind(api);
    api.batch = async (image, ops) => {
      await new Promise<void>((resolve) => (release = resolve));
      return original(image, ops);
    };
    model.commit([{ kind: 'update', id: 'a', before: { classId: 'car' }, after: { classId: 'bus' } }]);
    const first = autosave.flush();
    model.commit([{ kind: 'update', id: 'a', before: { classId: 'bus' }, after: { classId: 'car' } }]);
    release();
    await first;
    expect(autosave.pending).toBe(1);
  });
});
