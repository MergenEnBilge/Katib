import { describe, expect, it } from 'vitest';
import { resolveShortcut, type KeyPress } from './keys';

function press(key: string, extra: Partial<KeyPress> = {}): KeyPress {
  return { key, ctrl: false, shift: false, alt: false, ...extra };
}

describe('resolveShortcut', () => {
  it('maps tool keys in either case', () => {
    expect(resolveShortcut(press('v'))).toBe('tool:select');
    expect(resolveShortcut(press('B'))).toBe('tool:box');
    expect(resolveShortcut(press('p'))).toBe('tool:polygon');
  });

  it('maps digits to classes', () => {
    expect(resolveShortcut(press('1'))).toBe('class:1');
    expect(resolveShortcut(press('9'))).toBe('class:9');
    expect(resolveShortcut(press('0'))).toBe('zoom-fit');
  });

  it('separates undo and redo', () => {
    expect(resolveShortcut(press('z', { ctrl: true }))).toBe('undo');
    expect(resolveShortcut(press('Z', { ctrl: true, shift: true }))).toBe('redo');
    expect(resolveShortcut(press('y', { ctrl: true }))).toBe('redo');
  });

  it('navigates and finishes images', () => {
    expect(resolveShortcut(press('a'))).toBe('prev');
    expect(resolveShortcut(press('d'))).toBe('next');
    expect(resolveShortcut(press('Enter', { shift: true }))).toBe('done');
    expect(resolveShortcut(press('Enter'))).toBeNull();
  });

  it('does not steal Ctrl+D or unknown chords', () => {
    expect(resolveShortcut(press('d', { ctrl: true }))).toBeNull();
    expect(resolveShortcut(press('a', { alt: true }))).toBeNull();
    expect(resolveShortcut(press('q'))).toBeNull();
  });

  it('opens the class picker with C or slash, and help with question mark', () => {
    expect(resolveShortcut(press('c'))).toBe('class-picker');
    expect(resolveShortcut(press('/'))).toBe('class-picker');
    expect(resolveShortcut(press('?', { shift: true }))).toBe('help');
  });
});
