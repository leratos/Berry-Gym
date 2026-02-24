
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

**An intelligent training journal for home gym enthusiasts — AI coach, 1RM strength standards, advanced analytics & performance analysis**

🌐 **[Live Demo & Beta Testing](https://gym.last-strawberry.com)** 🌐

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Roadmap](#-roadmap--known-limitations) • [Contributing](#-contributing) • [Deutsche README](README.md)

</div>

---

## 📖 About This Project

HomeGym is a Django-based web application that combines strength training tracking with artificial intelligence. It enables detailed logging of workout sessions, analyzes progress with evidence-based metrics, and provides an **AI Coach** that automatically creates and optimizes training plans.

**Languages:** German & English (fully internationalized, 790+ translations)

### 🎯 Core Goals

- **Full Privacy**: Your training data stays on your server
- **Smart Tracking**: Automatic ghosting, RPE-based weight suggestions, superset support
- **Performance Focus**: 1RM tracking, volume analysis, plateau detection
- **Professional Reports**: Anatomical body maps with dynamic color coding
- **AI-Powered**: Gemini 2.5 Flash via OpenRouter (~€0.003 per plan generation)

---

## ✨ Features

### 📊 Core Training Features

- **Smart Training Logging**
  - Sets, reps, weight, RPE (Rate of Perceived Exertion)
  - Automatic ghosting: suggestions based on last workout
  - Warm-up sets tracked separately
  - **Superset Support**: Group up to 5 exercises (S1–S5) with color visualization
  - Notes per set & technique hints per plan exercise
  - **Undo Function**: Restore deleted sets within 5 seconds
  - **Keyboard Shortcuts**: Enter=Save, Esc=Close, N=New Set, S=Add Set
  - **Exercise Search with Autocomplete**: Fuzzy matching & score-based ranking
  - **Resume Training**: Quick access to open sessions directly from the dashboard

- **Weekly Overview on Dashboard**
  - Mon–Sun day strip with training status
  - Progress bar toward weekly goal
  - Configurable training goal (3–6 days/week) in profile

- **Custom Exercises**
  - Define your own exercises with muscle group, movement type & equipment
  - User-specific: only you see your custom exercises
  - Custom badge to distinguish from global exercises

- **Exercise Video Instructions**
  - Video links for exercises (YouTube & Vimeo support)
  - Responsive video player in the exercise info modal

- **Body Tracking & Statistics**
  - Weight, body fat, muscle mass tracking
  - Live conversion kg ↔ % when recording
  - BMI & FFMI calculation (height stored once in profile)
  - Progress photos (optional)

- **Cardio Tracking (Lite)**
  - 9 activities: Swimming, Running, Cycling, Rowing, Walking, HIIT, Stepper, Jump Rope, Other
  - 3 intensity levels with automatic fatigue point integration
  - Dashboard stats (sessions & minutes per week)

- **1RM Tracking & PRs**
  - Automatic 1RM calculation (Epley formula)
  - Personal records with notifications
  - Progression charts per exercise
  - Plateau detection (4+ weeks stagnation)
  - **Alternative Exercises**: Intelligent matching by movement type & muscle group
  - **1RM Strength Standards**: 4 performance levels per exercise (Beginner → Elite), bodyweight-scaled
  - **6-Month 1RM Development** with progress bar to next level

### 🤖 AI Coach Features

#### 1. AI Performance Analysis

**Dashboard Widget – Top 3 Warnings:**
- Plateau detection (session-based comparison)
- Regression detection: >15% performance drop
- Stagnation: muscle groups untrained for >14 days

**Training Counter – Every 3rd Workout:**
- Intensity analysis: RPE too low/high
- Volume trend: ±15% change
- Exercise variety warning

#### 2. Automatic Plan Generation (~€0.003 per plan)

- **Gemini 2.5 Flash** (via OpenRouter)
- Considers equipment, training history & frequency
- Real-time progress display via Server-Sent Events (SSE streaming)
- Context-based split type (2–3×/week → Fullbody, 4× → PPL, 5–6× → 4-day split)

#### 3. Automatic Plan Optimization (Hybrid: Rule-Based + AI)

- Tier 1 free: RPE analysis, muscle group balance, plateau detection
- Tier 2 AI (~€0.003): Exercise replacement, volume adjustments, diff view

#### 4. Live Training Guidance (~€0.002 per chat)

- Real-time form check tips
- Context-aware: knows your current training status

### 📈 Advanced Statistics

- Volume progression, weekly volume (4-week rolling average)
- Muscle group balance, 90-day training heatmap
- Performance Form Index (0–100), Fatigue Index with deload recommendations
- Plateau analysis (5-stage), consistency metrics, RPE quality analysis
- 1RM strength standards comparison

### 📄 Professional PDF Reports (7+ pages)

- Anatomical body map (SVG, 19 muscle groups dynamically colored)
- Push/pull balance, strength progression, trainer recommendations
- Fatigue index, 1RM standards, RPE quality analysis
- CSV export (compatible with Excel/Sheets)

### 📚 Plan Sharing & Library

- Duplicate plans, share (QR code, link, WhatsApp, Telegram)
- **Public Plan Library** (`/plan-library/`): searchable, 1-click copy
- Plan groups: rename, sort, public/private toggle

### 🌐 Internationalization

- **German** (default) & **English** fully translated
- 790+ translations, language switcher in navigation
- URL prefix for EN: `/en/dashboard/` instead of `/dashboard/`
- L10N-safe JavaScript (decimal numbers locale-independent)

### 🔐 User Management & Security

- Multi-user support with full data isolation
- @login_required guards on all sensitive views
- Rate limiting for all 5 AI endpoints (configurable via .env)
- IDOR protection, defusedxml, file upload validation

### 📱 Progressive Web App (PWA)

- Installable on smartphone/desktop
- Offline-capable (Service Worker)
- Push notifications (optional)

---

## 🚀 Installation

### Requirements

- **Python 3.12+**
- **Git**
- **Optional (for AI Coach):** OpenRouter API Key (https://openrouter.ai/)

### Quick Start (Development)

```bash
# 1. Clone repository
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# 2. Create & activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env: at minimum set SECRET_KEY

# 5. Initialize database
python manage.py migrate

# 6. Load exercises (113 predefined exercises)
python manage.py loaddata core/fixtures/initial_exercises.json

# 7. Create superuser
python manage.py createsuperuser

# 8. Start development server
python manage.py runserver
```

App runs at **http://127.0.0.1:8000**

### Environment Variables (.env)

```env
# Django Core
SECRET_KEY=your-secret-key-here
DEBUG=True          # Set to False for production!
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Optional – defaults to SQLite)
# DATABASE_ENGINE=django.db.backends.mysql
# DATABASE_NAME=homegym
# DATABASE_USER=your_user
# DATABASE_PASSWORD=your_password
# DATABASE_HOST=localhost
# DATABASE_PORT=3306

# AI Coach (Optional – AI features disabled without key)
USE_OPENROUTER_FALLBACK=True
OPENROUTER_MODEL=google/gemini-2.5-flash
# OPENROUTER_API_KEY stored via secrets_manager (not in .env!)

# AI Rate Limits (Optional – defaults shown)
AI_PLAN_LIMIT=3
AI_ANALYZE_LIMIT=50
AI_GUIDANCE_LIMIT=10
```

### AI Coach Setup (OpenRouter)

```bash
# Store API key securely
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx
```

**Cost:** ~€0.003 per plan generation. All other features work fully without an API key.

---

## 🗂️ Project Structure

```
Berry-Gym/
├── ai_coach/                   # AI Coach modules
│   ├── plan_generator.py       # Automatic plan generation (Gemini 2.5 Flash)
│   ├── plan_adapter.py         # Plan optimization & analysis
│   ├── live_guidance.py        # Live training guidance
│   ├── llm_client.py           # LLM wrapper (OpenRouter)
│   └── tests/
├── config/                     # Django configuration
│   ├── settings.py             # Main settings (i18n, L10N, caching)
│   └── urls.py                 # URL routing (incl. i18n_patterns)
├── core/                       # Main app
│   ├── models/                 # Data models (split by domain)
│   ├── views/                  # Modular views
│   ├── templates/core/         # HTML templates (Bootstrap 5, i18n)
│   ├── tests/                  # Extensive test suites (pytest)
│   ├── static/core/            # CSS, JS, PWA
│   ├── fixtures/               # initial_exercises.json, plan_templates.json
│   └── migrations/             # 70+ database migrations
├── locale/
│   └── en/LC_MESSAGES/
│       ├── django.po           # 790 EN translations (0 fuzzy, 0 untranslated)
│       └── django.mo
├── deployment/                 # Production configs
├── docs/                       # Documentation
│   ├── journal.txt             # Development journal
│   ├── PROJECT_ROADMAP.md      # Milestone roadmap (current)
│   └── DEPLOYMENT.md
├── README.md                   # German README
└── README_EN.md                # This file
```

---

## 🛠️ Technology Stack

| Area | Technology |
|------|-----------|
| Backend | Django 5.1.15, Python 3.12 |
| Frontend | Bootstrap 5.3, Chart.js, Vanilla JS |
| Database | MariaDB (production), SQLite (dev) |
| Caching | Django FileBasedCache (5–30 min) |
| AI | Google Gemini 2.5 Flash via OpenRouter |
| Server | Gunicorn, Nginx |
| PWA | Service Worker, manifest.json |
| PDF | xhtml2pdf, matplotlib, cairosvg, Pillow |
| i18n | Django i18n/L10N, gettext (DE/EN) |
| Testing | pytest, factory_boy, CI/CD |
| ML | scikit-learn (local weight predictions) |

### Project Statistics (Version 1.0, Feb 2026)

| Metric | Value |
|--------|-------|
| Tests | **800+**, CI/CD green |
| Translations | **790** (DE→EN, 0 fuzzy, 0 untranslated) |
| Exercises | **113** predefined + custom exercises |
| Migrations | **70+** |
| Templates | **55+** HTML/Django |
| Lines of Code | **~22,000+** |
| Project Status | **Live since Feb 2026** |

---

## 🔮 Roadmap & Known Limitations

Current prioritization and implementation status are tracked in
**[docs/PROJECT_ROADMAP.md](docs/PROJECT_ROADMAP.md)**
(milestone-based, updated 2026-02-24).

### Currently Available (v1.0)

- ✅ **Hevy Import/Export**: CSV import from Hevy/Strong with dry-run preview, automatic exercise matching and duplicate protection; export in Hevy format (14 columns)
- ✅ **Single Plan Activation**: Activate plans without a group directly as the active plan
- ✅ **CI/CD Pipeline**: GitHub Actions → automatic production deploy
- ✅ **Security**: IDOR fix, @login_required guards, defusedxml, file upload validation
- ✅ **Rate Limiting**: 5 AI endpoints secured (configurable via .env)
- ✅ **Internationalization**: DE & EN fully translated (790 translations, language switcher)
- ✅ **L10N Bug Fix**: Decimal numbers locale-safe in JavaScript
- ✅ **Weekly Overview**: Dashboard card Mon–Sun with progress bar
- ✅ **Extended Notes**: Technique hints per plan exercise, quick tags
- ✅ **Scientific Sources**: TrainingSource model, literature database
- ✅ **AI Plan Generator**: Gemini 2.5 Flash, SSE streaming, weakness coverage validation
- ✅ **Performance**: N+1 query fixes, database indexes, caching strategy
- ✅ **Load Testing**: Locust setup, SLO evaluation (100 concurrent users)
- ✅ **1RM Strength Standards**: 4 performance levels, bodyweight-scaled
- ✅ **Advanced Statistics**: Plateau, consistency, RPE quality, fatigue index
- ✅ **CSV Export**, Cardio Lite, Video support, Custom exercises, Superset, PWA

### Planned / Next Steps

- 🔥 **M5 – Coverage Sprint C**: targeted test depth for charts/stats/helpers
- 🧠 **M6 – AI Endpoint Contract Hardening**: consistent error contracts + edge-case tests
- 🔐 **M7 – Security & Compliance Tightening**: security findings process and policy hardening
- 🔜 Afterwards: operations maturity (M8) and incremental refactoring (M9)

### Known Limitations

- PDF reports require Cairo for optimal body maps (Pillow fallback available)
- AI Coach requires OpenRouter API key (~€0.003/plan)
- Custom exercises are user-specific (no global sharing)

**Last Updated:** 2026-02-24

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Fork & clone
git clone https://github.com/leratos/Berry-Gym.git
cd Berry-Gym

# Create branch
git checkout -b feature/new-feature

# Run tests
python -m pytest

# Open pull request
git push origin feature/new-feature
```

**Code Style:** PEP 8, type hints, Black/isort/flake8 (pre-commit hooks)

---

## 🔒 Security

**Never commit:** `.env`, `db.sqlite3`, API keys, production configs

```bash
# Store API keys securely
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY sk-or-v1-xxx
# Stored in ~/.homegym_secrets (not in Git!)
```

**Production Checklist:**
- [ ] `DEBUG=False` in .env
- [ ] `SECRET_KEY` generated and unique
- [ ] `ALLOWED_HOSTS` correctly set
- [ ] SSL/HTTPS enabled
- [ ] Database backups configured
- [ ] Gunicorn behind Nginx

---

## ❓ FAQ

**Q: Can I use HomeGym without the AI Coach?**
A: Yes! All core features (training logging, plans, statistics, PDF reports) work without the AI Coach.

**Q: What are the costs?**
A: Self-hosted operation is free. The AI Coach costs ~€0.003 per plan generation via OpenRouter — this is optional.

**Q: Is there a mobile app?**
A: HomeGym is a PWA — installable on iOS and Android directly from the browser.

**Q: What languages are supported?**
A: German (default) and English. The language switcher is in the top-right navigation.

---

## 📄 License

MIT License – see [LICENSE](LICENSE)

---

<div align="center">
Made with ❤️ for HomeGym enthusiasts

🌐 **[gym.last-strawberry.com](https://gym.last-strawberry.com)** | [Deutsche README](README.md)
</div>
