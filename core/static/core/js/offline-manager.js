// Offline Status Indicator & IndexedDB Manager
// Zeigt Connection Status und cached kritische Daten offline

class OfflineManager {
    constructor() {
        this.dbName = 'HomeGymDB';
        this.dbVersion = 1;
        this.db = null;
        this.init();
    }

    async init() {
        // IndexedDB initialisieren
        await this.openDB();

        // Online/Offline Events (mit zusätzlicher echter Prüfung)
        window.addEventListener('online', async () => {
            // Doppelt prüfen mit echtem Connectivity-Check
            const reallyOnline = await this.checkRealConnectivity();
            if (reallyOnline) {
                this.handleOnline();
            }
        });
        window.addEventListener('offline', () => this.handleOffline());

        // Initial Status setzen (mit echter Prüfung)
        await this.updateConnectionStatus();

        // Periodisch Status prüfen (alle 30 Sekunden für Desktop-PCs mit Problemen)
        setInterval(() => this.updateConnectionStatus(), 30000);

        // Markiere offline Sätze in UI (falls auf Training-Session)
        if (window.location.pathname.includes('/training/')) {
            await this.markOfflineSetsInUI();
        }

        // Service Worker Messages empfangen
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', event => {
                if (event.data.type === 'SYNC_COMPLETE') {
                    console.log(`[Sync] ${event.data.synced_count} Sätze synchronisiert`);
                    this.showToast(`✓ ${event.data.synced_count} Sätze synchronisiert`, 'success');

                    // Seite neu laden wenn auf Training-Session
                    if (window.location.pathname.includes('/training/')) {
                        setTimeout(() => window.location.reload(), 1500);
                    }
                }
            });
        }
    }

    async openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('IndexedDB error:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('[IndexedDB] Opened successfully');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Object Stores für offline Daten
                if (!db.objectStoreNames.contains('trainingData')) {
                    const trainingStore = db.createObjectStore('trainingData', { keyPath: 'id', autoIncrement: true });
                    trainingStore.createIndex('timestamp', 'timestamp', { unique: false });
                    trainingStore.createIndex('synced', 'synced', { unique: false });
                }

                if (!db.objectStoreNames.contains('exercises')) {
                    db.createObjectStore('exercises', { keyPath: 'id' });
                }

                if (!db.objectStoreNames.contains('plans')) {
                    db.createObjectStore('plans', { keyPath: 'id' });
                }

                console.log('[IndexedDB] Database upgraded to version', this.dbVersion);
            };
        });
    }

    handleOnline() {
        console.log('[Connection] Back online');
        this.updateConnectionStatus();
        this.showToast('✓ Verbindung wiederhergestellt', 'success');

        // Trigger manual sync immediately (don't rely only on Background Sync)
        this.manualSync();

        // Also register Background Sync
        if ('serviceWorker' in navigator && 'sync' in navigator.serviceWorker) {
            navigator.serviceWorker.ready.then(registration => {
                return registration.sync.register('sync-training-data');
            }).catch(err => console.error('Sync registration failed:', err));
        }
    }

    async manualSync() {
        console.log('[Manual Sync] Starting...');

        try {
            const unsyncedData = await this.getUnsyncedData('trainingData');

            if (unsyncedData.length === 0) {
                console.log('[Manual Sync] No data to sync');
                return;
            }

            console.log(`[Manual Sync] Found ${unsyncedData.length} items to sync`);

            // Filtere ungültige Einträge (z.B. uebung_id null)
            const validData = unsyncedData.filter(item => {
                if (!item.uebung_id || isNaN(item.uebung_id)) {
                    console.warn('[Manual Sync] Skipping invalid item (no uebung_id):', item.id);
                    return false;
                }
                return true;
            });

            if (validData.length === 0) {
                console.log('[Manual Sync] No valid data to sync');
                // Lösche ungültige Einträge
                for (const item of unsyncedData) {
                    if (!item.uebung_id || isNaN(item.uebung_id)) {
                        await this.deleteItem('trainingData', item.id);
                    }
                }
                return;
            }

            console.log(`[Manual Sync] Syncing ${validData.length} valid items`);

            // CSRF Token holen
            const csrfToken = this.getCSRFToken();

            const response = await fetch('/api/sync-offline/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(validData)
            });

            if (response.ok) {
                const result = await response.json();
                console.log('[Manual Sync] Response:', result);

                let syncedCount = 0;
                let failedCount = 0;

                // Markiere erfolgreiche Syncs
                if (result.results) {
                    for (const syncResult of result.results) {
                        if (syncResult.success) {
                            await this.markAsSynced('trainingData', syncResult.id);
                            syncedCount++;
                            console.log('[Manual Sync] Marked as synced:', syncResult.id);
                        } else {
                            failedCount++;
                            console.warn('[Manual Sync] Sync failed for:', syncResult.id, syncResult.error);
                        }
                    }
                }

                // Zeige detailliertes Feedback
                if (syncedCount > 0) {
                    const message = syncedCount === 1
                        ? '✓ 1 Satz synchronisiert'
                        : `✓ ${syncedCount} Sätze synchronisiert`;

                    // Verwende window.showToast falls vorhanden (von toast.js), sonst diese Methode
                    if (typeof window.showToast === 'function') {
                        window.showToast(message, 'success', 3000);
                    } else {
                        this.showToast(message, 'success');
                    }
                }

                if (failedCount > 0) {
                    const message = `⚠ ${failedCount} Satz(e) konnten nicht synchronisiert werden`;
                    if (typeof window.showToast === 'function') {
                        window.showToast(message, 'warning', 4000);
                    } else {
                        this.showToast(message, 'warning');
                    }
                }

                // Seite nach kurzer Verzögerung neu laden
                if (syncedCount > 0) {
                    setTimeout(() => {
                        if (window.location.pathname.includes('/training/')) {
                            console.log('[Manual Sync] Reloading page...');
                            window.location.reload();
                        }
                    }, 1500);
                }

            } else {
                const errorText = await response.text();
                console.error('[Manual Sync] Server error:', response.status, errorText);
                this.showToast('Sync fehlgeschlagen: ' + response.status, 'error');
            }

        } catch (error) {
            console.error('[Manual Sync] Error:', error);
            this.showToast('Sync Fehler: ' + error.message, 'error');
        }
    }

    getCSRFToken() {
        const name = 'csrftoken';
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                return cookie.substring(name.length + 1);
            }
        }
        return '';
    }

    async deleteItem(storeName, id) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.delete(id);

            request.onsuccess = () => {
                console.log('[IndexedDB] Deleted item:', id);
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    }

    handleOffline() {
        console.log('[Connection] Gone offline');
        this.updateConnectionStatus();
        this.showToast('⚠ Offline-Modus aktiv', 'warning');
    }

    async checkRealConnectivity() {
        // Echte Server-Prüfung statt navigator.onLine (unzuverlässig auf Desktop)
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout

            const response = await fetch('/static/core/manifest.json', {
                method: 'HEAD',
                cache: 'no-cache',
                signal: controller.signal
            });

            clearTimeout(timeoutId);
            return response.ok;
        } catch (error) {
            console.log('[Connection Check] Failed:', error.message);
            return false;
        }
    }

    async updateConnectionStatus() {
        // Nutze echte Server-Prüfung statt navigator.onLine
        const isOnline = await this.checkRealConnectivity();
        const indicator = document.getElementById('connectionIndicator');

        if (!indicator) {
            // Erstelle Indikator wenn nicht vorhanden
            this.createConnectionIndicator();
            return;
        }

        if (isOnline) {
            indicator.classList.remove('offline');
            indicator.classList.add('online');
            indicator.innerHTML = '<i class="bi bi-wifi"></i> Online';
        } else {
            indicator.classList.remove('online');
            indicator.classList.add('offline');
            indicator.innerHTML = '<i class="bi bi-wifi-off"></i> Offline';
        }
    }

    async createConnectionIndicator() {
        // Prüfe ob schon vorhanden
        if (document.getElementById('connectionIndicator')) return;

        // Echte Connectivity prüfen
        const isOnline = await this.checkRealConnectivity();

        const indicator = document.createElement('div');
        indicator.id = 'connectionIndicator';
        indicator.className = isOnline ? 'connection-indicator online' : 'connection-indicator offline';
        indicator.innerHTML = isOnline ?
            '<i class="bi bi-wifi"></i> Online' :
            '<i class="bi bi-wifi-off"></i> Offline';

        document.body.appendChild(indicator);
    }

    showToast(message, type = 'info') {
        // Einfacher Toast ohne Bootstrap Toast (zu komplex)
        const toast = document.createElement('div');
        toast.className = `connection-toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        // Animation
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    async registerBackgroundSync() {
        if ('serviceWorker' in navigator && 'sync' in navigator.serviceWorker) {
            const registration = await navigator.serviceWorker.ready;
            console.log('[Background Sync] Registered');
        }
    }

    // ======== IndexedDB CRUD Operations ========

    async saveOfflineData(storeName, data) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);

            // Timestamp und Sync-Status hinzufügen
            const dataToSave = {
                ...data,
                timestamp: Date.now(),
                synced: false
            };

            const request = store.add(dataToSave);

            request.onsuccess = () => {
                console.log(`[IndexedDB] Saved to ${storeName}:`, dataToSave);
                resolve(request.result);
            };

            request.onerror = () => {
                console.error(`[IndexedDB] Save error:`, request.error);
                reject(request.error);
            };
        });
    }

    async getOfflineData(storeName, id = null) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);

            let request;
            if (id) {
                request = store.get(id);
            } else {
                request = store.getAll();
            }

            request.onsuccess = () => {
                resolve(request.result);
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    async getUnsyncedData(storeName) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);

            // Hole alle Daten und filtere nach synced = false
            const request = store.getAll();

            request.onsuccess = () => {
                const allData = request.result || [];
                const unsyncedData = allData.filter(item => item.synced === false);
                console.log('[IndexedDB] Unsynced data found:', unsyncedData.length);
                resolve(unsyncedData);
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    async getAllData(storeName) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);
            const request = store.getAll();

            request.onsuccess = () => {
                resolve(request.result);
            };

            request.onerror = () => {
                reject(request.error);
            };
        });
    }

    async markAsSynced(storeName, id) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const getRequest = store.get(id);

            getRequest.onsuccess = () => {
                const data = getRequest.result;
                if (data) {
                    data.synced = true;
                    const putRequest = store.put(data);

                    putRequest.onsuccess = () => {
                        console.log(`[IndexedDB] Marked as synced: ${id}`);
                        resolve();
                    };

                    putRequest.onerror = () => reject(putRequest.error);
                } else {
                    reject(new Error('Data not found'));
                }
            };

            getRequest.onerror = () => reject(getRequest.error);
        });
    }

    async clearSyncedData(storeName) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.getAll();

            request.onsuccess = () => {
                const allData = request.result || [];
                const syncedItems = allData.filter(item => item.synced === true);

                // Lösche nur synced Items
                const deleteTransaction = this.db.transaction([storeName], 'readwrite');
                const deleteStore = deleteTransaction.objectStore(storeName);

                let deletedCount = 0;
                for (const item of syncedItems) {
                    deleteStore.delete(item.id);
                    deletedCount++;
                }

                deleteTransaction.oncomplete = () => {
                    console.log(`[IndexedDB] Cleared ${deletedCount} synced items from ${storeName}`);
                    resolve(deletedCount);
                };

                deleteTransaction.onerror = () => reject(deleteTransaction.error);
            };

            request.onerror = () => reject(request.error);
        });
    }

    async clearAllData(storeName) {
        if (!this.db) await this.openDB();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const clearRequest = store.clear();

            clearRequest.onsuccess = () => {
                console.log(`[IndexedDB] Cleared ALL data from ${storeName}`);
                resolve();
            };

            clearRequest.onerror = () => reject(clearRequest.error);
        });
    }

    async markOfflineSetsInUI() {
        try {
            const unsyncedData = await this.getUnsyncedData('trainingData');

            if (unsyncedData.length === 0) {
                console.log('[Offline UI] No unsynced data to mark');
                return;
            }

            console.log(`[Offline UI] Marking ${unsyncedData.length} offline sets`);

            // Warte kurz bis DOM geladen ist
            await new Promise(resolve => setTimeout(resolve, 500));

            for (const item of unsyncedData) {
                // Suche nach der Zeile mit diesem Satz
                // URL-Pattern: /training/.../edit-set/123/
                const setIdMatch = item.url && item.url.match(/\/edit-set\/(\d+)\//);
                if (!setIdMatch) continue;

                const setId = setIdMatch[1];
                const editBtn = document.querySelector(`button[onclick*="openEditModal('${setId}'"]`);

                if (editBtn) {
                    const row = editBtn.closest('tr');
                    if (row) {
                        // Füge gelben Hintergrund hinzu
                        row.classList.add('bg-warning', 'bg-opacity-10');

                        // Füge Badge hinzu (falls noch nicht vorhanden)
                        if (!row.querySelector('.badge.bg-warning')) {
                            const badge = document.createElement('span');
                            badge.className = 'badge bg-warning text-dark ms-2';
                            badge.textContent = 'Offline';
                            badge.title = 'Wird beim nächsten Sync übertragen';

                            const gewichtCell = row.cells[1];
                            if (gewichtCell) {
                                gewichtCell.appendChild(badge);
                            }
                        }

                        console.log(`[Offline UI] Marked set ${setId} as offline`);
                    }
                }
            }

            // Zeige Info-Toast wenn Offline-Sätze vorhanden
            if (unsyncedData.length > 0) {
                const message = unsyncedData.length === 1
                    ? '1 Satz wartet auf Synchronisierung'
                    : `${unsyncedData.length} Sätze warten auf Synchronisierung`;

                if (typeof window.showToast === 'function') {
                    window.showToast(message, 'info', 4000);
                }
            }

        } catch (error) {
            console.error('[Offline UI] Error marking offline sets:', error);
        }
    }
}

// Global initialisieren (nur wenn noch nicht vorhanden)
if (typeof window.offlineManager === 'undefined') {
    window.offlineManager = new OfflineManager();
    console.log('[Offline Manager] Initialized');
} else {
    console.log('[Offline Manager] Already initialized');
}
