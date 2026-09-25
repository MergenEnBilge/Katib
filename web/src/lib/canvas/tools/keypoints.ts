import { clamp01 } from '../geometry';
import type { Landmark, Point, SkeletonStyle, ToolEvent } from '../types';
import type { KeyInfo, Tool, ToolContext } from './tool';

const NO_SKELETON_HINT =
  'This class has no landmarks yet. Add them under Manage classes, then draw again.';

/**
 * Places landmarks one after another, in the order the class's skeleton lists them. Shift plus
 * click marks a landmark as hidden, N skips it, and Enter finishes early.
 */
export class KeypointsTool implements Tool {
  readonly name = 'keypoints';
  private placed: Landmark[] = [];
  private classId: string | null = null;
  private skeleton: SkeletonStyle | null = null;
  private pointer: Point | null = null;

  constructor(private readonly ctx: ToolContext) {}

  activate(): void {
    this.ctx.hint(this.idleHint());
  }

  private idleHint(): string {
    const id = this.ctx.activeClassId();
    const skeleton = id ? this.ctx.classStyle(id)?.skeleton : null;
    if (id && !skeleton) return NO_SKELETON_HINT;
    return skeleton ? `Click the ${skeleton.names[0]}.` : 'Choose a class to place landmarks.';
  }

  private prompt(): string {
    const next = this.skeleton?.names[this.placed.length];
    return next
      ? `Click the ${next}. Shift+click if it is hidden, N to skip, Enter to finish, Esc to cancel.`
      : '';
  }

  pointerDown(e: ToolEvent): void {
    if (e.button !== 0) return;
    if (!this.skeleton) {
      const id = this.ctx.activeClassId();
      if (!id) {
        this.ctx.needClass();
        return;
      }
      const skeleton = this.ctx.classStyle(id)?.skeleton;
      if (!skeleton) {
        this.ctx.hint(NO_SKELETON_HINT);
        return;
      }
      this.classId = id;
      this.skeleton = skeleton;
    }
    this.place({ x: clamp01(e.norm.x), y: clamp01(e.norm.y), v: e.shift ? 1 : 2 });
  }

  private place(point: Landmark): void {
    this.placed.push(point);
    if (this.skeleton && this.placed.length >= this.skeleton.names.length) {
      this.finish();
      return;
    }
    this.ctx.hint(this.prompt());
    this.ctx.requestRender();
  }

  pointerMove(e: ToolEvent): void {
    this.pointer = e.norm;
    if (this.placed.length > 0) this.ctx.requestRender();
  }

  pointerUp(): void {}

  private finish(): void {
    const { classId, skeleton } = this;
    const points = this.placed.slice();
    this.reset();
    if (!classId || !skeleton || !points.some((p) => p.v > 0)) return;
    while (points.length < skeleton.names.length) points.push({ x: 0, y: 0, v: 0 });
    const id = this.ctx.newId();
    this.ctx.model.commit([
      {
        kind: 'create',
        shape: { id, type: 'keypoints', classId, geometry: { points }, attrs: {}, version: 0 },
      },
    ]);
    this.ctx.model.select([id]);
  }

  key(e: KeyInfo): boolean {
    if (this.placed.length === 0 && this.skeleton === null) return false;
    if (e.key === 'Escape') {
      this.reset();
      return true;
    }
    if (e.key === 'Enter') {
      this.finish();
      return true;
    }
    if (e.key.toLowerCase() === 'n') {
      this.place({ x: 0, y: 0, v: 0 });
      return true;
    }
    if (e.key === 'Backspace' && this.placed.length > 0) {
      this.placed.pop();
      this.ctx.hint(this.prompt());
      this.ctx.requestRender();
      return true;
    }
    return false;
  }

  cancel(): void {
    this.reset();
  }

  render(g: CanvasRenderingContext2D): void {
    const skeleton = this.skeleton;
    if (!skeleton || this.placed.length === 0) return;
    const vp = this.ctx.viewport;
    const color = (this.classId && this.ctx.classStyle(this.classId)?.color) || '#ffffff';
    g.save();
    g.strokeStyle = color;
    g.fillStyle = color;
    g.lineWidth = 1.5;
    for (const [a, b] of skeleton.edges) {
      const from = this.placed[a];
      const to = this.placed[b];
      if (!from || !to || from.v === 0 || to.v === 0) continue;
      const pa = vp.normToScreen(from);
      const pb = vp.normToScreen(to);
      g.beginPath();
      g.moveTo(pa.x, pa.y);
      g.lineTo(pb.x, pb.y);
      g.stroke();
    }
    this.placed.forEach((point, i) => {
      if (point.v === 0) return;
      const at = vp.normToScreen(point);
      g.beginPath();
      g.arc(at.x, at.y, 4, 0, Math.PI * 2);
      if (point.v === 2) g.fill();
      else g.stroke();
      g.fillText(String(i + 1), at.x + 7, at.y - 6);
    });
    g.restore();
  }

  cursor(): string {
    return 'crosshair';
  }

  private reset(): void {
    this.placed = [];
    this.classId = null;
    this.skeleton = null;
    this.ctx.hint(this.idleHint());
    this.ctx.requestRender();
  }
}
