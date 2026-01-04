const CACHE_NAME = 'homegym-v1';
const urlsToCache = [
  '/',
  '/static/core/images/muscle_map.svg',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
];

// Install Event - Cache wichtige Assets
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Caching app shell');
        return cache.addAll(urlsToCache);
      })
      .catch(err => console.error('[Service Worker] Cache failed:', err))
  );
  self.skipWaiting();
});

// Activate Event - Alte Caches löschen
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Fetch Event - Cache-First für Static Assets, Network-First für API
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    // Cache CDN resources
    if (url.host.includes('cdn.jsdelivr.net')) {
      event.respondWith(
        caches.match(request).then(response => {
          return response || fetch(request).then(fetchResponse => {
            return caches.open(CACHE_NAME).then(cache => {
              cache.put(request, fetchResponse.clone());
              return fetchResponse;
            });
          });
        })
      );
    }
    return;
  }

  // API Requests: Network-First (immer frische Daten versuchen)
  if (url.pathname.startsWith('/api/') || request.method !== 'GET') {
    event.respondWith(
      fetch(request)
        .catch(() => caches.match(request))
    );
    return;
  }

  // Static Assets & Pages: Cache-First mit Network Fallback
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) {
        // Cached version found, return it but update cache in background
        fetch(request).then(freshResponse => {
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, freshResponse);
          });
        }).catch(() => {});
        return cachedResponse;
      }

      // Not in cache, fetch from network
      return fetch(request).then(response => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type === 'error') {
          return response;
        }

        // Clone the response
        const responseToCache = response.clone();
        
        // Cache static resources only
        if (url.pathname.startsWith('/static/') || url.pathname === '/') {
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
          });
        }

        return response;
      }).catch(() => {
        // Network failed, show offline page
        if (request.destination === 'document') {
          return caches.match('/');
        }
      });
    })
  );
});

// Background Sync (optional - für später)
self.addEventListener('sync', event => {
  console.log('[Service Worker] Background sync:', event.tag);
  if (event.tag === 'sync-training-data') {
    event.waitUntil(syncTrainingData());
  }
});

async function syncTrainingData() {
  // Placeholder für zukünftige Offline-Sync-Funktionalität
  console.log('[Service Worker] Syncing training data...');
}

// Push Notifications (optional - für später)
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'HomeGym';
  const options = {
    body: data.body || 'Neue Benachrichtigung',
    icon: '/static/core/images/icon-192x192.png',
    badge: '/static/core/images/icon-192x192.png',
    vibrate: [200, 100, 200],
    data: data.url || '/'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data)
  );
});
