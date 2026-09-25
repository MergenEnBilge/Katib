import { describe, expect, it } from 'vitest';
import { dismiss, parseTips, shouldShow, TIPS } from './tips';

describe('tips', () => {
  it('starts with nothing seen', () => {
    expect(parseTips(null)).toEqual({ seen: [], off: false });
  });

  it('shows a tip once', () => {
    const fresh = parseTips(null);
    expect(shouldShow(fresh, 'tool:box')).toBe(true);
    const after = dismiss(fresh, 'tool:box');
    expect(shouldShow(after, 'tool:box')).toBe(false);
    expect(shouldShow(after, 'tool:polygon')).toBe(true);
    expect(dismiss(after, 'tool:box')).toBe(after);
  });

  it('shows nothing when tips are off or the tip does not exist', () => {
    expect(shouldShow({ seen: [], off: true }, 'tool:box')).toBe(false);
    expect(shouldShow(parseTips(null), 'tool:made-up')).toBe(false);
  });

  it('ignores junk in storage', () => {
    expect(parseTips('nope')).toEqual({ seen: [], off: false });
    expect(parseTips('{"seen":["tool:box","gone",4],"off":"yes"}')).toEqual({
      seen: ['tool:box'],
      off: false,
    });
  });

  it('has a title and a body for every tip, and keys that are not empty', () => {
    for (const [id, tip] of Object.entries(TIPS)) {
      expect(tip.title, id).not.toBe('');
      expect(tip.body, id).not.toBe('');
      for (const k of tip.keys ?? []) expect(Boolean(k.keys && k.does), id).toBe(true);
    }
  });
});
