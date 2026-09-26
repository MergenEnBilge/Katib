import type { Point, ToolEvent } from '../types';
import type { KeyInfo, SegmentClick, Tool, ToolContext } from './tool';

/**
 * Click an object and a model outlines it.
 *
 * The model runs on the server, so an outline takes a moment to come back and the first click on
 * a picture takes longer than the rest. Between the click and the answer the tool shows where it
 * was clicked, so nothing feels stuck. Clicking again adds to the same outline rather than
 * starting a new one, which is how you rescue a shape that grabbed too little or too much.
 */
export class SmartTool implements Tool {
  readonly name = 'smart';
  private clicks: SegmentClick[] = [];
  private shapeId: string | null = null;
  /** Counts requests so a slow answer to an old click cannot overwrite a newer one. */
  private attempt = 0;
  private busy = false;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(this.idleHint());
  }

  private idleHint(): string {
    return 'Click an object to outline it. Shift-click to add to it, Ctrl-click to cut it back.';
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    const classId = this.ctx.activeClassId();
    if (!classId) {
      this.ctx.needClass();
      return;
    }
    if (!this.ctx.segment) {
      this.ctx.hint('This Katib has no model for clicking objects.');
      return;
    }
    const refining = (e.shift || e.ctrl) && this.shapeId !== null;
    if (!refining) {
      this.clicks = [];
      this.shapeId = null;
    }
    this.clicks = [...this.clicks, { x: e.norm.x, y: e.norm.y, positive: !e.ctrl }];
    void this.ask(classId);
  }

  private async ask(classId: string): Promise<void> {
    const segment = this.ctx.segment;
    if (!segment) return;
    const mine = ++this.attempt;
    this.busy = true;
    this.ctx.hint(this.clicks.length > 1 ? 'Working it out...' : 'Looking at the picture...');
    this.ctx.requestRender();
    let points: [number, number][] | null;
    try {
      points = await segment(this.clicks);
    } catch (err) {
      if (mine === this.attempt) {
        this.busy = false;
        this.reset();
        this.ctx.hint(err instanceof Error ? err.message : 'That did not work. Try again.');
        this.ctx.requestRender();
      }
      return;
    }
    if (mine !== this.attempt) return; // a newer click has already replaced this one
    this.busy = false;
    if (!points || points.length < 3) {
      this.ctx.hint('Nothing found there. Try clicking the middle of the object.');
      this.clicks = this.clicks.slice(0, -1);
      this.ctx.requestRender();
      return;
    }
    this.place(classId, points);
  }

  private place(classId: string, points: [number, number][]): void {
    const existing = this.shapeId ? this.ctx.model.get(this.shapeId) : undefined;
    if (existing) {
      this.ctx.model.commit([
        {
          kind: 'update',
          id: existing.id,
          before: { geometry: existing.geometry },
          after: { geometry: { points } },
        },
      ]);
    } else {
      const id = this.ctx.newId();
      this.ctx.model.commit([
        {
          kind: 'create',
          shape: { id, type: 'polygon', classId, geometry: { points }, attrs: {}, version: 0 },
        },
      ]);
      this.ctx.model.select([id]);
      this.shapeId = id;
    }
    this.ctx.hint(this.idleHint());
    this.ctx.requestRender();
  }

  private reset(): void {
    this.clicks = [];
    this.shapeId = null;
  }

  pointerMove(): void {}

  pointerUp(): void {}

  key(e: KeyInfo): boolean {
    if (e.key !== 'Escape' || this.clicks.length === 0) return false;
    this.attempt++;
    this.busy = false;
    this.reset();
    this.ctx.hint(this.idleHint());
    this.ctx.requestRender();
    return true;
  }

  cancel(): void {
    this.attempt++;
    this.busy = false;
    this.reset();
    this.ctx.requestRender();
  }

  render(g: CanvasRenderingContext2D): void {
    if (this.clicks.length === 0) return;
    const vp = this.ctx.viewport;
    g.save();
    for (const click of this.clicks) {
      const at: Point = vp.normToScreen({ x: click.x, y: click.y });
      g.beginPath();
      g.arc(at.x, at.y, 5, 0, Math.PI * 2);
      g.fillStyle = click.positive ? this.ctx.accent() : '#d9534f';
      g.fill();
      g.strokeStyle = '#ffffff';
      g.lineWidth = 1.5;
      g.stroke();
    }
    if (this.busy) {
      const last = this.clicks[this.clicks.length - 1] as SegmentClick;
      const at = vp.normToScreen({ x: last.x, y: last.y });
      g.beginPath();
      g.arc(at.x, at.y, 12, 0, Math.PI * 2);
      g.strokeStyle = this.ctx.accent();
      g.lineWidth = 2;
      g.setLineDash([4, 4]);
      g.stroke();
    }
    g.restore();
  }

  cursor(): string {
    return this.busy ? 'progress' : 'crosshair';
  }
}
