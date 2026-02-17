# 🏋️ HomeGym - AI-Powered Fitness Tracker

<div align="center">

![Django](https://img.shields.io/badge/Django-5.1.15-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square)
![Database](https://img.shields.io/badge/Database-MariaDB%20%7C%20SQLite-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)
![Version](https://img.shields.io/badge/Version-0.9.1-brightgreen?style=flat-square)
![PWA](https://img.shields.io/badge/PWA-Ready-purple?style=flat-square)

![CI/CD](https://github.com/leratos/Berry-Gym/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/leratos/Berry-Gym/branch/main/graph/badge.svg)](https://codecov.io/gh/leratos/Berry-Gym)

**Ein intelligentes Trainingstagebuch für HomeGym-Enthusiasten mit KI-gestütztem Coach, 1RM Kraftstandards, Advanced Analytics & AI Performance-Analyse**

🌐 **[Live Demo & Beta Testing](https://gym.last-strawberry.com)** 🌐

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Roadmap](#-roadmap--known-limitations) • [Contributing](#-contributing)

</div>

---

## 📖 Über dieses Projekt

HomeGym ist eine Django-basierte Web-Applikation, die Krafttraining tracking mit künstlicher Intelligenz kombiniert. Die App ermöglicht detailliertes Logging von Trainingseinheiten, analysiert Fortschritte mit evidenzbasierten Metriken und bietet einen **KI-Coach**, der automatisch Trainingspläne erstellt und optimiert.

### 🎯 Hauptziele

- **Vollständige Privatsphäre**: Deine Trainingsdaten bleiben auf deinem Server
- **KI ohne Cloud**: Lokale LLMs (Ollama) für 0€ Betriebskosten
- **Smart Tracking**: Automatisches Ghosting, RPE-basierte Gewichtsvorschläge, Superset-Support
- **Performance-Fokus**: 1RM Tracking, Volumen-Analyse, Plateau-Erkennung
- **Professionelle Reports**: Anatomische Body-Maps mit dynamischer Farbcodierung

---

## ✨ Features

### 📊 Core Training Features

- **Smart Training Logging**
  - Sätze, Wiederholungen, Gewicht, RPE (Rate of Perceived Exertion)
  - Automatisches Ghosting: Vorschläge basierend auf letztem Training
  - Aufwärmsätze separat markieren
  - **Superset-Support**: Gruppiere bis zu 5 Übungen (S1-S5) mit farbiger Visualisierung
  - Notizen pro Satz für detailliertes Tracking
  - **Undo-Funktion**: Gelöschte Sätze innerhalb 5 Sekunden wiederherstellen (v0.7.7)
  - **Keyboard-Shortcuts**: Enter=Save, Esc=Close, N=New Set, S=Add Set (v0.7.7)
  - **Übungssuche mit Autocomplete**: Fuzzy-Matching & Score-basiertes Ranking (v0.7.7)
  - **Training fortsetzen**: Gelber "Fortsetzen"-Button im Dashboard bei offener (nicht abgeschlossener) Session – direkt zurück zum laufenden Training ohne Navigation (v0.9.1)
  - Bei mehreren vergessenen Sessions: Warnung mit Link zur History zum Aufräumen

- **Custom Übungen erstellen** (v0.7.8)
  - Eigene Übungen definieren mit Muskelgruppe, Bewegungstyp & Equipment
  - User-spezifisch: Nur du siehst deine Custom-Übungen
  - Vollständige Integration in Training & Pläne
  - Custom-Badge zur Unterscheidung von globalen Übungen

- **Übungs-Video-Anleitungen** (v0.8.0)
  - Video-Links für Übungen (YouTube & Vimeo Support)
  - Responsive Video-Player im Exercise Info Modal
  - Automatische Konvertierung zu Embed-Format
  - Formcheck-Videos direkt beim Training verfügbar

- **Körperwerte & Statistiken**
  - Gewicht, Körperfettanteil, Muskelmasse tracking
  - BMI & FFMI Berechnung
  - Progress Photos (optional)
  - Langzeit-Trend-Analysen

- **Cardio-Tracking (Lite)** (v0.8.0)
  - Schnelles Erfassen von Cardio ohne Trainingsplan
  - 9 Aktivitäten: Schwimmen, Laufen, Radfahren, Rudern, Gehen, HIIT, Stepper, Seilspringen, Sonstiges
  - 3 Intensitätsstufen mit Ermüdungspunkten (Leicht: 0.1/Min, Moderat: 0.2/Min, Intensiv: 0.4/Min)
  - Automatische Integration in Ermüdungsindex (max. 20 Punkte bei 120+ Fatigue)
  - Dashboard-Statistiken (Einheiten & Minuten pro Woche)
  - Cardio-Liste mit Lösch-Funktion

- **1RM Tracking & PRs**
  - Automatische 1RM Berechnung (Epley-Formel)
  - Personal Records mit Benachrichtigungen
  - Progressions-Charts pro Übung
  - Plateau-Erkennung (4+ Wochen Stagnation)
  - **Alternative Übungen**: Intelligentes Matching nach Bewegungstyp & Muskelgruppe (v0.7.8)
  - **1RM Kraftstandards** (v0.9.0): 4 Leistungsstufen pro Übung (Anfänger → Elite), körpergewicht-skaliert
  - **6-Monats 1RM-Entwicklung** mit Fortschrittsbalken zum nächsten Level

### 🤖 AI Coach Features

#### 1. **AI Performance-Analyse** (v0.7.8)

**Dashboard Widget - Top 3 Warnungen:**
- **Plateau-Erkennung**: Session-basierter Vergleich (letzte 2 Wochen vs. Wochen 2-4)
- **Rückschritt-Erkennung**: >15% Leistungsabfall erkannt
- **Stagnation-Erkennung**: Muskelgruppen >14 Tage nicht trainiert
- Automatische Verbesserungsvorschläge (Drop-Sets, Volumen-Erhöhung, etc.)

**Training Counter - Jedes 3. Training:**
- Automatischer Optimierungsvorschlag nach Trainingsabschluss
- **Intensitätsanalyse**: RPE zu niedrig (<6.5) oder zu hoch (>8.5)
- **Volumen-Trend**: ±15% Veränderung erkannt
- **Übungsvielfalt**: Warnung bei <5 verschiedenen Übungen
- Priorisierung nach Severity (Danger → Warning → Info)

#### 2. **Automatische Plan-Generierung** (~0.003€ pro Plan)
```bash
python ai_coach/plan_generator.py --user-id 1
```
- LLM analysiert deine Training-Historie
- Berücksichtigt dein Equipment (Hanteln, Bank, Klimmzugstange, etc.)
- Erstellt personalisierten Split (2-6 Trainingstage/Woche)
- Balanced Push/Pull/Legs Aufteilung
- Science-based Volumen-Empfehlungen

#### 3. **Automatische Plan-Optimierung** (Hybrid: Regelbasiert + KI)

**Stufe 1 - Kostenlos (Regelbasierte Checks):**
- RPE-Analyse: Warnt bei zu niedrig (<7) oder zu hoch (>8.5)
- Muskelgruppen-Balance: Erkennt vernachlässigte Muskelgruppen
- Plateau-Erkennung: Identifiziert stagnierende Übungen
- Volumen-Trends: Warnt bei plötzlichen Spikes oder Drops

**Stufe 2 - KI-Optimierung (~0.003€):**
- LLM schlägt konkrete Änderungen vor
- Übungs-Ersatz (nur aus deinem Equipment-Bestand)
- Volumen-Anpassungen (Sets/Reps)
- Diff-View: Vorher/Nachher mit Begründungen
- Apply-Funktionalität: Änderungen mit 1 Klick übernehmen

#### 4. **Live Training Guidance** (~0.002€ pro Chat)
- Echtzeit-Formcheck-Tipps
- Technique-Verbesserungsvorschläge
- Progressive Overload Beratung
- Context-aware: Kennt deinen aktuellen Trainingsstand

### 📈 Erweiterte Statistiken

- **Volumen-Progression**: Training-zu-Training Vergleich
- **Wöchentliches Volumen**: 4-Wochen Rolling Average
- **Muskelgruppen-Balance**: Horizontale Bar-Charts
- **Trainings-Heatmap**: 90-Tage Aktivitätsmatrix
- **Performance Form-Index**: 0-100 Score (Frequenz + RPE + Volumen)
- **Ermüdungs-Index**: Automatische Deload-Empfehlungen
- **RPE-Statistiken**: Durchschnitt & Trend pro Übung
- **Plateau-Analyse** (v0.9.0): 5-stufige Progressions-Erkennung mit Regression-Detection
- **Konsistenz-Metriken** (v0.9.0): Streak-Tracking, Adherence-Rate, Trainings-Regelmäßigkeit
- **RPE-Qualitätsanalyse** (v0.9.0): Junk Volume & optimale Intensität erkennen
- **1RM Kraftstandards** (v0.9.0): Leistungsbewertung gegen evidenzbasierte Standards
- **CSV-Export** (v0.9.0): Alle Trainingsdaten als Download für Excel/Sheets

### � Professional PDF Reports

**Professioneller Trainingsreport (7+ Seiten)** mit xhtml2pdf:

#### Aufbau:
1. **Cover Page** mit anatomischer Body-Map
2. **Table of Contents**
3. **Executive Summary** mit Kerndaten & Data-Quality-Warnings
4. **Muskelgruppen-Analyse** mit Status-Badges & Erklärungen
5. **Push/Pull Balance** mit Pie-Chart & Empfehlungen
6. **Training Progress** (Top-5 Kraftzuwächse)
7. **Trainer Recommendations** (Stärken, Schwächen, Next Steps)
8. **Plateau-Analyse** mit 5-stufiger Progressions-Bewertung (v0.9.0)
9. **Konsistenz-Metriken** mit Streak & Adherence-Rate (v0.9.0)
10. **Ermüdungs-Index** mit Deload-Empfehlungen (v0.9.0)
11. **1RM Kraftstandards** mit Leistungsstufen-Vergleich (v0.9.0)
12. **RPE-Qualitätsanalyse** mit Intensitäts-Bewertung (v0.9.0)

#### Features:
- **Anatomische Body-Map** (SVG → PNG via cairosvg):
  - 1100x1024px Front + Back View
  - 19 Muskelgruppen dynamisch eingefärbt:
    - 🟢 **Grün**: Optimal trainiert (80-120% des Ziels)
    - 🟡 **Gelb**: Untertrainiert (< 80%)
    - 🔴 **Rot**: Übertrainiert (> 120%)
  - PIL-Fallback für Systeme ohne Cairo
  
- **Data Quality Checks**:
  - Warnung bei < 8 Trainingseinheiten
  - Weiche Formulierungen ("erste Eindrücke" statt harter Aussagen)
  - Konservative Empfehlungen bei wenig Daten
  
- **Advanced Charts** (matplotlib):
  - Muskelgruppen-Heatmap (horizontal bars)
  - Volumen-Entwicklung (line chart mit area fill)
  - Push/Pull Pie-Chart (korrekte Muskelgruppen-Zuordnung)
  
- **Professional Layout**:
  - CSS2.1-kompatibel für xhtml2pdf
  - Page-break Kontrolle (Grafik + Titel auf selber Seite)
  - 16px Legenden-Font
  - Border-less chart headers

**Technologie-Stack**: xhtml2pdf, matplotlib (Agg backend), cairosvg, Pillow, scikit-learn (ML-Modelle)

### 📚 Plan-Sharing & Bibliothek

- **Plan duplizieren**: Eigene Pläne oder Gruppen als Kopie erstellen
- **Plan teilen**: 
  - QR-Code für mobiles Scannen
  - Direkter Link zum Kopieren
  - Social-Sharing (WhatsApp, Telegram, E-Mail)
- **Öffentliche Plan-Bibliothek** (`/plan-library/`):
  - Durchsuchbare Sammlung aller öffentlichen Pläne
  - Gruppierte Anzeige von Split-Plänen
  - 1-Klick Kopieren in eigene Sammlung
- **Plan-Gruppen Management**:
  - Gruppen umbenennen & sortieren
  - Öffentlich/Privat Toggle
  - Gruppierung aufheben oder löschen

### 🔐 User Management

- Multi-User Support mit vollständiger Datenisolation
- Django Authentication (Login, Logout, Registration)
- User-spezifische Trainingspläne und Historie
- Equipment-Profil pro User

### 📱 Progressive Web App (PWA)

- Installierbar auf Smartphone/Desktop
- Offline-fähig (Service Worker)
- Native App-Experience
- Push-Benachrichtigungen (optional)

---

## 🚀 Installation

### Voraussetzungen

- **Python 3.12+**
- **Git**
- **Optional (für AI Coach):** [Ollama](https://ollama.ai/) mit llama3.1:8b Modell

### Quick Start (Development)

```bash
# 1. Repository klonen
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# 2. Virtual Environment erstellen
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Environment Variables setzen
cp .env.example .env
# Wichtig: .env bearbeiten und mindestens SECRET_KEY setzen
# Für Production: DEBUG=False, ALLOWED_HOSTS anpassen

# 5. Datenbank initialisieren
python manage.py migrate

# 6. Übungen hinzufügen (113 vordefinierte Übungen)
python manage.py loaddata core/fixtures/initial_exercises.json

# 7. Superuser erstellen
python manage.py createsuperuser

# 8. Static Files sammeln (für Production)
python manage.py collectstatic

# 9. Development Server starten
python manage.py runserver
```

App läuft auf **http://127.0.0.1:8000**

### Environment Variables (.env)

Erstelle eine `.env` Datei im Root-Verzeichnis:

```env
# Django Core
SECRET_KEY=your-secret-key-here  # WICHTIG: Generiere mit: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=True  # False für Production!
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Optional - Standard ist SQLite)
# DATABASE_ENGINE=django.db.backends.mysql
# DATABASE_NAME=homegym
# DATABASE_USER=your_user
# DATABASE_PASSWORD=your_password
# DATABASE_HOST=localhost
# DATABASE_PORT=3306

# AI Coach (Optional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
USE_OPENROUTER_FALLBACK=False

# Security (Production)
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True
```

**Wichtig für Production:**
- `SECRET_KEY` muss unique und sicher sein
- `DEBUG=False` setzen
- `ALLOWED_HOSTS` mit deiner Domain setzen
- SSL/HTTPS aktivieren

### Ollama Setup (für AI Coach)

```bash
# 1. Ollama installieren (https://ollama.ai/)

# 2. Llama 3.1 8B Modell downloaden
ollama pull llama3.1:8b

# 3. Server starten (läuft auf http://localhost:11434)
ollama serve

# 4. In .env konfigurieren
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Alternative: OpenRouter (Cloud LLM)**
```bash
# 1. API Key bei OpenRouter holen (https://openrouter.ai/)

# 2. Secure speichern mit secrets_manager
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx

# 3. In .env aktivieren
USE_OPENROUTER_FALLBACK=True
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct
```

### Troubleshooting

**Problem: Datenbank-Fehler beim Start**
```bash
# Lösung: Migrationen zurücksetzen und neu anlegen
python manage.py migrate --run-syncdb
```

**Problem: "No such table: core_uebung"**
```bash
# Lösung: Fixtures laden
python manage.py loaddata core/fixtures/initial_exercises.json
```

**Problem: Static Files werden nicht geladen**
```bash
# Lösung: Static Files sammeln
python manage.py collectstatic --noinput
```

**Problem: AI Coach funktioniert nicht**
```bash
# Lösung: Ollama prüfen
curl http://localhost:11434/api/tags
# Oder OpenRouter API Key prüfen
python ai_coach/secrets_manager.py get OPENROUTER_API_KEY
```

---

## 📱 Screenshots

### Dashboard
- Training-Heatmap (90 Tage)
- Performance Form-Index (0-100)
- AI Performance-Warnungen (Plateau, Rückschritt, Stagnation)
- Streak Counter & Wochenstatistiken
- **"Fortsetzen"-Button** bei offener Training-Session (v0.9.1)

### Training Session
- Übungssuche mit Autocomplete
- Satz-Logging mit RPE-Slider
- Undo-Funktion für gelöschte Sätze
- Keyboard-Shortcuts (Enter/Esc/N/S)
- Superset-Gruppierung (S1-S5)

### Exercise Detail
- 1RM Progression Chart
- RPE-Analyse & Trend
- Alternative Übungen (Modal mit Score-Ranking)
- Personal Records

### AI Coach
- Dashboard Performance-Widget (Top 3 Warnungen)
- Training Counter (jedes 3. Training)
- Plan-Optimierung mit Diff-View
- Live Guidance Chat

---

## 📚 Usage

### Training erstellen

1. **Dashboard** → "Training starten"
2. Wähle "Freies Training" oder einen Plan
3. Füge Übungen hinzu (Filter nach Muskelgruppe)
4. Logge Sätze: Gewicht, Wiederholungen, RPE (1-10)
5. Training beenden → Automatische Volumen-Berechnung

### Trainingsplan erstellen

1. **Pläne** → "Neuer Plan"
2. Übungen hinzufügen (mit Sätze/Wdh-Vorgaben)
3. Reihenfolge anpassen
4. Speichern → Plan ist sofort nutzbar

### AI Coach nutzen

**Plan generieren:**
```bash
python ai_coach/plan_generator.py --user-id 1 --days-per-week 4
```

**Plan optimieren (CLI):**
```bash
python ai_coach/plan_adapter.py --plan-id 3 --user-id 1 --optimize
```

**Plan optimieren (Web):**
1. Plan bearbeiten → "Performance-Analyse"
2. Review Warnings (kostenlos)
3. "KI-Optimierung starten" (0.003€)
4. Diff-View: Änderungen reviewen
5. Checkbox-Selektion → "Übernehmen"

**Live Guidance (Web):**
1. Training starten
2. "AI Coach" Button
3. Chat-Interface mit Echtzeit-Tipps

---

## 🗂️ Projekt-Struktur

```
Fitness/
├── ai_coach/                   # KI-Coach Module
│   ├── plan_generator.py       # Automatische Plan-Generierung
│   ├── plan_adapter.py         # Plan-Optimierung & Analyse
│   ├── live_guidance.py        # Live Training Guidance
│   ├── data_analyzer.py        # Performance-Analyse & Warnungen
│   ├── llm_client.py           # Hybrid LLM Wrapper (Ollama + OpenRouter)
│   ├── prompt_builder.py       # Prompt Engineering
│   ├── secrets_manager.py      # Secure API Key Storage
│   └── README.md               # AI Coach Dokumentation
├── config/                     # Django Konfiguration
│   ├── settings.py             # Haupt-Settings (mit .env Support)
│   ├── urls.py                 # URL Routing
│   └── wsgi.py                 # WSGI Server Config
├── core/                       # Haupt-App
│   ├── models/                 # Datenmodelle (aufgeteilt nach Domäne)
│   │   ├── training.py         # Trainingseinheit, Satz (inkl. abgeschlossen-Flag)
│   │   ├── exercise.py         # Übungen, Custom Übungen
│   │   ├── plan.py             # Trainingspläne, Gruppen
│   │   ├── body_tracking.py    # Körperwerte
│   │   ├── cardio.py           # Cardio-Einheiten
│   │   └── ...
│   ├── views/                  # Modulare Views
│   │   ├── training_session.py # Training-Logging, Training abschließen
│   │   ├── training_stats.py   # Dashboard, Statistiken (mit Caching)
│   │   └── ...
│   ├── migrations/             # Datenbank-Migrationen (61+)
│   ├── templates/              # HTML Templates (Bootstrap 5)
│   │   ├── core/               # App Templates
│   │   │   ├── dashboard.html         # Dashboard mit AI Widget
│   │   │   ├── training_session.html  # Training mit Autocomplete & Undo
│   │   │   ├── training_finish.html   # Training-Ende mit AI Tipp
│   │   │   ├── exercise_detail.html   # Übungs-Details mit Alternativen
│   │   │   ├── uebungen_auswahl.html  # Übungsauswahl mit Custom Modal
│   │   │   └── ...
│   │   └── includes/           # Reusable Components
│   ├── static/                 # CSS, JS, Service Worker
│   │   └── core/
│   │       ├── js/
│   │       │   ├── exercise-autocomplete.js  # Fuzzy Search (v0.7.7)
│   │       │   ├── keyboard-shortcuts.js     # Keyboard Support (v0.7.7)
│   │       │   ├── loading-manager.js        # Loading States
│   │       │   ├── favoriten.js              # Favoriten Toggle
│   │       │   └── toast.js                  # Toast Notifications
│   │       ├── css/
│   │       │   ├── theme-styles.css          # Dark/Light Theme
│   │       │   └── offline-manager.css       # PWA Styles
│   │       ├── service-worker.js             # PWA Service Worker
│   │       └── manifest.json                 # PWA Manifest
│   ├── fixtures/               # Initial-Daten
│   │   ├── initial_exercises.json  # 98 vordefinierte Übungen
│   │   └── plan_templates.json     # Beispiel-Pläne
│   ├── utils/                  # Utility Module
│   │   └── advanced_stats.py         # Erweiterte Analyse-Funktionen (587 Zeilen)
│   ├── management/commands/    # Custom Management Commands
│   └── migrations/             # Datenbank Migrationen (61+)
├── deployment/                 # Production Configs (Templates)
│   ├── homegym.service         # Systemd Service (Gunicorn)
│   └── homegym.nginx           # Nginx Reverse Proxy
├── docs/                       # Dokumentation
│   ├── AI_COACH_CONCEPT.md     # AI Coach Architektur
│   ├── DEPLOYMENT.md           # Production Deployment Guide
│   ├── OPENROUTER_SETUP.md     # Cloud LLM Setup
│   └── ...
├── .env.example                # Environment Variables Template
├── .gitignore                  # Git Ignore Rules
├── requirements.txt            # Python Dependencies
├── manage.py                   # Django CLI
├── ROADMAP.md                  # Feature Roadmap
├── CONTRIBUTING.md             # Contribution Guidelines
├── LICENSE                     # MIT License
└── README.md                   # Diese Datei
```

---

## 🐳 Production Deployment

Siehe **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** für detaillierte Anweisungen.

**Quick Summary:**
1. Server vorbereiten (Linux, MariaDB, Nginx)
2. `.env` mit Production-Werten erstellen
3. `./deploy.sh` ausführen
4. Systemd Service einrichten (`deployment/homegym.service`)
5. Nginx konfigurieren (`deployment/homegym.nginx`)

**Wichtig:** Root-Dateien `homegym.service` und `homegym.nginx` enthalten echte Secrets und werden **NICHT** committed (.gitignore)!

---

## 🛠️ Technologie-Stack

- **Backend:** Django 5.1.15, Python 3.12
- **Frontend:** Bootstrap 5.3, Chart.js, Vanilla JavaScript
- **Database:** MariaDB (Production), SQLite (Development)
- **Caching:** Django Cache Framework (5-min Dashboard, 30-min Übungsliste, unbegrenzt Plan-Templates)
- **AI:** Ollama (lokal), OpenRouter (Cloud Fallback)
- **Server:** Gunicorn, Nginx
- **PWA:** Service Worker, Manifest.json
- **PDF Generation:** xhtml2pdf 0.2.16, matplotlib 3.10.8, cairosvg 2.7.1, Pillow 12.1.0
- **Load Testing:** Locust 2.43.3 (3 Szenarien, SLO-Auswertung, siehe docs/LOAD_TESTING.md)

### Projekt-Statistiken (Version 0.9.1)
- **Lines of Code:** ~20,000+
- **Python Files:** 70+
- **Templates:** 55+ HTML/Django
- **Exercise Library:** 113 vordefinierte Übungen + Custom Übungen (mit 1RM Standards & anatomischen Daten)
- **Muscle Groups:** 19 (anatomisch korrekt)
- **PDF Report:** 7+ Seiten mit 4 Charts + 5 erweiterte Analysen
- **1RM Standards:** 4 Levels pro Übung (körpergewicht-skaliert)
- **Migrationen:** 61+
- **Tests:** 541 passed, 53% Coverage (Phase 5.3 abgeschlossen)
- **Development Time:** 14+ Monate

---

## 📊 Datenbank Schema

**Core Models:**
- `Uebung`: 113 vordefinierte Übungen + Custom Übungen (Bezeichnung, Muskelgruppe, Equipment, 1RM Standards, created_by)
- `Plan`: User-spezifische Trainingspläne
- `PlanUebung`: M2M Junction mit Reihenfolge, Sätze, Wdh
- `Trainingseinheit`: Einzelnes Training (Datum, Dauer, Kommentar, `abgeschlossen`-Flag)
- `Satz`: Einzelner Satz (Gewicht, Wdh, RPE, Notiz)
- `Koerperwerte`: Körperdaten (Gewicht, KFA, Muskelmasse)
- `Equipment`: User-Equipment für personalisierte Pläne
- `CardioEinheit`: Cardio-Tracking (Aktivität, Intensität, Dauer)

---

## 🔮 Roadmap & Known Limitations

### Aktuell verfügbar (v0.9.1)
- ✅ **Training fortsetzen**: Schnellzugriff auf offene Sessions direkt im Dashboard (v0.9.1)
- ✅ **Performance-Optimierung**: N+1-Query-Fixes, Database Indexes, Caching-Strategie (v0.9.1)
  - Phase 4.1: N+1 Query Elimination (8 Stellen behoben, 414 Tests)
  - Phase 4.2: Database Indexes (Compound Indexes auf Training/Plan, MariaDB-kompatibel)
  - Phase 4.3: Caching Strategy (FileBasedCache, 5min Dashboard, 30min Übungen, unbegrenzt Templates)
- ✅ **Load Testing**: Locust-Setup mit SLO-Auswertung, Baseline-Messung dokumentiert (v0.9.1)
- ✅ **AI/ML Testing Framework**: Phase 5.3 abgeschlossen (541 Tests, 53% Coverage)
  - test_koerpergewicht_support.py, test_ml_trainer.py, test_plan_generator.py
  - Körpergewicht-Skalierung für 1RM Standards (0.0-1.0 Faktor)
- ✅ **1RM Kraftstandards**: 4 Leistungsstufen pro Übung (Anfänger → Elite), körpergewicht-skaliert
- ✅ **Advanced Training Statistics**: Plateau-Analyse, Konsistenz-Metriken, RPE-Qualität, Ermüdungs-Index
- ✅ **CSV-Export**: Alle Trainingsdaten als Download
- ✅ **Erweiterter PDF-Report**: 5 neue Analyse-Module im professionellen Report
- ✅ Cardio Lite Tracking (9 Aktivitäten mit Ermüdungsindex)
- ✅ Video-Support für Übungen (YouTube & Vimeo)
- ✅ Custom Übungen erstellen
- ✅ AI Performance-Analyse (Dashboard Widget)
- ✅ AI Training Counter (jedes 3. Training)
- ✅ Alternative Übungen mit Scoring
- ✅ Keyboard-Shortcuts, Undo-Funktion, Autocomplete
- ✅ Security Improvements (31+ Alerts behoben)

### In Entwicklung (Week 5-6)
- 🔄 **Phase 5.4 – Charts & Statistics Testing** (nächste Phase)
  - Chart-Datenkorrektheit & Edge Cases
  - Robuste Visualisierungen ohne Crashes
- 🔄 **Phase 5.1 – Scientific Source System** (geplant)
  - TrainingSource Model mit DOI, Key Findings
  - Integration in UI-Tooltips & Disclaimers
- 🔄 **Phase 5.2 – KI-Plangenerator Optimierung** (geplant)
  - Eindeutige Plan-Namen (Datum + Ziel)
  - Kontextbasierter Split-Typ (Frequenz → PPL/Upper-Lower/Fullbody)

### Geplant (siehe ROADMAP.md)
- 🔜 Phase 5.5 – API Endpoints Testing
- 🔜 Phase 5.6 – Helper/Utils Testing
- 🔜 Onboarding-Tour & Feature-Discovery
- 🔜 Gewichtsempfehlungen UI-Polish
- 🔜 Notizen-System erweitern (Übungs- & Trainingstag-Notizen)
- 🔜 Social Features (Leaderboards, Challenges)
- 🔜 Nutrition Tracking (Makros & Kalorien)

### Bekannte Limitierungen
- PDF Reports benötigen Cairo-Installation für optimale Body-Maps (Pillow-Fallback verfügbar)
- AI Coach benötigt Ollama oder OpenRouter (nicht offline ohne LLM)
- Equipment-Matching ist case-sensitive (z.B. "Hantel" ≠ "Hanteln")
- Custom Übungen sind user-spezifisch (keine globale Sharing-Funktion)

---

## 🤝 Contributing

Contributions sind willkommen! Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Guidelines.

### Development Setup

```bash
# Fork & Clone
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# Branch erstellen
git checkout -b feature/neue-funktion

# Changes committen
git commit -m "feat: Beschreibung der Änderung"

# Pull Request öffnen
git push origin feature/neue-funktion
```

### Code Style

- **Python:** PEP 8, Type Hints wo sinnvoll
- **Django:** Offizielle Best Practices
- **JavaScript:** ES6+, Vanilla (kein Framework)
- **Templates:** Bootstrap 5 Conventions

---

## � Security

### Wichtige Sicherheitshinweise

**⚠️ Niemals committen:**
- `.env` Datei mit echten Secrets
- `db.sqlite3` Datenbank mit User-Daten
- API Keys (OpenRouter, etc.)
- Production Configs mit Passwörtern

**✅ Sicher committen:**
- `.env.example` als Template
- `deployment/*.example` Configs
- Anonymisierte Test-Fixtures

**Secrets Management:**
```bash
# API Keys sicher speichern mit secrets_manager
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx

# Secrets sind in ~/.homegym_secrets gespeichert (nicht im Git!)
```

**Production Checklist:**
- [ ] `DEBUG=False` in .env
- [ ] `SECRET_KEY` generiert und unique
- [ ] `ALLOWED_HOSTS` korrekt gesetzt
- [ ] SSL/HTTPS aktiviert
- [ ] Datenbank-Backups eingerichtet
- [ ] Firewall konfiguriert (nur Port 80/443)
- [ ] Gunicorn hinter Nginx
- [ ] Static Files korrekt served

---
## ❓ FAQ

**Q: Kann ich HomeGym ohne AI Coach nutzen?**
A: Ja! Alle Core-Features (Training Logging, Pläne, Statistiken) funktionieren ohne AI Coach. Die AI-Funktionen sind optional.

**Q: Welche Kosten entstehen?**
A: 
- **Vollständig kostenlos:** Mit lokaler Ollama-Installation
- **Cloud LLM (optional):** ~0.002-0.003€ pro AI-Request (OpenRouter)
- **Hosting:** Abhängig von deinem Server/Hosting-Anbieter

**Q: Kann ich meine Daten exportieren?**
A: Ja! CSV-Export für alle Trainingsdaten, professioneller PDF-Report mit Analysen, Plan-PDF mit QR-Code, sowie JSON-Export über Django's `dumpdata` Command.

**Q: Ist Multi-User-Betrieb möglich?**
A: Ja! Jeder User hat eigene Daten, Pläne und Custom-Übungen. Vollständige Datenisolation.

**Q: Wie funktioniert die Alternative Übungen Funktion?**
A: AI-Algorithmus matched Übungen nach:
- Bewegungstyp (Compound/Isolation): 50 Punkte
- Muskelgruppe: 40 Punkte
- Hilfsmuskeln: +10 Punkte pro Match
- Equipment-Verfügbarkeit wird berücksichtigt

**Q: Kann ich auf meinem Smartphone installieren?**
A: Ja! HomeGym ist eine PWA (Progressive Web App). Einfach im Browser öffnen und "Zum Startbildschirm hinzufügen".

---
## �📄 License

Dieses Projekt ist unter der [MIT License](LICENSE) lizenziert.

---

## 🙏 Acknowledgments

- [Django](https://www.djangoproject.com/) - Web Framework
- [Ollama](https://ollama.ai/) - Local LLM Runtime
- [Bootstrap](https://getbootstrap.com/) - UI Framework
- [Chart.js](https://www.chartjs.org/) - Visualisierungen
- [OpenRouter](https://openrouter.ai/) - Cloud LLM Fallback

---

## 📧 Support

- **Issues:** [GitHub Issues](https://github.com/leratos/Berry-Gym/issues)
- **Dokumentation:** [ROADMAP.md](ROADMAP.md), [AI_COACH_CONCEPT.md](docs/AI_COACH_CONCEPT.md), [Docs Index](docs/README.md), [Load Testing](docs/LOAD_TESTING.md)
- **Deployment:** [DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

<div align="center">
  
**Made with 💪 by fitness enthusiasts, for fitness enthusiasts**

</div>
