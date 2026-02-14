# 🚀 HomeGym App - Production Deployment Guide

## Übersicht
Dieses Dokument beschreibt die Schritte zum Deployment der HomeGym App auf einem Linux Rootserver mit Plesk.

---

## ✅ Voraussetzungen
- Linux Server mit Plesk installiert
- Python 3.12+ (über Plesk Python-Versionen verfügbar)
- SSH-Zugang zum Server
- Domain oder Subdomain konfiguriert

---

## 📋 Deployment-Schritte

### 1. Projekt hochladen
```bash
# Via SCP/SFTP alle Dateien hochladen nach:
/var/www/vhosts/deine-domain.de/homegym/
```

**Oder via Git:**
```bash
cd /var/www/vhosts/deine-domain.de/
git clone https://dein-repo.git homegym
cd homegym
```

### 2. Python-App in Plesk erstellen
1. In Plesk → Websites & Domains → Domain auswählen
2. "Python" → "Python-Anwendung erstellen"
3. **Python-Version:** 3.12
4. **Anwendungsordner:** `/homegym`
5. **Startdatei:** `config/wsgi.py`
6. **Umgebungsvariablen hinzufügen:**
   - `DJANGO_SETTINGS_MODULE` = `config.settings`
   - `DJANGO_SECRET_KEY` = `[Generieren mit: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"]`

### 3. Virtual Environment einrichten
```bash
cd /var/www/vhosts/deine-domain.de/homegym
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Datenbank vorbereiten (MariaDB)

**MariaDB Setup:**
```bash
# 1. Datenbank in Plesk erstellen:
#    - Datenbanken → Datenbank hinzufügen
#    - Name: homegym_db
#    - Benutzer erstellen mit allen Rechten
#    - Passwort notieren

# 2. MySQL-Client für Python installieren
pip install mysqlclient

# 3. config/settings.py anpassen:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'homegym_db',
        'USER': 'homegym_user',
        'PASSWORD': 'dein_sicheres_passwort',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# 4. Migrations ausführen
python manage.py migrate
python manage.py add_new_exercises  # Neue Übungen hinzufügen
python manage.py createsuperuser
```

**Alternative: SQLite (nur für Tests/Development):**
```bash
python manage.py migrate
python manage.py add_new_exercises
python manage.py createsuperuser
```

### 5. Static Files sammeln
```bash
python manage.py collectstatic --noinput
```

In `config/settings.py`:
```python
STATIC_ROOT = '/var/www/vhosts/deine-domain.de/homegym/staticfiles/'
STATIC_URL = '/static/'

MEDIA_ROOT = '/var/www/vhosts/deine-domain.de/homegym/media/'
MEDIA_URL = '/media/'
```

### 6. Production Settings anpassen
In `config/settings.py`:
```python
DEBUG = False
ALLOWED_HOSTS = ['deine-domain.de', 'www.deine-domain.de']

# Security Settings
SECURE_SSL_REDIRECT = True  # Nur wenn HTTPS aktiv
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

### 7. Nginx/Apache Konfiguration (über Plesk)

**Nginx-Konfiguration für Django App:**

Da bereits Port 8000 (api.last-strawberry.com) und 8001 (last-strawberry.com) belegt sind, verwenden wir **Port 8002** für die HomeGym App.

**Nginx Additional directives für Domain (z.B. homegym.last-strawberry.com):**

```nginx
# Django App auf Port 8002
location / {
    proxy_pass http://127.0.0.1:8002;
    
    # Timeouts für Django
    proxy_connect_timeout 60s;
    proxy_send_timeout    60s;
    proxy_read_timeout    60s;
    send_timeout          60s;
    
    # Proxy Headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    
    # WebSocket Support (für evtl. zukünftige Features)
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# Static Files direkt von Nginx ausliefern (Performance)
location /static/ {
    alias /var/www/vhosts/last-strawberry.com/homegym/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}

# Media Files
location /media/ {
    alias /var/www/vhosts/last-strawberry.com/homegym/media/;
    expires 7d;
    add_header Cache-Control "public";
}
```

**In Plesk eintragen:**
1. Domain auswählen → Apache & nginx Settings
2. "Additional nginx directives" → Obige Config einfügen
3. "OK" klicken

### 8. App starten mit Gunicorn

**Gunicorn installieren und konfigurieren:**
```bash
cd /var/www/vhosts/last-strawberry.com/homegym
source venv/bin/activate
pip install gunicorn

# Gunicorn als Service starten (Port 8002)
gunicorn --bind 127.0.0.1:8002 \
         --workers 3 \
         --timeout 60 \
         --access-logfile /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-access.log \
         --error-logfile /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-error.log \
         --daemon \
         config.wsgi:application
```

**Systemd Service erstellen (empfohlen):**
```bash
sudo nano /etc/systemd/system/homegym.service
```

**Inhalt:**
```ini
[Unit]
Description=HomeGym Django App
After=network.target mariadb.service

[Service]
Type=notify
User=root  # Oder dein Plesk-User
Group=psaserv
WorkingDirectory=/var/www/vhosts/last-strawberry.com/homegym
Environment="PATH=/var/www/vhosts/last-strawberry.com/homegym/venv/bin"
ExecStart=/var/www/vhosts/last-strawberry.com/homegym/venv/bin/gunicorn \
          --bind 127.0.0.1:8002 \
          --workers 3 \
          --timeout 60 \
          --access-logfile /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-access.log \
          --error-logfile /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-error.log \
          config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Service aktivieren:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable homegym
sudo systemctl start homegym
sudo systemctl status homegym
```

**Alternative: Supervisor (falls Systemd nicht verfügbar):**
```bash
pip install supervisor

# Supervisor Config erstellen
sudo nano /etc/supervisor/conf.d/homegym.conf
```

**Inhalt:**
```ini
[program:homegym]
command=/var/www/vhosts/last-strawberry.com/homegym/venv/bin/gunicorn --bind 127.0.0.1:8002 --workers 3 --timeout 60 config.wsgi:application
directory=/var/www/vhosts/last-strawberry.com/homegym
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn.log
```

**Supervisor starten:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start homegym
sudo supervisorctl status homegym
```

### 9. HTTPS einrichten (Let's Encrypt)
In Plesk:
1. SSL/TLS-Zertifikat → Let's Encrypt
2. Domain wählen und "Installieren" klicken
3. Automatische Erneuerung aktivieren

### 10. Erste Schritte nach Deployment
1. Admin-Account erstellen: `python manage.py createsuperuser`
2. In `/admin/` einloggen
3. Ersten User registrieren über `/register/`
4. Login testen über `/accounts/login/`

---

## 🔧 Wartung & Updates

### App neustarten
```bash
# Mit Systemd
sudo systemctl restart homegym

# Mit Supervisor
sudo supervisorctl restart homegym

# Manuell (falls Gunicorn im Daemon-Mode)
pkill -f "gunicorn.*config.wsgi"
cd /var/www/vhosts/last-strawberry.com/homegym
source venv/bin/activate
gunicorn --bind 127.0.0.1:8002 --workers 3 --daemon config.wsgi:application
```

### Logs prüfen
```bash
# Nginx Logs
tail -f /var/www/vhosts/last-strawberry.com/logs/error_log
tail -f /var/www/vhosts/last-strawberry.com/logs/access_log

# Gunicorn Logs
tail -f /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-error.log
tail -f /var/www/vhosts/last-strawberry.com/homegym/logs/gunicorn-access.log

# Systemd Logs
sudo journalctl -u homegym -f
```

### Datenbank-Backup (MariaDB)
```bash
# Backup erstellen
mysqldump -u homegym_user -p homegym_db > backup_$(date +%Y%m%d).sql

# Backup wiederherstellen
mysql -u homegym_user -p homegym_db < backup_20260103.sql

# Automatisches Backup via Cron (täglich um 3 Uhr)
crontab -e
# Folgende Zeile hinzufügen:
0 3 * * * mysqldump -u homegym_user -p'passwort' homegym_db > /backups/homegym_$(date +\%Y\%m\%d).sql
```

### Code-Updates
```bash
cd /var/www/vhosts/last-strawberry.com/homegym
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
python manage.py migrate
python manage.py collectstatic --noinput

# App neustarten
sudo systemctl restart homegym
# ODER
sudo supervisorctl restart homegym
```

---

## 🔒 Sicherheit Checkliste
- [x] `DEBUG = False` in Production
- [x] `DJANGO_SECRET_KEY` als Umgebungsvariable (Plesk) – oder `SECRET_KEY` in .env
- [x] HTTPS aktiviert (Let's Encrypt)
- [x] `ALLOWED_HOSTS` konfiguriert
- [x] Firewall-Regeln (nur 80/443 offen)
- [x] Regelmäßige Backups
- [x] User-Authentifizierung aktiv
- [x] CSRF-Protection aktiviert
- [x] Secure Cookies (HTTPS)

---

## 📞 Troubleshooting

### Problem: 500 Internal Server Error
```bash
# Logs prüfen
tail -f /var/www/vhosts/deine-domain.de/logs/error_log

# Django Debug aktivieren (nur kurz!)
DEBUG = True  # In settings.py
```

### Problem: Static Files nicht geladen
```bash
python manage.py collectstatic --clear
# Webserver-Rechte prüfen:
chown -R username:psaserv staticfiles/
chmod -R 755 staticfiles/
```

### Problem: Datenbank-Verbindungsfehler
```bash
# MariaDB Service prüfen
sudo systemctl status mariadb

# Verbindung testen
mysql -u homegym_user -p homegym_db

# Credentials in config/settings.py prüfen
# User-Rechte prüfen:
mysql -u root -p
GRANT ALL PRIVILEGES ON homegym_db.* TO 'homegym_user'@'localhost';
FLUSH PRIVILEGES;
```

---

## 📚 Nützliche Befehle

```bash
# Migrations erstellen
python manage.py makemigrations

# Migrations ausführen
python manage.py migrate

# Shell öffnen
python manage.py shell

# Custom Command ausführen
python manage.py add_new_exercises

# Testserver lokal
python manage.py runserver 0.0.0.0:8000
```

---

## 🎯 Performance-Optimierungen

1. **Gunicorn mit optimalen Workers:**
```bash
# Formel: (2 x CPU_CORES) + 1
# Für 4 CPU Cores: 9 Workers
gunicorn --workers 9 --bind 127.0.0.1:8002 --timeout 60 config.wsgi:application
```

2. **Redis für Caching & Sessions:**
```bash
# Redis installieren (falls nicht vorhanden)
sudo apt-get install redis-server
pip install redis django-redis

# In config/settings.py:
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Sessions in Redis speichern (schneller als DB)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

3. **MariaDB Optimierungen:**
```sql
-- In /etc/mysql/mariadb.conf.d/50-server.cnf
[mysqld]
innodb_buffer_pool_size = 1G
max_connections = 200
query_cache_size = 64M
query_cache_type = 1
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```

4. **Django Indexes (bereits implementiert):**
```python
# In core/models.py bereits vorhanden:
class Meta:
    indexes = [
        models.Index(fields=['datum']),
        models.Index(fields=['uebung', 'einheit']),
    ]
```

5. **Nginx Caching:**
```nginx
# In nginx.conf oder domain-specific config
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=homegym_cache:10m max_size=100m inactive=60m;

location / {
    proxy_cache homegym_cache;
    proxy_cache_valid 200 60m;
    proxy_cache_bypass $http_cache_control;
    add_header X-Cache-Status $upstream_cache_status;
    
    proxy_pass http://127.0.0.1:8002;
    # ... rest der config
}
```

---

## ✅ Nach erfolgreichem Deployment

- App erreichbar unter: https://homegym.last-strawberry.com (oder deine gewählte Subdomain)
- Admin-Panel: https://homegym.last-strawberry.com/admin/
- Login: https://homegym.last-strawberry.com/accounts/login/
- Registrierung: https://homegym.last-strawberry.com/register/

**Port-Übersicht:**
- Port 8000: api.last-strawberry.com (Uvicorn)
- Port 8001: last-strawberry.com (Backend)
- Port 8002: homegym.last-strawberry.com (Django/Gunicorn) ← **NEU**

**Systemd Service Status prüfen:**
```bash
sudo systemctl status homegym
sudo systemctl status mariadb
sudo systemctl status nginx
```

**Fertig! 🎉**

---

## 🔐 Zusätzliche Sicherheit für MariaDB

```bash
# MariaDB Secure Installation
sudo mysql_secure_installation

# Firewall: Nur localhost-Zugriff auf MariaDB
sudo ufw allow 3306/tcp from 127.0.0.1
sudo ufw deny 3306/tcp

# User-Rechte minimieren
mysql -u root -p
CREATE USER 'homegym_user'@'localhost' IDENTIFIED BY 'sicheres_passwort';
GRANT SELECT, INSERT, UPDATE, DELETE ON homegym_db.* TO 'homegym_user'@'localhost';
FLUSH PRIVILEGES;
```
