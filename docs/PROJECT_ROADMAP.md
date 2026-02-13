# 🚀 HomeGym - Project Roadmap: Beta → Production Launch

**Projekt:** Complete Project Restructuring & Production Preparation  
**Startdatum:** 09.02.2026  
**Aktueller Status:** Week 3 - Phase 3.4.1 COMPLETE (47% Coverage, 406 Tests grün)
**Projektpfad:** `C:\Dev\Berry-Gym` (aus OneDrive migriert am 2026-02-12)
**Python:** 3.12.3 via `.venv` (py -3.12)  
**Ziel:** Production-ready application for public launch

---

## 📊 **EXECUTIVE SUMMARY**

**This is NOT just testing** - it's a complete project restructuring:
- ✅ Test Coverage: 14% → 80%+
- 🔧 Code Refactoring: models.py split, base.html template
- ⚡ Performance: N+1 query elimination, caching, indexes
- 🔬 Scientific Foundation: Training science sources & citations
- 🚀 Production Ready: Security, monitoring, deployment automation
- 🌍 Public Launch: Marketing-ready, professional, scalable

---

## 🎯 **TIMELINE OVERVIEW**

| Phase | Duration | Focus | Coverage Goal | Status |
|-------|----------|-------|---------------|--------|
| **Week 1** | ✅ DONE | Foundation & Safety | 30.48% | ✅ COMPLETE |
| **Week 2** | Feb 11-17 | Testing & Views | 40% | 🔄 Phase 2.8 DONE (38%) |
| **Week 3** | Feb 18-24 | Refactoring & Quality | 50% | 🔄 Phase 3.1 DONE (38%) |
| **Week 4** | Feb 25-Mar 3 | Performance | 60% | ⏳ Planned |
| **Week 5-6** | Mar 4-17 | Advanced & Polish | 75% | ⏳ Planned |
| **Week 7** | Mar 18-24 | Pre-Launch Prep | 80%+ | ⏳ Planned |
| **Week 8** | Mar 25+ | 🚀 PUBLIC LAUNCH | - | 🎯 Goal |

---

## ✅ **WEEK 1 - FOUNDATION & PRODUCTION SAFETY (COMPLETE)**

**Duration:** Feb 9-11, 2026  
**Coverage:** 14% → 30.48% (Codecov) / 22% (pytest-cov core/)  
**Status:** ✅ **100% COMPLETE**

### 🎯 Week 1 Goals:
- [x] ✅ Test Coverage: 30%+ (Achieved: 30.48%)
- [x] ✅ Sentry Error Tracking: Production-ready
- [x] ✅ Scientific Disclaimers: Implemented & visible
- [x] ✅ Code Formatting: Black + isort + flake8

### 📦 Deliverables:

#### 1. Testing Infrastructure (Phase 1)
- ✅ `conftest.py` - Shared fixtures & pytest config
- ✅ `factories.py` - Factory Boy factories (97% coverage)
- ✅ `pytest.ini` - Test configuration
- ✅ `.pre-commit-config.yaml` - Quality checks (Black, isort, flake8)
- ✅ CI/CD with Codecov integration

#### 2. Core Test Suites (Phase 2.1-2.4)
- ✅ `test_plan.py` - 13 tests (Plan CRUD, sharing, favoriting)
- ✅ `test_training_views.py` - 18 tests (Training sessions, sets, superset)
- ✅ `test_body_tracking.py` - 17 tests (Körperwerte, progress photos)
- ✅ `test_plan_management.py` - 16 tests (Plan creation, templates, groups)
- ✅ `test_integration.py` - 4 E2E tests (Full workflows)
- ✅ `test_disclaimers.py` - 7 tests (Context processor, URL filtering)
- **Total:** 75 tests, all passing ✅

#### 3. Production Safety Features
- ✅ **Sentry Error Tracking:**
  - Configured in `settings.py` (lines 305-336)
  - SENTRY_DSN in production `.env`
  - Test script: `dev-scripts/test_sentry.py`
  - **Status:** 🟢 LIVE in production

- ✅ **Scientific Disclaimer System:**
  - Model: `ScientificDisclaimer` (94% coverage)
  - Context Processor: `core.context_processors.disclaimers` (100%)
  - Template: `includes/disclaimer_banner.html`
  - 3 default disclaimers loaded (1RM, Fatigue, General)
  - **Visible on 29 templates via `global_footer.html`**
  - ✅ Dark mode support (fixed readability bug)

#### 4. Code Quality
- ✅ Black formatting (line length 100)
- ✅ isort import sorting
- ✅ flake8 linting (E501 ignored)
- ✅ Pre-commit hooks active
- ✅ All commits pass quality checks

### 📊 Coverage Breakdown:
- **Codecov (Project-wide):** 30.48% (+30.49% vs 3 months ago)
- **pytest-cov (core/ app):** 22%
- **Key Files:**
  - `context_processors.py`: 100%
  - `factories.py`: 97%
  - `test_disclaimers.py`: 98%
  - `models_disclaimer.py`: 94%
  - `models.py`: 75%

### 📝 Documentation:
- ✅ `docs/DISCLAIMER_SYSTEM.md` - Complete integration guide
- ✅ `dev-scripts/test_sentry.py` - Sentry verification tool
- ✅ README.md updated with testing instructions

### 🎓 Lessons Learned:
1. **Context processors > template refactoring** for quick wins
2. **global_footer.html** was the perfect integration point (29 templates)
3. **Dark mode testing** is critical - caught major readability bug
4. **Codecov vs pytest-cov** measure different scopes (project vs app)
5. **User feedback** (dark mode bug) > automated tests for UI issues

---

## 🔄 **WEEK 2 - TESTING & VIEW COVERAGE (40% TARGET)**

**Duration:** Feb 11-17, 2026  
**Coverage Goal:** 30.48% → 40%  
**Status:** 🔄 **IN PROGRESS** (Phase 2.5 ✅ | Phase 2.6 ✅ | Phase 2.7 ✅ | Phase 2.8 ✅ COMPLETE - 38%)

### 🎯 Week 2 Goals:
- [ ] Coverage: 40%+ (Codecov project-wide)
- [ ] Complete all view tests (export, auth, exercise library)
- [ ] Template rendering validation
- [ ] Form submission tests
- [ ] User workflow integration tests

### 📋 Remaining Phase 2 Sub-Phases:

#### **Phase 2.5 - Export & Auth Tests** ✅ COMPLETE
**Time Estimate:** 2-3 days  
**Tests Added:** 30 tests (14 export + 16 auth)  
**Coverage Impact:** 30.48% → 33% (+2.52%)

**Test Files Created:**
- ✅ `test_export.py` - 14 tests (PDF/CSV export functionality)
  - Training session CSV export (4 tests)
  - Training session PDF export (3 tests)
  - Plan PDF export (3 tests)
  - Exercise export/import (4 tests)
  - File generation & validation
  - User data isolation

- ✅ `test_auth.py` - 16 tests (Authentication & authorization)  
  - Login/logout flows (4 tests)
  - Registration & beta invite codes (4 tests)
  - Password reset flow (2 tests)
  - Permission checks (3 tests)
  - Waitlist functionality (3 tests)

**Test Results:**
- ✅ **167 passing tests** (total test suite)
- ✅ **30 new passing tests** (Phase 2.5)
- ⚠️ 3 failing in old test_refactoring.py (factory updates needed)
- ✅ Coverage: 33% (goal was 34% - slightly under but acceptable)

**Key Achievements:**
- All Export views tested (CSV, PDF)
- Auth flow completely covered
- Beta code system validated
- User permission isolation verified
- File generation working

**Lessons Learned:**
- Factory parameter names critical (einheit= not trainingseinheit=)
- Model field names matter (bezeichnung= not name=)
- client.force_login(user) is standard pattern
- Content-Type includes charset (text/csv; charset=utf-8)

---

#### **Phase 2.6 - Exercise Library Tests** ✅ COMPLETE
**Completed:** 2026-02-11
**Tests Added:** 27 tests
**Coverage Impact:** 34% → 35%
**Total Tests:** 197 passing, 4 skipped

**Test File:** `test_exercise_library.py`

**Was getestet:**
- `uebungen_auswahl`: Login-Schutz, Seite lädt, globale Übungen, eigene Custom-Übungen sichtbar, fremde Custom-Übungen NICHT sichtbar
- `muscle_map`: Login-Schutz, Seite lädt
- `uebung_detail` + `exercise_detail`: Login-Schutz, Laden, 404 bei unbekannter ID
- `toggle_favorit` + `toggle_favorite`: Hinzufügen, Entfernen, JSON-Antwort, 404-Handling
- `create_custom_uebung`: Erfolg, fehlende Bezeichnung/Muskelgruppe → 400, Duplikat-Schutz, User-Isolation, is_custom Flag
- `get_alternative_exercises`: Login-Schutz, JSON-Response, 404

**Bug gefunden & gefixt:**
- `toggle_favorit` (exercise_library.py:398) hatte KEIN `@login_required` Decorator
- AnonymousUser-Zugriff führte zu 500 Internal Server Error statt 302 Redirect
- Fix: `@login_required` hinzugefügt

**Lessons Learned:**
- Tests finden echte Security-Bugs (fehlende @login_required)
- Gleichnamige Views (toggle_favorit vs toggle_favorite) separat testen
- Immer Login-Schutz aller Write-Endpoints testen

---

#### **Phase 2.7 - Exercise Management Tests** ✅ COMPLETE
**Completed:** 2026-02-11
**Tests Added:** 20 tests
**Coverage Impact:** 35% → 37% (+2%)
**Total Tests:** 217 passing, 4 skipped

**Test File:** `test_exercise_management.py`

**Was getestet:**
- `equipment_management`: Login-Schutz, Seite lädt, Context mit Equipment-Kategorien, Statistiken
- `toggle_equipment`: Login-Schutz, Hinzufügen, Entfernen, AJAX-JSON-Response, Non-AJAX Redirect, 404 bei unbekanntem Equipment
- `export_uebungen` (Staff-only): Nicht-Staff → 302, JSON-Export, JSON-Dateiname, CSV-Export, ungültiges Format → 400
- `import_uebungen` (Staff-only): Nicht-Staff → 302, nur POST erlaubt, ohne Datei → Redirect, JSON-Import erstellt Übungen, ungültiges JSON → Redirect

**Technische Details:**
- Equipment.name ist ein Choices-Feld → direkt `Equipment.objects.get_or_create(name="LANGHANTEL")` statt Factory
- Staff-Zugriff: `UserFactory(is_staff=True)`
- AJAX-Detection via `HTTP_X_REQUESTED_WITH: "XMLHttpRequest"` Header
- Import via `SimpleUploadedFile` mit JSON-Content

**Lessons Learned:**
- Factory-Sequence-Namen scheitern bei Choices-Feldern
- AJAX-Header explizit in Tests setzen
- File-Upload-Tests mit `SimpleUploadedFile` und `content_type="application/json"`

---

#### **Phase 2.8 - Config & Cardio Tests** ✅ COMPLETE
**Completed:** 2026-02-11
**Tests Added:** 30 tests
**Coverage Impact:** 37% → 38% (+1%)
**Total Tests:** 247 passing, 4 skipped

**Test File:** `test_config_cardio.py`

**Was getestet:**

`TestStaticPages` (4 Tests):
- `impressum` & `datenschutz` ohne Login erreichbar
- `metriken_help` Login-Schutz + Laden

`TestPwaEndpoints` (5 Tests):
- `service_worker`, `manifest`, `favicon` antworten korrekt
- Content-Type-Validierung (JS, JSON, PNG)
- Robuste Tests (200 oder 404 je nach Datei-Existenz)

`TestGetLastSet` (5 Tests):
- Login-Schutz
- Kein Satz → `success: false`
- Satz vorhanden → Progression-Hints in Response
- Aufwärmsätze werden ignoriert
- User-Isolation (fremde Sätze nicht sichtbar)

`TestCardioList` (6 Tests):
- Login-Schutz, Laden
- User-Isolation (nur eigene Einheiten)
- Statistiken im Context (total_minuten, total_einheiten)
- 30-Tage-Filter greift korrekt
- `?all=1` zeigt alle Einheiten

`TestCardioAdd` (6 Tests):
- Login-Schutz, GET zeigt Formular
- POST erstellt Einheit → 302
- POST ohne Aktivität → kein Objekt erstellt
- POST mit ungültiger Dauer → kein Objekt erstellt
- POST mit Dauer=0 → kein Objekt erstellt

`TestCardioDelete` (4 Tests):
- Login-Schutz (nicht eingeloggt → kein Delete)
- POST löscht eigene Einheit
- Fremde Einheit → 404 (User-Isolation!)
- GET-Request → Redirect, kein Delete

**Coverage-Highlights:**
- `cardio.py`: **96%** Coverage
- `config.py`: **74%** Coverage

**Hinweis:** `Satz` unused import entfernt (war nicht nötig da SatzFactory direkt benutzt)

---

### 🎯 Week 2 Success Metrics:
- ✅ 40%+ coverage (Codecov)
- ✅ All Phase 2 sub-phases complete (2.5-2.8)
- ✅ ~54 new tests (75 → 129 total)
- ✅ All critical views tested
- ✅ Form validation comprehensive

---

## 🛠️ **WEEK 3 - CODE QUALITY & REFACTORING (50% TARGET)**

**Duration:** Feb 18-24, 2026 (started Feb 11)  
**Coverage Goal:** 40% → 50%  
**Focus:** Code structure, maintainability, technical debt

### 🎯 Week 3 Goals:
- [ ] Coverage: 50%+
- [x] ✅ models.py refactored into multiple files (Phase 3.1 DONE)
- [ ] base.html template created
- [ ] Type hints: 80%+ of functions
- [ ] Cyclomatic complexity: <10 for all functions
- [ ] Test quality improvements

### 📋 Phase 3 Sub-Phases:

#### **Phase 3.1 - Model Refactoring** ✅ COMPLETE

---

#### **Phase 3.1b - Training Stats Test Suite** ✅ COMPLETE
**Abgeschlossen:** 2026-02-11
**Tests Added:** 27 Tests
**Total Tests:** 383 passing, 9 pre-existing errors in test_context_helpers.py (not caused here)

**Test File:** `test_training_stats_extended.py`

**Was getestet:**
- `TestDashboard` (9 Tests): Login-Schutz, Laden, Context-Keys, Wochenzählung, User-Isolation, Gesamtzählung, Aufwärmsatz-Filter, Favoriten Top-3, Streak=0
- `TestTrainingList` (4 Tests): Login-Schutz, Laden, User-Isolation (context key `trainings_data`), leere Liste
- `TestDeleteTraining` (4 Tests): Login-Schutz, Owner-Delete, Fremde-404, GET-löscht-nicht
- `TestTrainingStats` (4 Tests): Login-Schutz, Laden ohne/mit Daten, User-Isolation
- `TestExerciseStats` (6 Tests): Login-Schutz, Laden, 404 bei unbekannter ID, mit Satz-Daten, User-Isolation, Context-Uebung-Objekt

**🔴 Bug gefunden & gefixt:**
- `delete_training` View hatte KEINEN `request.method == "POST"` Check
- GET-Request auf `/training/<id>/delete/` löschte die Trainingseinheit sofort
- Fix: `if request.method == "POST":` Guard hinzugefügt
- **Sicherheitsrelevant:** Link-Prefetching durch Browser oder "Open in new tab" hätte Daten gelöscht

**Technische Details:**
- Context-Key der training_list View ist `trainings_data` (Liste von Dicts, nicht QuerySet)
- `gesamt_saetze` im Dashboard ignoriert Aufwärmsätze korrekt
- `favoriten` sind Top-3 nach Häufigkeit (Aufwärmsätze & Deload-Trainings ausgeschlossen)

**Lessons Learned:**
- Tests finden echte Sicherheits-Bugs (GET löscht Daten)
- Context-Key-Namen immer im View prüfen, nicht raten
- Antworten in Chunks schreiben (≤150 Zeilen) vermeidet Token-Abbrüche

---
**Abgeschlossen:** 2026-02-11  
**Time Estimate:** 1-2 days → **1 day**  
**Impact:** Massive maintainability improvement

**Ergebnis:**
- `core/models.py` (1.079 Zeilen) → `core/models/` Package mit 11 Modulen
- **0 Import-Änderungen** in views/tests/admin nötig (`__init__.py` re-exportiert alles)
- **247/247 Tests grün** nach Refactoring (Safety-Net hielt)
- Black/isort Hooks automatisch angewendet
- Commit: 1a2cdaf

**Neue Struktur:**
```
core/models/
  __init__.py       ← Re-exportiert alle Models (Interface nach außen)
  constants.py      ← Alle Choice-Listen (MUSKELGRUPPEN, GEWICHTS_TYP, etc.)
  exercise.py       ← UebungTag, Equipment, Uebung
  training.py       ← Trainingseinheit, Satz
  plan.py           ← Plan, PlanUebung
  body_tracking.py  ← KoerperWerte, ProgressPhoto
  cardio.py         ← CardioEinheit
  social.py         ← InviteCode, WaitlistEntry
  feedback.py       ← Feedback, PushSubscription
  ml.py             ← MLPredictionModel
  user_profile.py   ← UserProfile
  disclaimer.py     ← ScientificDisclaimer (Re-export)
```

**Current Problem:**
- `core/models.py`: **1,100+ lines** (unmaintainable)
- All models in one file
- Hard to navigate, test, modify

**Solution - Split into Logical Files:**

```
core/
  models/
    __init__.py          # Import all models
    user.py              # UserProfile, related models
    exercise.py          # Uebung, UebungTag, Equipment
    training.py          # Trainingseinheit, Satz, TrainingTag
    plan.py              # Plan, PlanUebung, PlanGruppe
    body_tracking.py     # Koerperwerte, ProgressPhoto
    cardio.py            # CardioEinheit
    feedback.py          # Feedback
    sharing.py           # PlanSharing, invite codes
    ml_models.py         # MLPredictionModel, standards
    disclaimer.py        # ScientificDisclaimer
```

**Benefits:**
- Each file: 50-150 lines (manageable)
- Easier testing (mock specific models)
- Faster navigation
- Clear separation of concerns
- Easier for new developers

**Migration Steps:**
1. Create `core/models/` directory
2. Split models into logical files
3. Update `__init__.py` with imports
4. Update all imports across codebase
5. Run tests to verify no breakage
6. Create migration if needed

---

#### **Phase 3.2 - Template Base Refactoring** ✅ ABGESCHLOSSEN (24/26)
**Time Estimate:** 1-2 days  
**Status:** ✅ Batch 1+2+3 DONE — Commit eba7083 + 37eb077 (Branch: feature/phase-3-2-template-base)

**Migriert (24 Templates):**
- ✅ training_list.html (+ delete_training GET→POST Bugfix)
- ✅ training_stats.html, stats_exercise.html, body_stats.html
- ✅ profile.html, feedback_list.html, cardio_list.html, cardio_add.html
- ✅ dashboard.html (960→673 Zeilen, duplizierte Theme-Funktionen entfernt)
- ✅ plan_details.html, plan_library.html, training_finish.html
- ✅ muscle_map.html, ml_dashboard.html, equipment_management.html
- ✅ add_koerperwert.html, edit_koerperwert.html, progress_photos.html
- ✅ metriken_help.html, exercise_detail.html, uebungen_auswahl.html
- ✅ edit_plan.html, training_select_plan.html
- ✅ equipment_management_old.html → GELÖSCHT

**Ausgenommen (korrekt, kein extends nötig):**
- Partials/Modals: ai_coach_chat.html, ai_plan_generator.html, exercise_info_modal.html, plan_optimization_modal.html
- PDF-Templates (standalone): training_pdf.html, training_pdf_simple.html, training_pdf_v2.html

**Noch ausstehend (separater Chat, komplex):**
- ⏳ create_plan.html (721 Zeilen) → Phase 3.2b
- ⏳ training_session.html (1654 Zeilen) → Phase 3.2c

**Solution - Create Template Hierarchy:**

```html
<!-- templates/base.html -->
<!doctype html>
<html lang="de" data-bs-theme="dark">
<head>
    {% block head %}
    <!-- Common meta, CDN, PWA -->
    {% endblock %}
</head>
<body>
    {% block nav %}
    <!-- Navigation -->
    {% endblock %}

    {% block content %}
    <!-- Page content -->
    {% endblock %}

    {% include 'includes/disclaimer_banner.html' %}
    {% include 'core/includes/global_footer.html' %}
</body>
</html>
```

**Refactor Templates:**
```html
<!-- dashboard.html - AFTER -->
{% extends 'base.html' %}

{% block content %}
<div class="container">
    <h1>Dashboard</h1>
    <!-- Dashboard-specific content -->
</div>
{% endblock %}
```

**Benefits:**
- Single point of change for common elements
- Disclaimers automatically everywhere
- Easier dark mode updates
- Reduced template size: 960 lines → 50 lines
- Faster page updates

**Priority Templates:**
1. `dashboard.html`
2. `training_session.html`
3. `stats_exercise.html`
4. `body_stats.html`
5. All others

---

#### **Phase 3.3 - Type Hints & Documentation** ✅ COMPLETE
**Abgeschlossen:** 2026-02-12
**Impact:** View-Signaturen annotiert, mypy konfiguriert

**Was gemacht wurde:**
- Alle 16 `core/views/*.py` Dateien: View-Funktionen auf `HttpRequest → HttpResponse` annotiert
- `Optional[int]` Fix: `training_start(plan_id: int = None)` → `Optional[int] = None`
- `send_welcome_email(user: User) -> None` in auth.py
- `_apply_mesocycle_from_plan(user: User, plan_data: dict[str, Any], plan_ids: list[int]) -> None` in ai_recommendations.py
- `training_list` in training_stats.py war vergessen – nachgetragen
- `mypy.ini` erstellt (Django plugin, pragmatische Konfiguration)
- `.pre-commit-config.yaml`: Kommentar aktualisiert (367 pre-existing errors dokumentiert)
- mypy bleibt in pre-commit deaktiviert – 367 Legacy-Fehler (django-stubs attr-defined) müssen inkrementell behoben werden

**Bekannte Einschränkung:**
- 367 mypy-Fehler sind **pre-existing** (django-stubs erkennt `Plan.id`, `Uebung.id` etc. nicht out-of-box)
- Vollständige mypy-Aktivierung geplant für Phase 4+

**Time Estimate:** 2-3 days → **0.5 days** (Großteil war bereits gemacht)

---

#### **Phase 3.4.1 - Complexity Reduction: Grade D/E/F (CC > 20)** ✅ COMPLETE
**Abgeschlossen:** 2026-02-13
**Goal:** Cyclomatic complexity < 10 für alle Grade D/E/F Funktionen

**Offender (gemessen mit radon, 2026-02-12):**
| CC | Funktion | Datei |
|----|----------|-------|
| 74 | `dashboard` | training_stats.py |
| 57 | `export_training_pdf` | export.py |
| 40 | `workout_recommendations` | ai_recommendations.py |
| 33 | `training_stats` | training_stats.py |
| 30 | `finish_training` | training_session.py |
| 28 | `find_substitute_exercise` | helpers/exercises.py |
| 26 | `training_session` | training_session.py |
| 25 | `import_uebungen` | exercise_management.py |

**Techniken:**
- Extract helper functions
- Early returns statt tief verschachtelter if/else
- Komplexe Blöcke in klar benannte private Funktionen auslagern

**Erfolgskriterium:**
- Alle oben genannten Funktionen: CC < 10
- Alle 392 bestehenden Tests bleiben grün

---

#### **Phase 3.4.2 - Complexity Reduction: Grade C (CC 11-20)** ⏳
**Time Estimate:** 2 days
**Goal:** Cyclomatic complexity < 10 für alle Grade C Funktionen

**Offender (gemessen mit radon, 2026-02-12):**
| CC | Funktion | Datei |
|----|----------|-------|
| 20 | `exercise_detail` | exercise_library.py |
| 19 | `profile` | auth.py |
| 18 | `generate_plan_api` | ai_recommendations.py |
| 18 | `update_set` | training_session.py |
| 18 | `sync_offline_data` | offline.py |
| 17 | `exercise_stats` | training_stats.py |
| 17 | `_apply_mesocycle_from_plan` | ai_recommendations.py |
| 17 | `apply_optimizations_api` | ai_recommendations.py |
| 15 | `training_start` | training_session.py |
| 15 | `register` | auth.py |
| 15 | `create_plan_from_template` | plan_templates.py |
| 14 | `api_reorder_group` | api_plan_sharing.py |
| 14 | `body_stats` | body_tracking.py |
| 14 | `get_alternative_exercises` | exercise_library.py |
| 14 | `exercise_api_detail` | exercise_library.py |
| 14 | `export_plan_pdf` | export.py |
| 14 | `export_plan_group_pdf` | export.py |
| 13 | `set_active_plan_group` | plan_management.py |
| 12 | `uebungen_auswahl` | exercise_library.py |
| 12 | `training_select_plan` | training_session.py |
| 12 | `add_set` | training_session.py |

**Techniken:**
- Extract helper functions
- Early returns
- Komplexe Query-Blöcke in Methoden auslagern

**Erfolgskriterium:**
- Alle oben genannten Funktionen: CC < 10
- Alle Tests bleiben grün

---

#### **Phase 3.5 - Test Quality Improvements**
**Time Estimate:** 1-2 days  

**Improvements:**
- Add docstrings to all test functions
- Group related tests into classes
- Add parametrize for similar tests
- Improve factory realism
- Add edge case tests

**Example:**
```python
@pytest.mark.parametrize("severity,expected_color", [
    ("INFO", "#2196F3"),
    ("WARNING", "#ff9800"),
    ("CRITICAL", "#f44336"),
])
def test_disclaimer_colors(severity, expected_color):
    ...
```

---

### 🎯 Week 3 Success Metrics:
- ✅ 50%+ coverage
- ✅ models.py split into 10+ files
- ✅ base.html template created & used in 10+ templates
- ✅ Type hints: 80%+
- ✅ Max complexity: <10
- ✅ All tests have docstrings

---

## ⚡ **WEEK 4 - PERFORMANCE & OPTIMIZATION (60% TARGET)**

**Duration:** Feb 25 - Mar 3, 2026  
**Coverage Goal:** 50% → 60%  
**Focus:** Speed, efficiency, scalability

### 🎯 Week 4 Goals:
- [ ] Coverage: 60%+
- [ ] Eliminate all N+1 queries
- [ ] Database indexes optimized
- [ ] Caching strategy implemented
- [ ] Load testing passed

### 📋 Phase 4 Sub-Phases:

#### **Phase 4.1 - N+1 Query Detection & Fix** 🔥 CRITICAL
**Time Estimate:** 2-3 days  
**Impact:** Page load time 2-5x faster

**Tools:**
- django-debug-toolbar
- nplusone package
- Manual query analysis

**Common N+1 Patterns:**
```python
# BAD - N+1 Query
for plan in Plan.objects.all():
    print(plan.uebungen.count())  # Query per plan!

# GOOD - Prefetch
plans = Plan.objects.prefetch_related('planuebung_set__uebung')
for plan in plans:
    print(plan.uebungen.count())  # No extra queries
```

**Critical Views to Fix:**
- `dashboard.html` - User stats
- `plan_details.html` - Plan exercises
- `training_session.html` - Current workout
- `stats_exercise.html` - Exercise history

**Test Coverage:**
- Add tests that count queries
- Assert max query count per view
- Use `django.test.utils.override_settings` + `DEBUG=True`

---

#### **Phase 4.2 - Database Indexes**
**Time Estimate:** 1 day  

**Add Indexes for:**
- Foreign keys (user, plan, exercise)
- Frequently filtered fields (date, is_active)
- Compound indexes (user + date)

**Example Migration:**
```python
class Migration:
    operations = [
        migrations.AddIndex(
            model_name='trainingseinheit',
            index=models.Index(
                fields=['user', 'datum'],
                name='training_user_date_idx'
            ),
        ),
    ]
```

**Impact:**
- Query time: 500ms → 50ms (10x faster)
- Especially for stats views

---

#### **Phase 4.3 - Caching Strategy**
**Time Estimate:** 2 days  

**Implement Caching:**
- Exercise list (changes rarely)
- User statistics (cache 5min)
- 1RM standards (static data)
- Plan templates (public data)

**Technologies:**
- Redis (if available)
- Django cache framework
- Cached properties for models

**Example:**
```python
from django.core.cache import cache

def get_user_stats(user_id):
    cache_key = f'user_stats_{user_id}'
    stats = cache.get(cache_key)
    if not stats:
        stats = calculate_stats(user_id)
        cache.set(cache_key, stats, 300)  # 5min
    return stats
```

---

#### **Phase 4.4 - Load Testing**
**Time Estimate:** 1 day  

**Tools:**
- Locust or Apache JMeter
- Simulate 100-1000 concurrent users

**Test Scenarios:**
- Dashboard load (logged in)
- Training session start
- Stats page generation
- Plan creation

**Success Criteria:**
- P95 response time: <500ms
- P99 response time: <1000ms
- Support 100 concurrent users

---

### 🎯 Week 4 Success Metrics:
- ✅ 60%+ coverage
- ✅ Zero N+1 queries in critical views
- ✅ All foreign keys indexed
- ✅ Cache hit rate: 70%+
- ✅ P95 response time: <500ms

---

## 🌟 **WEEK 5-6 - ADVANCED FEATURES & PRE-LAUNCH (75% TARGET)**

**Duration:** Mar 4-17, 2026  
**Coverage Goal:** 60% → 75%+  
**Focus:** Professional polish, scientific foundation

### 🎯 Week 5-6 Goals:
- [ ] Coverage: 75%+
- [ ] Scientific sources integrated
- [ ] AI/ML testing comprehensive
- [ ] Charts & statistics tested
- [ ] Helper/utility modules: 90%+ coverage
- [ ] All critical features production-ready

### 📋 Phase 5 Sub-Phases:

#### **Phase 5.1 - Scientific Source System** 🔬 IMPORTANT
**Time Estimate:** 1-2 days  
**Priority:** Before public launch

**Background:**
Current disclaimers say "Eingeschränkte wissenschaftliche Basis"  
Need: Proper literature citations for credibility

**Implementation:**

1. **Create TrainingSource Model:**
```python
class TrainingSource(models.Model):
    """Scientific literature source for training recommendations."""
    
    CATEGORY_CHOICES = [
        ('1RM', '1RM Standards'),
        ('VOLUME', 'Training Volume'),
        ('FREQUENCY', 'Training Frequency'),
        ('FATIGUE', 'Fatigue Management'),
        ('PROGRESSION', 'Progressive Overload'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    authors = models.CharField(max_length=200)
    year = models.IntegerField()
    publication = models.CharField(max_length=200)  # Journal/Book
    doi = models.CharField(max_length=100, blank=True)
    url = models.URLField(blank=True)
    summary = models.TextField()
    key_findings = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-year', 'authors']
```

2. **Literature to Add:**

**1RM Standards:**
- Schoenfeld, B. (2016) - "Science and Development of Muscle Hypertrophy"
- Nuckols, G. (2020) - Strength Standards Analysis
- Lon Kilgore - Strength Standards Tables

**Training Volume:**
- Schoenfeld, B. (2017) - "Dose-response relationship between weekly resistance training volume and increases in muscle mass"
- Israetel, M. (2020) - Renaissance Periodization Principles (MRV/MEV/MAV)
- Helms, E. (2018) - Muscle & Strength Pyramids

**Fatigue & Recovery:**
- Mike Israetel - Fatigue Management
- Eric Helms - Autoregulation Principles

**Progressive Overload:**
- NSCA (National Strength & Conditioning Association) Guidelines
- Kraemer, W. & Ratamess, N. (2004) - Fundamentals of Resistance Training Progression

3. **Management Command:**
```bash
python manage.py load_training_sources
```

4. **UI Integration:**
```html
<!-- In disclaimer or info tooltips -->
<div class="source-reference">
    📚 Based on: Schoenfeld (2016), Israetel (2020)
    <a href="#sources">View sources</a>
</div>
```

5. **Update Disclaimers:**
```python
# From: "Eingeschränkte wissenschaftliche Basis"
# To: "Basierend auf Schoenfeld et al. (2016) und NSCA Guidelines"
```

**Time Breakdown:**
- Literature research: 3h (read papers, extract key points)
- Model + migration: 1h
- Management command: 1h
- Load sources into DB: 30min
- UI integration: 2h
- Tests: 1h
- Documentation: 30min

---

#### **Phase 5.2 - AI/ML Testing**
**Time Estimate:** 2 days  

**Test Coverage:**
- `test_ml_models.py` - ML prediction tests
- `test_ai_coach.py` - AI coach responses
- `test_plan_generator.py` - AI plan generation

**Mock External Services:**
- Ollama/OpenRouter API calls
- Test with fixtures, not real API

---

#### **Phase 5.3 - Charts & Statistics Testing**
**Time Estimate:** 1-2 days  

**Test Coverage:**
- `test_charts.py` - Chart generation
- `test_statistics.py` - Stats calculations
- Verify chart data accuracy
- Test edge cases (empty data, single point)

---

#### **Phase 5.4 - API Endpoints Testing**
**Time Estimate:** 1 day  

**Test Coverage:**
- `test_api.py` - REST API endpoints
- Plan sharing API
- Stats API
- Authentication

---

#### **Phase 5.5 - Helper/Utils Testing**
**Time Estimate:** 1 day  
**Goal:** 90%+ coverage

**Test Coverage:**
- `test_helpers.py` - Helper functions
- `test_utils.py` - Utility modules
- `test_advanced_stats.py` - Statistics utils

---

### 🎯 Week 5-6 Success Metrics:
- ✅ 75%+ coverage
- ✅ Scientific sources integrated (10+ citations)
- ✅ AI/ML: 70%+ coverage
- ✅ Charts: 80%+ coverage
- ✅ Helpers/utils: 90%+ coverage
- ✅ Zero critical bugs

---

## 🚀 **WEEK 7 - PRE-LAUNCH PREPARATION (80%+ TARGET)**

**Duration:** Mar 18-24, 2026  
**Coverage Goal:** 75% → 80%+  
**Focus:** Final polish, deployment, monitoring

### 🎯 Week 7 Goals:
- [ ] Coverage: 80%+
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Deployment automation ready
- [ ] Monitoring dashboards configured
- [ ] Documentation complete

### 📋 Phase 6 Sub-Phases:

#### **Phase 6.1 - Security Audit**
**Time Estimate:** 1-2 days  

**Checklist:**
- [ ] OWASP Top 10 compliance
- [ ] SQL injection protection (Django ORM = safe)
- [ ] XSS protection (template escaping)
- [ ] CSRF protection (enabled)
- [ ] Authentication secure (django-axes rate limiting)
- [ ] Sensitive data encrypted
- [ ] API authentication (if applicable)
- [ ] File upload validation
- [ ] Password strength requirements
- [ ] Session security

**Tools:**
- django-security
- bandit (Python security scanner)
- Safety (check dependencies)

---

#### **Phase 6.2 - Performance Benchmarks**
**Time Estimate:** 1 day  

**Targets:**
- Page load: <2s (desktop)
- API response: <500ms (P95)
- Database queries: <50 per page
- Memory usage: <512MB per worker
- Support 100 concurrent users

**Tools:**
- Google Lighthouse
- WebPageTest
- New Relic / Datadog (if available)

---

#### **Phase 6.3 - Deployment Automation**
**Time Estimate:** 1 day  

**CI/CD Pipeline:**
1. Push to GitHub
2. Run tests (pytest)
3. Run quality checks (Black, isort, flake8)
4. Build Docker image (optional)
5. Deploy to staging
6. Run smoke tests
7. Deploy to production (if staging passes)

**Technologies:**
- GitHub Actions / GitLab CI
- Docker + docker-compose
- Ansible / Fabric for deployment

---

#### **Phase 6.4 - Monitoring Dashboards**
**Time Estimate:** 1 day  

**Setup:**
- Sentry dashboard (errors) ✅ Already configured
- Application monitoring (APM)
- Database monitoring (slow queries)
- Server monitoring (CPU, memory, disk)

**Tools:**
- Sentry (errors) ✅
- Grafana (metrics)
- Prometheus (time series data)
- Django Debug Toolbar (dev)

---

#### **Phase 6.5 - Documentation**
**Time Estimate:** 1 day  

**Documentation to Create:**
- [ ] `docs/DEPLOYMENT.md` - Production deployment guide
- [ ] `docs/API.md` - API endpoint documentation
- [ ] `docs/ARCHITECTURE.md` - System architecture
- [ ] `docs/CONTRIBUTING.md` - Contribution guidelines
- [ ] `docs/TROUBLESHOOTING.md` - Common issues
- [ ] Update README.md with screenshots

---

### 🎯 Week 7 Success Metrics:
- ✅ 80%+ coverage
- ✅ Security audit: No critical findings
- ✅ Performance: All benchmarks met
- ✅ CI/CD: Fully automated
- ✅ Monitoring: All dashboards live
- ✅ Documentation: Complete

---

## 🌍 **WEEK 8 - PUBLIC LAUNCH**

**Duration:** Mar 25+  
**Status:** 🎯 **READY FOR LAUNCH**

### 🚀 Launch Checklist:

#### **Pre-Launch (T-7 days):**
- [ ] All tests passing (80%+ coverage)
- [ ] Security audit complete
- [ ] Performance benchmarks met
- [ ] Sentry monitoring live
- [ ] Backup strategy tested
- [ ] Rollback plan ready

#### **Launch Day (T-0):**
- [ ] Deploy to production
- [ ] Run smoke tests
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify all critical features

#### **Post-Launch (T+1 to T+7):**
- [ ] Monitor Sentry daily
- [ ] Review user feedback
- [ ] Track performance metrics
- [ ] Fix critical bugs immediately
- [ ] Plan hotfix deployments

---

## 📊 **SUCCESS METRICS**

### **Quantitative:**
- Test Coverage: 80%+
- Tests Passing: 100%
- Performance: P95 <500ms
- Error Rate: <0.1%
- Uptime: 99.9%

### **Qualitative:**
- Code maintainable (models split, base.html)
- Documentation complete
- CI/CD automated
- Monitoring comprehensive
- Scientific foundation solid

---

## 🎓 **KEY LEARNINGS & BEST PRACTICES**

### **Testing:**
1. **Start with integration tests** - catch real user issues
2. **Factory Boy > fixtures** - more flexible, realistic
3. **Context processors** - powerful for cross-cutting concerns
4. **Dark mode testing** - critical for modern apps
5. **Codecov vs pytest-cov** - different scopes, both useful

### **Refactoring:**
1. **Split large files early** - models.py should be <300 lines
2. **base.html template** - saves 1000s of lines of duplication
3. **Type hints** - catch bugs at dev time, not production
4. **Complexity <10** - easier to test, maintain, understand

### **Performance:**
1. **N+1 queries** - biggest performance killer, hardest to spot
2. **Database indexes** - low-effort, high-impact
3. **Caching** - start with simple Django cache
4. **Load testing** - catches scalability issues early

### **Production:**
1. **Sentry** - non-negotiable for error tracking
2. **Scientific sources** - credibility for fitness apps
3. **Disclaimers** - legal protection + transparency
4. **Monitoring** - know about issues before users complain

---

## 📞 **SUPPORT & RESOURCES**

### **Documentation:**
- `docs/DISCLAIMER_SYSTEM.md` - Scientific disclaimer guide
- `docs/PROJECT_ROADMAP.md` - This file
- `dev-scripts/test_sentry.py` - Sentry verification
- `README.md` - Getting started guide

### **Key Files:**
- `core/tests/` - All test suites
- `core/models/` - Split models (after Phase 3.1)
- `templates/base.html` - Base template (after Phase 3.2)
- `config/settings.py` - Configuration

### **Tools:**
- pytest - Testing framework
- Codecov - Coverage reporting
- Sentry - Error tracking
- Black - Code formatting
- isort - Import sorting
- flake8 - Linting

---

## 🗓️ **TIMELINE SUMMARY**

```
Week 1 [✅] Foundation & Safety
  ├─ Day 1-2: Test infrastructure
  ├─ Day 2-3: Core test suites
  └─ Day 3: Sentry + Disclaimers
  Result: 30.48% coverage

Week 2 [🔄] Testing & Views
  ├─ Phase 2.5: Export & Auth ✅ (34%, 170 tests)
  ├─ Phase 2.6: Exercise Library ✅ (35%, 197 tests)
  ├─ Phase 2.7: Exercise Management ✅ (37%, 217 tests)
  └─ Phase 2.8: Config & Cardio ✅ (38%, 247 tests)
  Target: 40% coverage

Week 3 [🔄] Refactoring & Quality
  ├─ Phase 3.1: Model Refactoring ✅ (247 tests grün, 11 Module)
  ├─ Phase 3.1b: Training Stats Tests ✅ (383→392 tests, Bug in delete_training gefixt)
  ├─ Phase 3.1c: test_context_helpers.py gefixt ✅ (392/396 grün, 0 Fehler)
  ├─ Phase 3.2: base.html Template Migration 🔄 (3/~30 Templates migriert)
  │    ✅ training_list.html  ✅ training_stats.html  ✅ stats_exercise.html
  │    + Delete-Modal: GET→POST Fix (verhindert Datenverlust durch Prefetching)
  ├─ Phase 3.3: Type Hints ✅ (392 tests, mypy.ini)
  ├─ Phase 3.4.1: Complexity Grade D/E/F (CC > 20) ⏳
  ├─ Phase 3.4.2: Complexity Grade C (CC 11-20) ⏳
  └─ Phase 3.5: Test Quality ⏳
  Target: 50% coverage

Week 4 [⏳] Performance
  ├─ N+1 queries
  ├─ Database indexes
  ├─ Caching
  └─ Load testing
  Target: 60% coverage

Week 5-6 [⏳] Advanced & Polish
  ├─ Scientific sources
  ├─ AI/ML testing
  ├─ Charts/stats
  └─ Helpers/utils
  Target: 75% coverage

Week 7 [⏳] Pre-Launch
  ├─ Security audit
  ├─ Performance benchmarks
  ├─ Deployment automation
  └─ Documentation
  Target: 80%+ coverage

Week 8 [🎯] PUBLIC LAUNCH
  └─ Go live!
```

---

## 🏆 **PROJECT VISION**

**From:** MVP Beta (single user, 14% coverage, manual testing)  
**To:** Production-ready (public launch, 80%+ coverage, automated CI/CD)

**Timeline:** 8 weeks (Feb 9 - Mar 25, 2026)  
**Status:** Week 1 Complete ✅ - Week 2 In Progress 🔄 (Phase 2.5-2.8 ✅ DONE)

**Mission:** Build a professional, scalable, scientifically-sound fitness tracking application ready for public launch.

---

**Last Updated:** February 13, 2026 (Phase 3.4.1 COMPLETE – alle CC > 20 Funktionen refactored, 406 Tests, 47% Coverage)
**Version:** 3.1 (Phase 3.4.1 complete)
**Next Review:** Phase 3.4.2 – CC 11-20 Funktionen (Grade C) refactoren
