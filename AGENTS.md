# Berry-Gym Agent Instructions

Sei ehrlich, beschönige nichts, sei kritisch und weise aktiv auf
Logiklücken, Sicherheitsrisiken, fehlende Tests und technische Schulden hin.
Wenn etwas unklar ist, frage nach statt Annahmen als Fakten zu behandeln.

Diese Datei ist die allgemeine Arbeitsanweisung für LLM-gestützte Coding-
Agents in diesem Repository. Tool-spezifische Dateien wie `CLAUDE.md` sollen
auf diese Datei verweisen, statt ein zweites Regelwerk zu pflegen.

## Arbeitsteilung

- Claude.app: Planung und Konzepterstellung (Milestone-/Feature-Konzepte,
  Architektur- und Scope-Entscheidungen, Abnahmekriterien).
- Claude Code (VSCode): Ausführung (Implementierung, Tests, Commits).
- Setze Konzepte um, hinterfrage sie aber kritisch.

## Projektgedächtnis

Projekt: berry-gym

Aktives Projektgedächtnis ist das Bramble-MCP-Journal
(<https://journal.last-strawberry.com/mcp/>, projektgebundenes Token).

Zu Beginn jeder Session:

1. `journal_guide()` aufrufen und befolgen — die kanonischen, geteilten
   Journal-Konventionen (Status, Tags, Korrektur-/resolves-Modell,
   Open-Item-Semantik, Session-Start/Ende, DoD). Diese Regeln hier NICHT
   wiederholen.
2. `journal_context(project="berry-gym", n_recent=10)` lesen
   (Fallback: `journal_read(project="berry-gym", n=20)`).

Dieses Dokument ergänzt den Guide nur um Projekt-Spezifika:

- Lies zusätzlich relevante lokale Dokumente, wenn sie zum Arbeitsumfang
  gehören:
  - `docs/PROJECT_ROADMAP.md` für Planungs-/Scope-/Milestone-Fragen.
  - `README.md` für Feature-Überblick, Tech-Stack und Projektstruktur.
  - `docs/CODE_QUALITY.md`, `docs/RUNBOOK.md`, `docs/DEPLOYMENT.md`,
    `docs/CICD_GUIDE.md`, `docs/LOAD_TESTING.md` je nach Thema.
- `docs/journal.txt` ist nur historische Importquelle (kein neuer Eintrag).
- Wenn die Bramble-MCP-Tools nicht verfügbar sind, sage das ausdrücklich und
  nutze nur als groben Fallback `git log --oneline -30`, `CHANGELOG` und
  `docs/PROJECT_ROADMAP.md`. Markiere den Stand als grobkörnig, rate nicht.

## Planung vor Ausführung

- Nach dem Lesen des Projektgedächtnisses erstelle einen kurzen Plan.
- Warte auf explizite Bestätigung, bevor du mit einem neuen Milestone oder
  einer größeren Code-Änderung beginnst.
- Bei Dateiänderungen: nenne vorher die Dateien, die du ändern wirst.
- Lies bestehende Dateien vor dem Schreiben, auch wenn du ihren Inhalt zu
  kennen glaubst.
- Wenn der Nutzer ausdrücklich direkte Umsetzung verlangt, arbeite trotzdem
  kontrolliert: Kontext lesen, betroffene Dateien nennen, dann umsetzen.

## Code-Generierung

- Neue Code-Dateien: maximal ca. 400 Zeilen pro Datei-Chunk.
- Templates (Django, HTML): nie inline in Python erzeugen, sondern als separate
  Template-Dateien unter `core/templates/...`.
- Verwende relative Pfade vom Projekt-Root, z.B. `core/...`, `ai_coach/...`,
  `config/...`.
- Datenmodell-Änderungen immer mit Migration (`python manage.py makemigrations`
  / `migrate`) und passenden Tests.
- Nutzer-sichtbare Texte sind übersetzbar (i18n): neue Strings DE/EN pflegen
  (gettext); in JS Dezimalzahlen locale-sicher behandeln (`{% localize off %}`).
- Halte Änderungen eng am bestehenden Stil und an vorhandenen Abstraktionen.

## Tests und Code-Qualität

- Runner unter Windows aus dem Projekt-Root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- Tests mit pytest und factory_boy. CI/CD (GitHub Actions) muss grün bleiben.
- Nach Code-Änderungen: betroffene Tests ausführen und Ergebnis berichten.
- Mindestens testen: Happy Path, wichtigste Fehlerfälle, relevante Edge Cases.
- Code-Stil: PEP 8, Type Hints, Black/isort/flake8 (pre-commit). Siehe
  `docs/CODE_QUALITY.md`.

## Dependencies

- Source of Truth: `requirements.txt`.
- Keine neuen Dependencies ohne Rückfrage; begründe, warum sie nötig sind.

## Architektur (Django)

- Django 5.1.x, Python 3.12. Apps: `core/` (Haupt-App), `ai_coach/` (KI-Coach),
  `config/` (Settings/URLs/WSGI).
- `core/models/` ist nach Domäne aufgeteilt (training, exercise, plan,
  body_tracking, cardio, user_profile, ...). Views sind modular unter
  `core/views/`.
- Multi-User mit vollständiger Datenisolation; `@login_required` auf sensiblen
  Views; IDOR-Schutz; Rate-Limits auf allen KI-Endpunkten.
- KI: Google Gemini 2.5 Flash via OpenRouter (`ai_coach/`). Ohne API-Key
  bleiben Core-Features funktionsfähig. Modellwechsel nur mit Begründung.
- DB: MariaDB (Production), SQLite (Dev). Caching: Django FileBasedCache.

## Sicherheit

- Niemals committen: `.env`, `db.sqlite3`, API-Keys, Production-Configs.
- Secrets über `ai_coach/secrets_manager.py` (`~/.homegym_secrets`), nie ins
  Journal, in Logs oder ins Repo.
- defusedxml für XML, File-Upload-Validierung beibehalten.

## Umgebung

- Lokal (Windows): `.venv` in `C:\Dev\Berry-Gym\.venv`, Python 3.12.
  Falls `.venv` fehlt: `py -3.12 -m venv .venv`.
- Production: Linux, MariaDB, Gunicorn hinter Nginx (`deployment/`).

## GitHub

- Branch pro Milestone/Feature: `feature/kurzbeschreibung`
  (z.B. `feature/m6-ai-contract-hardening`). Branch-Namen lowercase,
  Bindestriche.
- Reihenfolge Journal <-> Commit (Konvention): zuerst `journal_append`
  (ID merken), dann committen und `Journal: berry-gym#<id>` in den Commit-Text
  schreiben.
- Vor Commit relevante Tests ausführen und im Abschluss nennen.
- Am Ende eines Milestones committen. Keinen Pull Request erstellen; das macht
  der Nutzer.

## Sessions und Chat-Management

- Möglichst je Milestone/größerem Feature eine eigene Session; sprechende
  Namen, z.B. `m6-ai-endpoint-contract-hardening`.
- Architekturfragen vor Code-Umsetzung zuerst planen.
- Wenn Antworten unzuverlässiger werden oder Kontext fehlt: aktiv melden.

## Qualität (DoD)

Die Definition of Done richtet sich nach `journal_guide()` (Session-Ende):
committen, Tests/Smoke ausführen und im Eintrag nennen, append-only
Journal-Eintrag, nächsten Schritt dokumentieren.

Projekt-Ergänzungen:

- CI/CD (GitHub Actions) muss grün sein.
- Melde fehlende Tests, Sicherheitslücken, Logiklücken und technische Schulden
  aktiv. Benenne den Preis riskanter Abkürzungen.
- i18n: neue nutzer-sichtbare Strings DE/EN konsistent halten.
