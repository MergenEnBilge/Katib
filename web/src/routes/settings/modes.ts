/**
 * The three ways people actually run Katib, as one choice.
 *
 * Each one sets several settings at once. Those settings stay visible and editable underneath, so
 * anybody who wants a different arrangement still has it; this only saves you from having to know
 * which things to change together.
 */

export interface Mode {
  id: 'alone' | 'team' | 'internet';
  label: string;
  hint: string;
  values: Record<string, unknown>;
}

export const MODES: readonly Mode[] = [
  {
    id: 'alone',
    label: 'Just me',
    hint: 'Katib answers on this computer only. No sign-in, nothing to set up.',
    values: { 'auth.mode': 'none', 'server.host': '127.0.0.1', 'server.behind_proxy': false },
  },
  {
    id: 'team',
    label: 'My team, on this network',
    hint: 'People on the same wifi sign in and share projects. Phones can join too.',
    values: { 'auth.mode': 'local', 'server.host': '0.0.0.0', 'server.behind_proxy': false },
  },
  {
    id: 'internet',
    label: 'Over the internet',
    hint: 'For a server behind a proxy that handles HTTPS, such as the Caddy in our compose file.',
    values: { 'auth.mode': 'local', 'server.host': '0.0.0.0', 'server.behind_proxy': true },
  },
];

/** Which mode the current settings match, or null when someone has arranged their own. */
export function activeMode(current: (key: string) => unknown): Mode['id'] | null {
  const match = MODES.find((mode) =>
    Object.entries(mode.values).every(([key, value]) => current(key) === value),
  );
  return match ? match.id : null;
}
