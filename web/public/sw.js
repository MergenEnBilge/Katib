// Keeps Katib usable when the connection drops.
//
// - The app itself (page and hashed assets) is cached, so it opens offline.
// - Images and thumbnails you have looked at are kept, up to a limit, so you can keep labeling them.
// - Everything else in the API always goes to the network. Edits made offline wait in the
//   browser's outbox and are sent later (see src/lib/sync/outbox.ts).

const SHELL = 'katib-shell-v1';
const IMAGES = 'katib-images';
const MAX_IMAGES = 400;

const isImage = (url) => /^\/api\/v1\/images\/[^/]+\/(file|thumb)$/.test(url.pathname);
const isAsset = (url) => url.pathname.startsWith('/assets/');

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const name of await caches.keys()) {
        if (name !== SHELL && name !== IMAGES) await caches.delete(name);
      }
      await self.clients.claim();
    })(),
  );
});

async function cacheFirst(request, cacheName, limit) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) {
    await cache.put(request, response.clone());
    if (limit) await trim(cache, limit);
  }
  return response;
}

async function trim(cache, limit) {
  const keys = await cache.keys();
  // Oldest first: the cache lists entries in the order they were added.
  for (const key of keys.slice(0, Math.max(0, keys.length - limit))) await cache.delete(key);
}

async function page(request) {
  const cache = await caches.open(SHELL);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put('/', response.clone());
    return response;
  } catch (error) {
    const saved = await cache.match('/');
    if (saved) return saved;
    throw error;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') event.respondWith(page(request));
  else if (isAsset(url)) event.respondWith(cacheFirst(request, SHELL));
  else if (isImage(url)) event.respondWith(cacheFirst(request, IMAGES, MAX_IMAGES));
});
