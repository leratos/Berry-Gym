# Phase 28 – Dokumentations-Aktualisierung

**Status:** 🔄 In Arbeit (seit 30.05.2026) – 28.1–28.4 umgesetzt, 28.5 + finaler README-Pass nach Phase 27
**Vorgänger:** Phase 27 (Style-Overhaul)
**Nachfolger:** offen
**Branch-Schema:** `feature/phase-28-X-kurzbeschreibung` pro Sub-Phase

Sammelt die nach Phase 24–27 fällige Dokumentations-Aktualisierung. Kein Code-Change, kein Logik-Change, nur Dokumente. Setzt voraus, dass die Code-Phasen abgeschlossen sind, damit die Dokumente nicht direkt nach Aktualisierung wieder veralten.

---

## 1. Problemanalyse

### 1.1 Bekannte veraltete Dokumente

| Dokument | Status | Grund |
|---|---|---|
| `PROJECT_ROADMAP.md` | ❌ veraltet seit ≥ Phase 23 | User-Aussage (07.05.2026): „komplett veraltet" |
| `README.md` | ⚠️ vermutlich veraltet | Letzte größere Strukturänderungen (Phase 23–27) nicht reflektiert |
| `docs/phase23_concept.md` | ⚠️ falsch platziert | Liegt im `docs/`-Root statt unter `docs/concepts/` |
| Sonstige `docs/*.md` (BETA_SYSTEM, CICD_GUIDE, etc.) | ❓ Stand unbekannt | Bei Phase 28 zu sichten |

### 1.2 Ziel

Alle Doku-Dateien auf den Stand nach Phase 27 bringen. Konsistente Struktur, klare Konventionen für künftige Updates.

---

## 2. Tasks

### 2.1 Sub-Phase 28.1 – Bestandsaufnahme

**Aufwand:** S · **Reihenfolge:** zuerst

Liste aller Dokumente in `docs/` und im Repository-Root durchgehen. Pro Datei klassifizieren:

- ✅ aktuell, kein Handlungsbedarf
- ⚠️ teilweise veraltet, gezielte Updates
- ❌ vollständig veraltet, Neufassung nötig
- 🗑️ obsolet, kann entfernt werden

Ergebnis als kleine Tabelle im Konzept-Doc (Section 5) oder als eigene `phase28-bestandsaufnahme.md`.

### 2.2 Sub-Phase 28.2 – README.md

**Aufwand:** M · **Reihenfolge:** nach 28.1

Vermuteter Inhalt (zu prüfen bei Sichtung):
- Was ist Berry-Gym? (Aktualität prüfen)
- Setup-Anleitung (auf aktuelles Python/Django/MariaDB-Setup abgleichen)
- Feature-Liste (Phase 23–27 reflektieren)
- Roadmap-Verweis (Link auf neue `PROJECT_ROADMAP.md`)
- Beitrag-Hinweise (falls vorhanden – aktualisieren)

### 2.3 Sub-Phase 28.3 – PROJECT_ROADMAP.md

**Aufwand:** M · **Reihenfolge:** nach 28.2

Komplette Neufassung. Vorschlag für neue Struktur:

- **Abgeschlossene Phasen** (1–27): kurze Beschreibung pro Phase, Link auf `docs/concepts/phaseXX_concept.md`
- **Aktive Phase**: aktuelle Arbeit
- **Geplante Phasen**: Roadmap-Items mit Reihenfolge-Begründung
- **Konventionen**: Branch-Naming, Konzept-Doc-Schema, Journal-Workflow

Sollte zukünftig zur Single-Source-of-Truth werden, was wir aktuell mit `journal.txt` und Konzept-Docs zusammen abdecken.

### 2.4 Sub-Phase 28.4 – Konzept-Doc-Aufräumen

**Aufwand:** S · **Reihenfolge:** nach 28.3

- `docs/phase23_concept.md` nach `docs/concepts/` verschieben (User-Aufgabe – kann delegiert oder selbst gemacht werden)
- Konzept-Docs-Verzeichnis prüfen: alle abgeschlossenen Phasen haben einen finalen Status-Eintrag, alle offenen Phasen haben aktuelle „nächste Schritte"
- Naming-Konvention prüfen: `phase23_concept.md` vs. `phase24_concept.md` vs. später z.B. `phase28-dokumentation.md` – einheitlich machen

### 2.5 Sub-Phase 28.5 – Sonstige Docs

**Aufwand:** abhängig von 28.1 · **Reihenfolge:** nach 28.4

Nach Befund aus 28.1: alle als ⚠️ oder ❌ markierten Dokumente überarbeiten. Reihenfolge nach Wichtigkeit/Sichtbarkeit:

- Operative Docs (DEPLOYMENT, RUNBOOK, CICD_GUIDE) zuerst, weil sie für aktuelle Arbeit gebraucht werden
- Feature-/System-Docs (BETA_SYSTEM, DISCLAIMER_SYSTEM, PUSH_NOTIFICATIONS) danach
- Spezial-Docs (LOAD_TESTING, LOGGING_GUIDE, SECRETS_SECURITY) zuletzt
- Veraltete entfernen oder archivieren

---

## 3. Reihenfolge & Begründung

```
28.1 (Bestandsaufnahme) → 28.2 (README) → 28.3 (ROADMAP) → 28.4 (Konzepte) → 28.5 (Sonstige)
```

- **28.1 zuerst:** Ohne Bestandsaufnahme weiß man nicht, was alles zu tun ist
- **28.2 vor 28.3:** README ist Außenfassade, ROADMAP ist intern – Außenfassade hat höhere Sichtbarkeit, also priorisieren
- **28.3 vor 28.4:** Neue ROADMAP definiert die Konvention, an der sich Konzept-Docs orientieren
- **28.5 zuletzt:** Spezial-Docs haben geringere Update-Priorität

---

## 4. Cross-Cutting Concerns

### 4.1 Doku-Stale-Prävention

Beim Aufräumen Konvention etablieren, die verhindert, dass Docs wieder schnell veralten:

- Pro Konzept-Phase: README-Touch-Check (1 Zeile prüfen: muss README aktualisiert werden?)
- Pro abgeschlossener Phase: ROADMAP-Eintrag setzen (statt „Phase 27 ✅" nur in Konzept-Doc)
- Journal-Workflow: am Ende einer Phase Hinweis „Doku-Pass nötig?" als Check

### 4.2 README als Außenkommunikation

Wenn die App perspektivisch nicht nur privat bleibt (User-Memory erwähnt Monetarisierung als deferred Topic), ist die README das erste Public-Facing-Doc. Tonalität und Inhalt entsprechend wählen.

---

## 5. Bestandsaufnahme (28.1, Stand 2026-05-30)

**In dieser Phase aktualisiert:**

| Dokument | Vorher | Aktion (Sub-Phase) |
|---|---|---|
| `README.md` / `README_EN.md` | ⚠️ Last-Updated 2026-03-26, M5–M9-Tail, Features ≤ Phase 23 | ✅ 28.2: Features 23–31 ergänzt, M5–M9-Tail durch aktuellen Phasen-Status ersetzt, Last-Updated 2026-05-30 |
| `docs/PROJECT_ROADMAP.md` | ❌ veraltet (nur Phasen 1–23, kein Last-Updated) | ✅ 28.3: kompakte Übersichtstabelle 1–31 + Konzept-Links, Header/Datum, Phasen-24–31-Bridge; Detail 1–23 erhalten |
| `docs/concepts/phase23–31` | top-Header größtenteils noch „📋 Konzept" trotz Abschluss | ✅ 28.4: top-Status-Header aktualisiert (✅/⏸️/🔄) |
| `docs/concepts/phase23_concept.md` | laut Konzept im `docs/`-Root vermutet | ✅ liegt bereits unter `docs/concepts/` – 28.4-Move war schon erledigt |

**Noch offen (28.5, sinnvoll nach Phase 27):**

| Dokument(e) | Klassifikation |
|---|---|
| `DEPLOYMENT.md`, `RUNBOOK.md`, `CICD_GUIDE.md`, `CODE_QUALITY.md` | ⚠️ operativ – Stichprobe in 28.5 |
| `BETA_SYSTEM`, `DISCLAIMER_SYSTEM`, `PUSH_NOTIFICATIONS_SETUP`, `OPENROUTER_SETUP`, `SECRETS_SECURITY`, `LOGGING_GUIDE`, `LOAD_TESTING`, `LAUNCH_CHECKLIST`, `PDF_EXPORT_OPTIMIERUNG` | ❓ Stand unbekannt – in 28.5 sichten |
| `AGENTS.md`, `CLAUDE.md` | ✅ aktuell (zuletzt mit Bramble-MCP-Umstellung gepflegt) |
| `SECURITY.md`, `CONTRIBUTING.md`, `.github/*` | ❓ Stichprobe, niedrige Prio |
| `ai_coach/README.md`, `core/tests/README.md`, `dev-scripts/*.md` | ❓ niedrige Prio |

> Per-Sub-Phasen-Header **innerhalb** von `phase29`/`phase30` (Zeilen „📋 Konzept")
> sind noch nicht einzeln nachgezogen – kosmetisch, in 28.5/Folge-Pass.

---

## 6. Akzeptanzkriterien

- Alle ⚠️ und ❌ klassifizierten Docs überarbeitet
- README spiegelt aktuellen Projektstand wider
- PROJECT_ROADMAP.md ist Single-Source-of-Truth für Phasenstand
- Doku-Stale-Prävention als Workflow etabliert

---

## 7. Offene Fragen

- F1: README-Sprache – Deutsch (wie Codebase) oder Englisch (für eventuelle Öffnung)?
- F2: ROADMAP-Tiefe – nur Phasen-Liste oder mit Begründungs-Text pro Entscheidung?
- F3: Welche Docs aus `docs/`-Root sind tatsächlich aktuell? (klärt 28.1)

---

## 8. Status-Updates

- **2026-05-30 (Start):** Phase 28 begonnen. Entscheidung mit User: style-
  unabhängige Teile (28.1–28.4) sofort, da README/ROADMAP-Inhalt nicht vom
  Phase-27-Style-Overhaul abhängt; 28.5-Tiefen-Rewrites + finaler README-Pass
  nach Phase 27. ROADMAP-Tiefe: kompakt + Links.
- **2026-05-30:** 28.1 Bestandsaufnahme (§5), 28.2 README DE+EN, 28.3
  PROJECT_ROADMAP (Übersichtstabelle 1–31), 28.4 Konzept-Status-Header
  umgesetzt. Offene Frage F1 (README-Sprache): bleibt **DE + EN** (beide
  README-Dateien gepflegt). F2 (ROADMAP-Tiefe): **kompakt + Links**.
- **Offen:** 28.5 (Sonstige Docs sichten) + finaler README-Pass nach
  Phase 27 (Style-abhängige Report-Beschreibungen).
