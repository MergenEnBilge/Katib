import { api, ApiError } from '../api/client';
import { toasts } from './toast.svelte';

/**
 * Show what a bulk action did, with an Undo that calls the server. The server keeps the inverse
 * for 30 days, so Undo still works after a reload.
 */
export function announceOperation(
  summary: string,
  operationId: string | null | undefined,
  afterRevert: () => void | Promise<void>,
): void {
  if (!operationId) {
    toasts.show(summary);
    return;
  }
  toasts.show(`${summary} You can undo this for 30 days.`, {
    label: 'Undo',
    run: () => void revert(operationId, afterRevert),
  });
}

export async function revert(
  operationId: string,
  afterRevert: () => void | Promise<void>,
): Promise<void> {
  try {
    const result = await api.operations.revert(operationId);
    toasts.show(result.message);
  } catch (err) {
    toasts.show(err instanceof ApiError ? err.message : 'Could not undo that.');
  }
  await afterRevert();
}
