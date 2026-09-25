import { i18n, t } from './i18n/index.svelte';

/** "1 image", "2 images". Numbers use the reader's locale separators. */
export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count.toLocaleString()} ${count === 1 ? one : many}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Relative for the first week ("2 hours ago"), an absolute date after that. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return t('time.never');
  const then = new Date(iso).getTime();
  const diff = Math.max(0, now - then);
  if (diff < MINUTE) return t('time.justNow');
  const words = new Intl.RelativeTimeFormat(i18n.locale, { numeric: 'always' });
  if (diff < HOUR) return words.format(-Math.floor(diff / MINUTE), 'minute');
  if (diff < DAY) return words.format(-Math.floor(diff / HOUR), 'hour');
  if (diff < 7 * DAY) return words.format(-Math.floor(diff / DAY), 'day');
  return new Date(then).toLocaleDateString(i18n.locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** A file size in the largest unit that keeps the number small, such as "3.4 MB". */
export function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 || value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}
