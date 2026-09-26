import type { AnnotationModel } from '../model';
import type { ClassStyle, ToolEvent } from '../types';
import type { Viewport } from '../viewport';
import type { Pixels } from '../wand';

/** A click handed to a segmentation model, as a fraction of the picture. */
export interface SegmentClick {
  x: number;
  y: number;
  /** False for "not this": a click that pushes the outline back off something it swallowed. */
  positive: boolean;
}

export interface ToolContext {
  model: AnnotationModel;
  viewport: Viewport;
  /** The class new shapes get, or null when none is chosen yet. */
  activeClassId(): string | null;
  classStyle(id: string): ClassStyle | undefined;
  requestRender(): void;
  /** Short instruction shown in the status chip, for example "Click to add points." */
  hint(text: string): void;
  /** Called when the person tries to draw without a class. */
  needClass(): void;
  newId(): string;
  /** Accent color for chrome such as marquees, read from the theme. */
  accent(): string;
  /** The picture's colors, shrunk to a working size, or null while it is still loading. */
  pixels(): Pixels | null;
  /**
   * Ask a model on the server to outline what the clicks point at. Absent when this Katib has no
   * such model, which is the usual case.
   */
  segment?(clicks: SegmentClick[]): Promise<[number, number][] | null>;
}

export interface KeyInfo {
  key: string;
  shift: boolean;
  ctrl: boolean;
}

/** Tools are small state machines driven by pointer events (ARCHITECTURE.md section 17). */
export interface Tool {
  readonly name: string;
  pointerDown(e: ToolEvent): void;
  pointerMove(e: ToolEvent): void;
  pointerUp(e: ToolEvent): void;
  /** Returns true when the key was used. */
  key(e: KeyInfo): boolean;
  /** Abort whatever is in progress. */
  cancel(): void;
  render(ctx: CanvasRenderingContext2D): void;
  cursor(): string;
  /** Called when the tool becomes active. */
  activate(): void;
}
