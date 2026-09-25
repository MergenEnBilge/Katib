import { api, ApiError, setUnauthorizedHandler } from '../api/client';
import type { Person } from '../api/types';
import { forgetCachedImages } from '../sync/offline';

export type Phase = 'loading' | 'error' | 'setup' | 'signed-out' | 'ready';

let phase = $state<Phase>('loading');
let mode = $state<'none' | 'local'>('none');
let user = $state<Person | null>(null);
let problem = $state('');
let needsCode = $state(false);

async function load(): Promise<void> {
  problem = '';
  try {
    const status = await api.auth.status();
    mode = status.mode;
    user = status.user ?? null;
    needsCode = status.needs_setup_code === true;
    if (status.needs_setup) phase = 'setup';
    else phase = user ? 'ready' : 'signed-out';
  } catch (err) {
    problem = err instanceof ApiError ? err.message : 'Could not reach the Katib server.';
    phase = 'error';
  }
}

setUnauthorizedHandler(() => {
  if (phase === 'ready' && mode === 'local') {
    user = null;
    phase = 'signed-out';
    void forgetCachedImages();
  }
});

/** Who is signed in. With auth off there is one implicit person and no sign-in screen. */
export const session = {
  get phase(): Phase {
    return phase;
  },
  get mode(): 'none' | 'local' {
    return mode;
  },
  get user(): Person | null {
    return user;
  },
  get problem(): string {
    return problem;
  },
  /** True when this server is open to the internet and the first account needs the code from its log. */
  get needsSetupCode(): boolean {
    return needsCode;
  },
  load,
  async signIn(email: string, password: string): Promise<void> {
    user = await api.auth.login(email, password);
    phase = 'ready';
  },
  async setup(email: string, name: string, password: string, code = ''): Promise<void> {
    user = await api.auth.setup(email, name, password, code);
    phase = 'ready';
  },
  async accept(token: string, email: string, name: string, password: string): Promise<void> {
    user = await api.auth.accept(token, email, name, password);
    phase = 'ready';
  },
  async signOut(): Promise<void> {
    await api.auth.logout().catch(() => undefined);
    await forgetCachedImages();
    user = null;
    phase = 'signed-out';
  },
};
