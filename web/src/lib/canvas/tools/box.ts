import { boxFromPoints, isBigEnough } from '../geometry';
import type { BoxGeometry, Point, ToolEvent } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const DEFAULT_HINT = 'Drag to draw a box.';

export class BoxTool implements Tool {
  readonly name = 'box';
  private start: Point | null = null;
  private current: Point | null = null;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(DEFAULT_HINT);
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    if (!this.ctx.activeClassId()) {
      this.ctx.needClass();
      return;
    }
    this.start = e.norm;
    this.current = e.norm;
    this.ctx.hint('Release to finish. Esc to cancel.');
  }

  pointerMove(e: ToolEvent): void {
    if (!this.start) return;
    this.current = e.norm;
    this.ctx.requestRender();
  }

  pointerUp(e: ToolEvent): void {
    if (!this.start) return;
    const box = boxFromPoints(this.start, e.norm);
    const classId = this.ctx.activeClassId();
    this.reset();
    if (!classId || !isBigEnough(box)) return;
    const id = this.ctx.newId();
    this.ctx.model.commit([
      {
        kind: 'create',
        shape: { id, type: 'box', classId, geometry: box, attrs: {}, version: 0 },
      },
    ]);
    this.ctx.model.select([id]);
  }

  key(e: KeyInfo): boolean {
    if (e.key === 'Escape' && this.start) {
      this.cancel();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.reset();
  }

  render(g: CanvasRenderingContext2D): void {
    if (!this.start || !this.current) return;
    const vp = this.ctx.viewport;
    const box: BoxGeometry = boxFromPoints(this.start, this.current);
    const a = vp.normToScreen({ x: box.x, y: box.y });
    const b = vp.normToScreen({ x: box.x + box.w, y: box.y + box.h });
    const classId = this.ctx.activeClassId();
    const color = (classId && this.ctx.classStyle(classId)?.color) || '#ffffff';
    g.save();
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    g.setLineDash([6, 4]);
    g.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
    g.restore();
  }

  cursor(): string {
    return 'crosshair';
  }

  private reset(): void {
    this.start = null;
    this.current = null;
    this.ctx.hint(DEFAULT_HINT);
    this.ctx.requestRender();
  }
}
