import { clamp01, polygonArea } from '../geometry';
import type { Point, ToolEvent } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const DEFAULT_HINT = 'Click to add points. Enter to close. Esc to cancel.';
const CLOSE_RADIUS = 12;
const DOUBLE_CLICK_MS = 300;
const DOUBLE_CLICK_PX = 6;

export class PolygonTool implements Tool {
  readonly name = 'polygon';
  private points: Point[] = [];
  private cursor_: Point | null = null;
  private lastClick: { time: number; x: number; y: number } | null = null;

  constructor(
    private readonly ctx: ToolContext,
    private readonly now: () => number = () => performance.now(),
  ) {}

  activate(): void {
    this.ctx.hint(DEFAULT_HINT);
  }

  private canClose(screen: Point): boolean {
    if (this.points.length < 3) return false;
    const first = this.ctx.viewport.normToScreen(this.points[0] as Point);
    return Math.hypot(first.x - screen.x, first.y - screen.y) <= CLOSE_RADIUS;
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    if (!this.ctx.activeClassId()) {
      this.ctx.needClass();
      return;
    }
    const time = this.now();
    const last = this.lastClick;
    this.lastClick = { time, x: e.screen.x, y: e.screen.y };
    if (this.canClose(e.screen)) {
      this.finish();
      return;
    }
    if (
      last &&
      this.points.length >= 3 &&
      time - last.time <= DOUBLE_CLICK_MS &&
      Math.hypot(last.x - e.screen.x, last.y - e.screen.y) <= DOUBLE_CLICK_PX
    ) {
      // The first click of a double click already added this point.
      this.finish();
      return;
    }
    this.points.push({ x: clamp01(e.norm.x), y: clamp01(e.norm.y) });
    this.ctx.hint(
      this.points.length >= 3
        ? 'Click the first point or press Enter to close. Backspace removes the last point.'
        : DEFAULT_HINT,
    );
    this.ctx.requestRender();
  }

  pointerMove(e: ToolEvent): void {
    this.cursor_ = e.norm;
    if (this.points.length > 0) this.ctx.requestRender();
  }

  pointerUp(): void {}

  key(e: KeyInfo): boolean {
    if (this.points.length === 0) return false;
    if (e.key === 'Enter') {
      this.finish();
      return true;
    }
    if (e.key === 'Escape') {
      this.cancel();
      return true;
    }
    if (e.key === 'Backspace') {
      this.points.pop();
      this.ctx.requestRender();
      return true;
    }
    return false;
  }

  private finish(): void {
    const classId = this.ctx.activeClassId();
    const pts = this.points.map((p): [number, number] => [p.x, p.y]);
    this.reset();
    if (!classId || pts.length < 3 || polygonArea(pts) <= 1e-6) return;
    const id = this.ctx.newId();
    this.ctx.model.commit([
      {
        kind: 'create',
        shape: {
          id,
          type: 'polygon',
          classId,
          geometry: { points: pts },
          attrs: {},
          version: 0,
        },
      },
    ]);
    this.ctx.model.select([id]);
  }

  cancel(): void {
    this.reset();
  }

  render(g: CanvasRenderingContext2D): void {
    if (this.points.length === 0) return;
    const vp = this.ctx.viewport;
    const classId = this.ctx.activeClassId();
    const color = (classId && this.ctx.classStyle(classId)?.color) || '#ffffff';
    const screen = this.points.map((p) => vp.normToScreen(p));
    g.save();
    g.strokeStyle = color;
    g.fillStyle = color;
    g.lineWidth = 1.5;
    g.beginPath();
    screen.forEach((p, i) => (i === 0 ? g.moveTo(p.x, p.y) : g.lineTo(p.x, p.y)));
    if (this.cursor_) {
      const c = vp.normToScreen(this.cursor_);
      g.setLineDash([6, 4]);
      g.lineTo(c.x, c.y);
    }
    g.stroke();
    g.setLineDash([]);
    screen.forEach((p, i) => {
      const canClose = i === 0 && this.cursor_ && this.canClose(vp.normToScreen(this.cursor_));
      g.beginPath();
      g.arc(p.x, p.y, canClose ? 6 : 3.5, 0, Math.PI * 2);
      g.fill();
    });
    g.restore();
  }

  cursor(): string {
    return 'crosshair';
  }

  private reset(): void {
    this.points = [];
    this.cursor_ = null;
    this.lastClick = null;
    this.ctx.hint(DEFAULT_HINT);
    this.ctx.requestRender();
  }
}
