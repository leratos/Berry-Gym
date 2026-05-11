# Phase 27 – Style-Overhaul

**Status:** 📋 Konzept (11.05.2026)
**Vorgänger:** Phase 26 (Konsolidierungs-Logik)
**Nachfolger:** Phase 28 (Dokumentations-Aktualisierung)
**Branch-Schema:** `feature/phase-27-X-kurzbeschreibung` pro Sub-Phase

> **Scope-Abgrenzung:** Diese Phase adressiert **visuelles Design** – Farbpalette, Typografie, Icon-Sprache, Karten/Boxen, Chart-Styling, allgemeine Optik. **Strukturelle Themen** (Pagebreaks, Sektion-Reihenfolge, doppelte Sichten, ToC-Verlinkung) sind in **Phase 25** abgeschlossen und werden hier nicht erneut aufgegriffen.
>
> Phase 27 setzt voraus, dass Phase 25 fertig ist – Style auf instabiler Struktur ist verschwendete Arbeit.

Diese Phase ist die einzige in der Roadmap, die **Design-Entscheidungen** statt Logik-Entscheidungen braucht. Beim Start sollten Mockups oder ein Style-Guide-Sketch existieren, sonst wird die Sub-Phasen-Aufteilung beliebig.

---

## 1. Problemanalyse

### 1.1 Ausgangspunkt

Nach Phase 25 ist der Report strukturell sauber, aber visuell unkohärent. Vermutete Schwachstellen (beim Start zu verifizieren):

- Farbpalette wirkt heterogen – Status-Farben aus Muskelgruppen-Sicht (grün/gelb/rot/grau) sind ein Schema, andere Sektionen nutzen andere Farben ohne erkennbares System
- Typografie ohne Hierarchie-Stufen über die HTML-Defaults hinaus (h1/h2/h3 als Auto-Style)
- Karten- und Box-Stile uneinheitlich (gefüllte Boxen, Ränder, Schatten gemischt)
- Chart-Styling verwendet matplotlib-Defaults statt einer abgestimmten Linie
- Keine konsistente Icon-Sprache (in Phase 25 wurde das `■`-Problem strukturell gelöst, aber kein einheitliches Icon-Set definiert)

### 1.2 Was diese Phase nicht macht

- Logik-Änderungen jeder Art
- Inhaltliche Änderungen (Wording, Reihenfolge, Datensicht)
- Performance-Optimierungen am Render-Pfad

### 1.3 Ziel

Visuell kohärenter Report mit klarer Design-Sprache. Lesbarkeit verbessern, Schnellerfassung von Status-Informationen erhöhen, „Professional Edition"-Anspruch des Reports einlösen.

---

## 2. Vor-Arbeit: Style-Decision-Phase

Bevor Sub-Phasen abgearbeitet werden können, müssen Design-Entscheidungen feststehen. Das ist **keine Implementierungs-Phase**, sondern eine Konzept-Verfeinerung mit dem User.

### 2.1 Entscheidungen die vor Implementierungs-Start fallen müssen

- **Farbpalette:** Primärfarbe, Sekundärfarbe, Status-Farben (Optimal/Über/Unter/Inaktiv), Hintergrund-Töne. Mit oder ohne Anlehnung an bestehende Berry-Gym-Identität?
- **Typografie:** Schrift-Familie, Stufen (h1/h2/h3/Body/Caption/Metadata). System-Schrift oder Web-Font (Renderer-Kompatibilität prüfen)?
- **Icon-Set:** Einheitliche Icon-Library (z.B. Lucide), oder pro Kontext unterschiedliche Sets erlaubt?
- **Karten-Stil:** Flat / Schatten / Gradient / Border-only?
- **Chart-Styling:** Linien-Farben, Marker-Stile, Hintergründe, Grid-Sichtbarkeit
- **Dichte:** Kompakter Style (mehr Info pro Seite) oder luftiger Style (bessere Lesbarkeit, mehr Seiten)?

### 2.2 Optionen für die Vor-Arbeit

- **(a) Direkt im Konzept-Doc:** User gibt Vorgaben als Text, kein Mockup.
- **(b) Mit Mockup:** Eine Beispiel-Seite (Executive Summary oder ähnliches) als visuelles Sketch, dann am Beispiel diskutieren.
- **(c) Style-Guide-Doc:** Eigenes `docs/concepts/phase27-style-guide.md` mit allen Tokens und Beispielen, dient als Referenz für die Sub-Phasen.

**Empfehlung:** (c) Style-Guide-Doc. Erlaubt es, später Phase-X-Style-Anpassungen an einer einzigen Stelle nachzupflegen.

---

## 3. Tasks (provisorisch – erst nach Style-Decision-Phase finalisieren)

### 3.1 Sub-Phase 27.1 – Style-Guide-Doc anlegen

**Aufwand:** S–M (je nach Tiefe) · **Reihenfolge:** zuerst

Style-Tokens definieren (Farben, Typografie-Stufen, Spacing, Border-Radius, Schatten), als Referenz-Dokument anlegen. Setzt die Vor-Arbeit aus Section 2 voraus. Kein Code-Change.

### 3.2 Sub-Phase 27.2 – Farbpalette anwenden

**Aufwand:** S · **Reihenfolge:** nach 27.1

CSS-Variablen oder Theme-Setup mit den Tokens aus 27.1. Bestehende Farb-Werte im Template/CSS auf Tokens umstellen. Keine neuen Farben einführen, nur konsistent machen.

### 3.3 Sub-Phase 27.3 – Typografie-Hierarchie

**Aufwand:** S · **Reihenfolge:** nach 27.2

Heading-Stufen, Body-Text, Captions, Metadata mit klar definierten Style-Tokens. Konsistent über alle Sektionen.

### 3.4 Sub-Phase 27.4 – Icon-Set

**Aufwand:** S–M · **Reihenfolge:** nach 27.3

Setzt auf 25.5 auf (Encoding-Artefakte). Phase 25 hat das technische Problem gelöst; Phase 27 vereinheitlicht jetzt das visuelle Set – ein einziges Icon-System statt mehrerer.

### 3.5 Sub-Phase 27.5 – Karten und Boxen

**Aufwand:** S–M · **Reihenfolge:** nach 27.4

Konsistenter Karten-Stil über alle Sektionen. Insbesondere die unterschiedlich gestylten Info-Boxen (was-ist-ein-Plateau / RPE-Erklärung / Warnungs-Box) auf ein Schema bringen.

### 3.6 Sub-Phase 27.6 – Chart-Styling

**Aufwand:** M · **Reihenfolge:** nach 27.5

matplotlib-Style-Override mit den Tokens. Linien-Farben, Marker, Hintergrund, Grid – alles aus Style-Guide. Achtung: Lesbarkeit (technische Klarheit) hat Vorrang vor visueller Konsistenz – wenn ein hübschere Farbe schlechter lesbar ist, verliert sie.

---

## 4. Reihenfolge & Begründung

```
27.0 (Vor-Arbeit Style-Decisions) → 27.1 (Style-Guide-Doc) → 27.2 (Farben) → 27.3 (Typo) → 27.4 (Icons) → 27.5 (Karten) → 27.6 (Charts)
```

- **27.0 ist Konzept-Arbeit mit User**, kein Branch, kein Code
- **27.1 ist Doc-Arbeit**, ggf. eigener kleiner Branch
- **27.2–27.6 sind Implementierungs-Branches**, jeder Sub-Phase ihr eigener
- Reihenfolge folgt Abhängigkeitskette: Tokens → Farben → Typo → Icons → Komponenten → Charts

---

## 5. Cross-Cutting Concerns

### 5.1 Renderer-Kompatibilität

Beim Style-Guide-Entwurf prüfen, was der PDF-Renderer (weasyprint / reportlab / anderes – beim Start klären, vermutlich schon in Phase 25.4 beantwortet) unterstützt:

- Web-Fonts (System-Schriften sind sicher, Custom-Fonts brauchen Renderer-Support)
- CSS-Features (Flexbox, Grid, CSS-Variablen)
- SVG-Inline (Icon-Strategie)
- Box-Shadow, Gradients

Style-Decisions dürfen keine Features verlangen, die der Renderer nicht kann.

### 5.2 Verifikation gegen Lera-Daten

Wie in Phase 25: nach jeder Sub-Phase ein Production-Export, visuell prüfen, dann nächste Sub-Phase. Style-Probleme zeigen sich erst im echten Rendering.

### 5.3 Phase 26 (Konsolidierung) bleibt entkoppelt

Falls Phase 26 noch nicht abgeschlossen ist beim Start von 27 – kein Problem, weil die zwei Themen unabhängig sind. Idealerweise aber Phase 26 vorher fertig, damit der neue Status `bereit_fuer_pr_versuch` ein Style-Token bekommt.

---

## 6. Offene Fragen

- F1: Vor-Arbeit Variante (a/b/c)? Empfehlung (c) Style-Guide-Doc
- F2: Bestehende Berry-Gym-Identität als Ausgangspunkt, oder freier Neu-Entwurf?
- F3: PDF-Renderer (kommt aus 25.4 oder noch zu klären)
- F4: Print-Optimierung (Schwarz-Weiß-tauglich)? Heute irrelevant, aber gut zu wissen für Farb-Decisions.

---

## 7. Akzeptanzkriterien

- Style-Guide-Doc als Referenz vorhanden
- Alle Tokens konsistent über alle Sektionen angewendet
- Keine Renderer-Kompatibilitäts-Probleme
- Lesbarkeit nicht durch Style-Decisions verschlechtert
- User-Feedback (Lera): visueller Eindruck deutlich kohärenter als vor Phase 27

---

## 8. Status-Updates

*(Wird beim Start und Abschluss jeder Sub-Phase ergänzt.)*
