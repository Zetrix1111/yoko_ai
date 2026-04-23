// Estrategia:
//   - HTML (navegación)  → network-first (siempre baja el último index.html)
//   - Assets hash-eados  → cache-first (Vite genera archivos con hash único por build)
//   - /api/*             → nunca se cachea (siempre pega al servidor)
//
// Bump CACHE_VERSION cuando quieras invalidar todo el caché a mano.
const CACHE_VERSION = 'v2';
const CACHE_NAME    = `yoko-cache-${CACHE_VERSION}`;

self.addEventListener('install', (event) => {
  // Activa esta versión del SW en cuanto termina de instalar,
  // sin esperar a que se cierren todas las pestañas abiertas.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Borra cualquier caché de versiones anteriores
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    );
    // Toma control inmediato de pestañas ya abiertas
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return; // no tocar endpoints

  // ── HTML / navegación: network-first ──
  if (req.mode === 'navigate' || req.destination === 'document') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(CACHE_NAME);
        cache.put(req, fresh.clone());
        return fresh;
      } catch {
        const cached = await caches.match(req);
        return cached || caches.match('/index.html');
      }
    })());
    return;
  }

  // ── Assets (JS, CSS, imágenes): cache-first ──
  event.respondWith((async () => {
    const cached = await caches.match(req);
    if (cached) return cached;
    try {
      const fresh = await fetch(req);
      if (fresh.ok && fresh.type === 'basic') {
        const cache = await caches.open(CACHE_NAME);
        cache.put(req, fresh.clone());
      }
      return fresh;
    } catch {
      return cached || Response.error();
    }
  })());
});
