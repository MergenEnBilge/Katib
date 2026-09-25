import en, { type MessageKey, type Messages } from './en';
import { pseudo } from './pseudo';

export type { MessageKey };

export interface Locale {
  /** A BCP 47 tag such as "en" or "ar". */
  code: string;
  /** The language's name in that language, for the picker. */
  name: string;
  dir: 'ltr' | 'rtl';
  /** Hidden locales are for testing. They are reachable with `?lang=` but not listed. */
  hidden?: boolean;
  /** Missing keys fall back to English. */
  messages: Partial<Messages>;
}

function pseudoMessages(): Messages {
  const out: Partial<Messages> = {};
  for (const key of Object.keys(en) as MessageKey[]) out[key] = pseudo(en[key]);
  return out as Messages;
}

/**
 * To add a language, copy `en.ts`, translate the values, and add an entry here. Nothing else
 * needs to change: the picker, text direction and number formats follow from the entry.
 */
export const LOCALES: Locale[] = [
  { code: 'en', name: 'English', dir: 'ltr', messages: en },
  { code: 'qps-ploc', name: 'Pseudo (accented)', dir: 'ltr', hidden: true, messages: pseudoMessages() },
  { code: 'qps-plocm', name: 'Pseudo (mirrored)', dir: 'rtl', hidden: true, messages: pseudoMessages() },
];

const STORAGE_KEY = 'katib.locale';

let code = $state('en');

function find(wanted: string | null | undefined): Locale | undefined {
  if (!wanted) return undefined;
  const lower = wanted.toLowerCase();
  return (
    LOCALES.find((l) => l.code.toLowerCase() === lower) ??
    LOCALES.find((l) => l.code.toLowerCase() === lower.split('-')[0])
  );
}

const current = (): Locale => find(code) ?? (LOCALES[0] as Locale);

function apply(locale: Locale): void {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = locale.code;
  document.documentElement.dir = locale.dir;
}

function remember(value: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Storage can be blocked. The choice then lasts until the page closes.
  }
}

function recall(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Fill `{name}` markers. A marker with no value is left as it is, so a gap is easy to spot. */
function fill(template: string, params: Record<string, string | number> | undefined): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (marker, name: string) =>
    name in params ? String(params[name]) : marker,
  );
}

/** Translate a message. Missing keys fall back to English. */
export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const locale = current();
  return fill(locale.messages[key] ?? en[key], params);
}

/** Translate a message that depends on a count. Uses `key.one`, `key.other` and so on. */
export function tp(base: string, count: number, params: Record<string, string | number> = {}): string {
  const category = new Intl.PluralRules(current().code).select(count);
  const locale = current();
  const catalog = locale.messages as Record<string, string | undefined>;
  const fallback = en as Record<string, string | undefined>;
  const template =
    catalog[`${base}.${category}`] ??
    catalog[`${base}.other`] ??
    fallback[`${base}.${category}`] ??
    fallback[`${base}.other`] ??
    base;
  return fill(template, { count: count.toLocaleString(current().code), ...params });
}

export const i18n = {
  get locale(): string {
    return current().code;
  },
  get dir(): 'ltr' | 'rtl' {
    return current().dir;
  },
  /** Languages people can choose from. */
  get choices(): Locale[] {
    return LOCALES.filter((l) => !l.hidden);
  },
  setLocale(next: string): void {
    const locale = find(next);
    if (!locale) return;
    code = locale.code;
    apply(locale);
    remember(locale.code);
  },
  /**
   * Choose the starting language: `?lang=` in the address, then the saved choice, then the
   * browser's language, then English. Call once when the app starts.
   */
  init(search = typeof location === 'undefined' ? '' : location.search, languages: readonly string[] = []): void {
    // Read once at start, so it does not need to be reactive.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const fromAddress = new URLSearchParams(search).get('lang');
    const saved = recall();
    const locale =
      find(fromAddress) ??
      find(saved) ??
      languages.map(find).find((l): l is Locale => !!l && !l.hidden) ??
      (LOCALES[0] as Locale);
    code = locale.code;
    apply(locale);
    if (fromAddress && find(fromAddress)) remember(locale.code);
  },
};
