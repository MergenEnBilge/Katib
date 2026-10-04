import { describe, expect, it } from 'vitest';
import type { Shape } from '../canvas/types';
import { same, segments, spanRange, trim } from './spans';

const TEXT = 'Katib runs on my laptop.';

function span(start: number, end: number, classId = 'c1'): Shape {
  return { id: `${start}-${end}`, type: 'span', classId, geometry: { start, end }, attrs: {}, version: 0 };
}

describe('spanRange', () => {
  it('reads the offsets', () => {
    expect(spanRange(span(0, 5))).toEqual({ start: 0, end: 5 });
  });

  it('treats a shape with no offsets as empty', () => {
    const odd: Shape = { id: 'x', type: 'span', classId: '', geometry: {}, attrs: {}, version: 0 };
    expect(spanRange(odd)).toEqual({ start: 0, end: 0 });
  });
});

describe('trim', () => {
  it('drops the space a mouse selection catches at the end', () => {
    expect(trim(TEXT, 0, 6)).toEqual({ start: 0, end: 5 });
  });

  it('drops space at the start', () => {
    expect(trim(TEXT, 5, 10)).toEqual({ start: 6, end: 10 });
  });

  it('refuses a selection that is only space', () => {
    expect(trim(TEXT, 5, 6)).toBeNull();
  });

  it('keeps the range inside the words, whichever way round it came', () => {
    expect(trim(TEXT, 10, 0)).toEqual({ start: 0, end: 10 });
    expect(trim(TEXT, 0, 9000)).toEqual({ start: 0, end: TEXT.length });
  });
});

describe('segments', () => {
  it('covers the whole document when there is nothing labelled', () => {
    expect(segments(TEXT.length, [])).toEqual([
      { start: 0, end: TEXT.length, spans: [], top: null },
    ]);
  });

  it('splits around one span', () => {
    const found = segments(TEXT.length, [span(0, 5)]);
    expect(found.map((s) => [s.start, s.end, s.spans.length])).toEqual([
      [0, 5, 1],
      [5, TEXT.length, 0],
    ]);
  });

  it('lists both spans where they overlap, the longer one first', () => {
    const phrase = span(0, 10, 'phrase');
    const word = span(6, 10, 'word');
    const found = segments(TEXT.length, [word, phrase]);
    expect(found.map((s) => [s.start, s.end])).toEqual([
      [0, 6],
      [6, 10],
      [10, TEXT.length],
    ]);
    expect(found[1]?.spans.map((s) => s.classId)).toEqual(['phrase', 'word']);
    expect(found[1]?.top?.classId).toBe('phrase');
  });

  it('leaves out a span that starts past the end of the words', () => {
    expect(segments(5, [span(10, 20)])).toEqual([{ start: 0, end: 5, spans: [], top: null }]);
  });

  it('clips a span that reaches past the end', () => {
    const found = segments(5, [span(3, 90)]);
    expect(found.map((s) => [s.start, s.end, s.spans.length])).toEqual([
      [0, 3, 0],
      [3, 5, 1],
    ]);
  });

  it('has nothing to draw for an empty document', () => {
    expect(segments(0, [])).toEqual([]);
  });
});

describe('same', () => {
  it('compares both ends', () => {
    expect(same({ start: 1, end: 2 }, { start: 1, end: 2 })).toBe(true);
    expect(same({ start: 1, end: 2 }, { start: 1, end: 3 })).toBe(false);
  });
});
