# Phase 24 – Report-Daten-Konsistenz

**Status:** 📋 Konzept (07.05.2026)
**Vorgänger:** Phase 23 (Time-windowed Stats) – ✅ abgeschlossen am 07.05.2026
**Nachfolger:** Phase 25 (Report-Layout-Refactor) – startet erst nach Phase 24
**Branch-Schema:** `feature/phase-24-X-kurzbeschreibung` pro Sub-Phase (Implementierungs-Branches werden in VSCode/Claude Code beim Start jeder Sub-Phase angelegt)

> **Hinweis:** `PROJECT_ROADMAP.md` ist veraltet (Stand 07.05.2026) und wird in einer separaten Aufgabe aktualisiert. Bis dahin ist dieses Dokument die alleinige Referenz für Phase 24.
>
> Konzept-Dokumente liegen ab jetzt unter `docs/concepts/`. Das ältere `docs/phase23_concept.md` wird vom User manuell hierher verschoben.

Dieses Dokument ist der Konzept-Fahrplan für Phase 24. Pro Sub-Phase werden Problem, Lösungsansatz, vermutete betroffene Dateien, Edge Cases, offene Fragen und Akzeptanzkriterien festgehalten. **Algorithmus-Skizzen und Testfälle werden bewusst NICHT im Voraus ausgearbeitet**, weil 24.4 (Audit) den Scope nachgelagerter Sub-Phasen verändern kann. Detail-Ausarbeitung erfolgt beim Start jeder Sub-Phase als Ergänzung in diesem Dokument.

---

## 1. Problemanalyse

### 1.1 Symptom

Der Mai-2026-Report (Zeitraum 07.04.–07.05.2026) hat trotz Phase-23-Abschluss noch folgende inhaltliche Probleme:

| Sektion im Report | Problem | Sub-Phase |
|---|---|---|
| Volumen-Diagnose | Sagt „Tonnage stabil" trotz KW17→KW18 -46 % Drop (Deload) | 24.1 |
| Push/Pull-Empfehlung | „Pull-betont (gut)" obwohl Pull-Muskeln im Übertraining-Status | 24.2 |
| Header-Zahlen | 53 Sessions / 757 Sätze passen nicht zum 30-Tage-Berichtszeitraum | 24.3 |
| Muskelgruppen-Verteilung | 5 Muskelgruppen haben exakt 9 Sätze (Verdacht: Default-Attribution) | 24.4 |
| Plateau-Status RDL | „Leichtes Plateau" trotz +26,5 kg/Monat Steigerungsrate | 24.5 |
| Kraftstandards | „0,4 %" bei Schwellen-knappem Status liest sich wie Stillstand | 24.6 |
| Trainer-Empfehlungen | Generisch, mischt Bewertungen mit Schritten | gestrichen → später |

### 1.2 Phase-23-Bilanz (was hat Phase 23 geliefert)

| Sub-Phase | Erwartung | Im Mai-Report sichtbar |
|---|---|---|
| 23.1 RPE 2w/4w/all | Drei Karten, 4w primär | ✅ greift |
| 23.2 Effektives Volumen + Diagnose | Zwei Linien, Diagnose-Tabelle | ⚠️ Linien da, Diagnose-Logik trägt Deload-Wochen nicht (→ 24.1) |
| 23.3 Plateau / Pause-Status | Pause-Status für inaktive Übungen | ⚠️ Pause greift, aber Plateau-Status entkoppelt nicht von Steigerungsrate (→ 24.5) |
| 23.4 Fatigue-Index 14d | Konsistente Zeitfenster | ✅ greift |
| 23.5 PDF-Hinweistext | Alte 40/30/30-Heuristik raus | ✅ greift |

Phase 23 hat die Zeitfenster-Konsistenz erfolgreich adressiert. Die jetzt verbliebenen Probleme sind anderer Natur: Daten-Quellen-Konflikte, Empfehlungs-Logik, Aggregations-Konventionen.

### 1.3 Ziel der Phase

Report-Daten so weit konsistent machen, dass das nachgelagerte Layout-Refactor (Phase 25) auf einer stabilen Datenbasis arbeitet. **Keine neuen Features, keine neuen Metriken** – nur Bereinigung, Korrektur und kontextabhängige Empfehlungslogik.

---

## 2. Architektur-Skizze (vermutet)

Vermutete Berührungspunkte (zu verifizieren beim Start jeder Sub-Phase):

- `core/views/training_stats.py` – Dashboard-Stats-Logik (existierend, robust gegen Deload, Plan-Wechsel, laufende Woche)
- `core/templates/core/training_pdf_simple.html` – PDF-Template
- `core/utils/advanced_stats.py` – Berechnungs-Helfer
- Übungs-Stammdaten-Modell und Set-Attribution (Detail in 24.4-Audit)

**Ein zentrales Muster soll etabliert werden:** Zeitfenster für Trends sind „letzte N Nicht-Deload-/Nicht-Plan-Wechsel-Wochen, ohne laufende Woche" statt „letzte N Kalenderwochen". Die Logik dafür existiert im Dashboard – die PDF muss sie übernehmen, nicht parallel implementieren.

**Implikation für Branches:** Da 24.4 ein Audit ist (kein Code-Change im Sinne von Logik-Änderung), bleibt offen, ob Phase 24 in einem gemeinsamen Branch (`feature/phase-24-data-consistency`) oder in pro-Sub-Phase-Branches umgesetzt wird. Empfehlung: Audit-Befund und seine Folge-Aktion getrennt von 24.1–24.6 behandeln, weil Audit ggf. zu einer eigenen Daten-Bereinigungs-Sub-Phase führen kann.

---

## 3. Tasks

### 3.1 Sub-Phase 24.4 – Set-Attribution-Audit

**Status:** ✅ Abgeschlossen (08.05.2026) · **Aufwand:** M (audit-only) · **Reihenfolge:** **zuerst**

**Ergebnis (08.05.2026):** Audit-Hypothese widerlegt. Die 5×9 Sätze sind kein Daten-Artefakt, sondern strikte Konsequenz der Plan-Struktur (3 Sätze × 1 Übung × 3 Trainings-Wochen pro Muskelgruppe). **Keine Folge-Sub-Phase nötig.** Vollständiger Befund inkl. sekundärer Beobachtung zu Hilfsmuskeln-Aggregation und Stammdaten-Inkonsistenz: [phase24-04-audit-bericht.md](phase24-04-audit-bericht.md).

**Konsequenzen für nachgelagerte Sub-Phasen:**

- 24.2 (Push/Pull) wird unblockiert – Edge-Case-Anmerkung *„Befund aus 24.4 kann Push/Pull-Sätze verschieben"* entfällt.
- 24.3 (Header) bestätigt: Header-Zahlen 53/757 ≈ Lifetime (Audit zeigte 54/773 zur Audit-Zeit), nicht 30-Tage.

#### Problem

Im Mai-Report zeigen fünf Muskelgruppen exakt 9 Sätze über 30 Tage:

- Schulter-Vordere (Deltoideus pars clavicularis)
- Schulter-Seitliche (Deltoideus pars acromialis)
- Oberschenkel Hinten (Hamstrings/Ischiocrurale)
- Hüftbeuger (Iliopsoas)
- Bauch (Abdominals)

Fünfmal exakt derselbe Wert ist mit hoher Wahrscheinlichkeit kein Zufall, sondern systemische Default-/Synergisten-Attribution oder Daten-Artefakt. Das verzerrt:

- Muskelgruppen-Übertraining/Untertraining-Diagnose
- Push/Pull-Ratio (Synergisten zählen mit)
- Trainer-Empfehlungen („Schulter-Vordere fokussieren" mit potenziell falscher Datengrundlage)

**User-Hinweis (07.05.2026):** *„anfang da hatte ich eher experimentiert"* – mögliches Indiz, dass die 9 Sätze aus alten experimentellen Sessions vor dem aktuellen Plan stammen.

#### Lösungsansatz

**Audit-only.** Kein Fix in dieser Sub-Phase. Drei Diagnose-Schritte:

1. **Welche Übung(en) erzeugen die 9 Sätze pro betroffener Muskelgruppe?** SQL-Query auf Production-DB (Zugriff in VSCode/Claude Code vorhanden), gefiltert auf den 30-Tage-Berichtszeitraum.
2. **Aus welchen Sessions stammen die Sätze?** Aktiver Plan vs. ad-hoc, Datum, ggf. experimenteller Charakter.
3. **Wie ist die Set-Attribution definiert?** DB-Tabelle pro Übung mit primären/sekundären Muskeln + Faktor, oder Code-Mapping?

#### Vermutete betroffene Dateien

- Übungs-Modell (vermutlich `core/models/uebung.py` oder ähnlich)
- Muskelgruppen-Mapping (Code oder DB)
- View-Logik für Muskelgruppen-Aggregation in `core/views/training_stats.py`

#### Ergebnis-Form

Audit-Bericht (als Anhang in diesem Konzept-Dokument oder als eigene Datei `docs/concepts/phase24-04-audit-bericht.md`) mit:

- Liste der Übung(en), die zu den 9 Sätzen führen, pro Muskelgruppe
- Datum/Plan-Zuordnung der relevanten Sessions
- Set-Attribution-Mechanismus (Datenmodell oder Code)
- Empfehlung für Fix-Strategie, mögliche Optionen:
  - (a) Daten-Bereinigung alter Sessions
  - (b) Code-Korrektur Aggregations-Logik
  - (c) Stammdaten-Anpassung Muskel-Faktoren
  - (d) Auswertungs-Filter „nur Sessions im aktiven Plan"

Auf Basis des Berichts werden Folge-Sub-Phasen geplant (eigene Phase 24.4b mit Fix, oder Integration in 24.2 wenn nur Push/Pull betroffen).

#### Edge Cases

- Wenn die 9 Sätze aus Sessions vor Plan-Aktivierung stammen → Auswertungs-Filter „aktiver Plan" wäre eine Option, müsste aber bei jeder Auswertung konsistent angewendet werden
- Wenn ein Synergisten-Faktor in Stammdaten fehlt → Daten-Issue, Migration nötig
- Wenn die fünf Werte tatsächlich legitim und zufällig gleich sind → unwahrscheinlich, dann Sub-Phase ohne Folge-Aktion abschließen

#### Offene Fragen

- F1: DB-Schema für Set-Attribution – welche Tabelle, welche Felder?
- F2: Existiert ein Auswertungs-Filter „nur aktiver Plan" bereits?
- F3: Sollen alte experimentelle Sessions in der Historie bleiben (für Lifetime-Statistiken) oder aus Auswertungen ausgeschlossen werden?

#### Akzeptanzkriterien

- Audit-Bericht im Konzept-Dokument oder als eigene Datei vorhanden
- Fix-Strategie für jede der fünf Muskelgruppen empfohlen (kann auch „keine Aktion nötig" sein, wenn Befund das ergibt)
- Folge-Sub-Phasen klar abgegrenzt – was wird wo gefixt, mit Aufwandsschätzung

---

### 3.2 Sub-Phase 24.1 – Deload, Plan-Wechsel & laufende Woche aus PDF-Trends ausnehmen

**Status:** ✅ Abgeschlossen (09.05.2026) · **Aufwand:** S–M · **Reihenfolge:** nach 24.4

**Ergebnis (09.05.2026):** PDF-Volumen-Diagnose vergleicht jetzt die letzten zwei vergleichbaren Wochen (nicht laufend, nicht Deload-Mehrheit, nicht Plan-Wechsel). Plan-Wechsel werden über die Plan-IDs-Sets aufeinanderfolgender Wochen erkannt. Bei zu wenigen vergleichbaren Wochen erscheint statt einer irreführenden Trend-Aussage *„Trend-Bewertung pausiert"*. Helper-Refactor (`_aggregate_weekly_volume`, `_classify_weeks_from_sessions`, `_fill_iso_week_range`, `_build_week_diagnose`) hält die Hauptfunktion unter der Komplexitäts-Schwelle. Verifiziert gegen Production-Daten von Lera (09.05.2026): vergleichbare Wochen `KW08/09/11/12/13/16/17`, neue Diagnose vergleicht `KW16→KW17` (+6,6 %), alte Logik hatte fälschlich `KW18 (Deload) → KW19 (laufend)` verglichen.

**Antworten auf F4–F6:**

- F4: Logik liegt jetzt in `core/export/stats_collector.py` (kein eigener Helper-Modul – die Filterung lebt lokal in vier kleinen Helpern derselben Datei).
- F5: Trend-Fenster bleibt bei „letzte zwei vergleichbaren Wochen". Eine Erweiterung auf 6 Wochen wurde verworfen, weil die Diagnose konzeptionell „Vorwoche vs. aktuelle abgeschlossene Woche" misst; bei zu dünner Datenlage greift jetzt der Pause-Hinweis.
- F6: Plan-Wechsel-Visualisierung im Chart wurde nicht angefasst – gehört zu Phase 25 (Layout). Aktuell nur als Diagnose-Label sichtbar.

#### Problem

PDF-Volumen-Diagnose sagt: *„Keine eindeutige Diagnose · Tonnage stabil · Effektives Volumen steigt"* – obwohl KW17 (23.157 kg) → KW18 (12.616 kg) ein Drop von -46 % ist. Ursache: KW18 ist Deload-Woche, KW19 ist die laufende Woche. Beide werden in der PDF-Trend-Berechnung wie normale Wochen behandelt.

Das Dashboard hat dieses Problem bereits gelöst – im Volumen-Chart sind Deload-Tage gelb markiert, die Volumen-Analyse-Box weist Plan-Wechsel-Wochen explizit aus (*„Volumen-Änderung durch Trainingsplan-Wechsel – kein Warnsignal"*), die laufende Woche wird mit *„Diese Woche ist noch nicht abgeschlossen – keine Bewertung möglich"* gekennzeichnet.

#### Lösungsansatz

**Bestehende Dashboard-Logik in PDF-Pipeline portieren.** Konkret:

1. Identifikation der existierenden Logik im Dashboard (vermutlich in `core/views/training_stats.py` oder `core/utils/advanced_stats.py`).
2. Anwendung derselben Filter-Logik auf:
   - PDF-Volumen-Chart (Deload-Punkte gelb wie im Dashboard, oder zumindest visuelle Markierung)
   - PDF-Volumen-Diagnose-Tabelle (aus Phase 23.2)
   - Ggf. Plateau-Berechnung (überlappt mit 24.5)
3. Visuelles Feedback im PDF-Chart so, dass Deload- und Plan-Wechsel-Wochen sichtbar bleiben (nicht ausgeblendet), aber **Trend nur über Nicht-Deload-/Nicht-Plan-Wechsel-/Nicht-laufende-Wochen** berechnet wird.

#### Wochen-Klassifikation

Klärung mit User (07.05.2026):

- **Deload-Woche:** Pläne werden vollständig durchgezogen; eine Woche, in der Trainingstage als Deload markiert sind, ist eine Deload-Woche. Wochen-Identifikation läuft über den ersten Trainingstag der Wochenplan-Iteration.
- **Plan-Wechsel-Woche:** Erste Woche eines neuen Plans. Tonnage kann sich strukturell ändern (z.B. Wechsel von Hantel-fokussiert zu Körpergewicht + Zusatzgewicht).
- **Laufende Woche:** Aktuelle Kalenderwoche bezogen auf Report-Erstellungs­datum. Wird nicht für Bewertungen herangezogen.

#### Vermutete betroffene Dateien

- `core/views/training_stats.py` (Dashboard-Logik vorhanden)
- `core/templates/core/training_pdf_simple.html` (Diagnose-Output)
- `core/utils/advanced_stats.py` (Volumen-Berechnung)

#### Edge Cases

- **Trend-Fenster zu klein:** Bei einem 3+1-Cycle und Ausschluss laufender Woche bleiben pro Cycle nur 2 vergleichbare Trainings-Wochen. Aktuelles 4-Kalenderwochen-Fenster könnte auf 1–2 Datenpunkte schrumpfen → Trend-Fenster sollte auf „letzte N Nicht-Deload-Wochen" gleitend umgestellt werden (Vorschlag: N=6).
- **Cycle-Übergang innerhalb einer KW:** unwahrscheinlich nach User-Aussage (Pläne laufen vollständig durch), aber prüfen, dass die Klassifikations-Konvention mit dem Dashboard übereinstimmt.
- **Nutzer ohne Plan:** alle Wochen sind „kein Plan-Bezug", Plan-Wechsel-Klassifikation entfällt – Fall handhaben.

#### Offene Fragen

- F4: Wo exakt sitzt die Dashboard-Logik (Klassifikation Deload / Plan-Wechsel / laufende Woche)?
- F5: Trend-Fenster auf „letzte 6 Nicht-Deload-Wochen" umstellen, oder fix bei „letzte 4 Kalenderwochen mit Filterung"?
- F6: Visualisierung Plan-Wechsel im PDF-Chart – eigene Farbe oder gleiche Konvention wie Deload?

#### Akzeptanzkriterien

- PDF-Volumen-Diagnose berücksichtigt Deload, Plan-Wechsel, laufende Woche
- Diagnose-Text zeigt nicht mehr „stabil" bei -46 % Drop in einer Deload-Woche
- Tests decken die drei Wochen-Klassifikationen ab (Deload / Plan-Wechsel / laufend) und ihre Kombinationen

---

### 3.3 Sub-Phase 24.2 – Push/Pull-Empfehlung kontextabhängig

**Status:** ✅ Abgeschlossen (09.05.2026) · **Aufwand:** S · **Reihenfolge:** nach 24.1
**Abhängigkeit:** Durch 24.4-Befund unblockiert (Set-Attribution kein Bug)

**Ergebnis (09.05.2026):** `collect_push_pull` konsultiert jetzt den Übertraining-Status der Push-/Pull-Muskeln aus `muskelgruppen_stats` und konditioniert die Empfehlung darauf. Die mathematische Ratio-Bewertung bleibt unverändert; der Empfehlungstext kippt, sobald die Seite, die der Math-Verdict loben oder aufstocken will, bereits Muskeln im Übertraining-Bereich enthält. Neue Output-Felder `push_overtrained`, `pull_overtrained`, `context_override` (für eine spätere Status-Tabelle in Phase 25; in 24.2 noch nicht gerendert). Verifiziert gegen Lera-Production-Daten (09.05.2026, ratio 1.0): alte Logik sagte *„Perfekt!"* trotz BRUST und RUECKEN_LAT im Übertraining; neue Logik gibt *„Push/Pull mengenmäßig ausgeglichen, aber Push: Brust im Übertraining-Bereich und Pull: Rücken-Lat im Übertraining-Bereich. Volumen pro Muskelgruppe einzeln prüfen."*

**Antworten auf F7–F8:**

- F7: Push/Pull-Mapping liegt in `core/export/constants.py` (`PUSH_GROUPS`, `PULL_GROUPS`). Bestehende Konstanten unverändert übernommen.
- F8: Status-Tabelle bewusst nicht in 24.2 – die strukturierten Felder (`push_overtrained`, `pull_overtrained`, `context_override`) sind aber schon im Result-Dict, damit Phase 25 ohne weitere Code-Änderung darauf zugreifen kann.

#### Problem

Aktueller Report: *„Pull-betont (gut). Ratio 0,75:1 — positiv für Schultergesundheit und Haltung."*

Drei Sektionen weiter zeigt die Muskelgruppen-Analyse:
- Rücken-Lat: 28 Sätze, mögliches Übertraining
- Schulter-Hintere: 24 Sätze, mögliches Übertraining

Pull-Muskeln werden als übertrainiert markiert und gleichzeitig als „mehr davon ist gut" gelobt. Die zwei Sektionen sprechen offensichtlich nicht miteinander.

#### Lösungsansatz

Empfehlungstext-Generierung in zwei Stufen:

1. **Mathematische Bewertung der Ratio bleibt:** Push-betont / ausgewogen / Pull-betont nach Set-Verhältnis.
2. **Empfehlungstext wird auf den Übertraining-Flag-Status der beteiligten Muskeln konditioniert:**
   - Wenn ein oder mehrere Pull-Muskeln im Status „möglich Übertraining": Empfehlung dreht. Beispiel: *„Pull-betont – Pull-Volumen bereits hoch (Rücken, hintere Schulter im Übertraining-Bereich). Push ergänzen statt Pull weiter aufbauen."*
   - Wenn alle Pull-Muskeln im Status „Optimal" oder „Untertrainiert": bestehender Text bleibt.
   - Symmetrisch für Push.

#### Optional: Status-Tabelle in der Sektion

Eine kompakte Tabelle in der Push/Pull-Sektion, die zeigt, welche Push- und Pull-Muskeln aktuell welchen Status haben. Macht die Empfehlung im Kontext lesbar, statt dass der Leser zwischen zwei Sektionen springen muss. **Entscheidung über Aufnahme:** Wenn Status-Tabelle, dann erst in Phase 25 (Layout) – in 24.2 nur Logik.

#### Vermutete betroffene Dateien

- Push/Pull-Berechnung (Code finden – vermutlich in `core/utils/advanced_stats.py`)
- PDF-Template Push/Pull-Sektion

#### Edge Cases

- **Mixed Status:** Ein Pull-Muskel übertrainiert, ein anderer untertrainiert → Empfehlung muss differenzieren statt pauschal
- **Ratio extrem (z.B. 1:5 Pull-betont mit allen Pull-Muskeln OK):** Mathematische Empfehlung „Push fehlt strukturell" sollte Vorrang vor Status-basierter Empfehlung haben
- **Befund aus 24.4:** Wenn Set-Attribution-Audit zeigt, dass Synergisten falsch attribuiert sind, ändern sich die Schulter-Hintere-Werte und damit die Empfehlung. Tests in 24.2 erst nach 24.4-Befund finalisieren.

#### Offene Fragen

- F7: Push/Pull-Muskel-Mapping – wo definiert (Code oder DB)?
- F8: Status-Tabelle in dieser Sektion sinnvoll oder ablenkend? Entscheidung verschieben auf Phase 25.

#### Akzeptanzkriterien

- Empfehlungstext widerspricht nicht der Muskelgruppen-Diagnose
- Tests decken alle Kombinationen (Ratio × Übertraining-Status auf Push-Seite × auf Pull-Seite) ab

---

### 3.4 Sub-Phase 24.5 – Plateau-Status vs. Steigerungsrate entkoppeln

**Status:** ✅ Abgeschlossen (10.05.2026) · **Aufwand:** S · **Reihenfolge:** nach 24.2

**Ergebnis (10.05.2026):** `classify_progression_status` bekommt einen neuen Override: bei langer Trainingshistorie (≥ 21 Tage) und einer relativen Steigerungsrate ≥ 2 % des PR-1RM pro Monat wird der Status auf `active_progression_paused` (Label *„📈 Aktive Progression (PR-Pause)"*) gesetzt – statt auf eine der drei Plateau-Stufen. Reihenfolge: nach `regression`/`active_progression`/`observe`/`pause`/`consolidation` und vor der reinen Tage-seit-PR-Logik. Konsolidierung (RPE sinkt) hat damit weiterhin Vorrang. Verifiziert gegen Lera-Production-Daten (10.05.2026): RDL kippt von `plateau_light` auf `active_progression_paused` (22.3 %/Monat); Trizeps Overhead Extension von `plateau` auf `active_progression_paused` (34.9 %/Monat); inaktive Übungen bleiben unverändert auf `pause`.

**Antworten auf F9–F10:**

- F9: Empirisch festgelegt mit relativem Schwellenwert `PROGRESSION_RATE_OVERRIDE_PCT = 2.0` (% des PR-1RM pro Monat). Gegen 1 %/Monat-Mikroprogression noch hinreichend strikt; gegen den RDL-Fall (22 %/Monat) eindeutig auf der Override-Seite. Median-basierter Vergleich verworfen, weil das einen zweiten Pass über alle Übungen erzwingen würde – die relative Schwelle ist ohne diesen Aufwand robust gegen Übungsstärke.
- F10: Konsolidierungs-Status bleibt als eigene Stufe mit Vorrang vor dem Override – Phase 23.3-Setup unverändert.

**Plan-Wechsel-Edge-Case:** im Konzept als „ggf." formuliert und in 24.5 nicht implementiert. Wenn relevant, kann das in einer Folge-Sub-Phase analog zur 24.1-Plan-Epoch-Logik nachgereicht werden.

**Reviewer-Nachzug (10.05.2026, PR #165):** Der Live-Plateau-Tracker `_calc_plateau_live` in `core/views/training_stats.py` rief `classify_progression_status` zunächst weiterhin ohne die neuen kwargs auf, sodass Dashboard und PDF auseinandergelaufen wären. Der gemeinsame Helper `compute_progression_rate` in `core/utils/advanced_stats.py` wird jetzt von beiden Pfaden verwendet; die Klassifikation ist wieder identisch.

#### Problem

RDL hat im Mai-Report den Status *„Leichtes Plateau (21 Tage ohne PR)"* UND gleichzeitig die Steigerungsrate *„Ø +26,5 kg/Monat"*. 26,5 kg/Monat als Plateau zu labeln ist kontraproduktiv und widersprüchlich. Phase 23.3 hat den Pause-Status korrekt eingeführt, aber der „Plateau"-Status hängt noch ausschließlich am Letzter-PR-Datum und ignoriert den langfristigen Steigerungstrend.

#### Lösungsansatz

Plateau-Status um Steigerungsraten-Komponente erweitern:

- Wenn `Tage seit letztem PR > Schwelle` UND `Steigerungsrate < X kg/Monat` → echtes Plateau
- Wenn `Tage seit letztem PR > Schwelle` UND `Steigerungsrate ≥ X kg/Monat` → neuer Status, z.B. „Aktive Progression mit kurzer Pause" o.ä.

Konkrete Schwellenwerte (X) werden beim Implementierungs-Start empirisch festgelegt – Vorschlag: Steigerungsrate-Median über alle Übungen des Users als Referenz, ggf. übungs­spezifisch normiert.

#### Vermutete betroffene Dateien

- Plateau-Berechnung in `core/utils/advanced_stats.py`
- Plateau-Tabelle in PDF-Template

#### Edge Cases

- **Übung mit nur 2–3 Datenpunkten:** Steigerungsrate stark verrauscht, Logik konservativ halten (im Zweifel kein „Plateau"-Label, weil Datenbasis zu dünn)
- **Übungswechsel innerhalb eines Plans** (z.B. von KH-Bankdrücken zu LH-Bankdrücken): Steigerungsrate über Wechsel hinaus berechnen oder bei Wechsel zurücksetzen?
- **Plan-Wechsel:** Wie 24.1 – ggf. Plateau-Diagnose bei Plan-Wechsel pausieren

#### Offene Fragen

- F9: Schwelle für Steigerungsrate – wissenschaftlich begründet (gibt es Normwerte?) oder empirisch (Median des Users)?
- F10: Soll der bestehende „Konsolidierung (RPE sinkt)"-Status von Phase 23.3 bleiben, oder wird er durch die neue Logik subsumiert?

#### Akzeptanzkriterien

- RDL-Fall (+26,5 kg/Monat, 21 Tage ohne PR) zeigt nicht mehr „Plateau"
- Hammer-Curls-Fall (Konsolidierung mit RPE-Sinken) bleibt korrekt klassifiziert
- Tests decken alle Status-Übergänge ab

---

### 3.5 Sub-Phase 24.3 – Header-Zahlen / Zeitraum-Konsistenz

**Status:** ✅ Abgeschlossen (10.05.2026) · **Aufwand:** S · **Reihenfolge:** nach 24.5

**Ergebnis (10.05.2026):** Umsetzung wie im Konzept (Option 2) empfohlen – pluralistische Zeiträume mit expliziter Beschriftung. `collect_pdf_stats` führt jetzt `trainingsbeginn_datum` mit (ältestes Trainingsdatum des Users) und die bereits existierenden `*_30_tage`-Felder werden im PDF-Template als Primärwerte angezeigt, die Lifetime-Werte als sekundäres Kontext-Suffix („insgesamt X seit DD.MM.YYYY"). Wenn Lifetime ≈ Berichtszeitraum (neuer User), wird nur das Fenster gezeigt. Verifiziert gegen Lera-Daten (10.05.2026): alte Anzeige zeigte 54 / 773, neue zeigt *„Trainingseinheiten: 12 (insgesamt 54 seit 03.01.2026), Sätze: 156 (insgesamt 773)"*.

**Antworten auf F11–F12:**

- F11: Berichtszeitraum-Werte: Header-Trainingseinheiten, Sätze, Volumen, RPE-Verteilung, Muskelgruppen-Verteilung, Push/Pull. Lifetime-Werte mit explizitem Suffix: Header-Lifetime-Spalte (NEU), Streak, Top-Fortschritte über mehrere Monate, Verlauf-Chart Körperentwicklung. Letztere sind bereits Lifetime und werden visuell als Verlauf erkannt – keine separate Anpassung in 24.3 nötig, ausser den Header-Block.
- F12: Konfigurierbarer Berichtszeitraum bewusst nicht in 24.3 – Scope wäre größer. Wenn die Anforderung kommt, ist das eine Folge-Phase.

#### Problem

Header sagt *„Berichtszeitraum 07.04.2026 – 07.05.2026"* (30 Tage). Executive Summary direkt darunter zeigt **53 Trainingseinheiten, 757 Sätze, 337.220 kg Volumen**. 53 Sessions in 30 Tagen = 1,77/Tag – unrealistisch für den deklarierten Zeitraum.

Auch: Verlauf-Chart der Körperentwicklung zeigt Datenpunkte ab 02.01.2026, nicht ab 07.04.2026. Streak-Anzeigen (19 Wochen) reichen ebenfalls weit über den Berichtszeitraum hinaus.

Vermutung: Werte stammen aus All-Time oder einem anderen impliziten Zeitraum als der Header deklariert.

#### Lösungsansatz

Drei Optionen:

1. **Strikte Konsistenz:** Alle Zahlen und Charts auf den deklarierten 30-Tage-Zeitraum filtern. Verlauf-Chart der Körperentwicklung wird kürzer, Streak verschwindet ggf.
2. **Pluralistische Zeiträume (empfohlen):** Pro Sektion expliziten Zeitraum angeben. Beispiele:
   - *„Trainingseinheiten gesamt: 53 (seit Trainingsbeginn XX.YY.YYYY)"*
   - *„Volumen letzte 30 Tage: …"*
   - Header bleibt deklarativ für die Hauptauswertung, die Lifetime-Werte werden mit Datum gelabelt.
3. **Mehrere Header:** Berichtszeitraum + Plan-Zeitraum + Lifetime nebeneinander. Risiko: Visuelle Überfrachtung.

**Empfehlung: Option 2.** Strikte Filterung verliert Lifetime-Kontext, der bei Streak und Lifetime-Volumen wertvoll ist. Pluralistische Zeiträume mit expliziter Beschriftung sind sauber und erhalten Information.

#### Vermutete betroffene Dateien

- PDF-Generation Berichts-Header
- Executive Summary-Block in `core/templates/core/training_pdf_simple.html`
- Datenaggregations-Stelle für die Header-Zahlen (Code finden)

#### Edge Cases

- **User mit weniger als 30 Tagen Trainings-Historie:** Lifetime ≈ Berichtszeitraum, beide Werte anzuzeigen ist redundant aber nicht falsch – Lifetime-Label dann ggf. weglassen
- **Wechsel des Berichtszeitraums** (falls in Zukunft konfigurierbar): jede Sektion muss konsistent reagieren

#### Offene Fragen

- F11: Welche Sektionen brauchen Lifetime-Kontext (Streak, Top-Fortschritte über mehrere Monate), welche reine Berichtszeitraum-Werte (Volumen, RPE)?
- F12: Soll der Berichtszeitraum konfigurierbar werden (User wählt 30/60/90 Tage), oder bleibt er bei fixen 30 Tagen?

#### Akzeptanzkriterien

- Jede Sektion hat einen erkennbar deklarierten Zeitraum
- Header-Zahlen sind im Report intern konsistent oder explizit als „seit Trainingsbeginn" / „letzte 30 Tage" gelabelt

---

### 3.6 Sub-Phase 24.6 – Kraftstandards-Anzeige bei Schwellen-Übergängen

**Status:** ✅ Abgeschlossen (10.05.2026) · **Aufwand:** S · **Reihenfolge:** zuletzt

**Ergebnis (10.05.2026):** `calculate_1rm_standards` setzt jetzt zwei zusätzliche Flags pro Übung in `standard_info`: `gerade_erreicht` (True, wenn der Korridor-Fortschritt unter 5 % liegt – die Schwelle wurde gerade überschritten) und `ist_endstufe` (True bei Elite). Das PDF-Template rendert in beiden Fällen statt der missverständlichen ProgressBar einen positiven Text: *„✓ Anfänger gerade erreicht. Nächstes Ziel: Fortgeschritten – noch 36,5 kg."* bzw. *„✓ Endstufe Elite erreicht."* Verifiziert gegen Lera (10.05.2026): Mai-Bug-Konstellation (Kniebeuge 73,3 kg knapp über 73,2 kg) ist organisch gewichen (Kniebeuge inzwischen 80 kg), keine Übung hat heute `gerade_erreicht=True` – alle bestehenden Anzeigen bleiben unverändert. Code-Fix bleibt für künftige knappe Schwellen-Überschritte relevant; Unit-Tests reproduzieren genau diesen Fall.

**Antworten auf F13–F14:**

- F13: Schwellenwerte werden pro Übung in der DB gepflegt (`Uebung.standard_beginner/intermediate/advanced/elite`) – nicht im UI konfigurierbar, aber DB-änderbar. Aktuelles Verhalten bleibt.
- F14: Zwischenstufen bewusst nicht eingeführt – Konzept-Vorgabe ist „klare Aussage > Granularität". Vier Hauptstufen (Anfänger / Fortgeschritten / Erfahren / Elite) bleiben.

#### Problem

Kniebeuge im Mai-Report: 1RM 73,3 kg, Anfänger-Schwelle 73,2 kg, Anzeige *„Noch 36,5 kg bis Fortgeschritten – 0,4 %"*. Die 0,4 % beziehen sich auf den Fortschritt im Anfänger→Fortgeschritten-Korridor (also: gerade über der Schwelle), liest sich aber wie Stillstand. Demotivierend für einen User, der die Schwelle gerade erreicht hat.

#### Lösungsansatz

Prozent-Anzeige durch zwei klare Aussagen ersetzen:

```
Status: Anfänger ✓ erreicht
Nächstes Ziel: Fortgeschritten (109,8 kg) — noch 36,5 kg
```

Optional als Stufen-Visualisierung: Erreichte Stufe markiert, Distanz zur nächsten als Balken ohne missverständliche Prozentzahl.

#### Vermutete betroffene Dateien

- 1RM-Sektion im PDF-Template
- Ggf. Berechnungslogik für Stufen-Status

#### Edge Cases

- **1RM unterhalb Anfänger-Schwelle:** eigener Status „Aufbau" oder „Noch nicht im System"
- **1RM über Elite:** keine Distanzangabe nötig, „Elite" als Endstufe
- **Schwellenwerte sehr nah beieinander** (z.B. 73,2 vs 73,3): bestätigender Hinweis „knapp erreicht – mit nächstem PR sicher in der Stufe"

#### Offene Fragen

- F13: Sind die Schwellenwerte konfigurierbar oder fix?
- F14: Sollen Zwischenstufen sichtbar sein („mittlerer Anfänger", „oberer Anfänger") oder nur die Hauptstufen?

#### Akzeptanzkriterien

- Keine missverständliche Prozent-Anzeige mehr
- User-Feedback (Lera): Lesart bei knapp erreichten Stufen nicht mehr demotivierend

---

### 3.7 ~~Sub-Phase 24.7 – Trainer-Empfehlungen~~

**Status:** ❌ Gestrichen (User-Entscheidung 07.05.2026)

**Begründung:** Aktuelle Empfehlungslogik mischt Bewertungen mit Schritten und ist generisch (z.B. Standard-Tipp *„Steigere Trainingsgewichte 2,5–5 % pro Woche"* ignoriert die in derselben Datei gerade ausgewiesenen Plateau-Diagnosen). User-Aussage: *„aufwand höher es zu reparieren als später sauber neu rein mit besseren ideen"*. Wird in einer späteren Phase neu angesetzt.

---

## 4. Reihenfolge & Begründung

```
24.4 (Audit) → 24.1 (Deload) → 24.2 (Push/Pull) → 24.5 (Plateau) → 24.3 (Header) → 24.6 (Kraftstandards)
```

- **24.4 zuerst:** Audit-Befund kann Set-Attribution korrigieren und damit die Sätze-pro-Muskelgruppe verschieben. Push/Pull-Empfehlung (24.2) und Muskelgruppen-Übertraining-Flags hängen direkt an diesen Werten. Wenn Push/Pull vor 24.4 implementiert wird, müssen Tests und Schwellen ggf. zweimal angepasst werden.
- **24.1 als zweites:** Größte sichtbare Verzerrung im Report (Tonnage-Diagnose). Bestehende Dashboard-Logik vorhanden – kleinerer Aufwand (Port statt Neubau). Mittlere Aufwandsschätzung berücksichtigt Test-Coverage über drei Wochen-Klassifikationen.
- **24.2 nach 24.4 + 24.1:** Übertraining-Flags brauchen sowohl korrekte Set-Attribution (24.4) als auch korrekte Volumen-Diagnose (24.1) als Kontext. Erst dann macht die kontextabhängige Empfehlungslogik Sinn.
- **24.5, 24.3, 24.6:** Untereinander unabhängig, lassen sich in beliebiger Reihenfolge nach 24.2 erledigen. Vorgeschlagene Reihenfolge folgt absteigender User-Sichtbarkeit.

**Hinweis zur Branch-Strategie:** Da Phase 24 mehrere Sub-Phasen mit unterschiedlichem Charakter umfasst (Audit, Logik-Änderungen, kosmetische Anpassungen), ist eine pro-Sub-Phase-Branch-Strategie sinnvoller als ein Sammel-Branch. Memory-Hinweis aus dem Projekt – Feature-Branches bleiben offen bis alle Sub-Steps fertig sind, weil Merge auf main einen Production-Deploy triggert – gilt aber pro Sub-Phase.

---

## 5. Cross-Cutting Concerns

### 5.1 Plan-Wechsel-Markierung als wiederverwendbarer Helper

Die Dashboard-Logik (Volumen-Analyse-Box: *„Volumen-Änderung durch Trainingsplan-Wechsel – kein Warnsignal"*) ist nicht nur für 24.1 (Volumen-Diagnose) relevant, sondern auch für:

- **Plateau-Analyse (24.5):** Plan-Wechsel kann eine Übung pausieren – das ist nicht Plateau, sondern Plan-Entscheidung
- **Kraftentwicklung Top 5** (Trainingsfortschritt-Sektion): Zeigt heute schon Plan-Bezug („im aktuellen Plan"), aber nicht alle Charts machen das
- **Übungsdetails-Charts (Gewichtsverlauf):** Plan-Wechsel als vertikale Marker-Linie sinnvoll

**Konsequenz:** Bei 24.1 die Plan-Wechsel-Erkennung als wiederverwendbaren Helper isolieren, nicht inline. Spätere Sub-Phasen (24.5, ggf. Phase 25) nutzen denselben Helper.

### 5.2 Dashboard ↔ PDF Konsistenz

Das Dashboard ist offenbar an mehreren Stellen weiter als die PDF (Volumen-Analyse, Deload-Markierung, Laufende-Woche-Hinweis). Wo immer möglich, soll die PDF die Dashboard-Logik wiederverwenden, nicht parallele Implementierungen aufbauen.

**Konsequenz:** Bei jeder Sub-Phase prüfen, ob im Dashboard bereits eine korrekte Logik existiert, bevor im PDF-Pfad neu implementiert wird.

### 5.3 BIA-Werte (Lera-spezifisch, nicht Teil von Phase 24)

Die Körperentwicklungs-Tabelle zeigt KFA, Muskelmasse, BMR aus BIA-Sensor – für den konkreten Nutzer (gastrischer Bypass) bekannt unzuverlässig. **Bewusst nicht Teil von Phase 24** (User-spezifischer Edge Case, kein generischer Produktfehler).

Falls ein generischer „Datenqualität-Hinweis" für BIA-Werte sinnvoll wäre (z.B. Plausibilitätsprüfung bei großen Sprüngen ohne Gewichts-Änderung), separat in Phase 25 oder später diskutieren.

---

## 6. Schnittstelle zu Phase 25 (Layout-Refactor)

Phase 25 startet erst nach Abschluss von Phase 24. Layout-Themen, die schon jetzt aufgefallen sind und in Phase 25 aufgegriffen werden sollten:

- **Pagebreaks:** Push/Pull-Header auf Seite 6, Inhalt auf Seite 7
- **Sektion-Reihenfolge:** Trainingsvolumen-Entwicklung gehört thematisch zu Trainingsfortschritt, nicht zu Push/Pull
- **Doppelte Sichten:** Top 5, Plateau-Analyse und Übungsdetails zeigen denselben Datensatz dreifach – Hierarchie schaffen oder entdoppeln
- **Charts mit überlappenden Datums-Achsen:** Verlauf-Chart, Hammer-Curls-Chart
- **Inhaltsverzeichnis:** Aktuell ohne Verlinkung
- **■-Symbol-Boxen:** Wirken wie Encoding-Reste, durch echte Design-Elemente ersetzen
- **BMR/FFMI/Wasser-Spalten in Verlauf-Tabelle:** Viel Platz für die unzuverlässigsten Werte (für allgemeinen Nutzer akzeptabel, aber Spalten-Priorisierung überdenken)
- **Push/Pull-Status-Tabelle:** Falls in 24.2 als optional aufgeführt, hier umsetzen

**Während Phase 24 keine neuen Layout-Issues sammeln** – nur was bei Implementierung auffällt, zur Phase-25-Liste hinzufügen.

---

## 7. Offene Punkte (Phase-übergreifend, ausserhalb Phase 24)

- **PROJECT_ROADMAP.md ist veraltet:** Aktualisierung als eigene Aufgabe nach Phase 24 oder 25
- **`docs/phase23_concept.md` Verschiebung:** User verschiebt manuell nach `docs/concepts/`
- **Trainer-Empfehlungen-Neuaufbau** (gestrichen aus 24.7): Eigene Phase nach Phase 25, mit besseren Ideen

---

## 8. Status-Updates pro Sub-Phase

### 24.1 – Deload, Plan-Wechsel & laufende Woche aus PDF-Trends ausnehmen

- **Start:** 09.05.2026 (Branch `feature/phase-24-1-deload-plan-current-week`)
- **Abschluss:** 09.05.2026
- **Ergebnis:** Diagnose vergleicht nur noch *vergleichbare* Wochen, mit explizitem Pause-Hinweis bei dünner Datenlage. Verifiziert gegen Lera-Production-Daten – Mai-Bug („Tonnage stabil" trotz Deload→laufend) ist nicht mehr reproduzierbar. Tests in `core/tests/test_stats_collector.py::TestCollectWeeklyVolumePdfDiagnose` decken die drei Klassifikationen + Kombinationen ab.

### 24.2 – Push/Pull-Empfehlung kontextabhängig

- **Start:** 09.05.2026 (Branch `feature/phase-24-2-push-pull-context-aware`)
- **Abschluss:** 09.05.2026
- **Ergebnis:** `collect_push_pull` konditioniert die Empfehlung jetzt auf den Übertraining-Status der Push-/Pull-Muskeln. Die mathematische Ratio-Bewertung bleibt; der Text kippt, sobald die zu lobende oder aufzustockende Seite Muskeln im Übertraining-Bereich enthält. Neue Felder `push_overtrained`, `pull_overtrained`, `context_override` für spätere Status-Tabelle (Phase 25). Verifiziert gegen Lera-Daten (09.05.2026): alte Logik sagte „Perfekt!" trotz BRUST + RUECKEN_LAT im Übertraining; neue Logik benennt beide Muskeln und empfiehlt Volumen-Prüfung pro Gruppe. Tests in `core/tests/test_stats_collector.py::TestCollectPushPullContextAware` decken alle Bewertungs-x-Status-Kombinationen ab.

### 24.5 – Plateau-Status vs. Steigerungsrate entkoppeln

- **Start:** 10.05.2026 (Branch `feature/phase-24-5-plateau-vs-progression`)
- **Abschluss:** 10.05.2026
- **Ergebnis:** `classify_progression_status` erkennt langfristig steigende Übungen jetzt als `active_progression_paused`, statt sie wegen ein paar Tagen ohne neuen PR fälschlich als Plateau zu labeln. Schwelle: ≥ 2 % des PR-1RM/Monat bei ≥ 21 Tagen Trainingshistorie. Konsolidierung (RPE sinkt) behält Vorrang. Verifiziert gegen Lera-Daten (10.05.2026): RDL → `active_progression_paused` (22.3 %/Monat statt `plateau_light`); Trizeps Overhead Extension → `active_progression_paused` (34.9 %/Monat statt `plateau`); inaktive Übungen bleiben korrekt auf `pause`. PDF-Template um Begründungs-Hinweis und Legende ergänzt. Tests in `core/tests/test_advanced_stats.py::TestPlateauAnalysis` decken RDL-Fall, echtes Plateau, Konsolidierungs-Vorrang, kurze Historie und Override-bei-mittlerem-Plateau ab.

### 24.3 – Header-Zahlen / Zeitraum-Konsistenz

- **Start:** 10.05.2026 (Branch `feature/phase-24-3-period-labels`)
- **Abschluss:** 10.05.2026
- **Ergebnis:** Executive Summary zeigt jetzt die Berichtszeitraum-Werte als Primärzahlen mit Lifetime-Kontext als sekundäres Suffix („insgesamt X seit DD.MM.YYYY"). Neues Feld `trainingsbeginn_datum` aus dem ältesten Trainingsdatum. Wenn Lifetime ≈ 30-Tage-Fenster (neuer User), wird nur das Fenster ohne Suffix angezeigt. Verifiziert gegen Lera (10.05.2026): alte Anzeige 54 / 773 → neue Anzeige *„Trainingseinheiten: 12 (insgesamt 54 seit 03.01.2026), Sätze: 156 (insgesamt 773)"*. Datenqualitäts-Hinweis (`< 8 Trainings`) bleibt auf Lifetime und wurde mit „insgesamt" verdeutlicht.

### 24.6 – Kraftstandards-Anzeige bei Schwellen-Übergängen

- **Start:** 10.05.2026 (Branch `feature/phase-24-6-kraftstandards-clear-display`)
- **Abschluss:** 10.05.2026
- **Ergebnis:** `calculate_1rm_standards` exponiert `gerade_erreicht` (Korridor-Progress < 5 %) und `ist_endstufe` (Elite). Das PDF-Template ersetzt die ProgressBar in beiden Fällen durch einen klaren Status-Text statt einer fast leeren Bar (z. B. *„✓ Anfänger gerade erreicht. Nächstes Ziel: Fortgeschritten – noch 36,5 kg."*). Verifiziert gegen Lera (10.05.2026): Mai-Bug-Konstellation organisch gewichen, keine Übung aktuell `gerade_erreicht=True`; Anzeigen für nicht-knappe Fälle bleiben unverändert. Tests in `core/tests/test_advanced_stats.py::TestOneRmStandards` reproduzieren den Mai-Bug + drei weitere Schwellen-Fälle.

### 24.1a – Streak-Regression fixen (Folge-Sub-Phase aus Section 9.2 B1)

- **Start:** 11.05.2026 (Branch `feature/phase-24-1a-streak-fix`)
- **Abschluss:** 11.05.2026
- **Ergebnis:** Aktueller Streak zählt jetzt bis zur letzten *abgeschlossenen* Trainings-Woche; die laufende Kalenderwoche ist neutral und bricht den Streak nicht mehr, wenn sie noch leer ist. Fix in beiden Pfaden (Dashboard & PDF) parallel implementiert: `core/utils/advanced_stats.py::calculate_consistency_metrics` (PDF) und `core/views/training_stats.py::_calculate_streak` (Dashboard). In der ersten Schleifen-Iteration (`is_current_week`) wird eine leere Woche ignoriert statt den Streak zu beenden.
- **Hypothesen-Korrektur:** Section 9.2 hatte `core/export/stats_collector.py` als Quelle vermutet. Tatsächlich liegt die Streak-Logik in `advanced_stats.py` (PDF-Pfad) und `views/training_stats.py` (Dashboard-Pfad). 24.1 hat keinen der beiden direkt angefasst – der Bug ist eine *latente* Schwäche, sichtbar geworden durch Report-Erstellung am Montag früh (KW20 noch leer).
- **Tests:** `core/tests/test_advanced_stats.py::TestConsistencyMetrics` – vier neue Fälle (`test_streak_laufende_woche_leer_zaehlt_vorwoche`, `..._mehrere_vorwochen`, `..._trainiert_zaehlt_mit`, `test_streak_loch_zwei_wochen_zurueck_bricht`). `core/tests/test_training_stats.py::TestCalculateStreak` – neue Test-Klasse mit fünf Fällen (Null, laufende leer, mehrere Vorwochen, gemischt, Loch). 373 Tests bestanden, keine Regression.
- **Cross-Cutting-Konsequenz:** Beide Pfade laufen wieder synchron – analog zur Lehre aus PR #165 (24.5-Reviewer-Nachzug). Kein gemeinsamer Helper extrahiert; die Logik ist <15 Zeilen pro Pfad und nutzt unterschiedliche Datenmodelle (Queryset vs. direkter DB-Zugriff).

### 24.1b – Fatigue-Index Deload-Skip (Folge-Sub-Phase aus Section 9.2 B2)

- **Start:** 11.05.2026 (Branch `feature/phase-24-1b-fatigue-deload-skip`, Stack-Basis 24.1a)
- **Abschluss:** 11.05.2026
- **Ergebnis:** Die Volumen-Spike-Komponente des Fatigue-Index nutzt jetzt denselben Klassifikator wie die 24.1-Volumen-Diagnose. Re-Aufbau-Wochen nach Deload triggern keine fälschliche „Sehr starker Volumen-Anstieg"-Warnung mehr. Die comparable-Wochen-Selektion (`ist_laufend`/`ist_deload_majority`/`ist_plan_wechsel`/Plan-Epoch-Grenze) wurde aus `_build_week_diagnose` in einen public Helper `select_comparable_weeks` in `core/export/stats_collector.py` extrahiert und wird von beiden Aufrufpfaden konsumiert.
- **Helper-Reuse statt Parallel-Implementierung:** `calculate_fatigue_index` in `core/utils/advanced_stats.py` importiert `select_comparable_weeks` lazy (analog zum bereits bestehenden Lazy-Import auf `core.views.training_stats`-Helper). Wenn weniger als zwei comparable Wochen vorhanden sind, liefert die Spike-Komponente 0 Punkte und keine Warnung statt eines irreführenden Vergleichs.
- **Layer-Bruch:** `advanced_stats → export` ist neu. Pragmatisch akzeptiert; vollständige Bereinigung (Helper nach `core/utils/`) ist Phase-25-Kandidat.
- **Tests:** `core/tests/test_stats_collector.py::TestSelectComparableWeeks` – fünf Direct-Tests (laufende/Deload/Plan-Wechsel-Stop/Null-Volumen/fehlende-Flags-Default). `core/tests/test_advanced_stats.py::TestFatigueIndex` – fünf neue Tests (`test_deload_zwischen_nicht_als_spike` für B2-Reproduktion, `test_plan_wechsel_stoppt_vergleich`, `test_laufende_woche_wird_uebersprungen`, `test_echter_spike_ohne_deload_loch_warnt_weiter`, `test_zu_wenig_comparable_wochen_kein_spike`). 443 Tests bestanden, keine Regression. Bestehende Spike-Tests bleiben grün, weil Dicts ohne 24.1-Flags durch den Helper als „neutral" behandelt werden.


---

## 9. Nach-Implementierungs-Befund (11.05.2026)

Erster Production-Export nach Phase-24-Abschluss: `TrainingReport_Leratos_20260411_20260511.pdf` (Erstellt 11.05.2026 03:55). Bewertung gegen Phase-24-Ziele:

### 9.1 Was greift wie geplant

- **24.3 Zeitraum-Labels:** Executive Summary zeigt sauber *„Trainingseinheiten: 12 (insgesamt 54 seit 03.01.2026), Sätze: 156 (insgesamt 773), Trainingsvolumen: 68615 kg (insgesamt 348012 kg)"*. Berichtszeitraum und Lifetime sind nicht mehr verwechselbar.
- **24.2 Push/Pull kontextabhängig:** Ratio 1,00:1 → *„Ausgewogen, aber Push: Brust im Übertraining-Bereich und Pull: Rücken-Lat im Übertraining-Bereich"*. Empfehlung widerspricht der Muskelgruppen-Diagnose nicht mehr.
- **24.5 Plateau-Status:** RDL (22,3 %/Monat, 25 Tage seit PR) → `aktive_progression_paused`. Trizeps OH (34,9 %/Monat, 63 Tage seit PR) → `aktive_progression_paused`. Hammer Curls → `konsolidierung`. Kein RDL-„Plateau"-Bug mehr.
- **24.1 Volumen-Diagnose:** Hinweis *„Vergleich KW17→KW19"* sichtbar — Deload-Skip im PDF-Trend wirkt.

### 9.2 Neue Bugs / Regressionen

#### B1 — Streak-Regression: aktueller Streak fälschlich auf 0 (Phase-24-Regression)

**Symptom:** Karte „Aktueller Streak (Wochen)" zeigt `0`, während „Längster Streak" weiterhin `19` zeigt und die Adherence bei `100,0 %` bleibt. Vor Phase 24 stand dort konsistent `19`.

**Plausibilitätsprüfung:**
- Heatmap zeigt KW19 (Vorwoche zum Report) vollständig trainiert
- Übungsdetail-Charts dokumentieren Trainings am 06.05. und 08.05.
- Adherence-Berechnung scheint weiterhin korrekt, nur die Streak-Anzeige nicht

**Vermutung:** Bei der Implementierung von 24.1 wurde das Konzept „laufende Woche ausschließen" auf die Streak-Berechnung mit angewendet, so dass der Streak ab der laufenden Kalenderwoche zählt — und KW20 (ab Mo 11.05.) hat naturgemäß noch kein Training, also Streak = 0.

**Korrektur-Anforderung:** Streak muss bis zur letzten **abgeschlossenen** Trainings-Woche zählen. Laufende Woche ist neutral, nicht streak-brechend.

**Vermutete Quelle:** `core/export/stats_collector.py` (oder dort, wo Streak nach 24.1 berührt wurde). Test-Fall: User trainiert wöchentlich, Report wird Montag früh erstellt → Streak muss `N`, nicht `0` zeigen.

#### B2 — Fatigue-Index ignoriert Deload-Klassifikation

**Symptom:** Fatigue-Index von `0/100` (07.05.) auf `40/100` mit Warnung *„Sehr starker Volumen-Anstieg"* (11.05.). Auslöser: KW18 = 12.616 kg (Deload), KW19 = 23.745 kg (Re-Aufbau). Der +88 %-Sprung ist das **erwartete Wiederaufnehmen nach Deload**, nicht ein gefährlicher Volumen-Spike.

**Kontext:** Phase 23.4 (Hinweistext im PDF) sagt explizit *„Volumen-Spike (Vergleich der letzten beiden Wochen)"* als Komponente. Phase 24.1 hat den entsprechenden Vergleich in der **Volumen-Diagnose** auf Deload-Skip umgestellt, im **Fatigue-Index** aber nicht. Inkonsistenz zwischen zwei Sektionen, die dieselbe Mechanik nutzen.

**Konsequenz wenn nicht gefixt:** Bei einem regelmäßigen 3+1-Cycle generiert der Fatigue-Index nach **jeder** Deload-Woche eine fälschliche „Volumen-Spike"-Warnung. Glaubwürdigkeit der Metrik kippt.

**Korrektur-Anforderung:** Die Deload-/Plan-Wechsel-/Laufende-Woche-Klassifikation aus 24.1 muss auch in die Volumen-Spike-Komponente des Fatigue-Index einfließen — gleicher Klassifikator, gleiche Skip-Logik.

**Vermutete Quelle:** `core/utils/advanced_stats.py::calculate_fatigue_index` (oder wo die Volumen-Spike-Komponente lebt). Helper aus 24.1 (`_classify_weeks_from_sessions` o.ä.) sollte wiederverwendet werden — siehe Cross-Cutting-Concern 5.1.

### 9.3 Logiklücke in 24.5

#### L1 — Steigerungsrate ist All-Time-Mittel statt aktueller Trend

**Symptom:** Trizeps Overhead Extension hat seit dem letzten PR am **09.03.** (63 Tage zurück) keine Veränderung mehr — Max-Gewicht laut Verlauf-Chart 17,5 kg seit 09.03., 1RM 26,2 kg seit März stabil. Die historische Steigerungsrate (34,9 %/Monat) stammt fast vollständig aus dem Aufbau Jan→März (5 → 17,5 kg). Die Übung wird trotzdem als `aktive_progression_paused` klassifiziert, weil das All-Time-Mittel die Schwelle (≥ 2 %/Monat) überschreitet.

**Materielle Bewertung:** 9 Wochen Stagnation der Maximalgewichts-Grenze sind kein „Aktive Progression mit Pause", sondern ein echtes Plateau. Die neue Klassifikation maskiert genau die Fälle, die sie eigentlich differenzieren sollte.

**Vergleichsfall RDL:** 22,3 %/Monat historisch — aber aktuell ebenfalls noch im Trend (80→85 kg in 4 Wochen ≈ +24 %/Monat). Hier ist die Klassifikation materiell richtig, die Logik prüft das aber nicht aktiv.

**Korrektur-Anforderung:** Steigerungsrate für die Klassifikations-Entscheidung darf nicht das All-Time-Mittel sein, sondern muss ein aktuelles Zeitfenster verwenden. Vorschläge:
- Variante A: Rate über die letzten 8–12 Wochen
- Variante B: Rate seit dem letzten PR (kein PR und keine Steigerung im aktuellen Fenster → echtes Plateau)
- Variante C: Beide Werte berechnen, nur klassifizieren wenn aktuelle UND historische Rate die Schwelle erfüllen

Das All-Time-Mittel kann als Info-Spalte sichtbar bleiben, aber **nicht als Trigger**.

**Vermutete Quelle:** `classify_progression_status` (laut Phase-24.5-Ergebnis). Tests in `core/tests/test_advanced_stats.py::TestPlateauAnalysis` müssen um einen Fall „hohe Historie, flache Gegenwart" ergänzt werden — genau der Trizeps-OH-Fall.

### 9.4 Status der Phase-24-Ziele nach Befund

| Ziel | Status |
|---|---|
| 24.4 Set-Attribution-Audit | ✅ unverändert gültig |
| 24.1 Volumen-Diagnose | ⚠️ greift, aber Streak-Regression (B1) und Fatigue-Index-Inkonsistenz (B2) sind direkte Folgen unvollständiger Klassifikator-Anwendung |
| 24.2 Push/Pull | ✅ greift |
| 24.5 Plateau | ⚠️ greift formal, aber Klassifikations-Trigger zu großzügig (L1) |
| 24.3 Header-Zeitraum | ✅ greift |
| 24.6 Kraftstandards | ✅ (organisch keine Fälle aktiv, Logik korrekt) |

### 9.5 Vorgeschlagene Folge-Sub-Phasen

| Sub | Inhalt | Aufwand | Priorität |
|---|---|---|---|
| 24.1a | Streak-Berechnung fixen (B1) — bis letzte abgeschlossene Woche zählen | S | hoch (klare Regression) |
| 24.1b | Fatigue-Index Volumen-Spike-Komponente um Deload-Skip erweitern (B2), Helper aus 24.1 wiederverwenden | S–M | hoch (kippt bei jedem Cycle) |
| 24.5a | Steigerungsraten-Klassifikation auf aktuelles Zeitfenster umstellen (L1) | S | mittel (materielle Falsch-Klassifikation, aber subtil) |

Alle drei sind direkte Folgen aus Phase 24, keine neuen Konzept-Themen. Empfehlung: Als Sammel-Sub-Phase `24.7-data-followups` oder als drei kleine Sub-Branches umsetzen — User entscheidet beim Start in VSCode.

### 9.6 Kosmetik (keine Sub-Phase, nur Anmerkung für Phase 25)

- Volumen-Diagnose-Zeile: *„Keine eindeutige Diagnose · Tonnage stabil · Effektives Volumen steigt · Vergleich KW17→KW19"* — die vier Tokens widersprechen sich teilweise. Phase 25 sollte den Diagnose-Block lesbarer machen (Haupt-Diagnose vs. Detail-Tokens visuell trennen oder eine prägnante Hauptaussage formulieren).
- Empfehlungstext aus 24.2: *„Volumen pro Muskelgruppe einzeln prüfen"* ist ein Hinweis, kein konkreter Schritt. Konkretisierung (z.B. „Brust/Rücken-Lat um X Sätze reduzieren, vordere/seitliche Schulter um Y ergänzen") wäre eine spätere Iteration, kein Phase-24-Defekt.
