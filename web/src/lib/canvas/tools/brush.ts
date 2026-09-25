import {
  anyOn,
  encodeRuns,
  gridFor,
  maskCells,
  maskToCanvas,
  paintDisc,
  paintLine,
} from '../mask';
import type { Point, Shape, ToolEvent } from '../types';
import { isMask } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const MIN_RADIUS = 1;
const MAX_RADIUS = 40;

interface Stroke {
  /** The mask being changed, or null when this stroke starts a new one. */
  existing: Shape | null;
  cells: Uint8Array;
  size: [number, number];
  last: Point;
  changed: boolean;
}

/**
 * Paints a mask on a coarse grid. Painting over a selected mask of the same class adds to it.
 * A stroke that starts with nothing selected makes a new mask.
 */
export class BrushTool implements Tool {
  readonly name = 'brush';
  radius = 5;
  erasing = false;
  private stroke: Stroke | null = null;
  private pointer: Point | null = null;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(this.idleHint());
  }

  private idleHint(): string {
    const mode = this.erasing ? 'Erasing' : 'Painting';
    return `${mode}. Drag to paint. E switches between paint and erase. [ and ] change the brush size.`;
  }

  /** The mask a stroke should add to: the one selected shape, when it is a mask of the active class. */
  private target(): Shape | null {
    const { model } = this.ctx;
    const classId = this.ctx.activeClassId();
    const selected = model.visible().filter((s) => model.selection.has(s.id));
    const only = selected.length === 1 ? (selected[0] as Shape) : null;
    return only && isMask(only.geometry) && only.classId === classId ? only : null;
  }

  private cellPoint(norm: Point, size: [number, number]): Point {
    return { x: norm.x * size[0], y: norm.y * size[1] };
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    if (!this.ctx.activeClassId()) {
      this.ctx.needClass();
      return;
    }
    const { imageW, imageH } = this.ctx.viewport;
    const existing = this.target();
    const geometry = existing && isMask(existing.geometry) ? existing.geometry : null;
    const stored = geometry ? maskCells(geometry) : null;
    const size: [number, number] = geometry && stored ? geometry.size : gridFor(imageW, imageH);
    // Copy the stored cells: the decoded array is shared with the renderer's cache.
    const cells = stored ? stored.slice() : new Uint8Array(size[0] * size[1]);
    const at = this.cellPoint(e.norm, size);
    this.stroke = { existing: stored ? existing : null, cells, size, last: at, changed: false };
    this.paint(at, at);
  }

  private paint(from: Point, to: Point): void {
    const s = this.stroke;
    if (!s) return;
    const value = this.erasing ? 0 : 1;
    const hit =
      from === to
        ? paintDisc(s.cells, s.size[0], s.size[1], to.x, to.y, this.radius, value)
        : paintLine(s.cells, s.size[0], s.size[1], from, to, this.radius, value);
    s.changed ||= hit;
    if (s.existing && hit) {
      this.ctx.model.setPreview(s.existing.id, { rle: encodeRuns(s.cells), size: s.size });
    }
    this.ctx.requestRender();
  }

  pointerMove(e: ToolEvent): void {
    this.pointer = e.norm;
    const s = this.stroke;
    if (!s) {
      this.ctx.requestRender();
      return;
    }
    const at = this.cellPoint(e.norm, s.size);
    this.paint(s.last, at);
    s.last = at;
  }

  pointerUp(): void {
    const s = this.stroke;
    this.stroke = null;
    if (!s) return;
    const { model } = this.ctx;
    const classId = this.ctx.activeClassId();
    if (!s.changed || !classId) {
      model.clearPreview();
      this.ctx.requestRender();
      return;
    }
    const rle = encodeRuns(s.cells);
    if (s.existing) {
      const before = s.existing.geometry;
      if (!anyOn(s.cells)) {
        model.clearPreview();
        model.commit([{ kind: 'delete', shape: { ...s.existing, geometry: before } }]);
      } else {
        model.commit([
          {
            kind: 'update',
            id: s.existing.id,
            before: { geometry: before },
            after: { geometry: { rle, size: s.size } },
          },
        ]);
      }
    } else if (anyOn(s.cells)) {
      const id = this.ctx.newId();
      model.commit([
        {
          kind: 'create',
          shape: {
            id,
            type: 'mask',
            classId,
            geometry: { rle, size: s.size },
            attrs: {},
            version: 0,
          },
        },
      ]);
      model.select([id]);
    }
    this.ctx.requestRender();
  }

  key(e: KeyInfo): boolean {
    const key = e.key.toLowerCase();
    if (key === 'e') {
      this.erasing = !this.erasing;
      this.ctx.hint(this.idleHint());
      this.ctx.requestRender();
      return true;
    }
    if (e.key === '[' || e.key === ']') {
      const step = e.key === ']' ? 1 : -1;
      this.radius = Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, this.radius + step));
      this.ctx.requestRender();
      return true;
    }
    if (e.key === 'Escape' && this.stroke) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.stroke = null;
    this.ctx.model.clearPreview();
    this.ctx.requestRender();
  }

  render(g: CanvasRenderingContext2D): void {
    const vp = this.ctx.viewport;
    const s = this.stroke;
    const classId = this.ctx.activeClassId();
    const color = (classId && this.ctx.classStyle(classId)?.color) || '#ffffff';
    if (s && !s.existing) {
      const art = maskToCanvas(s.cells, s.size[0], s.size[1], color);
      const a = vp.normToScreen({ x: 0, y: 0 });
      const b = vp.normToScreen({ x: 1, y: 1 });
      g.save();
      g.globalAlpha = 0.5;
      g.imageSmoothingEnabled = false;
      g.drawImage(art, a.x, a.y, b.x - a.x, b.y - a.y);
      g.restore();
    }
    if (!this.pointer) return;
    // The brush outline, sized to match what one stroke will cover.
    const size = s?.size ?? gridFor(vp.imageW, vp.imageH);
    const centre = vp.normToScreen(this.pointer);
    const cellPx = (vp.imageW * vp.scale) / size[0];
    g.save();
    g.strokeStyle = this.erasing ? '#ffffff' : color;
    g.setLineDash(this.erasing ? [3, 3] : []);
    g.lineWidth = 1.5;
    g.beginPath();
    g.arc(centre.x, centre.y, this.radius * cellPx, 0, Math.PI * 2);
    g.stroke();
    g.restore();
  }

  cursor(): string {
    return 'none';
  }
}
