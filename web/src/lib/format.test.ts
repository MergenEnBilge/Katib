import { describe, expect, it } from 'vitest';
import { formatBytes, plural, relativeTime } from './format';

describe('plural', () => {
  it('uses the singular for one', () => {
    expect(plural(1, 'image')).toBe('1 image');
    expect(plural(2, 'image')).toBe('2 images');
    expect(plural(0, 'image')).toBe('0 images');
  });
  it('accepts an irregular plural', () => {
    expect(plural(2, 'box', 'boxes')).toBe('2 boxes');
  });
});

describe('relativeTime', () => {
  const now = Date.parse('2026-05-10T12:00:00Z');
  it('says just now for the last minute', () => {
    expect(relativeTime('2026-05-10T11:59:40Z', now)).toBe('just now');
  });
  it('counts minutes, hours and days', () => {
    expect(relativeTime('2026-05-10T11:55:00Z', now)).toBe('5 minutes ago');
    expect(relativeTime('2026-05-10T10:00:00Z', now)).toBe('2 hours ago');
    expect(relativeTime('2026-05-08T12:00:00Z', now)).toBe('2 days ago');
  });
  it('switches to a date after a week', () => {
    expect(relativeTime('2026-04-01T12:00:00Z', now)).toMatch(/2026/);
  });
  it('handles missing values', () => {
    expect(relativeTime(null, now)).toBe('never');
  });
});

describe('formatBytes', () => {
  it('picks a unit that keeps the number short', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1536)).toBe('1.5 KB');
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB');
    expect(formatBytes(250 * 1024 * 1024 * 1024)).toBe('250 GB');
  });
});
