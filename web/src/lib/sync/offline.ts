import { api } from '../api/client';
import { plural } from '../format';
import { toasts } from '../state/toast.svelte';
import { browserOutbox, replayOutbox } from './outbox';

/** Let the browser keep Katib and the images you have opened, so they work without a connection. */
export function registerOfflineSupport(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').catch(() => undefined);
  });
}

/** Forget the cached images. Called on sign-out so the next person on this device cannot see them. */
export async function forgetCachedImages(): Promise<void> {
  if ('caches' in globalThis) await caches.delete('katib-images').catch(() => false);
}

/** Send edits made while offline, from an earlier visit. */
export async function sendWaitingEdits(): Promise<void> {
  const result = await replayOutbox(browserOutbox, (imageId, ops) => api.annotations.batch(imageId, ops));
  if (result.sent > 0) toasts.show(`Sent ${plural(result.sent, 'edit')} you made while offline.`);
  if (result.rejected > 0) {
    toasts.show(`${plural(result.rejected, 'offline edit')} could not be applied because the shapes had changed.`);
  }
}
