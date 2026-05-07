# Berry-Gym – Erweiterungs-Roadmap
**Erstellt:** 2026-03-12
**Ziel:** Professionelles, tägliches Trainings-Tool für private Nutzung mit Freunden
**Strategie:** Bugs & UX zuerst, dann Features – kein neues Feature ohne Polish des Bestehenden

---

## Phase 1 – Bugs & Navigation *(klein, sofort spürbar)*
**Branch:** `feature/phase1-ux-fixes`
**Status:** ✅ Abgeschlossen (2026-03-12)

| # | Aufgabe | Datei(en) |
|---|---|---|
| 1.1 | Dauer-Bug: `finish_training` zeigt für historische Trainings `jetzt - ursprung` | `training_session.py` |
| 1.2 | KI-Empfehlung auf Abschlussseite aktivieren (implementiert, deaktiviert) | `training_finish.html` |
| 1.3 | "Alle anzeigen" → "Trainingshistorie / Bearbeiten" (klarere Navigation) | `dashboard.html` |
| 1.4 | Wochenvolumen-Widget: Deload-Woche mit Kontext kennzeichnen (nicht "0 kg") | `dashboard.html`, `views/dashboard` |
| 1.5 | Session-Notiz & Dauer in Trainingshistorie anzeigen | `training_list.html` / Training-Detail |

---

## Phase 2 – PR-System *(mittlerer Aufwand, emotional wichtig)*
**Branch:** `feature/phase2-pr-system`
**Status:** ✅ Abgeschlossen (2026-03-13)

| # | Aufgabe | Details |
|---|---|---|
| 2.1 | PR-Detection beim Speichern | Neues Max-Gewicht ODER neue Wdh auf gleichem Gewicht → in DB markieren |
| 2.2 | PR-Moment auf Abschlussseite | Visuell hervorheben, nicht nur Text |
| 2.3 | PR-History pro Übung | In Übungsstatistik sichtbar |
| 2.4 | "Deine PRs diese Woche" auf Dashboard | Kleines Widget, optional |

---

## Phase 3 – Trainingsblock-Konzept *(Phasenwechsel intelligent behandeln)*
**Branch:** `feature/phase3-trainingsblock`
**Status:** ✅ Abgeschlossen (2026-03-23)
**Priorität:** Mittel – relevant sobald User Trainingsplan wechselt (aktueller Plan läuft noch ~7 Wochen)

### Hintergrund / Problem
Beim Wechsel von einer Definitionsphase (12–15 Wdh, ~50 kg) auf eine Massephase (6–8 Wdh, ~75 kg)
sinkt das **Trainingsvolumen** (kg × Wdh × Sätze) auf dem Papier dramatisch, obwohl die Belastung
tatsächlich höher ist. Das führt zu falschen Warnungen und irreführenden Trend-Diagrammen.

**Rechenbeispiel:**
- Definition: 4 × 12 × 50 kg = 2.400 kg Volumen
- Masse:       4 × 6 × 75 kg = 1.800 kg Volumen → −25 %, obwohl schwerer trainiert wird

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 3.1 | Trainingsblock-Modell | `Trainingsblock` mit `start_datum`, `end_datum`, `typ` (Definition/Masse/Kraft/Peaking/Deload), `ziel_rep_range` |
| 3.2 | Volumen-Baseline pro Block | Vergleiche Volumen nur innerhalb desselben Blocks, nicht blockübergreifend |
| 3.3 | Phasenwechsel-Hinweis | Beim Plan-Wechsel: User wird gefragt, ob neuer Block gestartet werden soll |
| 3.4 | Intensitäts-Normalisierung | Zeige sowohl Volumen als auch geschätzte 1RM-Last als Trend – so sind beide Phasen vergleichbar |
| 3.5 | Volumen-Warnungen unterdrücken | Keine "Volumen gesunken"-KI-Warnung in den ersten 3 Wochen eines neuen Blocks |

### Abhängigkeiten
- Setzt Phase 2 (PR-System, 1RM-Tracking) voraus ✅ erledigt
- Benötigt Plan-Wechsel-Event (User muss neuen Block manuell starten oder beim Plan-Aktivieren gefragt werden)

---

## Phase 4 – Dashboard-Hierarchie *(täglich sichtbar)*
**Branch:** `feature/phase4-dashboard`
**Status:** ✅ Abgeschlossen (2026-03-23)

| # | Aufgabe | Details |
|---|---|---|
| 4.1 | Quick Actions: 3 primäre Buttons | Training, Körperwerte, Cardio – Rest unter "Mehr" |
| 4.2 | Farbwirrwarr bereinigen | Einheitliche Button-Sprache |
| 4.3 | Motivationstext datenbasisiert | "Letztes Mal 80kg – heute PR-Versuch?" statt Generic |

---

## Phase 5 – Trainingsabschluss aufwerten *(Belohnungsmoment)*
**Branch:** `feature/phase5-finish-screen`
**Status:** ✅ Abgeschlossen (2026-03-23)

| # | Aufgabe | Details |
|---|---|---|
| 5.1 | Volumen vs. letztes Mal gleicher Trainingstag | Badge "+2.8% vs. letztes Mal" (grün/rot) unter Gesamtvolumen |
| 5.2 | PR-Integration aus Phase 2 | ✅ bereits vorhanden (session_prs) |
| 5.3 | Weiterleitung: "Nächstes Training vorschlagen" | Button "Speichern & nächstes Training – *Plan Name*" leitet direkt zu training_start_plan |

---

## Phase 6 – Trainingshistorie aufwerten *(Quick Wins, kein neues Model)*
**Branch:** `feature/phase6-data-visibility`

Beide ursprünglichen Punkte (Coach-Notizen, Trainingskommentar) waren bereits implementiert.
Echte Lücken in der Trainingshistorie:

| # | Aufgabe | Details |
|---|---|---|
| 6.1 | Plan-Name in Trainingshistorie | `select_related("plan")` in `training_list`-View + Plan-Name Badge in `training_list.html` |
| 6.2 | PR-Badge in Trainingshistorie | Annotate-Query ob Session PRs enthält → Trophy-Badge in `training_list.html` |

---

## Phase 7 – Statistiken vertiefen *(bestehende Daten besser nutzen)*
**Branch:** `feature/phase7-stats`

RPE wird bei jedem Satz erfasst, aber nie als Trend ausgewertet. Die Muskelgruppen-Balance
ist berechnet, aber löst keine proaktiven Hinweise aus.

| # | Aufgabe | Details |
|---|---|---|
| 7.1 | RPE-Trend pro Übung | Chart in `exercise_stats`: RPE-Verlauf über Zeit – "RPE steigt trotz gleichem Gewicht → Erholung prüfen" |
| 7.2 | Muscle-Group-Balance Alert | Erweiterung von `_get_performance_warnings()`: Alert wenn Muskelgruppe stark unterrepräsentiert – z.B. "Brust 4× diese Woche, Rücken 1×" |

---

## Phase 8 – Prognose & Forecasting *(Ziele greifbar machen)*
**Branch:** `feature/phase8-forecasting`
**Status:** ✅ Abgeschlossen (2026-03-23)

Beide Features nutzen pure-Python Least-Squares Regression auf vorhandenen Datenpunkten –
keine externe Bibliothek notwendig.

| # | Aufgabe | Details |
|---|---|---|
| 8.1 | 1RM-Trend + Prognose in Übungs-Statistik | Badge unter 1RM-Chart: "Bei aktuellem Tempo: ~X kg Est. 1RM in 8 Wochen" (min. 5 Sessions, nur bei positivem Trend) |
| 8.2 | Body-Composition-Forecast | Forecast-Card in `body_stats`: Gewicht ~X kg und KFA ~X% in 6 Wochen (min. 5 Datenpunkte) |

---

## Phase 9 – Datenqualität & Metriken-Hygiene *(Quick Wins, bestehende Features verbessern)*
**Branch:** `feature/phase9-data-quality`
**Status:** ✅ Abgeschlossen (2026-03-26)
**Quelle:** Auswertung 12-Wochen-PDF-Export (März 2026)

Bestehende Features (insbesondere Phase 8 Forecasting) liefern potenziell verzerrte Ergebnisse,
weil BIA-Ausreißer und kurzfristige Gewichtsschwankungen ungefiltert einfließen.
Diese Phase fixt die Datengrundlage, bevor neue Features darauf aufbauen.

| # | Aufgabe | Details |
|---|---|---|
| 9.1 | BIA-Ausreißer-Erkennung | 3-Punkt-Median-Filter über FFMI, KFA, Muskelmasse. Harte Schwellenwerte: FFMI Δ>0,5/Woche, KFA Δ>2,0%/Woche → automatisches Flagging als möglicher Messfehler. Optional: offener Kreis statt gefüllter Punkt in Trend-Charts |
| 9.2 | Gleitender 14-Tage-Durchschnitt für Gewichtstrend | Ersetzt das aktuelle 7-Tage-Fenster. Glättet Tagesfluktuation durch Wasserhaushalt und Mahlzeiten. Angezeigte Gewichtsveränderungsrate wird zuverlässiger |
| 9.3 | RPE-10-Warnung prominent in Dashboard/Stats | RPE-10-Anteil als eigene Metrik. Schwellenwerte: <5% optimal, 5–15% akzeptabel, >15% Warnung (Übertrainingsrisiko, Verletzungsgefahr) |
| 9.4 | Ermüdungs-Index Refactoring | RPE-Verteilung statt RPE-Durchschnitt verwenden. >20% RPE-10 = mindestens 50/100. Aktuelle Heuristik (40% Volumen, 30% RPE, 30% Frequenz) produziert inkonsistente Ergebnisse (20/100 trotz 22,7% RPE-10-Sätzen) |
| 9.5 | Tonnage als zusätzliche Volumen-Metrik | Gewicht × Reps × Sätze als ergänzende Metrik neben Satz-Zählung. Löst das Problem: 12 Sätze à 30 kg ≠ 12 Sätze à 50 kg |
| 9.6 | RPE-Ziel-basierte Gewichtssteigerung & Plateau-Konsolidierung | Gewicht wird nur noch hochgesetzt wenn Max-Wdh bei RPE ≤ Ziel-RPE erreicht werden (statt blindem Max-Wdh-Check). Neues `PlanUebung.rpe_ziel`-Feld vom AI-Generator gesetzt. ML-Pipeline um `rpe_target`-Feature erweitert. Plateau-Erkennung unterscheidet jetzt Konsolidierung (sinkender RPE = User wird stärker) von echtem Plateau (gleichbleibender RPE) |

### Abhängigkeiten
- 9.1 verbessert Forecast-Qualität aus Phase 8 (Ausreißer verzerren Regression)
- 9.4 nutzt bestehenden Ermüdungs-Index (kein Neubau, Refactoring)
- 9.6 greift in Empfehlungsalgorithmus, ML-Pipeline und Plateau-Erkennung ein

---

## Phase 10 – Periodisierungs-Intelligence *(baut auf Phase 3 auf)*
**Branch:** `feature/phase10-periodisierung`
**Status:** ✅ Abgeschlossen (2026-03-26)

Setzt den `Trainingsblock` aus Phase 3 voraus. Ein Block läuft typisch 8–12 Wochen –
das System soll proaktiv auf den Phasenwechsel hinweisen, statt passiv zu warten.

| # | Aufgabe | Details |
|---|---|---|
| 10.1 | Block-Alter-Warnung auf Dashboard | Wenn aktiver Block > 8 Wochen alt: Hinweis "Dein Kraft-Block läuft seit 9 Wochen – Zeit für Hypertrophie?" mit Link zum Plan-Wechsel-Flow |
| 10.2 | Block-Typ-Empfehlung | Basierend auf letztem Block-Typ einen logischen Folge-Block vorschlagen (Kraft → Hypertrophie → Definition → Deload-Block) |

---

## Phase 11 – KI-Planvalidierung *(niedrig-mittlerer Aufwand, fixt bestehendes Feature)*
**Branch:** `feature/phase11-plan-validation`
**Status:** ✅ Abgeschlossen (2026-03-26)
**Quelle:** Manuelle Auswertung eines KI-generierten 3er-Split Plans (März 2026)

Die KI-Plan-Generierung (`ai_coach/plan_generator.py`) hat strukturelle Fehler, die durch
reine Prompt-Anweisungen nicht zuverlässig verhindert werden. Die bestehende `validate_plan()`
prüft nur Pflichtfelder, Übungs-Existenz und Intra-Session-Duplikate. Alle folgenden Checks
sind programmatische Post-Validierungen, die nach der LLM-Antwort laufen.

| # | Aufgabe | Details |
|---|---|---|
| 11.1 | Cross-Session-Duplikat-Check | Bei ≤4 Sessions: identische Übung in verschiedenen Sessions flaggen. Verhindert z.B. RDL auf Pull UND Legs. Bei >4 Sessions (PPL 6x) weiterhin erlaubt |
| 11.2 | Verbotene Kombinationen | Programmatischer Check: Front Raises verboten wenn Bankdrücken ODER Schulterdrücken in derselben Session. Prompt-Regel existiert, wird vom LLM ignoriert |
| 11.3 | Anatomische Pflichtgruppen | Post-Validierung: Hintere Schulter (SCHULTER_HINT) muss im Plan ≥2 Sätze haben. Vertikaler Zug (RUECKEN_LAT) muss am Pull-Tag vorhanden sein. Kein Soft-Hint – harter Check mit Auto-Fix |
| 11.4 | Compound-vor-Isolation Reihenfolge | Order-Feld validieren: Compound-Übungen (erkennbar an Muskelgruppe + Satzanzahl ≥3) vor Isolation. Auto-Fix durch Umsortierung |
| 11.5 | Pausenzeiten-Plausibilität | rest_seconds prüfen: Compound (≥3 Sätze) → 120-180s, Isolation (<3 Sätze) → 60-90s. Korrektur auf Defaults wenn pauschal identisch |

### Abhängigkeiten
- Keine externen Abhängigkeiten – arbeitet auf bestehender `validate_plan()` Infrastruktur
- Smart Retry (`_fix_invalid_exercises()`) kann für Auto-Fixes erweitert werden

---

## Phase 12 – Kontextsensitive Empfehlungen *(mittlerer Aufwand, Empfehlungsqualität)*
**Branch:** `feature/phase12-context-recommendations`
**Status:** ✅ Abgeschlossen (2026-03-26)
**Quelle:** Auswertung 12-Wochen-PDF-Export (März 2026)

Empfehlungen und Warnungen passen sich an den aktiven Trainingsblock-Typ an.
Im Definitionsmodus wird "mehr Sätze" durch "Intensität halten" ersetzt.
Volumen-Schwellenwerte differenzieren nach Muskelgruppengröße statt one-size-fits-all.

| # | Aufgabe | Details |
|---|---|---|
| 12.1 | Trainingsmodus-Erweiterung | Baut auf Phase 3 Trainingsblock-Typ auf. Empfehlungstexte, Deload-Heuristik und Volumen-Schwellenwerte werden modusabhängig: Aufbau → Volumen-Steigerung priorisieren; Definition → Intensität halten, Compounds priorisieren, Isolation reduzieren |
| 12.2 | Gruppenspezifische Volumen-Kalibrierung | Differenzierte Schwellenwerte: Große Gruppen (Rücken, Beine, Brust) 12–25 Sätze; Mittlere (Schultern, Trizeps) 10–18; Kleine (Bizeps, Waden) 8–16; Haltung (Hüftbeuger, Rotatoren) 6–12. Ersetzt pauschale 12–20 für alle |
| 12.3 | Wiederholungsbereich-Analyse | Neuer Stats-Abschnitt: prozentuale Verteilung der Sätze in Hypertrophie (8–12), Kraft (3–6), Ausdauer (12–15+). Im Definitionsmodus: Empfehlung für schwere Compounds (6–8 Reps) statt leichte Sätze |

### Abhängigkeiten
- 12.1 setzt Phase 3 (Trainingsblock mit `typ`) voraus ✅ erledigt
- 12.2 erweitert bestehende Muskelgruppen-Analyse
- Bariatric-spezifische Schwellenwerte werden nicht als eigenes Feature implementiert – die Trainingsblock-Typen decken diesen Bedarf ab

---

## Phase 13 – LLM-Planqualität & Dynamische Periodisierung *(mittlerer Aufwand, Planqualität)*
**Branch:** `feature/phase13-plan-quality`
**Status:** ✅ Abgeschlossen (2026-03-27)
**Quelle:** Testauswertung KI-generierter Pläne nach Phase 11 Deploy (März 2026)

Trotz Phase-11-Validierung produziert das LLM weiterhin strukturelle Fehler, die
programmatisch abfangbar sind. Zusätzlich ist die Periodisierungs-Beschreibung im
Plan-PDF quasi-identisch bei jedem Profil — Werte wie RPE-Range, Wdh-Schwellen und
Deload-Prozente sind hardcodiert statt aus den Plan-Metadaten abgeleitet.

| # | Aufgabe | Details |
|---|---|---|
| 13.1 | Muskelgruppen-Überrepräsentation pro Session | Max ~7 Sätze gleiche primäre Muskelgruppe pro Session. Verhindert z.B. 3× Quad (Kniebeuge + Bulgarian Split Squat + Frontkniebeuge = 10 Sätze Quad). Auto-Fix: überzählige Übung durch unterrepräsentierte Gruppe ersetzen |
| 13.2 | Weakness-Coverage: hilfsmuskeln-only unzureichend | `hilfsmuskeln` allein gilt nicht als Coverage für Pflicht-Schwachstellen. Bei identifizierter Schwachstelle muss mind. 1 Übung mit `muskelgruppe=KEY` (primär) vorhanden sein. hilfsmuskeln nur als Bonus werten |
| 13.3 | Dynamische Periodisierungs-Beschreibung | Progressions-Text abhängig von `target_profile` und `periodization` statt hardcodiert. Kraft: "Steigere Gewicht wenn RPE < 7" statt ">12 Wdh". Definition: "Halte Gewicht, reduziere Pausen" statt "+1 Satz". Wellenförmig: Woche-für-Woche-Variation. Werte (RPE-Range, Wdh-Range, Deload-%) aus Plan-Metadaten ableiten |

### Abhängigkeiten
- 13.1 erweitert `plan_validator.py` (Phase 11 Infrastruktur)
- 13.2 ändert `_validate_weakness_coverage()` in `plan_generator.py`
- 13.3 ändert `prompt_builder.py` und ggf. Plan-Beschreibungs-Generierung

---

## Phase 14 – Körpergewicht-Übungen: Gegengewicht & Historisches Gewicht *(mittlerer Aufwand, Datenintegrität)*
**Branch:** `feature/phase14-bodyweight-accuracy`
**Status:** ✅ Abgeschlossen (2026-03-27)
**Quelle:** Praxistest – 15 kg Gewichtsverlust verfälscht Progressions-Tracking bei Dips/Klimmzügen

Körpergewicht-Übungen (`gewichts_typ=KOERPERGEWICHT`) nutzen `koerpergewicht_faktor` und
berechnen `effektives_gewicht = (user_kg * faktor) + zusatzgewicht`. Zwei fundamentale Lücken:

| # | Aufgabe | Details |
|---|---|---|
| 14.1 | Gegengewicht-Modus für assistierte Übungen | Neues Feld `Satz.ist_gegengewicht` (Boolean) oder `Uebung.gewichts_richtung` (ZUSATZ/GEGEN). Bei `ist_gegengewicht=True`: `effektives_gewicht = (user_kg * faktor) - gewicht` statt `+ gewicht`. Betrifft assistierte Dips, assistierte Klimmzüge. UI: Toggle "Gegengewicht" im Satz-Eingabeformular |
| 14.2 | Historisches Körpergewicht für 1RM-Berechnung | `_compute_1rm_and_weight()` nutzt aktuell immer das aktuelle Körpergewicht. Fix: bei KOERPERGEWICHT-Übungen das Körpergewicht vom Trainingstag verwenden (nächster `KoerperWerte`-Eintrag ≤ Trainingsdatum). Fallback: aktuelles Gewicht wenn kein historischer Wert existiert |
| 14.3 | Progressions-Korrektur in Trend-Charts | 1RM-Trend und Volumen-Charts für KOERPERGEWICHT-Übungen mit historischem Gewicht neu berechnen. Bestehende Berechnungen in `exercise_stats`, Tonnage (Phase 9.5), und Forecast (Phase 8) anpassen |

### Abhängigkeiten
- 14.2 nutzt bestehende `KoerperWerte`-Tabelle (Gewichtsverlauf ist bereits erfasst)
- 14.3 betrifft `training_stats.py` (`_compute_1rm_and_weight`), Tonnage-Berechnung, Forecast
- 14.1 benötigt DB-Migration (neues Feld auf Satz oder Uebung)

### Betroffene Berechnungen
- `_compute_1rm_and_weight()` in `training_stats.py` (zentral)
- PR-Detection (Phase 2): 1RM-Vergleich muss historisches Gewicht nutzen
- Forecast (Phase 8): Regression auf korrigierten 1RM-Werten
- Tonnage (Phase 9.5): Volumen = effektives_gewicht × reps × sets

---

## Phase 15 – Mindest-Satz-Budget Validierung & Auto-Fix *(klein, Planqualität)*
**Branch:** `feature/phase15-min-sets-budget`
**Status:** ✅ Abgeschlossen (2026-03-28)

| # | Aufgabe | Details |
|---|---|---|
| 15.1 | Session-Satz-Budget in `_auto_fix_weakness()` | Prüft verfügbares Budget bevor Übung ersetzt oder hinzugefügt wird. Bei Luft (current < max-2) → hinzufügen statt ersetzen |
| 15.2 | Mindest-Satz-Budget Validierung | Neuer Check `_check_min_sets_per_session()`: Warnung wenn Session < 14 Sätze (`_MIN_SETS_PER_SESSION`) |
| 15.3 | Bug-Fix LABEL_TO_KEYS | DB-Konstanten (HUEFTBEUGER, SCHULTER_HINT etc.) als Keys in `LABEL_TO_KEYS` aufgenommen |
| 15.4 | Plan-Titel Humanisierung | `_humanize_plan_name()` ersetzt DB-Konstanten durch Klartext im Plan-Namen |

---

## Phase 16 – Push/Pull-Validierung im Plangenerator *(klein, Planqualität)*
**Branch:** `feature/phase16-push-pull-validation`
**Status:** ✅ Abgeschlossen (2026-04-02)

### Hintergrund / Problem
Der Training Report (März 2026) identifiziert eine Push/Pull-Ratio von 1,64:1 und empfiehlt
mehr Pull-Übungen. Der Plangenerator validiert Muskelgruppen-Balance pro Session (Phase 13.1),
aber prüft die Push/Pull-Balance über den Gesamtplan nicht. Das LLM tendiert zu Push-lastigen
Plänen, weil Push-Übungen vielfältiger sind (Brust+Schulter+Trizeps vs. Rücken+Bizeps).

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 16.1 | Push/Pull-Klassifikation pro Übung | Bestehende Muskelgruppen-Zuordnung nutzen um jede Übung als Push, Pull oder Neutral (Legs/Core) zu klassifizieren. Mapping in `plan_validator.py` oder `constants.py` |
| 16.2 | Gesamtplan Push/Pull-Ratio Check | Nach Generierung: Push-Sätze vs. Pull-Sätze über alle Sessions zählen. Threshold: Ratio > 1,5:1 → Warnung. Ratio > 1,8:1 → Auto-Fix |
| 16.3 | Auto-Fix: Pull-Volumen erhöhen | Bei Imbalance: unterrepräsentierte Pull-Übung (z.B. Face Pulls, Reverse Flys) hinzufügen oder Push-Isolation (z.B. extra Seitheben) durch Pull-Isolation ersetzen. Nur Isolation-Übungen tauschen, Compounds nie antasten |

### Betroffene Dateien
- `ai_coach/plan_validator.py` – neuer Check + Auto-Fix
- `core/models/constants.py` – ggf. Push/Pull-Mapping
- Tests: neue Testfälle für Ratio-Berechnung und Auto-Fix

### Abhängigkeiten
- Keine – arbeitet auf bestehender Validator-Infrastruktur

### Abgrenzung
- Nur Gesamtplan-Level, nicht pro Session (Session-Balance ist Phase 13.1)
- Legs-Tag-Übungen als Neutral klassifizieren (Kniebeuge ist weder Push noch Pull im Oberkörper-Sinn)

---

## Phase 17 – Plandauer als Plan-Input *(mittel, Planqualität)*
**Branch:** `feature/phase17-plan-duration`
**Status:** ✅ Abgeschlossen (2026-04-02)

### Hintergrund / Problem
Der Plangenerator erzeugt immer 12-Wochen-Pläne mit hardcodierten Deload-Wochen (4, 8, 12).
Die Periodisierungsbeschreibung im Plan-PDF nennt feste Wochennummern unabhängig von der
tatsächlichen Plandauer. Ein 4-Wochen-Plan braucht andere Deload-Platzierung, aggressiveres
Startvolumen und andere Progressionserwartungen als ein 12-Wochen-Plan.

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 17.1 | Dauer-Feld in Plan-Erstellung | Neues Eingabefeld `plan_dauer_wochen` (Integer, 4–16, Default 12) im Plan-Erstellungs-UI und als Parameter an den Generator |
| 17.2 | Dynamische Deload-Berechnung | Deload-Wochen automatisch platzieren: alle 3–4 Wochen eine Deload-Woche. Bei 4 Wochen: Woche 4. Bei 8 Wochen: Woche 4+8. Bei 12 Wochen: 4+8+12. Formel statt Hardcoding |
| 17.3 | Periodisierungsbeschreibung anpassen | `prompt_builder.py`: Wochennummern im Periodisierungstext dynamisch aus Plandauer berechnen. Deload-%, RPE-Ziele und Progressionshinweise bleiben abhängig von `target_profile` (Phase 13.3) |
| 17.4 | Trainingsblock-Integration | `Trainingsblock.end_datum` aus `start_datum + plan_dauer_wochen` berechnen. Block-Alter-Warnung (Phase 10) nutzt die geplante Dauer statt pauschal 8 Wochen |

### Betroffene Dateien
- `ai_coach/prompt_builder.py` – Dauer-Parameter + dynamische Periodisierung
- `ai_coach/plan_generator.py` – Dauer entgegennehmen und weiterreichen
- `core/views/plan_creation.py` (o.ä.) – UI-Feld
- `core/models/training_block.py` – end_datum aus Dauer
- `core/utils/periodization.py` – Block-Alter-Logik anpassen

### Abhängigkeiten
- Phase 10 (Trainingsblock-Konzept) ✅ erledigt
- Phase 13.3 (Dynamische Periodisierungsbeschreibung) ✅ erledigt

### Abgrenzung
- KEINE Änderung der Schwachstellen-Strategie basierend auf Dauer (zweiter Schritt, ggf. Phase 22+)
- KEINE Änderung der Validierungsregeln basierend auf Dauer
- Nur Deload-Platzierung + Periodisierungsbeschreibung + Trainingsblock-Endedatum

---

## Phase 18 – Startgewicht-Empfehlung beim Planwechsel *(mittel, UX)*
**Branch:** `feature/phase18-start-weight`
**Status:** ✅ Abgeschlossen (2026-04-02)

### Hintergrund / Problem
Beim Wechsel auf einen neuen Plan weiß der User nicht, mit welchem Gewicht er starten soll.
Besonders relevant wenn bisherige Gewichte mit RPE 10 erzielt wurden und der neue Plan
RPE 8 als Ziel hat – das erfordert eine Gewichtsreduktion. Aktuell zeigt die App beim
Trainingsstart nur das letzte verwendete Gewicht ohne RPE-Kontext.

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 18.1 | Historisches RPE-Gewicht-Mapping | Für jede Übung im neuen Plan: letzte 3–5 Sätze mit Gewicht+RPE laden. Daraus ableiten bei welchem Gewicht der User typischerweise welche RPE erreicht |
| 18.2 | RPE-korrigierte Startempfehlung | Wenn Ziel-RPE des neuen Plans (z.B. 8) niedriger als letzte durchschnittliche RPE (z.B. 9,5): Gewichtsreduktion empfehlen. Heuristik: ~2,5% Reduktion pro RPE-Punkt Differenz (basierend auf RPE-Last-Tabellen) |
| 18.3 | UI: Empfehlung im Trainings-Start | Beim Start einer Session: neben jeder Übung „Empfohlen: X kg (basierend auf RPE 8)" anzeigen. Nur wenn historische Daten für die Übung existieren. Bei neuen Übungen: kein Hinweis |

### Betroffene Dateien
- `core/views/training_stats.py` – Berechnung RPE-korrigiertes Gewicht
- `core/views/training_session.py` – Empfehlung laden und an Template übergeben
- `core/templates/core/training_session.html` – Empfehlung anzeigen
- Tests: Berechnung der Empfehlung mit verschiedenen RPE-Historien

### Abhängigkeiten
- Phase 9.6 (RPE-Ziel auf PlanUebung) ✅ erledigt
- Historische Satz-Daten mit RPE müssen vorhanden sein

### Abgrenzung
- Empfehlung ist ein Hinweis, kein Zwang – User kann frei eingeben
- Keine automatische Gewichtsanpassung in der DB
- Nur für Übungen mit ≥3 historischen Sätzen mit RPE-Wert

---

## Phase 19 – Session-RPE-Trend *(klein, Dashboard)*
**Branch:** `feature/phase19-session-rpe-trend`
**Status:** ✅ Abgeschlossen (2026-04-02)

### Hintergrund / Problem
RPE wird pro Satz erfasst, aber nur als Gesamtverteilung ausgewertet (Phase 9.3).
Es gibt keinen Trend auf Session-Ebene. Steigende Durchschnitts-RPE über mehrere Sessions
ist ein Frühindikator für Fatigue-Akkumulation – bevor der Fatigue-Index anschlägt.

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 19.1 | Session-RPE berechnen | Durchschnitts-RPE pro Trainingseinheit als neue Metrik. Gewichtet nach Sätzen (nicht Übungen). Bereits vorhandene Satz-RPE-Daten aggregieren |
| 19.2 | RPE-Trend-Chart im Dashboard | Sparkline oder Mini-Chart: Session-RPE der letzten 8–12 Sessions. Trendlinie (lineare Regression) zeigt ob RPE steigt, fällt oder stabil ist |
| 19.3 | Frühwarnung bei steigendem RPE | Wenn Trend über 3+ Sessions steigt UND aktueller Durchschnitt > 8,5: Warnung „Deine Trainingsintensität steigt – Deload in Betracht ziehen?" Eingebunden in bestehende `_get_performance_warnings()` |

### Betroffene Dateien
- `core/views/training_stats.py` – Session-RPE Aggregation + Trend-Berechnung
- `core/templates/core/dashboard.html` – Mini-Chart
- Tests: Trend-Berechnung mit steigenden/fallenden/stabilen RPE-Werten

### Abhängigkeiten
- Keine – nutzt bestehende Satz-RPE-Daten

### Abgrenzung
- Kein RPE-Trend pro Übung (das ist Phase 7.1, bereits in Roadmap)
- Nur Session-Level-Aggregation

---

## Phase 20 – Schwachstellen-Tracker / Feedback-Loop *(mittel, Dashboard)*
**Branch:** `feature/phase20-weakness-tracker`
**Status:** ✅ Fertig

### Hintergrund / Problem
Der Report identifiziert Schwachstellen, der Generator baut einen Plan dagegen. Aber es gibt
keinen automatischen Zwischencheck ob der Plan die Schwachstellen tatsächlich behebt. Der User
muss manuell einen neuen Report exportieren und vergleichen. Es fehlt ein geschlossener
Feedback-Loop: Diagnose → Plan → Tracking → Re-Diagnose.

### Geplante Lösung

| # | Aufgabe | Details |
|---|---|---|
| 20.1 | Schwachstellen bei Plangenerierung persistieren | Neue Tabelle oder JSON-Feld auf `Trainingsblock`: identifizierte Schwachstellen mit Ist-Sätzen und Soll-Sätzen zum Zeitpunkt der Plananalyse speichern |
| 20.2 | Laufendes Satz-Tracking gegen Ziel | Pro Muskelgruppe aus den Schwachstellen: aktuelle Sätze im laufenden Monat zählen und gegen Soll-Bereich (12–20) tracken. Berechnung analog zur Muskelgruppen-Analyse im Report |
| 20.3 | Dashboard-Widget | Card „Schwachstellen-Fortschritt": Muskelgruppe – Ist-Sätze / Soll-Sätze – Fortschrittsbalken. Grün wenn Ziel erreicht, Gelb wenn auf Kurs, Rot wenn hinter Plan |
| 20.4 | Monatsende-Vergleich | Am Ende eines Monats (oder bei Report-Export): automatischer Vergleich mit dem Ausgangszustand. „Bauch: 6 → 14 Sätze ✓ Behoben" oder „Seitliche Schulter: 9 → 10 Sätze ✗ Noch untertrainiert" |

### Betroffene Dateien
- `core/models/` – neues Feld/Tabelle für persistierte Schwachstellen
- `ai_coach/plan_generator.py` – Schwachstellen bei Generierung speichern
- `core/views/training_stats.py` – laufendes Tracking
- `core/views/dashboard.py` – Widget-Daten
- `core/templates/core/dashboard.html` – Widget-UI
- Migration für neues Datenmodell

### Abhängigkeiten
- Phase 9 (Muskelgruppen-Analyse) ✅ erledigt
- Phase 11+ (Schwachstellen-Erkennung im Generator) ✅ erledigt

### Abgrenzung
- Kein automatischer Plan-Anpassung bei Zielverfehlung (das wäre ein autonomer Planner)
- Nur Tracking und Visualisierung – Handlung bleibt beim User
- Persistierte Schwachstellen sind Snapshot zum Zeitpunkt der Plananalyse, nicht live-berechnet

---

## Phase 21 – Statistik-Seite erweitern *(mittel, kann unterteilt werden)*
**Branch:** `feature/phase21-stats-upgrade`
**Status:** ✅ Abgeschlossen (2026-04-02)

### Hintergrund / Problem
Die besten Analysen (Plateau-Tracking, Kraftstandards, Push/Pull-Ratio, Kraftentwicklung Top 5)
existieren nur im PDF-Report. Die Statistik-Seite (`/stats/`) hat Volumen-Progression,
Muskelgruppen-Balance und Heatmap, aber nicht das vollständige Bild. Der User muss einen PDF
exportieren um alle Analysen zu sehen.

Ursprüngliches Konzept sah eine separate View `/training/report/` vor. Verworfen, weil:
- Muskelgruppen-Balance und Wochenvolumen wären doppelt vorhanden
- User müsste zwischen zwei Seiten springen für ein Gesamtbild
- Berechnungen überlappen stark (gleiche Helfer-Funktionen)
- 1-User-Tool – keine verschiedenen Zielgruppen die separate Views rechtfertigen

### Geplante Lösung
Bestehende `/stats/`-Seite um die fehlenden Report-Analysen erweitern. Kein neues Template,
keine neue Route – alles in `training_stats.py` + `training_stats.html` ergänzen.

| # | Aufgabe | Details |
|---|---|---|
| 21.1 | Muskelgruppen-Balance mit Soll-Bereich | Bestehendes Balkendiagramm um Soll-Bereich-Overlay erweitern (aus `VOLUMEN_SCHWELLENWERTE`). Klick auf Muskelgruppe → Detail mit Übungsliste und Satz-Verteilung |
| 21.2 | Push/Pull-Ratio (live) | Donut-Chart mit aktuellem Monatswert. Farbcodiert: Grün (<1,3), Gelb (1,3–1,5), Rot (>1,5) |
| 21.3 | Plateau-Tracking (live) | Tabelle der Top-5-Übungen mit Tage-seit-letztem-PR, Status-Badge. Analog zum PDF aber mit Live-Daten statt Report-Zeitraum |
| 21.4 | Kraftstandards-Übersicht | 1RM pro Übung mit Kraftstandard-Einordnung (Untrainiert→Elite). Progress-Bar zum nächsten Level. Bereits in PDF berechnet, hier als interaktive Ansicht |

### Betroffene Dateien
- `core/views/training_stats.py` – `training_stats()` View erweitern, neue Helfer-Funktionen
- `core/templates/core/training_stats.html` – neue Sektionen für 21.1–21.4
- `core/utils/advanced_stats.py` – Report-Logik ggf. refactoren für Dual-Use (PDF + Web)
- Tests: bestehende `test_training_stats.py` erweitern

### Abhängigkeiten
- Phase 16 (Push/Pull-Ratio) – für 21.2

### Abgrenzung
- PDF-Export bleibt bestehen – `/stats/` ist die interaktive Variante, PDF für Archivierung/Teilen
- Keine neuen Berechnungen – nur bestehende Report-Logik in die Stats-Seite überführen
- 21.6 (Wochenvolumen-Vollansicht) entfällt – `/stats/` hat das bereits
- Kann in Sub-Phasen aufgeteilt werden (21.1–21.2 als erster Schritt, 21.3–21.4 als zweiter)

---

## Phase 23 – Zeitfenster-basierte Trainingsanalysen *(mittel, Statistik-Hygiene)*
**Branch:** `feature/phase23-time-windowed-stats`
**Status:** ✅ Abgeschlossen (2026-05-07)
**Quelle:** Auswertung 30-Tage-PDF-Export (Mai 2026), User-Feedback zur RPE-Analyse

📄 **Detailkonzept:** [`docs/phase23_concept.md`](phase23_concept.md)

### Hintergrund / Problem
Mehrere Kennzahlen im Training Report nutzen einen All-Time-Schnitt über alle erfassten Sessions. Das verzerrt das Bild systematisch, wenn der User sein Trainingsverhalten bewusst ändert – die korrigierte Praxis wird durch das alte Verhalten überschrieben.

Konkret im Mai-2026-Report: RPE-10-Anteil 19,0 % (All-Time) löst Übertrainings-Warnung aus, obwohl die letzten 4 Wochen bei <7 % liegen. Die 19 % stammen aus den ersten 11+ Wochen Trainingshistorie und repräsentieren nicht den aktuellen Zustand.

Folgeprobleme: Volumen-Trend ohne RPE-Kontext irreführend (bewusste Intensitäts-Reduktion sieht aus wie Regression), Plateau-Logik wendet Konsolidierungs-Erkennung inkonsistent an, Ermüdungs-Index nutzt vermutlich anderen Zeitraum als RPE-Verteilung im selben Report (Inkonsistenz innerhalb desselben Dokuments).

### Geplante Lösung
Drei zusammenhängende Korrekturen mit gemeinsamer Grundidee: **Zeitfenster explizit machen statt implizit All-Time.** Andere Analysen (Muskelgruppen-Balance, Push/Pull) nutzen bereits 30-Tage-Fenster – RPE- und Volumen-Auswertung sind hier inkonsistent.

| # | Aufgabe | Details |
|---|---|---|
| 23.1 | RPE-Verteilung mit gestaffelten Zeitfenstern | RPE-Analyse zeigt Werte für letzte 2 Wochen / letzte 4 Wochen / Gesamt. Bewertung basiert auf 4-Wochen-Wert. Empfehlungen zitieren Zeitraum. |
| 23.2 | Effektives Volumen als zusätzliche Metrik | Neben Tonnage zweite Linie "Effektives Volumen" (nur RPE 7–9-Sätze). Trennt Junk Volume und Failure Volume ab. Zweite Linie im Wochen-Chart. |
| 23.3 | Plateau-Logik vereinheitlicht | Konsolidierungs-Erkennung (RPE sinkt bei stabilem/steigendem Gewicht) konsistent auf alle Plateau-Kandidaten anwenden. Aktuell inkonsistent angewendet. |
| 23.4 | Ermüdungs-Index Zeitfenster-Konsistenz | Vereinheitlichen auf festes 14-Tage-Fenster für alle Komponenten (Volumen/RPE/Frequenz). Vorab: Dead-Code-Status von `calculate_fatigue_index` klären (Tech-Debt aus Phase 9.4). |
| 23.5 | PDF-Report-Konsistenz *(optional)* | PDF-Export muss dieselbe Zeitfenster-Logik wie Live-Stats nutzen. Bestehende Tech-Debt aus Phase 9.4 (alte Heuristik im PDF) angleichen. Kann als 23.x ausgelagert werden. |

### Betroffene Dateien
- `core/utils/advanced_stats.py` – RPE-Verteilung, Plateau-Logik, evtl. Fatigue-Index
- `core/views/training_stats.py` – Effektives Volumen, Zeitfenster-Helfer
- `core/templates/core/training_stats.html` – RPE-Karte mit drei Zeiträumen, zweite Volumen-Linie
- `core/templates/core/training_pdf_simple.html` – PDF-Versionen analoger Sektionen
- `core/export/stats_collector.py` – Datenstruktur für drei Zeitfenster
- `core/tests/test_training_stats.py`, `test_advanced_stats.py` – neue Testfälle

### Abhängigkeiten
- Phase 9.3 (RPE-10-Warnung) – bestehende Logik wird zeitfenster-aware umgebaut
- Phase 9.4 (Ermüdungs-Index Refactoring) – Dead-Code-Status von `calculate_fatigue_index` muss vor 23.4 geklärt werden
- Phase 22 (Aktiver-Plan-Filter) – Reihenfolge: erst Plan-Filter, dann Zeitfenster innerhalb des Plans

### Abgrenzung
- KEINE Änderung am Plan-Generator (kein RPE-Profil als Generator-Input)
- KEINE neuen Trainingsblock-Features
- KEINE Änderung der Schwellenwerte (12–20 Sätze, RPE 7–9 etc.) – nur Berechnungs-Zeitraum
- All-Time-Werte bleiben sichtbar, nicht ersatzlos gestrichen
- 23.5 (PDF-Konsistenz) optional – falls Scope zu groß, in 23.x ausgliedern

---

## Bewusst NICHT in dieser Roadmap

- **Ernährungstracking:** Scope bleibt Trainings-Tool. Ein Basismodul (kcal + Protein) bringt zu wenig Nutzen bei zu wenig konsequenter Eingabe. Wer Ernährung trackt, nutzt ein dediziertes Tool dafür
- **Bariatric-Profil:** Medizinisch sensibel, persönliche Anpassung – nicht als Produkt-Feature. Trainingsblock-Typen + kontextsensitive Empfehlungen (Phase 12) decken den Bedarf an angepassten Schwellenwerten ab
- **Medizinisches Hinweisfeld:** Fällt mit Bariatric-Profil weg. Kein medizinisches Diagnose-Tool
- **Gewichtsverlust-Warnung bei aggressivem Defizit:** Sinnvoller Trigger, aber ohne Ernährungsdaten (kcal) nur eingeschränkt aussagekräftig. Zurückgestellt bis ggf. API-Integration mit einem Ernährungs-Tool existiert
- Schlaf-Tracking (braucht Wearable)
- Social Feed (zu aufwändig für privates Tool)
- Weitere AI/ML-Features (erst Polish des Bestehenden)
