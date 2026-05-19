# Phase 30 – Adaptive Plan Generation (Report-Output als Generator-Input)

**Status:** 📋 Konzept (20.05.2026)
**Vorgänger:** Phase 29 (Plan-Generator-Konsistenz – akute Bugs F1/F2/F3)
**Branch-Schema:** `feature/phase-30-X-kurzbeschreibung` pro Sub-Phase

> **Architektur-Phase.** Anlass: konkrete Plan-Generierung vom 19.05.2026
> (3er-Split, 22 Sätze/Tag, Sonnet 4.6) gegen den Trainings-Report vom selben
> Tag — der Plan würde drei Muskelgruppen weiter überlasten und eine echte
> Schwachstelle (Hüftbeuger) gar nicht adressieren. Phase 29.3 hat die
> Untertrainiert-Liste angekoppelt, aber das Übertraining-Stop-Signal und die
> Plateau-/Ermüdungs-Daten fehlen weiterhin im Generator-Input.

> **Konzept-Bezug:** Phase 29 hat sich explizit auf akute Bugs beschränkt
> (`phase29_concept.md` Section 1, Scope-Abgrenzung) und die volle
> Feedback-Loop-Architektur für „Phase 30: Adaptive Plan Generation"
> aufgehoben (Section 5.3). Dieses Dokument konkretisiert sie.

---

## 1. Problemanalyse

### 1.1 Konkreter Befund (19.05.2026)

Plan generiert vom Phase-29-Stand-Generator (User 2 / Leratos), gegen den
Trainings-Report vom selben Tag (30-Tage-Fenster):

| Muskelgruppe | Report-Ist (30 T) | Report-Status | Plan-Wochenvolumen | Effekt bei Plan-Ausführung |
|---|---:|---|---:|---|
| Brust | 28 Sätze | **Übertraining** | +8 | → ~36 → Übertraining schlimmer |
| Lat (RUECKEN_LAT) | 21 | **Übertraining** | +8 | → ~29 → schlimmer |
| Quad (BEINE_QUAD) | 21 | **Übertraining** | +11 | → ~32 → deutlich schlimmer |
| Trizeps | 20 | Optimal | +6 | im Rahmen |
| Schulter Hintere | 18 | Optimal | +7 | im Rahmen |
| Bizeps | 15 | Optimal | +7 | im Rahmen |
| Schulter Vordere | 12 | Optimal | +4 | im Rahmen |
| Schulter Seitliche | 12 | Optimal | +4 | im Rahmen |
| Hamstrings (BEINE_HAM) | 9 | **Untertrainiert** | **+7** | → 16 → Optimum ✓ |
| Bauch (BAUCH) | 9 | **Untertrainiert** | **+4** | → 13 → knapp Optimum ✓ |
| **Hüftbeuger (HUEFTBEUGER)** | **9** | **Untertrainiert** | **+0** | bleibt untertrainiert ✗ |

Treffer: 2 von 3 echten Schwachstellen adressiert. Schaden: 3 Übertraining-
Lagen werden bei wiederholter Plan-Ausführung schlimmer.

### 1.2 Wurzel-Mechanik

Zwei strukturelle Lücken im Generator-Input:

1. **Metrik-Mismatch zwischen Generator und Report.**
   - `data_analyzer._identify_weaknesses` nutzt **effektive Wiederholungen**
     (Sätze × Wdh × RPE/10) und vergleicht gegen `0.6 × Ø`.
   - Der Trainings-Report nutzt **Satzzahl** und vergleicht gegen einen
     Volumen-Schwellenwert (Anzeige: 12–20 Sätze/30 Tage).
   - Bei hochrepetitiven Muskelgruppen (Hüftbeuger ~15 Wdh, hoher RPE)
     bleiben eff. Wdh hoch, obwohl die Satzzahl niedrig ist → der Generator
     sieht keine Schwäche, der Report schon. Genau das erklärt das
     **Hüftbeuger-Loch** im Plan oben.
   - Zusätzlich: `data_analyzer` zählt nur **primäre** Muskelgruppen
     (`uebung.muskelgruppe`), nicht `hilfsmuskeln`. Der Report nutzt
     (vermutlich) eine andere Set-Attribution, was die Differenz verstärkt.

2. **Kein Übertraining-Signal im Generator.**
   Phase 29.3 hat ausschließlich die Untertrainiert-Seite eingebaut. Der
   Prompt enthält keinerlei Information darüber, welche Muskelgruppen bereits
   im Übertraining-Bereich stehen. Der Generator füllt den Tag stur auf
   `sets_per_session` Sätze hoch und verteilt 22 Sätze auf 6 Übungen →
   landet routinemäßig bei 7–8 Sätzen für die Compound-Muskeln (Brust, Lat,
   Quad), **unabhängig vom Ist-Stand**.

Zusätzliche, nicht genutzte Report-Signale (sichtbar im PDF, generator-unsichtbar):

- **Plateau-Status pro Top-Übung** („Aktive Progression" / „Beobachten" /
  „Konsolidierung" / „PR-Pause"). Beispiel: Bankdrücken steht auf „Aktive
  Progression (PR-Pause)" — Volumen weiter hochziehen ist kontraproduktiv,
  hier hilft Frequenz-/Tempo-Variation.
- **Ermüdungs-Index** (0–100). Bei 60+ sollte der Generator in einen
  Deload-/Recovery-Modus schalten, statt zusätzliches Volumen vorzuschlagen.
- **Trainings-Konsistenz / Frequenz** (Adherence %, Ø Pause-Tage). Bei
  <2x/Woche sollte der Generator Ganzkörper empfehlen, nicht Split.
- **Push/Pull-Ratio mit Bewertung**. Die existierende Push/Pull-Logik in
  `data_analyzer` wurde in 29.3 gefixt, ist aber noch nicht mit der
  Report-Bewertungslogik verzahnt.

### 1.3 Ziel der Phase

**Single Source of Truth.** Die Muskelgruppen- und Plateau-Klassifikationen,
die der User im Dashboard und PDF-Report sieht, sind dieselben, die in den
Plan-Prompt fließen. Der Generator hört auf, parallel eigene Heuristiken zu
rechnen, und konsumiert stattdessen den Report-Output (oder dessen
Berechnungs-Helper aus `core/utils/`).

---

## 2. Architektur-Skizze

```
UI (Stream/POST)
  └─ PlanGenerator
       ├─ TrainingReportSnapshot (NEU, ai_coach/training_report_snapshot.py)
       │    Liest aus core/utils/ – dieselben Helper, die der PDF-Report nutzt
       │    └─ volume_status[mg]   : Optimal | Untertrainiert | Übertraining | Nicht trainiert
       │    └─ ist_sets[mg]        : Satzzahl 30 Tage
       │    └─ soll_min, soll_max  : pro mg
       │    └─ plateau_status[übung]: Aktive Progression | Konsolidierung | …
       │    └─ ermuedungs_index    : 0–100
       │    └─ push_pull_ratio     : float + bewertung
       │    └─ frequency_per_week  : float
       ├─ PromptBuilder konsumiert TrainingReportSnapshot
       │    └─ Untertrainiert-Block (Pflicht, ≥N Sätze)        ← Quelle wechselt
       │    └─ Übertraining-Block (HARD-CAP, ≤M Sätze)         ← neu
       │    └─ Plateau-Hint pro Top-Übung                      ← neu
       │    └─ Ermüdungs-/Frequenz-Hint                        ← neu
       └─ Validator (plan_validator) prüft:
            └─ Übertraining-Cap eingehalten?                   ← neu
            └─ Untertrainiert-Floor erreicht? (29.3 verschärft mit Report-Liste)
```

Der zentrale neue Baustein ist `TrainingReportSnapshot` – ein einfacher
Daten-Container, der den Report-Zustand zur Generierungs-Zeit einfriert.

---

## 3. Sub-Phasen

### 3.1 Sub-Phase 30.1 – Übertraining-Cap (akuter Hotfix)

**Status:** 📋 Konzept · **Aufwand:** S–M · **Reihenfolge:** zuerst

#### Problem

Der Generator hat keine Information über Muskelgruppen im
Übertraining-Bereich → fügt routinemäßig 7–8 Sätze für Brust/Lat/Quad hinzu,
obwohl diese im konkreten Befund schon bei 21–28 Sätzen/30 Tagen stehen. Mit
dem 19.05.-Befund ist dieser Plan kein theoretisches Risiko, sondern wäre
tatsächlich zur Ausführung gekommen.

#### Lösungsansatz

1. **Helper** `classify_muscle_volume_status(user_id, days=30) → dict[str, dict]`
   in `core/utils/` (Arbeitsname `training_volume_status.py`).
   Nutzt dieselben Volumen-Schwellenwerte wie der Report (siehe Offene Frage
   zur Threshold-Quelle unten). Pro DB-Konstante:
   `{status, ist_sets, soll_min, soll_max}`.
2. **PlanGenerator** ruft den Helper beim Start auf und übergibt das
   Ergebnis an PromptBuilder.
3. **PromptBuilder** ergänzt im Anforderungs-Block:

   ```
   🛑 ÜBERTRAINING-CAP (HÖCHSTE PRIORITÄT):
   Folgende Muskelgruppen sind aktuell ÜBERTRAINIERT. Der neue Plan DARF NICHT
   noch zusätzliches Volumen hinzufügen.
   - Brust (aktuell 28 Sätze/30 Tage, Ziel max. 20): max. 4 Sätze/Woche
   - Latissimus (21 / max 20): max. 4 Sätze/Woche
   - Quadrizeps (21 / max 20): max. 4 Sätze/Woche
   ```

   Cap-Berechnung: `max(2, soll_max // 4 - 2)` oder ähnlich (Detail beim
   Implementieren — Ziel: nach 4 Plan-Wochen sollte der Ist-Wert in Richtung
   Soll-Max wandern, nicht darüber).

4. **Validator** (`plan_validator`) ergänzt
   `_check_overtraining_cap(plan_json, overtrained_caps) → warnings`:
   wenn eine geCappte Muskelgruppe im Plan über ihr Cap kommt → Warnung
   und (optional) Auto-Fix durch Sätze-Kürzung der schwächsten Übung.

#### Akzeptanzkriterien

- Übertraining-Liste fließt in jeden Plan ein (nachweisbar im Prompt-Output).
- Im generierten Plan bekommt eine Übertraining-Muskelgruppe ≤ Cap Sätze
  pro Woche.
- **Regressions-Test:** der 19.05.-Befund (User 2 / Leratos) generiert einen
  Plan, der Brust/Lat/Quad NICHT erhöht.
- Tests für Helper, Prompt-Block, Validator-Check.

### 3.2 Sub-Phase 30.2 – Untertrainiert-Quelle auf Report-Basis

**Status:** 📋 Konzept · **Aufwand:** M · **Reihenfolge:** nach 30.1

#### Problem

`data_analyzer._identify_weaknesses` (eff_reps < 60 % Ø) übersieht
Muskelgruppen, die per Satzzahl untertrainiert sind, aber hohe Wdh-Zahlen
haben (Hüftbeuger-Loch im 19.05.-Befund).

#### Lösungsansatz

`prompt_builder._build_weakness_block` und
`plan_generator._validate_weakness_coverage` konsumieren die in 30.1
eingeführte `classify_muscle_volume_status`-Quelle statt
`analysis_data["weaknesses"]`. Die 29.3-Volumen-Vorgabe (`≥ MIN_SETS_PER_WEAKNESS`)
bleibt; nur die Quelle der Liste wechselt.

`data_analyzer._identify_weaknesses` wird zur „weichen" Heuristik degradiert
(z. B. zusätzlich-zur-Anzeige im Prompt-Header, nicht mehr Pflicht-Quelle)
oder vollständig entfernt.

#### Akzeptanzkriterien

- Hüftbeuger im 19.05.-Befund landet im Pflicht-Block (Regressions-Test).
- Tests + Live-Verifikation.

### 3.3 Sub-Phase 30.3 – Plateau-Status als Volumen-Hint

**Status:** 📋 Konzept · **Aufwand:** M

Für Top-Übungen mit Plateau-Status `Aktive Progression (PR-Pause)` oder
`Konsolidierung` → Prompt-Hint, dass Volumen-Erhöhung für diese Übung
kontraproduktiv ist; stattdessen Frequenz-/Tempo-Variation oder
Akzessoire-Übung empfehlen.

Der Plateau-Status existiert bereits (sichtbar im Report, berechnet in
`core/utils/`); muss nur in den Snapshot aufgenommen und im Prompt
verwendet werden.

### 3.4 Sub-Phase 30.4 – Ermüdungs- und Konsistenz-Adaption

**Status:** 📋 Konzept · **Aufwand:** M

- **Ermüdungs-Index > Schwelle** (z. B. 60) → Plan-Generator schaltet in
  Deload-/Recovery-Modus (geringeres Volumen, Compound-Fokus, längere
  Pausen). Schwelle und Mechanik in 30.4 zu definieren.
- **Trainings-Frequenz < 2/Woche** → Ganzkörper-Empfehlung statt Split.
- **Push/Pull-Ratio aus dem Report** (nicht aus `data_analyzer`) feeds in
  den Prompt mit konkreter Empfehlung wie im PDF („Pull aufstocken um die
  Imbalance zu adressieren").

---

## 4. Reihenfolge & Begründung

```
30.1 (Übertraining-Cap)
  → 30.2 (Untertrainiert auf Report-Basis)
  → 30.3 (Plateau-Status)
  → 30.4 (Ermüdung/Konsistenz)
```

- **30.1 zuerst:** akuter Schaden im 19.05.-Befund, kleiner Aufwand,
  liefert sofort sichtbaren Wert. Bringt zusätzlich den Helper, den
  30.2/30.3/30.4 wiederverwenden.
- **30.2 als nächstes:** schließt das Hüftbeuger-Loch und vereinheitlicht
  die „Untertrainiert"-Definition zwischen Report und Generator.
- **30.3 / 30.4:** baut auf der etablierten Snapshot-Datenstruktur auf.

---

## 5. Offene Fragen

- **F-30-1:** Welche Volumen-Schwellenwerte gelten? Der PDF-Report zeigt
  durchgängig 12–20 Sätze/30 Tage für **alle** Muskelgruppen.
  `core/utils/periodization.py` hat dagegen größenklassen-spezifische Werte
  (`VOLUMEN_SCHWELLENWERTE`: gross 12–25, mittel 10–18, klein 8–16,
  haltung 6–12). Die zwei Systeme widersprechen sich. Welches ist
  kanonisch? Wenn beide gelten – warum? (Entscheidung muss vor 30.1 fallen,
  sonst wird der Cap willkürlich.)
- **F-30-2:** Soll `TrainingReportSnapshot` bei jeder Generation neu
  gerechnet werden, oder das im PDF-Report bereits berechnete Ergebnis
  wiederverwenden (z. B. via `Trainingsblock.schwachstellen_snapshot` o. ä.
  gecacht)? Tradeoff Frische vs. Konsistenz mit der zuletzt vom User
  gesehenen PDF.
- **F-30-3:** `data_analyzer.weaknesses` wird durch 30.2 entwertet – soll
  die Heuristik bleiben (als sekundäres Signal) oder entfernt werden?
- **F-30-4:** Wie verhält sich der Übertraining-Cap zum 29.3-Untertrainiert-
  Floor bei Konflikt (z. B. Push-Tag mit gleichzeitig Brust im Übertraining
  und Hintere Schulter untertrainiert)? Priorisierung definieren.
- **F-30-5:** Wie zählt der Report Hilfsmuskeln (sekundäre Beteiligung) bei
  der Set-Attribution? Wenn ja, sollte der Helper das auch tun – sonst
  divergieren die Zahlen wieder.

---

## 6. Akzeptanzkriterien (Phase-Gesamt)

- Plan-Generator konsumiert eine **dokumentierte zentrale Quelle** für
  Muskelgruppen-Status und Plateau-Daten (Single Source of Truth gemeinsam
  mit dem Report).
- Generierte Pläne **verschlimmern keine Übertraining-Lage** (verifiziert
  mit dem 19.05.-Befund als Regressions-Test).
- Plateau- und Ermüdungs-Daten fließen messbar in Plan-Entscheidungen ein.
- Hüftbeuger-Loch geschlossen (Regressions-Test).
- Single Source of Truth für die Schwellenwert-Frage (F-30-1) etabliert.

---

## 7. Status-Updates pro Sub-Phase

*(Wird beim Start und Abschluss jeder Sub-Phase ergänzt.)*
