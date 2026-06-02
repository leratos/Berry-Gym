# Phase 31 – Untertrainiert-Coverage-Hard-Fail + Quellen-Konsistenz

**Status:** ✅ Abgeschlossen (30.05.2026) — 31.1 Hard-Fail (#502),
31.2 Diagnose (#501), 31.3 Description-Sanitizing (#642)
**Vorgänger:** Phase 30 (Adaptive Plan Generation – Übertraining-Cap, Untertrain-Quelle, Plateau-/Push-Pull-Hints)
**Branch-Schema:** `feature/phase-31-X-kurzbeschreibung` pro Sub-Phase

> **Korrektur-Phase.** Anlass: konkrete Plan-Generierung vom 21.05.2026
> 03:36 (3er-Split Push/Pull/Legs, Sonnet 4.6) gegen den Trainings-Report
> vom 19.05.2026. Phase 30 wirkt – die Übertraining-Caps greifen sauber,
> der Plateau-Hint adressiert Bankdrücken über Frequenz/Tempo-Variation,
> der Push/Pull-Hint landet im Prompt-Block. **Aber:** die generierte
> Antwort produziert 4 von 4 Untertrainiert-Coverage-Warnungen, davon
> 2 gegen Muskelgruppen, die laut Report **nicht** untertrainiert sind
> – und der Plan wird trotz Verletzung als „verwendbar" gespeichert.

> **Konzept-Bezug:** Phase 30 hat die Eingabeseite (Hints im Prompt) und
> die Übertrainings-Seite der Validierung (`success=False` bei
> Cap-Verletzung, P1-Review-Fix in 30.1) sauber gemacht. Phase 31 zieht
> die Untertrainings-Seite symmetrisch nach und klärt eine Diskrepanz
> zwischen Report-Anzeige und Generator-Untertrainiert-Liste, die nach
> 30.2 nicht erwartet war.

---

## 1. Problemanalyse

### 1.1 Konkreter Befund (21.05.2026)

Plan generiert von Phase-30.4-Stand-Generator (User 2 / Leratos), gegen
den Trainings-Report vom 19.05.2026 (30-Tage-Fenster).

**Wichtig — Generator-Konfiguration weicht vom Default ab:**

- **Trainingshistorie-Fenster: 60 Tage** (Default sonst 30 Tage)
- **Sätze pro Trainingstag: 22** (vom User von 18 hochgesetzt, um pro
  Übung mehr Platz zu haben)

Die Window-Verschiebung ist konzeptuell relevant: der Stats-Report rechnet
auf 30 Tagen, der Generator hat im Lauf vom 21.05. auf 60 Tagen gerechnet.
Die 22 Sätze/Tag sind für die Coverage-Allocation relevant: bei 3 Tagen
× 22 = 66 Sätzen/Woche sollten 4 Pflicht-Schwachstellen × 6 Sätze
(= 24 Sätze) trivial unterzubringen sein.

**Generator-Warnungen beim Speichern:**

```
⚠️ Untertrainiert-Volumen zu niedrig: SCHULTER_VORN hat nur 4 Sätze (Ziel: mind. 6)
⚠️ Untertrainiert-Volumen zu niedrig: SCHULTER_SEIT hat nur 4 Sätze (Ziel: mind. 6)
⚠️ Untertrainiert-Volumen zu niedrig: BEINE_HAM hat nur 4 Sätze (Ziel: mind. 6)
⚠️ Untertrainiert-Volumen zu niedrig: BAUCH hat nur 4 Sätze (Ziel: mind. 6)
→ Der Plan ist trotzdem verwendbar.
```

Vergleich der beiden „untertrainiert"-Listen:

| Muskelgruppe | Stats-Report 19.05. (Volumen) | Stats-Report Status | Generator-Untertrainiert-Liste | Plan-Sätze | Lücke |
|---|---:|---|---|---:|---|
| **BEINE_HAM** | 9 (Soll 12–20) | Untertrainiert | ✓ enthalten | 4 | -2 vom Ziel 6 |
| **BAUCH** | 9 (Soll 12–20) | Untertrainiert | ✓ enthalten | 4 | -2 vom Ziel 6 |
| **HUEFTBEUGER** | 9 (Soll 12–20) | Untertrainiert | **✗ fehlt** | 0 | nicht adressiert |
| **SCHULTER_VORN** | 12 (Soll 12–20) | **Optimal** | ✗ unerwartet enthalten | 4 | -2, aber Block nicht nötig |
| **SCHULTER_SEIT** | 12 (Soll 12–20) | **Optimal** | ✗ unerwartet enthalten | 4 | -2, aber Block nicht nötig |

Zwei Befunde überlagern sich:

- **HUEFTBEUGER bleibt im Plan komplett unadressiert** (0 Sätze).
  Genau das „Hüftbeuger-Loch" aus Phase 30 Section 1.1 – Phase 30.2
  hätte das adressieren sollen, hat es aber nicht.
- **SCHULTER_VORN/_SEIT landen im Pflicht-Block, obwohl Report
  „Optimal" sagt** – das LLM dehnt den Plan unnötig in eine Richtung,
  die der Report nicht braucht.

### 1.2 Wirkungsbewertung Phase 30 (was funktioniert)

Zur Einordnung: die meisten Bausteine von Phase 30 wirken im selben Plan
sehr sauber – Phase 31 räumt nur die Restlücken auf, sie ersetzt
nichts.

| Sub-Phase | Erwartetes Verhalten | Plan vom 21.05. | Bewertung |
|---|---|---|---|
| 30.1 Cap | Brust 28 → wenig im Plan | 8 Sätze | ✅✅ (-71 %) |
| 30.1 Cap | Lat 21 → wenig im Plan | 8 Sätze | ✅ (-62 %) |
| 30.1 Cap | Quad 21 → wenig im Plan | 8 Sätze | ✅ (-62 %) |
| 30.3 Plateau | Bankdrücken-PR-Pause → Variation statt Volumen-Push | Plan: „Bankdrücken (Langhantel) wird in Frequenz/Tempo variiert statt im Volumen gesteigert" + Langhantel→Kurzhantel-Substitution | ✅✅ |
| 30.4 Push/Pull | Ratio 1.33:1 → Pull-Volumen erhöhen | Pull-Tag: 16 Sätze vs. Push 8+4+4+6=22 → Pull bewusst hoch | ✅ (Ratio noch ~1.4, aber Richtung stimmt) |

### 1.3 Drei strukturelle Lücken (Wurzelursachen)

**Lücke L1 – Asymmetrie 30.1 ↔ 30.2:**

- **Cap-Verletzung** (30.1, hardened durch P1-Review) → `success=False`,
  Plan wird **nicht gespeichert**.
- **Coverage-Verletzung** (Untertrainiert-Floor) → nur Warning, Plan
  wird **trotzdem gespeichert** („ist trotzdem verwendbar").

Das ist nicht konsistent: Übertraining-Schutz greift hart, Untertrain-
Adressierung wird vom User ignoriert werden, weil die UX das „ist
verwendbar" als „passt schon" liest. Genau in den User-Daten, wo der
Plan **nichts** für Hüftbeuger tut, sagt die App „passt schon".

Allokations-Anmerkung zur 22-Sätze-Konfig: bei 3 Tagen × 22 Sätzen
= 66 Sätzen/Woche sind 4 × 6-Sätze-Pflicht-Blöcke (24 Sätze) gut
unterzubringen – das LLM hat aber stur 4er-Lots gewählt und damit
genau das Floor-Minimum verfehlt. Das ist eher ein Prompt-Allokations-
Problem als ein Volumen-Knappheits-Problem, deutet aber darauf hin,
dass die Pflicht-Block-Sprache im Prompt nicht stark genug ist.

**Lücke L2 – Quellen-Diskrepanz Stats-Report ↔ Generator-Untertrainiert-Liste:**

Phase 30.2 hat den Stats-Collector als Single Source of Truth
eingeführt. Im aktuellen Plan-Lauf produziert er aber eine Liste, die
**nicht** zum Stats-Report passt. Drei Hypothesen, die separat
diagnostiziert werden müssen:

- **Hypothese H2c (Window-Schwellen-Mismatch) — Lead-Hypothese nach Konfig-Info:**
  Generator lief auf 60-Tage-Fenster, Stats-Report auf 30-Tage-Fenster.
  Wenn der Stats-Collector mit `days=60` aufgerufen wird, die
  Volumen-Schwellen aus `periodization.get_volumen_schwellenwerte()`
  aber für **30 Tage** kalibriert sind (12–20 Sätze/30 T), passiert
  Folgendes:
  - SCHULTER_VORN: 19.05.-Stand = 12 Sätze/30 T (Optimum-Min). Über
    60 Tage rechnet der Stats-Collector ≈ 20–24 Sätze, hält ihn weiter
    für „untertrainiert", wenn die Schwellen NICHT skaliert werden,
    sondern die 60-T-Summe gegen das 30-T-Min verglichen wird (umgekehrt
    – wenn die Summe richtig skaliert wird, wären 60-T-Ist > 60-T-Soll-Min
    und der Status wäre „optimal"). **Genau eine dieser zwei
    Skalierungs-Richtungen ist falsch — 31.2 muss klären, welche.**
  - HUEFTBEUGER: über 60 Tage könnte das Volumen unter die „nicht
    trainiert"-Schwelle fallen (siehe H2b) statt „untertrainiert" – dann
    wird er aus der Filter-Logik herausgefiltert.
  Die 30↔60-Tage-Window-Verschiebung ist konkret und im Code prüfbar,
  damit ist H2c die wahrscheinlichste Ursache.
- **Hypothese H2a (Fallback griff):** Stats-Collector schlug fehl, der
  Generator fiel auf `analysis_data["weaknesses"]` zurück (data_analyzer-
  Heuristik: eff_reps < 0.6 × Ø). 12 Sätze SCHULTER_VORN bei avg ≈ 16
  → von der Heuristik als „untertrainiert" geflaggt, vom Stats-Collector
  bei Schwelle 12 als „optimal". Das ist das Fallback-Verhalten aus
  dem 30.2 P1-Review – funktional korrekt als Fallback, aber wenn es
  griff, sollten wir das wissen.
- **Hypothese H2b (HUEFTBEUGER fällt aus der Filter-Logik):** Stats-
  Collector emittiert HUEFTBEUGER vielleicht als „nicht trainiert"
  (statt „untertrainiert"), wenn unter einer separaten Schwelle. Im
  Filter werden dann nur `Untertrainiert`-Status berücksichtigt – siehe
  Phase 30.3 Review-Fix für die analoge Bug-Klasse bei Plateau-Status-
  Keys. Kann auch sekundär zu H2c auftreten (60-T-Skalierung lässt
  Hüftbeuger unter eine andere Schwelle rutschen).

Bis L2 geklärt ist, bringt jedes Härten von L1 nur den falschen
Untertrainiert-Set in den Hard-Fail.

**Lücke L3 – Plan-Beschreibung widerspricht Plan-Inhalt:**

Im Plan-Beschreibungs-Feld steht wörtlich:

> „Alle Pflicht-Schwachstellen (vordere Schulter, seitliche Schulter,
> Hamstrings, Core) sind mit ≥6 Arbeitssätzen abgedeckt."

Tatsächlich: alle vier bei genau 4 Sätzen. Das LLM hat im freien
Description-Text eine Aussage produziert, die sein eigener strukturierter
Output widerlegt. Möglicherweise hat es Wiederholungen (6–12) mit Sätzen
(4) verwechselt, oder die Beschreibung wurde vor einem internen Trim
verfasst. **Für den User ist das schädlicher als die Warning**, weil die
Description das ist, was er liest, bevor er sich den Plan anschaut.

---

## 2. Architektur-Skizze

```
PlanGenerator
  ├─ _compute_undertrained_targets()  (Phase 30.2)
  │    └─ Stats-Collector  --(Erfolg)--> targets
  │    └─ Stats-Collector  --(Fehler)--> None (Sentinel, P1-Review)
  │                                          └─ caller: Fallback auf analysis_data["weaknesses"]
  │
  │    NEU 31.2:  Quellen-Log    → "undertrained_source=stats_collector|fallback_analysis_data"
  │    NEU 31.2:  Coverage-Set vs. Stats-Report-Set Diff → Telemetry-Log
  │
  ├─ generate(save_to_db=True)
  │    ├─ ... LLM-Generierung ...
  │    ├─ _validate_overtraining_cap()    --(Verletzung)--> success=False  (30.1 Hard-Fail)
  │    └─ _validate_weakness_coverage()
  │         └─ HEUTE: warnings.append() + Plan trotzdem speichern
  │         └─ NEU 31.1: HARD-FAIL bei verbleibender Lücke nach Auto-Fix
  │
  └─ Plan-Description-Sanitizing                                ← NEU 31.3
       └─ LLM-Aussagen über Sätze-Coverage entfernen oder gegen
         tatsächliches Sätze-Volumen verifizieren
```

Das ist eine kleine Phase – kein neuer Daten-Container, keine neuen
Helper. Die ersten zwei Sub-Phasen sind Verschärfungen existierender
Pfade, die dritte ist eine Description-Filterung.

---

## 3. Sub-Phasen

### 3.1 Sub-Phase 31.1 – Untertrainiert-Coverage als Hard-Fail

**Status:** 📋 Konzept · **Aufwand:** S · **Reihenfolge:** nach 31.2

#### Problem

`_validate_weakness_coverage` schreibt nach unzureichender Coverage
eine Warning, gibt aber `success=True` zurück und der Plan wird
gespeichert. Asymmetrisch zu 30.1 (Cap → `success=False`).

#### Lösungsansatz

1. Auto-Fix-Pass bleibt unverändert (29.3-Logik): wenn der Fix die
   Coverage-Lücke schließen kann, läuft alles wie gehabt.
2. Wenn nach Auto-Fix **mindestens eine** Pflicht-Muskelgruppe noch
   unter `MIN_SETS_PER_WEAKNESS` (= 6) liegt → `success=False` mit
   sprechender Error-Message analog zur Cap-Verletzung:
   ```
   ❌ Plan deckt eine oder mehrere Pflicht-Schwachstellen nicht ab
   - Hamstrings (Ist 4 Sätze, Soll-Min 6)
   - Bauch (Ist 4 Sätze, Soll-Min 6)
   Plan wird NICHT gespeichert – bitte erneut versuchen.
   ```
3. Tests parallel zu 30.1: ein Test, der mit nicht-erfüllbarem
   Undertrained-Set ein `success=False` erzwingt.

#### Akzeptanzkriterien

- Der 21.05.-Befund (User 2 / Leratos) generiert einen Plan, der ENTWEDER
  die 4 Schwachstellen erfüllt ODER `success=False` liefert. Niemals
  „verwendbar mit Warnung".
- Symmetrie mit 30.1: gleiches Verhalten beim Cap- und beim Coverage-
  Schutz.
- Tests + Live-Verifikation.

#### Reihenfolge-Hinweis

31.1 wird erst nach 31.2 gemerged: ohne 31.2 würde die Hard-Fail-Logik
unter der Hypothese H2a (Fallback griff) auch falsche Listen erzwingen
– und der User bekäme eine Hard-Fail-Schleife auf nicht-existente
Schwachstellen (SCHULTER_VORN/_SEIT laut Plan untertrainiert, laut
Report nicht).

**Update nach 31.2-Diagnose (21.05.2026):** Die Hypothese H2a/H2b
wurden empirisch widerlegt – die Generator-Liste vom 21.05. ist mit
dem heute generierten PDF-Report **deckungsgleich**. Der vermutete
Risikofall „Hard-Fail erzwingt falsche Liste" tritt nicht ein. 31.1
kann ohne Konzept-Anpassung gestartet werden.

### 3.2 Sub-Phase 31.2 – Quellen-Diagnose Stats-Collector ↔ Generator

**Status:** ✅ Abgeschlossen (21.05.2026) als reine Diagnose-Sub-Phase
ohne Code-Fix. Aufwand war S statt M (nur Logging + Live-Lauf), Befund
siehe Journal-Eintrag „31.2 – Diagnose Untertrainiert-Quelle".

#### Problem

Generator-Untertrainiert-Liste passt nicht zum Stats-Report:

- HUEFTBEUGER fehlt (Stats sagt untertrainiert, Generator nicht)
- SCHULTER_VORN/_SEIT zusätzlich (Stats sagt optimal, Generator
  untertrainiert)

Aus drei plausiblen Hypothesen (H2a/H2b/H2c) ohne Logging nicht
unterscheidbar.

#### Lösungsansatz

**Schritt 1: Logging-Patch (temporär, wie in 29.1).**

In `_compute_undertrained_targets`:

```python
print(f"[31.2] history_days={self.history_days}")  # erwartet 60 im 21.05.-Lauf
print(f"[31.2] stats_collector_result: {len(stats_result)} muskelgruppen, "
      f"untertrainiert={[mg for mg, s in stats_result.items() if s.status == 'untertrainiert']}, "
      f"nicht_trainiert={[mg for mg, s in stats_result.items() if s.status == 'nicht_trainiert']}")
print(f"[31.2] schwellen_used (Stichprobe SCHULTER_VORN, HUEFTBEUGER, BEINE_HAM):")
# Schwellen aus periodization.get_volumen_schwellenwerte für genau diese MG ausgeben,
# zusammen mit den 60-Tage-Ist-Werten – um zu sehen, ob Schwellen skaliert wurden
```

und im Aufrufer:

```python
print(f"[31.2] undertrained_source: "
      f"{'stats_collector' if undertrained_targets is not None else 'fallback_analysis_data'}")
print(f"[31.2] final_undertrained_set: {undertrained_targets or analysis_data['weaknesses']}")
```

**Schritt 2: Live-Lauf gegen User 2** im git-worktree (Pattern aus 30.4),
mit **gleicher Konfiguration** wie der ursprüngliche Befund:
`history_days=60`, `sets_per_session=22`.

```
ssh <user>@<prod-host> (worktree mit Phase-31.2-Logging) → verify312.py
```

Aus dem Output ableiten:

- Wird der Stats-Collector mit days=60 aufgerufen? Werden die
  Schwellen entsprechend skaliert oder bleiben sie auf 30-T-Basis?
  (Klärung H2c – Lead-Hypothese)
- Wurde der Fallback aktiviert? (Klärung H2a)
- Wenn Stats-Collector lief: welche Status-Strings emittiert er für
  HUEFTBEUGER? (Klärung H2b)

**Schritt 3: Fix je nach Diagnose.**

- H2c (Lead): **Festgelegter Fix:** Klassifikations-Pfad wird vom
  History-Window entkoppelt. Der Stats-Collector unterscheidet
  künftig zwei Konzepte:
  - **History-Window** (User-Auswahl in UI, 30/60/90 T): bestimmt,
    welche Trainings-Sätze in die Anzeige fließen (Tonnage, eff. Wdh,
    Übungsverläufe).
  - **Klassifikations-Window** (immer 30 T): bestimmt den
    Status-Vergleich gegen die Volumen-Schwellen aus
    `periodization.get_volumen_schwellenwerte()`. Status (Optimal /
    Untertrainiert / Übertraining / Nicht trainiert) wird ausschließlich
    auf den letzten 30 Tagen berechnet, unabhängig davon, wieviel
    Historie das UI gerade anzeigt.

  Begründung: Die Schwellen sind kalibriert für ein 30-T-Fenster (12–20
  Sätze/Monat als Standard-Range). Lineare Skalierung auf 60/90 T ist
  nur annähernd richtig, weil Trainings-Frequenz reinspielt – und sie
  würde die Single Source of Truth zwischen PDF-Report (immer 30 T) und
  Generator brechen. Klare Trennung „Daten-Fenster" vs.
  „Klassifikations-Fenster" bewahrt die SSoT und kostet im Code ≈ 5
  Zeilen (Stats-Collector ignoriert für die Status-Logik den `days`-
  Parameter und rechnet intern immer 30 T).

  Falls 31.2-Logging zeigt, dass H2c nicht zutrifft, fällt dieser
  Schritt weg – das Konzept-Risiko ist asymmetrisch (nichts kaputt,
  wenn die Hypothese widerlegt wird).

- H2a: Stats-Collector-Crash-Ursache fixen (vermutlich Edge-Case), so
  dass der Fallback nicht (mehr) griff.
- H2b: Filter-Logik in `_compute_undertrained_targets` /
  `_build_weakness_block` erweitern – `Untertrainiert` UND `Nicht
  trainiert` als „Pflicht"-Klassen (siehe Punkt-4-Recherche oben in
  §1.3 L2). Das ist nach Code-Befund **mit hoher Wahrscheinlichkeit
  ebenfalls notwendig** unabhängig von H2c – siehe F-31-2 unten.

**Schritt 4: Logging wieder entfernen** (wie nach Phase 29.1).

#### Akzeptanzkriterien

- Hypothesen H2a/H2b/H2c sind im Journal mit konkretem Live-Output
  diagnostiziert. EINE davon ist der Befund.
- Der 21.05.-Befund (User 2 / Leratos) liefert eine
  Untertrainiert-Liste, die mit dem Stats-Report-Set deckungsgleich
  ist (BEINE_HAM, HUEFTBEUGER, BAUCH).
- Regressions-Test: gegebener Stats-Collector-Output ⇒ erwartete
  Untertrainiert-Liste.

### 3.3 Sub-Phase 31.3 – Plan-Description vs. Plan-Inhalt

**Status:** 📋 Konzept · **Aufwand:** M

#### Problem

LLM produziert im `plan_description`-Feld inhaltliche Behauptungen
(„Alle Pflicht-Schwachstellen … ≥6 Arbeitssätzen"), die durch den
strukturierten Plan widerlegt werden. User sieht die Description vor
dem Plan und vertraut ihr.

#### Lösungsansatz (A + B kombiniert von Anfang an)

Der 21.05.-Befund hat gezeigt, dass das LLM **schon bei der
strukturierten Plan-Allokation** anweisungstreu war (4 statt 6 Sätze
pro Pflicht-MG, trotz expliziter `≥6 Sätze`-Vorgabe im Pflicht-Block).
Anzunehmen, dass es bei einer Description-Anweisung anders reagiert,
hat keine evidenzielle Grundlage – das wäre der gleiche Fehler in
einem weicheren Kontext. Deshalb beide Schichten von Anfang an:

**Schicht A (Anweisung im Prompt, ≈ 0 Aufwand):** Im PromptBuilder
explizit anweisen, dass die `plan_description` **keine quantitativen
Behauptungen über Schwachstellen-Coverage** enthalten soll, sondern nur
das Plan-Konzept beschreibt (Split-Typ, Periodisierung, Fokus-Themen).
Das ist die billige erste Verteidigungslinie; wenn das LLM ihr folgt,
spart Schicht B Arbeit. Wenn nicht, fängt Schicht B auf.

**Schicht B (Regex-Filter als Sicherheitsnetz):** Nach Auto-Fix einen
Description-Konsistenz-Pass:

- Regex-Suche nach Mustern wie `≥\s*\d+\s*(Sätze|Arbeitssätze|Sets)`
  in der Description.
- Pro Match: prüfen, ob die tatsächlichen Sätze im Plan zur Behauptung
  passen.
- Bei Diskrepanz: Description-Match streichen oder durch generischen
  Satz ersetzen („Plan-Schwerpunkte: siehe Tagesübersicht").

#### Akzeptanzkriterien

- 21.05.-Befund: Description enthält keine quantitative Behauptung
  über Untertrainiert-Coverage, die nicht zum strukturierten Output
  passt. Schicht B fängt alle Description-Aussagen ab, die Schicht A
  nicht verhindert hat.
- Tests für Regex-Filter (Schicht B): mindestens ein Test pro Muster
  („≥ N Arbeitssätze", „mit N Sätzen abgedeckt", „mind. N Sätze").
- Falls Schicht A ausreichend wirkt: Schicht B bleibt installiert,
  Code-Pfad nur ungenutzt. Keine A/B-Entscheidung im Implementierungs-
  schritt – beide bleiben.

#### Hinweis zum Aufwand

Die Regex-Schicht ist ≈ 30–50 LOC + 4–6 Tests. Damit ist 31.3 nicht
mehr „klein A vs. groß B", sondern eine zusammenhängende kleine
Implementierung. Wenn der Regex-Filter sich in der Praxis als zu eng
oder zu breit zeigt, wird er nachjustiert – das ist normaler
Wartungsaufwand, kein Konzept-Bruch.

---

## 4. Reihenfolge & Begründung

```
31.2 (Quellen-Diagnose)        ← zuerst, weil 31.1 ohne 31.2 falsche Listen erzwingt
  → 31.1 (Hard-Fail-Switch)
  → 31.3 (Description-Sanitizing)
```

- **31.2 zuerst:** ohne diesen Schritt riskiert 31.1, das gesamte
  Schwächen-Enforcement auf eine inkonsistente Liste zu zementieren.
- **31.1 als nächstes:** trivialer Switch im Validator, hoher
  UX-Wert (kein „verwendbar trotz Lücke" mehr).
- **31.3 zuletzt:** kosmetisch im Vergleich zu 31.1, aber adressiert
  das größte User-Vertrauens-Problem (gelogene Beschreibung).

---

## 5. Offene Fragen

- **F-31-1:** Soll der Hard-Fail aus 31.1 auch greifen, wenn nur
  EINE der Schwachstellen unter Soll-Min fällt, oder gibt es eine
  Toleranz (z. B. 1 von 3 verfehlbar)? Pragmatik vs. Strenge. Vorschlag
  Default: jede einzelne MG muss erreicht werden, analog zur
  Cap-Strenge.
- **F-31-2 (durch 31.2-Diagnose obsolet, 21.05.2026):** Die ursprüngliche
  Sorge war, dass HUEFTBEUGER aus der Filter-Logik fällt (H2b). Der
  Live-Lauf hat gezeigt, dass HUEFTBEUGER **mit Status `optimal`**
  klassifiziert wird (9 Sätze ≥ Schwelle 6 aus periodization.py /
  haltung-Klasse), nicht als `nicht_trainiert`. Die Filter-Erweiterung
  auf `Untertrainiert` + `Nicht trainiert` ist im aktuellen Datenstand
  **nicht nötig**.

  Notiz für später: Wenn ein User eine MG **nie** trainiert (z. B. ein
  Anfänger, der noch keinen Hüftbeuger-Tag hatte), liefert der Stats-
  Collector `status="nicht_trainiert"` und der aktuelle Filter
  (`if status != "untertrainiert": continue`) verwirft ihn. Das ist
  weiterhin ein konzeptioneller Edge-Case, aber bei User 2 ist er
  konkret nicht relevant. Wenn er später akut wird, ist die
  Implementierung trivial:

  ```python
  if mg.get("status") not in ("untertrainiert", "nicht_trainiert"):
      continue
  ```

  und der Pflicht-Block-Text muss zwischen „aufstocken" und „neu
  einführen" formulierungs-mäßig differenzieren. Phase-32-Notiz
  N-32-3 (siehe §5.1).
- **F-31-4:** Wenn 31.1 den Hard-Fail einführt – wie verhält sich das
  zum 30.1-Hard-Fail bei einem **Konflikt-Plan**, der gleichzeitig
  Cap-Verletzung UND Coverage-Lücke hat? Welche Error-Message gewinnt,
  oder beide? Vorschlag: beide gleichzeitig zeigen.
- **F-31-6 (Unerfüllbarkeit der User-Konfig):** Mit symmetrischen Hard-
  Fails (30.1 Cap + 31.1 Coverage) entsteht eine Klasse von User-
  Konfigurationen, die mathematisch nicht lösbar sind: z. B. 3 Tage ×
  18 Sätze = 54 Sätze/Woche, davon ≤ 16 Sätze in Caps eingesperrt
  (4 Compound-MGen × 4 Sätze max), ≥ 24 Sätze für 4 Pflicht-Floors,
  plus die optimalen MGen, die nicht ignoriert werden dürfen. „Plan
  wird nicht gespeichert – bitte erneut versuchen" führt dann in eine
  UX-Endlosschleife. Drei Lösungs-Pfade:
  - (1) **Pre-Generation-Check** (UX-freundlichste Variante): vor LLM-
    Aufruf prüfen, ob `sets_per_session × tage_pro_woche ≥ Σ Caps +
    Σ Floors + Mindest-Volumen-Optimal-MGen`. Wenn nicht: sofortige
    User-Meldung „Mit der Konfig X können Pflicht-Schwachstellen Y/Z
    nicht erfüllt werden – erhöhe `sets_per_session` auf ≥ N oder
    ergänze einen Trainingstag". Kein LLM-Aufruf, kein Token-Verbrauch.
  - (2) **Retry-Eskalation:** Nach N erfolglosen Versuchen die
    Hard-Fail-Bedingungen relaxieren („1 von M MG darf fehlen, mit
    expliziter Plan-Notiz") – führt aber die Asymmetrie wieder ein,
    die 31.1 gerade beseitigt.
  - (3) **Konfig-Vorschlag** statt Generierung: Liefere als „Plan"-
    Antwort einen Konfigurations-Vorschlag („Empfohlen: 22 Sätze/Tag
    bei 3 Tagen oder 18 Sätze/Tag bei 4 Tagen").

  Vorschlag-Default: (1) als kleine Sub-Phase 31.4 oder als Phase-32-
  Item. Aufwand klein (Mathe, kein LLM), UX-Impact groß. Wird vor
  31.1-Live-Schaltung umgesetzt, sonst riskiert man User-Frustration
  durch unerfüllbare Konfigs.

*(F-31-3, F-31-5 entfernt – F-31-3 obsolet durch §3.3-Festlegung
auf A+B-kombiniert, F-31-5 obsolet durch §3.2-Festschreibung auf
30-T-Klassifikations-Fenster.)*

### 5.1 Erkannt, aber nicht in 31er Scope (Phase-32-Notizen)

Beim Review des Phase-31-Konzepts haben sich zwei Themen herausgestellt,
die echte Probleme adressieren, aber außerhalb der Phase-31-Wirkungs-
fläche liegen. Hier dokumentiert, damit sie nicht verloren gehen:

- **N-32-1 — Volumen-Sprung-Sichtbarkeit:** Im 21.05.-Befund hat der
  User `sets_per_session` von 18 auf 22 gesetzt. Bei 3 Tagen sind das
  **66 Sätze/Woche** – gegenüber dem Report-Ist von ≈ 40–44 Sätzen/Woche
  ein **Sprung um +50 bis +65 %**, exakt in einer Phase, die der
  Stats-Report selbst als „Stabile Phase / Konsolidierung KW19→KW20"
  einordnet. Phase 31 lässt das durch ohne Hinweis. Eine Phase-32-Sub-
  Phase könnte einen Volumen-Sprung-Hint produzieren (`sets_per_session
  × tage_pro_woche` vs. Ist-Wochenvolumen vergleichen, Schwellen-
  Warnung ab z. B. +30 %), analog zum 30.4-Frequency-Hint.

- **N-32-2 — Plan-Description als Generator-Input statt -Output:** Die
  Plan-Description ist heute ein LLM-Output, der vom Generator
  abschließend sanitiert wird (31.3). Saubere Architektur: Generator
  baut die Description aus dem strukturierten Plan zusammen (Split-Typ,
  Periodisierung, abgedeckte Pflicht-MGen, Cap-Berücksichtigung) und
  übergibt sie nur als Render-Vorlage. Spart 31.3 mittelfristig komplett.
  Größerer Architektur-Schritt, gehört nicht in 31er Scope.

- **N-32-3 — Pflicht-Block für `nicht_trainiert`-MGen:** Im aktuellen
  Filter `if status != "untertrainiert": continue` werden Muskelgruppen
  mit `status="nicht_trainiert"` (anzahl == 0 im 30-T-Window) verworfen.
  Bei User 2 ist das aktuell kein Problem, weil alle relevanten MGen
  mindestens leicht trainiert werden. Bei einem Anfänger, der HÜFTBEUGER
  / WADEN / ADDUKTOREN nie angefasst hat, fallen diese aber durch den
  Pflicht-Block. Fix-Skizze siehe F-31-2 unten – Code-Diff ≈ 2 Zeilen
  plus Differenzierung der Pflicht-Block-Texte zwischen „aufstocken" und
  „neu einführen". In 31er Scope aus zwei Gründen nicht akut: (a) der
  konkrete 21.05.-Befund braucht es nicht, (b) der Test-Aufwand ist
  größer als der Diff, weil es ein eigener Datenstand-Setup-Pfad ist.

---

## 6. Akzeptanzkriterien (Phase-Gesamt)

- **Konsistenz:** Generator-Untertrainiert-Liste und Stats-Report-
  Untertrainiert-Liste sind im 21.05.-Befund (User 2) deckungsgleich.
- **Symmetrie:** Coverage-Verletzung hat dasselbe Schutzverhalten wie
  Cap-Verletzung (`success=False`).
- **Vertrauen:** Plan-Description macht keine inhaltlich falschen
  Behauptungen über das, was im strukturierten Plan steht.
- **Regression:** Tests + Live-Verifikation gegen User 2.
- **Telemetrie-Sauberkeit:** Keine zurückgelassenen Print-Statements
  nach 31.2 (wie nach 29.1).

---

## 7. Status-Updates pro Sub-Phase

*(Wird beim Start und Abschluss jeder Sub-Phase ergänzt.)*
