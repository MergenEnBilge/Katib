import { describe, expect, it } from 'vitest';
import { isThemePref, resolveTheme } from './theme';

describe('resolveTheme', () => {
  it('defaults to dark', () => {
    expect(resolveTheme('system', false)).toBe('dark');
  });
  it('follows a light system preference', () => {
    expect(resolveTheme('system', true)).toBe('light');
  });
  it('lets an explicit choice win over the system', () => {
    expect(resolveTheme('dark', true)).toBe('dark');
    expect(resolveTheme('light', false)).toBe('light');
  });
});

describe('isThemePref', () => {
  it('rejects unknown stored values', () => {
    expect(isThemePref('blue')).toBe(false);
    expect(isThemePref(null)).toBe(false);
    expect(isThemePref('light')).toBe(true);
  });
});
