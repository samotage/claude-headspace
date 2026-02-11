/* Service worker for Claude Headspace Voice PWA */
const CACHE_NAME = 'voice-bridge-v4';
const APP_SHELL = [
  '/voice',
  '/static/voice/voice.css',
  '/static/voice/voice-input.js',
  '/static/voice/voice-output.js',
  '/static/voice/voice-api.js',
  '/static/voice/voice-app.js',
  '/static/voice/manifest.json',
  '/static/voice/icons/icon-192.png',
  '/static/voice/icons/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Network-only for API and hook calls
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/hook/')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ error: 'offline' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        })
      )
    );
    return;
  }

  // Network-first for navigation (HTML pages) — always get fresh content,
  // fall back to cache offline. Update cache on success.
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
          return resp;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Network-first for static assets — always fetch fresh, cache as fallback.
  // Previous cache-first with ignoreSearch caused stale JS to persist across deploys.
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const clone = resp.clone();
        caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        return resp;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
