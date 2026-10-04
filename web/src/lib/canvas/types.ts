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

/** A rotated box. The angle turns it in pixel space, so `w` and `h` need the image size to draw. */
export interface ObbGeometry {
  cx: number;
  cy: number;
  w: number;
  h: number;
  /** Radians. */
  angle: number;
}

/** 0 is not labeled, 1 is hidden and 2 is visible. */
export type Visibility = 0 | 1 | 2;

export interface Landmark {
  x: number;
  y: number;
  v: Visibility;
}

export interface KeypointsGeometry {
  points: Landmark[];
}

/** A brush mask on a coarse grid stretched over the image. `rle` lists alternating run lengths. */
export interface MaskGeometry {
  rle: string;
  size: [number, number];
}

/** A label for the whole image. It has no geometry. */
export type TagGeometry = Record<string, never>;

/** Words about the whole image, such as a caption. It has no place on the picture. */
export interface TextGeometry {
  text: string;
}

/** A run of characters in a document: the first one, and the one just past the last. */
export interface SpanGeometry {
  start: number;
  end: number;
}

/** A link from one shape to another, by id. Both ends are spans on the same document. */
export interface RelationGeometry {
  from_id: string;
  to_id: string;
}

export type Geometry =
  | BoxGeometry
  | PolygonGeometry
  | ObbGeometry
  | KeypointsGeometry
  | MaskGeometry
  | TagGeometry
  | TextGeometry
  | SpanGeometry
  | RelationGeometry;

export type ShapeType =
  | 'box'
  | 'polygon'
  | 'obb'
  | 'keypoints'
  | 'mask'
  | 'tag'
  | 'text'
  // A run of characters in a text document, which has no place on a picture.
  | 'span'
  // A link between two spans, which is drawn between them rather than anywhere of its own.
  | 'relation';

/** Everything that can change on a shape after it is created. */
export interface ShapePatch {
  classId?: string;
  geometry?: Geometry;
  attrs?: Record<string, unknown>;
}

/** A shape in normalized coordinates (0 to 1, origin top-left). */
export interface Shape {
  id: string;
  type: ShapeType;
  classId: string;
  geometry: Geometry;
  attrs: Record<string, unknown>;
  version: number;
  source?: string;
  confidence?: number | null;
}

/** Landmark names in drawing order and the lines between them, by position. */
export interface SkeletonStyle {
  names: string[];
  edges: [number, number][];
}

export interface ClassStyle {
  name: string;
  color: string;
  hidden: boolean;
  locked: boolean;
  dash: number[];
  skeleton?: SkeletonStyle | null;
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

export function isBox(g: Geometry): g is BoxGeometry {
  return 'x' in g && 'w' in g && 'h' in g;
}

export function isPolygon(g: Geometry): g is PolygonGeometry {
  return 'points' in g && Array.isArray(g.points[0]);
}

export function isObb(g: Geometry): g is ObbGeometry {
  return 'angle' in g;
}

export function isKeypoints(g: Geometry): g is KeypointsGeometry {
  return 'points' in g && !Array.isArray(g.points[0]);
}

export function isMask(g: Geometry): g is MaskGeometry {
  return 'rle' in g;
}

/**
 * A shape that labels some part of the item rather than the whole of it. A tag or a caption is
 * about the item as a whole; a box, an outline or a span is about one part.
 */
export function isPartLabel(shape: Shape): boolean {
  return shape.type !== 'tag' && shape.type !== 'text';
}

/** The two ends of a link, or null for any other shape. */
export function linkEnds(shape: Shape): RelationGeometry | null {
  if (shape.type !== 'relation') return null;
  const g = shape.geometry as Partial<RelationGeometry>;
  return typeof g.from_id === 'string' && typeof g.to_id === 'string'
    ? { from_id: g.from_id, to_id: g.to_id }
    : null;
}

/**
 * A shape the canvas draws and can pick up. Whole-item shapes are listed beside the picture
 * instead, and a span lives in the words of a document, so the canvas leaves all of them alone.
 */
export function isDrawn(shape: Shape): boolean {
  return isPartLabel(shape) && shape.type !== 'span' && shape.type !== 'relation';
}
