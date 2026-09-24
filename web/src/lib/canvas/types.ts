/** Shared types for the canvas engine. The engine imports nothing from Svelte. */

export interface Point {
  x: number;
  y: number;
}

export interface BoxGeometry {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PolygonGeometry {
  points: [number, number][];
}

export type ShapeType = 'box' | 'polygon';

/** Everything that can change on a shape after it is created. */
export interface ShapePatch {
  classId?: string;
  geometry?: BoxGeometry | PolygonGeometry;
  attrs?: Record<string, unknown>;
}

/** A shape in normalized coordinates (0 to 1, origin top-left). */
export interface Shape {
  id: string;
  type: ShapeType;
  classId: string;
  geometry: BoxGeometry | PolygonGeometry;
  attrs: Record<string, unknown>;
  version: number;
  source?: string;
  confidence?: number | null;
}

export interface ClassStyle {
  name: string;
  color: string;
  hidden: boolean;
  locked: boolean;
  dash: number[];
}

export interface ToolEvent {
  /** Position in CSS pixels relative to the canvas. */
  screen: Point;
  /** Position in normalized image coordinates, not clamped. */
  norm: Point;
  shift: boolean;
  ctrl: boolean;
  button: number;
  pointerType: string;
}

export function isBox(g: Shape['geometry']): g is BoxGeometry {
  return 'w' in g;
}

export function isPolygon(g: Shape['geometry']): g is PolygonGeometry {
  return 'points' in g;
}
