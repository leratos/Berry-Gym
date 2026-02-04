const CACHE_NAME = 'homegym-v3'; // Version erhöht für Update
const urlsToCache = [
  '/',
  '/dashboard/',
  '/training/select/',
  '/static/core/images/muscle_map.svg',
  '/static/core/css/offline-manager.css',
  '/static/core/css/theme-styles.css',
  '/static/core/js/offline-manager.js',
  '/static/core/js/theme-toggle.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
];

// Install Event - Cache wichtige Assets
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing v3...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Caching app shell and core pages');
        // Cache CDN assets und static files die immer funktionieren sollten
        const staticAssets = urlsToCache.filter(url => 
          url.startsWith('https://') || url.startsWith('/static/')
        );
        
        // Cache HTML-Seiten mit Fehlerbehandlung (falls offline installiert)
        const htmlPages = urlsToCache.filter(url => 
          !url.startsWith('https://') && !url.startsWith('/static/')
        );
        
        return Promise.all([
          cache.addAll(staticAssets).catch(err => {
            console.warn('[SW] Some static assets failed to cache:', err);
          }),
          ...htmlPages.map(url => 
            fetch(url).then(response => {
              if (response.ok) return cache.put(url, response);
            }).catch(err => {
              console.warn(`[SW] Failed to cache ${url}:`, err);
            })
          )
        ]);
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
    // Cache CDN resources - Security: exact hostname match
    if (url.hostname === 'cdn.jsdelivr.net') {
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

  // API Requests & POST: Network-First (immer frische Daten versuchen)
  if (url.pathname.startsWith('/api/') || request.method !== 'GET') {
    event.respondWith(
      fetch(request)
        .catch(() => {
          // Offline Fallback für API-Requests
          return new Response(
            JSON.stringify({ 
              success: false, 
              error: 'Offline - Daten werden lokal gespeichert',
              offline: true
            }),
            { headers: { 'Content-Type': 'application/json' } }
          );
        })
    );
    return;
  }

  // HTML Pages: Network-First mit Cache Fallback für bessere Offline-Navigation
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request).then(response => {
        // Erfolgreicher Fetch - cache es
        if (response && response.ok) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
            console.log('[SW] Cached HTML:', request.url);
          });
        }
        return response;
      }).catch(() => {
        // Offline - versuche aus Cache zu laden
        return caches.match(request).then(cachedResponse => {
          if (cachedResponse) {
            console.log('[SW] Serving from cache:', request.url);
            return cachedResponse;
          }
          
          // Nicht gecached - versuche Dashboard als Fallback
          console.log('[SW] Page not cached, trying dashboard fallback');
          return caches.match('/dashboard/').then(dashboard => {
            if (dashboard) return dashboard;
            return caches.match('/');
          });
        });
      })
    );
    return;
  }

  // Static Assets: Cache-First mit Network Fallback
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
        
        // Cache static resources
        if (url.pathname.startsWith('/static/')) {
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
          });
        }

        return response;
      }).catch(() => {
        // Network failed, return cached version if available
        if (request.destination === 'document') {
          return caches.match('/');
        }
      });
    })
  );
});

// Background Sync
self.addEventListener('sync', event => {
  console.log('[Service Worker] Background sync:', event.tag);
  if (event.tag === 'sync-training-data') {
    event.waitUntil(syncTrainingData());
  }
});

async function syncTrainingData() {
  console.log('[Service Worker] Syncing training data...');
  
  try {
    // Öffne IndexedDB
    const db = await openIndexedDB();
    const unsyncedData = await getUnsyncedData(db, 'trainingData');
    
    if (unsyncedData.length === 0) {
      console.log('[Service Worker] No unsynced data');
      return;
    }
    
    console.log(`[Service Worker] Found ${unsyncedData.length} unsynced items`);
    
    // POST alle unsynced Items als Batch
    const response = await fetch('/api/sync-offline/', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRFToken': await getCSRFToken()
      },
      body: JSON.stringify(unsyncedData)
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('[Service Worker] Sync response:', result);
      
      // Markiere erfolgreiche Syncs
      if (result.results) {
        for (const item of result.results) {
          if (item.success) {
            await markAsSynced(db, 'trainingData', item.id);
            console.log('[Service Worker] Synced:', item.id);
          }
        }
      }
      
      // Notify clients
      const clients = await self.clients.matchAll();
      clients.forEach(client => {
        client.postMessage({
          type: 'SYNC_COMPLETE',
          synced_count: result.synced_count || 0
        });
      });
    } else {
      throw new Error('Sync failed: ' + response.status);
    }
  } catch (error) {
    console.error('[Service Worker] Sync failed:', error);
    throw error; // Retry sync later
  }
}

async function getCSRFToken() {
  // Versuche CSRF Token aus Cookies zu holen
  const cookies = await self.clients.matchAll().then(clients => {
    if (clients.length > 0) {
      return clients[0].cookies;
    }
  });
  
  // Fallback: Return empty (Backend hat @csrf_exempt)
  return '';
}

function openIndexedDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('HomeGymDB', 1);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getUnsyncedData(db, storeName) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readonly');
    const store = transaction.objectStore(storeName);
    
    // Hole alle Daten und filtere nach synced = false
    const request = store.getAll();
    
    request.onsuccess = () => {
      const allData = request.result || [];
      const unsyncedData = allData.filter(item => item.synced === false);
      console.log('[SW] Unsynced data found:', unsyncedData.length);
      resolve(unsyncedData);
    };
    request.onerror = () => reject(request.error);
  });
}

function markAsSynced(db, storeName, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);
    const getRequest = store.get(id);
    
    getRequest.onsuccess = () => {
      const data = getRequest.result;
      if (data) {
        data.synced = true;
        const putRequest = store.put(data);
        putRequest.onsuccess = () => resolve();
        putRequest.onerror = () => reject(putRequest.error);
      }
    };
  });
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
