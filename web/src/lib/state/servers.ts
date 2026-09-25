/** Other Katib servers this browser knows about, kept in the browser and nowhere else. */

export interface SavedServer {
  name: string;
  url: string;
}

const KEY = 'katib.servers';

export function loadServers(): SavedServer[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '[]') as unknown;
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (s): s is SavedServer =>
        typeof s === 'object' && s !== null && typeof s.name === 'string' && typeof s.url === 'string',
    );
  } catch {
    return [];
  }
}

export function saveServers(servers: SavedServer[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(servers));
  } catch {
    // Private browsing can refuse storage. The list then lasts until the page closes.
  }
}

/** Turn what someone typed into a web address, or return null when it cannot be one. */
export function cleanServerUrl(input: string): string | null {
  const text = input.trim();
  if (!text) return null;
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : `http://${text}`;
  try {
    const url = new URL(withScheme);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return url.origin;
  } catch {
    return null;
  }
}
