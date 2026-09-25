/**
 * Pseudo-localization: turns English into accented, longer text that is still readable.
 *
 * It exists to find problems before a real translation does. Text that stays plain English was
 * never put through `t()`. Text that is cut off or overlaps needs more room. `{name}` markers
 * are left alone so messages still fill in.
 */

const ACCENTS: Record<string, string> = {
  a: 'á',
  b: 'ƀ',
  c: 'ç',
  d: 'ð',
  e: 'é',
  f: 'ƒ',
  g: 'ĝ',
  h: 'ĥ',
  i: 'í',
  j: 'ĵ',
  k: 'ķ',
  l: 'ļ',
  m: 'ɱ',
  n: 'ñ',
  o: 'ó',
  p: 'þ',
  q: 'ǫ',
  r: 'ŕ',
  s: 'š',
  t: 'ţ',
  u: 'ú',
  v: 'ṽ',
  w: 'ŵ',
  x: 'ẋ',
  y: 'ý',
  z: 'ž',
};

export function pseudo(text: string): string {
  let out = '';
  let inMarker = false;
  for (const ch of text) {
    if (ch === '{') inMarker = true;
    const lower = ch.toLowerCase();
    const swapped = !inMarker && lower in ACCENTS ? (ACCENTS[lower] as string) : ch;
    out += !inMarker && ch !== lower ? swapped.toUpperCase() : swapped;
    if (ch === '}') inMarker = false;
  }
  // Translations are often a third longer, so pad to see what that does to the layout.
  const padding = '~'.repeat(Math.ceil(text.length * 0.3));
  return `[${out}${padding}]`;
}
