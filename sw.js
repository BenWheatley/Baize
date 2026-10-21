// Offline support with no build step. Every same-origin file, and the web fonts, are served from the
// cache when there is one and refreshed from the network in the background, so an edited baize.html
// is fetched at once; open pages are told, and offer a reload. Nothing here needs a version number.
const CACHE = 'baize';
const SHELL = ['./', 'baize.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/icon-maskable-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

/** Fetch past the browser's own cache (GitHub Pages lets it keep files for ten minutes). */
const fresh = request => fetch(request, { cache: 'no-cache' });

/** Tell every open page that the game it is running has been replaced, so it can offer a reload. */
async function announce() {
  for (const client of await self.clients.matchAll()) client.postMessage({ type: 'updated' });
}

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET' || !request.url.startsWith('http')) return;
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(request, { ignoreSearch: true });
    const watched = request.mode === 'navigate' || new URL(request.url).pathname.endsWith('/baize.html');
    const before = watched ? cached?.clone() : null;          // the page reads `cached` itself, so keep a copy to compare with
    const refresh = fresh(request).then(async response => {
      if (response.ok || response.type === 'opaque') {
        const changed = before && response.ok &&
          (await before.text()) !== (await response.clone().text());
        await cache.put(request, response.clone());
        if (changed) announce();
      }
      return response;
    });
    if (cached) { refresh.catch(() => {}); return cached; }
    try {
      return await refresh;
    } catch (error) {
      if (request.mode === 'navigate') return cache.match('baize.html');
      throw error;
    }
  }));
});
