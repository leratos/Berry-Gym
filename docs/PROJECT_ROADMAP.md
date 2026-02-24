# 🚀 Berry-Gym Roadmap (Stand: 24.02.2026)

## Zielbild

Berry-Gym ist bereits live und funktional breit aufgestellt (Training, AI-Coach,
i18n, Import/Export, PWA). Der Fokus wechselt von „Feature-Bau“ zu
**Produktstabilität, Testtiefe, Betriebsqualität und planbarer Weiterentwicklung**.

Diese Roadmap ersetzt die alte Wochen-1-bis-10-Struktur durch eine
milestone-basierte Planung ab dem aktuellen Ist-Stand.

---

## 1) Aktueller Projektstand (Ist)

### Produkt & Architektur

- Django-Monolith mit klaren Paketen: `core/`, `ai_coach/`, `ml_coach/`
- Live-Betrieb auf Production (HTTPS, Nginx + Gunicorn, MariaDB)
- AI-Funktionen produktiv: Plan-Generierung, Analyse, Optimierung, Live-Guidance
- SSE-Preview-Flow für AI-Planung vorhanden
- i18n DE/EN produktiv (inkl. EN-URL-Prefix)

### Delivery & Betrieb

- CI mit separaten Jobs für Tests/Coverage, Lint und Security
- Deploy-Workflow mit Auto-Deploy bei grüner CI auf `main` + Rollback-Mechanik
- Sentry laut Doku aktiv; Runbook/Deployment-Doku vorhanden

### Qualität & Tests

- Sehr breite Testbasis in `core/tests` und `ai_coach/tests`
- Zuletzt dokumentierte Coverage: ca. **53%** (starker Ausbau gegenüber Frühphase)
- Aktuelle Sprint-Arbeit erweitert besonders:
  - Sharing-API Fehler-/Ownership-Pfade
  - AI-Endpoint Edge Cases und Rate-Limit-Pfade
  - Admin-UI Regressionen (KI-Counter heute)

### Bekannte strukturelle Baustellen

- Alte Roadmap war in Teilen historisch/inkonsistent (doppelte oder veraltete Phasen)
- Mehrere komplexe Module mit `C901`-Ausnahmen (bewusste technische Schulden)
- mypy nur teilweise strikt; Typabdeckung ausbaufähig
- Hoher Qualitätsstandard in CI vorhanden, aber Security-Job (`safety`) aktuell
  bewusst nicht blockierend

---

## 2) Abgeschlossene Meilensteine (kompakt)

### ✅ M0 – Foundation & Launch (abgeschlossen)

- Test- und Qualitäts-Toolchain etabliert (pytest, black, isort, flake8)
- Performance-Maßnahmen (N+1, Indizes, Caching) umgesetzt
- Public Launch (DE) erfolgreich, Betrieb stabilisiert

### ✅ M1 – Internationalisierung (abgeschlossen)

- DE/EN vollständig integriert
- Language-Switching + EN-Routing produktiv
- Dokumentation in DE/EN vorhanden

### ✅ M2 – AI Coach Produktiv-Reife (abgeschlossen)

- LLM-Upgrade, Prompt-Härtung, Streaming, Retry-Strategien
- Rate-Limits und Kosten-/Nutzungs-Tracking eingeführt

### ✅ M3 – Datenportabilität (abgeschlossen)

- Hevy-kompatibler Import/Export inkl. Dry-Run und Mapping

### ✅ M4 – Stabilisierung Sprint A/B (abgeschlossen)

- API-Sharing und AI-Endpoints robustere Fehlerbehandlung
- Redirect-/HTTPS-Teststabilität verbessert
- Zusätzliche Regressionstests für Admin-Darstellung

### ✅ M5 – Coverage Sprint C (abgeschlossen, 24.02.2026)

- WP1: Stats-Helpers Edge Cases (`test_advanced_stats.py`)
- WP2: View-nahe Statistikpfade (`test_training_stats_extended.py`)
- WP3: Chart-Daten-Contract (`test_chart_generator.py`)
- WP4: Integrations-Regressionen (`test_training_views.py`, `test_training_session_views.py`)

---

## 3) Priorisierte nächste Meilensteine

## ✅ M5 – Coverage Sprint C (Charts/Stats/Helpers)

**Status:** Abgeschlossen (24.02.2026)

**Scope:**
- Testlücken in Statistik-/Chart-Pfaden schließen (`training_stats`,
  `advanced_stats`, chart-nahe Utilities)
- Fokus auf Edge Cases: leere Daten, Einzelpunkte, Nullwerte, Grenzbereiche
- Regressionssicherheit für Dashboard-nahe Kennzahlen erhöhen

**Akzeptanzkriterien:**
- Neue fokussierte Tests in den betroffenen Modulen
- Keine Regression in bestehenden Endpunkt-Tests
- Dokumentierte Coverage-Verbesserung in CI/Codecov

### M5 Sprintplan (umsetzbar)

**WP1 – Stats-Helpers Edge Cases (Startblock)**
- **Primärdateien:**
  - `core/utils/advanced_stats.py`
  - `core/helpers/exercises.py` (nur stat-relevante Hilfsfunktionen)
- **Tests (neu/erweitern):**
  - `core/tests/test_advanced_stats.py`
- **Testfälle:**
  - leere QuerySets / keine Trainingsdaten
  - Nullwerte in RPE/Gewicht/Wiederholungen
  - stabile Defaults statt Exceptions (`0`, leere Listen, klare Flags)

**WP2 – View-nahe Statistikpfade**
- **Primärdateien:**
  - `core/views/training_stats.py`
  - `core/views/training_stats_extended.py` (falls vorhanden in View-Struktur)
- **Tests (neu/erweitern):**
  - `core/tests/test_training_stats_extended.py`
- **Testfälle:**
  - einzelner Datenpunkt (keine Trend-Berechnungsfehler)
  - Zeitfenster ohne Daten (30/90 Tage)
  - Dashboard-nahe Kennzahlen bleiben konsistent

**WP3 – Chart-Daten Contract**
- **Primärdateien:**
  - `core/chart_generator.py`
  - chart-nahe Serializer/Response-Pfade in `core/views/`
- **Tests (neu/erweitern):**
  - `core/tests/test_chart_generator.py`
  - ggf. Erweiterung in `core/tests/test_api_endpoints.py` für Chart-Responses
- **Testfälle:**
  - Label/Series-Längen identisch
  - deterministische Reihenfolge von Datenpunkten
  - leere Charts liefern valide, renderbare JSON-Struktur

**WP4 – Integrations-Regressionen für bestehende User-Flows**
- **Primärdateien:** keine Feature-Änderungen, nur Sicherung bestehender Flows
- **Tests (erweitern):**
  - `core/tests/test_training_views.py`
  - `core/tests/test_training_session_views.py`
- **Testfälle:**
  - Statistik-/Chart-Aufrufe brechen Session- und Dashboard-Flows nicht
  - Ownership-Schutz unverändert intakt

**Empfohlene Ausführungsreihenfolge (pro Commit):**
1. WP1 (Helper-Basis)
2. WP2 (View-Statistiken)
3. WP3 (Chart-Contract)
4. WP4 (Integrationssicherung)

**Definition of Done (M5):**
- Alle neuen Tests grün in lokaler Zielausführung (`pytest` auf betroffene Module)
- Keine Änderung am produktiven Verhalten außerhalb der abgesicherten Fixes
- CI-Gates für Format/Lint bestehen
- Sichtbarer Coverage-Uplift in den Zielmodulen (Stats/Charts/Helpers)

---

## 🧠 M6 – AI Endpoint Contract Hardening

**Priorität:** Hoch  
**Zeithorizont:** Kurzfristig (1 Woche, parallel möglich)

**Scope:**
- Einheitliche Fehlerverträge für AI-APIs (HTTP-Code + JSON-Struktur)
- Konsistente Behandlung von NotFound/Ownership/Validation über alle AI-Pfade
- Ergänzende Tests für Response-Shape und Fehlersignaturen

**Akzeptanzkriterien:**
- Definierte Fehlermatrix je Endpoint dokumentiert
- Testabdeckung aller zentralen Error-Branches
- Keine generischen 500er in erwartbaren User-Fehlpfaden

### M6 Fehlermatrix (Baseline)

| Endpoint | Case | Erwarteter Status | Contract (Baseline) |
|---|---|---:|---|
| `generate_plan_api` | falsche Methode (`GET`) | `405` | JSON mit `error` |
| `generate_plan_api` | ungültiger `plan_type` | `400` | JSON mit `error` |
| `analyze_plan_api` | falsche Methode (`POST`) | `405` | JSON mit `error` |
| `analyze_plan_api` | fehlendes `plan_id` | `400` | JSON mit `error` |
| `analyze_plan_api` | fremder Plan | `404` | JSON mit `error` |
| `optimize_plan_api` | falsche Methode (`GET`) | `405` | JSON mit `error` |
| `optimize_plan_api` | fehlendes `plan_id` | `400` | JSON mit `error` |
| `optimize_plan_api` | fremder Plan | `404` | JSON mit `error` |
| `live_guidance_api` | falsche Methode (`GET`) | `405` | JSON mit `error` |
| `live_guidance_api` | fehlende Pflichtfelder | `400` | JSON mit `error` |
| `live_guidance_api` | fremde Session | `404` | JSON mit `error` |
| `generate_plan_stream_api` | falsche Methode (`POST`) | `405` | Plain-Text `GET required` |
| `generate_plan_stream_api` | Rate Limit | `429` | SSE `text/event-stream` mit `success=false` |

**Nächster Schritt (M6.1):**
- Contract-Tests für Methoden-/Error-Baseline zentralisieren und auf allen
  AI-Endpunkten absichern (`core/tests/test_ai_endpoints_extended.py`).

**Statusupdate (24.02.2026):**
- M6.1 umgesetzt: erste und zweite Testwelle für Method-/Error-Contracts
  (405/400/404/429/500) in `core/tests/test_ai_endpoints_extended.py` ergänzt.
- M6.2 umgesetzt: `apply_optimizations_api` um konsistenten JSON-404-Contract
  ergänzt und per Regressionstests abgesichert.
- M6.3 umgesetzt: `generate_plan_stream_api` um zusätzliche SSE-Error-Contracts
  (Validierungsfehler + Generator-Exception) testseitig gehärtet.

---

## 🔐 M7 – Security & Compliance Tightening

**Priorität:** Mittel-Hoch  
**Zeithorizont:** Mittelfristig (1–2 Wochen)

**Scope:**
- Security-Checks aus CI systematisieren (Bandit-Befunde triagieren, Safety-Prozess)
- Klarer Umgang mit `safety`-Findings (Policy: blockierend vs. nicht-blockierend)
- Review sensibler Flows: AI-Endpunkte, Ownership-Prüfungen, Upload/Export-Wege

**Akzeptanzkriterien:**
- Dokumentierte Security-Policy in `docs/`
- Offene Security-Findings priorisiert und terminiert
- Keine offenen High-Risk Findings ohne Follow-up

---

## 📈 M8 – Observability & Ops Maturity

**Priorität:** Mittel  
**Zeithorizont:** Mittelfristig (1 Woche)

**Scope:**
- Logging/Monitoring auf kritische User-Flows fokussieren (AI, Training-Session,
  Import/Export)
- Sentry-Signale und Alarmierung auf Praxisniveau prüfen
- Runbook-Drills für typische Vorfälle (Deploy-Fail, API-Ausfall, Rate-Limit-Fehler)

**Akzeptanzkriterien:**
- Definierte Alert-Pfade für kritische Fehlerklassen
- Nachvollziehbare Incident-Checkliste in `docs/RUNBOOK.md`
- 1 dokumentierter Probe-Drill

---

## 🧩 M9 – Refactoring gezielter High-Complexity-Module

**Priorität:** Mittel  
**Zeithorizont:** Fortlaufend, inkrementell

**Scope:**
- Gezielte Entlastung der größten `C901`-Hotspots
- Kleine, risikoarme Extraktionen in Service-/Helper-Funktionen
- Refactor nur dort, wo Tests vorhanden sind oder zeitgleich ergänzt werden

**Akzeptanzkriterien:**
- Messbar reduzierte Komplexität in priorisierten Dateien
- Kein funktionaler Scope-Creep
- Bestehende Regressionstests bleiben grün

---

## 4) Reihenfolge & Abhängigkeiten

1. **M6 (AI Contract Hardening)** als unmittelbarer Fokus
2. **M7 (Security Tightening)** direkt danach, auf Basis der stabilen Testlage
3. **M8 (Ops Maturity)** zur Betriebsfestigung vor größeren neuen Features
4. **M9 (Refactoring)** kontinuierlich, nur testgeführt und modular

---

## 5) Qualitäts-Gates für alle neuen Meilensteine

- `pytest` grün (inkl. neuer Regressionstests)
- `black --check core/ config/ ai_coach/`
- `isort --check-only core/ config/ ai_coach/`
- `flake8 core/ config/ ai_coach/`
- Security-Checks aus CI ohne neue ungeklärte High-Risk-Funde
- Journal-Einträge in `docs/journal.txt` je Phase (`In Arbeit` / `Abgeschlossen`)

---

## 6) Nicht-Ziele (für den aktuellen Zyklus)

- Kein großflächiger Architekturwechsel weg vom Monolithen
- Keine parallele Einführung neuer Großfeatures ohne Test-/Qualitätsbudget
- Kein „Big Bang“-Refactor ohne inkrementelle Absicherung

---

## Status-Notiz

Diese Roadmap ist auf **Milestone-Steuerung ab Live-Betrieb** ausgerichtet.
Sie dient als operative Priorisierung für die nächsten Umsetzungsphasen und
wird nach jedem abgeschlossenen Milestone kurz aktualisiert.

**Last Updated:** 2026-02-24
**Nächster Fokus:** M6