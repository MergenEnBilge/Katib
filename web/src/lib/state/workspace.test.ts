import { describe, expect, it } from 'vitest';
import { imageFromUrl } from './workspace.svelte';

const ID = '0195c0de-1234-7abc-8def-0123456789ab';

describe('imageFromUrl', () => {
  it('reads the image id from the query string', () => {
    expect(imageFromUrl(`?image=${ID}`)).toBe(ID);
    expect(imageFromUrl(`?x=1&image=${ID}&y=2`)).toBe(ID);
  });
  it('ignores missing or malformed values', () => {
    expect(imageFromUrl('')).toBeNull();
    expect(imageFromUrl('?image=abc')).toBeNull();
  });
});
