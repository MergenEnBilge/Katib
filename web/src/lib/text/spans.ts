/**
 * Working with labelled runs of characters in a document.
 *
 * A span is stored as `{ start, end }`, where `start` is the first character and `end` the one
 * just past the last, so `text.slice(start, end)` is what was labelled. Everything here is
 * plain arithmetic on those numbers, kept apart from the page so it can be tested on its own.
 */

import type { Shape } from '../canvas/types';

export interface Range {
  start: number;
  end: number;
}

/** One stretch of the document to draw, and the spans covering it, outermost first. */
export interface Segment extends Range {
  spans: Shape[];
  /** The span whose colour the stretch takes, or null where nothing covers it. */
  top: Shape | null;
}

export function spanRange(shape: Shape): Range {
  const geometry = shape.geometry as { start?: unknown; end?: unknown };
  const start = typeof geometry.start === 'number' ? geometry.start : 0;
  const end = typeof geometry.end === 'number' ? geometry.end : 0;
  return { start, end };
}

/**
 * Pull a range in from any space at its edges, and drop it if nothing but space is left.
 *
 * Selecting words with a mouse almost always catches the space after the last one, and a span
 * that includes it exports as a label with a trailing blank, which no training code wants.
 */
export function trim(text: string, start: number, end: number): Range | null {
  let from = Math.max(0, Math.min(start, text.length));
  let to = Math.max(0, Math.min(end, text.length));
  if (to < from) [from, to] = [to, from];
  while (from < to && /\s/.test(text.charAt(from))) from++;
  while (to > from && /\s/.test(text.charAt(to - 1))) to--;
  return to > from ? { start: from, end: to } : null;
}

/**
 * Split `text` into the stretches to draw, so that every stretch has the same spans over it.
 *
 * Spans may overlap, which happens as soon as someone labels a phrase and a word inside it. Each
 * segment therefore lists every span across it, longest first, so the page can colour by the
 * outermost and still show that there is more than one.
 */
export function segments(length: number, spans: Shape[]): Segment[] {
  const ranges = spans
    .map((shape) => ({ shape, ...spanRange(shape) }))
    .filter((s) => s.end > s.start && s.start < length)
    .map((s) => ({ ...s, end: Math.min(s.end, length) }));
  const edges = new Set<number>([0, length]);
  for (const span of ranges) {
    edges.add(span.start);
    edges.add(span.end);
  }
  const points = [...edges].filter((n) => n >= 0 && n <= length).sort((a, b) => a - b);
  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i] ?? 0;
    const end = points[i + 1] ?? 0;
    if (end <= start) continue;
    const over = ranges
      .filter((s) => s.start <= start && s.end >= end)
      .sort((a, b) => b.end - b.start - (a.end - a.start))
      .map((s) => s.shape);
    out.push({ start, end, spans: over, top: over[0] ?? null });
  }
  return out;
}

/** Whether two ranges cover exactly the same characters, so the same span is not made twice. */
export function same(a: Range, b: Range): boolean {
  return a.start === b.start && a.end === b.end;
}
