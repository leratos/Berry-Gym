# Phase 26 – Konsolidierungs-Logik zeitlich begrenzen

**Status:** 📋 Konzept (11.05.2026)
**Vorgänger:** Phase 25 (Layout-Refactor)
**Nachfolger:** Phase 27 (Style-Overhaul)
**Branch-Schema:** `feature/phase-26-X-kurzbeschreibung` pro Sub-Phase

Diese Phase ist klein, fokussiert auf einen einzigen Logik-Punkt. Kein Sammelpaket, keine Sub-Phasen über mehrere Themen verstreut. Wenn beim Implementieren mehr Findings auftauchen, werden sie als eigene Phase angelegt – nicht hier reingenommen.

---

## 1. Problemanalyse

### 1.1 Beobachtung

Im Production-Export vom 11.05.2026 (16:45) zeigt Trizeps Overhead Extension den Status *„Konsolidierung (RPE sinkt)"*. Konkret:

- Letzter PR: 09.03.2026 (63 Tage zurück)
- Max-Gewicht laut Verlauf-Chart: 17,5 kg seit 09.03., unverändert
- RPE-Trend: sank in den letzten 4 Wochen von 8,5 auf 7,5
- Klassifikation: `konsolidierung_rpe_sinkt`

Die Klassifikation ist nach der heutigen Definition korrekt: Gewicht stabil, RPE sinkt → User wird stärker. Aber:

### 1.2 Materielle Lücke

„Konsolidierung" als Status setzt voraus, dass die RPE-Reduktion zu einem PR-Versuch führt. Über **9 Wochen** Konsolidierung ohne PR-Versuch ist physiologisch und didaktisch nicht mehr „Konsolidierung", sondern einer von drei Zuständen:

- **Verpasster Steigerungsversuch** – User sieht das Signal zum Hochgehen nicht oder traut sich nicht. Häufigster Fall.
- **RPE-Re-Kalibrierung** – User schätzt sich nach längerer Übungs-Erfahrung konsistent niedriger ein, ohne tatsächlich stärker zu sein.
- **Plateau auf neuem Niveau** – Reiz reicht nicht mehr für weitere Adaptation, RPE-Sinken kommt aus Gewöhnung statt aus Stärkezuwachs.

Alle drei wollen unterschiedliche User-Reaktionen. „Konsolidierung" deckt sie pauschal mit einem positiven Label zu – der User bekommt kein Signal, dass es Zeit für einen PR-Versuch ist.

### 1.3 Ziel

Konsolidierungs-Status zeitlich begrenzen. Ab einer Schwelle kippt der Status in „Bereit für PR-Versuch" oder ähnlich – positiv formuliert (kein Vorwurf), aber als Aufforderung erkennbar.

---

## 2. Lösungsansatz

### 2.1 Stufen-Modell (Vorschlag)

| Dauer Konsolidierung | Status | Bedeutung |
|---|---|---|
| 0–4 Wochen | `konsolidierung_rpe_sinkt` | „Konsolidierung (RPE sinkt)" – aktueller Zustand, alles gut |
| 4–8 Wochen | `bereit_fuer_pr_versuch` | „Bereit für PR-Versuch – RPE seit X Wochen niedrig" |
| > 8 Wochen | `konsolidierung_ueberlang` | „Konsolidierung dauert ungewöhnlich lange – PR-Versuch oder Übungs-Variation prüfen" |

Schwellen sind Vorschläge, beim Implementieren empirisch zu justieren.

### 2.2 Was zählt als „Dauer Konsolidierung"?

Zwei Möglichkeiten:

- **(a) Tage seit letztem PR**, sofern RPE-Sinken im Zeitraum erkennbar. Einfach zu berechnen.
- **(b) Tage seit Beginn des RPE-Sinkens** (Zeitpunkt, ab dem RPE-Trend nachweislich fällt). Präziser, aber komplexere Erkennung.

**Empfehlung:** Variante (a). Einfachheit gewinnt; RPE-Sinken wird im aktuellen 4-Wochen-Fenster ohnehin schon geprüft, das reicht als Konsolidierungs-Evidenz.

### 2.3 Status-Übergänge

- `konsolidierung_rpe_sinkt` → `bereit_fuer_pr_versuch` (zeitgesteuert nach 4 Wochen)
- `konsolidierung_rpe_sinkt` → `konsolidierung_ueberlang` (zeitgesteuert nach 8 Wochen)
- Jeder dieser Status → `aktive_progression` (sobald ein neuer PR fällt)
- Jeder dieser Status → `pause` (sobald die Übung > 4 Wochen nicht trainiert wird – Logik aus 24.5 bleibt vorrangig)

### 2.4 Vermutete betroffene Dateien

- `classify_progression_status` (vermutlich `core/utils/advanced_stats.py`)
- PDF-Template Plateau-/Übersicht-Sektion (Status-Label und Legende)
- Tests in `core/tests/test_advanced_stats.py::TestPlateauAnalysis`

---

## 3. Edge Cases

- **RPE-Sinken endet, Gewicht bleibt:** RPE steigt zurück auf das ursprüngliche Niveau, Gewicht unverändert. Heute kippt Status vermutlich auf `leichtes_plateau` oder `plateau`. Soll der neue „Bereit für PR-Versuch"-Status sich an dieser Stelle einreihen?
- **RPE-Sinken stark, Gewicht steigt nicht:** User wird messbar stärker, nutzt es aber nicht. Das ist exakt der Hauptfall. Status muss klar signalisieren, dass jetzt ein PR-Versuch fällig ist.
- **Sehr lange Konsolidierung, dann plötzlicher PR:** Übergang zurück nach `aktive_progression` muss sauber funktionieren – keine „Hängenbleibe" in `konsolidierung_ueberlang`.
- **Übung mit dünner Datenlage:** < 4 Wochen RPE-Trend → kein Konsolidierungs-Status, fällt auf neutralen Status zurück.

---

## 4. Offene Fragen

- F1: Schwellen 4 Wochen / 8 Wochen empirisch sinnvoll oder andere Werte?
- F2: Status-Label-Texte – wie konkret formulieren? Vorschläge:
  - „Bereit für PR-Versuch – RPE seit 4 W niedrig"
  - „Konsolidierung dauert ungewöhnlich lange – Variation oder PR-Versuch prüfen"
- F3: Soll der „Bereit für PR-Versuch"-Status auch in Trainer-Empfehlungen auftauchen (proaktiver Hinweis), oder nur in der Plateau/Progressions-Tabelle?

---

## 5. Akzeptanzkriterien

- Trizeps OH (heutiger Live-Fall) kippt von `konsolidierung_rpe_sinkt` auf `bereit_fuer_pr_versuch` (oder `konsolidierung_ueberlang`, je nach Schwelle)
- Frisch konsolidierende Übungen (< 4 Wochen) bleiben unverändert auf `konsolidierung_rpe_sinkt`
- Übergänge zurück nach `aktive_progression` und nach `pause` funktionieren
- Tests decken alle Status-Übergänge ab, insbesondere den Trizeps-OH-Fall

---

## 6. Status-Updates

*(Wird beim Start und Abschluss ergänzt.)*
