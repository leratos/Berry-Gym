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

Beide Features nutzen lineare Regression auf vorhandenen Datenpunkten – keine
externe KI, nur `numpy`/simple Slope-Berechnung.

| # | Aufgabe | Details |
|---|---|---|
| 8.1 | 1RM-Trend + Prognose in Übungs-Statistik | Trendlinie + "In 8 Wochen bei aktuellem Tempo: ~X kg" in `exercise_stats` – motiviert und hilft beim Ziel-Setting |
| 8.2 | Body-Composition-Forecast | Trendextrapolation auf `KoerperWerte`: "Bei aktuellem Tempo KFA 12% in ~6 Wochen" in `body_stats` |

---

## Phase 9 – Periodisierungs-Intelligence *(baut auf Phase 3 auf)*
**Branch:** `feature/phase9-periodisierung`

Setzt den `Trainingsblock` aus Phase 3 voraus. Ein Block läuft typisch 8–12 Wochen –
das System soll proaktiv auf den Phasenwechsel hinweisen, statt passiv zu warten.

| # | Aufgabe | Details |
|---|---|---|
| 9.1 | Block-Alter-Warnung auf Dashboard | Wenn aktiver Block > 8 Wochen alt: Hinweis "Dein Kraft-Block läuft seit 9 Wochen – Zeit für Hypertrophie?" mit Link zum Plan-Wechsel-Flow |
| 9.2 | Block-Typ-Empfehlung | Basierend auf letztem Block-Typ einen logischen Folge-Block vorschlagen (Kraft → Hypertrophie → Definition → Deload-Block) |

---

## Bewusst NICHT in dieser Roadmap

- Ernährungstracking (anderes Produkt)
- Schlaf-Tracking (braucht Wearable)
- Social Feed (zu aufwändig für privates Tool)
- Weitere AI/ML-Features (erst Polish des Bestehenden)
