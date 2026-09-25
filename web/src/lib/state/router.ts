export type Route =
  | { name: 'projects' }
  | { name: 'workspace'; projectId: string }
  | { name: 'gallery'; projectId: string }
  | { name: 'inbox' }
  | { name: 'settings' }
  | { name: 'invite'; token: string }
  | { name: 'not-found' };

/** Map a URL path to a route. Trailing slashes are ignored. */
export function matchRoute(path: string): Route {
  const clean = path.replace(/\/+$/, '') || '/';
  if (clean === '/') return { name: 'projects' };
  if (clean === '/inbox') return { name: 'inbox' };
  if (clean === '/settings') return { name: 'settings' };
  const invite = /^\/invite\/([A-Za-z0-9_-]{16,})$/.exec(clean);
  if (invite?.[1]) return { name: 'invite', token: invite[1] };
  const gallery = /^\/p\/([0-9a-fA-F-]{36})\/gallery$/.exec(clean);
  if (gallery?.[1]) return { name: 'gallery', projectId: gallery[1] };
  const workspace = /^\/p\/([0-9a-fA-F-]{36})$/.exec(clean);
  if (workspace?.[1]) return { name: 'workspace', projectId: workspace[1] };
  return { name: 'not-found' };
}
