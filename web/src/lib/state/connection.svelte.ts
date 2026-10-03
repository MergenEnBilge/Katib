/**
 * Whether the Katib server is answering. A request that cannot reach it marks the connection
 * lost; from then on a light health check runs every few seconds until it answers again, so the
 * banner clears by itself when the server comes back -- after a restart, say -- and the rest of
 * the app is told to fetch what it shows again.
 */

const CHECK_MS = 3000;

let lost = $state(false);
let checking = $state(false);
let timer: ReturnType<typeof setTimeout> | undefined;

async function answers(): Promise<boolean> {
  try {
    const response = await fetch('/api/v1/health', { cache: 'no-store' });
    return response.ok;
  } catch {
    return false;
  }
}

async function check(): Promise<void> {
  clearTimeout(timer);
  checking = true;
  const back = await answers();
  checking = false;
  if (back) {
    connection.reachable();
    return;
  }
  timer = setTimeout(() => void check(), CHECK_MS);
}

export const connection = {
  get lost(): boolean {
    return lost;
  },
  get checking(): boolean {
    return checking;
  },
  /** A request could not reach the server at all. */
  unreachable(): void {
    if (lost) return;
    lost = true;
    timer = setTimeout(() => void check(), CHECK_MS);
  },
  /** Something answered, so the server is there. */
  reachable(): void {
    clearTimeout(timer);
    if (!lost) return;
    lost = false;
    window.dispatchEvent(new Event('katib:reconnected'));
  },
  /** Check now instead of waiting for the next try. */
  retry(): void {
    void check();
  },
};
