import { AnnotationModel } from './model';
import { Renderer } from './renderer';
import { BoxTool } from './tools/box';
import { PolygonTool } from './tools/polygon';
import { SelectTool } from './tools/select';
import type { Tool, ToolContext } from './tools/tool';
import type { ClassStyle, Point, ToolEvent } from './types';
import { Viewport } from './viewport';

export type ToolName = 'select' | 'box' | 'polygon';

export interface EngineOptions {
  activeClassId(): string | null;
  needClass(): void;
  onHint(text: string): void;
  /** Fired when zoom or pan changes, so the UI can show the zoom level. */
  onView(): void;
  onCursor?(cursor: string): void;
}

/**
 * Owns the two canvases, the viewport and the active tool. It has no Svelte in it: the
 * workspace component creates it, feeds it data and forwards keyboard events.
 */
export class Engine {
  readonly viewport = new Viewport();
  readonly model = new AnnotationModel();
  classes = new Map<string, ClassStyle>();
  hideAll = false;
  opacity = 1;
  patternMode = false;
  crosshair = false;

  private renderer: Renderer;
  private tools: Record<ToolName, Tool>;
  private tool: Tool;
  private toolName: ToolName = 'select';
  private dirty = true;
  private imageDirty = true;
  private frame = 0;
  private pointers = new Map<number, Point>();
  private pinch: { distance: number; center: Point } | null = null;
  private panning: { last: Point } | null = null;
  private spaceHeld = false;
  private guide: Point | null = null;
  private observer: ResizeObserver;
  private disposers: (() => void)[] = [];
  private bitmapLoad = 0;

  constructor(
    private readonly host: HTMLElement,
    private readonly opts: EngineOptions,
  ) {
    const imageCanvas = document.createElement('canvas');
    const overlay = document.createElement('canvas');
    for (const c of [imageCanvas, overlay]) {
      c.style.position = 'absolute';
      c.style.inset = '0';
      host.appendChild(c);
    }
    overlay.style.touchAction = 'none';
    overlay.tabIndex = 0;
    this.renderer = new Renderer(imageCanvas, overlay);

    const context: ToolContext = {
      model: this.model,
      viewport: this.viewport,
      activeClassId: () => opts.activeClassId(),
      classStyle: (id) => this.classes.get(id),
      requestRender: () => this.requestRender(),
      hint: (text) => opts.onHint(text),
      needClass: () => opts.needClass(),
      newId: () => crypto.randomUUID(),
      accent: () => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
    };
    this.tools = {
      select: new SelectTool(context),
      box: new BoxTool(context),
      polygon: new PolygonTool(context),
    };
    this.tool = this.tools.select;

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(host);
    this.disposers.push(this.model.onView(() => this.requestRender()));
    this.listen(overlay, 'pointerdown', this.onPointerDown);
    this.listen(overlay, 'pointermove', this.onPointerMove);
    this.listen(overlay, 'pointerup', this.onPointerUp);
    this.listen(overlay, 'pointercancel', this.onPointerUp);
    this.listen(overlay, 'pointerleave', () => {
      this.guide = null;
      this.requestRender();
    });
    this.listen(overlay, 'wheel', this.onWheel, { passive: false });
    this.listen(overlay, 'contextmenu', (e) => e.preventDefault());
    this.overlay = overlay;
    this.resize();
  }

  private overlay: HTMLCanvasElement;

  private listen<K extends keyof HTMLElementEventMap>(
    target: HTMLElement,
    type: K,
    handler: (e: HTMLElementEventMap[K]) => void,
    options?: AddEventListenerOptions,
  ): void {
    const bound = handler.bind(this) as EventListener;
    target.addEventListener(type, bound, options);
    this.disposers.push(() => target.removeEventListener(type, bound));
  }

  get activeTool(): ToolName {
    return this.toolName;
  }

  setTool(name: ToolName): void {
    if (name === this.toolName) return;
    this.tool.cancel();
    this.toolName = name;
    this.tool = this.tools[name];
    this.tool.activate();
    this.updateCursor();
    this.requestRender();
  }

  /** Show an image. Shapes are unaffected. Fits the image to the view. */
  async setImage(url: string, width: number, height: number): Promise<void> {
    const token = ++this.bitmapLoad;
    this.viewport.setImage(width, height);
    this.viewport.fit();
    this.renderer.setBitmap(null);
    this.viewChanged();
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    try {
      await img.decode();
    } catch {
      return;
    }
    if (token !== this.bitmapLoad) return;
    this.renderer.setBitmap(img);
    this.imageDirty = true;
    this.requestRender();
  }

  clearImage(): void {
    this.bitmapLoad++;
    this.renderer.setBitmap(null);
    this.viewport.setImage(0, 0);
    this.imageDirty = true;
    this.requestRender();
  }

  fit(): void {
    this.viewport.fit();
    this.viewChanged();
  }

  zoomIn(): void {
    this.viewport.zoomStep(1);
    this.viewChanged();
  }

  zoomOut(): void {
    this.viewport.zoomStep(-1);
    this.viewChanged();
  }

  setClasses(classes: Map<string, ClassStyle>): void {
    this.classes = classes;
    this.requestRender();
  }

  requestRender(): void {
    this.dirty = true;
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.draw();
    });
  }

  keyDown(e: KeyboardEvent): boolean {
    if (e.code === 'Space' && !this.spaceHeld) {
      this.spaceHeld = true;
      this.updateCursor();
      return true;
    }
    return this.tool.key({ key: e.key, shift: e.shiftKey, ctrl: e.ctrlKey || e.metaKey });
  }

  keyUp(e: KeyboardEvent): void {
    if (e.code === 'Space') {
      this.spaceHeld = false;
      this.panning = null;
      this.updateCursor();
    }
  }

  dispose(): void {
    cancelAnimationFrame(this.frame);
    this.observer.disconnect();
    this.disposers.forEach((d) => d());
    this.host.replaceChildren();
  }

  private viewChanged(): void {
    this.opts.onView();
    this.imageDirty = true;
    this.requestRender();
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.host;
    if (w === 0 || h === 0) return;
    const hadView = this.viewport.viewW > 0;
    this.viewport.setView(w, h);
    this.renderer.resize(w, h, window.devicePixelRatio || 1);
    if (!hadView) this.viewport.fit();
    this.viewChanged();
  }

  private draw(): void {
    if (this.imageDirty) {
      this.renderer.drawImage(this.viewport);
      this.imageDirty = false;
    }
    if (!this.dirty) return;
    this.dirty = false;
    this.renderer.drawOverlay(this.viewport, {
      model: this.model,
      classes: this.classes,
      hideAll: this.hideAll,
      opacity: this.opacity,
      patternMode: this.patternMode,
      drawTool: (g) => this.tool.render(g),
      guide: this.crosshair && this.toolName !== 'select' ? this.guide : null,
    });
  }

  private eventFor(e: PointerEvent): ToolEvent {
    const rect = this.overlay.getBoundingClientRect();
    const screen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    return {
      screen,
      norm: this.viewport.screenToNorm(screen),
      shift: e.shiftKey,
      ctrl: e.ctrlKey || e.metaKey,
      button: e.button,
      pointerType: e.pointerType,
    };
  }

  private updateCursor(): void {
    const cursor = this.panning || this.spaceHeld ? 'grab' : this.tool.cursor();
    this.overlay.style.cursor = cursor;
    this.opts.onCursor?.(cursor);
  }

  private onPointerDown(e: PointerEvent): void {
    this.overlay.focus({ preventScroll: true });
    this.overlay.setPointerCapture(e.pointerId);
    const ev = this.eventFor(e);
    this.pointers.set(e.pointerId, ev.screen);

    if (this.pointers.size === 2) {
      this.tool.cancel();
      const [a, b] = [...this.pointers.values()] as [Point, Point];
      this.pinch = { distance: Math.hypot(a.x - b.x, a.y - b.y), center: midpoint(a, b) };
      return;
    }
    if (e.button === 1 || this.spaceHeld) {
      this.panning = { last: ev.screen };
      this.updateCursor();
      return;
    }
    this.tool.pointerDown(ev);
    this.updateCursor();
  }

  private onPointerMove(e: PointerEvent): void {
    const ev = this.eventFor(e);
    if (this.pointers.has(e.pointerId)) this.pointers.set(e.pointerId, ev.screen);

    if (this.pinch && this.pointers.size >= 2) {
      const [a, b] = [...this.pointers.values()] as [Point, Point];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      const center = midpoint(a, b);
      this.viewport.panBy(center.x - this.pinch.center.x, center.y - this.pinch.center.y);
      if (this.pinch.distance > 0) this.viewport.zoomBy(distance / this.pinch.distance, center);
      this.pinch = { distance, center };
      this.viewChanged();
      return;
    }
    if (this.panning) {
      this.viewport.panBy(ev.screen.x - this.panning.last.x, ev.screen.y - this.panning.last.y);
      this.panning.last = ev.screen;
      this.viewChanged();
      return;
    }
    this.guide = ev.screen;
    this.tool.pointerMove(ev);
    if (this.crosshair) this.requestRender();
    this.updateCursor();
  }

  private onPointerUp(e: PointerEvent): void {
    const ev = this.eventFor(e);
    this.pointers.delete(e.pointerId);
    if (this.overlay.hasPointerCapture(e.pointerId)) this.overlay.releasePointerCapture(e.pointerId);
    if (this.pinch) {
      if (this.pointers.size < 2) this.pinch = null;
      return;
    }
    if (this.panning) {
      this.panning = null;
      this.updateCursor();
      return;
    }
    this.tool.pointerUp(ev);
    this.updateCursor();
  }

  private onWheel(e: WheelEvent): void {
    e.preventDefault();
    const rect = this.overlay.getBoundingClientRect();
    const anchor = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    if (e.ctrlKey || e.metaKey) {
      this.viewport.zoomBy(Math.exp(-e.deltaY * 0.0015), anchor);
    } else {
      this.viewport.panBy(-e.deltaX, -e.deltaY);
    }
    this.viewChanged();
  }
}

function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
