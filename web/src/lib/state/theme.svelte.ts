import { isThemePref, resolveTheme, THEME_KEY, type Theme, type ThemePref } from './theme';

const query = window.matchMedia('(prefers-color-scheme: light)');

function readPref(): ThemePref {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (isThemePref(stored)) return stored;
  } catch {
    // Storage can be blocked. Fall back to following the system.
  }
  return 'system';
}

function writePref(pref: ThemePref): void {
  try {
    localStorage.setItem(THEME_KEY, pref);
  } catch {
    // The choice still applies for this session.
  }
}

let pref = $state<ThemePref>(readPref());
let systemLight = $state(query.matches);
query.addEventListener('change', (event) => (systemLight = event.matches));

export const theme = {
  get current(): Theme {
    return resolveTheme(pref, systemLight);
  },
  toggle(): void {
    pref = theme.current === 'dark' ? 'light' : 'dark';
    writePref(pref);
  },
};

export function applyTheme(): void {
  document.documentElement.dataset.theme = theme.current;
}
