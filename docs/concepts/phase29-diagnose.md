# Phase 29.1 – Diagnose-Bericht: Plan-Generator-Konsistenz

**Status:** ✅ Diagnose abgeschlossen (19.05.2026)
**Branch:** `feature/phase-29-1-generator-diagnose`
**Bezug:** `docs/concepts/phase29_concept.md` (Findings F1/F2/F3, Section 1.2)

> **Scope:** 29.1 ist reine Diagnose. Kein Fix in dieser Sub-Phase. Pro Finding
> ist unten eine identifizierte Ursache und eine Fix-Strategie für 29.2/29.3
> dokumentiert.

---

## 1. Methode & Reproduktions-Setup

- **Code-Sichtung** der gesamten Generator-Pipeline (siehe Section 2).
- **git blame / git log** für Phase-Zuordnung der Validator-Regeln und der
  betroffenen Code-Stellen.
- **Live-Reproduktion** auf dem Produktions-Server (`last-strawberry.com`,
  `~/gym.last-strawberry.com`):
  - Modell bestätigt: `.env` → `OPENROUTER_MODEL=anthropic/claude-sonnet-4.6`,
    `DEBUG=false` → Server nutzt immer OpenRouter (kein Ollama).
  - Eigenständiges Diagnose-Script (kein Produktions-Code geändert),
    `preview`-Modus (`save_to_db=False`), Script nach Lauf gelöscht.
  - Parameter: User 2 (Leratos, 13 Sessions/30 Tage), `sets_per_session=22`,
    `plan_type=3er-split`, `temperature=0.3` (Web-Default).
  - Ein Sonnet-4.6-Call, Kosten ~0,93 Cent.

---

## 2. Datenfluss UI → Generator → Validator → Speicherung

```
UI (Stream/POST)
  └─ core/views/ai_recommendations.py
       _validate_plan_gen_params()        → plan_type, sets_per_session, …
       generate_plan_api / generate_plan_stream_api
  └─ PlanGenerator(__init__)              ai_coach/plan_generator.py
       generate() → _generate_with_existing_django()
         1. TrainingAnalyzer.analyze()    ai_coach/data_analyzer.py
              → analysis_data["weaknesses"]  (eigene <60%-Heuristik)
         2. PromptBuilder.get_available_exercises_for_user()
         3. PromptBuilder.build_messages() ai_coach/prompt_builder.py
              system_prompt + user_prompt (inkl. Weakness-Block, Satz-Budget)
         4. LLMClient.generate_training_plan()  ai_coach/llm_client.py
              _generate_with_openrouter(max_tokens=_get_max_tokens())
              _extract_json()  → json.loads, sonst json-repair
         5. Validierung:
              llm_client.validate_plan()        (Pflichtfelder/Übungen/Dup)
              → Smart-Retry _fix_invalid_exercises() bei halluzinierten Übungen
              plan_validator.validate_plan_structure()  (Phase 11/13/16)
              _validate_weakness_coverage() + _auto_fix_weakness()
         6. _save_plan_to_db()  (nur wenn save_to_db=True)
```

**Prompt-Template-Ort:** inline im Code, `ai_coach/prompt_builder.py`
(`_build_system_prompt()` + `build_user_prompt()`). Keine externe Datei.

---

## 3. Finding F1 – Volumen-Steuerung wirkt nicht

**Symptom:** UI-Eingabe „22 Sätze pro Tag“ → Output ~18. Reproduziert:
Tag 1 = 20 Sätze, Tag 2 = 18 Sätze (Tag 3 durch F2 verstümmelt).

### Hypothesen-Bewertung (Konzept F1 a–d)

| Hyp. | Bewertung | Begründung |
|------|-----------|------------|
| (a) Prompt-Variable nicht durchgereicht | ❌ falsch | `sets_per_session` wird sauber durchgereicht: View `int(data.get("sets_per_session", 18))` (`ai_recommendations.py:686`) → `PlanGenerator` → `build_user_prompt`. |
| (b) Validator-Hard-Cap | ❌ falsch | Kein Validator kappt das Tages-Gesamtvolumen. `_MAX_SETS_PER_MUSCLE_GROUP=7` gilt pro Muskelgruppe; der Auto-Fix verschiebt Sätze, reduziert sie nicht. `_MIN_SETS_PER_SESSION=14` ist eine Untergrenze. |
| (c) LLM ignoriert numerische Vorgabe | ✅ **zutreffend** | Aber nicht „im luftleeren Raum“ – der Prompt widerspricht sich selbst (siehe Ursache). |
| (d) Alte Default-Konfiguration überschreibt | ❌ falsch | Default `18` greift nur bei fehlendem Key; die View liefert den Wert immer. |

### Ursache (bestätigt)

Der Prompt enthält **zwei einander widersprechende Volumen-Signale**:

1. **Eine 4 Sätze breite Range** statt einer Zielzahl.
   `ai_coach/prompt_builder.py:396-397`:
   `min_sets = max(10, sets_per_session - 4)` → für 22: **`min_sets=18, max_sets=22`**.
   Prompt-Zeile (reproduziert): `SATZ-BUDGET: 18-22 Sätze pro Trainingstag`.
   Die untere Grenze (18) entspricht exakt dem Status-quo-Default.
2. **Drei hartcodierte Beispiel-Tage**, die alle ~18 Sätze summieren –
   unabhängig von `sets_per_session`.
   `ai_coach/prompt_builder.py:523-546` (reproduziert):
   `Beispiel Push-Tag (18 Sätze) … = 18 Sätze total`,
   `Beispiel Pull-Tag (18 Sätze) … = 18 Sätze total`,
   `Beispiel Legs-Tag (18 Sätze) … = 16-18 Sätze total`.
   git blame: `0771b0f` (2026-01-10) + `842c74a` (2026-02-17).

Das LLM ankert an den konkretesten Zahlen im Prompt – den voll
durchgerechneten Beispielen (18) – und die Range erlaubt 18 als gültiges
Ergebnis. „22“ degradiert deterministisch zu ~18-20.

### Fix-Strategie 29.2 (Aufwand S)

1. Beispiel-Blöcke dynamisch an `sets_per_session` skalieren **oder** ganz
   entfernen (sie bringen wenig, schaden aber konkret).
2. Statt Range eine **exakte Zielzahl** vorgeben: „Jeder Trainingstag: GENAU
   `{sets_per_session}` Arbeitssätze (Toleranz ±1).“ `min_sets` nicht mehr als
   `sets-4` definieren.
3. Optional als zweite Verteidigungslinie: Validator-Check auf
   Satz-Abweichung > Toleranz → Retry mit härterem Hint.

---

## 4. Finding F2 – Strukturbruch bei Sonnet (Tag-Anzahl)

**Symptom (18.05.):** Sonnet 4.6 erzeugt deterministisch nur 2 Tage
(Push/Pull), Legs fehlt. **Reproduziert (19.05.):** 3 Tage, aber der
Legs-Tag ist ein Stummel mit 1 Übung / 4 Sätzen.

### Hypothesen-Bewertung (Konzept F2 a–c)

| Hyp. | Bewertung | Begründung |
|------|-----------|------------|
| (a) Validator verwirft Tag 3 | ❌ falsch | Validator-Regel-Audit (Section 7): **keine** Regel entfernt eine Session. Reproduziert: der Stummel-Legs-Tag löst nur die Warnung „nur 4 Sätze … asymmetrisch“ aus – kein Drop. |
| (b) Token-Output-Limit erreicht | ✅ **zutreffend, primär** | Siehe Ursache + Token-Check (Section 6). |
| (c) Parser/Edge-Case-Bug | ⚠️ teil-zutreffend | `json-repair` rettet die abgeschnittene Antwort **still** zu einem Teil-Plan, statt laut zu scheitern – das maskiert die Truncation und macht aus dem Bug einen speicherbaren „Erfolg“. |

### Ursache (bestätigt)

`_get_max_tokens()` (`ai_coach/plan_generator.py:160-169`, git blame `f86b359`,
2026-02-16) liefert für `3er-split` **3000 Tokens**.

Reproduktions-Beweis (Sonnet 4.6, `3er-split`, 22 Sätze):

```
Max Tokens: 3000
OpenRouter Response: Tokens: 8983 (in: 5983, out: 3000)
```

→ **`completion_tokens` = 3000 = exakt `max_tokens`.** Die Antwort wurde
hart abgeschnitten. Raw-Response 7705 Zeichen, `{`=33 vs `}`=30 (Differenz 3 →
unvollständig). Die Antwort endet mitten in der 2. Übung des Legs-Tags:
`… "exercise_name": "Rumänisches` (abgebrochen).

`json.loads` scheitert (`Expecting ',' delimiter`), danach rettet
`json-repair` einen Teil-Plan: der Legs-Tag überlebt mit nur der einen
vollständig erzeugten Übung (Kniebeuge, 4 Sätze).

**Warum mal 2, mal 3 Tage:** Der Abschneide-Punkt schwankt minimal
(`temperature=0.3`, nahezu deterministisch). Liegt er nach Tag 2, verwirft
`json-repair` die unvollständige Tag-3-Struktur komplett → **2 Tage**. Liegt
er in Tag 3, bleibt ein Stummel-Tag übrig → **3 Tage, 4 Sätze**. Gleiche
Wurzel, unterschiedlicher Schaden.

**Warum Gemini funktioniert:** Gemini 2.5 Flash formuliert knapper; sein
Output passt in 3000 Tokens. Sonnet 4.6 schreibt ausführlichere `notes` und
generiert den vollständigen 12-Wochen-`macrocycle` (laut JSON-Schema **vor**
den `sessions`) – die Tokens sind erschöpft, bevor Tag 3 fertig ist.

### Fix-Strategie 29.2 (Aufwand S–M)

1. **`max_tokens` für `3er-split` deutlich erhöhen** (~6000–8000). Der
   reproduzierte Bedarf liegt nachweislich über 3000; mit Puffer für 3
   ausführliche Sonnet-Tage + Periodisierung realistisch ~5000–6000.
2. **Truncation-Detektor:** wenn `completion_tokens >= max_tokens` oder
   `{`-/`}`-Bilanz ≠ 0 → harter Fehler statt stiller `json-repair`-Rettung;
   gezielter Retry. Verhindert, dass je wieder ein Teil-Plan gespeichert wird.
3. **Optional, Token-sparend:** den `macrocycle` nicht vom LLM erzeugen
   lassen – `_ensure_periodization_metadata()` füllt ihn ohnehin
   deterministisch. Den `macrocycle`-Block aus dem Prompt-Schema streichen
   spart grob 500–800 Output-Tokens.

---

## 5. Finding F3 – Fokus-Hint & Untertrainiert-Liste wirken schwach

**Symptom:** Plan-Titel „Fokus Hamstrings & Bauch“ → Hamstrings im Output
nicht/kaum adressiert. Untertrainiert-Liste wirkt nicht systematisch.

### Wie der Fokus aktuell in den Prompt kommt

1. **Es gibt keinen separaten „Fokus-Hint“-Input.** Der Plan-Titel
   „Fokus …“ wird **nachträglich** aus `analysis_data["weaknesses"]` erzeugt
   (`prompt_builder.py:418-438`, `plan_generator.py:422-431`). Der Titel ist
   rein kosmetisch und hat **null Volumen-Wirkung**.
2. Die Untertrainiert-Liste stammt aus `data_analyzer._identify_weaknesses()`
   – einer **eigenen Heuristik** (Muskelgruppe < 60 % des Durchschnitts der
   effektiven Wiederholungen). Das ist **nicht** die volumen-schwellenwert-
   basierte „Untertrainiert“-Klassifikation des Trainings-Reports. Generator
   und Report nutzen also unterschiedliche Definitionen (29.3-Scope).
3. Die Liste soll über `_build_weakness_block()` als „PFLICHT-ANFORDERUNG #0“
   in den Prompt gelangen.

### Ursache (bestätigt) – Label-Format-Mismatch

`data_analyzer` emittiert Schwachstellen mit **DB-Konstanten als Label**
(`Uebung.muskelgruppe` ist eine DB-Konstante, `core/models/constants.py`).
Reproduziert:

```
data_analyzer.weaknesses (RAW):
  'BEINE_HAM: Untertrainiert (nur 82 eff. Wdh vs. Ø 176)'
  'BAUCH: Untertrainiert (nur 104 eff. Wdh vs. Ø 176)'
```

`prompt_builder.WEAKNESS_LABEL_TO_KEYS` (git blame `cdca369`, 2026-02-17)
enthält dagegen **nur menschenlesbare Keys** („hintere schulter“,
„oberschenkel hinten“ …). `_build_weakness_block()` macht
`WEAKNESS_LABEL_TO_KEYS.get(label.lower())` → für `"beine_ham"` → `None` →
`continue` → die Schwachstelle wird **still verworfen**.

Reproduzierter Mapping-Check:

```
VERWORFEN 'BEINE_HAM'  -> NICHT in WEAKNESS_LABEL_TO_KEYS
OK        'BAUCH'      -> ['BAUCH']
```

Der erzeugte Weakness-Block enthielt folglich **nur Bauch/Core – Hamstrings
erreichte den Prompt überhaupt nicht.**

**Divergenz-Ursprung:** Commit `932efbc` (2026-03-28, „LABEL_TO_KEYS erkennt
jetzt DB-Konstanten als Weakness-Labels“) erweiterte
`plan_generator._validate_weakness_coverage.LABEL_TO_KEYS` um
DB-Konstanten-Keys – ließ aber `prompt_builder.WEAKNESS_LABEL_TO_KEYS`
unangetastet. Seither divergieren die zwei Mapping-Dicts; der Kommentar
„Gleiche Quelle wie plan_generator…“ (`prompt_builder.py:8`) ist veraltet.

**Welche Labels überleben zufällig:** nur die, deren DB-Konstante
kleingeschrieben einem deutschen Wort entspricht (`brust`, `trizeps`,
`bizeps`, `bauch`, `waden`, `unterarme`, `adduktoren`, `abduktoren`). Alle
zusammengesetzten Konstanten (`SCHULTER_*`, `RUECKEN_*`, `BEINE_*`), `PO`
und `HUEFTBEUGER` fallen durch.

### Zweite Schwäche

Selbst für überlebende Schwachstellen fordert `_build_weakness_block()` nur
**„mind. 1 Übung“** – keine Volumen-Vorgabe. Bauch landet damit bei ~3-4
Sätzen, nicht „prominent“.

### Folge im reproduzierten Lauf

Da der Prompt-Weakness-Block versagte, mussten BEINE_HAM und BAUCH
**nachträglich** vom Post-Validierungs-Auto-Fix (`_validate_weakness_coverage`,
das DB-Konstanten kennt) eingesetzt werden. Beide landeten auf dem **Push-Tag**
– weil der Legs-Tag durch F2 zum 4-Satz-Stummel verstümmelt war. **F2
sabotiert F3.** (Bestätigt die Konzept-Reihenfolge: 29.2 vor 29.3.)

### Fix-Strategie 29.3 (Aufwand M)

1. **`WEAKNESS_LABEL_TO_KEYS` um DB-Konstanten-Keys ergänzen** – idealerweise
   eine **gemeinsame Mapping-Quelle** für `data_analyzer`, `prompt_builder`
   und `plan_generator` (Single Source of Truth). Klein, sofort wirksam.
2. `_build_weakness_block()` von „mind. 1 Übung“ auf eine **Volumen-Vorgabe**
   heben (z. B. „mind. N Sätze/Woche“, N=12 gem. Konzept 3.3).
3. Optional: die **Report-Untertrainiert-Liste** statt/zusätzlich zur
   data_analyzer-Heuristik einspeisen (eigentlicher 29.3-Kern).

---

## 6. Token-Limit-Check (Konzept-Frage F-29-5)

`_get_max_tokens()`-Map (`plan_generator.py:160-169`):

| plan_type | max_tokens | Reicht für 3 Tage Sonnet? |
|-----------|-----------:|---------------------------|
| ganzkörper | 2000 | – |
| 2er-split / upper-lower | 2200 | – |
| **3er-split** | **3000** | ❌ **Nein** – reproduziert: out=3000=cap, abgeschnitten |
| 4er-split | 3800 | fraglich (gleiches Risiko) |
| ppl / push-pull-legs | 4500 | fraglich bei 6 Sessions |

**Befund:** Für Sonnet 4.6 ist `3000` für einen `3er-split` **nicht
ausreichend**. Der Header-Kommentar kalkuliert „~700 Tokens pro Session“ –
Sonnet liegt darüber (ausführlichere `notes`, vollständiger 12-Wochen-
`macrocycle` vor den Sessions). Empfehlung: alle Werte in 29.2 für Sonnet
neu kalibrieren, nicht nur `3er-split`.

---

## 7. Validator-Regel-Audit (Konzept-Fragen F-29-2, F-29-6)

Alle programmatischen Post-Validierungen, mit Phase-Zuordnung (git blame):

| Regel | Phase | Commit / Datum | Aktion | Entfernt eine Session? |
|-------|-------|----------------|--------|------------------------|
| `validate_plan` – Pflichtfelder, Übungs-Existenz, Intra-Session-Duplikate | — (`llm_client.py`) | — | bei Fehler: Smart-Retry der Übungen; sonst ganzer Plan abgelehnt | **Nein** |
| 11.1 Cross-Session-Duplikate | 11 | `eceeb6b` 2026-03-26 | Warnung | **Nein** |
| 11.2 Verbotene Kombinationen | 11 | `eceeb6b` 2026-03-26 | Warnung | **Nein** |
| 11.3 Anatomische Pflichtgruppen | 11 | `eceeb6b` 2026-03-26 | Warnung | **Nein** |
| 11.4 Compound-vor-Isolation | 11 | `eceeb6b` 2026-03-26 | Auto-Fix (Reihenfolge innerhalb Session) | **Nein** |
| 11.5 Pausenzeiten-Plausibilität | 11 | `eceeb6b` 2026-03-26 | Auto-Fix (`rest_seconds`) | **Nein** |
| 13.1 Muskelgruppen-Überrepräsentation (>7/MG) | 13 | `b637f26` 2026-03-27 | Auto-Fix (Übung tauschen) | **Nein** |
| Mindest-Satz-Budget pro Session (`_MIN_SETS_PER_SESSION=14`) | — | `d7f4ab0` 2026-03-28 | Warnung | **Nein** |
| 16 Push/Pull-Ratio | 16 | `51e1690` 2026-04-02 | Warnung + Auto-Fix (Übung tauschen) | **Nein** |

**Ergebnis:** Keine einzige Validator-Regel entfernt einen Trainingstag.
Alle Regeln warnen oder tauschen/sortieren Übungen **innerhalb** einer
Session. F2-Hypothese (a) ist damit widerlegt.

---

## 8. Phase-23-Verdacht – widerlegt

Das Konzept (Section 5.2) verdächtigt Phase-23-Validator-Regeln. Befund:

- `feature/phase23-time-windowed-stats` betraf **ausschließlich Stats-Code**
  (RPE-Verteilung, Fatigue-Index, Plateau-Logik, PDF) – nicht den Generator.
- Der Plan-Generator wurde zuletzt in **Phase 20** angefasst (`29ec51e`,
  2026-04-02, „weakness tracker with dashboard feedback loop“), davor
  Phase 17/16/13/11.
- Alle Validator-Regeln stammen aus Phase **11/13/16** (Section 7). Es gibt
  **keine Phase-23-Validator-Regel.**
- Die User-Erinnerung „Generator zuletzt in Phase 23 angefasst“ ist ungenau –
  es war Phase 20. Der F3-relevante Defekt entstand in `932efbc`
  (2026-03-28, ein unvollständiger Fix), nicht in Phase 23.

---

## 9. Nebenbefund – `push_pull_balance` immer 0 (gleiche Bug-Klasse wie F3)

Reproduziert: `push_pull_balance: {'push_volume': 0, 'pull_volume': 0,
'ratio': 0, 'balanced': False}` – obwohl User 2 reichlich Push/Pull-Volumen
hat.

**Ursache:** `data_analyzer.PUSH_GROUPS` / `PULL_GROUPS` (`data_analyzer.py:46-55`)
verwenden menschenlesbare Labels (`"Brust"`, `"Rücken"`), `muscle_volume` ist
aber mit DB-Konstanten (`"BRUST"`, `"RUECKEN_LAT"`) gekeyt → die Summen
treffen nie zu → immer 0/„Unbalanced“. Der Prompt erhält dadurch
„Push: 0 | Pull: 0 – Unbalanced“ als wertlosen Input.

**Gleiche Wurzel wie F3** (DB-Konstante vs. menschenlesbares Label). In 29.3
mit der Single-Source-of-Truth-Mapping-Bereinigung mitfixen oder als eigenes
kleines Ticket führen.

---

## 10. Zusammenfassung & Fix-Roadmap

| Finding | Zutreffende Hypothese | Ursache (kurz) | Fix in | Aufwand |
|---------|----------------------|----------------|--------|---------|
| **F1** | (c) | Prompt widerspricht sich: 4-breite Range (Untergrenze=18) + 3 hartcodierte „18 Sätze“-Beispiele | 29.2 | S |
| **F2** | (b) primär, (c) sekundär | `max_tokens=3000` zu niedrig für Sonnet → Truncation; `json-repair` maskiert sie still | 29.2 | S–M |
| **F3** | Label-Format-Mismatch | `data_analyzer` liefert DB-Konstanten, `prompt_builder.WEAKNESS_LABEL_TO_KEYS` kennt nur menschenlesbare Labels → Schwachstellen still verworfen; zusätzlich nur „1 Übung“ statt Volumen gefordert | 29.3 | M |

**Reihenfolge bestätigt:** 29.2 (F1+F2) vor 29.3 (F3) – die F2-Truncation
zerstört den Legs-Tag, auf den die F3-Schwachstellen-Abdeckung angewiesen ist.

**Akzeptanzkriterien 29.1 erfüllt:** Jeder Finding hat eine identifizierte,
reproduzierte Ursache (kein „bleibt unklar“). Jede Fix-Strategie ist auf
S/M-Aufwand begrenzt. Keine Fixes in 29.1.
