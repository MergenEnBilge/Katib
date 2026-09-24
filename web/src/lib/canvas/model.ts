import type { BoxGeometry, PolygonGeometry, Shape, ShapePatch } from './types';

export type Change =
  | { kind: 'create'; shape: Shape }
  | { kind: 'update'; id: string; before: ShapePatch; after: ShapePatch }
  | { kind: 'delete'; shape: Shape };

export type ChangeOrigin = 'edit' | 'undo' | 'redo' | 'remote';
export type ChangeListener = (changes: Change[], origin: ChangeOrigin) => void;

export const HISTORY_LIMIT = 200;

export function invert(change: Change): Change {
  switch (change.kind) {
    case 'create':
      return { kind: 'delete', shape: change.shape };
    case 'delete':
      return { kind: 'create', shape: change.shape };
    case 'update':
      return { kind: 'update', id: change.id, before: change.after, after: change.before };
  }
}

/** Per-image command stack. Undo produces the inverse changes, so the server never sees "undo". */
export class History {
  private undoStack: Change[][] = [];
  private redoStack: Change[][] = [];

  constructor(private readonly limit = HISTORY_LIMIT) {}

  push(batch: Change[]): void {
    if (batch.length === 0) return;
    this.undoStack.push(batch);
    if (this.undoStack.length > this.limit) this.undoStack.shift();
    this.redoStack = [];
  }

  /** Changes that reverse the most recent batch, or null when there is nothing to undo. */
  undo(): Change[] | null {
    const batch = this.undoStack.pop();
    if (!batch) return null;
    this.redoStack.push(batch);
    return [...batch].reverse().map(invert);
  }

  redo(): Change[] | null {
    const batch = this.redoStack.pop();
    if (!batch) return null;
    this.undoStack.push(batch);
    return batch;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
  }
}

/** The shapes on one image, plus selection, live drag previews and history. */
export class AnnotationModel {
  shapes: Shape[] = [];
  readonly selection = new Set<string>();
  /** Geometry shown while a drag is in progress. Not part of history until committed. */
  private preview = new Map<string, BoxGeometry | PolygonGeometry>();
  private readonly history = new History();
  private readonly listeners = new Set<ChangeListener>();
  private readonly viewListeners = new Set<() => void>();

  load(shapes: Shape[]): void {
    this.shapes = shapes;
    this.selection.clear();
    this.preview.clear();
    this.history.clear();
    this.notifyView();
  }

  get(id: string): Shape | undefined {
    return this.shapes.find((s) => s.id === id);
  }

  /** Shapes with any in-progress drag geometry applied. This is what gets drawn and hit-tested. */
  visible(): Shape[] {
    if (this.preview.size === 0) return this.shapes;
    return this.shapes.map((s) => {
      const geometry = this.preview.get(s.id);
      return geometry ? { ...s, geometry } : s;
    });
  }

  setPreview(id: string, geometry: BoxGeometry | PolygonGeometry | null): void {
    if (geometry) this.preview.set(id, geometry);
    else this.preview.delete(id);
    this.notifyView();
  }

  clearPreview(): void {
    if (this.preview.size === 0) return;
    this.preview.clear();
    this.notifyView();
  }

  /** Apply changes from the user, record them for undo and tell listeners (autosave). */
  commit(changes: Change[]): void {
    if (changes.length === 0) return;
    this.preview.clear();
    this.apply(changes);
    this.history.push(changes);
    this.emit(changes, 'edit');
  }

  undo(): boolean {
    const changes = this.history.undo();
    if (!changes) return false;
    this.preview.clear();
    this.apply(changes);
    this.emit(changes, 'undo');
    return true;
  }

  redo(): boolean {
    const changes = this.history.redo();
    if (!changes) return false;
    this.preview.clear();
    this.apply(changes);
    this.emit(changes, 'redo');
    return true;
  }

  /** Apply a change that came from the server without adding it to history. */
  applyRemote(changes: Change[]): void {
    this.apply(changes);
    this.emit(changes, 'remote');
  }

  /** Record the version the server assigned after a save. */
  setVersion(id: string, version: number): void {
    const shape = this.get(id);
    if (shape) shape.version = version;
  }

  get canUndo(): boolean {
    return this.history.canUndo;
  }

  get canRedo(): boolean {
    return this.history.canRedo;
  }

  select(ids: string[], additive = false): void {
    if (!additive) this.selection.clear();
    ids.forEach((id) => this.selection.add(id));
    this.notifyView();
  }

  toggle(id: string): void {
    if (this.selection.has(id)) this.selection.delete(id);
    else this.selection.add(id);
    this.notifyView();
  }

  clearSelection(): void {
    if (this.selection.size === 0) return;
    this.selection.clear();
    this.notifyView();
  }

  onChange(listener: ChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Redraw hint: something visible changed, including selection and previews. */
  onView(listener: () => void): () => void {
    this.viewListeners.add(listener);
    return () => this.viewListeners.delete(listener);
  }

  private apply(changes: Change[]): void {
    for (const change of changes) {
      if (change.kind === 'create') {
        if (!this.get(change.shape.id)) this.shapes = [...this.shapes, change.shape];
      } else if (change.kind === 'delete') {
        this.shapes = this.shapes.filter((s) => s.id !== change.shape.id);
        this.selection.delete(change.shape.id);
      } else {
        this.shapes = this.shapes.map((s) => (s.id === change.id ? { ...s, ...change.after } : s));
      }
    }
    this.notifyView();
  }

  private emit(changes: Change[], origin: ChangeOrigin): void {
    this.listeners.forEach((l) => l(changes, origin));
  }

  private notifyView(): void {
    this.viewListeners.forEach((l) => l());
  }
}
