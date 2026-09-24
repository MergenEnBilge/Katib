/** "1 image", "2 images". Numbers use the reader's locale separators. */
export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count.toLocaleString()} ${count === 1 ? one : many}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Relative for the first week ("2 hours ago"), an absolute date after that. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  const diff = Math.max(0, now - then);
  if (diff < MINUTE) return 'just now';
  if (diff < HOUR) return plural(Math.floor(diff / MINUTE), 'minute') + ' ago';
  if (diff < DAY) return plural(Math.floor(diff / HOUR), 'hour') + ' ago';
  if (diff < 7 * DAY) return plural(Math.floor(diff / DAY), 'day') + ' ago';
  return new Date(then).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
