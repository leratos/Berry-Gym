# 🏋️ HomeGym - Projekt Status & Features

**Stand:** 04.01.2026  
**Version:** 0.3.0  
**Status:** ✅ **PRODUKTIV** (Live auf gym.last-strawberry.com)

---

## 📊 Projekt-Überblick

| Aspekt | Status | Details |
|--------|--------|---------|
| **Entwicklungs-Phase** | Phase 3.5 | 85% aller geplanten Features |
| **Deployment** | ✅ Live | Plesk Server, MariaDB, Gunicorn, Nginx |
| **Testing** | ✅ Manuell getestet | Alle Core-Features validiert |
| **Dokumentation** | ✅ Komplett | README, DEPLOYMENT, ROADMAP |
| **PWA Support** | ✅ Aktiv | Manifest.json, Service Worker |
| **Performance** | ✅ Optimiert | 4 Gunicorn Worker, Redis-ready |

---

## 🎯 Kernfeatures (Implementiert)

### 🏃 Training Management
- ✅ **Training starten** (frei oder nach Plan)
- ✅ **Sätze erfassen** (Gewicht, Wdh, RPE, Notizen)
- ✅ **Smart Ghosting** (letzte Werte auto-ausfüllen)
- ✅ **Aufwärmsätze** (separat markieren)
- ✅ **Training beenden** (Dauer, Kommentar speichern)
- ✅ **Trainingshistorie** (Übersicht + Details)
- ✅ **Training löschen** (mit Bestätigung)

### 📋 Trainingspläne
- ✅ **Plan erstellen** (User-Interface, keine Admin nötig)
- ✅ **Plan bearbeiten/löschen** (volle Kontrolle)
- ✅ **Übungsauswahl** (mit Muskelgruppen-Filter)
- ✅ **Reihenfolge-Editor** (Drag & Drop Buttons)
- ✅ **Sätze/Wdh-Vorgaben** (pro Übung anpassbar)
- ✅ **Plan-Historie** (letztes Gewicht/Wdh anzeigen)
- ✅ **Plan-Beschreibung** (Notizen hinzufügen)

### 💪 Übungen Management
- ✅ **98 vordefinierte Übungen** (alle Muskelgruppen)
- ✅ **Muskelgruppen-Zuordnung** (Haupt + Hilfsmuskeln)
- ✅ **Übungs-Details** (Name, Bewegungstyp, Gewicht)
- ✅ **Favoriten-System** (★ Übungen markieren)
- ✅ **Übungs-Suche** (schnelle Filterung)
- ✅ **Hilfsmuskeln-Parsing** (String zu List konvertiert)

### 📊 Statistiken & Tracking
- ✅ **1RM Progression** (Epley-Formel)
- ✅ **Personal Records** (schwerster Satz, 1RM Max)
- ✅ **Trainingsvolumen** (kg × Wdh berechnet)
- ✅ **Chart.js Visualisierung** (4 verschiedene Diagramme)
- ✅ **Trainingshistorie Charts** (Volumen über Zeit)
- ✅ **Dashboard Metriken:**
  - Trainingsfrequenz diese Woche
  - Streak Counter (aufeinanderfolgende Wochen)
  - Top 3 Favoriten-Übungen
  - Form-Index (0-100 Score)

### 📈 Körperwerte Tracking
- ✅ **Mehrere Metriken** (Gewicht, Größe, Körperfett, Muskelmasse)
- ✅ **BMI & FFMI Berechnung** (automatisch)
- ✅ **4-Chart Dashboard** (Gewicht, BMI, KFA, Muskeln)
- ✅ **Body Stats Tabelle** (Verlauf mit Datum)
- ✅ **Werte bearbeiten/löschen** (volle Kontrolle)

### 🎨 Visualisierung
- ✅ **Interaktive Muscle Map** (klickbar, responsive)
- ✅ **Übungs-Detail SVG** (Haupt/Hilfsmuskel unterschiedlich)
- ✅ **Color-Coding System:**
  - 🟥 Rot = Hauptmuskel
  - 🟦 Blau = Hilfsmuskel
  - ⬜ Grau = Inaktiv
- ✅ **Hover-Effekte** (visuelles Feedback)
- ✅ **Intensitäts-Färbung** (basierend auf Volumen)
- ✅ **Responsive Design** (Mobile-First)

### ⏱️ Training-Features
- ✅ **Rest Timer** (60s / 90s / 120s / 180s auswählbar)
- ✅ **Timer UI** (zirkuläre Anzeige mit Countdown)
- ✅ **Auto-Farben** (Gelb → Rot bei Countdown)
- ✅ **Timer-Sound** (Web Audio API, 3-Ton Melodie)
- ✅ **Countdown-Beeps** (bei letzten 3 Sekunden)
- ✅ **Vibration-Feedback** (wenn verfügbar)
- ✅ **Nicht-blockierende Notification** (mit Auto-Dismiss)
- ✅ **Timer-Persistenz** (LocalStorage)

### 🧠 Smart Features
- ✅ **Progressive Overload System:**
  - RPE-basierte Progression (RPE <7 → +2.5kg)
  - Wiederholungs-Strategie (12+ Wdh → mehr Gewicht)
  - UI-Hinweise mit konkreten Tipps
  - Vergleich mit letztem Training
- ✅ **Intelligente Gewichtsvorschläge**
- ✅ **Performance Form-Index** (Auswertung: Freq, Streak, RPE, Volumen)

### 🔐 Security & Auth
- ✅ **User-Authentifizierung** (Django auth)
- ✅ **Login/Logout** (mit Session-Management)
- ✅ **Passwort-Reset** (Email-basiert)
- ✅ **Admin-Interface** (für Übungen, Benutzer)
- ✅ **Registrierung DEAKTIVIERT** (nur Admin kann Nutzer anlegen)
- ✅ **Per-User Data Isolation** (nur eigene Daten sichtbar)

### 📱 PWA & Mobile
- ✅ **Web App Manifest** (installierbar auf Android)
- ✅ **Service Worker** (offline-Caching)
- ✅ **Responsive CSS** (Bootstrap 5)
- ✅ **Dark Mode** (Standard, Toggle möglich)
- ✅ **Touch-optimierte UI** (große Buttons, Swipe-ready)
- ✅ **Icons generiert** (192x192, 512x512, maskable)

### 🌐 Deployment
- ✅ **Systemd Service** (Autostart, Restart-Policy)
- ✅ **Gunicorn WSGI** (4 Worker, Unix Socket)
- ✅ **Nginx Reverse Proxy** (Plesk-kompatibel)
- ✅ **MariaDB Integration** (Production Database)
- ✅ **Static Files** (collectstatic, Caching-Header)
- ✅ **Media Files** (User-Uploads Verzeichnis)
- ✅ **SSL/HTTPS** (via Plesk Let's Encrypt)
- ✅ **Database Export/Import** (JSON-basiert)

### 📊 Export & Reporting
- ✅ **CSV Export** (Trainingshistorie)
- ✅ **JSON Backup** (komplette DB-Migration)
- ✅ **Trainings-Statistik Export** (auswählbar)

---

## 📁 Projekt-Struktur

```
Fitness/
├── config/                          # Django-Konfiguration
│   ├── settings.py                  # Haupteinstellungen (mit .env-Support)
│   ├── urls.py                      # URL-Routing
│   ├── asgi.py                      # ASGI-Config
│   └── wsgi.py                      # WSGI-Server-Config
│
├── core/                            # Haupt-App
│   ├── models.py                    # Datenmodelle (80+ Zeilen)
│   │   ├── Uebung                   # Übungen (98 Einträge)
│   │   ├── Trainingseinheit         # Training-Sessions
│   │   ├── Satz                     # Individual Sets
│   │   ├── Plan                     # Training Plans
│   │   ├── PlanUebung               # Plan-Exercise Relation
│   │   └── KoerperWerte             # Body Metrics
│   │
│   ├── views.py                     # Business Logic (1415 Zeilen)
│   │   ├── Authentication           # Login/Register
│   │   ├── Dashboard                # Main Overview
│   │   ├── Training                 # Training Management
│   │   ├── Plans                    # Plan CRUD
│   │   ├── Exercises                # Exercise Management
│   │   ├── Statistics               # Analytics
│   │   └── Body Stats               # Metrics Tracking
│   │
│   ├── urls.py                      # App URL Routes (37 URLs)
│   ├── admin.py                     # Admin Interface
│   ├── apps.py                      # App Config
│   │
│   ├── templates/                   # HTML-Templates
│   │   ├── registration/
│   │   │   ├── login.html           # Login Page
│   │   │   └── register.html        # Register (DEAKTIVIERT)
│   │   └── core/
│   │       ├── dashboard.html       # Main Dashboard
│   │       ├── training_*.html      # Training Pages (5)
│   │       ├── plan_*.html          # Plan Pages (3)
│   │       ├── body_stats.html      # Metrics Pages (4)
│   │       ├── muscle_map.html      # Interactive Map
│   │       ├── uebung_detail.html   # Exercise Detail + SVG
│   │       └── training_finish.html # Summary Screen
│   │
│   ├── static/
│   │   └── core/
│   │       ├── manifest.json        # PWA Manifest
│   │       ├── service-worker.js    # Offline Support
│   │       └── images/
│   │           ├── icon-192x192.png # App Icon
│   │           ├── icon-512x512.png
│   │           └── icon-maskable.png
│   │
│   ├── fixtures/
│   │   └── initial_exercises.json   # 98 vordefinierte Übungen
│   │
│   └── management/commands/
│       └── add_new_exercises.py     # Data Import Script
│
├── logs/                            # Gunicorn Logs
├── media/                           # User Uploads
├── staticfiles/                     # Collected Static Files
│
├── requirements.txt                 # Python Dependencies
├── manage.py                        # Django CLI
├── .env.example                     # Environment Template
├── .env                             # Production Settings (server only)
├── .gitignore                       # Git Exclusions
│
├── README.md                        # Feature Overview
├── ROADMAP.md                       # Development Roadmap
├── DEPLOYMENT.md                    # Server Setup Guide
├── DEPLOY_QUICKSTART.md             # Quick Deployment
├── PROJECT_STATUS.md                # This File
│
├── db.sqlite3                       # Dev Database
├── homegym.service                  # Systemd Unit File
├── homegym.nginx                    # Nginx Configuration
├── deploy.sh                        # Deployment Script
├── export_db.py                     # DB Export Tool
├── import_db.py                     # DB Import Tool
├── generate_secret_key.py           # Key Generator
├── fix_hilfsmuskeln.py              # Data Cleanup Tool
│
└── homegym_backup_*.json            # Database Backups
```

---

## 💾 Datenbank-Schema

### Hauptmodelle

**Uebung** (Exercises)
- 98 vordefinierte Übungen
- Felder: bezeichnung, muskelgruppe, bewegungstyp, hilfsmuskeln (JSON), gewichts_typ
- Relations: ← Satz, ← PlanUebung, ← Favorit

**Trainingseinheit** (Training Sessions)
- Felder: user, datum, dauer_minuten, kommentar
- Relations: → Satz (1:M)

**Satz** (Sets)
- Felder: einheit, uebung, gewicht, wiederholungen, rpe, ist_aufwaermsatz, notiz
- Relations: ← Trainingseinheit

**Plan** (Training Plans)
- Felder: user, name, beschreibung, erstellt_am
- Relations: → PlanUebung (1:M)

**PlanUebung** (Plan Exercises)
- Felder: plan, uebung, reihenfolge, saetze_ziel, wiederholungen_ziel
- Relations: ← Plan, ← Uebung

**KoerperWerte** (Body Metrics)
- Felder: gewicht_kg, hoehe_cm, koerperfett_prozent, muskelmasse_kg, datum
- Berechnete: BMI, FFMI

---

## 🔧 Technologie-Stack

| Layer | Technologie | Version |
|-------|------------|---------|
| **Backend** | Django | 5.0.3 |
| **Database** | MariaDB | Latest |
| **Cache** | Redis | (optional) |
| **Server** | Gunicorn | 22.0.0 |
| **Web** | Nginx | Plesk-managed |
| **Frontend** | Bootstrap | 5.3.3 |
| **Charts** | Chart.js | 3.x |
| **Icons** | Bootstrap Icons | 1.11.3 |
| **PWA** | Service Worker | Native |
| **OS** | Linux (Debian) | - |
| **Python** | 3.12 | - |

### Dependencies
```
Django==5.0.3
gunicorn==22.0.0
mysqlclient==2.2.4
Pillow==12.1.0
python-dotenv==1.0.1
(redis==5.0.1)  # Optional
(django-redis==5.4.0)  # Optional
```

---

## 🚀 Deployment Status

### ✅ Server-Setup (Complete)
- Domain: `gym.last-strawberry.com`
- Server: Plesk-managed (last-strawberry.com)
- Path: `/var/www/vhosts/last-strawberry.com/gym.last-strawberry.com`
- User: `lera:psaserv` (Plesk user)
- SSL: ✅ Let's Encrypt (auto-renewed)
- Database: MariaDB `gym_` (user: `fit`)

### ✅ App-Status
- Service: Active (running)
- Gunicorn: 4 workers, Unix socket binding
- Nginx: Plesk-configured with custom directives
- Database: 98 exercises + 1 user + 2 plans imported
- Static Files: Collected & cached

### ✅ Features Active
- User authentication (working)
- Dashboard (fully functional)
- Training logging (tested)
- Plans & exercises (98 available)
- Statistiken (all calculated)
- Timer with sounds (tested)
- PWA installation (banner shown)

---

## 🎨 Frontend-Features

### Pages (13 Templates)

1. **login.html** - Login
2. **register.html** - Register (DISABLED)
3. **dashboard.html** - Home with stats
4. **training_select_plan.html** - Plan selection
5. **training_session.html** - Main training page
6. **training_list.html** - History view
7. **training_stats.html** - Analytics
8. **training_finish.html** - Summary screen
9. **plan_details.html** - Plan overview
10. **create_plan.html** - Plan builder
11. **edit_plan.html** - Plan editor
12. **body_stats.html** - Metrics dashboard
13. **muscle_map.html** - Interactive anatomy
14. **uebung_detail.html** - Exercise detail + SVG
15. **uebungen_auswahl.html** - Exercise list
16. (+ registration/login.html, register.html)

### Components
- Dark mode (Bootstrap data-bs-theme="dark")
- Modal dialogs (for exercises, confirmations)
- Progress indicators (set counters)
- Form validation (Bootstrap)
- SVG anatomy visualization
- Chart.js graphs
- Responsive cards & grids

---

## 📈 Performance & Optimization

### Implemented
- ✅ Gunicorn worker processes (4x)
- ✅ Database connection pooling
- ✅ Static file caching (Nginx headers)
- ✅ Service Worker for PWA (offline)
- ✅ LocalStorage (Timer state)
- ✅ Lazy loading (images, charts)
- ✅ CSS minification (Bootstrap CDN)
- ✅ JSON fixture loading (initial data)

### Monitoring
- Systemd logs: `journalctl -xeu homegym.service`
- Gunicorn access/error logs: `/logs/`
- Nginx access logs: Plesk panel

---

## 🐛 Bekannte Issues & Fixes

| Issue | Status | Lösung |
|-------|--------|--------|
| Hilfsmuskeln als String statt List | ✅ Fixed | `fix_hilfsmuskeln.py` Script |
| SVG-Anzeige bei Detail-View | ✅ Works | Fetch-basiert, responsive |
| Timer-Sound in PWA | ✅ Works | Web Audio API (offline-compatible) |
| DB-Import SQLite Fallback | ✅ Fixed | .env.backup_temp Handling |
| Registrierung auf Production | ✅ Fixed | Route disabled |

---

## 🔐 Security-Checks

- ✅ SECRET_KEY gespeichert (nicht im Code)
- ✅ DEBUG=False auf Server
- ✅ ALLOWED_HOSTS konfiguriert
- ✅ CSRF-Protection aktiv
- ✅ SQL-Injection Prevention (ORM)
- ✅ XSS-Protection (Template escaping)
- ✅ User Permissions (login_required)
- ✅ Per-User Data Isolation (queryset filtering)
- ✅ HTTPS enforced (Let's Encrypt)
- ✅ Password hashing (Django auth)

---

## 📋 Checkliste für Zukünftige Features

### Quick Wins (Recommended)
- [ ] Sound-Einstellungen (Volume, On/Off)
- [ ] PR-Benachrichtigungen (Toast alerts)
- [ ] Trainings-Kalender/Heatmap
- [ ] Fortschrittsfotos (Before/After)
- [ ] Superset/Circuit Support
- [ ] Exportieren als PDF

### Mittlere Priorität
- [ ] Ernährungstracking (basic)
- [ ] Rest-Day Recommendations
- [ ] Social Sharing (Stats)
- [ ] Dark/Light Mode Toggle
- [ ] Multiple Languages (i18n)

### Längerfristig
- [ ] Workout Recommendations (ML)
- [ ] Community Features
- [ ] Sync across devices
- [ ] Wearable Integration
- [ ] Mobile App (React Native)

---

## 📞 Administration

### User Management
```bash
# Superuser erstellen
python manage.py createsuperuser

# User ändern (Shell)
python manage.py shell
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='lera')
>>> user.set_password('new_pass')
>>> user.save()
```

### Database
```bash
# Backup
python export_db.py

# Restore
python import_db.py backup_file.json

# Migrations
python manage.py makemigrations
python manage.py migrate
```

### Service Management
```bash
# Status
sudo systemctl status homegym

# Restart
sudo systemctl restart homegym

# Logs
sudo journalctl -xeu homegym.service -n 100
tail -f logs/gunicorn-error.log
```

---

## 📞 Support & Kontakt

- **Entwicklung**: Lokal in VS Code
- **Server**: Plesk (last-strawberry.com)
- **Backup**: tägliche Exports
- **Updates**: via deploy.sh Script
- **Dokumentation**: README.md, DEPLOYMENT.md, ROADMAP.md

---

## 📊 Statistik

| Metrik | Wert |
|--------|------|
| **Python Zeilen** | ~3500 |
| **HTML-Templates** | 16 |
| **Database Tables** | 6 |
| **API Endpoints** | 37 URLs |
| **Übungen** | 98 Stück |
| **Muskelgruppen** | 22 |
| **Views/Functions** | 30+ |
| **Models/Classes** | 6 |

---

**Zuletzt aktualisiert:** 04.01.2026  
**Maintainer:** lera  
**License:** MIT (optional)
