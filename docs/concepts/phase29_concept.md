# Phase 29 – Plan-Generator-Konsistenz & Qualität

**Status:** ✅ Abgeschlossen (19.–20.05.2026)
**Vorgänger:** Phase 25 (Layout-Refactor, läuft – Sub-Phase 25.8 als PR offen)
**Nachfolger:** Phase 26 (Konsolidierungs-Logik) – wurde nach 29 verschoben
**Branch-Schema:** `feature/phase-29-X-kurzbeschreibung` pro Sub-Phase

> **Priorisierung:** Phase 29 wird vor Phase 26/27/28 gezogen, weil die nächste reale Trainingsplan-Generierung in ~5 Wochen ansteht. Der Plan-Generator liefert aktuell nicht das, was die UI-Eingaben verlangen – das hat höhere Priorität als Konsolidierungs-Logik oder Style.

> **Scope-Abgrenzung:** Diese Phase adressiert **akute Bugs und kleine Qualitätsverbesserungen** im Plan-Generator. Die größere architektonische Frage „Report-Output systematisch als Plan-Generator-Input" (Feedback-Loop) ist als eigene spätere Phase (Phase 30 oder später) aufgehoben. In 29.3 wird eine abgespeckte Variante davon umgesetzt: die Liste untertrainierter Muskelgruppen aus dem aktuellen Report wird als Generator-Hint genutzt.

---

## 1. Problemanalyse

### 1.1 Test-Befunde (18.05.2026)

Zwei Test-Generierungen mit unterschiedlichen LLMs ergaben drei reproduzierbare Probleme:

**Test 1 – Gemini Flash 2.5** (Plan: 3 Tage Push/Pull/Legs, Anforderung „22 Sätze pro Tag"):
- Output: Tag 1 = 18, Tag 2 = 18, Tag 3 = 19 Sätze
- Wochensumme 55 Sätze, identisch mit Status quo (3 × 18 = 54)
- Tag-3-Asymmetrie (19 statt 18)
- 4 von 5 untertrainierten Muskelgruppen bekommen **weniger** Sätze als im vorherigen Plan, nicht mehr

**Test 2 – Sonnet 4.6** (zweimal hintereinander generiert):
- Output: Nur 2 Tage (Push/Pull), Legs-Tag fehlt komplett
- Plan-Titel sagt weiterhin „3er-Split (Push/Pull/Legs)"
- Plan-Header zeigt „Trainingsgruppe: 2 Trainingstage"
- Bauchmuskeln und hintere Schulter inhaltlich besser adressiert pro Tag als bei Gemini
- Schulterdrücken auf 4 Sätze (Gemini: 3) – Untertrainiert-Hint wirkt teilweise
- Zwei Sonnet-Läufe lieferten beide Male 2 Tage Push/Pull (deterministisch), Übungs-Auswahl pro Tag variierte
- Beim zweiten Lauf hat der Validator eine Übung korrigiert – Validator ist also aktiv und greift ein

### 1.2 Drei abgeleitete Findings

**F1 – Volumen-Steuerung wirkt nicht**
UI-Eingabe „Sätze pro Tag" (22 angefordert) wird vom Generator nicht umgesetzt. Output landet bei ~18, was zufällig dem Status-quo-Default entspricht. Hypothesen:
- (a) Prompt-Variable wird nicht durchgereicht (UI sendet, Prompt-Template ignoriert)
- (b) Validator hat Hard-Cap und verwirft hohe Set-Zahlen
- (c) LLM ignoriert die numerische Vorgabe trotz Prompt-Erwähnung
- (d) Eine ältere Default-Konfiguration überschreibt User-Input

**F2 – Strukturbruch bei Sonnet: nur 2 statt 3 Tage**
Sonnet 4.6 erzeugt deterministisch 2 Tage, obwohl 3 Tage angefordert sind. Gemini erzeugt korrekt 3 Tage. Hypothesen:
- (a) Validator verwirft den dritten Tag wegen einer Regel, die Sonnet-Output verletzt aber Gemini-Output nicht
- (b) Token-Output-Limit pro Generation-Call wird mit Sonnets ausführlicheren Tag-Definitionen erreicht, bevor Tag 3 erzeugt ist
- (c) Prompt-Template oder Parser hat Edge-Case-Bug, der auf bestimmte Sonnet-Antwortstruktur trifft

**Phase-23-Hinweis:** Plan-Generator wurde laut User-Aussage zuletzt in Phase 23 angefasst. Möglicherweise wurde dort eine Validator-Regel hinzugefügt, die mit Sonnet-Output anders interagiert als mit Gemini-Output. Bei der Diagnose Validator-Regeln aus Phase 23 explizit prüfen.

**F3 – Fokus-Hint und Untertrainiert-Liste wirken schwach**
Plan-Titel „Fokus Hamstrings & Bauch" führt im Gemini-Output nicht zu erhöhtem Volumen für diese Muskelgruppen (Hamstrings 4 Sätze, Bauch 3 Sätze – nicht prominent). Im Sonnet-Output etwas besser (Bauch explizit als eigene Übung), aber Hamstrings überhaupt nicht abgedeckt (Legs-Tag fehlt). Aktueller Trainings-Report listet 5 untertrainierte Muskelgruppen – der Generator nutzt diese Information offenbar nicht systematisch.

### 1.3 Ziel der Phase

- Strukturelle Garantie: Wenn 3 Tage angefordert werden, kommen 3 Tage raus (F2)
- Volumen-Steuerung: UI-Eingabe „Sätze pro Tag" wirkt messbar auf Output (F1)
- Fokus-Wirkung: Untertrainierte Muskelgruppen aus Report werden im Plan systematisch aufgewertet (F3, begrenzte Form)
- Aktuelles Modell **Sonnet 4.6 bleibt aktiv** – Modellwechsel ist nicht Teil dieser Phase

---

## 2. Architektur-Skizze (zu verifizieren beim Start)

Bekannt:
- Generator-Code: `C:\Dev\Berry-Gym\ai_coach\plan_generator.py`
- Validator: `plan_validator.py` (Pfad nicht bestätigt, vermutlich `ai_coach/plan_validator.py`)
- LLM: Sonnet 4.6 (aktuell aktiv, vorher Gemini Flash 2.5)
- User-Memory bestätigt: Validator fängt binäre Fehler (fehlende Felder, Duplikate, Pflicht-Übungen), kann aber keine Trade-off-Qualität enforcen

Beim Start zu klären:
- Wo ist das Prompt-Template? Inline im Code oder externe Datei?
- Wie werden UI-Eingaben (Sätze pro Tag, Fokus-Hint, Tage-Anzahl) in den Prompt eingebaut?
- Welche Validator-Regeln existieren? Welche wurden in Phase 23 hinzugefügt?
- Gibt es einen Retry-Loop wenn die Validierung fehlschlägt? Was passiert mit verworfenen Tagen/Übungen?
- Wo werden untertrainierte Muskelgruppen (aus dem Trainings-Report) intern gespeichert? Verfügbar zur Generierungs-Zeit?

---

## 3. Tasks

### 3.1 Sub-Phase 29.1 – Diagnose

**Status:** 📋 Konzept · **Aufwand:** M · **Reihenfolge:** zuerst

#### Aufgabe

Reproduzierbare Diagnose aller drei Findings, ohne sofort zu fixen. Output: Diagnose-Bericht im Konzept-Doc (Section 9 oder eigene `phase29-diagnose.md`) mit klarer Zuordnung Symptom → Ursache.

#### Vorgehen

1. **Code-Sichtung** `ai_coach/plan_generator.py` und Validator. Prompt-Template lokalisieren. Datenfluss UI → Generator → Validator → DB-Speicherung nachvollziehen.

2. **Reproduktion mit Logging.** Eine Generierungs-Run mit aktiviertem Debug-Output:
   - Welcher Prompt geht raus (inkl. UI-Eingaben)
   - Welche Raw-Response kommt von Sonnet zurück
   - Was macht der Validator (Annahmen, Korrekturen, Verwerfungen)
   - Was wird gespeichert
   
   Wenn nötig: Temporäre Logging-Statements einbauen, nach Diagnose wieder entfernen.

3. **Validator-Regel-Audit.** Liste aller Validator-Regeln mit Datum/Phase-Zuordnung. Insbesondere Regeln aus Phase 23 markieren. Pro Regel klären: Würde diese Regel den dritten Tag (Legs) eines Sonnet-Outputs verwerfen?

4. **Token-Limit-Check.** Welche max_tokens-Einstellung läuft im Sonnet-Call? Reichen die Tokens für 3 vollständige Tag-Definitionen?

#### Output

Diagnose-Bericht mit:
- F1 Volumen: Welche der vier Hypothesen (a-d) trifft zu?
- F2 Strukturbruch: Welche der drei Hypothesen (a-c) trifft zu?
- F3 Fokus: Wie wird der Fokus-Hint aktuell im Prompt verwendet? Wie kommt die Untertrainiert-Liste in den Generator (oder gar nicht)?
- Empfehlung pro Finding: Fix-Strategie

#### Akzeptanzkriterien

- Jeder der drei Findings hat eine identifizierte Ursache (kein „bleibt unklar")
- Fix-Strategie pro Finding ist klein genug für eine Sub-Phase mit S/M-Aufwand
- Keine Fixes in 29.1 – nur Diagnose, damit 29.2/29.3 auf solider Grundlage stehen

---

### 3.2 Sub-Phase 29.2 – Strukturelle Garantien

**Status:** 📋 Konzept · **Aufwand:** S–M · **Reihenfolge:** nach 29.1

#### Problem

Bug F2: Sonnet erzeugt nur 2 Tage statt der angeforderten 3.
Bug F1: Eingabe „Sätze pro Tag" wirkt nicht auf Output.

#### Lösungsansatz

Abhängig vom Diagnose-Befund aus 29.1. Mögliche Strategien:

**Wenn F2-Ursache = Validator verwirft Tag 3:**
- Validator-Regel identifizieren und korrigieren (oder Regel optional machen)
- Re-Validierungs-Logik: Bei verworfenem Tag → erneute Generation für genau diesen Tag, nicht ganzen Plan verwerfen

**Wenn F2-Ursache = Token-Limit:**
- max_tokens für Generation-Call erhöhen
- Oder: Plan in zwei Calls splitten (Tag 1+2 in Call 1, Tag 3 in Call 2)

**Wenn F2-Ursache = Parser-Bug:**
- Parser robust machen gegen Sonnet-Antwortstruktur

**Wenn F1-Ursache = Prompt-Variable nicht durchgereicht:**
- UI-Wert konsistent ins Prompt-Template einbauen
- Sätze-pro-Tag muss prominent und numerisch klar erwähnt sein im Prompt

**Wenn F1-Ursache = LLM ignoriert numerische Vorgabe:**
- Prompt-Engineering: stärkere Constraint-Formulierung, ggf. Explizit-Validierung im Prompt selbst
- Validator als zweite Verteidigungslinie: bei Set-Anzahl-Abweichung > Toleranz → Retry mit härterem Hint

#### Akzeptanzkriterien

- 3-Tage-Anforderung erzeugt deterministisch 3 Tage (verifiziert mit 3 unabhängigen Test-Generierungen)
- „Sätze pro Tag X" erzeugt im Plan ungefähr N × X Sätze (Toleranz ±10 % über alle Tage, Tag-Symmetrie ±2 Sätze zwischen Tagen)
- Beide Garantien gelten für Sonnet 4.6 (Gemini-Kompatibilität nicht erforderlich, weil Modellwechsel-Rückkehr nicht geplant)
- Tests in `ai_coach/tests/` (falls existiert, sonst neu anlegen) decken beide Garantien ab

---

### 3.3 Sub-Phase 29.3 – Untertrainiert-Liste als Generator-Input

**Status:** 📋 Konzept · **Aufwand:** M · **Reihenfolge:** nach 29.2

#### Problem

F3: Der aktuelle Plan-Generator nutzt die Untertrainiert-Liste aus dem letzten Trainings-Report nicht systematisch. Konsequenz: Schwachstellen bleiben oder verschlimmern sich plan-über-plan.

Dies ist die **abgespeckte Variante von F2 (Feedback-Loop)**. Die volle Architektur (Plateau-Status, Konsolidierungs-Signale, Volumen-Trends → Generator) bleibt für eine spätere Phase aufgehoben.

#### Lösungsansatz

1. **Datenfluss klären:** Wo wird die Untertrainiert-Klassifikation berechnet (vermutlich `core/utils/advanced_stats.py` oder Helper, der vom PDF-Pfad benutzt wird)? Beim Generierungs-Zeitpunkt zugänglich machen.

2. **Prompt-Integration:** Untertrainiert-Liste in den Prompt einbauen als explizite Constraint, z.B.:
   ```
   Folgende Muskelgruppen sind untertrainiert und MÜSSEN im neuen Plan
   mit mindestens 12 Sätzen pro Woche adressiert werden:
   - Schulter-Vordere (aktuell 9 Sätze)
   - Hamstrings (aktuell 9 Sätze)
   [...]
   ```

3. **Validator-Erweiterung:** Validator prüft, dass die angegebenen Muskelgruppen tatsächlich mit ausreichend Sätzen im Plan vorkommen. Falls nicht: Retry oder explizite Fehlermeldung.

#### Edge Cases

- **Generator kommt mit allen Constraints in Konflikt:** Volumen-Vorgabe + Tag-Anzahl + Untertrainiert-Liste passen ggf. nicht gleichzeitig in einen Plan. Priorisierungs-Regel definieren (z.B. Untertrainiert-Adressierung > Volumen-Genauigkeit > Tag-Symmetrie).
- **Keine Trainings-Historie vorhanden:** Neuer User ohne Report → Untertrainiert-Liste ist leer, Constraint entfällt.
- **Untertrainiert-Liste durch Set-Attribution-Artefakt verfälscht:** Phase-24.4-Audit hat gezeigt, dass 5 Muskelgruppen exakt 9 Sätze haben – möglicherweise systemisch. Wenn das Phänomen real ist, gibt der Generator falsche Prioritäten. Nicht in 29.3 fixen, aber als Risiko dokumentieren.

#### Akzeptanzkriterien

- Aktuelle Untertrainiert-Liste fließt nachweislich in jeden generierten Plan ein
- Generierter Plan enthält für jede gelistete Muskelgruppe mindestens N Sätze (Schwellenwert beim Implementieren festlegen, Vorschlag: N=12 entsprechend „Optimal"-Bereich)
- Tests decken den „neue Plan adressiert Untertrainiert-Liste"-Fall ab

---

## 4. Reihenfolge & Begründung

```
29.1 (Diagnose) → 29.2 (Strukturelle Garantien) → 29.3 (Untertrainiert-Input)
```

- **29.1 zuerst:** Ohne Diagnose sind 29.2-Fixes Schüsse ins Blaue
- **29.2 vor 29.3:** Strukturelle Garantien (Tag-Anzahl, Set-Volumen) sind Voraussetzung dafür, dass 29.3 überhaupt sinnvoll funktioniert
- **29.3 zuletzt:** Erweitert den Generator inhaltlich, baut auf stabilem Struktur-Fundament

---

## 5. Cross-Cutting Concerns

### 5.1 Sonnet bleibt aktiv

Aktuelle Konfiguration: Sonnet 4.6 als Plan-Generator-LLM. Modellwechsel zurück zu Gemini ist nicht geplant. Begründung: Sonnet-Output ist pro Tag inhaltlich besser, nur der Strukturbruch ist problematisch – und der wird in 29.2 adressiert.

Konsequenz: Tests und Fix-Strategien können Sonnet-Spezifika berücksichtigen. Keine Generator-Kompatibilität für beide Modelle erforderlich.

### 5.2 Phase 23 als Verdachts-Quelle

User-Erinnerung: Plan-Generator wurde zuletzt in Phase 23 angefasst. Bei Validator-Regel-Audit (29.1) Regeln aus Phase 23 priorisiert prüfen. Möglicherweise eingeschleppte Regression, die mit Sonnet-Output sichtbar wurde.

### 5.3 Volle Feedback-Loop später

F2 in der ursprünglichen Befund-Liste war „Plan-Generator-Feedback-Loop" als architektonische Aufgabe. Davon wird in 29.3 nur ein Teil umgesetzt (Untertrainiert-Liste). Die volle Architektur (Plateau-Status, Konsolidierungs-Signale, Volumen-Trends, RPE-Pattern als Generator-Input) bleibt für eine spätere Phase (Arbeitsname „Phase 30: Adaptive Plan Generation").

---

## 6. Offene Fragen (beim Start zu klären)

- F-29-1: Welche der vier F1-Hypothesen trifft zu?
- F-29-2: Welche der drei F2-Hypothesen trifft zu?
- F-29-3: Wo liegt das Prompt-Template? Inline oder extern?
- F-29-4: Gibt es Tests für den Generator? Wo?
- F-29-5: max_tokens im Sonnet-Call – ausreichend für 3 Tage?
- F-29-6: Welche Validator-Regeln stammen aus Phase 23?
- F-29-7: Wie wird die Untertrainiert-Liste berechnet, ist sie zur Generierungs-Zeit zugänglich?

---

## 7. Akzeptanzkriterien (Phase-Gesamt)

- Drei unabhängige Test-Generierungen (3 Tage, 22 Sätze/Tag, Fokus auf 2 untertrainierte Muskelgruppen) liefern:
  - Alle 3 Tage ✓
  - Set-Volumen ungefähr wie angefordert (Toleranz ±10 %) ✓
  - Untertrainiert-Liste adressiert mit mindestens 12 Sätzen pro genannte Muskelgruppe ✓
- Sonnet 4.6 bleibt aktives Modell
- Tests für alle drei Garantien grün
- Konzept-Doc abgeschlossen, Status-Updates pro Sub-Phase dokumentiert

---

## 8. Folge-Phasen

Nach Phase 29 wird die ursprüngliche Pipeline wieder aufgenommen:

- **Phase 26:** Konsolidierungs-Logik zeitlich begrenzen (war geplant nach Phase 25, wurde wegen Phase 29 verschoben)
- **Phase 27:** Style-Overhaul
- **Phase 28:** Dokumentations-Aktualisierung
- **Phase 30 (Arbeitstitel):** Volle Adaptive Plan Generation (Plateau-Status, Konsolidierung, RPE-Pattern, Volumen-Trends als Generator-Input)

---

## 9. Status-Updates pro Sub-Phase

### 29.1 – Diagnose · ✅ abgeschlossen (19.05.2026)

Branch `feature/phase-29-1-generator-diagnose`. Vollständiger Diagnose-Bericht:
**`docs/concepts/phase29-diagnose.md`**.

Ergebnis (Ursache pro Finding, reproduziert auf Sonnet 4.6):

- **F1** – Hypothese **(c)**: Der Prompt widerspricht sich – eine 4 Sätze
  breite Range (Untergrenze = `sets_per_session - 4` = 18 = Status quo) plus
  drei hartcodierte „18 Sätze“-Beispiel-Tage. → Fix in 29.2 (S).
- **F2** – Hypothese **(b)** primär: `max_tokens=3000` für `3er-split` zu
  niedrig für Sonnet 4.6. Reproduziert: `completion_tokens` = 3000 = exakt
  `max_tokens`, Antwort abgeschnitten. `json-repair` rettet still einen
  Teil-Plan (mal 2 Tage, mal Stummel-Legs). Validator verwirft **keinen** Tag
  (Regel-Audit). → Fix in 29.2 (S–M).
- **F3** – Label-Format-Mismatch: `data_analyzer` liefert DB-Konstanten
  (`BEINE_HAM:`), `prompt_builder.WEAKNESS_LABEL_TO_KEYS` kennt nur
  menschenlesbare Labels → untertrainierte Muskelgruppen werden still aus dem
  Prompt verworfen; zusätzlich fordert der Weakness-Block nur „1 Übung“ statt
  Volumen. → Fix in 29.3 (M).

Nebenbefunde: Phase-23-Verdacht **widerlegt** (Generator zuletzt in Phase 20
angefasst, keine Phase-23-Validator-Regel). `push_pull_balance` ist immer 0
(gleiche DB-Konstante-vs-Label-Bug-Klasse wie F3).
