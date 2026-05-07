# Phase 23 – Detail-Fahrplan

**Status:** 📋 Konzept (06.05.2026)
**Roadmap-Eintrag:** [`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md) – Phase 23
**Branch (bei Start):** `feature/phase23-time-windowed-stats`

Dieses Dokument ist der detaillierte Fahrplan für Phase 23. Die Roadmap nennt nur Tasks und Abgrenzung – hier stehen Algorithmen, Datenstrukturen, Edge Cases, Testfälle, offene Fragen und Reihenfolge-Empfehlung.

---

## 1. Problemanalyse

### 1.1 Symptom

Mai-2026-PDF-Report (Berichtszeitraum 06.04. – 06.05.2026, 53 Sessions, 757 Sätze) liefert folgende inkonsistente Datenpunkte:

| Kennzahl                      | Wert im Report | Tatsächlicher Wert (letzte 4 W) | Inkonsistenz                          |
|-------------------------------|----------------|---------------------------------|---------------------------------------|
| RPE-10-Anteil                 | 19,0 %         | ~6 %                            | Zieht ältere Sessions herein          |
| Empfehlung                    | "Ziel: <5 %"   | bereits unterschritten          | Empfehlung passt nicht zu Verhalten   |
| Wochenvolumen KW18/KW19       | 13k / 13k kg   | bewusste Intensitäts-Reduktion  | Sieht aus wie Regression              |
| Ermüdungs-Index               | 0/100          | "Du kannst noch mehr trainieren"| Nicht plausibel bei 19 % RPE-10       |
| Plateau-Label "Hammer Curls"  | Konsolidierung | korrekt                         | inkonsistent angewendet               |
| Plateau-Label "Trizeps OH"    | Plateau        | könnte Konsolidierung sein      | gleicher Mechanismus, anderes Label   |

### 1.2 Ursache

Mehrere Berechnungen nutzen unterschiedliche oder implizite Zeiträume:

- **Muskelgruppen-Balance** und **Push/Pull-Ratio**: explizit 30-Tage-Fenster (korrekt)
- **RPE-Verteilung**: All-Time über alle Sessions (verzerrt)
- **Ermüdungs-Index**: vermutlich anderer Zeitraum als RPE-Verteilung (siehe Tech-Debt aus Phase 9.4 – Funktion `calculate_fatigue_index` möglicherweise Dead Code)
- **Plateau-Logik**: nutzt PR-Datum als Anker (zeitlich korrekt), aber Konsolidierungs-Erkennung wird nicht konsistent auf alle Plateau-Kandidaten angewendet

### 1.3 Ziel der Phase

Drei klar getrennte Zeitfenster definieren und auf alle betroffenen Berechnungen anwenden:

- **Kurzfristig (2 Wochen)**: aktueller Zustand, hohe Reaktivität, kann unzuverlässig sein bei wenigen Sessions
- **Mittelfristig (4 Wochen)**: primäre Steuerungsgröße, ausreichend Daten, glättet Wochen-Schwankungen
- **All-Time**: historischer Kontext, bleibt sichtbar (nicht ersatzlos gestrichen)

Bewertung und Empfehlung basieren auf dem **4-Wochen-Wert**, kurzfristig und All-Time werden zur Einordnung mit angezeigt.

---

## 2. Architektur-Übersicht

### 2.1 Daten-Layer

Bestehende Tabellen reichen aus – **keine Migration nötig**. Alle Zeitfenster lassen sich aus `Satz` mit `session__datum`-Filter ableiten.

### 2.2 Berechnungs-Layer (`core/utils/advanced_stats.py`)

Neue zentrale Helper-Funktion:

```python
def get_time_windows(reference_date: date) -> dict[str, tuple[date, date]]:
    """
    Liefert Standard-Zeitfenster für alle Phase-23-Analysen.

    Returns:
        {
          "2w": (reference_date - 14 days, reference_date),
          "4w": (reference_date - 28 days, reference_date),
          "all": (None, reference_date),  # None = unbegrenzt
        }
    """
```

Bestehende Funktionen werden um optionalen `window`-Parameter erweitert (Default `"4w"`), nicht ersetzt – damit bleibt All-Time-Verhalten weiter abrufbar (z. B. für Lifetime Hall of Fame aus Phase 22-Backlog).

### 2.3 View-Layer (`core/views/training_stats.py`)

Stats-View liefert pro Karte ein Dict mit allen drei Zeitfenstern:

```python
{
    "rpe_distribution": {
        "2w": {"rpe_10_pct": 0.0, "rpe_optimal_pct": 100.0, "n_sets": 12, ...},
        "4w": {"rpe_10_pct": 6.2, "rpe_optimal_pct": 87.5, "n_sets": 48, ...},
        "all": {"rpe_10_pct": 19.0, "rpe_optimal_pct": 80.3, "n_sets": 757, ...},
        "primary_window": "4w",  # Bewertung basiert hierauf
        "evaluation": "optimal",
        "recommendation": "Letzte 4 Wochen: 6,2 % RPE-10 – innerhalb Ziel (<10 %).",
    }
}
```

### 2.4 Template-Layer

UI-Pattern: drei kompakte Werte nebeneinander, primärer (4-Wochen-) Wert hervorgehoben. Empfehlungstext nennt explizit den Zeitraum.

---

## 3. Task 23.1 – RPE-Verteilung mit gestaffelten Zeitfenstern

### 3.1 Was wird verändert

Bestehende RPE-Verteilung (vermutlich in `advanced_stats.calculate_rpe_distribution()` oder ähnlich) bekommt einen `window`-Parameter und wird drei Mal aufgerufen (2w / 4w / all). Die View bündelt die Ergebnisse und übergibt sie an Template + PDF.

### 3.2 Algorithmus-Skizze

```
def calculate_rpe_distribution(user, reference_date, window="4w"):
    start, end = resolve_window(window, reference_date)
    sets = Satz.objects.filter(
        session__user=user,
        session__datum__gte=start,
        session__datum__lte=end,
        rpe__isnull=False,
    )
    n_total = sets.count()

    if n_total < MIN_SETS_FOR_WINDOW:  # z.B. 30
        return _fallback_to_larger_window(user, reference_date, window)

    return {
        "n_sets": n_total,
        "rpe_below_7_pct": sets.filter(rpe__lt=7).count() / n_total * 100,
        "rpe_optimal_pct": sets.filter(rpe__gte=7, rpe__lte=9).count() / n_total * 100,
        "rpe_10_pct": sets.filter(rpe=10).count() / n_total * 100,
        "rpe_avg": sets.aggregate(Avg("rpe"))["rpe__avg"],
        "window": window,
        "window_start": start,
        "window_end": end,
    }
```

### 3.3 Bewertung & Empfehlung

Bewertung basiert ausschließlich auf dem **4-Wochen-Wert**. Schwellenwerte aus Phase 9.3 bleiben bestehen:

| RPE-10-Anteil (4 W) | Status         | Empfehlungstext (Beispiel)                                         |
|---------------------|----------------|---------------------------------------------------------------------|
| < 5 %               | Optimal        | "Letzte 4 Wochen: X % RPE-10 – innerhalb Ziel."                     |
| 5–15 %              | Akzeptabel     | "Letzte 4 Wochen: X % RPE-10 – im akzeptablen Bereich."             |
| > 15 %              | Risiko         | "Letzte 4 Wochen: X % RPE-10 – Übertrainings-Risiko."               |

Zusatzlogik: Wenn 2-Wochen-Wert **deutlich** vom 4-Wochen-Wert abweicht (>5 Prozentpunkte), Hinweis "Trend ändert sich – Verhalten in den letzten 2 Wochen weicht ab". Das fängt sowohl Verbesserung (User korrigiert) als auch Verschlechterung (User schlampt) ab.

### 3.4 Edge Cases

| Fall                                               | Verhalten                                                                       |
|----------------------------------------------------|----------------------------------------------------------------------------------|
| Weniger als 30 Sätze in 2 Wochen                   | "2-Wochen-Wert" entfällt (n.a. anzeigen), 4w + all bleiben                     |
| Weniger als 30 Sätze in 4 Wochen                   | Fallback auf All-Time, Hinweis "Zu wenig Daten für 4-Wochen-Auswertung"        |
| User komplett ohne RPE-Daten                       | Karte zeigt "Keine RPE-Daten erfasst", keine Bewertung                         |
| Kombination mit Plan-Filter (Phase 22)             | Plan-Filter zuerst angewendet, dann Zeitfenster innerhalb des Plans            |
| Plan jünger als 4 Wochen                           | 4w-Fenster reicht ggf. vor Plan-Start zurück → 4w = "seit Plan-Start"          |

### 3.5 Testfälle (für `test_advanced_stats.py`)

```
TestRpeDistributionWindowed:
  - test_4w_window_excludes_old_high_rpe        # historisch viel RPE-10, jetzt sauber → 4w zeigt sauber
  - test_2w_window_reflects_recent_only         # letzte 2 W sauber, 4 W noch belastet → 2w grün, 4w gelb
  - test_fallback_when_insufficient_data        # neuer User, 5 Sätze → fallback all
  - test_plan_filter_combination                # Plan-Wechsel vor 3 Wochen → 4w respektiert Plan-Start
  - test_evaluation_uses_4w_only                # 4w grün, all rot → Bewertung "optimal"
  - test_divergence_hint_on_trend_change        # 2w 0%, 4w 8%, all 19% → Hinweis "Trend verbessert sich"
```

### 3.6 UI-Anpassung

Aktuell: Donut-Chart mit einem Wert (Ø 8.1) und Detail-Liste.

Neu: Drei kompakte Karten nebeneinander (Mobile: gestapelt). 4-Wochen-Karte größer/farbig hervorgehoben. Donut-Chart bleibt für 4-Wochen-Wert.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  2 Wochen    │  │  4 WOCHEN    │  │   Gesamt     │
│  RPE-10: 0%  │  │  RPE-10: 6%  │  │  RPE-10: 19% │
│  n=12        │  │  ★ n=48      │  │  n=757       │
└──────────────┘  └──────────────┘  └──────────────┘

Bewertung: Optimal · Empfehlung: Letzte 4 Wochen 6 % – innerhalb Ziel.
Hinweis: Trend verbessert sich (2 Wochen: 0 %, vorher: 8 %).
```

---

## 4. Task 23.2 – Effektives Volumen als zusätzliche Metrik

### 4.1 Was wird verändert

Wochenvolumen-Chart bekommt eine zweite Linie. Bestehende Tonnage-Linie bleibt unverändert. Neue Metrik:

```
effektives_volumen[woche] = Σ (gewicht * reps) für alle Sätze mit RPE 7–9
```

Sätze mit RPE < 7 (Junk Volume) und RPE 10 (Failure Volume, recovery-teuer) werden ausgeschlossen.

### 4.2 Algorithmus-Skizze

```python
def weekly_effective_volume(user, week_start, week_end, rpe_min=7, rpe_max=9):
    sets = Satz.objects.filter(
        session__user=user,
        session__datum__gte=week_start,
        session__datum__lte=week_end,
        rpe__gte=rpe_min,
        rpe__lte=rpe_max,
    ).annotate(set_volume=F("gewicht") * F("wiederholungen"))
    return sets.aggregate(total=Sum("set_volume"))["total"] or 0
```

### 4.3 Interpretationsregeln

Wichtig für die Empfehlungslogik in `_get_performance_warnings()`:

| Tonnage      | Eff. Volumen | Diagnose                                     |
|--------------|--------------|----------------------------------------------|
| sinkt        | sinkt        | Echte Regression – Warning rechtfertigt      |
| sinkt        | stabil       | Intensitäts-Korrektur – KEIN Warning         |
| sinkt        | steigt       | Qualitäts-Verbesserung – positive Erwähnung  |
| steigt       | sinkt        | Mehr Junk/Failure-Volumen – Effizienz prüfen |
| stabil       | stabil       | Stabile Phase – neutral                      |

Diese Tabelle löst das im Mai-Report sichtbare Problem (KW18/19-Einbruch) sauber auf.

### 4.4 Edge Cases

| Fall                                              | Verhalten                                                            |
|---------------------------------------------------|-----------------------------------------------------------------------|
| Sätze ohne RPE-Eintrag                            | Werden ausgeschlossen (können weder Junk noch Failure sein)          |
| Übungen mit ist_gegengewicht (Phase 14.1)         | effektives_gewicht analog Phase 14 berechnen, nicht rohes `gewicht`  |
| Bodyweight-Übungen                                | Historisches Körpergewicht aus Phase 14.2 nutzen                     |
| Deload-Woche (Block-Typ aus Phase 3)              | Nicht als "Regression" markieren – Block-Typ-Awareness ggf. nötig    |

### 4.5 Testfälle

```
TestEffectiveVolume:
  - test_excludes_rpe_below_7
  - test_excludes_rpe_10
  - test_includes_rpe_7_to_9
  - test_handles_missing_rpe_gracefully
  - test_uses_effektives_gewicht_for_bodyweight_exercises
  - test_uses_historical_bodyweight_for_dips
  - test_diagnostic_intensity_correction_no_warning
  - test_diagnostic_real_regression_emits_warning
```

### 4.6 UI-Anpassung

Trainingsvolumen-Chart bekommt zwei Linien:
- Tonnage (bisher) – grau-blau
- Effektives Volumen – kräftiges Blau, primär

Legende erklärt den Unterschied. Tooltip pro Woche zeigt beide Werte und Anteil RPE-Verteilung.

---

## 5. Task 23.3 – Plateau-Logik vereinheitlicht

### 5.1 Was wird verändert

Im Mai-2026-Report bekommt nur **Hammer Curls** das Label "Konsolidierung (RPE sinkt)", obwohl der Mechanismus auch bei anderen Plateau-Kandidaten greifen könnte. Das Label-System existiert also schon – es wird nur inkonsistent angewendet. Diese Task gleicht das an.

### 5.2 Definition Plateau vs. Konsolidierung vs. Regression

Aktuell vermutlich nur Plateau/Aktive-Progression-Unterscheidung mit einer Sonder-Erkennung für "RPE sinkt". Nach Phase 23.3 vier klar getrennte Zustände:

| Status                | Kein PR seit | Gewichts-Trend | RPE-Trend     | Bedeutung                                  |
|-----------------------|--------------|----------------|----------------|--------------------------------------------|
| Aktive Progression    | < 14 Tage    | beliebig       | beliebig       | Standard, kein Eingriff                    |
| Konsolidierung        | ≥ 14 Tage    | stabil/steigt  | sinkt/stabil   | User wird stärker, baut RPE-Reserve auf    |
| Plateau               | ≥ 30 Tage    | stabil         | stabil/steigt  | Echte Stagnation, Variation prüfen         |
| Regression            | ≥ 14 Tage    | sinkt          | beliebig       | Leistung fällt – Recovery / Krankheit?     |

**Wichtig (kritischer Punkt aus Vorgesprächen):** Konsolidierung darf Regression nicht maskieren. Reine RPE-Senkung bei sinkendem Gewicht ist Deload oder Regression – nicht Konsolidierung. Daher die Gewichts-Trend-Bedingung.

### 5.3 Algorithmus-Skizze

```python
def classify_progression_status(user, exercise, reference_date):
    last_pr = get_last_pr(user, exercise)
    if not last_pr:
        return "no_data"

    days_since_pr = (reference_date - last_pr.datum).days
    if days_since_pr < 14:
        return "active_progression"

    # Vergleichszeiträume:
    # - "current": letzte 4 Wochen
    # - "before_pr": 4 Wochen vor letztem PR
    current_weight_trend = compute_weight_trend(user, exercise, last_4_weeks)
    current_rpe_avg = compute_avg_rpe(user, exercise, last_4_weeks)
    before_pr_rpe_avg = compute_avg_rpe(user, exercise, 4w_before_pr)

    weight_stable_or_up = current_weight_trend >= -0.02   # max 2% Verlust
    weight_falling = current_weight_trend < -0.05         # mehr als 5% Verlust
    rpe_falling = current_rpe_avg < before_pr_rpe_avg - 0.5
    rpe_stable_or_rising = current_rpe_avg >= before_pr_rpe_avg - 0.3

    if weight_falling:
        return "regression"
    if weight_stable_or_up and rpe_falling:
        return "consolidation"
    if days_since_pr >= 30 and weight_stable_or_up and rpe_stable_or_rising:
        return "plateau"
    if days_since_pr < 30:
        return "light_plateau"
    return "plateau"
```

### 5.4 Edge Cases

| Fall                                            | Verhalten                                                          |
|-------------------------------------------------|--------------------------------------------------------------------|
| Übung mit weniger als 5 Sessions                | "Nicht genug Daten" statt Plateau-Label                           |
| Übung ohne RPE-Daten                            | Fallback auf alte Plateau-Logik (nur PR-Datum-basiert)            |
| Letzter PR direkt nach Plan-Wechsel             | Kein "consolidation"-Label – User ist vielleicht im neuen Plan   |
| User pausiert Übung 4 Wochen, kommt zurück      | Letzter Trainings-Tag als Vergleich, nicht reference_date          |

### 5.5 Testfälle

```
TestProgressionClassification:
  - test_active_progression_when_recent_pr
  - test_consolidation_when_weight_stable_rpe_falling
  - test_consolidation_when_weight_rising_rpe_falling
  - test_plateau_when_weight_stable_rpe_stable_30_days
  - test_regression_when_weight_falling
  - test_regression_not_masked_by_falling_rpe
  - test_no_data_when_insufficient_sessions
  - test_fallback_when_no_rpe_data
```

### 5.6 UI-Anpassung

Plateau-Tabelle in `training_pdf_simple.html` und neuer Stats-Sektion (Phase 21.3) bekommt zusätzliche Spalte oder Tooltip mit Begründung:

```
RDL · 119 kg · 20 Tage · Konsolidierung (RPE sank von 8.5 auf 7.8)
Trizeps OH · 26 kg · 58 Tage · Plateau (RPE stabil bei 8.0)
```

---

## 6. Task 23.4 – Ermüdungs-Index Zeitfenster-Konsistenz

### 6.1 Vorab-Klärung erforderlich

Aus Memory: `calculate_fatigue_index()` in `advanced_stats.py` ist möglicherweise Dead Code seit Phase 9.4. Vor jeder Implementierung:

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "calculate_fatigue_index"
```

Drei mögliche Ergebnisse:

1. **Dead Code**: Funktion entfernen, Fatigue-Index neu schreiben oder aus PDF entfernen
2. **Wird genutzt**: Genauen Aufrufer finden, Zeitraum prüfen
3. **Wird im PDF genutzt, im Web durch andere Logik ersetzt**: Tech-Debt aus Memory bestätigt – PDF angleichen

### 6.2 Was wird verändert (nach Klärung)

Annahme: Fatigue-Index bleibt erhalten, wird aber zeitfenster-konsistent neu berechnet. **Festes 14-Tage-Fenster** für alle drei Komponenten:

```
fatigue_index = (
    0.4 * normalize_volume(volume_last_14d, baseline_volume) +
    0.3 * normalize_rpe(rpe_distribution_last_14d) +
    0.3 * normalize_frequency(sessions_last_14d, target_frequency)
)
```

Wichtig: RPE-Komponente nutzt **dieselbe Verteilungslogik wie 23.1** mit 14-Tage-Fenster, nicht All-Time. Das löst das Mai-Report-Problem (0/100 trotz hohem historischen RPE-10) sauber, weil die RPE-Komponente bei <5 % RPE-10 in den letzten 14 Tagen tatsächlich niedrig anschlägt – das Verhalten *ist* dann ja korrigiert.

### 6.3 Edge Cases

| Fall                                             | Verhalten                                                          |
|--------------------------------------------------|--------------------------------------------------------------------|
| Weniger als 3 Sessions in 14 Tagen               | "Keine valide Berechnung – zu wenig Trainingstage"                 |
| Fresh Start nach langer Pause                    | Erste 14 Tage neutral (50/100), nicht künstlich niedrig            |
| Deload-Woche (wenn Block-Typ erkannt)            | Niedriger Index erwartet, ist Feature nicht Bug                    |

### 6.4 Testfälle

```
TestFatigueIndex14d:
  - test_low_when_low_volume_and_low_rpe
  - test_high_when_high_volume_and_high_rpe10
  - test_responds_to_recent_correction       # historisch hoch, jetzt niedrig → niedrig
  - test_neutral_when_insufficient_sessions
```

### 6.5 PDF vs. Live-Konsistenz

Aktuell laut Memory: PDF nutzt alte 40/30/30-Heuristik, Live-Stats hat schon RPE-10-fokussierte Version aus Phase 9.4. Diese Phase ist Anlass das anzugleichen – siehe Task 23.5.

---

## 7. Task 23.5 – PDF-Report-Konsistenz *(optional)*

### 7.1 Scope-Entscheidung

Diese Task ist **optional** und wird abhängig von Aufwand entweder Teil von Phase 23 oder als 23.x ausgegliedert. Die Live-Stats-Seite hat Vorrang (Phase 21).

**Kriterium für Aufnahme in Phase 23:** Wenn 23.1–23.4 zusammen weniger als 5 Tage Aufwand sind, 23.5 mit aufnehmen. Sonst auslagern.

### 7.2 Was wird angepasst

`core/templates/core/training_pdf_simple.html` und `core/export/stats_collector.py`:

1. RPE-Sektion: drei Zeitfenster (analog UI) statt einem All-Time-Wert
2. Trainingsvolumen-Chart: zweite Linie für Effektives Volumen
3. Plateau-Tabelle: einheitliche Status-Logik aus 23.3
4. Ermüdungs-Index: 14-Tage-Heuristik aus 23.4 (ersetzt 40/30/30 aus Phase 9.4-Tech-Debt)

### 7.3 Migrationspfad

Bestehende `stats_collector.py` liefert flat-Dict. Phase 22 hat bereits Plan-Filter eingeführt. Phase 23 ergänzt Zeitfenster-Dimension. Beispiel-Struktur:

```python
{
    "rpe_distribution": {
        "windows": {"2w": {...}, "4w": {...}, "all": {...}},
        "primary_window": "4w",
        "evaluation": "optimal",
    },
    # ...
}
```

Template iteriert über `windows`, hebt `primary_window` hervor. Bestehende Template-Sektionen bleiben rückwärtskompatibel über Default-Branch (falls `windows` fehlt → All-Time anzeigen wie bisher).

### 7.4 Testfälle

```
TestPDFExportPhase23:
  - test_rpe_section_renders_three_windows
  - test_volume_chart_renders_two_lines
  - test_fatigue_index_uses_14d_in_pdf
  - test_plateau_table_uses_unified_status
  - test_backwards_compat_when_window_data_missing
```

---

## 8. Offene Fragen vor Implementierungsbeginn

Vor dem ersten Code-Commit sollten diese Fragen beantwortet sein – idealerweise im ersten Implementierungs-Chat geklärt:

### 8.1 Fatigue-Index Dead-Code-Status

**Frage:** Wird `calculate_fatigue_index()` in `advanced_stats.py` noch aufgerufen? Wenn ja, wo?
**Klärung:** Repo-Search (siehe 6.1). Ergebnis bestimmt Scope von 23.4.
**Blocker für:** 23.4

### 8.2 Schwellenwerte für Konsolidierung

**Frage:** Welche RPE-Differenz gilt als "RPE sinkt"? Im Algorithmus-Skizze 23.3 steht 0.5 Punkte. Reicht das? Zu sensibel? Empirisch prüfen anhand bestehender Daten.
**Klärung:** Vorhandene PR-Historien manuell durchgehen, sehen welche Schwelle plausibel klassifiziert.
**Blocker für:** 23.3

### 8.3 Mindest-Datenmenge pro Zeitfenster

**Frage:** Wie viele Sätze sind nötig damit ein Zeitfenster valide auswertbar ist? Im Konzept: 30 Sätze. Bei einem User mit 1 Training/Woche und 10 Sätzen/Session wären das 3 Wochen Daten – grenzwertig.
**Klärung:** Empirische Prüfung an realen Daten (mehrere User-Profile durchspielen).
**Blocker für:** 23.1

### 8.4 Plan-Filter und Zeitfenster: Reihenfolge

**Frage:** Wenn Plan-Wechsel vor 3 Wochen war, soll 4-Wochen-RPE
- (a) auf "seit Plan-Start" verkürzen,
- (b) plan-übergreifend rechnen,
- (c) deaktiviert werden mit Hinweis "zu wenig Daten im aktuellen Plan"?

**Empfehlung im Konzept:** (a) – konsistent mit Phase 22. Aber explizit bestätigen.
**Blocker für:** 23.1, 23.2

### 8.5 Block-Typ-Awareness für 23.2

**Frage:** Soll die Effektives-Volumen-Diagnostik (Tabelle in 4.3) den Block-Typ aus Phase 3 berücksichtigen? In einer Deload-Woche sollte "Tonnage sinkt + Eff-Volumen sinkt" nicht als Regression markiert werden.
**Empfehlung:** Ja, aber als Feature-Flag – Block-Typ-Awareness ist eigene Komplexität. Falls zu groß: 23.x nachschieben.
**Blocker für:** 23.2 (Diagnose-Tabelle)

---

## 9. Reihenfolge-Empfehlung

Optimaler Pfad mit minimalem Risiko und maximalem Inkrementalwert:

1. **Vorab (kein Code):** Offene Fragen 8.1–8.4 klären. Empirische Schwellenwert-Prüfung.
2. **23.1** zuerst – isolierter, gut testbarer Effekt, klärt Zeitfenster-Helper-Infrastruktur. Sichtbarer Impact für User (Mai-Report-Problem direkt gelöst).
3. **23.3** als zweites – nutzt Zeitfenster-Helper aus 23.1, aber unabhängig von 23.2.
4. **23.2** als drittes – baut auf RPE-Filterlogik aus 23.1 auf (Wiederverwendung).
5. **23.4** als viertes – nach Klärung 8.1, nutzt 23.1-Verteilungslogik.
6. **23.5** zuletzt – konsolidiert alle Änderungen im PDF, profitiert von stabilisierten Datenstrukturen.

Jeder Sub-Schritt einzeln deploybar, keine Big-Bang-Änderung.

---

## 10. Risiken & Performance-Überlegungen

### 10.1 Performance

Drei Zeitfenster pro Stats-Request bedeutet drei DB-Queries pro RPE-Aggregation. Bei aktueller Stats-View vermutlich vernachlässigbar (User hat <1000 Sätze/Monat), aber prüfen ob `select_related` / `prefetch_related` ausreicht oder ob ein einzelner Query mit `Case/When`-Aggregation effizienter ist.

**Maßnahme:** `django-debug-toolbar` oder `connection.queries`-Inspektion vor und nach Implementierung. Akzeptanzkriterium: keine zusätzlichen N+1-Queries, Stats-View-Latenz nicht > 20 % langsamer.

### 10.2 Cache-Invalidierung

Falls bestehende Stats-Berechnungen gecached sind (Memory erwähnt Cache in `setUp`-Tests): Cache-Keys um Zeitfenster-Dimension erweitern. `cache.clear()`-Pattern aus bestehenden Tests übernehmen.

### 10.3 Rückwärtskompatibilität

Templates und PDF müssen mit alter und neuer Datenstruktur klarkommen während der Migration. Default-Branch: wenn `windows`-Dict fehlt, Verhalten wie bisher (All-Time-Wert anzeigen). Test-Coverage dafür siehe 7.4.

### 10.4 Verwirrung beim User durch drei Werte

Drei Zahlen statt einer kann überfordern. Mitigation: 4-Wochen-Wert visuell dominant, andere zwei kleiner und sekundär. Empfehlungstext nennt explizit den primären Zeitraum.

---

## 11. Start-Prompt für Implementierungs-Chat

Ready-to-paste für nächsten Chat:

```
Phase 23 starten – Zeitfenster-basierte Trainingsanalysen.

Kontext: Lies zuerst:
1. docs/journal.txt (letzte 80 Zeilen)
2. docs/PROJECT_ROADMAP.md – Phase 23 Eintrag
3. docs/phase23_concept.md – Detail-Fahrplan

Vor jedem Code-Touch: Offene Fragen aus Abschnitt 8 des Detail-Konzepts
klären. Speziell 8.1 (Fatigue-Index Dead Code) per Repo-Search.

Reihenfolge: 23.1 → 23.3 → 23.2 → 23.4 → 23.5 (siehe Abschnitt 9).

Branch beim Start: feature/phase23-time-windowed-stats

Schritt 1 deines Plans: Beantworte 8.1 + 8.4, präsentiere Plan für 23.1
inkl. konkreter Datei-Anpassungen, warte auf Bestätigung.
```

---

## 12. Done-Definition für Phase 23

- [ ] Alle Tasks 23.1–23.4 implementiert
- [ ] 23.5 entweder implementiert ODER bewusst als 23.x ausgelagert (Roadmap-Eintrag)
- [ ] Alle Testfälle aus Abschnitten 3.5, 4.5, 5.5, 6.4, 7.4 grün
- [ ] Mai-2026-Report-Daten würden mit neuer Logik plausibles Bild geben (manuelle Prüfung)
- [ ] Performance-Akzeptanzkriterium aus 10.1 erfüllt
- [ ] Journal-Eintrag pro Sub-Phase
- [ ] PROJECT_ROADMAP.md Phase 23 Status auf ✅ Abgeschlossen
- [ ] Bekannte Tech-Debt aus Phase 9.4 entweder gelöst (PDF angeglichen) oder explizit als bestehend dokumentiert

---

**Ende Detail-Konzept Phase 23**
