import { boundsOf, obbCorners } from './geometry';
import { handlesOf } from './hit';
import { maskCells, maskToCanvas } from './mask';
import type { AnnotationModel } from './model';
import type { ClassStyle, Point, Shape } from './types';
import { isBox, isDrawn, isKeypoints, isMask, isObb } from './types';
import type { Viewport } from './viewport';

export interface RenderState {
  model: AnnotationModel;
  classes: Map<string, ClassStyle>;
  hideAll: boolean;
  /** 0 to 1 multiplier on fills. */
  opacity: number;
  /** Add a dash style per class so classes differ without color. */
  patternMode: boolean;
  /** Draws tool feedback on top of everything else. */
  drawTool: (g: CanvasRenderingContext2D) => void;
  guide: Point | null;
}

const LABEL_TEXT = '#0b0e0c';
const HANDLE = 9;

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Draws the image on one canvas and shapes on another so shapes redraw without the image. */
export class Renderer {
  private imageCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;
  private bitmap: CanvasImageSource | null = null;
  /** Small tinted canvases for masks, kept so a redraw does not rebuild them. */
  private maskArt = new Map<string, HTMLCanvasElement>();
  private dpr = 1;
  private width = 0;
  private height = 0;

  constructor(
    private readonly imageCanvas: HTMLCanvasElement,
    private readonly overlayCanvas: HTMLCanvasElement,
  ) {
    const image = imageCanvas.getContext('2d');
    const overlay = overlayCanvas.getContext('2d');
    if (!image || !overlay) throw new Error('This browser cannot draw on a canvas.');
    this.imageCtx = image;
    this.overlayCtx = overlay;
  }

  setBitmap(bitmap: CanvasImageSource | null): void {
    this.bitmap = bitmap;
  }

  resize(width: number, height: number, dpr: number): void {
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    for (const canvas of [this.imageCanvas, this.overlayCanvas]) {
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }
  }

  drawImage(vp: Viewport): void {
    const g = this.imageCtx;
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    g.clearRect(0, 0, this.width, this.height);
    if (!this.bitmap) return;
    g.imageSmoothingEnabled = vp.scale < 4;
    g.drawImage(this.bitmap, vp.offsetX, vp.offsetY, vp.imageW * vp.scale, vp.imageH * vp.scale);
  }

  drawOverlay(vp: Viewport, state: RenderState): void {
    const g = this.overlayCtx;
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    g.clearRect(0, 0, this.width, this.height);
    const bg = cssVar('--bg', '#0b0e0c');
    const accent = cssVar('--accent', '#2fa366');

    if (!state.hideAll) {
      const shapes = state.model.visible().filter(isDrawn);
      const selected = shapes.filter((s) => state.model.selection.has(s.id));
      const rest = shapes.filter((s) => !state.model.selection.has(s.id));
      for (const shape of [...rest, ...selected]) {
        const style = state.classes.get(shape.classId);
        if (!style || style.hidden) continue;
        this.drawShape(g, vp, shape, style, state, state.model.selection.has(shape.id));
      }
      if (selected.length === 1) {
        const only = selected[0] as Shape;
        const style = state.classes.get(only.classId);
        if (style && !style.locked) this.drawHandles(g, vp, only, style.color, bg);
      }
    }

    if (state.guide) {
      g.save();
      g.strokeStyle = accent;
      g.globalAlpha = 0.5;
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(state.guide.x, 0);
      g.lineTo(state.guide.x, this.height);
      g.moveTo(0, state.guide.y);
      g.lineTo(this.width, state.guide.y);
      g.stroke();
      g.restore();
    }
    state.drawTool(g);
  }

  private path(g: CanvasRenderingContext2D, vp: Viewport, shape: Shape): void {
    const geo = shape.geometry;
    g.beginPath();
    if (isBox(geo)) {
      const a = vp.normToScreen({ x: geo.x, y: geo.y });
      const b = vp.normToScreen({ x: geo.x + geo.w, y: geo.y + geo.h });
      g.rect(a.x, a.y, b.x - a.x, b.y - a.y);
      return;
    }
    const ring: [number, number][] = isObb(geo)
      ? obbCorners(geo, vp.imageW, vp.imageH)
      : 'points' in geo && Array.isArray(geo.points[0])
        ? (geo.points as [number, number][])
        : [];
    ring.forEach(([x, y], i) => {
      const p = vp.normToScreen({ x, y });
      if (i === 0) g.moveTo(p.x, p.y);
      else g.lineTo(p.x, p.y);
    });
    g.closePath();
  }

  private drawMask(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    style: ClassStyle,
    state: RenderState,
    selected: boolean,
  ): void {
    const geo = shape.geometry;
    if (!isMask(geo)) return;
    const cells = maskCells(geo);
    if (!cells) return;
    const key = `${style.color}:${geo.size.join('x')}:${geo.rle}`;
    let art = this.maskArt.get(key);
    if (!art) {
      art = maskToCanvas(cells, geo.size[0], geo.size[1], style.color);
      if (this.maskArt.size >= 24) this.maskArt.delete(this.maskArt.keys().next().value as string);
      this.maskArt.set(key, art);
    }
    const a = vp.normToScreen({ x: 0, y: 0 });
    const b = vp.normToScreen({ x: 1, y: 1 });
    g.save();
    g.globalAlpha = (selected ? 0.6 : 0.4) * state.opacity;
    g.imageSmoothingEnabled = false;
    g.drawImage(art, a.x, a.y, b.x - a.x, b.y - a.y);
    g.restore();
  }

  private drawKeypoints(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    style: ClassStyle,
    selected: boolean,
  ): void {
    const geo = shape.geometry;
    if (!isKeypoints(geo)) return;
    const screen = geo.points.map((p) => vp.normToScreen(p));
    g.save();
    g.strokeStyle = style.color;
    g.lineWidth = selected ? 2 : 1.5;
    for (const [a, b] of style.skeleton?.edges ?? []) {
      const from = geo.points[a];
      const to = geo.points[b];
      if (!from || !to || from.v === 0 || to.v === 0) continue;
      const pa = screen[a] as Point;
      const pb = screen[b] as Point;
      g.beginPath();
      g.moveTo(pa.x, pa.y);
      g.lineTo(pb.x, pb.y);
      g.stroke();
    }
    geo.points.forEach((point, i) => {
      if (point.v === 0) return;
      const at = screen[i] as Point;
      g.beginPath();
      g.arc(at.x, at.y, selected ? 5 : 4, 0, Math.PI * 2);
      if (point.v === 2) {
        g.fillStyle = style.color;
        g.fill();
      } else {
        g.fillStyle = cssVar('--bg', '#0b0e0c');
        g.fill();
        g.stroke();
      }
    });
    g.restore();
  }

  private drawShape(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    style: ClassStyle,
    state: RenderState,
    selected: boolean,
  ): void {
    if (isMask(shape.geometry)) {
      this.drawMask(g, vp, shape, style, state, selected);
      this.drawLabel(g, vp, shape, style);
      return;
    }
    if (isKeypoints(shape.geometry)) {
      this.drawKeypoints(g, vp, shape, style, selected);
      this.drawLabel(g, vp, shape, style);
      return;
    }
    g.save();
    this.path(g, vp, shape);
    g.fillStyle = style.color;
    g.globalAlpha = (selected ? 0.22 : 0.08) * state.opacity;
    g.fill();
    g.globalAlpha = 1;
    g.strokeStyle = style.color;
    g.lineWidth = selected ? 2 : 1.5;
    const dash = shape.source === 'model' ? [6, 4] : state.patternMode ? style.dash : [];
    g.setLineDash(dash);
    g.stroke();
    g.restore();
    if (style.locked) this.drawLock(g, vp, shape, style.color);
    this.drawLabel(g, vp, shape, style);
  }

  private drawLabel(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    style: ClassStyle,
  ): void {
    const bounds = boundsOf(shape, vp.imageW, vp.imageH);
    const anchor = vp.normToScreen({ x: bounds.x, y: bounds.y });
    const text =
      shape.source === 'model' && shape.confidence != null
        ? `${style.name} ${shape.confidence.toFixed(2)}`
        : style.name;
    g.save();
    g.font = `500 11px ${cssVar('--font-ui', 'sans-serif')}`;
    const width = g.measureText(text).width + 10;
    const height = 16;
    const x = anchor.x;
    const y = Math.max(0, anchor.y - height);
    g.fillStyle = style.color;
    g.beginPath();
    g.roundRect(x, y, width, height, 3);
    g.fill();
    g.fillStyle = LABEL_TEXT;
    g.textBaseline = 'middle';
    g.fillText(text, x + 5, y + height / 2 + 0.5);
    g.restore();
  }

  private drawLock(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    color: string,
  ): void {
    const bounds = boundsOf(shape, vp.imageW, vp.imageH);
    const p = vp.normToScreen({ x: bounds.x + bounds.w, y: bounds.y });
    g.save();
    g.fillStyle = color;
    g.fillRect(p.x - 12, p.y + 2, 10, 8);
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    g.beginPath();
    g.arc(p.x - 7, p.y + 2, 3, Math.PI, 0);
    g.stroke();
    g.restore();
  }

  private drawHandles(
    g: CanvasRenderingContext2D,
    vp: Viewport,
    shape: Shape,
    color: string,
    fill: string,
  ): void {
    g.save();
    g.fillStyle = fill;
    g.strokeStyle = color;
    g.lineWidth = 1.5;
    for (const h of handlesOf(shape, vp)) {
      g.beginPath();
      if (h.id === 'rot') g.arc(h.screen.x, h.screen.y, HANDLE / 2 + 1, 0, Math.PI * 2);
      else g.roundRect(h.screen.x - HANDLE / 2, h.screen.y - HANDLE / 2, HANDLE, HANDLE, 2);
      g.fill();
      g.stroke();
    }
    g.restore();
  }
}
