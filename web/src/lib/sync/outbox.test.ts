import { describe, expect, it } from 'vitest';
import type { BatchOp, OpResult } from '../api/types';
import { AnnotationModel } from '../canvas/model';
import { Autosave } from './autosave';
import { replayOutbox, type Outbox, type OutboxEntry } from './outbox';

class MemoryOutbox implements Outbox {
  entries = new Map<string, OutboxEntry>();
  async put(imageId: string, ops: BatchOp[]) {
    this.entries.set(imageId, { imageId, ops, savedAt: 0 });
  }
  async remove(imageId: string) {
    this.entries.delete(imageId);
  }
  async all() {
    return [...this.entries.values()];
  }
}

const create = (id: string): BatchOp => ({ op: 'create', id, type: 'box', class_id: 'car', geometry: {}, attrs: {} });
const ok = (id: string): OpResult => ({ id, status: 'ok', annotation: null, error: null });

describe('replayOutbox', () => {
  it('sends each image once and empties the outbox', async () => {
    const outbox = new MemoryOutbox();
    await outbox.put('one', [create('a'), create('b')]);
    await outbox.put('two', [create('c')]);
    const sent: string[] = [];
    const result = await replayOutbox(outbox, async (imageId, ops) => {
      sent.push(imageId);
      return { results: ops.map((op) => ok(op.id)) };
    });
    expect(sent).toEqual(['one', 'two']);
    expect(result).toEqual({ sent: 3, rejected: 0 });
    expect(outbox.entries.size).toBe(0);
  });

  it('counts refused operations and still clears them', async () => {
    const outbox = new MemoryOutbox();
    await outbox.put('one', [create('a')]);
    const result = await replayOutbox(outbox, async () => ({
      results: [{ id: 'a', status: 'conflict', annotation: null, error: null }],
    }));
    expect(result).toEqual({ sent: 0, rejected: 1 });
    expect(outbox.entries.size).toBe(0);
  });

  it('keeps an entry when the network is still down', async () => {
    const outbox = new MemoryOutbox();
    await outbox.put('one', [create('a')]);
    const result = await replayOutbox(outbox, async () => {
      throw new Error('offline');
    });
    expect(result).toEqual({ sent: 0, rejected: 0 });
    expect(outbox.entries.size).toBe(1);
  });
});

describe('Autosave with an outbox', () => {
  function setup() {
    const model = new AnnotationModel();
    const outbox = new MemoryOutbox();
    let offline = true;
    const autosave = new Autosave(
      'img',
      model,
      {
        batch: async (_image, ops) => {
          if (offline) throw new Error('offline');
          return { results: ops.map((op) => ok(op.id)) };
        },
      },
      { onStatus: () => undefined, onConflict: () => undefined, onRejected: () => undefined, outbox, schedule: () => 0 as never },
      [],
    );
    return { model, outbox, autosave, reconnect: () => (offline = false) };
  }

  const box = { id: 'a', type: 'box' as const, classId: 'car', geometry: { x: 0, y: 0, w: 0.1, h: 0.1 }, attrs: {}, version: 0 };

  it('keeps failed edits in the outbox, including ones made after the failure', async () => {
    const { model, outbox, autosave } = setup();
    model.commit([{ kind: 'create', shape: box }]);
    await autosave.flush();
    expect(outbox.entries.get('img')?.ops).toHaveLength(1);

    model.commit([{ kind: 'create', shape: { ...box, id: 'b' } }]);
    await Promise.resolve();
    expect(outbox.entries.get('img')?.ops).toHaveLength(2);
  });

  it('clears the entry once a save goes through', async () => {
    const { model, outbox, autosave, reconnect } = setup();
    model.commit([{ kind: 'create', shape: box }]);
    await autosave.flush();
    reconnect();
    await autosave.flush();
    expect(outbox.entries.size).toBe(0);
  });
});
