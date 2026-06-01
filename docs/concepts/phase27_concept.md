# Phase 27 – Style-Konzept (Style-Overhaul)

**Status:** ✅ Style-Decisions getroffen (30.05.2026) · bereit für Umsetzung durch Claude Code
**Rolle dieses Docs:** Single Source of Truth für alle Style-Tokens. Sub-Phasen 27.2–27.6 setzen *nur* die hier festgelegten Werte um — keine neuen Farben/Größen erfinden.
**Pipelines:** (1) **LIVE** = Bootstrap 5.3.3 + Chart.js (dark-first, Light-Toggle). (2) **PDF** = xhtml2pdf/pisa + matplotlib (immer hell, druckbar).

> **Konvention in diesem Doc:** Jede Entscheidung trägt einen Parität-Tag:
> · **[= identisch]** — in beiden Pipelines pixel-/wert-gleich umsetzbar.
> · **[≈ angenähert]** — gleiche Designabsicht, kleine technische Differenz (z. B. Helligkeit auf dunklem vs. hellem Grund).
> · **[PDF-Abweichung: …]** — Feature, das xhtml2pdf nicht kann; mit Ersatzlösung.

---

## 0. Markenrichtung (Ergebnis der Decision-Session)

| Entscheidung | Wahl |
|---|---|
| Identität | Freier Neu-Entwurf, nur Name „Berry-Gym" |
| Akzent-Richtung | **Berry / Plum** (Swatch 2) |
| Grundstimmung | Dark-first live, Light als Toggle; PDF immer hell |
| Charakter | **Premium / edel, zurückhaltend** |
| Status-Schema | Komplett neu (in diesem Doc definiert) |
| S/W-Druck | **Pflicht** — Status ohne Farbe lesbar (Form + Label) |
| Dichte | Ausgewogen |
| Karten | Subtiler Schatten live / Border im PDF |

> ✅ **Akzent-Hex bestätigt:** **Berry-Plum `#8A2B66`** (verfeinerte Swatch-2-Richtung — druck- & dark-tauglich, distinct von Gefahr-Rot). Token `--berry-600`.

**Design-Leitidee:** Berry trägt die Marke *sparsam* (Buttons, Links, Primär-Serie, Cover-Titel, eine Akzentkante). Den Rest macht ein **warm-neutrales Grau** (kein Bootstrap-Kaltgrau) — das ist der „edel/zurückhaltend"-Hebel. Berry ist ein warmer Ton, warme Neutrale harmonieren damit besser als die kühlen Defaults.

---

## A) Farbpalette als Tokens

### A.1 Marken-Rampe „Berry"

| Token | Hex | RGB-Triplet | Einsatz |
|---|---|---|---|
| `--berry-900` | `#4A1638` | 74,22,56 | Tiefster Ton, optional H1 auf Weiß |
| `--berry-700` | `#6D2150` | 109,33,80 | Aktiv/Hover, Border-Akzent |
| **`--berry-600`** | **`#8A2B66`** | **138,43,102** | **PRIMARY** — Buttons, Links (light/PDF), Primär-Serie, Cover-Titel |
| `--berry-400` | `#B85C90` | 184,92,144 | Sekundär-Akzent, Tints |
| `--berry-300` | `#D981B0` | 217,129,176 | **Akzent auf Dunkel** (Links/Charts im Dark-Theme, AA-fest) |
| `--berry-100` | `#F0D6E5` | 240,214,229 | Border feiner Tint |
| `--berry-050` | `#F9EDF4` | 249,237,244 | Subtile Füllung (PDF-Infobox „berry") |

**[≈ angenähert]** Primary-Fill `#8A2B66` mit weißer Schrift funktioniert auf *beiden* Hintergründen (Kontrast ≈ 8:1, AAA). Für *Text-Links auf dunklem Grund* nutzen wir `--berry-300` (AA bei ≥ 0.85rem), für Text-Links auf Weiß/PDF `--berry-700`. Diese Helligkeits-Differenz ist die einzige Abweichung und ist beabsichtigt (Lesbarkeit).

### A.2 Status-Palette (neues Schema) → Bootstrap-Semantik-Slots

Fünf Slots, je ein **Kern-Hex** (für PDF/Weiß-Grund & matplotlib), ein **On-Dark-Hex** (Live-Dark) und die für Bootstrap-Utilities nötigen `-rgb`-Triplets. Töne sind bewusst leicht entsättigt (premium), aber signalstark. **Luminanz wurde gestaffelt** (Amber hell → Grün mittel → Rot dunkel), damit Grün/Rot in S/W *nicht* verschmelzen.

| Slot (semantisch) | Kern-Hex (PDF/Light) | `--bs-{slot}-rgb` | On-Dark-Hex (Live) | Textfarbe auf Fill | Bedeutung |
|---|---|---|---|---|---|
| `success` | `#2F7D5B` | 47,125,91 | `#4FB286` | `#FFFFFF` | Progression / optimal |
| `warning` | `#CF9116` | 207,145,22 | `#E0A93D` | **`#1F2226`** (dunkel!) | Beobachten / untertrainiert |
| `danger` | `#A82E22` | 168,46,34 | `#E0685C` | `#FFFFFF` | Plateau / Rückschritt / übertrainiert |
| `info` | `#2C6E9B` | 44,110,155 | `#5AA0CE` | `#FFFFFF` | Konsolidierung / neutrale Metrik |
| `secondary` | `#6B6660` | 107,102,96 | `#A39C93` | `#FFFFFF` | Pause / inaktiv |

**[= identisch]** Kern-Hex gilt für PDF-Badges (`.badge-success` …), die `bg-{{ status_farbe }}`-if-Kette und die matplotlib-Charts.
**[≈ angenähert]** Live-Dark hebt jeden Ton auf `On-Dark-Hex` an, damit Badges/Linien auf `#212529` AA erreichen. Im Light-Theme & PDF gilt der Kern-Hex.
**[= identisch]** **WCAG:** alle Fills mit weißer Schrift ≥ 4.5:1 (AA). **Ausnahme `warning`:** Amber braucht *dunkle* Schrift `#1F2226` (so wie heute schon `.badge-warning{color:#333}`). Bitte beibehalten.

**Bootstrap-Override (CDN, kein SCSS-Build) — gehört in `theme-styles.css`:**
```css
:root{
  --bs-primary:#8A2B66;       --bs-primary-rgb:138,43,102;
  --bs-success:#2F7D5B;       --bs-success-rgb:47,125,91;
  --bs-warning:#CF9116;       --bs-warning-rgb:207,145,22;
  --bs-danger:#A82E22;        --bs-danger-rgb:168,46,34;
  --bs-info:#2C6E9B;          --bs-info-rgb:44,110,155;
  --bs-secondary:#6B6660;     --bs-secondary-rgb:107,102,96;
}
[data-bs-theme="dark"]{
  --bs-primary:#B85C90;       --bs-primary-rgb:184,92,144;   /* hellerer Akzent auf Dunkel */
  --bs-link-color:#D981B0;    --bs-link-hover-color:#E7A9C8;
}
```
> Hinweis: Bootstrap-Utilities (`.bg-success`, `.text-warning`, …) lesen die `-rgb`-Tripel — beide Werte (Hex *und* RGB) müssen gesetzt sein, sonst greift der Override nicht.

### A.3 matplotlib-Palette (PDF-Charts, weißer Grund)

Identisch zu den Kern-Hex aus A.2 (kein zweites Schema pflegen):
```python
STATUS = {
    "success":"#2F7D5B", "warning":"#CF9116", "danger":"#A82E22",
    "info":"#2C6E9B", "secondary":"#6B6660",
}
PRIMARY = "#8A2B66"
```
**Kategorische Serie** (z. B. 12 Muskelgruppen — ersetzt den zufälligen Bootstrap-Regenbogen durch eine gedämpfte Marken-Reihe, zyklisch):
```python
CATEGORICAL = ["#8A2B66","#B85C90","#2C6E9B","#5AA0CE",
               "#2F7D5B","#6B8E4E","#CF9116","#6B6660"]
```
**Sequentielle Rampe** für Intensitäts-Heatmaps (niedrig→hoch), löst das alte Grau→Reinrot ab durch **Neutral→Berry** (S/W-tauglich, weil rein über Helligkeit):
```python
# LinearSegmentedColormap "berry", low→high:
BERRY_SEQ = ["#ECE9E6", "#E2B9D0", "#C26A9C", "#8A2B66"]
```
**[= identisch]** Live nutzt dieselben Hex (Chart.js bekommt `STATUS`/`CATEGORICAL` als JS-Konstanten; die SVG-Body-Map interpoliert `#ECE9E6`→`#8A2B66` statt `#d9d9d9`→`#ff0000`).

### A.4 Neutrale (Chrome)

| Rolle | Dark-Theme (Live) | Light-Theme & PDF |
|---|---|---|
| App-/Body-BG | `#1A1D21` / `#212529` | `#F7F6F4` (live) / `#FFFFFF` (PDF) |
| Surface (Card) | `#2B3035` | `#FFFFFF` |
| Border | `#3A4047` | `#E2DFDA` |
| Text primär | `#F2F2F0` (warm-weiß) | `#1F2226` |
| Text muted | `#A8A29A` | `#6B6660` |
| „Nicht trainiert"-Grau (Map) | `#D6D3CE` | `#D6D3CE` |

**[≈ angenähert]** Warme Neutrale (`#F7F6F4`, `#E2DFDA`, `#6B6660`) ersetzen Bootstraps Kaltgrau (`#f8f9fa`, `#dee2e6`, `#6c757d`). Live über `theme-styles.css`, PDF über die `<style>`-Werte — gleiche Hex, daher visuell identisch.

### A.5 S/W-Druck-Strategie

**[PDF-Abweichung: Farbe darf nicht alleiniger Träger sein]** Jeder Status wird **doppelt kodiert**: Farbe **+** Form-Glyph **+** Textlabel (siehe C). Zusätzlich:
- **Body-Map (matplotlib, kategorisch): selektives Hatching** — nur die **Handlungs-Status** bekommen Textur, damit das Cover-Bild ruhig/premium bleibt und die Schraffur als *Aufmerksamkeits-Lenker* dient: `übertrainiert` = `'///'`, `untertrainiert` = `'...'`, `optimal` = **solid** (ruhig), `inaktiv` = **blank/hell** (tritt zurück). So ist S/W eindeutig *und* der Blick wird auf die Bereiche gezogen, wo gehandelt werden muss. Legende behält Farbe + Label.
- **Status-Balken-Charts** (`muskelSollChart` etc.): in matplotlib `hatch=` pro Status; in Chart.js zusätzlich `borderColor`/`borderWidth` als Form-Hilfe.
- Luminanz-Staffel (A.2) sorgt dafür, dass selbst ohne Hatch Grün/Amber/Rot in Graustufen unterscheidbar bleiben.

---

## B) Typografie

**Entscheidung (war „decide for me"): Adobe-Source-Superfamilie** — eine editoriale Serife für Headings (premium/edel) + humanistische Sans für Body/Daten. Beide sind Open-Source, als **TTF in xhtml2pdf registrierbar**, und bilden live wie PDF dieselbe Hierarchie ab. (Bewusst **nicht** Inter/Roboto/Arial/Fraunces.)

| Rolle | Familie | Live-Stack | PDF-Stack (registriert) |
|---|---|---|---|
| Display / Headings | **Source Serif 4** | `'Source Serif 4', Georgia, 'Times New Roman', serif` | TTF `SourceSerif4-SemiBold/Bold`; Fallback `Georgia` |
| Body / UI / Daten | **Source Sans 3** | `'Source Sans 3', -apple-system, 'Segoe UI', sans-serif` | TTF `SourceSans3-Regular/SemiBold`; Fallback `Helvetica` |

**[PDF-Abweichung: Fonts müssen registriert werden]** In `chart_generator.py` und im PDF-View die vier TTFs via `pisa`/ReportLab registrieren (`@font-face` im PDF-`<style>` **und** `pdfmetrics.registerFont` für matplotlib). Werden sie nicht ausgeliefert, greift der Fallback-Stack (Georgia/Helvetica) — Layout bleibt stabil, nur die Anmutung ist generischer.

### Hierarchie & Größen

| Ebene | Live | PDF | Parität |
|---|---|---|---|
| Stat-Value (Kennzahl) | Sans, 2.0rem / 700, tabular-nums | 28px / 700 | **[= identisch]** Rolle |
| Cover-Titel | — | Serif, 32px / 700, `--berry-600` | PDF-only |
| H1 (Sektion) | Serif, 1.5rem / 600 | Serif, 18px / 700, `--berry-600`, Border-bottom 2px berry | **[≈]** PDF etwas kompakter (Druckdichte) |
| H2 | Serif, 1.25rem / 600 | Serif, 13px / 600, Border-bottom 1px `#E2DFDA` | **[≈]** s. o. |
| H3 | Sans, 1.0rem / 600 | Sans, 11px / 600 | **[= identisch]** |
| Body | Sans, 0.95rem / 400, lh 1.5 | 10px / 1.5 | **[≈]** PDF-Basisgröße kleiner (Print) |
| Caption / muted | Sans, 0.8rem | 8px | **[≈]** |
| Stat-Label | Sans, 0.7rem, UPPERCASE, ls 1px | 9px UPPERCASE | **[= identisch]** Stil |

**[PDF-Abweichung: keine `rem`]** xhtml2pdf rechnet in `pt/px` — PDF-Größen sind in px fix angegeben (die Staffel ist proportional zur Live-rem-Skala, nur in Print-Dichte). Markiert als **[≈]**, weil Hierarchie-Verhältnis erhalten bleibt.

---

## C) Icon- & Glyph-Strategie

**Entscheidung (war „decide for me"): Geometrische Unicode-Glyphen + Label** als PDF-Ersatz für Emoji; live bleiben **Bootstrap-Icons**. Die Glyphen sind so gewählt, dass jeder Status eine **eigene Form** hat → S/W- und farbblind-tauglich. **Emoji werden in beiden Pipelines entfernt.**

| Bedeutung | Slot | Live (Bootstrap-Icon) | PDF-Glyph | Alt-Emoji (entfällt) |
|---|---|---|---|---|
| Aktive Progression | success | `bi-graph-up-arrow` | `▲` | ✅ 📈 |
| Optimal / Normal | success | `bi-check-circle-fill` | `●` | ✅ |
| Beobachten | info | `bi-eye` | `○` | 👀 |
| Konsolidierung | info | `bi-arrow-left-right` | `◇` | 💪 |
| Leichtes Plateau / Erhöht | warning | `bi-dash-circle` | `◆` | ⚠️ |
| Plateau | danger | `bi-exclamation-triangle-fill` | `■` | 🔴 |
| Langzeit-Plateau / Hoch | danger | `bi-x-octagon-fill` | `✕` | ❌ |
| Rückschritt | danger | `bi-graph-down-arrow` | `▼` | ⚠️ |
| Pause / inaktiv | secondary | `bi-pause-circle` | `‖` | ⏸️ |
| Primär-Karte (Hervorhebung) | — | `bi-star-fill` | `★` | ★ (ok) |
| Delta hoch / runter | — | `bi-caret-up/down-fill` | `▲ / ▼` | ▲▼ (ok) |

**[≈ angenähert]** Gleiche Semantik, andere Glyphen-Form (Icon-Font live, Unicode-Geometrie im PDF). Beide tragen **immer** das Textlabel daneben — die Form ist Redundanz, kein alleiniger Informationsträger.
**[= identisch]** `★ ▲ ▼ ● ■ ◆ ◇ ○ ✕ ‖` sind in den Standard-PDF-Fonts (Helvetica/Source Sans) vorhanden und rendern in xhtml2pdf zuverlässig — **keine Emoji-Codepoints** mehr.

---

## D) Karten / Komponenten

Karten-Entscheidung: **subtiler Schatten live / 1px-Border im PDF.** Akzent-Border-links bleibt das Leitmotiv **nur** für Callout-Boxen (Info/Warnung/Empfehlung), nicht für jede Card — das hält es ruhig.

| Token | Live | PDF | Parität |
|---|---|---|---|
| Spacing-Skala | 4 · 8 · 12 · 16 · 24 · 32 px | identisch | **[= identisch]** |
| Card-Padding | 16px (Body 16–20) | 12–15px | **[≈]** Druckdichte |
| Radius Card | 10px | 0–2px | **[PDF-Abweichung: `border-radius` kaum unterstützt → eckig]** |
| Radius Badge/Button | 6px / 8px | 0px | **[PDF-Abweichung: eckig]** |
| Erhebung | `box-shadow:0 1px 3px rgba(20,15,18,.10)` (light) / `…rgba(0,0,0,.30)` (dark) | **kein Schatten** → `1px solid var(--border)` | **[PDF-Abweichung: kein `box-shadow` → Border-Ersatz]** |
| Callout-Box | `border-left:4px solid {status}` + Tint-BG (`--berry-050`/`success-050`…) | identisch (border-left geht in xhtml2pdf) | **[= identisch]** |
| Tabellen | Header-BG `--berry-600`, Zebra `#F7F6F4`, Border `#E2DFDA` | identisch; Header-Repeat via `repeat="1"` | **[= identisch]** (Live: `table` Theme-aware) |
| Progress-Bar | Track `#E2DFDA`, Fill `{status}` | identisch (Block-Element) | **[= identisch]** |

**[PDF-Abweichung: kein Flexbox/Grid]** Live-Layouts mit `d-flex`/`row g-*` werden im PDF wie bisher über `display:table`/`table-cell` (z. B. `.stats-grid`) nachgebaut. Style-Tokens (Farben/Border/Padding) sind identisch, nur der Layout-Mechanismus unterscheidet sich — das ist Struktur (Phase 25), hier nicht erneut angefasst.

---

## E) Charts (Chart.js ↔ matplotlib gleich aussehen lassen)

Gemeinsame Regeln, damit Live- und PDF-Charts als „dieselbe Familie" lesen:

| Aspekt | Chart.js (Live) | matplotlib (PDF) | Parität |
|---|---|---|---|
| Daten-Farben | `STATUS` / `CATEGORICAL` / `PRIMARY` (A.2/A.3) | identische Hex | **[= identisch]** |
| Primär-Serie (Volumen/Progression) | `#D981B0` (auf Dunkel) | `#8A2B66` (auf Weiß) | **[≈]** Helligkeit für Lesbarkeit je Grund |
| Flächenfüllung | Berry/Status bei **α 0.10** | `alpha=0.10` | **[= identisch]** |
| Gridlines | `#3A4047` (dark) | `#E2DFDA` | **[≈]** je Hintergrund |
| Achsen-/Tick-Text | `#A8A29A` (dark) | `#6B6660` | **[≈]** je Hintergrund |
| Font | `Source Sans 3` (`Chart.defaults.font.family`) | registrierte TTF, sonst Helvetica | **[≈]** Fallback im PDF |
| Spines/Rahmen | nur Achsen, top/right aus | `ax.spines['top'/'right'].set_visible(False)` | **[= identisch]** Absicht |
| Marker | Kreis r4; Deload = `warning` hohl + gestrichelt | Kreis; Deload = `warning` hohl + `--` | **[= identisch]** Absicht |
| Hintergrund | transparent | `figure/axes facecolor white` | **[≈]** Grund unterscheidet sich konzeptbedingt |
| S/W-Sicherung | Status-Balken + `borderColor` | Status-Balken + `hatch` (A.5) | **[≈]** |

> **Vorrang-Regel (aus Phase-27-Scope):** Technische Lesbarkeit schlägt Konsistenz. Wenn eine „schönere" Berry-Linie schlechter lesbar ist als das alte Grün, gewinnt Lesbarkeit — dann den **Kern-Hex** des passenden Status nutzen, nicht Berry.

**Konkrete Defaults — `chart_generator.py` (matplotlib rcParams):**
```python
rcParams.update({
  "figure.facecolor":"#FFFFFF", "axes.facecolor":"#FFFFFF",
  "axes.edgecolor":"#E2DFDA", "axes.linewidth":0.8,
  "axes.grid":True, "grid.color":"#E2DFDA", "grid.linewidth":0.6,
  "axes.spines.top":False, "axes.spines.right":False,
  "text.color":"#1F2226", "axes.labelcolor":"#6B6660",
  "xtick.color":"#6B6660", "ytick.color":"#6B6660",
  "font.family":"Source Sans 3", "figure.dpi":150,
})
```
**Live — `training_stats.html` `chartDefaults`:** `legend/tick color → #A8A29A`, `grid.color → #3A4047`, `Chart.defaults.font.family = 'Source Sans 3'`, Primär-Serie `#D981B0`, Deload-Marker → neue `warning`-Werte.

---

## F) Sub-Phasen-Aufteilung (Umsetzungs-Reihenfolge für Claude Code)

Reihenfolge folgt der Abhängigkeitskette **Tokens → Chrome → Live-Templates → PDF → Charts**. Jede Sub-Phase = eigener Branch `feature/phase-27-X-…`, je ein Production-Export zur Sicht-Kontrolle danach.

### 27.1 — Token-Fundament (dieses Doc)
**Aufwand:** erledigt · kein Code.
Dieses Konzept ist die Referenz. *Gate:* Akzent-Hex-Rückfrage (Abschnitt 0) bestätigt, bevor 27.2 startet.
**Dateien:** `docs/concepts/phase27_concept.md`

### 27.2 — Farb-Tokens & Bootstrap-Override
**Aufwand:** S · **[= identisch]** Kern-Hex; **[≈]** Dark-Akzent.
`:root`- und `[data-bs-theme]`-Variablen aus A.2/A.4 setzen; alle hartkodierten Bootstrap-Hex (`#0d6efd`, `#198754`, `#28a745`, `#17a2b8`, `#ffc107`, `#dc3545`, `#6c757d`, `#0dcaf0`) auf Tokens umstellen. Warme Neutrale ersetzen Kaltgrau. **Keine** neuen Farben.
**Dateien:** `core/static/core/css/theme-styles.css` · *(Verifikation:)* `base.html` (`theme-color`-Meta), `global_header/footer.html`

### 27.3 — Typografie
**Aufwand:** S–M · **[PDF-Abweichung: Font-Registrierung]**.
Source-Serif-4-/Source-Sans-3-Webfonts laden (self-hosted, kein CDN-Risiko); Heading-Serife + Body-Sans als CSS-Variablen; Größen-/Gewichts-Staffel aus B. TTFs ins Static-Verzeichnis für die PDF-Registrierung legen.
**Dateien:** `core/static/core/css/theme-styles.css`, `base.html` (Font-Preload/`@font-face`), `core/static/core/fonts/*` (neu)

### 27.4 — Icon-/Glyph-Set
**Aufwand:** S–M · **[≈]** Form, **[= identisch]** Semantik.
Live: einheitliche Bootstrap-Icons je Status (Tabelle C). PDF: Emoji in `status_label`/Legenden durch Unicode-Glyphen ersetzen; Status-Legenden synchronisieren. Baut auf Phase 25.5 (Encoding) auf.
**Dateien:** `training_stats.html`, `training_pdf_simple.html`, ggf. `core/*` wo `status_label`/`status_farbe` erzeugt werden (View/Helper), Legenden-Includes

### 27.5 — Karten, Boxen & Tabellen
**Aufwand:** S–M · **[PDF-Abweichung: kein shadow/radius]**.
Karten-Stil (Schatten live / Border PDF), Callout-Boxen (Info/RPE/Plateau/Warnung) auf **ein** Schema (border-left + Tint), Tabellen-Header auf `--berry-600`, Spacing/Radius-Tokens. Progress-Bars auf Status-Tokens.
**Dateien:** `theme-styles.css`, `training_stats.html`, `training_pdf_simple.html`

### 27.6 — Chart-Styling (live + PDF)
**Aufwand:** M · **[≈]** je Hintergrund, **[= identisch]** Datenfarben.
matplotlib-`rcParams` + Status-/Kategorie-/Sequenz-Paletten + Hatch (S/W); Chart.js-`chartDefaults` + Farbkonstanten + Body-Map-Interpolation Neutral→Berry. Vorrang-Regel (Lesbarkeit) beachten.
**Dateien:** `core/chart_generator.py`, `training_stats.html` (Inline-Chart-Skripte), `core/static/core/images/muscle_map.svg` (Default-Füllung)

---

## G) Betroffene Dateien — Gesamtübersicht

| Datei | 27.2 | 27.3 | 27.4 | 27.5 | 27.6 |
|---|:-:|:-:|:-:|:-:|:-:|
| `core/static/core/css/theme-styles.css` | ● | ● | | ● | |
| `templates/.../base.html` | ○ | ● | | | |
| `core/static/core/fonts/*` (neu) | | ● | | | |
| `training_stats.html` (Live) | ○ | ○ | ● | ● | ● |
| `training_pdf_simple.html` (PDF) | ○ | ○ | ● | ● | |
| `core/chart_generator.py` | | ○ | ○ | | ● |
| `core/static/core/images/muscle_map.svg` | | | | | ● |
| Status-Helper/View (`status_farbe`/`label`) | | | ● | | |
| `global_header.html` / `global_footer.html` | ○ | | | ○ | |

● = primär geändert · ○ = berührt/zu verifizieren

---

## H) Akzeptanzkriterien (ergänzt)

- Alle Hex/Größen aus A–E sind als Tokens umgesetzt; **kein** hartkodierter Bootstrap-Default mehr im Live- oder PDF-Pfad.
- Status ist in **S/W** allein über Form + Label erkennbar (Druck-Test einer Beispielseite).
- WCAG-AA für alle Status-Fills (weiße Schrift; Amber = dunkle Schrift).
- Keine Emoji mehr im PDF; Glyphen rendern in xhtml2pdf zuverlässig.
- Live- und PDF-Charts lesen als dieselbe Familie (Farbe/Font/Grid/Spines).
- Jede `[PDF-Abweichung]` ist mit dokumentierter Ersatzlösung umgesetzt.
- User-Eindruck (Lera): deutlich kohärenter & „premium" gegenüber Vor-Phase-27.

---

## I) Entscheidungen — alle bestätigt ✅

1. ✅ **Akzent-Hex:** Berry-Plum `#8A2B66` (Abschnitt 0).
2. ✅ **Webfonts self-hosten:** ja (Source Serif 4 + Source Sans 3 lokal; kein CDN-Ausfallrisiko, sauberer PDF-Registrierungspfad).
3. ✅ **Body-Map S/W:** selektives Hatching — nur `übertrainiert ///` + `untertrainiert ...`; gute/inaktive Status bleiben clean. Doppelter Nutzen: S/W-eindeutig *und* Blick-Lenkung auf Handlungs-Bereiche.

**→ Doc ist freigegeben. Claude Code kann mit Sub-Phase 27.2 starten.**

---

## J) Umsetzungs-Ergebnis (Claude Code, 01.06.2026)

Branch `feature/phase-27-style-overhaul`, 10 Commits (27.1–27.6 + Emoji-Sweep).
Verifikation jeweils via `pytest` (test_export/test_training_stats/
test_advanced_stats) + flake8/black; **visuelle Abnahme durch den User**.

**Umgesetzt:**
- **27.2** Farb-Tokens + `--bs-*`-Override – inkl. expliziter Button-Variablen
  (Bootstrap-CDN kompiliert `.btn-*` literal, liest NICHT `--bs-primary`) +
  warme Neutrale; `theme-color`, Header-Chrome, Offline-Toasts.
- **27.3** Typografie self-hosted (Source Serif 4 / Source Sans 3, 4 OFL-TTFs
  im Repo) – **live + matplotlib aktiv**.
- **27.4** Status-Icons live (Bootstrap-Icons), Emoji aus `status_label` raus.
- **27.5** Karten (Schatten live / Border PDF) + **vollständige PDF-Palette-
  Migration** (literale Hex, da xhtml2pdf kein `var()`).
- **27.6a/b** matplotlib- + Chart.js-Charts auf Marken-Palette, Body-Map
  Neutral→Berry.
- **Emoji-Sweep** der Report-Bewertungs-Strings → AK „keine Emoji im PDF".

**NICHT umgesetzt / DEFERRED (mit Begründung):**
- **PDF-Custom-Fonts + Geometrie-Status-Glyphen:** mit **xhtml2pdf nicht
  machbar** – `@font-face`/Font-Laden crasht den Export (`urlopen
  unknown url type: c` + Temp-`PermissionError`). PDF bleibt auf
  Arial/Helvetica + Klartext-Labels (emoji-frei). Die §B/§C-Annahme
  „Glyphen/Fonts rendern in xhtml2pdf" hält mit dieser Engine **nicht**.
  → **Empfehlung: Engine-Wechsel zu WeasyPrint** (echtes `@font-face`) als
  eigene Phase – Architektur-/Claude.app-Entscheidung.
- **Body-Map-Hatching** (§A.5, S/W übertrainiert `///`/untertrainiert `...`)
  noch offen.
- **Heatmap:** live grün (GitHub-Metapher) vs. PDF berry (§A.3) – bewusst,
  ggf. vereinheitlichen.
- OFL-`LICENSE` zu den TTFs ergänzen (Lizenz-Hygiene).
