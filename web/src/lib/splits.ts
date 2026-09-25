import type { SplitName } from './api/types';

export const SPLIT_NAMES: SplitName[] = ['train', 'val', 'test'];

export const SPLIT_LABELS: Record<SplitName | 'none', string> = {
  train: 'Train',
  val: 'Validation',
  test: 'Test',
  none: 'No split',
};

export const KIND_LABELS: Record<string, string> = {
  detect: 'Object detection',
  segment: 'Segmentation',
  obb: 'Rotated boxes',
  keypoints: 'Poses and keypoints',
  tags: 'Image tags',
  text: 'Text',
};

/** Ratios as whole percentages that add up to 100, for showing next to the number boxes. */
export function toPercent(ratios: Record<string, number>): Record<SplitName, number> {
  const total = SPLIT_NAMES.reduce((sum, n) => sum + (ratios[n] ?? 0), 0) || 1;
  const out = { train: 0, val: 0, test: 0 };
  let used = 0;
  for (const name of SPLIT_NAMES.slice(1)) {
    out[name] = Math.round(((ratios[name] ?? 0) / total) * 100);
    used += out[name];
  }
  out.train = 100 - used;
  return out;
}
