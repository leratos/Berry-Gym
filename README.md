# 🏋️ HomeGym - Persönliches Trainingstagebuch

Eine Django-basierte Web-Applikation für HomeGym-Enthusiasten, um Trainings zu tracken, Fortschritte zu analysieren und smarte Trainingspläne zu erstellen.

![Django](https://img.shields.io/badge/Django-5.0.3-green)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Database](https://img.shields.io/badge/Database-MariaDB%20%7C%20SQLite-orange)

---

## ✨ Features

### 📊 Phase 1: Basis-Features (100% ✅)
- **Training Logging**: Sätze, Wiederholungen, Gewicht, RPE
- **Smart Ghosting**: Automatisches Vorausfüllen basierend auf letztem Training
- **Körperwerte**: Gewicht, Körperfett, Muskelmasse mit BMI/FFMI-Berechnung
- **1RM-Tracking**: Progression pro Übung (Epley-Formel)
- **Dashboard**: Trainingsfrequenz, Streak-Counter, Favoriten-Übungen

### 🎯 Phase 2: Trainingspläne & Smart Features (100% ✅)
- **Trainingspläne**: Erstellen, Bearbeiten, Löschen (ohne Admin)
- **Intelligente Empfehlungen**: Bewegungstyp-Balance-Analyse
- **Progressive Overload**: RPE-basierte Gewichtsvorschläge
- **Rest Timer**: Automatischer Countdown nach jedem Satz
- **80 Übungen**: Komplett mit Eigengewicht/Hanteln/Bank

### 📈 Phase 3: Fortgeschrittene Statistiken (100% ✅)
- **Volumen-Progression**: Training-zu-Training Analyse
- **Wöchentliches Volumen**: 4-Wochen-Vergleich
- **Muskelgruppen-Balance**: Horizontale Bar-Charts
- **Trainings-Heatmap**: 90-Tage-Aktivität
- **Performance Form-Index**: 0-100 Score aus Frequenz, RPE, Volumen
- **Ermüdungs-Index**: Deload-Erkennung & Recovery-Management
- **PR-Benachrichtigungen**: Automatische Rekord-Alerts
- **RPE-Statistiken**: Durchschnitt & Trend pro Übung
- **Motivations-Quotes**: Dynamisch basierend auf Performance

### 🔐 User-System
- **Multi-User Support**: Jeder User hat eigene Daten
- **Authentication**: Login, Logout, Registrierung
- **Datenschutz**: Vollständige User-Isolation

---

## 🚀 Quick Start (Development)

### Voraussetzungen
- Python 3.12+
- Git

### Installation
```bash
# Repository klonen
git clone https://dein-repo.git
cd homegym

# Virtual Environment erstellen
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Migrations ausführen
python manage.py migrate

# Übungen hinzufügen
python manage.py add_new_exercises

# Superuser erstellen
python manage.py createsuperuser

# Server starten
python manage.py runserver
```

App läuft auf: **http://127.0.0.1:8000**

---

## 🐳 Production Deployment

Siehe **[DEPLOYMENT.md](DEPLOYMENT.md)** für detaillierte Anweisungen.

### Kurzversion (Linux Server mit Plesk & MariaDB):
```bash
# 1. .env erstellen
cp .env.example .env
# .env anpassen (SECRET_KEY, DB_PASSWORD, ALLOWED_HOSTS)

# 2. Deployment-Script ausführen
chmod +x deploy.sh
./deploy.sh

# 3. Nginx-Konfiguration anpassen (siehe DEPLOYMENT.md)
# 4. Systemd Service erstellen (optional)
```

**Port-Zuordnung:**
- Port 8002: HomeGym Django App

---

## 📁 Projekt-Struktur

```
homegym/
├── config/              # Django-Konfiguration
│   ├── settings.py      # Haupt-Settings (mit .env-Support)
│   ├── urls.py          # URL-Routing
│   └── wsgi.py          # WSGI-Server Config
├── core/                # Haupt-App
│   ├── models.py        # Datenmodelle (Übung, Training, Plan, etc.)
│   ├── views.py         # Business Logic
│   ├── urls.py          # App-URLs
│   ├── admin.py         # Admin-Interface
│   ├── templates/       # HTML-Templates
│   ├── fixtures/        # Initial-Daten (Übungen)
│   └── management/      # Custom Commands
├── db.sqlite3           # SQLite-Datenbank (Development)
├── manage.py            # Django CLI
├── requirements.txt     # Python-Dependencies
├── .env.example         # Umgebungsvariablen-Template
├── deploy.sh            # Deployment-Script
├── DEPLOYMENT.md        # Deployment-Anleitung
└── ROADMAP.md           # Feature-Roadmap
```

---

## 🗄️ Datenbank

### Development: SQLite
Automatisch erstellt bei `python manage.py migrate`.

### Production: MariaDB
```python
# In .env:
DB_ENGINE=django.db.backends.mysql
DB_NAME=homegym_db
DB_USER=homegym_user
DB_PASSWORD=sicheres_passwort
DB_HOST=localhost
DB_PORT=3306
```

---

## 🔧 Nützliche Befehle

```bash
# Migrations
python manage.py makemigrations
python manage.py migrate

# Übungen hinzufügen/aktualisieren
python manage.py add_new_exercises

# Static Files sammeln
python manage.py collectstatic

# Shell öffnen
python manage.py shell

# Testserver
python manage.py runserver 0.0.0.0:8000

# Production Server (Gunicorn)
gunicorn --bind 127.0.0.1:8002 --workers 3 config.wsgi:application
```

---

## 📊 Technologie-Stack

- **Backend**: Django 5.0.3
- **Frontend**: Bootstrap 5.3.3 (Dark Mode)
- **Charts**: Chart.js
- **Database**: MariaDB / SQLite
- **WSGI Server**: Gunicorn
- **Web Server**: Nginx (Reverse Proxy)
- **Deployment**: Plesk, Systemd

---

## 🎯 Roadmap

- ✅ Phase 1: Basis-Features (100%)
- ✅ Phase 2: Trainingspläne & Smart Features (100%)
- ✅ Phase 3: Fortgeschrittene Statistiken (100%)
- ⏳ Phase 4: Ernährung & Lifestyle (0%)
- ⏳ Phase 5: Extended Features (20%)

Details: [ROADMAP.md](ROADMAP.md)

---

## 🤝 Beitragen

Contributions sind willkommen! Bitte erstelle einen Pull Request oder öffne ein Issue.

---

## 📝 Lizenz

[Deine Lizenz hier]

---

## 👤 Autor

Dein Name

---

## 🙏 Danksagungen

- Django Community
- Bootstrap Team
- Chart.js Contributors

---

**Viel Erfolg beim Training! 💪🏋️**
