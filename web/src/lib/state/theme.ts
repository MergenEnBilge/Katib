export type ThemePref = 'system' | 'dark' | 'light';
export type Theme = 'dark' | 'light';

export const THEME_KEY = 'katib.theme';

export function isThemePref(value: unknown): value is ThemePref {
  return value === 'system' || value === 'dark' || value === 'light';
}

/** Dark is the default. "system" follows the OS only when the OS asks for light. */
export function resolveTheme(pref: ThemePref, systemPrefersLight: boolean): Theme {
  if (pref === 'light') return 'light';
  if (pref === 'system' && systemPrefersLight) return 'light';
  return 'dark';
}
