# HomeGym Server Deployment - Quick Start

## 📋 Checkliste vor Deployment

### 1. Lokale Vorbereitung
- [x] requirements.txt aktualisiert (Pillow 12.1.0)
- [x] PWA Icons generiert (192x192, 512x512)
- [x] Service Worker getestet
- [ ] settings.py für Production bereit:
  - DEBUG = False
  - ALLOWED_HOSTS angepasst
  - SECRET_KEY aus Umgebungsvariable
  - STATIC_ROOT gesetzt

### 2. Server Dateien
```bash
# Diese Dateien auf Server übertragen:
- requirements.txt
- homegym.service (Systemd Autostart)
- homegym.nginx (Nginx Config)
- deploy.sh (Deployment-Script)
- Alle App-Dateien
```

---

## 🚀 Schnelle Installation auf Server

### Schritt 1: Projekt hochladen
```bash
# Via SCP
scp -r * user@server:/var/www/vhosts/DEINE-DOMAIN.de/homegym/

# Oder via Git
ssh user@server
cd /var/www/vhosts/DEINE-DOMAIN.de/
git clone https://github.com/DEIN-REPO/homegym.git
cd homegym
```

### Schritt 2: Deployment Script ausführen
```bash
chmod +x deploy.sh
./deploy.sh
```

Das Script macht:
- ✅ Virtual Environment erstellen
- ✅ Dependencies installieren
- ✅ Verzeichnisse erstellen (logs, static, media)
- ✅ Migrations ausführen
- ✅ Übungen importieren
- ✅ Static files sammeln
- ✅ Gunicorn starten (Dev-Modus)

### Schritt 3: Systemd Service einrichten (Autostart)
```bash
# 1. Domain in homegym.service anpassen
nano homegym.service
# - DEINE-DOMAIN.de ersetzen
# - SECRET_KEY einfügen
# - DB-Passwort einfügen

# 2. Service installieren
sudo cp homegym.service /etc/systemd/system/
sudo systemctl daemon-reload

# 3. Service aktivieren & starten
sudo systemctl enable homegym
sudo systemctl start homegym

# 4. Status prüfen
sudo systemctl status homegym
```

### Schritt 4: Nginx einrichten
```bash
# 1. Domain in homegym.nginx anpassen
nano homegym.nginx
# - DEINE-DOMAIN.de ersetzen

# 2. Nginx Config installieren
sudo cp homegym.nginx /etc/nginx/sites-available/homegym
sudo ln -s /etc/nginx/sites-available/homegym /etc/nginx/sites-enabled/

# 3. Logs-Verzeichnis erstellen
sudo mkdir -p /var/www/vhosts/DEINE-DOMAIN.de/homegym/logs

# 4. Testen & Neuladen
sudo nginx -t
sudo systemctl reload nginx
```

### Schritt 5: SSL/HTTPS mit Let's Encrypt
```bash
# Certbot installieren (falls nicht vorhanden)
sudo apt install certbot python3-certbot-nginx

# SSL-Zertifikat für Domain ausstellen
sudo certbot --nginx -d DEINE-DOMAIN.de -d www.DEINE-DOMAIN.de

# Auto-Renewal testen
sudo certbot renew --dry-run
```

---

## 🔧 Service Management

### Systemd Befehle
```bash
# Status prüfen
sudo systemctl status homegym

# Starten
sudo systemctl start homegym

# Stoppen
sudo systemctl stop homegym

# Neustarten (nach Code-Änderungen)
sudo systemctl restart homegym

# Logs anzeigen
sudo journalctl -u homegym -f

# Gunicorn Logs
tail -f /var/www/vhosts/DEINE-DOMAIN.de/homegym/logs/gunicorn-error.log
```

### Nach Code-Updates
```bash
cd /var/www/vhosts/DEINE-DOMAIN.de/homegym

# Git pull (wenn via Git)
git pull

# Dependencies aktualisieren
source venv/bin/activate
pip install -r requirements.txt

# Migrations & Static Files
python manage.py migrate
python manage.py collectstatic --noinput

# Service neustarten
sudo systemctl restart homegym
```

---

## 📊 Monitoring & Logs

### Log-Dateien
```bash
# Gunicorn Access Log
tail -f logs/gunicorn-access.log

# Gunicorn Error Log
tail -f logs/gunicorn-error.log

# Nginx Access Log
sudo tail -f /var/log/nginx/access.log

# Nginx Error Log
sudo tail -f /var/log/nginx/error.log

# Systemd Service Log
sudo journalctl -u homegym -f
```

### Health Check
```bash
# App Status
curl -I https://DEINE-DOMAIN.de

# Service Status
sudo systemctl is-active homegym

# Nginx Status
sudo systemctl status nginx
```

---

## 🛡️ Sicherheit

### Firewall (UFW)
```bash
# HTTP & HTTPS erlauben
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

### Berechtigungen
```bash
# App-Verzeichnis
sudo chown -R www-data:www-data /var/www/vhosts/DEINE-DOMAIN.de/homegym

# Logs beschreibbar
sudo chmod -R 755 /var/www/vhosts/DEINE-DOMAIN.de/homegym/logs

# Static/Media beschreibbar
sudo chmod -R 755 /var/www/vhosts/DEINE-DOMAIN.de/homegym/staticfiles
sudo chmod -R 755 /var/www/vhosts/DEINE-DOMAIN.de/homegym/media
```

---

## 🐛 Troubleshooting

### Problem: App startet nicht
```bash
# 1. Logs prüfen
sudo journalctl -u homegym -n 50
tail -f logs/gunicorn-error.log

# 2. Manuell starten (Debug)
cd /var/www/vhosts/DEINE-DOMAIN.de/homegym
source venv/bin/activate
gunicorn --bind 127.0.0.1:8000 config.wsgi:application

# 3. Socket-Datei prüfen
ls -la /var/www/vhosts/DEINE-DOMAIN.de/homegym/homegym.sock
```

### Problem: Static Files nicht gefunden
```bash
# collectstatic nochmal ausführen
python manage.py collectstatic --noinput --clear

# Nginx Cache leeren
sudo systemctl reload nginx
```

### Problem: 502 Bad Gateway
```bash
# 1. Gunicorn läuft?
sudo systemctl status homegym

# 2. Socket-Verbindung?
sudo nginx -t

# 3. Berechtigungen?
ls -la /var/www/vhosts/DEINE-DOMAIN.de/homegym/homegym.sock
```

---

## 📱 PWA auf Android testen

Nach erfolgreichem Deployment:

1. **Chrome auf Android** öffnen
2. **https://DEINE-DOMAIN.de** aufrufen
3. **Menu (⋮)** → "Zum Startbildschirm hinzufügen"
4. **Bestätigen** → App installiert!

**PWA Features:**
- ✅ Fullscreen-Modus
- ✅ Home Screen Icon
- ✅ Offline-Funktionalität (gecachte Seiten)
- ✅ Push-Notifications bereit (später)

---

## 🎯 Performance-Optimierung

### Nginx Caching
```nginx
# In homegym.nginx bereits konfiguriert:
- Static Files: 30 Tage Cache
- Media Files: 7 Tage Cache
- Service Worker: Kein Cache (immer aktuell)
```

### Gunicorn Workers
```bash
# Formel: (2 x CPU_CORES) + 1
# Beispiel: 2 CPUs → 5 Workers

# In homegym.service anpassen:
--workers 5
```

### Database Indexing
```bash
# Falls Performance-Probleme:
python manage.py dbshell
# Dann in MySQL:
SHOW INDEX FROM core_satz;
```

---

## 📞 Support

Bei Problemen:
1. Logs prüfen (siehe oben)
2. Service-Status prüfen
3. Nginx-Konfiguration testen: `sudo nginx -t`
4. Gunicorn manuell starten (Debug-Modus)

**Wichtige Dateien:**
- `/etc/systemd/system/homegym.service` (Service Config)
- `/etc/nginx/sites-available/homegym` (Nginx Config)
- `/var/www/vhosts/DEINE-DOMAIN.de/homegym/.env` (Umgebungsvariablen)
- `logs/gunicorn-error.log` (Error Logs)
