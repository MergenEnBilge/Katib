import { describe, expect, it } from 'vitest';
import { toPercent } from './splits';

describe('toPercent', () => {
  it('turns weights into percentages that add up to 100', () => {
    expect(toPercent({ train: 0.8, val: 0.1, test: 0.1 })).toEqual({ train: 80, val: 10, test: 10 });
    expect(toPercent({ train: 1, val: 1, test: 1 })).toEqual({ train: 34, val: 33, test: 33 });
  });

  it('copes with a split left out', () => {
    expect(toPercent({ train: 3, val: 1 })).toEqual({ train: 75, val: 25, test: 0 });
  });
});
