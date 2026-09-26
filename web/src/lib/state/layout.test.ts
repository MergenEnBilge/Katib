import { describe, expect, it } from 'vitest';
import { OPEN, parseLayout } from './layout';

describe('parseLayout', () => {
  it('starts with every panel open', () => {
    expect(parseLayout(null)).toEqual(OPEN);
  });

  it('reads what was folded away', () => {
    const raw = '{"sidebar":true,"rail":false,"panel":true,"tab":"details"}';
    expect(parseLayout(raw)).toEqual({ sidebar: true, rail: false, panel: true, tab: 'details' });
  });

  it('ignores junk in storage', () => {
    expect(parseLayout('nope')).toEqual(OPEN);
    expect(parseLayout('{"sidebar":"yes","tab":"made-up"}')).toEqual(OPEN);
    expect(parseLayout('[]')).toEqual(OPEN);
  });
});
