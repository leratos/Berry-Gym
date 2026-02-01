# PWA & Offline Features - Integration Guide

## ✅ Implementierte Features

### 1. Offline-Indikator (Connection Status)
- **Datei:** `core/static/core/js/offline-manager.js`
- **Styles:** `core/static/core/css/offline-manager.css`
- **Features:**
  - Zeigt Online/Offline Status rechts oben
  - Toast-Benachrichtigungen bei Verbindungswechsel
  - Automatische Erkennung via `navigator.onLine`

### 2. IndexedDB Offline-Speicherung
- **Datei:** `core/static/core/js/offline-manager.js`
- **Object Stores:**
  - `trainingData` - Trainings-Sätze offline speichern
  - `exercises` - Übungsdatenbank offline
  - `plans` - Trainingspläne offline
- **Features:**
  - Automatisches Speichern bei fehlender Verbindung
  - Sync-Status Tracking (synced/unsynced)
  - Timestamp für jede Änderung

### 3. Background Sync
- **Datei:** `core/static/core/service-worker.js`
- **Features:**
  - Automatisches Syncen wenn Verbindung zurück
  - Retry-Logic bei Fehlern
  - Markiert gesyncte Daten in IndexedDB

### 4. Push Notifications (vorbereitet)
- **Datei:** `core/static/core/service-worker.js`
- **Status:** Grundgerüst vorhanden, aber nicht aktiviert
- **Benötigt:** VAPID Keys + Backend-Integration

## 🔧 Integration in Templates

Füge in **jedes Template** (oder in einer Base-Template, falls vorhanden) hinzu:

```django-html
{% load static %}

<!-- In <head> -->
<link rel="stylesheet" href="{% static 'core/css/offline-manager.css' %}">

<!-- Vor </body> -->
<script src="{% static 'core/js/offline-manager.js' %}"></script>
```

## 📱 Verwendung

### Offline-Daten speichern (JavaScript)

```javascript
// Training-Satz offline speichern
const trainingData = {
    uebung_id: 1,
    gewicht: 100,
    wiederholungen: 10,
    rpe: 8
};

await offlineManager.saveOfflineData('trainingData', trainingData);
```

### Unsynced Daten abrufen

```javascript
// Alle unsyncten Trainings-Daten
const unsynced = await offlineManager.getUnsyncedData('trainingData');
console.log('Unsynced items:', unsynced);
```

### Manuell als synced markieren

```javascript
await offlineManager.markAsSynced('trainingData', itemId);
```

## 🚀 Service Worker Update

Nach Änderungen am Service Worker:

```javascript
// In Browser Console
navigator.serviceWorker.getRegistrations().then(registrations => {
    registrations.forEach(reg => reg.unregister());
});
// Dann Seite neu laden
```

## 🧪 Testen

### Offline-Modus simulieren

1. **Chrome DevTools:** Network Tab → "Offline" auswählen
2. **Firefox:** about:config → `network.dns.offline-localhost` auf `false`
3. **Oder:** WLAN/LAN deaktivieren

### Background Sync testen

```javascript
// In Browser Console (wenn online)
navigator.serviceWorker.ready.then(reg => {
    return reg.sync.register('sync-training-data');
});
```

## 📊 Browser Support

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Service Worker | ✅ | ✅ | ✅ | ✅ |
| IndexedDB | ✅ | ✅ | ✅ | ✅ |
| Background Sync | ✅ | ❌ | ❌ | ✅ |
| Push Notifications | ✅ | ✅ | ✅* | ✅ |

*Safari benötigt iOS 16.4+ für Web Push

## 🔐 Sicherheit

- IndexedDB ist pro Origin isoliert
- Service Worker läuft nur auf HTTPS (außer localhost)
- Sensible Daten sollten verschlüsselt gespeichert werden

## 📝 Nächste Schritte (Optional)

1. **Push Notifications aktivieren:**
   - VAPID Keys generieren
   - Backend-Endpoint für Subscription
   - User Permission Request

2. **Offline-First UI:**
   - Forms mit Offline-Queue
   - Loading-States bei Sync
   - Conflict-Resolution bei Daten-Kollisionen

3. **Advanced Caching:**
   - Bilder komprimieren vor Cache
   - Cache-Größe limitieren
   - Selektives Pre-Caching (nur wichtige Routes)

## 🐛 Bekannte Einschränkungen

- Background Sync funktioniert nicht in Firefox/Safari
- IndexedDB hat Browser-Limits (ca. 50MB - 1GB je nach Browser)
- Service Worker benötigt HTTPS in Production
