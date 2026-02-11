/* Service worker for Claude Headspace Voice PWA */
const CACHE_NAME = 'voice-bridge-v2';
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

  // Network-first for API calls
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

  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  );
});
