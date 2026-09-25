import { SvelteSet } from 'svelte/reactivity';
import { api, ApiError } from '../api/client';
import type {
  Annotation,
  Comment,
  ImageItem,
  Lock,
  Member,
  Project,
  ProjectClass,
} from '../api/types';
import type { ClassStyle, Shape } from '../canvas/types';
import { isBox } from '../canvas/types';
import type { Engine } from '../canvas/engine';
import { Autosave, shapeFromAnnotation, type SaveState } from '../sync/autosave';
import { browserOutbox } from '../sync/outbox';
import { isoIn, Realtime, type PresenceUser, type ServerEvent } from '../sync/realtime';
import { session } from './session.svelte';
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
  presence = $state<PresenceUser[]>([]);
  members = $state<Member[]>([]);
  comments = $state<Comment[]>([]);
  /** Someone else holds the edit lock on the open image. */
  lockedByOther = $state<Lock | null>(null);

  engine = $state.raw<Engine | null>(null);
  private autosave: Autosave | null = null;
  private clipboard: Shape[] = [];
  private openToken = 0;
  private stopModel: (() => void)[] = [];
  private classRefresh: ReturnType<typeof setTimeout> | undefined;

  private realtime: Realtime | null = null;
  private lockTimer: ReturnType<typeof setInterval> | undefined;
  private lockedImage: string | null = null;

  constructor(readonly projectId: string) {}

  get role(): string {
    return this.project?.role ?? 'viewer';
  }

  get canEdit(): boolean {
    return this.role !== 'viewer';
  }

  get canManage(): boolean {
    return this.role === 'owner' || this.role === 'manager';
  }

  get canReview(): boolean {
    return this.canManage || this.role === 'reviewer';
  }

  /** Editing is off for viewers and while someone else has the image open. */
  get readOnly(): boolean {
    return !this.canEdit || this.lockedByOther !== null;
  }

  /** Other people in the project, for the presence avatars. */
  get others(): PresenceUser[] {
    const me = session.user?.id;
    return this.presence.filter(
      (p, i, all) => p.user_id !== me && all.findIndex((q) => q.user_id === p.user_id) === i,
    );
  }

  get current(): ImageItem | null {
    return this.images.find((i) => i.id === this.currentId) ?? null;
  }

  get currentIndex(): number {
    return this.images.findIndex((i) => i.id === this.currentId);
  }

  /** The annotation types this project uses, in toolbar order. */
  get types(): string[] {
    return this.project?.annotation_types ?? ['box', 'polygon'];
  }

  /** Classes that have a tag on the open image. */
  taggedClasses(): Set<string> {
    void this.modelTick;
    const model = this.engine?.model;
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    return new Set((model?.shapes ?? []).filter((s) => s.type === 'tag').map((s) => s.classId));
  }

  /** Add the class as a tag on the open image, or take it off when it is already there. */
  toggleTag(classId: string): void {
    const model = this.engine?.model;
    if (!model || this.readOnly) return;
    const existing = model.shapes.find((s) => s.type === 'tag' && s.classId === classId);
    if (existing) {
      model.commit([{ kind: 'delete', shape: existing }]);
      return;
    }
    model.commit([
      {
        kind: 'create',
        shape: { id: crypto.randomUUID(), type: 'tag', classId, geometry: {}, attrs: {}, version: 0 },
      },
    ]);
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
        skeleton: c.skeleton
          ? { names: [...c.skeleton.names], edges: (c.skeleton.edges ?? []).map(([a, b]) => [a, b] as [number, number]) }
          : null,
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

  private startRealtime(): void {
    if (session.mode !== 'local' || this.realtime) return;
    this.realtime = new Realtime({
      projectId: this.projectId,
      onEvent: (event) => this.onEvent(event),
      onReconnect: () => void this.refresh().then(() => this.reloadCurrent()),
    });
    this.realtime.connect();
  }

  private onEvent(event: ServerEvent): void {
    const me = session.user?.id;
    switch (event.type) {
      case 'presence':
        this.presence = event.users;
        break;
      case 'class.changed':
        void this.refreshClasses();
        break;
      case 'image.status': {
        const item = this.images.find((i) => i.id === event.image_id);
        if (item) item.status = event.status;
        break;
      }
      case 'image.locked': {
        const item = this.images.find((i) => i.id === event.image_id);
        const lock: Lock = {
          user_id: event.user_id,
          name: event.name,
          until: isoIn(45_000),
          mine: event.user_id === me,
        };
        if (item) item.lock = lock;
        if (event.image_id === this.currentId) this.lockedByOther = lock.mine ? null : lock;
        break;
      }
      case 'image.unlocked': {
        const item = this.images.find((i) => i.id === event.image_id);
        if (item) item.lock = null;
        if (event.image_id === this.currentId && this.lockedByOther) {
          this.lockedByOther = null;
          void this.acquireLock();
        }
        break;
      }
      case 'annotation.changed':
        if (event.image_id === this.currentId && event.user_id !== me && this.pending === 0) {
          void this.reloadCurrent();
        }
        break;
      default:
        break;
    }
  }

  /** Take the edit lock for the open image and keep it alive. A held lock means read-only. */
  private async acquireLock(): Promise<void> {
    const id = this.currentId;
    if (!id || session.mode !== 'local' || !this.canEdit) return;
    try {
      await api.work.lock(id);
      if (id === this.currentId) this.lockedByOther = null;
      this.lockedImage = id;
    } catch (err) {
      if (err instanceof ApiError && err.code === 'image_locked' && id === this.currentId) {
        const d = err.details as { user_id?: string; name?: string; until?: string };
        this.lockedByOther = {
          user_id: d.user_id ?? '',
          name: d.name ?? null,
          until: d.until ?? isoIn(0),
          mine: false,
        };
      }
    }
    this.applyReadOnly();
    clearInterval(this.lockTimer);
    this.lockTimer = setInterval(() => void this.acquireLock(), 15_000);
  }

  private async releaseLock(): Promise<void> {
    clearInterval(this.lockTimer);
    const id = this.lockedImage;
    this.lockedImage = null;
    if (id && session.mode === 'local') await api.work.unlock(id).catch(() => undefined);
  }

  applyReadOnly(): void {
    if (this.engine) this.engine.readOnly = this.readOnly;
  }

  async takeOver(): Promise<void> {
    const id = this.currentId;
    if (!id) return;
    try {
      await api.work.takeOver(id);
      this.lockedByOther = null;
      this.lockedImage = id;
      this.applyReadOnly();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not take over.');
    }
  }

  detach(): void {
    this.realtime?.close();
    this.realtime = null;
    void this.releaseLock();
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
      this.startRealtime();
      void this.loadMembers();
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
    await this.releaseLock();
    this.autosave?.dispose();
    this.autosave = null;
    this.lockedByOther = null;
    const token = ++this.openToken;
    this.currentId = imageId;
    this.imageLoading = true;
    const item = this.images.find((i) => i.id === imageId);
    try {
      const annotations: Annotation[] = await api.annotations.list(imageId);
      if (token !== this.openToken) return;
      const fresh = item ?? (await api.images.get(imageId));
      engine.model.load(annotations.map(shapeFromAnnotation));
      if (item) item.annotation_count = annotations.length;
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
        outbox: browserOutbox,
      }, annotations);
      this.saveState = 'saved';
      this.pending = 0;
      await engine.setImage(api.images.fileUrl(imageId), fresh.width, fresh.height);
      this.prefetch(imageId);
      this.realtime?.setViewing(imageId);
      void this.loadComments();
      await this.acquireLock();
      this.applyReadOnly();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not open this image.');
    } finally {
      if (token === this.openToken) this.imageLoading = false;
    }
  }

  async loadMembers(): Promise<void> {
    try {
      this.members = await api.members.list(this.projectId);
    } catch {
      this.members = [];
    }
  }

  async loadComments(): Promise<void> {
    const id = this.currentId;
    if (!id) {
      this.comments = [];
      return;
    }
    try {
      const list = await api.work.comments(id);
      if (id === this.currentId) this.comments = list;
    } catch {
      this.comments = [];
    }
  }

  async addComment(body: string): Promise<void> {
    const id = this.currentId;
    if (!id) return;
    try {
      await api.work.comment(id, body);
      await this.loadComments();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not add the comment.');
    }
  }

  async resolveComment(id: string, resolved: boolean): Promise<void> {
    try {
      await api.work.resolve(id, resolved);
      await this.loadComments();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not update the comment.');
    }
  }

  /** Approve or send back the open image. */
  async review(status: 'approved' | 'rejected'): Promise<void> {
    const item = this.current;
    if (!item) return;
    await this.flushNow();
    try {
      const updated = await api.work.setStatus(item.id, status);
      item.status = updated.status;
      item.reviewer_id = updated.reviewer_id;
      toasts.show(status === 'approved' ? 'Approved.' : 'Sent back for changes.');
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not update the image.');
    }
  }

  /** Ask the queue for the next image for me. */
  async takeNext(): Promise<void> {
    try {
      const { image } = await api.work.next(this.projectId);
      if (!image) {
        toasts.show('No images are waiting for you right now.');
        return;
      }
      if (!this.images.some((i) => i.id === image.id)) this.images = [...this.images, image];
      await this.open(image.id);
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not get the next image.');
    }
  }

  async assignCurrent(assigneeId: string | null): Promise<void> {
    const item = this.current;
    if (!item) return;
    try {
      await api.work.assign(this.projectId, [item.id], assigneeId);
      item.assignee_id = assigneeId;
      toasts.show(assigneeId ? 'Assigned.' : 'Assignment cleared.');
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not assign that.');
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
