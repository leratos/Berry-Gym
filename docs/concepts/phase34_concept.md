# Phase 34 – Pausenbereinigte Blockdauer + Entfernung der Ernährungsaussagen

> Status: **v1 (Fundorte am Code verifiziert, Scope bestätigt)** – Claude Code /
> VSCode, 2026-07-21. Auslöser + User-Entscheidungen: Journal #1053.
> Anders als bei Phase 33 v1 sind die Fundorte hier **keine Hypothesen mehr** –
> Schritt 1 (reine Code-Verifikation, Journal-Auftrag) ist abgeschlossen; die
> wenigen Rest-Hypothesen sind explizit als solche markiert (§6).

## 1. Ziel

Zwei unabhängige Produktionsbefunde (Dashboard, 21.07.2026):

1. **Blockdauer zählt Pausenwochen mit.** Die Phasenwechsel-Karte („Definition /
   Hypertrophie läuft seit 15 Wochen") zählt Kalenderwochen seit Blockstart,
   blind gegenüber dokumentierten `TrainingsPause`-Zeiträumen (hier:
   18.06.–19.07.2026, 32 Tage). Der Dauer-Schwellwert der
   Phasenwechsel-Empfehlung feuert dadurch verfrüht – *weil* der User krank
   war. Gleichzeitig zeigt das Dashboard direkt darüber den
   Wiedereinstiegs-Banner (33.3): zwei sich widersprechende Karten.
2. **Ernährungsaussagen in Empfehlungstexten.** „… der Stoffwechsel ist bereit
   für einen Kalorienüberschuss" (u. a.). Das Tool macht keine
   Ernährungsberatung und soll keine machen; im konkreten Nutzerkontext
   (Bypass-Historie) zusätzlich unverantwortlich.

Strukturgleich zu 32.x (Volumen/Streak/adherence) und 33.4 (Stagnation):
**Kalenderzeit ≠ Trainingszeit.** Der Pfad „Blockdauer → Phasenempfehlung" ist
in beiden Audits durchgerutscht; `test_pausen_audit` (Konvergenzgarant aus 32.4)
wird deshalb um diesen Pfad erweitert – kein isolierter Einzeltest.

## 2. User-Entscheidungen (fixiert, #1053 + 21.07.)

1. **Brutto UND Netto anzeigen**, Brutto nicht überschreiben – Datenintegrität
   vor Präsentation. Anzeigeziel: „läuft seit 15 Wochen (11 Trainingswochen,
   4 Wochen Pause)"; ohne Pause im Block unverändert einzeilig.
2. **Ernährungsaussagen komplett raus**, nicht entschärfen.
   Trainingsphasen-Aussagen (z. B. „Körperfett reduzieren" als Phasenziel)
   bleiben bestehen.
3. Eigene **Phase 34**, kein Bugfix-Anhang an Phase 33.
4. (21.07., Chat) **`weight_analysis.py` gehört mit in den 34.3-Sweep**
   („Kaloriendefizit"-Erklärung + „Proteinzufuhr prüfen").

## 3. Verifizierte Fundorte (Schritt-1-Ergebnis)

### 3.1 Blockdauer & Schwellwert

- Dauer: `Trainingsblock.weeks_since_start` (`core/models/training.py:193`) =
  `(heute − start_datum).days // 7` – reine Kalendertage.
- Karte: `get_block_age_warning` (`core/utils/periodization.py:166`), einziger
  Aufrufer `dashboard`-View (`core/views/training_stats.py:1375`, im
  `dashboard_computed`-Cache), gerendert in `dashboard.html:185–209`.
- Schwellwert: `warning_threshold_weeks` = `plan_dauer_wochen` (falls gesetzt),
  sonst `BLOCK_AGE_WARNING_THRESHOLD = 8`. **Nicht** je Phasentyp
  unterschiedlich. Severity „danger" ab 1,5× Schwellwert.

### 3.2 Alle Konsumenten der Blockdauer

| Konsument | Umgang in Phase 34 |
|---|---|
| Phasenwechsel-Karte (`get_block_age_warning`) | **Netto auswerten (34.2), Brutto+Netto anzeigen (34.1)** |
| Fatigue-Gate `_get_volume_spike_fatigue` (`training_stats.py:416`, Block < 3 Wochen → keine Volumen-Warnung) | **Netto (34.2)** – gleicher Bug, gleiche Richtung: Brutto beendet das Schutzfenster nach Pause zu früh |
| Dashboard-Hinweis „Neuer Block – Vergleiche ab Woche 3" (`dashboard.html:615`) | **Netto (34.2)** – muss konsistent zum Fatigue-Gate bleiben |
| W-Badge „· W16" (`dashboard.html:580`) | bleibt **Brutto** (Kalenderposition, keine Bewertung) |
| `set_active_plan.html:123` „(X Woche(n))" | bleibt **Brutto** (reine Info) |
| Admin `list_display` (`core/admin.py:932`) | bleibt **Brutto** (Rohdaten) |
| **KI-Plan-Generator (`ai_coach/`)** | **NICHT betroffen** (verifiziert): nutzt nur `active_block.typ`; `weeks_since_start` fließt nirgends in den Prompt; der `fatigue_hint` kommt aus `calculate_fatigue_index`, das seit 32.3 pause-aware ist |
| PDF-Export | **NICHT betroffen** (verifiziert): Blockdauer/Karte wird nirgends im PDF gerendert → keine Paritätspflicht |

### 3.3 Ernährungsaussagen (vollständiges Sweep-Inventar)

| # | Datei:Zeile | Text (Kern) | Behandlung |
|---|---|---|---|
| 1 | `periodization.py:74` | „Stoffwechsel … Kalorienüberschuss" | ersetzen (Trainings-Begründung) |
| 2 | `periodization.py:62` | „überschüssiges Körperfett … abbauen" | umformulieren („angesammeltes Körperfett reduzieren" – Wortstamm-Kollision mit Textregel vermeiden; Körperfett als Phasenziel bleibt) |
| 3 | `periodization.py:273` | „RPE 9.5+ im Defizit …" | „in der Definitionsphase" |
| 4 | `periodization.py:277` | „Im Defizit ist Stagnation normal …" | „In der Definitionsphase …" |
| 5 | `ai_recommendations.py:616` | „Im Defizit ist schweres Training …" | „In der Definitionsphase …" |
| 6 | `ai_recommendations.py:620` | „… bei Kaloriendefizit" | „… in der Definitionsphase" |
| 7 | `weight_analysis.py:100` | „… auf ein Kaloriendefizit zurückzuführen" | ersetzen (Aussage über Muskelmasse, nicht Kalorien) |
| 8 | `weight_analysis.py:113` | „Proteinzufuhr prüfen …" | ersetzen (Beobachtungs-Hinweis ohne Ernährung) |
| 9 | `advanced_stats.py:1330` | „Recovery, Schlaf und Ernährung prüfen" | „Recovery und Schlaf prüfen" |
| 10 | `training_stats.py:818` | „Prüfe Regeneration, Ernährung und Schlaf" | „Prüfe Regeneration und Schlaf" |

Anzupassender Test: `test_ai_recommendations.py:1007` (`assert "Defizit" in …`).

**Bewusst NICHT im Sweep:**
- `load_disclaimers.py:56` – rechtlicher Disclaimer, listet die
  Grundumsatz-(kcal)-*Berechnung* des Body-Trackings als Schätzung; keine
  Empfehlung.
- `core/models/body_tracking.py` (`grundumsatz_kcal`) – Datenfeld, keine
  Empfehlung.
- `views_old.py` – toter Code (nirgends importiert/geroutet); dokumentiertes
  Fremdproblem, wird hier nicht angefasst.

### 3.4 SoT-Bausteine (week_classification.py) & Semantik-Entscheidung

Vorhanden: `_clamp_pausen` (auf heute geclampte Ranges), `_classify_week_pause`
(Achse 1 Abdeckung: `ist_ausfall`/`teilweise_ausfall`; Achse 2 Dauer:
`ist_pausen_grenze`), `pausen_grenze_keys`, `letzte_iso_wochen_keys`,
`PAUSE_BOUNDARY_MIN_DAYS = 5`.

**Zentrale Semantik-Entscheidung (am Produktionsfall verifiziert):** Die Pause
Do 18.06.–So 19.07. *berührt* 5 ISO-Wochen (W25 nur Do–So), *deckt* aber nur 4
voll ab. `pausen_grenze_keys` (Grenz-Semantik = „berührt") ergäbe „5 Wochen
Pause"; die Ziel-Anzeige „(11 Trainingswochen, 4 Wochen Pause)" entspricht der
**Abdeckungs-Semantik** (`ist_ausfall`: ISO-Woche voll von Pause abgedeckt UND
0 Sessions). Eine trotz Pause trainierte Woche zählt als Trainingswoche.
→ 34.1 komponiert `ist_ausfall`, **nicht** `ist_pausen_grenze` (exakt die
Achsen-Trennung aus Phase 32; keine Parallel-Logik – nur ein dünner öffentlicher
Helfer, weil `_clamp_pausen`/`_classify_week_pause` modulprivat sind).

## 4. Sub-Phasen

### 34.1 – Netto-Wochen-Helfer + zweizeilige Anzeige

- **`week_classification.py`**: neue öffentliche Funktion
  `pausen_ausfall_wochen(pausen, start_datum, heute_date, sessions_week_keys)`
  → Anzahl ISO-Wochen in `[start_datum, heute]`, die `ist_ausfall` sind
  (voll von geclampter Pause abgedeckt, keine Session). Reine Funktion,
  komponiert `_clamp_pausen` + `_classify_week_pause` + `letzte_iso_wochen_keys`.
- **`periodization.get_block_age_warning(active_block, netto_weeks=None)`**:
  optionaler Parameter; Rückgabe-Dict zusätzlich `netto_weeks` und
  `pausen_wochen` (= Brutto − Netto). `weeks` bleibt Brutto. Ohne Pause
  (`pausen_wochen == 0`) rendert das Template unverändert einzeilig.
- **`dashboard`-View** (im gecachten Block – Pausen-CRUD invalidiert
  `dashboard_computed` seit 32.2 ⑬): `sessions_week_keys` aus abgeschlossenen
  `Trainingseinheit`-Daten seit Blockstart (33.x-Lektion: nur
  `abgeschlossen=True`), Netto berechnen, an `get_block_age_warning`
  durchreichen; `block_netto_weeks`/`block_pausen_wochen` in den Context.
- **`dashboard.html`**: Karte zeigt bei `pausen_wochen > 0` die zweizeilige
  Form „läuft seit X Wochen (N Trainingswochen, P Wochen Pause)", sonst
  unverändert.
- **i18n**: neuer `blocktrans`-String + der (vorbestehend fehlende) einzeilige
  String werden manuell ans `django.po` angehängt (kein `makemessages`,
  Reorder-Lektion 33.3) + `compilemessages`.

### 34.2 – Schwellwert auf Netto + Unterdrückung während Rampe

- `get_block_age_warning`: Schwellwert-Vergleich und Severity (`danger` ab
  1,5×) werten `netto_weeks` aus (Fallback ohne Parameter: Brutto → bestehende
  Aufrufer/Tests unverändert grün).
- **Unterdrückung**: im View **nach** dem Cache-Read (Reentry ist bewusst
  „immer frisch" außerhalb des Caches, 33.3-Entscheidung):
  `reentry_pause is not None` (= `get_active_reentry_pause` liefert laufende
  Rampe) → `context["block_age_warning"] = None`. Kein Mutieren des gecachten
  Dicts.
- Fatigue-Gate + „Neuer Block"-Hinweis (§3.2) auf Netto umstellen.

### 34.3 – Ernährungs-Sweep (Inventar §3.3)

- Alle 10 Stellen ersetzen wie tabelliert; `test_ai_recommendations.py:1007`
  anpassen; Templates auf Restvorkommen gegenprüfen (grep).
- `.po`-Befund (verifiziert): **keiner** der Sweep-Texte ist im Katalog (die
  reason-Texte sind nicht gettext-markiert – vorbestehende, dokumentierte
  Lücke, siehe §6) → nichts zu entfernen; nur die neuen 34.1-Strings kommen
  dazu. `compilemessages`, `test_i18n` grün.

### 34.4 – Audit-Erweiterung + Textregel-Test

- **`test_pausen_audit.py`** (kein isolierter Einzeltest): Pfad 6
  „Blockdauer/Phasenwechsel" ins `INVENTORY` + Testklasse:
  - Brutto ≥ Schwellwert, Netto < Schwellwert → keine Empfehlung (Kernbug).
  - Brutto 15 / 4 Ausfall-Wochen → Karte mit `weeks=15`, `netto_weeks=11`,
    `pausen_wochen=4`.
  - Severity auf Netto (Brutto ≥ 1,5×, Netto < 1,5× → „warning", nicht
    „danger").
  - Teilweise überlappte Woche und Woche mit Session trotz Pause zählen NICHT
    als Pausenwoche (Abdeckungs-Semantik).
  - Laufende Rampe (`get_active_reentry_pause` ≠ None) → Karte unterdrückt
    (Dashboard-Integrationstest).
  - Positivkontrolle: ohne Pause feuert die Empfehlung unverändert (keine
    Übersuppression).
- **Textregel-Test** (neu, `core/tests/test_empfehlung_textregeln.py`):
  verbietet Ernährungsbegriffe (`kalorien`, `defizit`, `überschuss`/`überschüss`,
  `stoffwechsel`, `ernährung`, `proteinzufuhr`, `eiweiß`, `kcal`, `diät`,
  jeweils inkl. ASCII-Varianten, case-insensitive) in den
  Empfehlungs-Quellen: `periodization.py`-Konstanten (Dict-Walk) + Quelltext von
  `periodization.py`, `ai_recommendations.py`, `weight_analysis.py`,
  `advanced_stats.py`, `training_stats.py`. Regel im Testcode statt Konvention
  im Kopf (Phase-11-/30.1-Lektion).

## 5. Abnahmekriterien

1. Produktionsfall reproduziert: Block 15 Kalenderwochen mit 4 voll
   abgedeckten Pausenwochen → Anzeige „15 Wochen (11 Trainingswochen,
   4 Wochen Pause)"; Schwellwert/Severity auf 11 ausgewertet.
2. Ohne Pause im Block: Anzeige und Verhalten byte-identisch zu vorher
   (einzeilig, Brutto).
3. Solange `get_active_reentry_pause` eine laufende Rampe liefert, erscheint
   keine Phasenwechsel-Empfehlung (kein Karten-Widerspruch mehr).
4. Kein Empfehlungstext (Phasen, RPE, Stagnation, Fatigue/Diagnose,
   Gewichtsanalyse) enthält Ernährungsbegriffe; Textregel-Test erzwingt das.
5. `test_pausen_audit` deckt den Blockdauer-Pfad ab (inkl. Positivkontrolle).
6. i18n: neue Strings DE/EN, `.mo` kompiliert, `test_i18n` grün.
7. Volle Testsuite grün bis auf die zwei dokumentierten vorbestehenden Fehler
   (`test_stats_collector::test_mit_verlauf` order-flaky,
   `ai_coach test_secrets_manager::test_cli_full_set_get_list_delete_flow`
   env-abhängig – beide am 21.07. gegen clean main gegenverifiziert).

## 6. Risiken, Rest-Hypothesen, dokumentierte Fremdprobleme

- **Erwartete Verhaltensänderung, keine Regression:** Mit Netto-Auswertung
  verschwinden Empfehlungen, die vorher (verfrüht) erschienen; das
  Fatigue-Gate unterdrückt nach Pausen länger. Gewollt (#1053).
- **Rest-Hypothese (klein):** Für Blöcke ohne Pause ist
  `pausen_ausfall_wochen == 0` und alles verhält sich exakt wie vorher – wird
  durch bestehende `test_periodization`-Tests (Default-Parameter) abgesichert,
  nicht neu bewiesen.
- **Semantik-Kante (dokumentiert):** Brutto zählt volle 7-Tage-Fenster ab
  Blockstart, die Pausen-Wochen zählen ISO-Kalenderwochen – bei Blockstart
  mitten in der Woche kann die Rand-Woche der Pause in keiner der beiden
  Zählungen auftauchen (konservativ: Netto fällt eher zu hoch als zu niedrig
  aus → Empfehlung eher zu früh als zu spät = Status quo, nie schlechter).
- **Fremdprobleme (NICHT in Phase 34 fixen):**
  - `views_old.py` ist toter Code (enthält u. a. alte Empfehlungstexte).
  - Die `recommendation.reason`-Texte sind nicht gettext-markiert und der
    einzeilige Karten-String fehlte im EN-Katalog → EN-Dashboard zeigt
    teilweise Deutsch. Phase 34 ergänzt nur die von ihr berührten Strings;
    vollständige i18n der Empfehlungstexte wäre eine eigene Aufgabe.
  - `test_mit_verlauf` (order-flaky) + `test_secrets_manager` (env-abhängig):
    vorbestehende Tech-Schuld, gegenverifiziert.

## 7. Reihenfolge & Branch

34.1 → 34.2 → 34.3 → 34.4. Branch
`feature/phase-34-pausenbereinigte-blockdauer`, Commit pro Sub-Phase, dieses
Konzept-Doc als erster Commit. Kein Merge/PR (macht der User; Merge =
Prod-Deploy). Journal: Entwurf vor Commit, Abschluss danach, Merge-/Deploy-
Eintrag nach dem Merge (Lektion #1052).
