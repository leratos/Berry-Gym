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
- **International Expansion:** English i18n (Week 9-10) for global reach

---

## 🎯 TIMELINE OVERVIEW

| Phase    | Focus                   | Coverage-Ziel | Status         |
|----------|-------------------------|---------------|----------------|
| Week 1   | Foundation & Safety     | 30%           | ✅ COMPLETE     |
| Week 2   | Testing & Views         | 40%           | ✅ COMPLETE     |
| Week 3   | Refactoring & Quality   | 50%           | ✅ COMPLETE     |
| Week 4   | Performance             | 60%           | ✅ COMPLETE     |
| Week 5-6 | Advanced & Polish       | 75%           | ✅ COMPLETE     |
| Week 7   | Pre-Launch Prep         | 80%+          | 🔄 IN PROGRESS  |
| Week 8   | 🚀 PUBLIC LAUNCH (DE)   | —             | 🎯 Goal         |
| Week 9-10| Internationalization    | —             | ✅ COMPLETE     |

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

## ✅ WEEK 3 – REFACTORING & QUALITY (COMPLETE)

**Ergebnis:** 38% → 50% Coverage, 408 Tests

### Abgeschlossene Phasen

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

---

## ✅ WEEK 4 – PERFORMANCE & OPTIMIZATION (COMPLETE)

**Ergebnis:** 50% → 60% Coverage, schnellere Ladezeiten

### Phase 4.1 – N+1 Query Detection & Fix ✅

**Abgeschlossen:** 2026-02-14  
**Branch:** `feature/phase-4-1-n-plus-one-queries`  
**Ergebnis:** 8 N+1-Stellen eliminiert, 6 neue Query-Count-Tests, 414 Tests grün

**Betroffene Bereiche:**
- Dashboard View: select_related für user, plan
- Training-Liste: prefetch_related für sätze, übung
- Exercise-Detail: prefetch_related für equipment
- Plan-Management: select_related optimiert

---

### Phase 4.2 – Database Indexes ✅

**Abgeschlossen:** 2026-02-15  
**Migration:** `0062_add_performance_indexes.py`

**Hinzugefügte Indexes:**
- Compound Index: `(user_id, datum)` auf Trainingseinheit
- Compound Index: `(user_id, erstellt_am)` auf Plan
- FK-Indexes: user, plan, exercise (automatisch)

**Ergebnis:** Query-Zeit 5-10x schneller für Stats-Views, MariaDB-kompatibel

---

### Phase 4.3 – Caching Strategy ✅

**Abgeschlossen:** 2026-02-15  
**Stack:** Django FileBasedCache

**Caching-Regeln:**
- Dashboard-Statistiken: 5 Minuten
- Übungs-Liste: 30 Minuten
- Plan-Templates: Unbegrenzt (manuell invalidiert)
- Cache-Invalidierung: via signals.py bei Datenänderungen

**Betroffene Views:**
- `dashboard_view`: Cache-Key `dashboard_stats_{user_id}`
- `uebungen_auswahl`: Cache-Key `exercise_list`
- `plan_templates`: Cache-Key `plan_templates_public`

---

### Phase 4.4 – Load Testing ✅

**Abgeschlossen:** 2026-02-15  
**Tool:** Locust 2.43.3

**Setup:**
- 3 Test-Szenarien: Browse, Training Session, Plan Management
- SLO-Auswertung: P95 < 500ms, P99 < 1000ms
- Baseline-Messung dokumentiert in `docs/LOAD_TESTING.md`

**Ergebnis:** 100 concurrent users erfolgreich getestet

---

## ✅ WEEK 5-6 – ADVANCED FEATURES & POLISH (COMPLETE)

**Ergebnis:** 60% → 53% Coverage, 541 Tests

**Coverage-Anmerkung:** Coverage sank von 60% auf 53% durch massive Code-Ergänzungen in Week 5-6 (AI Coach Optimierung, Scientific Sources, neue Features). Absolute Test-Anzahl stieg von 414 auf 541 (+127 Tests = +31%)!

---

### Phase 5.1 – Scientific Source System ✅

**Abgeschlossen:** 2026-02-16  
**Transcript:** `2026-02-16-03-40-38-phase-5-1-sources-adherence-bugfix.txt`

**Neue Features:**
- `TrainingSource` Model mit DOI, Key Findings (JSONField)
- Management Command: `load_training_sources`
- Integration in UI-Tooltips & wissenschaftliche Disclaimer
- Literatur-Datenbank: Schoenfeld, Israetel, Helms, NSCA, Kraemer & Ratamess

**Betroffene Dateien:**
- `core/models/training_source.py` (neu)
- `core/management/commands/load_training_sources.py` (neu)
- `core/fixtures/scientific_sources.json` (neu)
- Templates mit Tooltip-Integration

---

### Phase 5.2 – KI-Plangenerator Optimierung ✅

**Abgeschlossen:** 2026-02-16/17 (über mehrere Tage)  
**Transcripts:** 
- `2026-02-16-19-26-27-phase-5-2-llm-upgrade-gemini.txt`
- `phase-5-2-prompt-optimization-retry.txt`
- `phase-5-2-smart-retry-dynamic-tokens.txt`
- `2026-02-17-11-56-35-phase-5-2-streaming-sse-implementation.txt`
- Weitere Optimierungen

**Umgesetzte Verbesserungen:**

**1. LLM Upgrade:**
- Llama 3.1 70B → **Gemini 2.5 Flash** (via OpenRouter)
- Bessere Plan-Qualität, schneller, günstiger

**2. Eindeutige Plan-Namen:**
- LLM generiert spezifische Namen (Datum + Ziel + Fokus)
- Beispiel: "Kraft-Aufbau Intermediate – Brust/Rücken-Fokus"
- Tag-Namen differenziert: "Push A", "Pull A"

**3. Kontextbasierter Split-Typ:**
- Frequenz-Mapping: 2-3x/Woche → Fullbody/Upper-Lower, 4x → PPL, 5-6x → 4er-Split
- User-Eingabe: Häufigkeit als Pflichtfeld im Formular
- LLM begründet Split-Wahl

**4. Server-Sent Events (Streaming):**
- Echtzeit-Fortschrittsanzeige während Plan-Generierung
- `/ai/generate-plan-stream/` Endpoint
- JavaScript EventSource Integration

**5. Weitere Optimierungen:**
- Temperature-Fix (0.7 statt 1.0)
- Equipment-Filter (nur verfügbares Equipment)
- Smart Retry mit exponential backoff
- Dynamic max_tokens basierend auf Trainingstagen
- Weakness Coverage Validation (Post-Generation Check)
- Pause Time Feature für Übungen

**Betroffene Dateien:**
- `ai_coach/ai_config.py`
- `ai_coach/llm_client.py`
- `ai_coach/prompt_builder.py`
- `ai_coach/plan_generator.py`
- `core/views/ai_recommendations.py`
- `core/templates/core/ai_plan_generator.html`

---

### Phase 5.3 – AI/ML Testing ✅

**Abgeschlossen:** 2026-02-17  
**Branch:** `feature/phase-5-3-ai-ml-testing`  
**Ergebnis:** 541 Tests passed, 53% Coverage

**Neue Test-Suites:**
1. `test_koerpergewicht_support.py` (67 Tests)
   - Körpergewicht-Skalierung für 1RM Standards
   - 0.0-1.0 Faktor-System (Dips 0.7, Crunch 0.3, etc.)

2. `test_ml_trainer.py` (Neue Tests)
   - ML-Model Training & Prediction
   - Feature Engineering Tests

3. `test_plan_generator.py` (Erweitert)
   - AI Plan Generation mit Mocks
   - Equipment-Filtering
   - Split-Typ-Logik

**Coverage-Entwicklung:**
- Vorher: 474 Tests, ~50% Coverage
- Nachher: 541 Tests, 53% Coverage (+67 Tests)

**Betroffene Dateien:**
- `core/tests/test_koerpergewicht_support.py` (neu)
- `core/tests/test_ml_trainer.py` (neu)
- `ai_coach/tests/test_plan_generator.py` (erweitert)

---

### Phase 5.4 – Charts & Statistics Testing 🔄

**Status:** IN PROGRESS (nächste Phase)

**Geplant:**
- Chart-Datenkorrektheit & Edge Cases
- Volumen-Charts, 1RM-Progression, Muskelgruppen-Heatmaps
- Robuste Visualisierungen ohne Crashes (leere Daten, Einzelpunkte)

---

### Phase 5.5 – API Endpoints Testing ⏳

**Status:** Planned

---

### Phase 5.6 – Helper/Utils Testing ⏳

**Status:** Planned
**Ziel:** 90%+ Coverage für helpers/, utils/

---

## 🔄 WEEK 7 – PRE-LAUNCH PREPARATION (IN PROGRESS)

**Aktuell:** Phase 7.5 – i18n (Englisch)
**Ziel:** App auf Englisch verfügbar, Export danach ohne doppelte String-Arbeit

### Phase 7.1 – Rate Limiting KI-Endpoints ✅

**Status:** COMPLETE (2026-02-19)
- django-ratelimit + UserProfile-Counter
- 5 KI-Endpoints abgesichert (Plan, Stream, Guidance, Analyse, Optimierung)
- Limits via .env konfigurierbar (3/50/10 pro Tag)
- 17 Tests

### Phase 7.2 – Test-Medien aufräumen ✅

**Status:** COMPLETE (2026-02-19)
- 102 test_photo_*.png aus media/ gelöscht
- conftest.py: use_temp_media_root autouse-Fixture

### Phase 7.3 – Notizen erweitern ✅

**Status:** COMPLETE (2026-02-19)
- PlanUebung.notiz: Technik-Hinweis pro Übung (Migration 0069 auf 7.1-Branch)
- Satz.notiz: max_length entfernt
- Dashboard: Kommentar in Trainingsliste, Hinweisbox im Training
- Quick-Tags: +4 neue Emojis
- 12 Tests

### Phase 7.4 – Wochenübersicht Dashboard ✅

**Status:** COMPLETE (2026-02-19)
- UserProfile.trainings_pro_woche (Migration 0069 auf 7.4-Branch)
- _get_week_overview(): Mo–So mit Trainings-Status
- Dashboard-Karte mit Tagesstreifen + Fortschrittsbalken
- 15 Tests

### Phase 7.5 – Internationalisierung Englisch (i18n) ✅

**Status:** COMPLETE (21.02.2026)

**Ergebnis:** 790 Übersetzungen, 0 fuzzy, 0 untranslated

- Framework-Setup: settings.py, LocaleMiddleware, i18n_patterns, Language-Switcher
- 16 Templates mit {% trans %} markiert
- django.po/mo compiliert (via polib, kein GNU gettext erforderlich)
- L10N-Bug gefixt: Dezimalzahlen in JS mit {% localize off %} (Timer-Bug)
- Quote-Escaping-Fix: {% trans "..." %} in HTML-Attributen → {% trans '...' %}
- 100 fuzzy + 12 untranslated Einträge manuell korrigiert (Phase 7.5f)
- Regression-Tests: L10nJsDecimalTest (2 Tests), LanguageSwitcherTest (7 Tests)
- Dokumentation: README.md + README_EN.md erstellt/aktualisiert

### Phase 7.6 – Import/Export (Hevy-Format) ⏳

**Status:** Planned
- CSV-Export kompatibel mit Hevy/Strong
- "Bring your data" für Switcher

---

## 🌍 WEEK 8 – PUBLIC LAUNCH

**Pre-Launch (T-7):** Alle Tests grün, Security Audit clean, Sentry live, Backup getestet, Rollback-Plan ready
**Launch Day (T-0):** Deploy, Smoke Tests, Error Rate monitoren, Performance prüfen
**Post-Launch (T+7):** Sentry täglich, User Feedback, Hotfix-Prozess etabliert

---

## 🌍 WEEK 9-10 – INTERNATIONALIZATION (ENGLISH LAUNCH)

**Ziel:** App auf Englisch verfügbar machen, internationale Expansion

### Warum Englisch?
- **Größere Zielgruppe:** 500M+ potenzielle User statt 80M (DACH)
- **Open Source Community:** 5-10x mehr Contributors aus der ganzen Welt
- **Marketing:** "AI-powered fitness tracker" → bessere Suchbarkeit & Reichweite
- **Bereits vorbereitet:** Code/Comments auf Englisch, Django i18n eingebaut

---

### Phase 7.1 – i18n Framework Setup

**Aufwand:** 2-4 Stunden

**Tasks:**
- Django i18n aktivieren in `config/settings.py`:
  - `LANGUAGE_CODE = 'de'` (Default)
  - `LANGUAGES = [('de', 'Deutsch'), ('en', 'English')]`
  - `USE_I18N = True`
  - `LOCALE_PATHS = [BASE_DIR / 'locale']`
- `django.middleware.locale.LocaleMiddleware` einrichten
- Language-Switcher UI in `base.html` (Dropdown in Navigation)
- URL-Konfiguration für Sprachwechsel (`/i18n/setlang/`)

**Akzeptanzkriterien:**
- User kann zwischen DE/EN wechseln (Session-basiert)
- Sprachwahl bleibt erhalten beim Seitenwechsel
- Default-Sprache ist Deutsch

**Betroffene Dateien:**
- `config/settings.py`
- `config/urls.py`
- `core/templates/base.html`

---

### Phase 7.2 – Template Lokalisierung

**Aufwand:** 8-12 Stunden

**Tasks:**
- `{% load i18n %}` in allen Templates (55+ Dateien)
- `{% trans "Text" %}` für statische UI-Strings
- `{% blocktrans %}` für dynamische Texte mit Variablen
- `.po` Dateien erstellen:
  - `django-admin makemessages -l de`
  - `django-admin makemessages -l en`
- Übersetzungen in `.po` Dateien eintragen (~200-300 Strings)
- `django-admin compilemessages` ausführen

**Kritische Bereiche:**
- Navigation & Buttons (Dashboard, Training, Pläne, etc.)
- Form-Labels & Validierungs-Fehler
- Success/Error-Messages (Toasts)
- Modal-Dialoge (Bestätigungen, Warnungen)
- Chart-Labels & Statistik-Überschriften

**Akzeptanzkriterien:**
- Alle UI-Texte sind übersetzt (0 hardcoded deutsche Strings)
- Umlaute funktionieren korrekt (ä, ö, ü, ß)
- Pluralisierung funktioniert (`1 Satz` vs. `2 Sätze` / `1 set` vs. `2 sets`)

**Betroffene Dateien:**
- `core/templates/` (alle 55+ Templates)
- `locale/de/LC_MESSAGES/django.po`
- `locale/en/LC_MESSAGES/django.po`

---

### Phase 7.3 – Model & Choice Lokalisierung

**Aufwand:** 4-6 Stunden

**Tasks:**
- `gettext_lazy()` für Model-Choices:
  - `MUSKELGRUPPEN` → "Brust" / "Chest"
  - `BEWEGUNGS_TYP` → "Compound" / "Isolation"
  - `EQUIPMENT_CHOICES` → "Langhantel" / "Barbell"
  - `GEWICHTS_TYP` → "Gesamt" / "Total"
- Model `verbose_name` & `verbose_name_plural` übersetzen
- Form-Labels & Help-Texts in `forms.py`
- Admin-Interface Texte (falls relevant)

**Akzeptanzkriterien:**
- Alle Dropdowns zeigen übersetzte Werte
- Admin bleibt auf Deutsch (oder auch übersetzt)
- Datenbank-Werte bleiben unverändert (nur Display übersetzt)

**Betroffene Dateien:**
- `core/models/constants.py`
- `core/models/*.py` (alle Model-Klassen)
- `core/forms.py` (falls vorhanden)

---

### Phase 7.4 – Content Lokalisierung

**Aufwand:** 6-10 Stunden

**Tasks:**
- **Übungs-Beschreibungen** (113 Übungen):
  - Fitness-Fachbegriffe korrekt übersetzen
  - z.B. "Schulterblätter zusammenziehen" → "Retract shoulder blades"
  - Anatomische Begriffe: "Brust" → "Chest", "Rücken" → "Back"
- **README_EN.md** erstellen:
  - Feature-Übersicht
  - Installation (englisch)
  - Usage Examples
- **Scientific Sources:**
  - Meist schon auf Englisch (DOI, Journals)
  - `TrainingSource.key_findings` übersetzen (falls auf Deutsch)
- **Email-Templates** (falls vorhanden):
  - Welcome Email, Password Reset, etc.

**Akzeptanzkriterien:**
- Übungs-Beschreibungen sind korrekt & verständlich
- README_EN.md ist vollständig & professionell
- Keine Google-Translate-Qualität (manuelle Review!)

**Betroffene Dateien:**
- `core/fixtures/initial_exercises.json` (Update mit EN-Beschreibungen)
- `README_EN.md` (neu)
- `core/models/training_source.py` (ggf. Übersetzungen)

---

### Phase 7.5 – AI Coach Lokalisierung

**Aufwand:** 4-6 Stunden (optional in Phase 7, kann auch später)

**Tasks:**
- `prompt_builder.py` → Sprach-Parameter hinzufügen
- Prompts mit `{% trans %}` oder Template-basiert
- Plan-Generator UI: Sprache aus User-Einstellung
- Live Guidance: Antworten in gewählter Sprache

**Herausforderung:**
- Gemini 2.5 Flash kann Deutsch & Englisch
- Prompt-Qualität in Englisch testen

**Akzeptanzkriterien:**
- AI Coach antwortet in gewählter Sprache
- Prompt-Qualität ist vergleichbar (DE vs. EN)

**Betroffene Dateien:**
- `ai_coach/prompt_builder.py`
- `ai_coach/plan_generator.py`
- `core/views/ai_recommendations.py`

---

### Phase 7.6 – Testing & QA

**Aufwand:** 4-6 Stunden

**Tasks:**
- **Language-Switch Tests:**
  - Sprachwechsel funktioniert auf allen Seiten
  - Session bleibt konsistent
- **Übersetzungs-Coverage:**
  - Scan nach unübersetzten Strings (`grep -r "{% trans" templates/`)
  - Prüfen: Fehlen Strings in `.po` Dateien?
- **PDF-Report auf Englisch:**
  - Labels, Chart-Titel, Body-Map-Beschreibungen
- **Edge Cases:**
  - Datum/Zeit-Formate (DE: dd.mm.yyyy, EN: mm/dd/yyyy)
  - Zahlen-Formatierung (DE: 1.234,56 / EN: 1,234.56)

**Akzeptanzkriterien:**
- 0 hardcoded Strings auf produktiven Seiten
- PDF-Report funktioniert in beiden Sprachen
- Keine Layout-Breaks durch längere englische Texte

**Betroffene Dateien:**
- `core/tests/test_i18n.py` (neu)
- `core/views/export.py` (PDF-Generierung)

---

### Phase 7.7 – Documentation & Launch

**Aufwand:** 2-3 Stunden

**Tasks:**
- **README_EN.md** finalisieren
- **CONTRIBUTING_EN.md** (optional, wenn viele Contributors)
- **GitHub:** Language-Badges hinzufügen
  - `![Languages](https://img.shields.io/badge/Languages-DE%20%7C%20EN-blue)`
- **Deployment:**
  - `django-admin compilemessages` auf Server
  - `.mo` Dateien committen oder Server-seitig generieren
- **Announcement:**
  - Reddit, HackerNews, ProductHunt
  - "AI-powered fitness tracker with local LLM support - now in English!"

**Akzeptanzkriterien:**
- README_EN.md ist vollständig & professionell
- GitHub-Seite zeigt beide Sprachen
- Deployment-Prozess funktioniert

**Betroffene Dateien:**
- `README_EN.md` (neu)
- `CONTRIBUTING_EN.md` (optional)
- `.github/workflows/ci.yml` (ggf. `compilemessages` Step)

---

## 📊 PHASE 7 - AUFWANDSTABELLE

| Task                      | Aufwand    | Priorität | Status    |
|---------------------------|------------|-----------|-----------|
| 7.1 - Framework Setup     | 2-4h       | Hoch      | ⏳ Planned |
| 7.2 - Template i18n       | 8-12h      | Hoch      | ⏳ Planned |
| 7.3 - Model Choices       | 4-6h       | Mittel    | ⏳ Planned |
| 7.4 - Content (Übungen)   | 6-10h      | Hoch      | ⏳ Planned |
| 7.5 - AI Coach (optional) | 4-6h       | Niedrig   | ⏳ Planned |
| 7.6 - Testing & QA        | 4-6h       | Hoch      | ⏳ Planned |
| 7.7 - Documentation       | 2-3h       | Mittel    | ⏳ Planned |
| **TOTAL**                 | **30-47h** | **≈1-1.5 Wochen** | |

---

## 🎯 PHASE 7 - SUCCESS CRITERIA

**Must-Have:**
- ✅ UI vollständig auf Englisch (Templates, Forms, Messages)
- ✅ 113 Übungs-Beschreibungen übersetzt
- ✅ README_EN.md vorhanden & vollständig
- ✅ Language-Switcher funktioniert
- ✅ Tests grün in beiden Sprachen

**Nice-to-Have:**
- 🔄 AI Coach auf Englisch (kann auch später)
- 🔄 URL-i18n (`/en/dashboard`, `/de/dashboard`)
- 🔄 Datum/Zeit-Formate lokalisiert

**Optional (Post-Launch):**
- ⏳ Weitere Sprachen (ES, FR, IT, PT)
- ⏳ Community-Übersetzungen (Crowdin)
- ⏳ RTL-Support (AR, HE)

---

## 🚀 PHASE 7 - LAUNCH STRATEGY

**Pre-Launch (T-7):**
- Alle Übersetzungen reviewed (kein Google Translate!)
- Native Speaker Feedback eingeholt
- Screenshots für README_EN.md erstellt

**Launch Day (T-0):**
- README_EN.md live
- GitHub Language-Badge
- Social Media Announcement (Reddit, HN, ProductHunt)

**Post-Launch (T+7):**
- User-Feedback sammeln (falsche Übersetzungen?)
- Issue-Labels: `i18n`, `translation`
- Community-Übersetzungen erwägen

---

## 📊 SUCCESS METRICS

**Technical Quality (Week 1-7):**

| Metrik          | Ziel      |
|-----------------|-----------|
| Test Coverage   | 80%+      |
| Tests Passing   | 100%      |
| P95 Response    | <500ms    |
| Error Rate      | <0.1%     |
| Uptime          | 99.9%     |

**International Expansion (Week 9-10):**

| Metrik                    | Ziel      |
|---------------------------|-----------|
| Translation Coverage      | 100%      |
| Übungen übersetzt (EN)    | 113/113   |
| Native Speaker Review     | ✓         |
| README Languages          | DE + EN   |
| GitHub Stars (6 Monate)   | 100+      |

---

## 📁 KEY FILES

- `core/tests/` – alle Test-Suites
- `core/models/` – aufgeteilte Models (seit Phase 3.1)
- `core/templates/base.html` – Base Template (seit Phase 3.2)
- `core/views/` – alle Views (16 Dateien)
- `config/settings.py` – Konfiguration
- `docs/journal.txt` – aktueller Arbeitsstand

---

**Last Updated:** 2026-02-17
**Nächste Phase:** 5.4 – Charts & Statistics Testing
