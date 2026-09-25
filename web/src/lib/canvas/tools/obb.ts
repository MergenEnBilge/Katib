import { obbCorners, obbFromEdge } from '../geometry';
import type { ObbGeometry, Point, ToolEvent } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const DEFAULT_HINT = 'Drag along one edge of the object.';
const REACH_HINT = 'Move out to the far side, then click. Esc goes back.';
/** An edge shorter than this many screen pixels is treated as a stray click. */
const MIN_EDGE_PX = 6;

/**
 * Draws a rotated box in two steps. First drag along one edge, which sets the angle and the
 * length. Then move out to the opposite side and click to set the width.
 */
export class ObbTool implements Tool {
  readonly name = 'obb';
  private from: Point | null = null;
  private to: Point | null = null;
  private edgeDone = false;
  private reach: Point | null = null;
  private reaching = false;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(DEFAULT_HINT);
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    if (!this.edgeDone) {
      if (!this.ctx.activeClassId()) {
        this.ctx.needClass();
        return;
      }
      this.from = e.norm;
      this.to = e.norm;
      return;
    }
    this.reaching = true;
    this.reach = e.norm;
  }

  pointerMove(e: ToolEvent): void {
    if (!this.edgeDone) {
      if (!this.from) return;
      this.to = e.norm;
    } else {
      this.reach = e.norm;
    }
    this.ctx.requestRender();
  }

  pointerUp(e: ToolEvent): void {
    if (!this.edgeDone) {
      if (!this.from) return;
      const a = this.ctx.viewport.normToScreen(this.from);
      const b = this.ctx.viewport.normToScreen(e.norm);
      if (Math.hypot(a.x - b.x, a.y - b.y) < MIN_EDGE_PX) {
        this.reset();
        return;
      }
      this.to = e.norm;
      this.edgeDone = true;
      this.reach = e.norm;
      this.ctx.hint(REACH_HINT);
      this.ctx.requestRender();
      return;
    }
    if (!this.reaching) return;
    this.finish(e.norm);
  }

  private finish(reach: Point): void {
    const classId = this.ctx.activeClassId();
    const { imageW, imageH } = this.ctx.viewport;
    const box = this.from && this.to ? obbFromEdge(this.from, this.to, reach, imageW, imageH) : null;
    this.reset();
    if (!classId || !box) return;
    const id = this.ctx.newId();
    this.ctx.model.commit([
      { kind: 'create', shape: { id, type: 'obb', classId, geometry: box, attrs: {}, version: 0 } },
    ]);
    this.ctx.model.select([id]);
  }

  key(e: KeyInfo): boolean {
    if (e.key !== 'Escape') return false;
    if (this.edgeDone) {
      // Back to the first step, keeping nothing.
      this.reset();
      return true;
    }
    if (this.from) {
      this.reset();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.reset();
  }

  render(g: CanvasRenderingContext2D): void {
    if (!this.from || !this.to) return;
    const vp = this.ctx.viewport;
    const classId = this.ctx.activeClassId();
    const color = (classId && this.ctx.classStyle(classId)?.color) || '#ffffff';
    g.save();
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    g.setLineDash([6, 4]);
    const a = vp.normToScreen(this.from);
    const b = vp.normToScreen(this.to);
    if (this.edgeDone && this.reach) {
      const box: ObbGeometry | null = obbFromEdge(this.from, this.to, this.reach, vp.imageW, vp.imageH);
      if (box) {
        g.beginPath();
        obbCorners(box, vp.imageW, vp.imageH).forEach(([x, y], i) => {
          const p = vp.normToScreen({ x, y });
          if (i === 0) g.moveTo(p.x, p.y);
          else g.lineTo(p.x, p.y);
        });
        g.closePath();
        g.stroke();
        g.restore();
        return;
      }
    }
    g.beginPath();
    g.moveTo(a.x, a.y);
    g.lineTo(b.x, b.y);
    g.stroke();
    g.restore();
  }

  cursor(): string {
    return 'crosshair';
  }

  private reset(): void {
    this.from = null;
    this.to = null;
    this.reach = null;
    this.edgeDone = false;
    this.reaching = false;
    this.ctx.hint(DEFAULT_HINT);
    this.ctx.requestRender();
  }
}
