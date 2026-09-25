import type { BatchOp, OpResult } from '../api/types';

/**
 * Edits that could not be sent yet, one entry per image.
 *
 * Autosave writes here when the network fails, so edits survive a closed tab or a dead battery.
 * Each entry holds the full set of pending operations for its image, so a newer entry simply
 * replaces the older one.
 */
export interface OutboxEntry {
  imageId: string;
  ops: BatchOp[];
  savedAt: number;
}

export interface Outbox {
  put(imageId: string, ops: BatchOp[]): Promise<void>;
  remove(imageId: string): Promise<void>;
  all(): Promise<OutboxEntry[]>;
}

const DB_NAME = 'katib';
const STORE = 'outbox';

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: 'imageId' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Could not open local storage.'));
  });
}

async function run<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = work(db.transaction(STORE, mode).objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error ?? new Error('Local storage failed.'));
    });
  } finally {
    db.close();
  }
}

/** The outbox kept in the browser. Every call fails soft: if storage is blocked, nothing is saved. */
export const browserOutbox: Outbox = {
  async put(imageId, ops) {
    const entry: OutboxEntry = { imageId, ops, savedAt: Date.now() };
    await run('readwrite', (store) => store.put(entry)).catch(() => undefined);
  },
  async remove(imageId) {
    await run('readwrite', (store) => store.delete(imageId)).catch(() => undefined);
  },
  async all() {
    return (await run<OutboxEntry[]>('readonly', (store) => store.getAll()).catch(() => [])) ?? [];
  },
};

export interface ReplayResult {
  /** Operations the server accepted. */
  sent: number;
  /** Operations the server refused, usually because someone else changed the shape first. */
  rejected: number;
}

/**
 * Send everything waiting in the outbox. Entries the server answered are removed, including
 * refused operations, because the server's version wins and retrying would not change that.
 * Entries that hit a network error stay for the next start.
 */
export async function replayOutbox(
  outbox: Outbox,
  send: (imageId: string, ops: BatchOp[]) => Promise<{ results: OpResult[] }>,
): Promise<ReplayResult> {
  const total: ReplayResult = { sent: 0, rejected: 0 };
  for (const entry of await outbox.all()) {
    try {
      const { results } = await send(entry.imageId, entry.ops);
      for (const result of results) {
        if (result.status === 'ok') total.sent++;
        else total.rejected++;
      }
      await outbox.remove(entry.imageId);
    } catch {
      // Still offline, or the server is down. Leave it for next time.
    }
  }
  return total;
}
