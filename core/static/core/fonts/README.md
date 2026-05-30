# Self-hosted Fonts (Phase 27.3)

Berry-Gym nutzt zwei selbst-gehostete Open-Source-Schriften (OFL, kein
CDN-Risiko, und für die PDF-Pipeline – xhtml2pdf/matplotlib – zwingend lokal):

| Rolle | Familie | Benötigte Dateien (genau diese Namen) |
|---|---|---|
| Headings (Display) | **Source Serif 4** | `SourceSerif4-SemiBold.ttf`, `SourceSerif4-Bold.ttf` |
| Body / UI / Daten | **Source Sans 3** | `SourceSans3-Regular.ttf`, `SourceSans3-SemiBold.ttf` |

## Woher

Beide sind Open Source unter der **SIL Open Font License 1.1**:

- Source Serif 4: <https://github.com/adobe-fonts/source-serif> bzw.
  <https://fonts.google.com/specimen/Source+Serif+4>
- Source Sans 3: <https://github.com/adobe-fonts/source-sans> bzw.
  <https://fonts.google.com/specimen/Source+Sans+3>

Die **statischen** TTF-Instanzen (nicht die Variable-Font-Datei) mit den oben
genannten Gewichten herunterladen und mit **exakt** diesen Dateinamen in
dieses Verzeichnis legen. (Optional zusätzlich `.woff2` für kleinere
Live-Downloads – dann die `@font-face`-`src` in
`core/static/core/css/theme-styles.css` um `format('woff2')` ergänzen.)

## Solange die Dateien fehlen

`@font-face` schlägt still fehl und der Fallback-Stack greift
(`Georgia`/`Times` für Headings, `-apple-system`/`Segoe UI` für Body). Das
Layout bleibt stabil; nur die Anmutung ist generischer. `font-display: swap`
verhindert FOIT (kein unsichtbarer Text).

## Lizenz

OFL erlaubt das Mitliefern im Repo. Bitte die jeweilige `LICENSE`/`OFL.txt`
mit ablegen, wenn die Fonts eingecheckt werden.
