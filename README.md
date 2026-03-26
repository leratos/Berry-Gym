
<div align="center">

![Django](https://img.shields.io/badge/Django-5.1.15-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square)
![Database](https://img.shields.io/badge/Database-MariaDB%20%7C%20SQLite-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)
![Version](https://img.shields.io/badge/Version-1.0-brightgreen?style=flat-square)
![PWA](https://img.shields.io/badge/PWA-Ready-purple?style=flat-square)
![i18n](https://img.shields.io/badge/i18n-DE%20%7C%20EN-blue?style=flat-square)

![CI/CD](https://github.com/leratos/Berry-Gym/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/leratos/Berry-Gym/branch/main/graph/badge.svg)](https://codecov.io/gh/leratos/Berry-Gym)

**Ein intelligentes Trainingstagebuch für HomeGym-Enthusiasten mit KI-gestütztem Coach, 1RM Kraftstandards, Advanced Analytics & AI Performance-Analyse**

🌐 **[Live Demo & Beta Testing](https://gym.last-strawberry.com)** 🌐

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Roadmap](#-roadmap--known-limitations) • [Contributing](#-contributing) • [English README](README_EN.md)

</div>

---

## 📖 Über dieses Projekt

HomeGym ist eine Django-basierte Web-Applikation, die Krafttraining-Tracking mit künstlicher Intelligenz kombiniert. Die App ermöglicht detailliertes Logging von Trainingseinheiten, analysiert Fortschritte mit evidenzbasierten Metriken und bietet einen **KI-Coach**, der automatisch Trainingspläne erstellt und optimiert.

**Sprachen:** Deutsch & Englisch (vollständig internationalisiert, 790+ Übersetzungen)

### 🎯 Hauptziele

- **Vollständige Privatsphäre**: Deine Trainingsdaten bleiben auf deinem Server
- **Smart Tracking**: Automatisches Ghosting, RPE-basierte Gewichtsvorschläge, Superset-Support
- **Performance-Fokus**: 1RM Tracking, Volumen-Analyse, Plateau-Erkennung
- **Professionelle Reports**: Anatomische Body-Maps mit dynamischer Farbcodierung
- **KI-gestützt**: Gemini 2.5 Flash via OpenRouter (~0.003€ pro Plangenerierung)

---

## ✨ Features

### 📊 Core Training Features

- **Smart Training Logging**
  - Sätze, Wiederholungen, Gewicht, RPE (Rate of Perceived Exertion)
  - Automatisches Ghosting: Vorschläge basierend auf letztem Training
  - Aufwärmsätze separat markieren
  - **Superset-Support**: Gruppiere bis zu 5 Übungen (S1–S5) mit farbiger Visualisierung
  - Notizen pro Satz & Technik-Hinweis pro Plan-Übung
  - **Undo-Funktion**: Gelöschte Sätze innerhalb 5 Sekunden wiederherstellen
  - **Keyboard-Shortcuts**: Enter=Save, Esc=Close, N=New Set, S=Add Set
  - **Übungssuche mit Autocomplete**: Fuzzy-Matching & Score-basiertes Ranking
  - **Training fortsetzen**: Schnellzugriff auf offene Sessions direkt im Dashboard
  - Bei mehreren vergessenen Sessions: Warnung mit Link zur History

- **Wochenübersicht im Dashboard**
  - Mo–So Tagesstreifen mit Trainings-Status
  - Fortschrittsbalken zum Wochenziel
  - Konfigurierbares Trainingsziel (3–6 Tage/Woche) im Profil

- **Custom Übungen erstellen**
  - Eigene Übungen definieren mit Muskelgruppe, Bewegungstyp & Equipment
  - User-spezifisch: Nur du siehst deine Custom-Übungen
  - Custom-Badge zur Unterscheidung von globalen Übungen

- **Übungs-Video-Anleitungen**
  - Video-Links für Übungen (YouTube & Vimeo Support)
  - Responsive Video-Player im Exercise Info Modal

- **Körperwerte & Statistiken**
  - Gewicht, Körperfettanteil, Muskelmasse tracking
  - Live-Umrechnung kg ↔ % beim Erfassen
  - BMI & FFMI Berechnung (Körpergröße einmalig im Profil)
  - Progress Photos (optional)

- **Cardio-Tracking (Lite)**
  - 9 Aktivitäten: Schwimmen, Laufen, Radfahren, Rudern, Gehen, HIIT, Stepper, Seilspringen, Sonstiges
  - 3 Intensitätsstufen mit automatischer Ermüdungspunkt-Integration
  - Dashboard-Statistiken (Einheiten & Minuten pro Woche)

- **1RM Tracking & PRs**
  - Automatische 1RM Berechnung (Epley-Formel)
  - Personal Records mit Benachrichtigungen
  - Progressions-Charts pro Übung
  - Plateau-Erkennung (4+ Wochen Stagnation)
  - **Alternative Übungen**: Intelligentes Matching nach Bewegungstyp & Muskelgruppe
  - **1RM Kraftstandards**: 4 Leistungsstufen pro Übung (Anfänger → Elite), körpergewicht-skaliert
  - **6-Monats 1RM-Entwicklung** mit Fortschrittsbalken zum nächsten Level

### 🤖 AI Coach Features

#### 1. AI Performance-Analyse

**Dashboard Widget – Top 3 Warnungen:**
- Plateau-Erkennung (Session-basierter Vergleich)
- Rückschritt-Erkennung: >15% Leistungsabfall
- Stagnation: Muskelgruppen >14 Tage nicht trainiert

**Training Counter – Jedes 3. Training:**
- Intensitätsanalyse: RPE zu niedrig/hoch
- Volumen-Trend: ±15% Veränderung
- Übungsvielfalt-Warnung

#### 2. Automatische Plan-Generierung (~0.003€ pro Plan)

- **Gemini 2.5 Flash** (via OpenRouter)
- Berücksichtigt Equipment, Trainingshistorie & Frequenz
- Echtzeit-Fortschrittsanzeige via Server-Sent Events (SSE Streaming)
- Kontextbasierter Split-Typ (2–3×/Woche → Fullbody, 4× → PPL, 5–6× → 4er-Split)

#### 3. Automatische Plan-Optimierung (Hybrid: Regelbasiert + KI)

- Stufe 1 kostenlos: RPE-Analyse, Muskelgruppen-Balance, Plateau-Erkennung
- Stufe 2 KI (~0.003€): Übungs-Ersatz, Volumen-Anpassungen, Diff-View

#### 4. Live Training Guidance (~0.002€ pro Chat)

- Echtzeit-Formcheck-Tipps
- Context-aware: Kennt deinen aktuellen Trainingsstand

### 📈 Erweiterte Statistiken

- Volumen-Progression, Wöchentliches Volumen (4-Wochen Rolling Average)
- Muskelgruppen-Balance, Trainings-Heatmap (90 Tage)
- Performance Form-Index (0–100), Ermüdungs-Index mit Deload-Empfehlungen
- Plateau-Analyse (5-stufig), Konsistenz-Metriken, RPE-Qualitätsanalyse
- 1RM Kraftstandards-Vergleich

### 📄 Professionelle PDF Reports (7+ Seiten)

- Anatomische Body-Map (SVG, 19 Muskelgruppen dynamisch eingefärbt)
- Push/Pull Balance, Kraft-Progression, Trainer Recommendations
- Ermüdungs-Index, 1RM Standards, RPE-Qualitätsanalyse
- Export als CSV (kompatibel mit Excel/Sheets)

### 📚 Plan-Sharing & Bibliothek

- Plan duplizieren, teilen (QR-Code, Link, WhatsApp, Telegram)
- **Öffentliche Plan-Bibliothek** (`/plan-library/`): durchsuchbar, 1-Klick-Kopieren
- Plan-Gruppen: umbenennen, sortieren, öffentlich/privat Toggle

### 🌐 Internationalisierung

- **Deutsch** (Standard) & **Englisch** vollständig übersetzt
- 790+ Übersetzungen, Language-Switcher in der Navigation
- URL-Prefix für EN: `/en/dashboard/` statt `/dashboard/`
- L10N-sicheres JavaScript (Dezimalzahlen locale-unabhängig)

### 🔐 User Management & Sicherheit

- Multi-User Support mit vollständiger Datenisolation
- @login_required Guards auf allen sensiblen Views
- Rate Limiting für alle 5 KI-Endpoints (konfigurierbar via .env)
- IDOR-Schutz, defusedxml, File Upload Validation

### 📱 Progressive Web App (PWA)

- Installierbar auf Smartphone/Desktop
- Offline-fähig (Service Worker)
- Push-Benachrichtigungen (optional)

---

## 🚀 Installation

### Voraussetzungen

- **Python 3.12+**
- **Git**
- **Optional (für AI Coach):** OpenRouter API Key (https://openrouter.ai/)

### Quick Start (Development)

```bash
# 1. Repository klonen
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# 2. Virtual Environment erstellen & aktivieren
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Environment Variables setzen
cp .env.example .env
# .env bearbeiten: mindestens SECRET_KEY setzen

# 5. Datenbank initialisieren
python manage.py migrate

# 6. Übungen laden (113 vordefinierte Übungen)
python manage.py loaddata core/fixtures/initial_exercises.json

# 7. Superuser erstellen
python manage.py createsuperuser

# 8. Development Server starten
python manage.py runserver
```

App läuft auf **http://127.0.0.1:8000**

### Environment Variables (.env)

```env
# Django Core
SECRET_KEY=your-secret-key-here
DEBUG=True          # False für Production!
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Optional – Standard: SQLite)
# DATABASE_ENGINE=django.db.backends.mysql
# DATABASE_NAME=homegym
# DATABASE_USER=your_user
# DATABASE_PASSWORD=your_password
# DATABASE_HOST=localhost
# DATABASE_PORT=3306

# AI Coach (Optional – ohne Key sind KI-Funktionen deaktiviert)
USE_OPENROUTER_FALLBACK=True
OPENROUTER_MODEL=google/gemini-2.5-flash
# OPENROUTER_API_KEY wird via secrets_manager gespeichert (nicht in .env!)

# KI-Rate-Limits (Optional – Defaults unten)
AI_PLAN_LIMIT=3
AI_ANALYZE_LIMIT=50
AI_GUIDANCE_LIMIT=10
```

### AI Coach Setup (OpenRouter)

```bash
# API Key sicher speichern
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx
```

**Kosten:** ~0.003€ pro Plangenerierung. Ohne API Key bleiben alle anderen Features voll funktionsfähig.

---

## 🗂️ Projekt-Struktur

```
Berry-Gym/
├── ai_coach/                   # KI-Coach Module
│   ├── plan_generator.py       # Automatische Plan-Generierung (Gemini 2.5 Flash)
│   ├── plan_adapter.py         # Plan-Optimierung & Analyse
│   ├── live_guidance.py        # Live Training Guidance
│   ├── data_analyzer.py        # Performance-Analyse & Warnungen
│   ├── llm_client.py           # LLM Wrapper (OpenRouter)
│   ├── prompt_builder.py       # Prompt Engineering
│   ├── secrets_manager.py      # Secure API Key Storage
│   └── tests/                  # AI Coach Tests
├── config/                     # Django Konfiguration
│   ├── settings.py             # Haupt-Settings (i18n, L10N, Caching)
│   ├── urls.py                 # URL Routing (inkl. i18n_patterns)
│   └── wsgi.py
├── core/                       # Haupt-App
│   ├── models/                 # Datenmodelle (nach Domäne aufgeteilt)
│   │   ├── training.py         # Trainingseinheit, Satz
│   │   ├── exercise.py         # Übungen, Custom Übungen
│   │   ├── plan.py             # Trainingspläne, Gruppen
│   │   ├── body_tracking.py    # Körperwerte, Progress Photos
│   │   ├── cardio.py           # Cardio-Einheiten
│   │   ├── training_source.py  # Wissenschaftliche Quellen
│   │   └── user_profile.py     # UserProfile (Equipment, Ziele, Rate Limits)
│   ├── views/                  # Modulare Views
│   │   ├── training_session.py # Training-Logging, Plan-Auswahl
│   │   ├── training_stats.py   # Dashboard, Statistiken (mit Caching)
│   │   ├── plan_management.py  # Plan CRUD, Sharing, Bibliothek
│   │   ├── ai_recommendations.py # KI-Endpunkte (Rate-Limited)
│   │   └── ...
│   ├── templates/core/         # HTML Templates (Bootstrap 5, i18n)
│   ├── tests/                  # Umfangreiche Test-Suites (pytest)
│   ├── static/core/            # CSS, JS, PWA
│   ├── fixtures/               # initial_exercises.json, plan_templates.json
│   ├── migrations/             # 70+ Datenbank-Migrationen
│   └── management/commands/    # Custom Management Commands
├── locale/                     # Übersetzungen
│   └── en/LC_MESSAGES/
│       ├── django.po           # 790 EN-Übersetzungen (0 fuzzy, 0 untranslated)
│       └── django.mo           # Kompilierte MO-Datei
├── deployment/                 # Production Configs
│   ├── homegym.service         # Systemd Service (Gunicorn)
│   └── homegym.nginx           # Nginx Reverse Proxy
├── docs/                       # Dokumentation
│   ├── journal.txt             # Entwicklungstagbuch (laufend gepflegt)
│   ├── PROJECT_ROADMAP.md      # Milestone-Roadmap (aktuell)
│   ├── DEPLOYMENT.md           # Production Deployment Guide
│   ├── RUNBOOK.md              # Incident Response & Operations
│   ├── CICD_GUIDE.md           # CI/CD Pipeline Guide
│   ├── CODE_QUALITY.md         # Code Quality Standards
│   └── LOAD_TESTING.md         # Locust SLO-Dokumentation
├── README.md                   # Diese Datei (DE)
├── README_EN.md                # English README
└── requirements.txt
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

---

## 🛠️ Technologie-Stack

| Bereich | Technologie |
|---------|------------|
| Backend | Django 5.1.15, Python 3.12 |
| Frontend | Bootstrap 5.3, Chart.js, Vanilla JS |
| Datenbank | MariaDB (Production), SQLite (Dev) |
| Caching | Django FileBasedCache (5–30 min) |
| AI | Google Gemini 2.5 Flash via OpenRouter |
| Server | Gunicorn, Nginx |
| PWA | Service Worker, manifest.json |
| PDF | xhtml2pdf, matplotlib, cairosvg, Pillow |
| i18n | Django i18n/L10N, gettext (DE/EN) |
| Testing | pytest, factory_boy, CI/CD |
| ML | scikit-learn (lokale Gewichtsvorhersagen) |

### Projekt-Statistiken (Version 1.0, Stand Feb 2026)

| Metrik | Wert |
|--------|------|
| Tests | **800+**, CI/CD grün |
| Übersetzungen | **790** (DE→EN, 0 fuzzy, 0 untranslated) |
| Übungen | **113** vordefiniert + Custom Übungen |
| Migrationen | **70+** |
| Templates | **55+** HTML/Django |
| Python Files | **70+** |
| Lines of Code | **~22.000+** |
| Projektstatus | **Live seit Feb 2026** |

---

## 🔮 Roadmap & Known Limitations

Aktuelle Priorisierung und Umsetzungsstatus stehen in
**[docs/PROJECT_ROADMAP.md](docs/PROJECT_ROADMAP.md)**
(Milestone-basiert, Stand 24.02.2026).

### Aktuell verfügbar (v1.0)

- ✅ **Hevy Import/Export**: CSV-Import aus Hevy/Strong mit Dry-Run, automatischem Übungs-Matching und Duplikatschutz; Export im Hevy-Format (14 Spalten)
- ✅ **Einzelplan-Aktivierung**: Pläne ohne Gruppe direkt als aktiven Plan setzen
- ✅ **CI/CD Pipeline**: GitHub Actions → automatischer Deploy auf Production
- ✅ **Security**: IDOR-Fix, @login_required Guards, defusedxml, File Upload Validation
- ✅ **Rate Limiting**: 5 KI-Endpoints abgesichert (konfigurierbar via .env)
- ✅ **Internationalisierung**: DE & EN vollständig (790 Übersetzungen, Language-Switcher)
- ✅ **L10N-Bug-Fix**: Dezimalzahlen in JS locale-sicher ({% localize off %})
- ✅ **Wochenübersicht**: Dashboard-Karte Mo–So mit Fortschrittsbalken
- ✅ **Notizen erweitert**: Technik-Hinweis pro Plan-Übung, Quick-Tags
- ✅ **Scientific Sources**: TrainingSource Model, Literatur-Datenbank (Schoenfeld, Israetel etc.)
- ✅ **KI-Plangenerator**: Gemini 2.5 Flash, SSE Streaming, Weakness Coverage Validation
- ✅ **Performance**: N+1-Query-Fixes, Database Indexes, Caching-Strategie
- ✅ **Load Testing**: Locust-Setup, SLO-Auswertung (100 concurrent users)
- ✅ **1RM Kraftstandards**: 4 Leistungsstufen, körpergewicht-skaliert
- ✅ **Advanced Statistics**: Plateau, Konsistenz, RPE-Qualität, Ermüdungs-Index
- ✅ **CSV-Export**, Cardio Lite, Video-Support, Custom Übungen, Superset, PWA
- ✅ **Import/Export (Hevy-Format)**: CSV-Export & Import kompatibel mit Hevy/Strong – "Bring your data" für Wechsler, Dry-Run Vorschau, automatisches Übungs-Matching
- ✅ **Einzelplan-Aktivierung**: Pläne ohne Gruppe können direkt als aktiver Plan gesetzt werden
- ✅ **KI-Planvalidierung**: 5 programmatische Post-Validierungen (Cross-Session-Duplikate, verbotene Kombinationen, anatomische Pflichtgruppen, Compound-vor-Isolation Auto-Fix, Pausenzeiten Auto-Fix)
- ✅ **Kontextsensitive Empfehlungen**: Trainingsmodus-abhängige Empfehlungstexte, gruppenspezifische Volumen-Schwellenwerte (gross/mittel/klein/haltung), Wiederholungsbereich-Analyse mit Stacked-Progress-Bar

### In Planung / Nächste Schritte

- 🔥 **M5 – Coverage Sprint C**: gezielte Testvertiefung für Charts/Stats/Helpers
- 🧠 **M6 – AI Endpoint Contract Hardening**: konsistente Fehlerverträge + zusätzliche Edge-Case-Tests
- 🔐 **M7 – Security & Compliance Tightening**: Security-Findings-Prozess und Policy-Schärfung
- 🔜 Danach: Operations-Reife (M8) und inkrementelles Refactoring (M9)

### Bekannte Limitierungen

- PDF Reports benötigen Cairo für optimale Body-Maps (Pillow-Fallback verfügbar)
- AI Coach benötigt OpenRouter API Key (Kosten: ~0.003€/Plan)
- Custom Übungen sind user-spezifisch (kein globales Sharing)
- GNU gettext nicht zwingend erforderlich (MO-Kompilierung via polib)

**Last Updated:** 2026-03-26

---

## 🤝 Contributing

Contributions sind willkommen! Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Guidelines.

```bash
# Fork & Clone
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# Branch erstellen
git checkout -b feature/neue-funktion

# Tests ausführen
python -m pytest

# Pull Request öffnen
git push origin feature/neue-funktion
```

**Code Style:** PEP 8, Type Hints, Black/isort/flake8 (pre-commit hooks)

---

## 🔒 Security

**Niemals committen:** `.env`, `db.sqlite3`, API Keys, Production Configs

```bash
# API Keys sicher speichern
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx
# Gespeichert in ~/.homegym_secrets (nicht im Git!)
```

**Production Checklist:**
- [ ] `DEBUG=False` in .env
- [ ] `SECRET_KEY` generiert und unique
- [ ] `ALLOWED_HOSTS` korrekt gesetzt
- [ ] SSL/HTTPS aktiviert
- [ ] Datenbank-Backups eingerichtet
- [ ] Gunicorn hinter Nginx

---

## ❓ FAQ

**Q: Kann ich HomeGym ohne AI Coach nutzen?**
A: Ja! Alle Core-Features (Training Logging, Pläne, Statistiken, PDF Reports) funktionieren ohne AI Coach.

**Q: Welche Kosten entstehen?**
A: Der Self-Hosted-Betrieb ist kostenlos. Der AI Coach kostet ~0.003€ pro Plangenerierung via OpenRouter – das ist optional.

**Q: Gibt es eine Mobile App?**
A: HomeGym ist eine PWA – installierbar auf iOS und Android direkt aus dem Browser.

**Q: Welche Sprachen werden unterstützt?**
A: Deutsch (Standard) und Englisch. Der Language-Switcher ist in der Navigation oben rechts.

---

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

<div align="center">
Made with ❤️ for HomeGym enthusiasts

🌐 **[gym.last-strawberry.com](https://gym.last-strawberry.com)** | [English README](README_EN.md)
</div>
