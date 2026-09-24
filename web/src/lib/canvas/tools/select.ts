import { boundsOf, clamp01, resizeBox, translate } from '../geometry';
import { handleAt, hitShape, isBoxHandle, segmentAt } from '../hit';
import type { Change } from '../model';
import type { BoxGeometry, Point, PolygonGeometry, Shape, ToolEvent } from '../types';
import { isBox, isPolygon } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const DRAG_THRESHOLD_PX = 3;
const DUPLICATE_OFFSET = 0.02;
const DEFAULT_HINT = 'Click a shape to select it. Drag to move. Drag empty space to select several.';

type Geometry = BoxGeometry | PolygonGeometry;

type Drag =
  | {
      kind: 'move';
      startScreen: Point;
      startNorm: Point;
      originals: Map<string, Geometry>;
      active: boolean;
    }
  | { kind: 'handle'; id: string; handle: string; baseline: Geometry; working: Geometry }
  | { kind: 'marquee'; startScreen: Point; startNorm: Point; current: Point; additive: boolean };

const RESIZE_CURSORS: Record<string, string> = {
  nw: 'nwse-resize',
  se: 'nwse-resize',
  ne: 'nesw-resize',
  sw: 'nesw-resize',
  n: 'ns-resize',
  s: 'ns-resize',
  e: 'ew-resize',
  w: 'ew-resize',
};

export class SelectTool implements Tool {
  readonly name = 'select';
  private drag: Drag | null = null;
  private hoverHandle: { shapeId: string; handle: string } | null = null;
  private hoverShape: string | null = null;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(DEFAULT_HINT);
  }

  private editable = (s: Shape): boolean => {
    const style = this.ctx.classStyle(s.classId);
    return !style?.locked && !style?.hidden;
  };

  private hittable = (s: Shape): boolean => !this.ctx.classStyle(s.classId)?.hidden;

  private selectedShapes(): Shape[] {
    const { model } = this.ctx;
    return model.visible().filter((s) => model.selection.has(s.id));
  }

  private single(): Shape | null {
    const selected = this.selectedShapes();
    const only = selected.length === 1 ? (selected[0] as Shape) : null;
    return only && this.editable(only) ? only : null;
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    const { model, viewport } = this.ctx;
    const only = this.single();

    if (only) {
      const handle = handleAt(only, e.screen, viewport, e.pointerType);
      if (handle) {
        this.drag = {
          kind: 'handle',
          id: only.id,
          handle: handle.id,
          baseline: structuredClone(only.geometry),
          working: only.geometry,
        };
        return;
      }
      if (isPolygon(only.geometry)) {
        const seg = segmentAt(only, e.screen, viewport);
        if (seg) {
          const points = [...only.geometry.points];
          points.splice(seg.index + 1, 0, [seg.point.x, seg.point.y]);
          const working: PolygonGeometry = { points };
          this.drag = {
            kind: 'handle',
            id: only.id,
            handle: `v${seg.index + 1}`,
            baseline: structuredClone(only.geometry),
            working,
          };
          model.setPreview(only.id, working);
          return;
        }
      }
    }

    const hit = hitShape(model.visible(), e.norm, viewport, (s) => !this.hittable(s));
    if (hit) {
      if (e.shift) {
        model.toggle(hit.id);
        if (!model.selection.has(hit.id)) return;
      } else if (!model.selection.has(hit.id)) {
        model.select([hit.id]);
      }
      const originals = new Map<string, Geometry>();
      for (const s of this.selectedShapes()) {
        if (this.editable(s)) originals.set(s.id, structuredClone(s.geometry));
      }
      this.drag = {
        kind: 'move',
        startScreen: e.screen,
        startNorm: e.norm,
        originals,
        active: false,
      };
      return;
    }

    if (!e.shift) model.clearSelection();
    this.drag = {
      kind: 'marquee',
      startScreen: e.screen,
      startNorm: e.norm,
      current: e.norm,
      additive: e.shift,
    };
  }

  pointerMove(e: ToolEvent): void {
    const { model } = this.ctx;
    const drag = this.drag;
    if (!drag) {
      this.updateHover(e);
      return;
    }
    if (drag.kind === 'move') {
      if (
        !drag.active &&
        Math.hypot(e.screen.x - drag.startScreen.x, e.screen.y - drag.startScreen.y) <
          DRAG_THRESHOLD_PX
      ) {
        return;
      }
      drag.active = true;
      const dx = e.norm.x - drag.startNorm.x;
      const dy = e.norm.y - drag.startNorm.y;
      drag.originals.forEach((geometry, id) => model.setPreview(id, translate(geometry, dx, dy)));
    } else if (drag.kind === 'handle') {
      const p = { x: clamp01(e.norm.x), y: clamp01(e.norm.y) };
      if (isBoxHandle(drag.handle) && isBox(drag.baseline)) {
        drag.working = resizeBox(drag.baseline, drag.handle, p);
      } else if (isPolygon(drag.working)) {
        const index = Number(drag.handle.slice(1));
        const points = [...drag.working.points];
        points[index] = [p.x, p.y];
        drag.working = { points };
      }
      model.setPreview(drag.id, drag.working);
    } else {
      drag.current = e.norm;
      this.ctx.requestRender();
    }
  }

  pointerUp(e: ToolEvent): void {
    const { model } = this.ctx;
    const drag = this.drag;
    this.drag = null;
    if (!drag) return;

    if (drag.kind === 'marquee') {
      const moved =
        Math.hypot(e.screen.x - drag.startScreen.x, e.screen.y - drag.startScreen.y) >=
        DRAG_THRESHOLD_PX;
      if (moved) {
        const x0 = Math.min(drag.startNorm.x, e.norm.x);
        const x1 = Math.max(drag.startNorm.x, e.norm.x);
        const y0 = Math.min(drag.startNorm.y, e.norm.y);
        const y1 = Math.max(drag.startNorm.y, e.norm.y);
        const ids = model
          .visible()
          .filter((s) => this.hittable(s))
          .filter((s) => {
            const b = boundsOf(s);
            return b.x <= x1 && b.x + b.w >= x0 && b.y <= y1 && b.y + b.h >= y0;
          })
          .map((s) => s.id);
        model.select(ids, drag.additive);
      }
      this.ctx.requestRender();
      return;
    }

    const changes: Change[] = [];
    if (drag.kind === 'move') {
      if (drag.active) {
        for (const [id, before] of drag.originals) {
          const shape = model.visible().find((s) => s.id === id);
          if (shape) {
            changes.push({
              kind: 'update',
              id,
              before: { geometry: before },
              after: { geometry: shape.geometry },
            });
          }
        }
      }
    } else if (JSON.stringify(drag.working) !== JSON.stringify(drag.baseline)) {
      changes.push({
        kind: 'update',
        id: drag.id,
        before: { geometry: drag.baseline },
        after: { geometry: drag.working },
      });
    }
    if (changes.length > 0) model.commit(changes);
    else model.clearPreview();
  }

  private updateHover(e: ToolEvent): void {
    const { model, viewport } = this.ctx;
    const only = this.single();
    this.hoverHandle = null;
    if (only) {
      const h = handleAt(only, e.screen, viewport, e.pointerType);
      if (h) this.hoverHandle = { shapeId: only.id, handle: h.id };
    }
    const hit = hitShape(model.visible(), e.norm, viewport, (s) => !this.hittable(s));
    this.hoverShape = hit?.id ?? null;
  }

  key(e: KeyInfo): boolean {
    const { model, viewport } = this.ctx;
    if (e.key === 'Escape') {
      if (this.drag) {
        this.cancel();
        return true;
      }
      if (model.selection.size > 0) {
        model.clearSelection();
        return true;
      }
      return false;
    }

    if (e.key === 'Tab') {
      const list = model.visible().filter((s) => this.hittable(s));
      if (list.length === 0) return false;
      const current = list.findIndex((s) => model.selection.has(s.id));
      const step = e.shift ? -1 : 1;
      const next = current === -1 ? (step === 1 ? 0 : list.length - 1) : (current + step + list.length) % list.length;
      model.select([(list[next] as Shape).id]);
      return true;
    }

    if (e.ctrl && e.key.toLowerCase() === 'a') {
      model.select(model.visible().filter((s) => this.hittable(s)).map((s) => s.id));
      return true;
    }

    const targets = this.selectedShapes().filter((s) => this.editable(s));

    if (e.key === 'Delete' || e.key === 'Backspace') {
      const vertex = this.hoverHandle;
      const only = this.single();
      if (vertex && only && only.id === vertex.shapeId && isPolygon(only.geometry) && /^v\d+$/.test(vertex.handle)) {
        if (only.geometry.points.length > 3) {
          const index = Number(vertex.handle.slice(1));
          const before = only.geometry;
          const after: PolygonGeometry = { points: before.points.filter((_, i) => i !== index) };
          model.commit([{ kind: 'update', id: only.id, before: { geometry: before }, after: { geometry: after } }]);
          this.hoverHandle = null;
        }
        return true;
      }
      if (targets.length === 0) return false;
      model.commit(targets.map((shape): Change => ({ kind: 'delete', shape })));
      return true;
    }

    if (e.key.startsWith('Arrow') && targets.length > 0) {
      const step = e.shift ? 10 : 1;
      const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0;
      const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
      model.commit(
        targets.map((s): Change => ({
          kind: 'update',
          id: s.id,
          before: { geometry: s.geometry },
          after: { geometry: translate(s.geometry, dx / viewport.imageW, dy / viewport.imageH) },
        })),
      );
      return true;
    }

    if (e.ctrl && e.key.toLowerCase() === 'd' && targets.length > 0) {
      const copies = targets.map((s): Shape => ({
        ...s,
        id: this.ctx.newId(),
        geometry: translate(s.geometry, DUPLICATE_OFFSET, DUPLICATE_OFFSET),
        attrs: { ...s.attrs },
        version: 0,
      }));
      model.commit(copies.map((shape): Change => ({ kind: 'create', shape })));
      model.select(copies.map((s) => s.id));
      return true;
    }
    return false;
  }

  cancel(): void {
    this.drag = null;
    this.ctx.model.clearPreview();
    this.ctx.requestRender();
  }

  render(g: CanvasRenderingContext2D): void {
    const drag = this.drag;
    if (!drag || drag.kind !== 'marquee') return;
    const vp = this.ctx.viewport;
    const a = vp.normToScreen(drag.startNorm);
    const b = vp.normToScreen(drag.current);
    g.save();
    g.strokeStyle = this.ctx.accent();
    g.fillStyle = this.ctx.accent();
    g.lineWidth = 1;
    g.setLineDash([4, 3]);
    g.globalAlpha = 0.12;
    g.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    g.globalAlpha = 1;
    g.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
    g.restore();
  }

  cursor(): string {
    if (this.drag?.kind === 'move' && this.drag.active) return 'move';
    if (this.drag?.kind === 'handle') return RESIZE_CURSORS[this.drag.handle] ?? 'move';
    if (this.hoverHandle) return RESIZE_CURSORS[this.hoverHandle.handle] ?? 'move';
    if (this.hoverShape && this.ctx.model.selection.has(this.hoverShape)) return 'move';
    return 'default';
  }
}
