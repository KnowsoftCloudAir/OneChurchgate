/* Churchgate offline shell — cache app UI + Kwealth resources for offline use */
const CACHE = 'churchgate-offline-v4';
const PRECACHE = [
  '/',
  '/login',
  '/member/portal',
  '/member/kwealth',
  '/member/kwealth/books',
  '/member/kwealth/notes',
  '/member/kwealth/excerpts',
  '/member/kwealth/borrow',
  '/member/device-music',
  '/member/hymns',
  '/static/manifest.json',
  '/static/sw.js',
  '/static/js/offline-store.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-512-maskable.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(PRECACHE.map((u) => cache.add(u).catch(() => null)))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function isAsset(url) {
  return (
    url.pathname.startsWith('/static/') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname.endsWith('.json')
  );
}

function isAppShell(url) {
  const p = url.pathname;
  return (
    p === '/' ||
    p === '/login' ||
    p.startsWith('/member/') ||
    p.startsWith('/kwealth')
  );
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Network-first for APIs; cache-first for shell & static
  if (url.pathname.startsWith('/member/api/') || url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ ok: false, offline: true, error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' },
          status: 503,
        })
      )
    );
    return;
  }

  if (isAsset(url) || isAppShell(url)) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        const network = fetch(event.request)
          .then((res) => {
            if (res && res.ok) cache.put(event.request, res.clone()).catch(() => {});
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok && isAppShell(url)) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(event.request).then((r) => r || caches.match('/member/portal') || caches.match('/')))
  );
});
