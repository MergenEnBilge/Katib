import { api } from '../api/client';

/** Picture files, by name. Label files are never skipped: a re-import may only bring labels. */
const PICTURE = /\.(jpe?g|png|webp|bmp|tiff?)$/i;
/** How many digests go in one request. */
const BATCH = 500;

/**
 * SHA-256 of a file, in hex. Browsers only offer this on secure pages (https, or localhost), so
 * on plain http it returns null and the file is sent as usual.
 */
export async function digestOf(file: File): Promise<string | null> {
  if (!globalThis.crypto?.subtle) return null;
  const bytes = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * The picture files this project already holds, found by their contents rather than their names.
 * A file that cannot be hashed is never reported as known, so it is sent.
 */
export async function knownPictures(projectId: string, files: File[]): Promise<Set<File>> {
  const digests = new Map<File, string>();
  for (const file of files) {
    if (!PICTURE.test(file.name)) continue;
    const digest = await digestOf(file);
    if (digest) digests.set(file, digest);
  }
  const known = new Set<File>();
  if (digests.size === 0) return known;
  const unique = [...new Set(digests.values())];
  const have = new Set<string>();
  for (let i = 0; i < unique.length; i += BATCH) {
    const reply = await api.images.have(projectId, unique.slice(i, i + BATCH));
    for (const digest of reply.have) have.add(digest);
  }
  for (const [file, digest] of digests) if (have.has(digest)) known.add(file);
  return known;
}
