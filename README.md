# 🏋️ HomeGym - AI-Powered Fitness Tracker

<div align="center">

![Django](https://img.shields.io/badge/Django-5.0.3-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square)
![Database](https://img.shields.io/badge/Database-MariaDB%20%7C%20SQLite-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

**Ein intelligentes Trainingstagebuch für HomeGym-Enthusiasten mit KI-gestütztem Coach**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📖 Über dieses Projekt

HomeGym ist eine Django-basierte Web-Applikation, die Krafttraining tracking mit künstlicher Intelligenz kombiniert. Die App ermöglicht detailliertes Logging von Trainingseinheiten, analysiert Fortschritte und bietet einen **KI-Coach**, der automatisch Trainingspläne erstellt und optimiert.

### 🎯 Hauptziele

- **Vollständige Privatsphäre**: Deine Trainingsdaten bleiben auf deinem Server
- **KI ohne Cloud**: Lokale LLMs (Ollama) für 0€ Betriebskosten
- **Smart Tracking**: Automatisches Ghosting, RPE-basierte Gewichtsvorschläge
- **Performance-Fokus**: 1RM Tracking, Volumen-Analyse, Plateau-Erkennung

---

## ✨ Features

### 📊 Core Training Features

- **Smart Training Logging**
  - Sätze, Wiederholungen, Gewicht, RPE (Rate of Perceived Exertion)
  - Automatisches Ghosting: Vorschläge basierend auf letztem Training
  - Aufwärmsätze separat markieren
  - **Superset-Support**: Gruppiere bis zu 5 Übungen (S1-S5) mit farbiger Visualisierung
  - Notizen pro Satz für detailliertes Tracking

- **Körperwerte & Statistiken**
  - Gewicht, Körperfettanteil, Muskelmasse tracking
  - BMI & FFMI Berechnung
  - Progress Photos (optional)
  - Langzeit-Trend-Analysen

- **1RM Tracking & PRs**
  - Automatische 1RM Berechnung (Epley-Formel)
  - Personal Records mit Benachrichtigungen
  - Progressions-Charts pro Übung
  - Plateau-Erkennung (4+ Wochen Stagnation)

### 🤖 AI Coach Features

#### 1. **Automatische Plan-Generierung** (~0.003€ pro Plan)
```bash
python ai_coach/plan_generator.py --user-id 1
```
- LLM analysiert deine Training-Historie
- Berücksichtigt dein Equipment (Hanteln, Bank, Klimmzugstange, etc.)
- Erstellt personalisierten Split (2-6 Trainingstage/Woche)
- Balanced Push/Pull/Legs Aufteilung
- Science-based Volumen-Empfehlungen

#### 2. **Automatische Plan-Optimierung** (Hybrid: Regelbasiert + KI)

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

#### 3. **Live Training Guidance** (~0.002€ pro Chat)
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
git clone https://github.com/leratos/Fitness.git
cd homegym

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
# .env bearbeiten (mindestens SECRET_KEY setzen)

# 5. Datenbank initialisieren
python manage.py migrate

# 6. Übungen hinzufügen (98 vordefinierte Übungen)
python manage.py add_new_exercises

# 7. Equipment zuweisen (für AI Coach)
python manage.py assign_equipment

# 8. Superuser erstellen
python manage.py createsuperuser

# 9. Development Server starten
python manage.py runserver
```

App läuft auf **http://127.0.0.1:8000**

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
homegym/
├── ai_coach/                   # KI-Coach Module
│   ├── plan_generator.py       # Automatische Plan-Generierung
│   ├── plan_adapter.py         # Plan-Optimierung & Analyse
│   ├── live_guidance.py        # Live Training Guidance
│   ├── llm_client.py           # Hybrid LLM Wrapper (Ollama + OpenRouter)
│   ├── prompt_builder.py       # Prompt Engineering
│   ├── secrets_manager.py      # Secure API Key Storage
│   └── README.md               # AI Coach Dokumentation
├── config/                     # Django Konfiguration
│   ├── settings.py             # Haupt-Settings (mit .env Support)
│   ├── urls.py                 # URL Routing
│   └── wsgi.py                 # WSGI Server Config
├── core/                       # Haupt-App
│   ├── models.py               # Datenmodelle (100+ Übungen, Trainings, Pläne)
│   ├── views.py                # Business Logic + API Endpoints
│   ├── admin.py                # Django Admin Interface
│   ├── templates/              # HTML Templates (Bootstrap 5)
│   ├── static/                 # CSS, JS, Service Worker
│   ├── fixtures/               # Initial-Daten (Übungen)
│   ├── management/commands/    # Custom Management Commands
│   └── migrations/             # Datenbank Migrationen
├── deployment/                 # Production Configs (Templates)
│   ├── homegym.service         # Systemd Service (Gunicorn)
│   └── homegym.nginx           # Nginx Reverse Proxy
├── .env.example                # Environment Variables Template
├── .gitignore                  # Git Ignore Rules
├── requirements.txt            # Python Dependencies
├── manage.py                   # Django CLI
├── DEPLOYMENT.md               # Production Deployment Guide
├── ROADMAP.md                  # Feature Roadmap
└── README.md                   # Diese Datei
```

---

## 🐳 Production Deployment

Siehe **[DEPLOYMENT.md](DEPLOYMENT.md)** für detaillierte Anweisungen.

**Quick Summary:**
1. Server vorbereiten (Linux, MariaDB, Nginx)
2. `.env` mit Production-Werten erstellen
3. `./deploy.sh` ausführen
4. Systemd Service einrichten (`deployment/homegym.service`)
5. Nginx konfigurieren (`deployment/homegym.nginx`)

**Wichtig:** Root-Dateien `homegym.service` und `homegym.nginx` enthalten echte Secrets und werden **NICHT** committed (.gitignore)!

---

## 🛠️ Technologie-Stack

- **Backend:** Django 5.0.3, Python 3.12
- **Frontend:** Bootstrap 5.3, Chart.js, Vanilla JavaScript
- **Database:** MariaDB (Production), SQLite (Development)
- **AI:** Ollama (lokal), OpenRouter (Cloud Fallback)
- **Server:** Gunicorn, Nginx
- **PWA:** Service Worker, Manifest.json

---

## 📊 Datenbank Schema

**Core Models:**
- `Uebung`: 98 vordefinierte Übungen (Bezeichnung, Muskelgruppe, Equipment)
- `Plan`: User-spezifische Trainingspläne
- `PlanUebung`: M2M Junction mit Reihenfolge, Sätze, Wdh
- `Trainingseinheit`: Einzelnes Training (Datum, Dauer, Kommentar)
- `Satz`: Einzelner Satz (Gewicht, Wdh, RPE, Notiz)
- `Koerperwerte`: Körperdaten (Gewicht, KFA, Muskelmasse)
- `Equipment`: User-Equipment für personalisierte Pläne

---

## 🤝 Contributing

Contributions sind willkommen! Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Guidelines.

### Development Setup

```bash
# Fork & Clone
git clone https://github.com/leratos/Fitness.git
cd homegym

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

## 📄 License

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

- **Issues:** [GitHub Issues](https://github.com/leratos/Fitness/issues)
- **Dokumentation:** [ROADMAP.md](ROADMAP.md), [AI_COACH_CONCEPT.md](AI_COACH_CONCEPT.md)
- **Deployment:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

<div align="center">
  
**Made with 💪 by fitness enthusiasts, for fitness enthusiasts**

</div>
