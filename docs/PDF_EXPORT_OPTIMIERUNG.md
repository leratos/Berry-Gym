# Berry-Gym PDF-Export — Optimierungsplan

Erstellt am 28.03.2026 auf Basis von: PDF-Export `homegym_report_20260328.pdf` (18 Seiten),
Quellcode-Analyse von `core/views/export.py`, `core/chart_generator.py`,
`core/utils/advanced_stats.py`, `core/templates/core/training_pdf_simple.html`.

---

## 1. Ist-Zustand: Architektur

### Tech-Stack
- **Django** Web-App mit `@login_required` Views
- **xhtml2pdf (pisa)** für HTML → PDF Konvertierung
- **matplotlib** (Agg Backend) für Charts (Balken, Linien, Pie, Area)
- **cairosvg** für SVG Muscle-Map → PNG (mit **PIL Fallback** auf Windows)
- **defusedxml** für sichere SVG-Verarbeitung
- Charts werden als **Base64-PNGs** inline im HTML eingebettet

### Schlüssel-Dateien

| Datei | Zeilen | Verantwortung |
|---|---|---|
| `core/views/export.py` | ~1.800 | Haupt-Orchestrator: Daten-Queries, Stats-Berechnung, Chart-Generierung, Template-Rendering, PDF-Response |
| `core/chart_generator.py` | ~800 | matplotlib Charts + SVG Muscle-Map Rendering |
| `core/utils/advanced_stats.py` | ~650 | Plateau-Analyse, Konsistenz, Ermüdungs-Index, 1RM-Standards, RPE-Qualität |
| `core/templates/core/training_pdf_simple.html` | ~2.200 | Aktives Template (Professional Edition) |
| `core/templates/core/training_pdf_v2.html` | ~850 | Ältere V2-Version |
| `core/templates/core/training_pdf.html` | ~500 | Basis-Version |

### Datenfluss

```
export_training_pdf()          [View, Zeile ~700]
  ├── _collect_pdf_stats()     [Zeile ~595] → 40+ Felder aus DB
  │     ├── Trainingseinheit.objects.filter(user, last 30 days)
  │     ├── Satz.objects.filter(exclude warmup/deload)
  │     ├── Top 10 Übungen (Count, Max, Avg, Sum)
  │     ├── Muskelgruppen-Balance (vs. _EMPFOHLENE_SAETZE)
  │     ├── Push/Pull Ratio (mit klinischen Schwellwerten)
  │     ├── RPE-Verteilung
  │     └── Kraft-Progression (erste 3 vs. letzte 3 Sätze)
  │
  ├── calculate_*() aus advanced_stats.py
  │     ├── calculate_consistency_metrics()
  │     ├── calculate_plateau_analysis() → Epley 1RM
  │     ├── calculate_fatigue_index() → 40% Vol + 30% RPE + 30% Freq
  │     ├── calculate_1rm_standards() → Allometrische Skalierung
  │     └── calculate_rpe_quality_analysis()
  │
  ├── _generate_pdf_charts()   [Zeile ~352]
  │     ├── generate_body_map_with_data() → SVG/PIL → Base64 PNG
  │     ├── generate_muscle_heatmap() → matplotlib Balken
  │     ├── generate_volume_chart() → matplotlib Area
  │     ├── generate_push_pull_pie() → matplotlib Pie
  │     └── generate_body_trend_chart() → matplotlib Dual-Axis
  │
  ├── _analyze_weight_loss_context()  [Zeile ~427]
  │     └── Multi-Faktor Muskelabbau-Risiko
  │
  └── _render_training_pdf_response() [Zeile ~335]
        ├── render_to_string('training_pdf_simple.html', context)
        ├── pisa.pisaDocument(html → BytesIO)
        └── HttpResponse(pdf, filename='homegym_report_YYYYMMDD.pdf')
```

---

## 2. Identifizierte Schwachstellen

### A. Architektur & Code

| # | Problem | Datei | Detail |
|---|---|---|---|
| A1 | **export.py ist monolithisch (1.800 Zeilen)** | export.py | Daten-Queries, Stats, Chart-Orchestrierung, Template-Context, PDF-Rendering — alles in einer Datei. |
| A2 | **training_pdf_simple.html ist das größte Template (2.200 Zeilen)** | training_pdf_simple.html | Gesamtes Styling + Layout + Logik in einer Datei. CSS allein ~300 Zeilen. |
| A3 | **Kein Chart-Caching** | export.py, chart_generator.py | Jeder PDF-Export generiert alle 5 Charts neu (~2-4 Sekunden). Kein Caching bei unveränderten Daten. |
| A4 | **3 Template-Varianten parallel gepflegt** | templates/ | `training_pdf.html`, `training_pdf_v2.html`, `training_pdf_simple.html` — Code-Duplikation, nur Simple wird aktiv genutzt. |
| A5 | **cairosvg nicht verfügbar auf Windows** | chart_generator.py | PIL-Fallback erzeugt schematische Ellipsen statt der echten SVG Muscle-Map. Produktions-Server (Linux) nutzt cairosvg. |

### B. Layout & Design (aus PDF-Analyse)

| # | Problem | Impact |
|---|---|---|
| B1 | **18 Seiten mit viel Whitespace** | 1RM-Sektion braucht 4 Seiten für 5 Übungen. Viele halb-leere Seiten. |
| B2 | **Keine Seitennummern** | Bei 18 Seiten keine Navigation möglich. |
| B3 | **Inhaltsverzeichnis ohne Seitenzahlen** | Rein dekorativ, nicht funktional. |
| B4 | **Inkonsistente Sektions-Header** | Manche mit blauem Quadrat, manche mit gelbem + blauem. |
| B5 | **Chart-Legenden überlappen Datenpunkte** | Körperwerte-Trend: Legende über letzten Datenpunkten. |
| B6 | **KW10 fehlt im Volumen-Chart** | Sprung KW09 → KW11 ohne Kennzeichnung. |

### C. Daten & Inhalt

| # | Problem | Impact |
|---|---|---|
| C1 | **Kraftentwicklung: Keine Prozentwerte** | "Gewinn" statt "+318%" — die aussagekräftigste Metrik fehlt. |
| C2 | **Kein Delta zum Vormonat in Executive Summary** | Aktueller Stand ohne Vergleichsbasis. |
| C3 | **RPE-Verteilung nur als Textliste** | Kein Donut/Balken-Chart, obwohl alle anderen Sektionen Charts haben. |
| C4 | **Viszeral-Spalte durchgehend leer** | Spalte "Viszeral" im Körperwerte-Verlauf komplett "-". |
| C5 | **Trainingsvolumen-Chart ohne Trendlinie** | Rohdaten ohne gleitenden Durchschnitt. |
| C6 | **"Tage her = 0" statt "Heute"** | Plateau-Analyse zeigt "0" statt verständlichem Text. |

### D. Technisch/UX

| # | Problem | Impact |
|---|---|---|
| D1 | **Dateiname generisch** | `homegym_report_YYYYMMDD.pdf` ohne Athlet/Zeitraum. |
| D2 | **Kein PDF-Bookmark/Navigation** | Keine klickbaren Links im Inhaltsverzeichnis. |
| D3 | **xhtml2pdf CSS-Limitierung** | xhtml2pdf unterstützt nur CSS 2.1 Subset — viele moderne Layouts nicht möglich. |

---

## 3. Optimierungsplan — 4 Phasen

---

### Phase A: Quick Wins (1-2 Tage)

**Ziel:** Sofortige visuelle und inhaltliche Verbesserung ohne Architektur-Änderungen.

#### A1. Seitennummern einfügen
**Datei:** `training_pdf_simple.html` (CSS `@page`)
```css
@page {
    @bottom-center {
        content: "Seite " counter(page) " von " counter(pages);
        font-size: 8px;
        color: #999;
    }
}
```
**Aufwand:** 15 Minuten

#### A2. Kraftentwicklung: Prozentuale Steigerung
**Datei:** `export.py` → `_collect_pdf_stats()` → `kraft_progression`
- Berechnung existiert bereits teilweise (erste 3 vs. letzte 3 Sätze)
- Neue Spalte: `steigerung_pct = ((aktuell - start) / start * 100)`
- Im Template: Farbkodierung >100%=Gold, >50%=Grün, >20%=Blau
**Aufwand:** 30 Minuten

#### A3. Delta zum Vormonat in Executive Summary
**Datei:** `export.py` → `_collect_pdf_stats()`
- Zusätzliche Query: `KoerperWerte` vom Vormonat
- Delta berechnen: `delta_kfa = aktuell_kfa - vormonat_kfa`
- Im Template: `↑ +0.7%` / `↓ -1.4%` mit Farbe
**Aufwand:** 1 Stunde

#### A4. 1RM-Sektion komprimieren (4 → 2 Seiten)
**Datei:** `training_pdf_simple.html`
- Aktuell: Jede Übung als eigener Block mit viel Padding/Margin
- Optimierung: 2 Übungen pro Seite, kompakteres Layout
- Level-Badge + Fortschrittsbalken inline statt gestapelt
**Aufwand:** 1-2 Stunden

#### A5. Whitespace eliminieren
**Datei:** `training_pdf_simple.html`
- Intelligentere Page-Breaks (`page-break-inside: avoid` statt `page-break-before: always`)
- Sektionen zusammenführen wenn Platz (z.B. Konsistenz + RPE auf einer Seite)
- Ziel: **18 → 12-13 Seiten**
**Aufwand:** 1-2 Stunden

#### A6. Dateiname mit Kontext
**Datei:** `export.py` → `_render_training_pdf_response()` (Zeile ~335)
```python
# Aktuell:
filename = f"homegym_report_{now.strftime('%Y%m%d')}.pdf"
# Neu:
filename = f"TrainingReport_{user.username}_{start:%Y%m%d}_{end:%Y%m%d}.pdf"
```
**Aufwand:** 10 Minuten

#### A7. Viszeral-Spalte bereinigen
**Datei:** `training_pdf_simple.html`
- Wenn alle Werte "-": Spalte aus Tabelle entfernen
- Template-Logik: `{% if any_viszeral %}` → Spalte zeigen
**Aufwand:** 20 Minuten

#### A8. "Tage her" = 0 → "Heute"
**Datei:** `export.py` oder Template
```python
# In Plateau-Analyse:
tage_her = "Heute" if days == 0 else f"{days} Tage"
```
**Aufwand:** 10 Minuten

---

### Phase B: Visuelle Aufwertung (2-3 Tage)

#### B1. RPE-Verteilung als Donut-Chart
**Datei:** `chart_generator.py` — neue Funktion
```python
def generate_rpe_donut(rpe_verteilung: dict) -> str:
    """Donut-Chart: Grün (RPE 7-9), Gelb (<7), Rot (10)"""
```
- Zentral im Donut: Gesamt-Bewertung
- In `_generate_pdf_charts()` aufrufen, Base64 ans Template
**Aufwand:** 2 Stunden

#### B2. Trainingsvolumen-Trend mit gleitendem Durchschnitt
**Datei:** `chart_generator.py` → `generate_volume_chart()`
- Zusätzliche gestrichelte Linie: 4-Wochen-Durchschnitt
- `np.convolve(volumes, np.ones(4)/4, mode='valid')`
**Aufwand:** 30 Minuten

#### B3. Fehlende KW kennzeichnen
**Datei:** `export.py` → `_calc_volume_trend_weekly()`
- Lücken in Kalenderwochen mit 0-Wert füllen statt überspringen
- Im Chart: Gestrichelte Linie für Wochen ohne Training
**Aufwand:** 1 Stunde

#### B4. Chart-Legenden fixen
**Datei:** `chart_generator.py` → `generate_body_trend_chart()`
- `plt.legend(loc='upper left', bbox_to_anchor=(0, 1.15))` → Legende über dem Chart
- Einheitliche Position für alle Charts
**Aufwand:** 30 Minuten

#### B5. Konsistente Sektions-Header
**Datei:** `training_pdf_simple.html`
- Einheitliches Pattern: `■ Sektionsname` mit blauer Linie
- Alle Header gleich formatieren (aktuell 2 verschiedene Styles)
**Aufwand:** 30 Minuten

#### B6. Inhaltsverzeichnis mit Seitenzahlen
**Datei:** `training_pdf_simple.html`
- xhtml2pdf unterstützt `<pdf:toc />` nativ
- Alternativ: Manuelle Nummerierung basierend auf bekannter Seitenstruktur
**Aufwand:** 1-2 Stunden (xhtml2pdf TOC-Feature testen)

#### B7. Vormonat-Vergleich visuell
**Datei:** Template + export.py
- Mini-Pfeile (▲▼) neben jedem Wert in der Executive Summary
- Farbkodiert: Grün = Verbesserung, Rot = Verschlechterung (kontextabhängig)
**Aufwand:** 1 Stunde

---

### Phase C: Architektur-Refactoring (2-3 Tage)

**Ziel:** export.py von 1.800 auf ~400 Zeilen pro Modul reduzieren.

#### C1. export.py aufteilen

```
core/views/export.py           (~400 → View-Funktionen + Routing)
core/export/                   [NEU]
  ├── __init__.py
  ├── pdf_renderer.py          (HTML → PDF Konvertierung, ~100 Zeilen)
  ├── stats_collector.py       (_collect_pdf_stats + Helpers, ~400 Zeilen)
  ├── chart_orchestrator.py    (_generate_pdf_charts + Context-Building, ~100 Zeilen)
  ├── weight_analysis.py       (_analyze_weight_loss_context, ~100 Zeilen)
  └── constants.py             (_EMPFOHLENE_SAETZE, Push/Pull Groups, ~50 Zeilen)
```

**Begründung:**
- Jedes Modul unter 400 Zeilen
- `stats_collector.py` separat testbar ohne Django-Request
- `constants.py` zentral und wiederverwendbar
**Aufwand:** 1 Tag

#### C2. Alte Templates aufräumen
- `training_pdf.html` und `training_pdf_v2.html` archivieren oder löschen
- Nur `training_pdf_simple.html` als aktives Template behalten
- Template in Partials aufteilen: `_pdf_cover.html`, `_pdf_executive.html`, etc.
**Aufwand:** 2 Stunden

#### C3. Chart-Caching einführen
**Datei:** `chart_orchestrator.py`
```python
from django.core.cache import cache

def _get_or_generate_chart(cache_key, generator_fn, *args, ttl=3600):
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = generator_fn(*args)
    cache.set(cache_key, result, ttl)
    return result
```
- Cache-Key: `pdf_chart_{user_id}_{chart_type}_{date_hash}`
- Invalidierung: Bei neuem Training-Log
- Erwartete Speedup: **~60% schnellere PDF-Generierung**
**Aufwand:** 2 Stunden

---

### Phase D: Neue Features (3-5 Tage)

#### D1. Wochen-Heatmap (GitHub-Contribution-Style)
- Kalender-Grid: 7 Reihen (Mo-So) × N Wochen
- Farbe = Trainingsintensität
**Aufwand:** 3-4 Stunden

#### D2. Übungsdetail-Seiten (konfigurierbar)
- Pro Top-5-Übung: Gewichtsverlauf als Linien-Chart
- Konfigurierbar: `include_exercise_details=True/False`
**Aufwand:** 4-6 Stunden

#### D3. PDF-Bookmarks / Interaktivität
- xhtml2pdf unterstützt Bookmarks via `<pdf:bookmark />`
- Jede Sektion als navigierbares Lesezeichen
**Aufwand:** 1-2 Stunden

#### D4. Zusammenfassungs-Seite
- Letzte Seite: 1-Page-Summary
- Die 3 größten Fortschritte + Die 3 wichtigsten Handlungsfelder
**Aufwand:** 2 Stunden

#### D5. WeasyPrint als Alternative evaluieren
**Begründung:** xhtml2pdf ist auf CSS 2.1 limitiert. WeasyPrint (bereits im venv!) unterstützt:
- CSS3 (Flexbox, Grid)
- Bessere Schriftarten-Unterstützung
- Native PDF-Bookmarks
**Aufwand:** 1 Tag (Proof-of-Concept)

---

## 4. Zusammenfassung

| Phase | Name | Aufwand | Impact | Dateien |
|---|---|---|---|---|
| **A** | Quick Wins | 1-2 Tage | ★★★★★ | export.py, training_pdf_simple.html |
| **B** | Visuelle Aufwertung | 2-3 Tage | ★★★★ | chart_generator.py, training_pdf_simple.html |
| **C** | Architektur-Refactoring | 2-3 Tage | ★★★★ | export.py → core/export/ |
| **D** | Neue Features | 3-5 Tage | ★★★ | Alle |

**Empfohlene Reihenfolge:** A → B → C → D

**Phase A allein (1-2 Tage) bringt:**
- 18 → 12 Seiten (kompakter, professioneller)
- Prozentuale Kraftsteigerung (die wichtigste fehlende Metrik)
- Vormonats-Deltas (Report wird "actionable")
- Seitennummern + besserer Dateiname (Basics die fehlen)

**Phase C (Refactoring) ist der wichtigste technische Hebel:**
- export.py von 1.800 → 5 Module à ~100-400 Zeilen
- Ermöglicht isoliertes Testen der Stats-Berechnung
- Chart-Caching spart ~60% Generierungszeit

**Bonus-Insight: WeasyPrint liegt bereits im venv!**
Ein Wechsel von xhtml2pdf zu WeasyPrint würde CSS3, bessere Fonts und native Bookmarks
ermöglichen — ohne neue Dependency.

---

*Analyse erstellt mit Claude Opus 4.6 auf Basis von:
Quellcode (export.py ~1.800 LOC, chart_generator.py ~800 LOC, advanced_stats.py ~650 LOC,
training_pdf_simple.html ~2.200 LOC), PDF-Export vom 28.03.2026, Projektarchitektur-Review.*
