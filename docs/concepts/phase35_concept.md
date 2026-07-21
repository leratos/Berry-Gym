# Phase 35 – Kontextblinde Report-Pfade nach dokumentierter Pause

> Status: **v1 (Fundorte am Code verifiziert, Scope aus #1061)** – Claude Code /
> VSCode, 2026-07-21. Auslöser: Report-Audit #1059 (Befunde (a)–(g)), gültiger
> Sub-Phasen-Schnitt: #1061 (35.1–35.4). Phase 34 ist gemerged/deployed und
> wird nicht wieder geöffnet. Schritt 1 (reine Code-Verifikation) ist
> abgeschlossen; Rest-Hypothesen sind explizit markiert (§6).
> Entscheidungsmodus (User, 21.07.): offene Design-Entscheidungen werden hier
> getroffen und als Empfehlung mit Begründung dokumentiert (§2) – Review beim
> Konzept-Read.

## 1. Ziel

Der PDF-Report vom 21.07.2026 (32 Pausentage + genau 1 Trainingseinheit im
Berichtszeitraum) legt Analysepfade offen, die auf je eigene Weise
kontextblind sind – nicht (nur) gegenüber Kalenderzeit ≠ Trainingszeit wie
32/33/34, sondern gegenüber degenerierten Eingaben (n=0, leeres Fenster) und
der eigenen Wiedereinstiegs-Empfehlung:

1. **(b)** Status „Rückschritt" bestraft das Befolgen der eigenen
   Rampen-Empfehlung (reentry-Faktor 0,85 reißt zwangsläufig die
   5-%-Regressions-Schwelle).
2. **(c)** Push/Pull degeneriert bei n=0 einer Seite zu „Ratio 0,00:1 –
   Pull überwiegt leicht (gut)".
3. **(d)** Schwachstellen-Erkennung ist invertiert: 0-Satz-Gruppen können
   keine Schwachstelle sein, weil sie die Statistik nie erreichen.
4. **(e)** „Deine Stärken"-Empty-State widerspricht dem restlichen Report.
5. **(f)** RPE-Empfehlungstext fällt bei dünnem 4W-Fenster auf All-Time
   zurück und transportiert dessen kontextfreie Empfehlungsliste.
6. **(g)** Kein globaler Pausen-Kontext im Report; Heatmap ohne
   Pause-Marker direkt neben dem pausenbewussten Volumen-Chart.
7. **Deload-Zeile** („Geschätzte Deload-Woche") ist ein hartkodiertes
   „heute + 6 Wochen" – täuscht eine Heuristik vor, die nicht existiert.
8. **(a)** „Guter Verlust" bewertet krankheitsbedingten Gewichtsverlust
   positiv – Ernährungsbewertung, vom 34.3-Sweep nicht erfasst.

Leitplanke überall: **„nicht bewertbar" ausgeben statt einen degenerierten
Wert zu beschönigen.** Bestehende SoT (week_classification.py, reentry.py,
Phase-34-Helfer) konsumieren, keine Parallel-Logik.

## 2. Entscheidungen (in dieser Phase getroffen, je mit Empfehlung)

| # | Frage | Entscheidung/Empfehlung | Begründung / verworfene Alternative |
|---|---|---|---|
| E1 | Rückschritt während Rampe: unterdrücken oder eigener Status? | **Eigener Status `reentry` („Wiederaufbau nach Pause", info)**, solange `get_active_reentry_pause` eine laufende Rampe liefert | Bloßes Unterdrücken (→ fällt auf Plateau-Zweige durch) erzeugt neue Falschaussagen; ein sichtbarer Status erklärt die Lage. Alternative „Vergleich nur post-Pause" verworfen: Regression ist bewusst ein Vergleich vs. All-Time-PR |
| E2 | Push/Pull-Guard-Schwelle | **Nur Ein-Seiten-Null-Guard** (push==0 XOR pull==0 → „Nicht bewertbar"), kein allgemeines Mindest-n | Minimal-invasiv, deckt den belegten Fehlerfall; ein Mindest-n wäre Spekulation ohne Befund. Live-Zwilling `_calc_push_pull_ratio` bekommt denselben Guard |
| E3 | Schwachstellen: 0-Satz-Gruppen | **`collect_muscle_balance` appendet auch `anzahl == 0`** (Status `nicht_trainiert` wird damit erreichbar) | Single Source of Truth statt separater Schwachstellen-Sonderliste (wäre Parallel-Logik). Nebeneffekt gewollt: Körperkarte/Push-Pull sehen dieselbe vollständige Liste |
| E4 | Stärken-Empty-State | **Text differenzieren:** nur bei „nie trainiert" der alte Onboarding-Satz; sonst „Im 30-Tage-Fenster keine Muskelgruppe im optimalen Bereich" (Pausen-Kontext liefert der 35.3-Banner) | Der Onboarding-Satz ist bei 64 Einheiten Historie objektiv falsch |
| E5 | RPE-All-Time-Fallback | **Empfehlungsliste bei `insufficient_4w` nicht rendern** (die Wrapper-Kontextzeile „Bewertung basiert auf Gesamtzeitraum" bleibt); 4W-Kachel rendert ihr vorhandenes `insufficient_data`-Flag sichtbar | Fallback-Design bleibt erhalten (bewusste Phase-23-Entscheidung), nur das kontextfreie Empfehlungs-Artefakt wird gekappt. Alternative „Fallback ganz streichen" verworfen: All-Time als gelabelter Kontext ist legitim |
| E6 | Deload-Zeile | **Ersatzlos entfernen** (Template-Zeile + `naechste_deload`-Key + 2 Tests anpassen) | Ein konstantes „heute+6 Wochen" ist keine Heuristik, sondern Präzisions-Theater. Alternative „echte Netto-Heuristik" verworfen: bräuchte neue Deload-Historik-Logik = eigene Phase, nicht 35er-Scope |
| E7 | „Guter Verlust"-Schnitt | **Ganze Bewertungs-Kette neutralisieren** (deskriptiv: „Zunahme/Verlust/Stabil", keine Wert-Adjektive); der `weight_loss_analysis`-Risk-Zweig (Muskelabbau-Risiko) bleibt | „Guter/Moderater Verlust", „Schnelle Zunahme" sind dieselbe Bewertungsklasse – nur ein Label zu tauschen ließe die Nachbarn als Regelverstoß stehen. Risk-Zweig ist trainingsbezogen (Muskelabbau), keine Ernährungsbewertung |
| E8 | Banner-Mechanik | **Ein gemeinsamer Daten-Helfer** (`week_classification.pausen_im_zeitraum`) **+ zwei Template-Einbaustellen** (PDF-Deckblatt, Live-Statistikseite) | Es gibt keine gemeinsame Template-Stelle Live/PDF (verifiziert); geteilt wird die Datenquelle, nicht das Markup |
| E9 | Heatmap-Marker | **Optionale `pause_ranges` an `generate_training_heatmap`**, Pausentage als eigene Zellfarbe + Legenden-Eintrag „Pause" | Heatmap ist tages-granular; die wochen-key-Helfer passen nicht direkt. Tages-Ranges aus geclampten `TrainingsPause`-Spannen = dieselbe SoT, kein neues Regelwerk |

## 3. Verifizierte Fundorte (Schritt-1-Ergebnis, 21.07.2026)

### 3.1 „Rückschritt"-Klassifikator (35.1)

- **Ein** SoT-Klassifikator: `classify_progression_status`
  (`core/utils/advanced_stats.py:213`); Regression bei
  `weight_drop_pct > REGRESSION_WEIGHT_DROP_PCT (5.0)` – bestes 1RM der
  letzten 28 Tage vs. All-Time-PR (`:296–316`). Kein Pausen-Wissen; der
  Regressions-Check läuft **vor** dem `cur_4w_n < 2`-Pause-Check (`:331`)
  → erste Session nach Pause mit Rampengewichten = „Rückschritt".
- **Drei Konsumenten** (Fix an einer Stelle wirkt überall):
  1. Live: `_calc_plateau_live` (`core/views/training_stats.py:2168`,
     Aufruf `:2254`, View `:2503`).
  2. PDF: `calculate_plateau_analysis` (`advanced_stats.py:413`) →
     `stats_collector.py:587` → `export.py:200–203` merged in
     Kraftentwicklungs-Top-5 **und** Übungsdetail-Charts (inkl.
     `weight_drop_pct`-Annotation „1RM-Drop X % vs. PR").
  3. **KI-Plan-Generator** (`ai_coach/plan_generator.py:1631–1640`) – in
     #1055 nicht als Konsument gezählt; der falsche Status floss bisher in
     den Plan-Kontext.
- `_check_pr` bestätigt unbeteiligt (deckt sich mit #888/#1059).

### 3.2 Push/Pull (35.2)

- PDF: `collect_push_pull` (`core/export/stats_collector.py:211`); Guard nur
  für `push == 0 and pull == 0` (`:225`); push=0/pull>0 → ratio 0,0 →
  „Pull-betont (gut)" (`:232–241`) → „Pull überwiegt leicht …" (`:160`).
- Live (separater Codepfad, ebenfalls degeneriert): `_calc_push_pull_ratio`
  (`training_stats.py:2124`); push=0/pull=18 → ratio 0,0 → **„Ausgeglichen"**
  (`:2148–2151`).
- Bereits korrekt (Vorbild): Balance-Warner `ai_recommendations.py:300`
  (`return []` wenn eine Seite 0).

### 3.3 Schwachstellen/Stärken (35.2)

- Die Schwachstellen-Filterung (`stats_collector.py:614–618`) schließt
  `nicht_trainiert` formal ein – aber `collect_muscle_balance` appendet nur
  bei `anzahl > 0` (`:95`); der `nicht_trainiert`-Zweig (`:42`) ist im
  PDF-Pfad toter Code. 0-Satz-Gruppen erreichen weder Schwachstellen noch
  Push/Pull noch Körperkarte.
- Stärken: `status == "optimal"` im 30-Tage-Fenster (`:619`); Empty-State =
  `{% else %}`-Zweig `training_pdf_simple.html:1329–1340`.
- Live-Kontrast (korrekt): `_calc_muscle_soll_bereiche`
  (`training_stats.py:2096–2102`) iteriert alle Gruppen inkl.
  `counts.get(mg_code, 0)`.

### 3.4 RPE (35.2)

- **Kein getrennter Codepfad**: Kacheln + Empfehlung kommen aus
  `calculate_rpe_quality_analysis_windowed` (`advanced_stats.py:1140`); Live
  (`training_stats.py:2490`) und PDF (`stats_collector.py:629`) nutzen
  denselben Wrapper.
- 4W n < `MIN_SETS_FOR_WINDOW (30)` → `primary = "all"` (`:1211–1215`);
  Template rendert `primary.empfehlungen` (`training_pdf_simple.html:
  1200–1209`) = All-Time-Liste aus `calculate_rpe_quality_analysis`
  (`:984–1000`, der Audit-Satz stammt aus `:996`). Die ehrliche
  Kontextzeile (`:1229–1233`) wird daneben ebenfalls gerendert.
- 2W/4W-Widerspruch: nur die 2W-Karte unterdrückt ihren Wert
  (`:1272–1274`); die 4W-Karte behält ihn designgemäß, aber das Template
  rendert das `insufficient_data`-Flag nicht (`training_pdf_simple.html:
  1160–1166`).
- Nebenfund: `export.py:236` speist „Handlungsfelder" aus der All-Time-
  `rpe_quality` (Junk-Volume > 30 %).

### 3.5 Deload-Zeile (35.2)

- `advanced_stats.py:709`: `naechste_deload = heute + timedelta(weeks=6)` –
  hartkodiert, kein Blockdauer-/Deload-Historik-Konsument (Hypothese aus
  #1059/#1061 damit widerlegt). Probe: 21.07. + 42 T = 01.09.2026 =
  Report-Wert. Einziger Konsument: `training_pdf_simple.html:1304`.
  Tests auf den Key: `test_advanced_stats.py:365`,
  `test_helpers_and_utils.py:667`.

### 3.6 „Guter Verlust" (35.2)

- Template-Inline-Schwellenkette `training_pdf_simple.html:659–672`
  (`gewichts_rate > -1.0` → „Guter Verlust"; Nachbarn „Schnelle/Leichte
  Zunahme", „Moderater Verlust"; darunter `weight_loss_analysis`-Risk-Labels).
  Vom 34.3-Sweep nicht erfasst; der Textregel-Test kann die Labels
  wortstamm-bedingt nicht fangen. Kein Live-Pendant (String nur in diesem
  Template).

### 3.7 Banner + Heatmap (35.3)

- Keine gemeinsame Stelle Live/PDF: PDF = Standalone-Template mit
  Deckblatt/„Berichtszeitraum" (`training_pdf_simple.html:449`), Kontext aus
  `export_training_pdf` (`export.py:114–134`, fixes 30-Tage-Fenster); Live =
  `training_stats.html` (extends base) mit eigenem View.
- Volumen-Chart: `generate_volume_chart` (`chart_generator.py:691`) liest
  `ist_ausfall`/`teilweise_ausfall` aus den `volumen_wochen`-Zeilen
  (week_classification-SoT) und zeichnet Marker (`:707–798`).
- Heatmap: `generate_training_heatmap` (`chart_generator.py:1002`) bekommt
  nur `[{datum, intensitaet}]` aus `collect_training_heatmap_data`
  (`stats_collector.py:485`) – Pausen-Info erreicht den Generator nie.

## 4. Sub-Phasen

### 35.1 – „Rückschritt"-Status rampen-aware (zuerst, höchster Alltagsnutzen)

- `classify_progression_status(..., reentry_pause=None)`: neuer optionaler
  Keyword-Parameter (Ergebnis von `get_active_reentry_pause(user)`, von den
  Aufrufern **einmal** berechnet und durchgereicht – reentry bleibt wie in
  33.3 außerhalb des Dashboard-Caches).
- Neue Statusstufe **vor** dem Regressions-Check: laufende Rampe UND
  Regressions-Bedingung erfüllt → `status="reentry"`,
  `status_label="Wiederaufbau nach Pause"`, `status_farbe="info"`;
  Icon/Glyph in `_PROGRESSION_STATUS_ICON`/`_GLYPH` ergänzen. Ohne
  Regressions-Bedingung (User trainiert in der Rampe auf altem Niveau)
  bleibt die normale Klassifikation unverändert – keine Übersuppression.
- `calculate_plateau_analysis(..., reentry_pause=None)` reicht durch;
  Aufrufer anpassen: `_calc_plateau_live` (hat `user`),
  `stats_collector.collect_pdf_stats`-Pfad (hat `user`),
  `ai_coach/plan_generator.py:1640` (hat `user`). Default `None` =
  bisheriges Verhalten → bestehende Tests bleiben grün.
- PDF-Status-Legende (`training_pdf_simple.html:950–953`) um den neuen
  Status ergänzen; Live-Template rendert `status_label` generisch (kein
  Templateumbau).
- i18n: neue Label-Strings manuell ans `django.po` DE/EN anhängen (kein
  `makemessages`, Reorder-Lektion 33.3) + `compilemessages`.

### 35.2 – Guard-Klauseln

1. **Push/Pull PDF** (`collect_push_pull`): neuer Zweig
   `push == 0 or pull == 0` (nicht beide) → `bewertung="Nicht bewertbar"`,
   `ratio=None`-sicher rendern, `empfehlung`: „Nur {Pull|Push}-Sätze im
   Zeitraum ({n}) – Balance nicht bewertbar." Kein Gesundheitslob.
2. **Push/Pull Live** (`_calc_push_pull_ratio`): derselbe Guard →
   `status_text="Nicht bewertbar"`, `farbe="secondary"`.
3. **Schwachstellen** (`collect_muscle_balance`): `if anzahl > 0`-Gate
   entfernen; 0-Satz-Gruppen mit `volumen=0.0`, `avg_rpe=0.0`,
   `prozent_von_optimal=0.0` appenden → `nicht_trainiert` erreicht die
   Schwachstellen-Auswahl (Sortierung `key=saetze` priorisiert sie korrekt
   an Position 1).
4. **Stärken-Empty-State** (`training_pdf_simple.html`): `{% else %}`
   differenzieren – bei vorhandener Trainingshistorie (`trainings_gesamt >
   0`) neutraler Fenster-Text statt Onboarding-Satz (E4).
5. **RPE**: Template-Gate `{% if not rqw.insufficient_4w %}` um den
   Empfehlungen-Block (PDF + Live); 4W-Karte rendert bei
   `card.insufficient_data` den Zusatz „(n={{ card.n_sets }} –
   eingeschränkt aussagekräftig)".
6. **Deload-Zeile**: `training_pdf_simple.html:1304` entfernen;
   `naechste_deload` aus `calculate_fatigue_index`-Rückgabe streichen; die
   zwei Key-Tests entfernen/anpassen (§3.5).
7. **Körperentwicklungs-Bewertung**: Schwellenkette `:659–672` durch
   deskriptive Labels ersetzen („Zunahme"/„Verlust"/„Stabil", Schwellen
   ±0,1 kg/Woche für „Stabil"); Risk-Zweig (`weight_loss_analysis`) bleibt.

### 35.3 – Report-Banner + Heatmap-Pausenmarker

- **`week_classification.pausen_im_zeitraum(pausen, start, end)`** (neu,
  öffentlich): geclampte Pausen-Spannen (≥ `PAUSE_BOUNDARY_MIN_DAYS`) mit
  Überlappung zu `[start, end]` → Liste + Summentage + `medizinisch`-Flag.
  Komponiert `_clamp_pausen`; keine Parallel-Logik.
- **PDF**: `export_training_pdf` ruft den Helfer, Context
  `pausen_banner`; Render unter dem „Berichtszeitraum"-Block
  (`training_pdf_simple.html:449`): „Berichtszeitraum enthält N dokumentierte
  Pausentage (DD.MM.–DD.MM.); zeitfenster-basierte Auswertungen
  eingeschränkt aussagekräftig."
- **Live**: `training_stats`-View analog (30-Tage-Fenster), Alert-Banner
  oben in `training_stats.html` (i18n-markiert, manueller .po-Anhang).
- **Heatmap**: `generate_training_heatmap(training_dates, pause_ranges=None)`;
  Pausentage als eigene Zellfarbe (außerhalb der Intensitäts-Colormap, per
  Overlay-Rechtecke) + Legenden-Eintrag „Pause". Aufrufer `export.py:155`
  übergibt die geclampten Spannen aus dem Banner-Helfer.

### 35.4 – Audit-Erweiterung + Textregel-Test

- **`test_pausen_audit.py`**: `INVENTORY` 7 → **13**; neue Pfade je mit
  Kernbug-Test + Positivkontrolle:
  - Pfad 8 Rückschritt: Rampe aktiv + Drop > 5 % → `reentry`, nicht
    `regression`; Rampe aktiv ohne Drop → normale Klassifikation; keine
    Rampe + Drop → weiterhin `regression` (Positivkontrolle).
  - Pfad 9 Push/Pull: push=0/pull>0 → „Nicht bewertbar" (PDF + Live);
    beide > 0 → unverändert.
  - Pfad 10 Schwachstellen/Stärken: 0-Satz-Gruppe erscheint als
    Schwachstelle Position 1; Stärken-Empty-State-Text je Historie.
  - Pfad 11 RPE: `insufficient_4w=True` → Empfehlungen-Block nicht im
    gerenderten PDF-HTML; 4W-Karte trägt Einschränkungs-Zusatz.
  - Pfad 12 Banner: Pause im Zeitraum → Banner in PDF-HTML + Live-Context;
    ohne Pause → kein Banner.
  - Pfad 13 Heatmap: `pause_ranges` gesetzt → Chart generiert (Smoke +
    Legenden-/Param-Test in `test_chart_generator`).
- **Textregel-Test** (`test_empfehlung_textregeln.py`) erweitern:
  Verbotsliste wertender Körpergewichts-Labels („Guter Verlust",
  „Moderater Verlust", „Schnelle Zunahme", „Leichte Zunahme") im Quelltext
  von `training_pdf_simple.html`; bestehende Ernährungswort-Regel bleibt.

## 5. Abnahmekriterien

1. Reproduktion Report-Fall: erste Session nach 32-Tage-Pause mit
   0,85-Rampengewichten → Kraftentwicklungs-/Übungsdetail-Status
   „Wiederaufbau nach Pause" (nicht „Rückschritt"), Live + PDF + Plan-Kontext.
2. push=0/pull=18 → „Nicht bewertbar" (PDF und Live), keine
   Gesundheits-/Balance-Aussage.
3. Muskelgruppe mit 0 Sätzen im 30-Tage-Fenster erscheint in
   „Schwachstellen (Priorität)" vor allen trainierten Gruppen.
4. „Deine Stärken" zeigt bei vorhandener Historie den Fenster-Text, nie den
   Onboarding-Satz.
5. Bei 4W n<30 enthält der Report keine All-Time-Empfehlungszeile mehr;
   die Kontextzeile („Bewertung basiert auf Gesamtzeitraum") bleibt; die
   4W-Kachel ist als eingeschränkt markiert.
6. „Geschätzte Deload-Woche" existiert nicht mehr (Template + Datenpfad).
7. Körperentwicklungs-Bewertung ist deskriptiv; Textregel-Test erzwingt
   das Verbot der wertenden Labels.
8. Pause im Berichtszeitraum → Banner in PDF und Live-Statistik; Heatmap
   markiert Pausentage konsistent zum Volumen-Chart.
9. Ohne dokumentierte Pause und mit gefüllten Fenstern: alle Pfade
   byte-identisch zu vorher (Positivkontrollen in 35.4).
10. Volle Testsuite inkl. `test_chart_generator` + `test_i18n` grün bis auf
    die dokumentierten vorbestehenden Fehler (vor Branch-Start gegen clean
    main gegenverifizieren).

## 6. Risiken, Rest-Hypothesen, Abgrenzung

- **`collect_muscle_balance`-Erweiterung (E3)** verlängert die
  Muskelgruppen-Tabelle im PDF um 0-Satz-Zeilen und ändert die Eingabe von
  `generate_muscle_heatmap`/Body-Map/`collect_push_pull`. Push/Pull ist
  arithmetisch neutral (+0); Chart-Generatoren sind vor Commit auf
  0-Werte-Robustheit zu prüfen (Rest-Hypothese: sie rendern 0-Einträge
  bereits heute korrekt als „grau/leer" – am Code zu verifizieren, sonst
  dort minimal härten).
- **Signatur-Erweiterungen** (`classify_progression_status`,
  `calculate_plateau_analysis`, `generate_training_heatmap`) sind
  default-kompatibel (`None`) – bestehende Aufrufer/Tests unverändert.
- **Erwartete Verhaltensänderung, keine Regression:** Nach Rampenende kann
  bei fortbestehendem Kraftverlust wieder „Rückschritt" erscheinen – dann
  ist es eine wahre Aussage (echtes Detraining), bewusst nicht unterdrückt.
- **Nebenfund außerhalb des Scopes:** `export.py:236` („Handlungsfelder"
  aus All-Time-Junk-Volume) und die `push_pull_balance` im
  `ai_coach/data_analyzer` (LLM-Prompt) sind weitere All-Time-/Degeneriert-
  Konsumenten – dokumentiert, nicht Teil von 35 (Scope-Disziplin).
- **NICHT in Phase 35:** #1060 (PDF-Rendering: mehrzeilige `{# #}`-Kommentare
  werden von Django nicht als Kommentar erkannt, `<pdf:pagenumber/>` ist
  ein xhtml2pdf-Vendor-Tag) → eigener Branch, eigener Fix.

## 7. Reihenfolge & Branch

35.1 → 35.2 → 35.3 → 35.4. Branch `feature/phase-35-report-guards`, Commit
pro Sub-Phase, dieses Konzept-Doc als erster Commit. Kein Merge/PR (macht
der User; Merge = Prod-Deploy). Journal: Entwurf vor Commit, Abschluss
danach, Merge-/Deploy-Eintrag nach dem Merge; vor jedem scope-setzenden
Append Journalstand neu ziehen (Lektion #1061).
