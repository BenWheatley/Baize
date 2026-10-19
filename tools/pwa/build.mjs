// Builds an installable copy of the app in dist/: a complete page around baize.html, a web app
// manifest, a service worker that keeps the app working offline, and the icons.
//
//   node tools/pwa/build.mjs        then serve dist/ from any HTTPS host (or `python3 -m http.server`)
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');
const dist = join(root, 'dist');

const app = readFileSync(join(root, 'baize.html'), 'utf8');
const version = createHash('sha256').update(app).digest('hex').slice(0, 12);

// baize.html is a fragment (title, fonts, styles, then the page). The styles belong in <head>.
const split = app.indexOf('</style>') + '</style>'.length;
const [head, body] = [app.slice(0, split), app.slice(split)];

const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#2c6a54">
<meta name="description" content="A card table for solitaire games: Klondike, FreeCell, Golf, Pyramid, Spider and Forty Thieves.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Baize">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
${head}
</head>
<body>
${body}
<script>
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
  addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => { /* the app works without it */ }));
}
</script>
</body>
</html>
`;

const manifest = {
  name: 'Baize',
  short_name: 'Baize',
  description: 'A card table for solitaire games.',
  start_url: './',
  scope: './',
  display: 'standalone',
  orientation: 'any',
  background_color: '#14211b',
  theme_color: '#2c6a54',
  icons: [
    { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
    { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    { src: 'icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
  ],
};

// Same-origin files are cached whole and served from the cache first. The web fonts come from another
// origin and are kept as they are fetched; without them the page falls back to system fonts.
const worker = `const CACHE = 'baize-${version}';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png',
  'icons/icon-maskable-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    try {
      const response = await fetch(request);
      if (response.ok || response.type === 'opaque') cache.put(request, response.clone());
      return response;
    } catch (error) {
      if (request.mode === 'navigate') return cache.match('index.html');
      throw error;
    }
  }));
});
`;

rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, 'icons'), { recursive: true });
writeFileSync(join(dist, 'index.html'), page);
writeFileSync(join(dist, 'manifest.webmanifest'), `${JSON.stringify(manifest, null, 2)}\n`);
writeFileSync(join(dist, 'sw.js'), worker);
cpSync(join(here, 'icons'), join(dist, 'icons'), { recursive: true });
console.log(`dist/ built, cache baize-${version}`);
