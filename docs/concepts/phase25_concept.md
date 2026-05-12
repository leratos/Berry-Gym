# Phase 25 – Report-Layout-Refactor (Struktur & Technik)

**Status:** 📋 Konzept (11.05.2026) · Offene Fragen F1–F7 entschieden (12.05.2026)
**Vorgänger:** Phase 24 (Report-Daten-Konsistenz) – ✅ inhaltlich abgeschlossen, 24.5b Hotfix noch offen
**Nachfolger:** Phase 26 (Konsolidierungs-Logik), Phase 27 (Style-Overhaul), Phase 28 (Dokumentations-Aktualisierung)
**Branch-Schema:** `feature/phase-25-X-kurzbeschreibung` pro Sub-Phase

> **Scope-Abgrenzung:** Diese Phase adressiert **strukturelle und technische** Layout-Probleme – Pagebreaks, Sektion-Reihenfolge, doppelte Sichten, ToC-Verlinkung, Encoding-Artefakte, Tabellen-Spalten-Priorisierung. **Style-Themen** (Farben, Typografie, allgemeine Optik, Design-Sprache) sind bewusst ausgeklammert und gehören in **Phase 27**. Beide Phasen können getrennt entschieden und entwickelt werden.

Wie bei Phase 24 gilt: Pro Sub-Phase werden Problem, Lösungsansatz, vermutete Dateien, Edge Cases, offene Fragen und Akzeptanzkriterien dokumentiert. Algorithmus-Skizzen und konkrete Markup-Vorschläge erst beim Start jeder Sub-Phase – verhindert, dass früh fixierte Entscheidungen den Spielraum für sinnvolle Refactorings verengen.

---

## 1. Problemanalyse

### 1.1 Ausgangspunkt

Mai-2026-Reports (07.05. und 11.05.) haben gezeigt, dass die Daten-Logik nach Phase 24 sauber arbeitet, das Layout aber an mehreren Stellen Lesbarkeit kostet:

- Sektionen brechen unglücklich um (Header auf einer Seite, Inhalt auf der nächsten)
- Sektion-Reihenfolge folgt nicht der thematischen Gruppierung (z.B. Volumen-Chart unter Push/Pull statt unter Trainingsfortschritt)
- Dieselben Daten erscheinen in mehreren Sichten ohne erkennbare Hierarchie
- Inhaltsverzeichnis ist nicht klickbar
- Encoding-Reste (`■`) erscheinen als Section-Marker, wirken wie Bug
- Charts mit überlappenden X-Achsen-Beschriftungen
- Verlauf-Tabelle in Executive Summary priorisiert BIA-Spalten (BMR, FFMI, Wasser) über stabilere Werte – nicht falsch, aber Platz-ineffizient

### 1.2 Was diese Phase nicht macht

Bewusst ausgeklammert (gehört in Phase 27 Style-Overhaul):

- Farbpalette, Color-Coding-Konventionen
- Typografie (Schriftarten, -größen, -gewichte über die strukturellen Notwendigkeiten hinaus)
- Allgemeine visuelle Sprache (Kartenstil, Schatten, Rundungen, Icons)
- Branding-Elemente
- Chart-Styling (Linien-Farben, Marker-Stile, Hintergründe) über die technische Lesbarkeit hinaus

Die Trennlinie ist nicht immer scharf – im Zweifel wird in dieser Phase entschieden: **Bringt die Änderung die Information besser rüber (Phase 25) oder sieht sie nur schöner aus (Phase 27)?**

### 1.3 Ziel

Strukturell saubere PDF-Ausgabe als stabile Grundlage für den Style-Overhaul in Phase 27. Keine Bug-Fixes, sondern Layout-Hygiene.

---

## 2. Architektur-Skizze

Vermutete zentrale Datei: `core/templates/core/training_pdf_simple.html`. Sektionen werden vermutlich linear gerendert (kein Layout-Engine mit Float/Spalten-Optimierung), Pagebreaks entstehen durch Inhalt + CSS `page-break`-Hinweise.

**Implikation:** Pagebreak-Probleme können meist durch CSS oder gezielte `<div>`-Gruppierung gelöst werden, nicht durch komplettes Template-Umschreiben. Sektion-Reihenfolge ist eine reine Block-Sortierung im Template.

**Cross-Cutting:** Bei jeder Sub-Phase prüfen, ob es eine generische Lösung gibt (z.B. eine Section-Wrapper-Component, die Pagebreak-Verhalten und Header konsistent rendert), statt jede Sektion einzeln zu reparieren.

---

## 3. Tasks

### 3.1 Sub-Phase 25.1 – Sektion-Reihenfolge und thematische Gruppierung

**Status:** 📋 Konzept · **Aufwand:** S · **Reihenfolge:** zuerst

#### Problem

Aktuelle Reihenfolge: Executive Summary → Muskelgruppen → Push/Pull → Trainingsfortschritt → Plateau → Konsistenz → Fatigue → 1RM → RPE → Übungsdetails → Empfehlungen → Zusammenfassung.

Probleme:
- *Trainingsvolumen-Entwicklung* (Chart) steht unter Push/Pull, gehört thematisch zu *Trainingsfortschritt*
- *Plateau-Analyse* und *Übungsdetails* sind durch *Konsistenz / Fatigue / 1RM / RPE* getrennt – obwohl alle drei die gleichen Übungen zeigen
- *Trainer-Empfehlungen* und *Zusammenfassung* überschneiden sich inhaltlich (beide listen Handlungsfelder) und stehen nebeneinander

#### Lösungsansatz

Thematische Gruppen klar trennen:

1. **Status:** Executive Summary
2. **Trainings-Volumen-Sicht:** Muskelgruppen → Push/Pull (mit Volumen-Chart) → Volumen-Entwicklung
3. **Trainings-Fortschritts-Sicht:** Trainingsfortschritt Top 5 → Plateau-Analyse → Übungsdetails Gewichtsverlauf → 1RM/Kraftstandards
4. **Belastungs-Sicht:** Konsistenz → RPE → Fatigue/Deload
5. **Ableitung:** Trainer-Empfehlungen (oder Zusammenfassung – nicht beide)

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html` – Block-Reihenfolge im Template

#### Edge Cases

- **Inhaltsverzeichnis aktuell statisch:** Wenn ToC-Verlinkung (25.4) zeitgleich angegangen wird, kann die ToC-Reihenfolge automatisch aus der Section-Definition generiert werden – Synergie mit 25.4
- **Empfehlungen vs. Zusammenfassung:** Vor dem Refactor entscheiden, ob beide bleiben oder eine entfällt. Aktuell duplizieren sie sich. Empfehlung: Eine bleibt (Empfehlungen, weil konkreter), die andere entfällt. **Frage F1.**

#### Offene Fragen

- F1: Trainer-Empfehlungen oder Zusammenfassung – welche bleibt?
- F2: Sollen Volumen-Chart und Push/Pull-Chart konsolidiert oder getrennt bleiben? Aktuell beide unter Push/Pull-Sektion.

#### Entscheidung (12.05.2026)

- **F1 → Trainer-Empfehlungen bleibt, Zusammenfassung entfällt.** Begründung: Empfehlungen ist mit *Stärken / Schwachstellen (Priorität) / Nächste Schritte* konkreter und handlungsorientiert (nummerierte To-do-Liste). Überlapp `Schwachstellen ≈ Handlungsfelder`. **Migration:** „Top Fortschritte" der bisherigen Zusammenfassung wird als neuer Block ganz oben in den Empfehlungen integriert (vor „Stärken") — keine Information verloren.
- **F2 → Getrennt halten, aber Volumen-Entwicklung aus Push/Pull herauslösen.** Push/Pull-Chart bleibt in Push/Pull-Sektion. Volumen-Entwicklungs-Chart wird zur eigenen H1-Sektion in der Volumen-Gruppe (zwischen Push/Pull und Trainingsfortschritt). Begründung: Die zwei Charts zeigen unterschiedliche Dimensionen (Verhältnis vs. Zeitverlauf), Konsolidierung in ein Chart verliert beides.

#### Akzeptanzkriterien

- Sektionen folgen den fünf thematischen Gruppen
- Keine inhaltlichen Sprünge mehr (z.B. Volumen-Chart in Pull-Sektion)
- Zusammenfassung entfernt; „Top Fortschritte"-Inhalt in Trainer-Empfehlungen migriert (keine Information verloren)
- Volumen-Entwicklungs-Chart hat eigene H1-Sektion (nicht mehr unter Push/Pull)

---

### 3.2 Sub-Phase 25.2 – Pagebreak-Verhalten

**Status:** 📋 Konzept · **Aufwand:** S–M · **Reihenfolge:** nach 25.1

#### Problem

Mai-Reports zeigen:
- Push/Pull-Header auf Seite 6, Inhalt auf Seite 7 (Header ohne Inhalt am Seitenende)
- Ähnliche Brüche bei Plateau-Tabelle (Header auf einer Seite, erste Zeile auf der nächsten)
- Charts werden manchmal von Pagebreak durchschnitten

#### Lösungsansatz

CSS-basierte Pagebreak-Kontrolle:

- `page-break-inside: avoid` auf Sektion-Container und Chart-Wrapper
- `page-break-after: avoid` auf Section-Header (verhindert Header-Waisen am Seitenende)
- `page-break-before: auto` global, gezielte Overrides

**Wenn Section-Wrapper-Component eingeführt wird** (siehe Architektur-Skizze 2): Pagebreak-Regeln zentralisieren statt pro Sektion duplizieren.

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html`
- CSS-Datei für PDF-Rendering (Pfad finden – evtl. inline im Template oder eigene `.css`)

#### Edge Cases

- **Sektion länger als eine Seite:** `page-break-inside: avoid` wirkungslos. Dann besser auf kleinere Sub-Blöcke (z.B. einzelne Übungs-Charts) anwenden.
- **Chart-Beschriftung am Seiten-Ende abgeschnitten:** Eigener Fall, evtl. eigene Sub-Sub-Phase

#### Akzeptanzkriterien

- Keine isolierten Section-Header am Seitenende
- Charts und ihre Beschriftung werden nicht durch Pagebreak getrennt
- Tabellen-Header und mindestens die erste Daten-Zeile auf derselben Seite

---

### 3.3 Sub-Phase 25.3 – Doppelte Sichten konsolidieren

**Status:** 📋 Konzept · **Aufwand:** M · **Reihenfolge:** nach 25.2

#### Problem

Drei Sektionen zeigen denselben Datensatz (Top-Übungen) ohne erkennbare Hierarchie:
- *Kraftentwicklung Top 5* (Trainingsfortschritt) – Tabelle mit Start/Aktuell/Steigerung
- *Plateau-Analyse* – Tabelle mit Letzter PR/Tage her/Rate/Status
- *Übungsdetails Gewichtsverlauf* – Chart pro Übung mit Trend

Inhaltlich überlappen sich Start/Aktuell-Werte und PR-Datum. Der Leser muss zwischen drei Stellen wechseln, um ein vollständiges Bild einer Übung zu bekommen.

#### Lösungsansatz

Drei Optionen:

- **(a) Pro-Übung-Block:** Pro Top-Übung ein konsolidierter Block (Steigerung + Plateau-Status + Chart). Vorteil: alle Infos zur Übung auf einem Blick. Nachteil: Verliert die Quer-Sicht „welche Übung steht am besten/schlechtesten?".
- **(b) Hierarchie schaffen:** Top-5-Tabelle als Übersicht (mit Plateau-Status als Spalte), Plateau-Analyse als separate Sektion entfällt, Übungsdetails-Charts bleiben als Detail-View. Vorteil: Übersicht + Detail klar getrennt. Nachteil: PR-Datum müsste in Top-5-Tabelle integriert werden – mehr Spalten.
- **(c) Plateau-Tabelle entfällt:** Plateau-Status als Spalte in Top-5-Tabelle und als visuelle Annotation in Übungsdetails-Charts. Nachteil: Plateau-Begründung (Rate, Tage seit PR) verliert eigenen Raum.

**Empfehlung:** Variante (b) – Hierarchie. Übersicht (Top 5 mit Plateau-Spalte) → Detail (Übungs-Charts mit Trend). Plateau-Tabelle entfällt, Inhalte werden in beide bestehenden Sichten integriert.

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html` – drei Sektions-Blöcke
- Ggf. Datenaufbereitung im Collector, falls Plateau-Daten nicht heute schon in der Top-5-Struktur zur Verfügung stehen

#### Edge Cases

- **Inkonsistente Übungs-Auswahl:** Top 5 und Plateau-Analyse listen heute potenziell unterschiedliche Übungs-Mengen (z.B. Plateau-Analyse zeigt mehr/weniger als 5). Vor Konsolidierung Schnittmenge prüfen.
- **Status-Vielfalt:** 8 Status-Kategorien (Aktive Progression, Konsolidierung, Plateau, …) müssen in einer einzigen Tabellen-Spalte darstellbar bleiben

#### Offene Fragen

- F3: Welche Variante (a/b/c)?
- F4: Wenn (b): wie viele Spalten verträgt die Top-5-Tabelle, ohne unleserlich zu werden?

#### Entscheidung (12.05.2026)

- **F3 → Variante (b) Hierarchie.** Top-5-Tabelle wird zur Übersicht (inkl. Plateau-Status als Spalte), separate Plateau-Sektion entfällt, Übungsdetails-Charts bleiben als Detail-View. Begründung: (a) verliert die Quer-Sicht (Spitzenreiter vs. Sorgenkind) — für Trainer-Report essentiell. (c) verliert die wertvollen Plateau-Begründungs-Zeilen („RPE sank von X auf Y", „1RM-Drop X% vs. PR").
- **Zusatz zu F3:** Plateau-Begründungs-Zeilen (RPE-Drop, 1RM-Drop, „letzte 4 W nicht trainiert" etc.) wandern als Annotation pro Übung in die Übungsdetails-Charts. Keine Diagnose-Info geht verloren.
- **F4 → Max. 6 Spalten.** Vorschlag-Layout:
  ```
  Übung (mode_label als small darunter) | Start | Aktuell | Steigerung | Letzter PR (vor X Tagen) | Status
  ```
  „Datum" und „Tage her" werden zu einer Zelle (`PR-Datum (vor X Tagen)`) zusammengefasst. „Ø +kg/Monat" wandert zu den Begründungs-Annotationen in Übungsdetails-Charts.

#### Akzeptanzkriterien

- Übungs-Datensatz wird nicht mehr dreifach gezeigt
- Übersicht-Detail-Verhältnis klar erkennbar
- Keine Information verloren (Plateau-Begründungen in Übungsdetails-Charts erhalten)
- Top-5-Tabelle bleibt mit max. 6 Spalten lesbar

---

### 3.4 Sub-Phase 25.4 – Inhaltsverzeichnis verlinken

**Status:** 📋 Konzept · **Aufwand:** S · **Reihenfolge:** nach 25.3

#### Problem

Aktuelles ToC ist statischer Text. Klick auf Eintrag springt nirgendwohin. Bei einem 18-Seiten-Report verliert der Leser viel Zeit beim Suchen.

#### Lösungsansatz

PDF-Bookmarks (interne Links) generieren. Vermutung: Wenn `weasyprint` oder ähnliches eingesetzt wird, reicht `<a href="#section-id">` mit korrespondierenden `id`-Attributen auf Section-Headern. Wenn ein anderer PDF-Renderer (z.B. ReportLab) eingesetzt wird, muss anders gearbeitet werden – beim Implementieren prüfen.

**Zweite Verbesserung:** ToC-Generierung sollte automatisch aus der Section-Definition kommen, nicht hardcoded sein. Heute steht das ToC fest, wenn Sub-Phase 25.1 die Reihenfolge ändert, müsste das ToC manuell mitziehen – Bug-Quelle.

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html` – ToC-Block und Section-Header
- Renderer-Konfiguration (falls Bookmarks separat aktiviert werden müssen)

#### Edge Cases

- **PDF-Reader unterscheiden sich:** Manche zeigen interne Links als Bookmark-Panel, manche als klickbaren Text, manche beides. Akzeptabel ist „klickbarer Text" als Minimum.
- **Section ohne ToC-Eintrag:** Sub-Sections (z.B. Push/Pull innerhalb Muskelgruppen) – ToC nur auf Top-Level oder verschachtelt? Empfehlung: nur Top-Level.

#### Offene Fragen

- F5: Welcher PDF-Renderer wird eingesetzt? Bestimmt, wie Bookmarks generiert werden.
- F6: ToC-Auto-Generierung aus Section-Liste oder weiterhin hardcoded?

#### Entscheidung (12.05.2026)

- **F5 → Renderer ist `xhtml2pdf`** (`requirements.txt:39`, `core/views/export.py:24`, `core/export/pdf_renderer.py:17`) — reportlab-basiert. Implikationen:
  - In-Doc-Links via `<a href="#section-id">` mit korrespondierenden `id`-Attributen auf Section-Headern funktioniert nativ.
  - PDF-Outline-Bookmarks (linker Reader-Panel) via xhtml2pdf-spezifisches `<pdf:outline name="..." level="0">`-Tag.
  - **Empfehlung:** Beides implementieren (In-Doc-Klick + Reader-Bookmark). Kein Renderer-Wechsel nötig.
- **F6 → Auto-generieren.** Eine `sections`-Liste im View-Context (Schema: `[{title, anchor, visible_if}, ...]`), Template iteriert. Löst zwei Probleme:
  1. ToC bleibt nach 25.1-Reihenfolge-Änderung automatisch konsistent.
  2. Die bedingte Nummerierung `{% if exercise_detail_charts %}11{% else %}10{% endif %}` (heute in `training_pdf_simple.html:412-413`) entfällt — Index wird beim Rendern aus der Liste abgeleitet.

  Synergie mit Cross-Cutting Section-Wrapper aus Konzept 5.1: Section-Wrapper liest aus derselben Liste (Header + Anchor-ID + Pagebreak-Verhalten).

#### Akzeptanzkriterien

- ToC-Einträge sind klickbar (In-Doc-Sprung)
- PDF-Outline-Panel zeigt Section-Hierarchie (zusätzlich, falls Reader es darstellt)
- ToC bleibt nach 25.1-Reihenfolge-Änderung automatisch konsistent
- Keine hartkodierten Nummerierungs-Conditionals mehr im Template

---

### 3.5 Sub-Phase 25.5 – Encoding-Artefakte ersetzen

**Status:** 📋 Konzept · **Aufwand:** S · **Reihenfolge:** nach 25.4

#### Problem

Im Report erscheinen mehrfach `■`-Zeichen als Section-Marker (Inhaltsverzeichnis, Section-Header, Listen-Bullets, Status-Indikatoren). Wirkt wie Encoding-Rest, nicht wie absichtliches Design-Element. Beispiel: `■ Executive Summary`, `■ Aktive Progression`.

Vermutung: Hier waren ursprünglich Icons oder Symbol-Glyphen gemeint, die im PDF-Render-Pfad nicht korrekt aufgelöst werden (Font-Substitution, fehlende Unicode-Codepoint-Unterstützung).

#### Lösungsansatz

Zwei Varianten:

- **(a) Echte Icons:** SVG-Inline-Icons oder Icon-Font (z.B. Bootstrap Icons, Lucide) statt Unicode-Glyphen. Setzt voraus, dass der PDF-Renderer Inline-SVG kann.
- **(b) Saubere Unicode-Alternativen:** Bestätigte renderbare Glyphen (z.B. `▸`, `●`, `▪`) – Risiko, dass diese ebenfalls Substitution-Probleme haben.

**Empfehlung (revidiert 12.05.2026):** Wegen des nachgewiesenen Renderers `xhtml2pdf` (siehe F5) ist Inline-SVG **nicht nativ unterstützt** — die ursprünglich favorisierte Variante (a) ist so nicht direkt umsetzbar. Stattdessen:

- **Status-Marker und Section-Marker:** Variante (b) mit verifizierten Unicode-Glyphen (`▶`, `●`, `▪`). Beim Implementieren mit Test-Export prüfen, dass der eingebettete Font diese Glyphen sauber rendert (DejaVu Sans deckt sie typischerweise ab).
- **Branding/Cover-Icons (falls vorhanden):** PNG-Konvertierung via `cairosvg` (Projekt hat den Stack bereits — siehe `core/chart_generator.py` rendert die Muscle-Map-SVG nach PNG für xhtml2pdf).
- **Status-Farben:** Bleiben über CSS-Klassen (`badge-success`/`-warning`/`-danger`/`-info`/`-secondary`) erhalten, unabhängig von der Glyphe.

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html` – alle `■`-Vorkommen
- Statisches Asset-Verzeichnis für SVG-Icons (Pfad finden)
- Status-Klassifikation: Wo werden Status-Labels mit `■` ausgegeben? (Plateau-Tabelle, Trainer-Empfehlungen, Push/Pull-Status)

#### Edge Cases

- **Renderer unterstützt kein Inline-SVG:** Fallback auf saubere Unicode oder PNG-Icons
- **Status-Farben:** Aktuell rot/gelb/grün/grau über die `■`-Glyphe transportiert. Bei Icon-Wechsel muss Farb-Transport sichergestellt sein – ohne Icon-Farbe verliert die Status-Sicht ihre Schnellerfassung.

#### Akzeptanzkriterien

- Keine `■`-Glyphen mehr im Output
- Status-Farben bleiben erhalten
- Renderer-Kompatibilität geprüft

---

### 3.6 Sub-Phase 25.6 – Chart-Achsen-Beschriftung

**Status:** 📋 Konzept · **Aufwand:** S · **Reihenfolge:** nach 25.5

#### Problem

Verlauf-Chart der Körperentwicklung und Hammer-Curls-Chart zeigen überlappende X-Achsen-Datumsbeschriftungen. Bei vielen Datenpunkten werden alle Datums-Labels nebeneinander gerendert und überlagern sich.

#### Lösungsansatz

Standard-Chart-Konfiguration in matplotlib (vermuteter Renderer):
- `tick_params(rotation=45, ha='right')` für gedrehte Beschriftung
- `MaxNLocator` oder `MonthLocator` zur Reduzierung der Tick-Dichte
- Bei sehr vielen Datenpunkten: nur jeder N-te Tick als Label, andere als kleine Markierung

#### Vermutete betroffene Dateien

- Chart-Generierungs-Code in `core/utils/` oder `core/export/`
- Verlauf-Chart Körperentwicklung (Executive Summary)
- Übungs-Charts (Übungsdetails)

#### Edge Cases

- **Sehr kurze Trainings-Historie:** Wenig Datenpunkte, alle Labels passen rein – Auto-Logik muss diesen Fall sauber handhaben (nicht künstlich ausdünnen)
- **Mobile-Ansicht:** Nicht relevant für PDF, aber falls Charts an mehreren Stellen geteilt sind (Dashboard + PDF), Logik vereinheitlichen

#### Akzeptanzkriterien

- Keine überlappenden Datums-Labels in keinem Chart
- Bei kurzer Historie alle Datenpunkte sichtbar gelabelt
- Bei langer Historie sinnvolle Tick-Auswahl (z.B. monatliche Marker)

---

### 3.7 Sub-Phase 25.7 – Verlauf-Tabelle Spalten-Priorisierung

**Status:** 📋 Konzept · **Aufwand:** XS · **Reihenfolge:** zuletzt

#### Problem

Verlauf-Tabelle in Executive Summary zeigt 7 Spalten: Datum, Gewicht, BMI, FFMI, KFA %, Muskeln %, Wasser %, BMR. Vier davon (FFMI, KFA, Muskeln, Wasser, BMR) sind BIA-abgeleitet und für viele Nutzer (insbesondere nach gastrischem Bypass oder anderen physiologischen Edge-Cases) bekannt unzuverlässig. Die zuverlässigsten Werte (Gewicht, BMI) bekommen relativ wenig Platz.

**User-spezifischer Kontext (Lera):** BIA-Werte explizit unzuverlässig, aber für allgemeinen Nutzer nicht zwingend so – Phase 25 macht hier keinen generischen Datenqualität-Hinweis, nur eine Layout-Anpassung.

#### Lösungsansatz

Drei Varianten:

- **(a) Spalten reduzieren:** Nur Gewicht, BMI, KFA %, Muskeln %. BMR und Wasser % entfallen aus Tabelle, bleiben in Detail-Sicht.
- **(b) Zweispalten-Layout:** Stabile Werte (Gewicht, BMI) in einer Tabelle, BIA-Werte in zweiter Tabelle/Block.
- **(c) Status quo lassen:** Layout-Frage ohne klaren Best-Case, vielleicht nicht in Phase 25 priorisieren.

**Empfehlung:** Variante (a). Reduziert kognitive Last, BIA-Werte bleiben aber für interessierte Nutzer in den Detailgrafiken sichtbar.

#### Vermutete betroffene Dateien

- `core/templates/core/training_pdf_simple.html` – Verlauf-Tabelle in Executive Summary

#### Edge Cases

- **Nutzer, die BIA-Werte für ihr Tracking verlassen:** Verlieren mit Variante (a) den Tabellen-Quick-Look. Akzeptabel, weil Detail-Sichten erhalten bleiben.

#### Offene Fragen

- F7: Variante (a) bestätigt oder andere Präferenz?

#### Entscheidung (12.05.2026)

- **F7 → Variante (a) bestätigt, mit leichter Justierung.** Endgültiges Spalten-Set für die Verlauf-Tabelle:
  ```
  Datum | Gewicht | BMI | KFA % | Muskeln % | (Viszeral, conditional)
  ```
  5 Spalten (6 mit Viszeral, wenn `any_viszeral`). Entfernt:
  - **FFMI** — aus Gewicht + KFA ableitbar, eigene Spalte redundant.
  - **Wasser %** — höchste BIA-Unzuverlässigkeit, geringster Nutzwert.
  - **BMR** — berechneter Wert, erscheint bereits in der „Aktuell"-Tabelle (`training_pdf_simple.html:588`).

  KFA und Muskelmasse bleiben (BIA, aber etablierte Tracking-Metriken). Alle entfernten Werte bleiben über die Detail-Sichten / Aktuell-Tabelle weiter sichtbar.

#### Akzeptanzkriterien

- Tabelle bleibt scanbar (max. 6 Spalten inkl. Viszeral)
- Entfernte Werte (FFMI, Wasser %, BMR) bleiben in den Detail-Sichten verfügbar
- Keine Information verloren

---

## 4. Reihenfolge & Begründung

```
25.1 (Reihenfolge) → 25.2 (Pagebreaks) → 25.3 (Doppelte Sichten) → 25.4 (ToC) → 25.5 (Encoding) → 25.6 (Charts) → 25.7 (Tabelle)
```

- **25.1 zuerst:** Sektion-Reihenfolge definiert, wo Pagebreaks überhaupt anfallen können. Erst sortieren, dann Brüche fixen.
- **25.2 als zweites:** Pagebreak-CSS-Regeln werden in der neuen Reihenfolge verifiziert.
- **25.3 nach 25.1+25.2:** Konsolidierung betrifft mehrere Sektionen – einfacher, wenn Reihenfolge schon stabil ist.
- **25.4 nach 25.3:** ToC wird automatisch generiert (idealer Endzustand), also nach der Section-Konsolidierung am stabilsten.
- **25.5, 25.6, 25.7:** Untereinander unabhängig, kein zwingender Vorrang. Vorgeschlagene Reihenfolge folgt absteigender Sichtbarkeit für den Nutzer.

---

## 5. Cross-Cutting Concerns

### 5.1 Section-Wrapper-Component

Wenn 25.1 ohnehin alle Sektionen anfasst, lohnt sich die Einführung einer Section-Wrapper-Component (Template-Include oder Macro), die konsistent rendert:
- Header (mit Icon aus 25.5)
- Pagebreak-Verhalten (aus 25.2)
- ID für ToC-Anker (aus 25.4)

Reduziert Duplikation und verhindert, dass spätere Layout-Änderungen pro Sektion einzeln nachgezogen werden müssen.

### 5.2 Verifikation gegen Lera-Daten

Phase 24 hat gezeigt, dass Bugs erst beim Production-Export sichtbar werden. Phase 25 sollte nach jeder Sub-Phase einen Test-Export generieren und visuell prüfen, bevor die nächste Sub-Phase startet.

### 5.3 Phase 27 (Style) bleibt entkoppelt

Beim Implementieren: keine Style-Entscheidungen mit reinmischen. Wenn ein Pagebreak-Fix nebenbei „eine gute Gelegenheit für eine Farb-Anpassung" wäre – nicht machen, in Phase 27 sammeln.

---

## 6. Offene Fragen Übersicht

Alle Fragen am 12.05.2026 anhand Code-Sichtung entschieden. Details siehe jeweilige Sub-Phase „Entscheidung"-Block.

- ✅ F1 (25.1): **Trainer-Empfehlungen bleibt, Zusammenfassung entfällt** — „Top Fortschritte" wandert in Empfehlungen.
- ✅ F2 (25.1): **Getrennt** — Volumen-Entwicklung wird eigene H1-Sektion, nicht mehr unter Push/Pull.
- ✅ F3 (25.3): **Variante (b) Hierarchie** — Plateau-Begründungen als Annotation in Übungsdetails-Charts erhalten.
- ✅ F4 (25.3): **Max. 6 Spalten** — Schema `Übung | Start | Aktuell | Steigerung | Letzter PR (vor X Tagen) | Status`.
- ✅ F5 (25.4): **`xhtml2pdf`** (reportlab-basiert, bereits im Projekt). Kein Renderer-Wechsel. Links via `<a href="#anchor">` + Bookmarks via `<pdf:outline>`.
- ✅ F6 (25.4): **Auto-generieren** aus `sections`-Liste im Context. Synergie mit Cross-Cutting Section-Wrapper.
- ✅ F7 (25.7): **Variante (a) bestätigt** — Verlauf-Tabelle auf 5–6 Spalten reduziert (FFMI / Wasser % / BMR entfernt).

**Nebeneffekt aus F5 für 25.5:** Inline-SVG ist mit xhtml2pdf nicht nativ möglich — die ursprünglich favorisierte „Variante (a) SVG-Icons" wurde im Lösungsansatz auf Unicode-Glyphen (Status-Marker) + PNG-via-cairosvg (Branding) revidiert.

---

## 7. Status-Updates pro Sub-Phase

*(Wird beim Start und Abschluss jeder Sub-Phase ergänzt.)*
