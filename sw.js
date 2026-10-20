// Offline support with no build step. Every same-origin file, and the web fonts, are served from the
// cache when there is one and refreshed from the network in the background, so an edited baize.html
// shows up the next time the app is opened. Nothing here needs a version number.
const CACHE = 'baize';
const SHELL = ['./', 'baize.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/icon-maskable-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET' || !request.url.startsWith('http')) return;
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(request, { ignoreSearch: true });
    const refresh = fetch(request).then(response => {
      if (response.ok || response.type === 'opaque') cache.put(request, response.clone());
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
