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
        
        // Online/Offline Events
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
        
        // Initial Status setzen
        this.updateConnectionStatus();
        
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
                
                // Markiere erfolgreiche Syncs
                if (result.results) {
                    for (const syncResult of result.results) {
                        if (syncResult.success) {
                            await this.markAsSynced('trainingData', syncResult.id);
                            console.log('[Manual Sync] Marked as synced:', syncResult.id);
                        } else {
                            console.warn('[Manual Sync] Sync failed for:', syncResult.id, syncResult.error);
                        }
                    }
                }
                
                // Zeige Erfolg
                this.showToast(`✓ ${result.synced_count || validData.length} Sätze synchronisiert`, 'success');
                
                // Seite nach kurzer Verzögerung neu laden
                setTimeout(() => {
                    if (window.location.pathname.includes('/training/')) {
                        console.log('[Manual Sync] Reloading page...');
                        window.location.reload();
                    }
                }, 1500);
                
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

    updateConnectionStatus() {
        const isOnline = navigator.onLine;
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

    createConnectionIndicator() {
        // Prüfe ob schon vorhanden
        if (document.getElementById('connectionIndicator')) return;
        
        const indicator = document.createElement('div');
        indicator.id = 'connectionIndicator';
        indicator.className = navigator.onLine ? 'connection-indicator online' : 'connection-indicator offline';
        indicator.innerHTML = navigator.onLine ? 
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
}

// Global initialisieren (nur wenn noch nicht vorhanden)
if (typeof window.offlineManager === 'undefined') {
    window.offlineManager = new OfflineManager();
    console.log('[Offline Manager] Initialized');
} else {
    console.log('[Offline Manager] Already initialized');
}
