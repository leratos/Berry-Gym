# 🚀 HomeGym - Project Roadmap: Beta → Production Launch

**Projekt:** Complete Project Restructuring & Production Preparation
**Startdatum:** 09.02.2026
**Projektpfad:** `C:\Dev\Berry-Gym`
**Python:** 3.12.3 via `.venv` (py -3.12)
**Ziel:** Production-ready application for public launch

---

## 📊 EXECUTIVE SUMMARY

- Test Coverage: 14% → 80%+
- Code Refactoring: models.py split, base.html template
- Performance: N+1 query elimination, caching, indexes
- Scientific Foundation: Training science sources & citations
- Production Ready: Security, monitoring, deployment automation
- Public Launch: Marketing-ready, professional, scalable

---

## 🎯 TIMELINE OVERVIEW

| Phase    | Focus                   | Coverage-Ziel | Status         |
|----------|-------------------------|---------------|----------------|
| Week 1   | Foundation & Safety     | 30%           | ✅ COMPLETE     |
| Week 2   | Testing & Views         | 40%           | ✅ COMPLETE     |
| Week 3   | Refactoring & Quality   | 50%           | 🔄 IN PROGRESS  |
| Week 4   | Performance             | 60%           | ⏳ Planned      |
| Week 5-6 | Advanced & Polish       | 75%           | ⏳ Planned      |
| Week 7   | Pre-Launch Prep         | 80%+          | ⏳ Planned      |
| Week 8   | 🚀 PUBLIC LAUNCH        | —             | 🎯 Goal         |

---

## ✅ WEEK 1 – FOUNDATION & PRODUCTION SAFETY (COMPLETE)

**Ergebnis:** 14% → 30.48% Coverage, 75 Tests

- Testing Infrastructure: conftest.py, factories.py, pytest.ini, pre-commit (Black/isort/flake8)
- Core Test Suites: test_plan.py, test_training_views.py, test_body_tracking.py, test_plan_management.py, test_integration.py
- Sentry Error Tracking: Live in Production (SENTRY_DSN in .env)
- Scientific Disclaimer System: Model + Context Processor + Banner (29 Templates, Dark Mode)
- Bugs gefunden: Dark Mode Readability Bug (durch User-Feedback)

---

## ✅ WEEK 2 – TESTING & VIEW COVERAGE (COMPLETE)

**Ergebnis:** 30.48% → 38% Coverage, 247 Tests

| Phase | Tests  | Inhalt                                        |
|-------|--------|-----------------------------------------------|
| 2.5   | +30    | Export (CSV/PDF), Auth, Beta-Codes, Waitlist  |
| 2.6   | +27    | Exercise Library, Favoriten, Custom-Übungen   |
| 2.7   | +20    | Equipment Management, Staff-Import/Export     |
| 2.8   | +30    | Cardio, Config, Static Pages, PWA Endpoints   |

Bugs gefunden: `toggle_favorit` hatte kein `@login_required` (Security-Fix)

---

## 🔄 WEEK 3 – REFACTORING & QUALITY (IN PROGRESS)

**Ziel:** 38% → 50% Coverage
**Aktuell:** 47% Coverage, 408 Tests

### ✅ Abgeschlossene Phasen

| Phase  | Ergebnis                                                                     |
|--------|------------------------------------------------------------------------------|
| 3.1    | models.py (1079 Zeilen) → 11 Module in core/models/, 0 Import-Änderungen    |
| 3.1b   | 27 neue Tests (Dashboard, TrainingList, Delete, Stats, ExerciseStats)        |
| 3.1c   | test_context_helpers.py gefixt (392 Tests, 0 Fehler)                        |
| 3.2    | base.html erstellt, 26/26 Templates migriert (Commits eba7083–fe50aa5)       |
| 3.3    | View-Signaturen annotiert (HttpRequest→HttpResponse), mypy.ini erstellt      |
| 3.4.1  | CC-Reduktion Grade D/E/F (CC>20): dashboard 74→<10, export_pdf 57→<10 u.a.  |
| 3.4.2  | CC-Reduktion Grade C (CC 11–20): 26 Funktionen in 10 Dateien, alle CC < 11  |
| 3.5    | Test Quality: 53 Docstrings ergänzt, parametrize eingeführt, 4 Imports bereinigt |

Bugs gefunden: `delete_training` hatte keinen POST-Guard (GET löschte Daten)

### ⏳ Offene Phasen

---

## ⚡ WEEK 4 – PERFORMANCE & OPTIMIZATION (60% TARGET)

**Ziel:** 50% → 60% Coverage, schnellere Ladezeiten

#### Phase 4.1 – N+1 Query Detection & Fix 🔥 ← NÄCHSTE PHASE

**Tools:** django-debug-toolbar, nplusone
**Kritische Views:** dashboard, plan_details, training_session, stats_exercise
**Vorgehen:** select_related / prefetch_related, Query-Count-Tests

### Phase 4.2 – Database Indexes

**Kandidaten:** FK-Felder (user, plan, exercise), Datums-Filter, Compound Index (user+datum)
**Erwartung:** Query-Zeit 10x schneller für Stats-Views

### Phase 4.3 – Caching Strategy

**Was cachen:** Exercise-Liste, User-Statistiken (5 min), 1RM-Standards, Plan-Templates
**Stack:** Django Cache Framework, optional Redis

### Phase 4.4 – Load Testing

**Tool:** Locust
**Ziel:** P95 < 500ms, P99 < 1000ms, 100 concurrent users

---

## 🌟 WEEK 5-6 – ADVANCED FEATURES & POLISH (75% TARGET)

**Ziel:** 60% → 75% Coverage

### Phase 5.1 – Scientific Source System 🔬

Aktuell: "Eingeschränkte wissenschaftliche Basis" – zu vage für Public Launch.

**Neue Model:** `TrainingSource` (Kategorie, Titel, Autoren, Jahr, DOI, Key Findings als JSONField)
**Literatur:** Schoenfeld (2016), Israetel (2020), Helms (2018), NSCA Guidelines, Kraemer & Ratamess (2004)
**Integration:** Management Command `load_training_sources`, UI-Tooltips, aktualisierte Disclaimer-Texte

### Phase 5.2 – AI/ML Testing

- test_ml_models.py, test_ai_coach.py, test_plan_generator.py
- Externe API-Calls (Ollama/OpenRouter) mit Fixtures mocken

### Phase 5.3 – Charts & Statistics Testing

- Chart-Datenkorrektheit, Edge Cases (leere Daten, Einzelpunkt)

### Phase 5.4 – API Endpoints Testing

- Plan Sharing API, Stats API, Auth

### Phase 5.5 – Helper/Utils Testing

- Ziel: 90%+ Coverage für helpers/, utils/

---

## 🚀 WEEK 7 – PRE-LAUNCH PREPARATION (80%+ TARGET)

**Ziel:** 75% → 80%+ Coverage

### Phase 6.1 – Security Audit

- OWASP Top 10, django-axes Rate Limiting, bandit, Safety (Dependencies)
- File Upload Validation, Session Security

### Phase 6.2 – Performance Benchmarks

- Lighthouse, WebPageTest
- Ziele: <2s Page Load, <500ms API (P95), <50 Queries/Page, <512MB/Worker

### Phase 6.3 – Deployment Automation

- GitHub Actions: Test → Quality Checks → Staging → Production
- Smoke Tests nach Deploy

### Phase 6.4 – Monitoring

- Sentry ✅ bereits live
- Slow Query Monitoring, Server Metrics (CPU/RAM/Disk)

### Phase 6.5 – Documentation

- docs/DEPLOYMENT.md, docs/API.md, docs/ARCHITECTURE.md
- README.md mit Screenshots

---

## 🌍 WEEK 8 – PUBLIC LAUNCH

**Pre-Launch (T-7):** Alle Tests grün, Security Audit clean, Sentry live, Backup getestet, Rollback-Plan ready
**Launch Day (T-0):** Deploy, Smoke Tests, Error Rate monitoren, Performance prüfen
**Post-Launch (T+7):** Sentry täglich, User Feedback, Hotfix-Prozess etabliert

---

## 📊 SUCCESS METRICS

| Metrik          | Ziel      |
|-----------------|-----------|
| Test Coverage   | 80%+      |
| Tests Passing   | 100%      |
| P95 Response    | <500ms    |
| Error Rate      | <0.1%     |
| Uptime          | 99.9%     |

---

## 📁 KEY FILES

- `core/tests/` – alle Test-Suites
- `core/models/` – aufgeteilte Models (seit Phase 3.1)
- `core/templates/base.html` – Base Template (seit Phase 3.2)
- `core/views/` – alle Views (16 Dateien)
- `config/settings.py` – Konfiguration
- `docs/journal.txt` – aktueller Arbeitsstand

---

**Last Updated:** 2026-02-14
**Nächste Phase:** 4.1 – N+1 Query Detection & Fix
