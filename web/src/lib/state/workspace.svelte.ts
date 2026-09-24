import { SvelteSet } from 'svelte/reactivity';
import { api, ApiError } from '../api/client';
import type { Annotation, ImageItem, Project, ProjectClass } from '../api/types';
import type { ClassStyle, Shape } from '../canvas/types';
import { isBox } from '../canvas/types';
import type { Engine } from '../canvas/engine';
import { Autosave, shapeFromAnnotation, type SaveState } from '../sync/autosave';
import { announceOperation, revert } from './operations';
import { toasts } from './toast.svelte';

export type StatusFilter = 'all' | 'todo' | 'in_progress' | 'done';

const PAGE = 100;

/** The image id in `?image=...`, used by "Open in image" from the gallery. */
export function imageFromUrl(search: string): string | null {
  const match = /[?&]image=([0-9a-fA-F-]{36})(?:&|$)/.exec(search);
  return match?.[1] ?? null;
}
const DASHES = [[], [8, 4], [2, 3], [8, 3, 2, 3]];

/** Everything the workspace screen needs that is not about the DOM. */
export class Workspace {
  project = $state<Project | null>(null);
  classes = $state<ProjectClass[]>([]);
  images = $state<ImageItem[]>([]);
  imagesNext = $state<string | null>(null);
  imagesLoading = $state(false);
  loadError = $state('');
  statusFilter = $state<StatusFilter>('all');
  search = $state('');
  currentId = $state<string | null>(null);
  imageLoading = $state(false);
  activeClassId = $state<string | null>(null);
  hiddenClasses = new SvelteSet<string>();
  lockedClasses = new SvelteSet<string>();
  hideAll = $state(false);
  opacity = $state(1);
  patternMode = $state(false);
  saveState = $state<SaveState>('saved');
  pending = $state(0);
  shapeCount = $state(0);
  selectionCount = $state(0);
  canUndo = $state(false);
  canRedo = $state(false);
  /** Bumped on every model change so derived UI (details panel) can refresh. */
  modelTick = $state(0);

  engine = $state.raw<Engine | null>(null);
  private autosave: Autosave | null = null;
  private clipboard: Shape[] = [];
  private openToken = 0;
  private stopModel: (() => void)[] = [];
  private classRefresh: ReturnType<typeof setTimeout> | undefined;

  constructor(readonly projectId: string) {}

  get current(): ImageItem | null {
    return this.images.find((i) => i.id === this.currentId) ?? null;
  }

  get currentIndex(): number {
    return this.images.findIndex((i) => i.id === this.currentId);
  }

  get styles(): Map<string, ClassStyle> {
    // Plain data handed to the canvas engine, which is not reactive, so a SvelteMap would add nothing.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const map = new Map<string, ClassStyle>();
    this.classes.forEach((c, i) => {
      map.set(c.id, {
        name: c.name,
        color: c.color,
        hidden: this.hiddenClasses.has(c.id),
        locked: this.lockedClasses.has(c.id),
        dash: DASHES[i % DASHES.length] ?? [],
      });
    });
    return map;
  }

  attach(engine: Engine): void {
    this.engine = engine;
    this.stopModel.forEach((s) => s());
    const sync = (): void => {
      this.shapeCount = engine.model.shapes.length;
      this.selectionCount = engine.model.selection.size;
      this.canUndo = engine.model.canUndo;
      this.canRedo = engine.model.canRedo;
      this.modelTick++;
    };
    this.stopModel = [
      engine.model.onView(sync),
      engine.model.onChange((_changes, origin) => {
        sync();
        if (origin === 'remote') return;
        const item = this.current;
        if (item) {
          item.annotation_count = engine.model.shapes.length;
          if (item.status === 'todo' && item.annotation_count > 0) item.status = 'in_progress';
        }
      }),
    ];
    engine.setClasses(this.styles);
  }

  detach(): void {
    this.stopModel.forEach((s) => s());
    this.stopModel = [];
    void this.autosave?.flush();
    this.autosave?.dispose();
    this.autosave = null;
    clearTimeout(this.classRefresh);
    this.engine = null;
  }

  pushStyles(): void {
    this.engine?.setClasses(this.styles);
  }

  async init(): Promise<void> {
    this.loadError = '';
    try {
      const [project, classes] = await Promise.all([
        api.projects.get(this.projectId),
        api.classes.list(this.projectId),
      ]);
      this.project = project;
      this.classes = classes;
      this.activeClassId = classes[0]?.id ?? null;
      const wanted = imageFromUrl(location.search);
      await this.loadImages(true);
      if (wanted) await this.open(wanted);
    } catch (err) {
      this.loadError = err instanceof ApiError ? err.message : 'Could not open this project.';
    }
  }

  /** Reload counts, classes and the image list after something was imported. */
  async refresh(): Promise<void> {
    try {
      this.project = await api.projects.get(this.projectId);
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not refresh the project.');
    }
    await this.refreshClasses();
    await this.loadImages(true);
  }

  async loadImages(reset: boolean): Promise<void> {
    if (this.imagesLoading) return;
    this.imagesLoading = true;
    try {
      const page = await api.images.list(this.projectId, {
        status: this.statusFilter === 'all' ? undefined : this.statusFilter,
        q: this.search.trim() || undefined,
        after: reset ? undefined : this.imagesNext,
        limit: PAGE,
      });
      this.images = reset ? page.items : [...this.images, ...page.items];
      this.imagesNext = page.next ?? null;
      if (reset && !this.images.some((i) => i.id === this.currentId)) {
        const first = this.images[0];
        if (first) await this.open(first.id);
        else this.clearCurrent();
      }
    } catch (err) {
      this.loadError = err instanceof ApiError ? err.message : 'Could not load images.';
    } finally {
      this.imagesLoading = false;
    }
  }

  private clearCurrent(): void {
    this.currentId = null;
    this.engine?.clearImage();
    this.engine?.model.load([]);
  }

  async setFilter(status: StatusFilter, search: string): Promise<void> {
    this.statusFilter = status;
    this.search = search;
    await this.loadImages(true);
  }

  async open(imageId: string): Promise<void> {
    if (imageId === this.currentId && this.autosave) return;
    const engine = this.engine;
    if (!engine) return;
    await this.autosave?.flush();
    this.autosave?.dispose();
    this.autosave = null;
    const token = ++this.openToken;
    this.currentId = imageId;
    this.imageLoading = true;
    const item = this.images.find((i) => i.id === imageId);
    try {
      const annotations: Annotation[] = await api.annotations.list(imageId);
      if (token !== this.openToken) return;
      const fresh = item ?? (await api.images.get(imageId));
      engine.model.load(annotations.map(shapeFromAnnotation));
      this.autosave = new Autosave(imageId, engine.model, api.annotations, {
        onStatus: (state, pending) => {
          this.saveState = state;
          this.pending = pending;
          if (state === 'saved') this.scheduleClassRefresh();
        },
        onConflict: (n) =>
          toasts.show(
            n === 1
              ? 'A shape was changed by someone else. It now shows their version.'
              : `${n} shapes were changed by someone else. They now show their versions.`,
          ),
        onRejected: (message) => toasts.show(message),
      }, annotations);
      this.saveState = 'saved';
      this.pending = 0;
      await engine.setImage(api.images.fileUrl(imageId), fresh.width, fresh.height);
      this.prefetch(imageId);
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not open this image.');
    } finally {
      if (token === this.openToken) this.imageLoading = false;
    }
  }

  /** Reload the open image after the server changed its shapes, for example by a merge or revert. */
  async reloadCurrent(): Promise<void> {
    const id = this.currentId;
    if (!id) return;
    this.currentId = null;
    this.autosave?.dispose();
    this.autosave = null;
    await this.open(id);
    await this.refreshClasses();
    try {
      this.project = await api.projects.get(this.projectId);
    } catch {
      // The counts refresh on the next load.
    }
  }

  /** Undo a server-side operation, tell the person what came back and refresh the screen. */
  async revertOperation(id: string): Promise<void> {
    await revert(id, () => this.afterServerChange());
  }

  private async afterServerChange(): Promise<void> {
    await this.reloadCurrent();
    await this.loadImages(true);
  }

  /** Toast for a finished operation. */
  announce(summary: string, operationId: string | null | undefined): void {
    announceOperation(summary, operationId, () => this.afterServerChange());
  }

  /** Warm the browser cache for the next two images so switching feels instant. */
  private prefetch(imageId: string): void {
    const index = this.images.findIndex((i) => i.id === imageId);
    for (const item of this.images.slice(index + 1, index + 3)) {
      const img = new Image();
      img.src = api.images.fileUrl(item.id);
      void api.annotations.list(item.id).catch(() => undefined);
    }
  }

  async step(delta: 1 | -1): Promise<void> {
    const index = this.currentIndex + delta;
    const target = this.images[index];
    if (target) {
      await this.open(target.id);
      if (delta === 1 && index >= this.images.length - 5 && this.imagesNext) void this.loadImages(false);
    } else if (delta === 1 && this.imagesNext) {
      await this.loadImages(false);
      const more = this.images[index];
      if (more) await this.open(more.id);
    }
  }

  async markDone(): Promise<void> {
    const item = this.current;
    if (!item) return;
    await this.autosave?.flush();
    try {
      const updated = await api.images.setStatus(item.id, 'done');
      item.status = updated.status;
      item.version = updated.version;
      if (this.project) this.project.done_count = await this.countDone();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not mark this image as done.');
      return;
    }
    if (this.currentIndex >= this.images.length - 1 && !this.imagesNext) {
      toasts.show('Marked as done. That was the last image.');
    } else {
      await this.step(1);
    }
  }

  private async countDone(): Promise<number> {
    const project = await api.projects.get(this.projectId);
    return project.done_count;
  }

  async reopen(): Promise<void> {
    const item = this.current;
    if (!item) return;
    const updated = await api.images.setStatus(item.id, 'in_progress');
    item.status = updated.status;
  }

  async flushNow(): Promise<void> {
    await this.autosave?.flush();
  }

  // Classes

  async refreshClasses(): Promise<void> {
    try {
      this.classes = await api.classes.list(this.projectId);
      if (this.activeClassId && !this.classes.some((c) => c.id === this.activeClassId)) {
        this.activeClassId = this.classes[0]?.id ?? null;
      }
      this.pushStyles();
    } catch {
      // Counts are decoration. The next save refreshes them again.
    }
  }

  private scheduleClassRefresh(): void {
    clearTimeout(this.classRefresh);
    this.classRefresh = setTimeout(() => void this.refreshClasses(), 600);
  }

  async addClass(name: string): Promise<ProjectClass> {
    const created = await api.classes.create(this.projectId, name);
    await this.refreshClasses();
    this.activeClassId = created.id;
    return created;
  }

  async renameClass(id: string, name: string): Promise<void> {
    await api.classes.update(id, { name });
    await this.refreshClasses();
  }

  async recolorClass(id: string, color: string): Promise<void> {
    await api.classes.update(id, { color });
    await this.refreshClasses();
  }

  toggleHidden(id: string): void {
    if (!this.hiddenClasses.delete(id)) this.hiddenClasses.add(id);
    this.pushStyles();
  }

  toggleLocked(id: string): void {
    if (!this.lockedClasses.delete(id)) this.lockedClasses.add(id);
    this.pushStyles();
  }

  /** Choose the class for new shapes. With shapes selected, they are relabeled too. */
  chooseClass(id: string): void {
    this.activeClassId = id;
    const model = this.engine?.model;
    if (!model || model.selection.size === 0) return;
    const changes = model.shapes
      .filter((s) => model.selection.has(s.id) && s.classId !== id)
      .filter((s) => !this.lockedClasses.has(s.classId))
      .map((s) => ({
        kind: 'update' as const,
        id: s.id,
        before: { classId: s.classId },
        after: { classId: id },
      }));
    model.commit(changes);
  }

  classByShortcut(n: number): ProjectClass | undefined {
    return this.classes[n - 1];
  }

  // Clipboard

  copy(): void {
    const model = this.engine?.model;
    if (!model) return;
    this.clipboard = model.shapes.filter((s) => model.selection.has(s.id)).map((s) => structuredClone(s));
    if (this.clipboard.length > 0) toasts.show(`Copied ${this.clipboard.length} ${this.clipboard.length === 1 ? 'shape' : 'shapes'}.`);
  }

  paste(): void {
    const model = this.engine?.model;
    if (!model || this.clipboard.length === 0) return;
    const copies: Shape[] = this.clipboard.map((s) => ({
      ...structuredClone(s),
      id: crypto.randomUUID(),
      version: 0,
    }));
    model.commit(copies.map((shape) => ({ kind: 'create' as const, shape })));
    model.select(copies.map((s) => s.id));
  }

  /** Geometry of the single selected shape in image pixels, for the details panel. */
  selectedShape(): Shape | null {
    void this.modelTick;
    const model = this.engine?.model;
    if (!model || model.selection.size !== 1) return null;
    const [id] = [...model.selection];
    return (id && model.get(id)) || null;
  }

  pixelBox(shape: Shape): { x: number; y: number; w: number; h: number } | null {
    const item = this.current;
    if (!item || !isBox(shape.geometry)) return null;
    const g = shape.geometry;
    return {
      x: Math.round(g.x * item.width),
      y: Math.round(g.y * item.height),
      w: Math.round(g.w * item.width),
      h: Math.round(g.h * item.height),
    };
  }
}
