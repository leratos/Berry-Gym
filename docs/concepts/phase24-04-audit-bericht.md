# Phase 24.4 – Audit-Bericht: Set-Attribution

**Status:** ✅ Abgeschlossen (08.05.2026)
**Branch:** `feature/phase-24-4-set-attribution-audit`
**Vorgehen:** Read-only Django-Shell-Query auf Production-DB (User `lera@last-strawberry.com`, Skript `/tmp/phase24_4_audit.py`)
**Zeitraum:** Letzte 30 Tage ab Server-Zeit 08.05.2026 16:53 UTC, also 08.04.2026 – 08.05.2026 (im Mai-Report war es 07.04.2026 – 07.05.2026, ein Tag kürzer; daher hat das Audit eine zusätzliche Legs-Session erfasst – siehe 1.2)

---

## 1. Befund

### 1.1 Hypothese widerlegt

Die im Phase-24-Konzept formulierte Hypothese, die fünf Muskelgruppen mit exakt 9 Sätzen seien Folge von **Default-/Synergisten-Attribution oder alten experimentellen Sessions**, bestätigt sich **nicht**.

Alle 5 betroffenen Muskelgruppen erhalten ihre Sätze ausschließlich aus genau einer Übung im **aktiven Plan** "Hypertrophie-3ER/SPLIT – Fokus Hüftbeuger (02.04.2026)". Die Konstellation ist strukturell, nicht artefaktisch:

- 3 Plan-Tage (Push / Pull / Legs)
- pro Plan-Tag genau **1 Übung pro betroffene Muskelgruppe**
- pro Übung **3 Arbeits-Sätze**
- im Bewertungs-Fenster (KW15–KW17) **3 Trainings-Wochen**

→ 3 Sätze × 1 Übung × 3 Wochen = **9** für jede der fünf Muskelgruppen.

Fünfmal exakt 9 ist also kein Zufall, sondern eine triviale arithmetische Folge des Plan-Schnitts. Die User-Hypothese vom 07.05.2026 (*„anfang da hatte ich eher experimentiert"*) war eine plausible Vermutung, trifft aber nicht zu – die Sätze stammen alle aus abgeschlossenen Sessions des aktuellen Plans.

### 1.2 Tatsächliche Treffer pro Muskelgruppe

| Muskelgruppe | Sätze (08.05.) | Sätze (07.05. lt. Report) | Übung | Plan-Tag |
|---|---|---|---|---|
| SCHULTER_VORN | 9 | 9 | Schulterdrücken (Sitzend, Kurzhantel) – id=6 | Push |
| SCHULTER_SEIT | 9 | 9 | Seitheben (Kurzhantel) – id=7 | Push |
| BEINE_HAM | 12 | 9 | Rumänisches Kreuzheben (RDL) – id=21 | Legs |
| HUEFTBEUGER | 12 | 9 | Psoas Marches (Körpergewicht) – id=96 | Legs |
| BAUCH | 12 | 9 | Hanging Leg Raises – id=41 | Legs |

Heute (08.05.2026) wurde eine vierte Legs-Session (Session id=92) absolviert, die im Mai-Report (Stichtag 07.05.) noch nicht enthalten war. Daher zeigt das Audit für die Legs-Muskelgruppen 12 statt 9. Die Push-Muskelgruppen sind unverändert bei 9.

Alle herangezogenen Sätze sind:
- aus dem aktuellen aktiven Plan (Plan-Gruppe `553417d0-8e5d-4b26-b67a-c22be3934a00`),
- in abgeschlossenen Sessions (`abgeschlossen=True`),
- keine Aufwärmsätze (`ist_aufwaermsatz=False`),
- keine Deload-Sessions (`einheit__ist_deload=False`).

### 1.3 Code-Modell der Set-Attribution (F1)

`Uebung` hält:

- `muskelgruppe` – CharField, **ein** Hauptmuskel via Choices (`MUSKELGRUPPEN`).
- `hilfsmuskeln` – JSONField, **Liste** ohne Faktor.

Aggregations-Funktion: `core.export.stats_collector.collect_muscle_balance`. Sie filtert via `Satz.uebung__muskelgruppe=<key>` (Hauptmuskel-only) gegen das 30-Tage-Fenster. **Hilfsmuskeln werden nicht in die Set-Counts einbezogen.** Es gibt im Codebase keine Stelle, an der `hilfsmuskeln` für Statistiken gelesen wird – nur Stammdaten-Anzeige (Admin) und Auswahl-Forms.

### 1.4 Auswertungs-Filter „nur aktiver Plan" (F2)

Existiert bereits (`get_active_plan_exercise_ids`) und wird in der PDF-Pipeline für **drei** Stellen verwendet:

- Top-5-Übungen (`build_top_uebungen`)
- Kraftentwicklung (`collect_strength_progression`)
- RPE-Quality-Window (Plan-Clamping)

**Nicht** verwendet in:

- `collect_muscle_balance` ← Audit-Ziel
- `collect_push_pull` (Folge aus muskelgruppen_stats)
- Header-Aggregationen (Volumen, Sätze, Sessions)

Für 24.4 ergibt sich aus dem Befund (1.1): Ein Plan-Filter würde an den Set-Counts in den 5 Muskelgruppen **nichts** ändern, weil ohnehin alle Sätze aus dem aktiven Plan stammen. Für andere Sub-Phasen (24.3 Header) ist das Fehlen eines Plan-Filters dennoch relevant.

### 1.5 Persistenz alter Sessions (F3)

`Trainingseinheit.plan` ist FK auf den Plan zur Session-Zeit (nullable). Sessions werden bei Plan-Wechsel weder gelöscht noch markiert. Die Historie bleibt vollständig erhalten (gut für Lifetime-Statistiken), und Auswertungen können bei Bedarf über `Trainingseinheit.plan` filtern.

---

## 2. Sekundärer Befund: Hilfsmuskeln werden nicht gezählt

Während das Audit lief, ist ein verwandtes – aber nicht in der ursprünglichen Frage angelegtes – Problem aufgefallen: Die Übertraining/Untertraining-Diagnose pro Muskelgruppe basiert ausschließlich auf Hauptmuskel-Treffern. Faktisches Volumen, das über Synergisten auf einen Muskel wirkt, fließt nicht ein.

Beispiele aus dem Audit-Fenster:

| Muskelgruppe | Hauptmuskel-Sätze | Hilfsmuskel-Sätze (info) | Beitragende Übungen (Hilfsmuskel) |
|---|---|---|---|
| SCHULTER_VORN | 9 | 36 | Bankdrücken LH (12), Schrägbankdrücken KH (9), Assistierte Dips (9), Trizeps Overhead (6) |
| SCHULTER_SEIT | 9 | 9 | Schulterdrücken Sitzend KH (9) |
| BEINE_HAM | 12 | 0 | – |
| HUEFTBEUGER | 12 | 12 | Hanging Leg Raises (12) |
| BAUCH | 12 | 74 | Squat (16), Klimmzüge (16), Bulgarian Split (12), Rudern (12), Bizeps Curls (12), Trizeps Overhead (6) |

Effekt im PDF-Report: BAUCH hat im Mai-Report wahrscheinlich „untertrainiert" gezeigt (9 Sätze, Empfehlung 12–20), faktisch wirken aber 86 Sätze (12 Haupt + 74 Hilfs) auf den Bauchmuskel. Dasselbe Muster gilt schwächer für SCHULTER_VORN (9 / 45) und HUEFTBEUGER (12 / 24).

Das ist nicht das ursprünglich gesuchte Artefakt, aber ein systematischer Effekt mit Auswirkung auf:

- Übertraining/Untertraining-Bewertung pro Muskelgruppe
- Push/Pull-Empfehlung (24.2) – Empfehlungs-Logik basiert auf demselben Hauptmuskel-Count
- Schwachstellen-Liste

### 2.1 Datenqualitäts-Issue in `hilfsmuskeln`

Bei der Stammdaten-Sichtung sind inkonsistente Werte aufgefallen. Die Liste `hilfsmuskeln` mischt zwei Schreibweisen:

- **Keys** (Großbuchstaben-Slugs, korrekt): `'TRIZEPS'`, `'SCHULTER_SEIT'`, `'HUEFTBEUGER'`
- **Labels** (lesbare Form, nicht maschinenverwertbar): `'Trizeps'`, `'Bauch'`, `'Schulter - Vordere'`, `'Hüftbeuger'`

Konkret betroffen (Auszug aus Audit-Output, ohne Anspruch auf Vollständigkeit):

| Übung-ID | Bezeichnung | hilfsmuskeln (gemischt) |
|---|---|---|
| 73 | Pike Push-ups | `['Trizeps', 'Brust']` |
| 75 | Upright Rows | `['Rücken - Nacken/Trapez', 'Schulter - Vordere']` |
| 94 | Lying Leg Raises | `['Bauch']` |
| 95 | Standing Knee Raises | `['Bauch']` |
| 96 | Psoas Marches | `['Bauch']` |
| 97 | Mountain Climbers | `['Bauch', 'Brust', 'Schulter - Vordere']` |
| 99 | Dead Bug | `['Hüftbeuger']` |
| 100 | Crunch | `[]` |
| 101 | Reverse Crunch | `['Hüftbeuger']` |

Weil heute keine Aggregation auf `hilfsmuskeln` zurückgreift, bleibt das aktuell folgenlos. Sobald 24.4b (Synergisten in Aggregation einbeziehen) angegangen wird, muss diese Inkonsistenz vorher bereinigt sein. `dev-scripts/fix_hilfsmuskeln.py` existiert bereits – **vor einer Migration prüfen, ob das Skript dasselbe macht oder nicht.**

---

## 3. Empfehlung Fix-Strategie

### 3.1 Bewertung der vier Optionen aus dem Konzept

| Option (laut Konzept) | Bewertung |
|---|---|
| (a) Daten-Bereinigung alter Sessions | **Nicht nötig.** Hypothese widerlegt – alle Sätze stammen aus dem aktiven Plan. |
| (b) Code-Korrektur Aggregations-Logik | **Optional (24.4b), siehe 3.2.** |
| (c) Stammdaten-Anpassung Muskel-Faktoren | **Verbunden mit (b).** Schema-Änderung wäre größer. |
| (d) Auswertungs-Filter „nur aktiver Plan" | **Nicht für 24.4 nötig** – würde an den Counts nichts ändern. Für 24.3 (Header) separat zu betrachten. |

### 3.2 Empfehlung: 24.4 als Audit-only abschließen, KEINE Folge-Sub-Phase

Weil:

1. Das ursprüngliche Audit-Ziel (5×9-Anomalie aufklären) ist abgeschlossen, kein Bug.
2. Eine Synergisten-Aggregation (24.4b) wäre eine **inhaltliche Erweiterung** der Aussage des Reports, kein Bug-Fix. Der Aufwand ist nicht trivial:
   - Stammdaten-Migration `hilfsmuskeln` (24.4a) – S
   - Faktor-Konzept entscheiden (binär 1.0 vs. 0.5 vs. übungsspezifisch) – Diskussion
   - `collect_muscle_balance`-Erweiterung + neue Tests – S
   - Empfehlungs-Schwellen `EMPFOHLENE_SAETZE` ggf. neu kalibrieren (sonst werden plötzlich alle Muskeln „übertrainiert") – M
3. Die ursprüngliche Phase-24-Bilanz formuliert: *„Keine neuen Features, keine neuen Metriken – nur Bereinigung, Korrektur und kontextabhängige Empfehlungslogik."* Synergisten-Aggregation ist eher Feature als Bereinigung.

### 3.3 Konsequenzen für nachgelagerte Sub-Phasen

- **24.2 Push/Pull-Empfehlung:** Kann ohne 24.4-Folge-Aktion umgesetzt werden. Befund bestätigt: `muskelgruppen_stats[muskel].status` (Hauptmuskel-only) ist die richtige Datenbasis für die kontextabhängige Empfehlung. Edge-Case-Anmerkung im Konzept (*„Befund aus 24.4 kann Push/Pull-Sätze verschieben"*) entfällt.
- **24.3 Header-Zahlen:** Audit hat nebenbei `lifetime: 54 Sessions, 773 Sätze` gezeigt. Das passt grob zu den 53/757 im Mai-Report (Differenz ist die heutige Session 92). Bestätigt die Sub-Phase-Diagnose: Header zeigt Lifetime, nicht 30-Tage-Fenster.

### 3.4 Optionaler Anhang: Phase 25-Liste erweitern

Falls in Phase 25 ohnehin Layout-Refactor läuft, könnte der Hinweis sinnvoll sein:

- **Muskelgruppen-Diagnose-Sektion könnte einen Hilfsmuskel-Hinweis enthalten** (z.B. „BAUCH wirkt zusätzlich als Stabilisator in 5 weiteren Übungen, ~74 Sätze"), ohne die Zählung selbst zu verändern. Reine Transparenz-Anzeige, kein Logik-Eingriff.

Dieser Hinweis wird in Phase 25-Layoutliste aufgenommen (siehe Konzept §6).

### 3.5 Hilfsmuskeln-Stammdaten-Bereinigung – wann?

Nicht jetzt. Nur wenn 24.4b (oder eine spätere Phase) Synergisten in eine Auswertung einbezieht. Solange die Liste nirgends programmatisch ausgewertet wird, ist die Inkonsistenz Cosmetic Debt. Empfehlung: Aufnahme in eine generische „Datenqualität"-Sammelphase nach Phase 25, zusammen mit anderen Stammdaten-Themen (z.B. BIA-Plausibilitätsprüfung aus §5.3).

---

## 4. Akzeptanzkriterien des Audits (siehe Konzept §3.1)

- [x] Audit-Bericht im Konzept-Verzeichnis vorhanden (diese Datei)
- [x] Fix-Strategie für jede der fünf Muskelgruppen empfohlen → **„keine Aktion nötig"** (Befund: kein Artefakt, sondern Plan-Struktur)
- [x] Folge-Sub-Phasen klar abgegrenzt: **24.4 schließt ohne Folge-Aktion**, 24.2 wird unblockiert. Hilfsmuskeln-Aggregation und Stammdaten-Bereinigung optional in späteren Phasen.

---

## 5. Reproduzierbarkeit

Das Audit-Skript `/tmp/phase24_4_audit.py` auf dem Server ist read-only und kann jederzeit erneut ausgeführt werden:

```bash
ssh lera@last-strawberry.com 'cd gym.last-strawberry.com && source venv/bin/activate && python manage.py shell < /tmp/phase24_4_audit.py'
```

Volltext-Output ist lokal in `c:/tmp/phase24_4_audit_output.txt` archiviert.
