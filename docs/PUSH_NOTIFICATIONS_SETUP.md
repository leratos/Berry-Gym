# 🔔 Push Notifications - Setup Guide

## Was sind VAPID Keys?

**VAPID** (Voluntary Application Server Identification) Keys sind kryptografische Schlüssel, die zur Authentifizierung von Web Push Notifications benötigt werden. Sie bestehen aus:

- **Private Key** (geheim halten!) - Zum Signieren von Push-Nachrichten
- **Public Key** (öffentlich) - Wird vom Browser zur Verifizierung verwendet

## 🚀 Einrichtung (Entwicklung & Produktion)

### Schritt 1: VAPID Keys generieren

```bash
# Im Projekt-Root ausführen
python generate_vapid_keys.py
```

**Output:**
```
✅ VAPID Keys generated successfully!

📋 Use the PEM files for your application
------------------------------------------------------------
Public Key file: vapid_public.pem
Private Key file: vapid_private.pem
------------------------------------------------------------
```

### Schritt 2: Keys sichern

Die generierten Dateien werden erstellt:
- `vapid_private.pem` - **GEHEIM HALTEN!**
- `vapid_public.pem` - Kann öffentlich sein

**WICHTIG:** Diese Dateien werden automatisch von `.gitignore` ausgeschlossen und dürfen **NICHT** in Git committed werden!

```gitignore
# Bereits in .gitignore enthalten:
vapid_*.pem
```

### Schritt 3: Umgebungsvariablen konfigurieren

Erstelle/bearbeite deine `.env` Datei:

```env
# Web Push Notifications
VAPID_PRIVATE_KEY_FILE=vapid_private.pem
VAPID_PUBLIC_KEY_FILE=vapid_public.pem
VAPID_CLAIMS_EMAIL=mailto:deine-email@example.com
```

**⚠️ VAPID_CLAIMS_EMAIL:** Ersetze durch eine echte E-Mail-Adresse! Diese wird von Push-Services zur Kontaktaufnahme verwendet, falls es Probleme gibt.

### Schritt 4: Server neu starten

```bash
python manage.py runserver
```

Die Keys werden automatisch beim Start geladen. In der Konsole sollte **KEINE** Warnung erscheinen:
```
# KEINE dieser Meldungen:
⚠️  VAPID Keys nicht geladen: ...
   Push Notifications werden deaktiviert
```

## 🔒 Sicherheitshinweise

### ✅ DO's:

- **Keys EINMAL generieren** und auf allen Servern verwenden
- Private Key in `.env` oder Secrets Manager speichern
- `vapid_*.pem` Dateien in `.gitignore` eintragen
- Backup der Keys an sicherem Ort (Passwort-Manager, Server-Secrets)
- In Produktion: File-Permissions auf 600 setzen (`chmod 600 vapid_private.pem`)

### ❌ DON'Ts:

- **NIEMALS** Private Key in Git committen
- **NICHT** neue Keys generieren, wenn User bereits subscribed sind (alte Subscriptions werden ungültig!)
- Keys nicht per E-Mail oder Chat teilen
- Keine Screenshots der `.pem` Dateien machen

## 📦 Deployment (Production)

### Option A: Keys mit deployen

```bash
# Auf Production-Server
scp vapid_*.pem user@server:/path/to/app/

# File-Permissions setzen
chmod 600 /path/to/app/vapid_private.pem
chmod 644 /path/to/app/vapid_public.pem
```

### Option B: Environment Variables

Statt PEM-Dateien können die Keys auch direkt in Umgebungsvariablen gespeichert werden (für Docker/Cloud):

```python
# In settings.py ändern:
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')  # Kompletter PEM-String
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')   # Kompletter PEM-String
```

PEM als ENV Variable:
```bash
export VAPID_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIKxxx...
-----END EC PRIVATE KEY-----"
```

### Option C: Secrets Manager

Für Cloud-Deployments (AWS, Azure, GCP):
- AWS: Secrets Manager oder Parameter Store
- Azure: Key Vault
- GCP: Secret Manager
- Heroku: Config Vars

## 🧪 Testen

### 1. Im Browser (Chrome DevTools)

```javascript
// Console öffnen (F12)
await pushManager.init();
await pushManager.subscribe();
// Sollte "Push-Benachrichtigungen aktiviert" zurückgeben
```

### 2. Test-Notification senden

```python
# Django Shell
python manage.py shell

from core.views import send_push_notification
from django.contrib.auth.models import User

user = User.objects.get(username='dein_username')
send_push_notification(
    user=user,
    title='🎉 Test Notification',
    body='Push Notifications funktionieren!',
    url='/dashboard/'
)
```

### 3. Überprüfen

Admin-Interface:
- Navigiere zu `/admin/core/pushsubscription/`
- Sollte deine Subscription anzeigen

## 🐛 Troubleshooting

### "VAPID keys not configured" Fehler

**Problem:** Keys wurden nicht geladen

**Lösung:**
1. Prüfe ob `vapid_private.pem` und `vapid_public.pem` existieren
2. Prüfe `.env` Konfiguration
3. Server-Output beim Start prüfen
4. File-Permissions prüfen (müssen lesbar sein)

### "Could not deserialize key data" Fehler

**Problem:** Keys sind im falschen Format oder korrupt

**Lösung:**
1. Keys neu generieren: `python generate_vapid_keys.py`
2. Alte Subscriptions löschen (siehe "Key-Rotation")
3. Server neu starten
4. User müssen sich neu subscriben

**Hinweis:** `py_vapid` generiert Keys im PKCS#8 Format ("BEGIN PRIVATE KEY"), was von `pywebpush` unterstützt wird.

### "Permission denied" beim Subscribe

**Problem:** Notification-Permission wurde abgelehnt

**Lösung:**
1. Browser-Einstellungen → Site-Settings → Benachrichtigungen
2. Permission zurücksetzen oder erlauben
3. Seite neu laden und erneut subscriben

### "Subscription expired (410 Error)"

**Problem:** Browser hat Subscription invalidiert

**Lösung:**
- Wird automatisch behandelt - alte Subscription wird gelöscht
- User muss sich neu subscriben

### Keys wurden neu generiert - User bekommen keine Notifications

**Problem:** Alte Subscriptions sind mit neuen Keys inkompatibel

**Lösung:**
```python
# Alle alten Subscriptions löschen
python manage.py shell
from core.models import PushSubscription
PushSubscription.objects.all().delete()
```

User müssen sich neu subscriben!

## 📊 Monitoring

### Aktive Subscriptions prüfen

```python
from core.models import PushSubscription
from django.contrib.auth.models import User

# Gesamt
print(f"Total Subscriptions: {PushSubscription.objects.count()}")

# Pro User
for user in User.objects.all():
    count = user.push_subscriptions.count()
    if count > 0:
        print(f"{user.username}: {count} device(s)")
```

### Test-Notification an alle User

```python
from core.views import send_push_notification
from django.contrib.auth.models import User

for user in User.objects.all():
    send_push_notification(
        user=user,
        title='📢 HomeGym Update',
        body='Neue Features verfügbar!',
        url='/dashboard/'
    )
```

## 🔄 Key-Rotation (bei Kompromittierung)

Falls der Private Key kompromittiert wurde:

1. **Neue Keys generieren:**
   ```bash
   # Alte Keys sichern
   mv vapid_private.pem vapid_private.pem.old
   mv vapid_public.pem vapid_public.pem.old
   
   # Neue generieren
   python generate_vapid_keys.py
   ```

2. **Alte Subscriptions löschen:**
   ```bash
   python manage.py shell
   from core.models import PushSubscription
   PushSubscription.objects.all().delete()
   ```

3. **Server neustarten** und User informieren, dass sie Notifications neu aktivieren müssen

## 📚 Weitere Ressourcen

- [Web Push Protokoll RFC](https://datatracker.ietf.org/doc/html/rfc8030)
- [VAPID Spezifikation](https://datatracker.ietf.org/doc/html/rfc8292)
- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [pywebpush Dokumentation](https://github.com/web-push-libs/pywebpush)

## ✅ Checkliste

Vor dem Production-Deployment:

- [ ] VAPID Keys generiert
- [ ] `.gitignore` enthält `vapid_*.pem`
- [ ] Keys sind NICHT in Git
- [ ] `.env` konfiguriert mit korrekter E-Mail
- [ ] Keys auf Production-Server kopiert
- [ ] File-Permissions gesetzt (600 für private.pem)
- [ ] Server startet ohne Fehler
- [ ] Test-Notification erfolgreich gesendet
- [ ] Backup der Keys erstellt und sicher verwahrt
- [ ] Monitoring eingerichtet (optional)

## 🎯 Quick Start Zusammenfassung

```bash
# 1. Keys generieren
python generate_vapid_keys.py

# 2. .env konfigurieren
echo "VAPID_PRIVATE_KEY_FILE=vapid_private.pem" >> .env
echo "VAPID_PUBLIC_KEY_FILE=vapid_public.pem" >> .env
echo "VAPID_CLAIMS_EMAIL=mailto:deine@email.com" >> .env

# 3. Server starten
python manage.py runserver

# 4. Im Browser testen (F12 Console)
# await pushManager.subscribe()
```

**Fertig!** 🎉 Push Notifications sind jetzt aktiviert.
