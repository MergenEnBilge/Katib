import type { Change } from '../canvas/model';
import type { AnnotationModel } from '../canvas/model';
import type { Shape } from '../canvas/types';
import type { Annotation, BatchOp, OpResult } from '../api/types';

export type SaveState = 'saved' | 'saving' | 'error';

export interface SaveApi {
  batch(imageId: string, ops: BatchOp[]): Promise<{ results: OpResult[] }>;
}

export interface AutosaveOptions {
  debounceMs?: number;
  /** Called whenever the state or the number of unsaved edits changes. */
  onStatus(state: SaveState, pending: number): void;
  /** Some edits were rejected and the shapes were reset to the server's version. */
  onConflict(count: number): void;
  onRejected(message: string): void;
  /** Timers are injectable so tests do not wait. */
  schedule?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
}

type Field = 'class' | 'geometry' | 'attrs';
const BACKOFF_MS = [2000, 4000, 8000, 16000, 30000];
const MAX_OPS = 500;

export function shapeFromAnnotation(a: Annotation): Shape {
  return {
    id: a.id,
    type: a.type as Shape['type'],
    classId: a.class_id ?? '',
    geometry: a.geometry as unknown as Shape['geometry'],
    attrs: a.attrs,
    version: a.version,
    source: a.source,
    confidence: a.confidence,
  };
}

/**
 * Keeps one image's shapes in sync with the server.
 *
 * It does not queue every change. It remembers which shapes were touched and, at flush time,
 * compares each one against what the server is known to have. That way undo, redo and rapid
 * edits collapse into the smallest set of create, update and delete operations.
 */
export class Autosave {
  private touched = new Map<string, Set<Field>>();
  /** Bumped on every edit, so an edit made while a save is in flight is not marked as saved. */
  private revs = new Map<string, number>();
  private onServer = new Set<string>();
  private versions = new Map<string, number>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private inFlight: Promise<void> | null = null;
  private failures = 0;
  private stopListening: () => void;
  private state: SaveState = 'saved';

  constructor(
    private readonly imageId: string,
    private readonly model: AnnotationModel,
    private readonly api: SaveApi,
    private readonly opts: AutosaveOptions,
    loaded: Annotation[],
  ) {
    for (const a of loaded) {
      this.onServer.add(a.id);
      this.versions.set(a.id, a.version);
    }
    this.stopListening = model.onChange((changes, origin) => {
      if (origin !== 'remote') this.record(changes);
    });
  }

  get pending(): number {
    return this.touched.size;
  }

  private record(changes: Change[]): void {
    for (const change of changes) {
      const touchedId = change.kind === 'update' ? change.id : change.shape.id;
      this.revs.set(touchedId, (this.revs.get(touchedId) ?? 0) + 1);
      if (change.kind === 'update') {
        const fields = this.touched.get(change.id) ?? new Set<Field>();
        if ('classId' in change.after) fields.add('class');
        if ('geometry' in change.after) fields.add('geometry');
        if ('attrs' in change.after) fields.add('attrs');
        this.touched.set(change.id, fields);
      } else {
        const id = change.shape.id;
        this.touched.set(id, this.touched.get(id) ?? new Set<Field>(['class', 'geometry', 'attrs']));
        if (change.kind === 'create') {
          for (const f of ['class', 'geometry', 'attrs'] as const) this.touched.get(id)?.add(f);
        }
      }
    }
    this.setState('saving');
    this.arm(this.opts.debounceMs ?? 400);
  }

  private arm(ms: number): void {
    clearTimeout(this.timer);
    const schedule = this.opts.schedule ?? setTimeout;
    this.timer = schedule(() => void this.flush(), ms);
  }

  private setState(state: SaveState): void {
    this.state = state;
    this.opts.onStatus(state, this.pending);
  }

  private buildOps(): { ops: BatchOp[]; ids: string[] } {
    const ops: BatchOp[] = [];
    const ids: string[] = [];
    for (const [id, fields] of this.touched) {
      const shape = this.model.get(id);
      const known = this.onServer.has(id);
      if (shape && !known) {
        ops.push({
          op: 'create',
          id,
          type: shape.type,
          class_id: shape.classId,
          geometry: shape.geometry as unknown as Record<string, unknown>,
          attrs: shape.attrs,
        });
      } else if (shape && known) {
        const patch: Record<string, unknown> = {};
        if (fields.has('class')) patch.class_id = shape.classId;
        if (fields.has('geometry')) patch.geometry = shape.geometry;
        if (fields.has('attrs')) patch.attrs = shape.attrs;
        ops.push({ op: 'update', id, if_version: this.versions.get(id) ?? null, patch });
      } else if (!shape && known) {
        ops.push({ op: 'delete', id, if_version: this.versions.get(id) ?? null });
      } else {
        continue;
      }
      ids.push(id);
    }
    return { ops, ids };
  }

  /** Send everything that is pending. Safe to call at any time, for example before leaving. */
  flush(): Promise<void> {
    clearTimeout(this.timer);
    if (this.inFlight) return this.inFlight.then(() => (this.pending ? this.flush() : undefined));
    this.inFlight = this.run().finally(() => (this.inFlight = null));
    return this.inFlight;
  }

  private async run(): Promise<void> {
    const { ops, ids } = this.buildOps();
    if (ops.length === 0) {
      this.touched.clear();
      this.revs.clear();
      this.setState('saved');
      return;
    }
    const sent = new Map(ids.map((id) => [id, this.revs.get(id)]));
    this.setState('saving');
    let conflicts = 0;
    try {
      for (let i = 0; i < ops.length; i += MAX_OPS) {
        const chunk = ops.slice(i, i + MAX_OPS);
        const { results } = await this.api.batch(this.imageId, chunk);
        conflicts += this.apply(chunk, results);
      }
    } catch {
      this.failures++;
      this.setState('error');
      const wait = BACKOFF_MS[Math.min(this.failures - 1, BACKOFF_MS.length - 1)] as number;
      this.arm(wait);
      return;
    }
    this.failures = 0;
    for (const [id, rev] of sent) {
      if (this.revs.get(id) === rev) this.touched.delete(id);
    }
    if (conflicts > 0) this.opts.onConflict(conflicts);
    this.setState(this.pending > 0 ? 'saving' : 'saved');
    if (this.pending > 0) this.arm(this.opts.debounceMs ?? 400);
  }

  /** Update local knowledge from the server's answer. Returns how many edits were rejected. */
  private apply(ops: BatchOp[], results: OpResult[]): number {
    let rejected = 0;
    results.forEach((result, i) => {
      const op = ops[i];
      if (!op) return;
      if (result.status === 'ok') {
        if (op.op === 'delete') {
          this.onServer.delete(op.id);
          this.versions.delete(op.id);
        } else if (result.annotation) {
          this.onServer.add(op.id);
          this.versions.set(op.id, result.annotation.version);
          this.model.setVersion(op.id, result.annotation.version);
        }
        return;
      }
      rejected++;
      if (result.status === 'invalid' && result.error) this.opts.onRejected(result.error);
      const local = this.model.get(op.id);
      if (result.status === 'invalid' && op.op === 'create' && local) {
        // The server will never accept this shape, so do not leave it on screen unsaved.
        this.model.applyRemote([{ kind: 'delete', shape: local }]);
      }
      if (result.annotation) {
        // Take the server's copy so the screen matches what is stored.
        this.versions.set(op.id, result.annotation.version);
        const shape = shapeFromAnnotation(result.annotation);
        if (this.model.get(op.id)) {
          this.model.applyRemote([
            {
              kind: 'update',
              id: op.id,
              before: {},
              after: {
                classId: shape.classId,
                geometry: shape.geometry,
                attrs: shape.attrs,
              },
            },
          ]);
          this.model.setVersion(op.id, shape.version);
        }
      } else if (result.status === 'not_found') {
        this.onServer.delete(op.id);
      }
    });
    return rejected;
  }

  dispose(): void {
    clearTimeout(this.timer);
    this.stopListening();
  }

  get status(): SaveState {
    return this.state;
  }
}
