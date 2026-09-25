import type { Point, ToolEvent } from '../types';
import { wandPolygon } from '../wand';
import type { KeyInfo, Tool, ToolContext } from './tool';

const MIN_TOLERANCE = 4;
const MAX_TOLERANCE = 120;
const STEP = 4;
/** Recompute the preview only after the pointer has moved this many screen pixels. */
const PREVIEW_MOVE_PX = 5;

/**
 * Click inside an object and get an outline of the area around the click with a similar color.
 * Moving the pointer shows what a click would make. [ and ] change how alike the colors must be.
 */
export class WandTool implements Tool {
  readonly name = 'wand';
  tolerance = 32;
  private preview: [number, number][] | null = null;
  private previewAt: Point | null = null;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(this.idleHint());
  }

  private idleHint(): string {
    return `Click inside an object to outline it. [ and ] change the color range (now ${this.tolerance}).`;
  }

  private outline(norm: Point): [number, number][] | null {
    const pixels = this.ctx.pixels();
    return pixels ? wandPolygon(pixels, norm.x, norm.y, this.tolerance) : null;
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    const classId = this.ctx.activeClassId();
    if (!classId) {
      this.ctx.needClass();
      return;
    }
    if (!this.ctx.pixels()) {
      this.ctx.hint('The picture is still loading.');
      return;
    }
    const points = this.outline(e.norm);
    if (!points) {
      this.ctx.hint('Nothing to outline there. Try a wider color range with ].');
      return;
    }
    const id = this.ctx.newId();
    this.ctx.model.commit([
      {
        kind: 'create',
        shape: { id, type: 'polygon', classId, geometry: { points }, attrs: {}, version: 0 },
      },
    ]);
    this.ctx.model.select([id]);
    this.preview = null;
    this.previewAt = null;
    this.ctx.hint(this.idleHint());
  }

  pointerMove(e: ToolEvent): void {
    const last = this.previewAt;
    if (last && Math.hypot(e.screen.x - last.x, e.screen.y - last.y) < PREVIEW_MOVE_PX) return;
    this.previewAt = e.screen;
    this.preview = this.outline(e.norm);
    this.ctx.requestRender();
  }

  pointerUp(): void {}

  key(e: KeyInfo): boolean {
    if (e.key !== '[' && e.key !== ']') return false;
    const change = e.key === ']' ? STEP : -STEP;
    this.tolerance = Math.min(MAX_TOLERANCE, Math.max(MIN_TOLERANCE, this.tolerance + change));
    this.preview = null;
    this.previewAt = null;
    this.ctx.hint(this.idleHint());
    this.ctx.requestRender();
    return true;
  }

  cancel(): void {
    this.preview = null;
    this.previewAt = null;
    this.ctx.requestRender();
  }

  render(g: CanvasRenderingContext2D): void {
    if (!this.preview) return;
    const vp = this.ctx.viewport;
    const classId = this.ctx.activeClassId();
    const color = (classId && this.ctx.classStyle(classId)?.color) || '#ffffff';
    g.save();
    g.beginPath();
    this.preview.forEach(([x, y], i) => {
      const p = vp.normToScreen({ x, y });
      if (i === 0) g.moveTo(p.x, p.y);
      else g.lineTo(p.x, p.y);
    });
    g.closePath();
    g.fillStyle = color;
    g.globalAlpha = 0.18;
    g.fill();
    g.globalAlpha = 1;
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    g.setLineDash([6, 4]);
    g.stroke();
    g.restore();
  }

  cursor(): string {
    return 'crosshair';
  }
}
