export type Route =
  | { name: 'projects' }
  | { name: 'workspace'; projectId: string }
  | { name: 'not-found' };

/** Map a URL path to a route. Trailing slashes are ignored. */
export function matchRoute(path: string): Route {
  const clean = path.replace(/\/+$/, '') || '/';
  if (clean === '/') return { name: 'projects' };
  const workspace = /^\/p\/([0-9a-fA-F-]{36})$/.exec(clean);
  if (workspace?.[1]) return { name: 'workspace', projectId: workspace[1] };
  return { name: 'not-found' };
}
