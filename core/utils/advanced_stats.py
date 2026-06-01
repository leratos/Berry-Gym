"""
Advanced Training Statistics - Helper Functions
Provides comprehensive analysis for training progression, consistency, and performance.
"""

from datetime import datetime, timedelta

from django.utils import timezone

# Phase 23: Zeitfenster-Konstanten für gestaffelte Trainingsanalysen
WINDOW_2W_DAYS = 14
WINDOW_4W_DAYS = 28
# Minimum Sätze, damit ein Zeitfenster valide auswertbar ist (Konzept 3.4 / 8.3).
# Empirisch justierbar – aktuell konservativer Default.
MIN_SETS_FOR_WINDOW = 30
# Minimum Sätze für 2w-Hinweis-Logik (kleiner als MIN_SETS_FOR_WINDOW, da 2w
# inhaltlich weniger Aussagekraft braucht – nur "Trend ändert sich"-Signal).
MIN_SETS_FOR_DIVERGENCE = 10
# Schwelle in Prozentpunkten, ab der ein Trend-Hinweis "Verhalten weicht ab"
# zwischen 2-Wochen- und 4-Wochen-RPE-10-Anteil ausgelöst wird (Konzept 3.3).
DIVERGENCE_THRESHOLD_PCT = 5.0

# Phase 23.3: Plateau-Logik vereinheitlicht
# RPE-Differenz first-half vs. second-half der letzten 4w → "Konsolidierung".
# Empirisch validiert (Mai-2026-Daten): die alte First/Second-Half-Logik mit
# 0.5-Schwelle hat Hammer Curls korrekt als Konsolidierung erkannt; höhere
# Schwellen würden zu wenig fangen, niedrigere wären Noise.
CONSOLIDATION_RPE_DELTA = 0.5
# >5% 1RM-Drop im current 4w gegenüber PR → Regression (vorher 10%).
REGRESSION_WEIGHT_DROP_PCT = 5.0
# < 2 Sätze in den letzten 4w → "Pause" statt "Plateau". Adressiert die im
# Mai-2026-Report sichtbare Inkonsistenz: Übungen, die seit Wochen nicht
# trainiert wurden, sollen nicht als "Plateau" gelten.
PAUSE_MIN_CUR_SETS = 2
# Min. RPE-erfasste Sätze in letzten 4w für Konsolidierungs-Check.
PROGRESSION_RPE_MIN_SETS = 4

# Phase 24.5: Plateau-Status entkoppelt von langfristiger Steigerungsrate.
# Wenn die historische Steigerungsrate (kg/Monat) ≥ X % des aktuellen PR-1RM
# beträgt UND die Trainingshistorie der Übung lang genug ist, wird die reine
# Tage-seit-PR-Diagnose ("Plateau") überschrieben mit
# ``active_progression_paused`` ("Aktive Progression (PR-Pause)").
# Konservativ gewählt: 2 % pro Monat = ein Jahr lang stetiger Aufbau, das ist
# klare Progression. RDL-Fall (+26.5 kg/Monat bei ~73 kg 1RM ≙ 36 %) wird
# damit eindeutig nicht mehr als Plateau klassifiziert; eine echte 1 %/Monat-
# Mikroprogression bleibt korrekt als Plateau klassifiziert.
PROGRESSION_RATE_OVERRIDE_PCT = 2.0
# Übungen mit weniger als ~3 Wochen Historie haben zu starkes Rauschen in
# `progression_pro_monat`, der Override soll dort nicht greifen.
PROGRESSION_RATE_MIN_HISTORY_DAYS = 21
# Phase 24.5a: Steigerungsrate für die Override-Entscheidung wird über das
# aktuelle Fenster (Default 8 Wochen) berechnet, NICHT mehr über das All-Time-
# Mittel. Damit werden lange Stagnationen mit hoher Anfangs-Steigerungsrate
# (z.B. Trizeps OH: 9 Wochen flach nach starkem Aufbau) wieder korrekt als
# Plateau klassifiziert. Das All-Time-Mittel war als Trigger zu großzügig.
PROGRESSION_RATE_RECENT_WINDOW_WEEKS = 8

# Phase 23.2: Effektives Volumen
# RPE-Range, der als "produktives" Volumen gilt – außerhalb davon liegt
# Junk Volume (RPE <7, zu leicht) bzw. Failure Volume (RPE 10, recovery-teuer).
EFFECTIVE_VOLUME_RPE_MIN = 7.0
EFFECTIVE_VOLUME_RPE_MAX = 9.0
# Schwelle für "Volumen sinkt/steigt"-Klassifikation (Diagnose-Tabelle 4.3).
# 5 % Differenz Woche-zu-Woche zählt als "stabil", darüber als Trend.
VOLUME_TREND_STABLE_PCT = 5.0
# Hybrid-Block-Typ-Awareness (Phase 23.2 / Frage 8.5):
# Wenn ≥50 % der Sessions einer Woche `ist_deload=True` haben, gilt die
# Woche als Deload-Woche und der "Regression"-Hinweis wird unterdrückt.
DELOAD_WEEK_MAJORITY_PCT = 50.0


def _find_best_1rm_satz(uebung_saetze):
    """Liefert (best_1rm, best_satz) via Epley-Formel über alle gewichteten Sätze.

    Bei Gleichstand gewinnt der **chronologisch erste** Satz (strict >), damit
    `tage_seit_pr` plausibel ist (= Datum, an dem der PR erstmals erreicht wurde).
    """
    bester_1rm = 0.0
    bester_satz = None
    for satz in uebung_saetze.filter(gewicht__isnull=False).order_by("einheit__datum"):
        wdh = satz.wiederholungen or 1
        einzel_1rm = float(satz.gewicht) * (1 + wdh / 30.0)
        if einzel_1rm > bester_1rm:
            bester_1rm = einzel_1rm
            bester_satz = satz
    return bester_1rm, bester_satz


def compute_progression_rate(
    uebung_saetze,
    pr_satz,
    *,
    reference_date=None,
    recent_window_weeks: int = PROGRESSION_RATE_RECENT_WINDOW_WEEKS,
) -> tuple[float, int]:
    """Phase 24.5 / 24.5a: Helper für ``classify_progression_status``-Override.

    Berechnet die 1RM-Steigerungsrate (kg/Monat) über das **aktuelle Fenster**
    (Default 8 Wochen) und die All-Time-Trainingshistorie der Übung (Tage
    zwischen erstem gewichteten Satz und PR-Satz). Wird sowohl von
    ``calculate_plateau_analysis`` (PDF) als auch von ``_calc_plateau_live``
    (Dashboard) genutzt, damit beide Pfade identisch klassifizieren.

    Vor Phase 24.5a war die Rate das All-Time-Mittel zwischen erstem Satz und
    PR. Das führte dazu, dass eine Übung mit starkem Anfangsaufbau und
    anschließender Stagnation (z.B. Trizeps OH: 5 → 17,5 kg in 8 Wochen, dann
    9 Wochen flach) trotz materiellem Plateau als ``active_progression_paused``
    klassifiziert wurde. Die Recent-Window-Rate misst stattdessen den
    *aktuellen* Trend.

    Args:
        uebung_saetze: Satz-Queryset für genau eine Übung.
        pr_satz: Satz mit dem höchsten geschätzten 1RM.
        reference_date: Stichtag (Default ``timezone.now()``). Das
            Recent-Window endet hier und reicht
            ``recent_window_weeks`` Wochen zurück.
        recent_window_weeks: Länge des Recent-Windows in Wochen
            (Default ``PROGRESSION_RATE_RECENT_WINDOW_WEEKS``).

    Returns:
        ``(progression_pro_monat, training_history_days)`` – Rate über das
        Recent-Window, History in Tagen *all-time* (= PR-Datum minus
        erster-Satz-Datum). ``history_days`` bleibt all-time, damit der
        Min-History-Schutz in ``classify_progression_status`` unverändert
        wirken kann (junge Übungen → kein Override).
    """
    if pr_satz is None or not pr_satz.gewicht:
        return 0.0, 0
    weighted_saetze = list(uebung_saetze.filter(gewicht__isnull=False).order_by("einheit__datum"))
    if not weighted_saetze:
        return 0.0, 0
    erster = weighted_saetze[0]
    history_days = (pr_satz.einheit.datum.date() - erster.einheit.datum.date()).days
    if history_days <= 0:
        return 0.0, 0

    if reference_date is None:
        reference_date = timezone.now()
    window_start = reference_date - timedelta(days=recent_window_weeks * 7)
    recent = [s for s in weighted_saetze if s.einheit.datum >= window_start and s.gewicht]
    if len(recent) < 2:
        return 0.0, history_days
    erster_recent, letzter_recent = recent[0], recent[-1]
    span_days = (letzter_recent.einheit.datum.date() - erster_recent.einheit.datum.date()).days
    if span_days <= 0:
        return 0.0, history_days
    erstes_1rm = float(erster_recent.gewicht) * (1 + (erster_recent.wiederholungen or 1) / 30.0)
    letztes_1rm = float(letzter_recent.gewicht) * (1 + (letzter_recent.wiederholungen or 1) / 30.0)
    rate = round((letztes_1rm - erstes_1rm) / span_days * 30, 2)
    return rate, history_days


# ─────────────────────────────────────────────────────────────────────────────
# Phase 27.4: Status → Form (Single Source der §C-Zuordnung des Style-Konzepts).
# Live nutzt Bootstrap-Icons, PDF Unicode-Geometrie. Emoji sind aus den Labels
# entfernt; die FORM trägt das Icon/Glyph, die BEDEUTUNG das Textlabel daneben.
# consolidation_ready/_overlong sind vorausschauend gemappt (Phase 26), damit
# der Merge mit der Phase-26-Branch keine Lücke hinterlässt.
# ─────────────────────────────────────────────────────────────────────────────
_PROGRESSION_STATUS_ICON = {
    "active_progression": "bi-graph-up-arrow",
    "active_progression_paused": "bi-graph-up-arrow",
    "observe": "bi-eye",
    "pause": "bi-pause-circle",
    "consolidation": "bi-arrow-left-right",
    "consolidation_ready": "bi-arrow-up-circle",
    "consolidation_overlong": "bi-hourglass-split",
    "plateau_light": "bi-dash-circle",
    "plateau": "bi-exclamation-triangle-fill",
    "plateau_long": "bi-x-octagon-fill",
    "regression": "bi-graph-down-arrow",
    "no_data": "bi-question-circle",
}
_PROGRESSION_STATUS_GLYPH = {
    "active_progression": "▲",
    "active_progression_paused": "▲",
    "observe": "○",
    "pause": "‖",
    "consolidation": "◇",
    "consolidation_ready": "◆",
    "consolidation_overlong": "◆",
    "plateau_light": "◆",
    "plateau": "■",
    "plateau_long": "✕",
    "regression": "▼",
    "no_data": "·",
}


def _finalize_progression(result: dict) -> dict:
    """Phase 27.4: ergänzt ``status_icon`` (Bootstrap-Icon, live) und
    ``status_glyph`` (Unicode-Geometrie, PDF) anhand des Status-Keys."""
    status = result.get("status", "no_data")
    result["status_icon"] = _PROGRESSION_STATUS_ICON.get(status, "")
    result["status_glyph"] = _PROGRESSION_STATUS_GLYPH.get(status, "")
    return result


def classify_progression_status(
    uebung_saetze,
    pr_satz,
    reference_date=None,
    *,
    progression_pro_monat=None,
    training_history_days=None,
):
    """
    Klassifiziert den Progressions-Status einer einzelnen Übung (Phase 23.3).

    Status-Hierarchie (höchste Priorität zuerst):
        1. ``regression``                  – >5 % 1RM-Drop im aktuellen 4w-Fenster vs. PR
        2. ``active_progression``          – PR ≤ 7 Tage alt
        3. ``observe``                     – PR 8–14 Tage alt
        4. ``pause``                       – < 2 Sätze in den letzten 4w
        5. ``consolidation``               – RPE sinkt (≥ 0.5) first-half vs. second-half
        6. ``active_progression_paused``   – Phase 24.5: lange Steigerungsrate ≥
                                             ``PROGRESSION_RATE_OVERRIDE_PCT`` % vom PR-1RM
                                             pro Monat → keine echte Stagnation
        7. ``plateau_light``               – 15–42 Tage seit PR, sonst kein Auslöser
        8. ``plateau``                     – 43–84 Tage seit PR
        9. ``plateau_long``                – > 84 Tage seit PR
       10. ``no_data``                     – kein PR-Satz vorhanden

    Args:
        uebung_saetze: Satz-Queryset für genau eine Übung. Sollte bereits
            user-, warmup- und deload-gefiltert sein.
        pr_satz: Satz mit dem höchsten geschätzten 1RM (oder ``is_pr=True``-Satz).
            Muss ``gewicht`` und ``einheit.datum`` haben.
        reference_date: Stichtag (default ``timezone.now()``).
        progression_pro_monat: float oder None – durchschnittlicher 1RM-Zuwachs in
            kg/Monat über die gesamte erfasste Übungshistorie. Optional; wird nur
            für die Phase-24.5-Override genutzt.
        training_history_days: int oder None – Tage zwischen erstem Satz der Übung
            und dem PR-Satz. Optional; gemeinsam mit ``progression_pro_monat`` für
            den Override genutzt (Schutz vor zu kurzer Historie).

    Returns:
        dict mit:
            - ``status``: einer der oben gelisteten Schlüssel
            - ``status_label``: Lesbarer Label-String (mit Emoji)
            - ``status_farbe``: Bootstrap-Color-Class
            - ``days_since_pr``: int oder None
            - ``rpe_first_half``, ``rpe_second_half``, ``rpe_delta``: float oder None
            - ``weight_drop_pct``: float oder None (positiv = Drop gegenüber PR)
            - ``cur_4w_n``: Anzahl Sätze in letzten 4w (für Pause-Erkennung)
            - ``progression_rate_pct``: float oder None – relativer monatlicher
                Zuwachs (kg/Monat / PR-1RM × 100). Nur gesetzt, wenn der Phase-24.5-
                Override greift bzw. die Eingabewerte ausreichend sind.
    """
    if reference_date is None:
        reference_date = timezone.now()

    result = {
        "status": "no_data",
        "status_label": "Keine Daten",
        "status_farbe": "secondary",
        "days_since_pr": None,
        "rpe_first_half": None,
        "rpe_second_half": None,
        "rpe_delta": None,
        "weight_drop_pct": None,
        "cur_4w_n": 0,
        "progression_rate_pct": None,
    }

    if not pr_satz or not pr_satz.gewicht or not getattr(pr_satz, "einheit", None):
        return _finalize_progression(result)

    pr_date = pr_satz.einheit.datum
    days_since_pr = (reference_date.date() - pr_date.date()).days
    result["days_since_pr"] = days_since_pr
    pr_1rm = float(pr_satz.gewicht) * (1 + (pr_satz.wiederholungen or 1) / 30.0)

    vier_wochen_start = reference_date - timedelta(days=28)
    cur_saetze = list(
        uebung_saetze.filter(einheit__datum__gte=vier_wochen_start).order_by("einheit__datum")
    )
    result["cur_4w_n"] = len(cur_saetze)

    # Weight-Drop berechnen, sofern mindestens 1 Working Set in den letzten 4w
    cur_weighted = [s for s in cur_saetze if s.gewicht]
    if cur_weighted and pr_1rm > 0:
        cur_best_1rm = max(
            float(s.gewicht) * (1 + (s.wiederholungen or 1) / 30.0) for s in cur_weighted
        )
        result["weight_drop_pct"] = round((pr_1rm - cur_best_1rm) / pr_1rm * 100, 2)

    # 1) Regression schlägt alles
    if (
        result["weight_drop_pct"] is not None
        and result["weight_drop_pct"] > REGRESSION_WEIGHT_DROP_PCT
    ):
        result.update(status="regression", status_label="Rückschritt", status_farbe="danger")
        return _finalize_progression(result)

    # 2) Frischer PR
    if days_since_pr <= 7:
        result.update(
            status="active_progression",
            status_label="Aktive Progression",
            status_farbe="success",
        )
        return _finalize_progression(result)
    if days_since_pr <= 14:
        result.update(status="observe", status_label="Beobachten", status_farbe="info")
        return _finalize_progression(result)

    # 3) Pause: zu wenig aktuelle Sätze, kein Regressions-Signal
    if result["cur_4w_n"] < PAUSE_MIN_CUR_SETS:
        result.update(status="pause", status_label="Pause", status_farbe="secondary")
        return _finalize_progression(result)

    # 4) Konsolidierung: RPE-Trend in den letzten 4w vergleichen.
    rpe_saetze = [s for s in cur_saetze if s.rpe is not None and s.gewicht]
    if len(rpe_saetze) >= PROGRESSION_RPE_MIN_SETS:
        rpe_values = [float(s.rpe) for s in rpe_saetze]
        mid = len(rpe_values) // 2
        first_half = sum(rpe_values[:mid]) / mid
        second_half = sum(rpe_values[mid:]) / len(rpe_values[mid:])
        delta = first_half - second_half
        result["rpe_first_half"] = round(first_half, 2)
        result["rpe_second_half"] = round(second_half, 2)
        result["rpe_delta"] = round(delta, 2)
        if delta >= CONSOLIDATION_RPE_DELTA:
            result.update(
                status="consolidation",
                status_label="Konsolidierung (RPE sinkt)",
                status_farbe="info",
            )
            return _finalize_progression(result)

    # Phase 24.5: Override – starke Steigerungsrate schlägt Plateau-Klassifikation.
    # Greift NACH Konsolidierung (RPE sinkt hat Vorrang) und VOR der reinen
    # Tage-seit-PR-Logik. Schutz: nur wenn Eingaben da sind und die
    # Übungshistorie hinreichend lang ist – sonst Rauschen aus 2–3 Sätzen.
    #
    # Phase 24.5a: ``progression_pro_monat`` wird über das aktuelle 8w-Fenster
    # berechnet (siehe ``compute_progression_rate``). Eine Rate von 0 / leicht
    # negativ ist sinnvoll – sie zeigt eine flache Gegenwart trotz langer
    # Historie und führt korrekt NICHT zum Override.
    if (
        progression_pro_monat is not None
        and progression_pro_monat >= 0
        and training_history_days is not None
        and training_history_days >= PROGRESSION_RATE_MIN_HISTORY_DAYS
        and pr_1rm > 0
    ):
        rate_pct = round(progression_pro_monat / pr_1rm * 100, 1)
        if rate_pct >= PROGRESSION_RATE_OVERRIDE_PCT:
            result.update(
                status="active_progression_paused",
                status_label="Aktive Progression (PR-Pause)",
                status_farbe="success",
                progression_rate_pct=rate_pct,
            )
            return _finalize_progression(result)
        result["progression_rate_pct"] = rate_pct

    # 5) Plateau nach Tagen seit PR
    if days_since_pr <= 42:
        result.update(
            status="plateau_light",
            status_label="Leichtes Plateau",
            status_farbe="warning",
        )
    elif days_since_pr <= 84:
        result.update(status="plateau", status_label="Plateau", status_farbe="danger")
    else:
        result.update(status="plateau_long", status_label="Langzeit-Plateau", status_farbe="danger")
    return _finalize_progression(result)


def calculate_plateau_analysis(alle_saetze, top_uebungen):
    """
    Analyzes progression for top exercises to detect plateaus.

    Returns list with:
    - uebung: Exercise name
    - letzter_pr: Last personal record weight (estimated 1RM)
    - pr_datum: Date of last PR
    - tage_seit_pr: Days since last PR
    - progression_pro_monat: Average weight increase per month
    - status: status key (siehe :func:`classify_progression_status`)
    - status_label, status_farbe: Anzeige-Felder
    - rpe_first_half, rpe_second_half, rpe_delta, weight_drop_pct, cur_4w_n: Diagnose-Daten
    - muskelgruppe: Muscle group
    """
    heute = timezone.now()
    plateau_analysis = []

    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]
        muskelgruppe = uebung.get("muskelgruppe_display", "")

        uebung_saetze = alle_saetze.filter(uebung__bezeichnung=uebung_name).order_by(
            "einheit__datum"
        )

        if uebung_saetze.count() < 2:
            continue

        bester_1rm, pr_satz = _find_best_1rm_satz(uebung_saetze)
        if not pr_satz:
            continue

        letzter_pr = round(bester_1rm, 1)
        pr_datum = pr_satz.einheit.datum

        # Phase 24.5a: Steigerungsrate über das aktuelle 8-Wochen-Fenster,
        # nicht mehr All-Time. Anker = ``heute`` für Test-Determinismus.
        progression_pro_monat, training_history_days = compute_progression_rate(
            uebung_saetze, pr_satz, reference_date=heute
        )

        classification = classify_progression_status(
            uebung_saetze,
            pr_satz,
            reference_date=heute,
            progression_pro_monat=progression_pro_monat,
            training_history_days=training_history_days,
        )

        plateau_analysis.append(
            {
                "uebung": uebung_name,
                "muskelgruppe": muskelgruppe,
                "letzter_pr": letzter_pr,
                "pr_datum": pr_datum.strftime("%d.%m.%Y"),
                "tage_seit_pr": classification["days_since_pr"],
                "progression_pro_monat": progression_pro_monat,
                "progression_rate_pct": classification["progression_rate_pct"],
                "status": classification["status"],
                "status_label": classification["status_label"],
                "status_farbe": classification["status_farbe"],
                "status_icon": classification["status_icon"],
                "status_glyph": classification["status_glyph"],
                "rpe_first_half": classification["rpe_first_half"],
                "rpe_second_half": classification["rpe_second_half"],
                "rpe_delta": classification["rpe_delta"],
                "weight_drop_pct": classification["weight_drop_pct"],
                "cur_4w_n": classification["cur_4w_n"],
            }
        )

    return plateau_analysis


def calculate_consistency_metrics(alle_trainings):
    """
    Calculates training consistency metrics including streaks and adherence.

    Returns dict with:
    - aktueller_streak: Current weeks with training
    - laengster_streak: Longest streak ever
    - adherence_rate: % of weeks with training
    - avg_pause_tage: Average days between sessions
    - bewertung: Overall consistency rating
    """
    if not alle_trainings.exists():
        return None

    heute = timezone.now()

    # Streak berechnen (aufeinanderfolgende Wochen mit mindestens 1 Training)
    aktueller_streak = 0
    laengster_streak = 0
    temp_streak = 0
    aktueller_streak_aktiv = True  # Flag ob wir noch im aktuellen Streak sind

    check_date = heute
    wochen_geprueft = 0

    while wochen_geprueft < 104:  # Max 2 Jahre zurück
        iso_weekday = check_date.isoweekday()
        week_start = check_date - timedelta(days=iso_weekday - 1)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        is_current_week = wochen_geprueft == 0

        trainings_in_week = alle_trainings.filter(datum__gte=week_start, datum__lt=week_end).count()

        if trainings_in_week > 0:
            temp_streak += 1
            if temp_streak > laengster_streak:
                laengster_streak = temp_streak
            # Aktueller Streak: Nur Wochen die direkt zusammenhängen bis heute
            if aktueller_streak_aktiv:
                aktueller_streak = temp_streak
        elif is_current_week:
            # Laufende Woche ohne Training ist neutral – sie darf den Streak
            # nicht brechen, weil der User noch Zeit hat zu trainieren.
            pass
        else:
            # Streak unterbrochen
            if aktueller_streak_aktiv:
                # Erste Lücke = aktueller Streak endet hier
                aktueller_streak_aktiv = False
            temp_streak = 0

        # Gehe 1 Woche zurück
        check_date = week_start - timedelta(days=1)
        wochen_geprueft += 1

    # Adherence Rate: % der Wochen mit Training
    # WICHTIG: Zähler (wochen_mit_training) und Nenner (wochen_gesamt) müssen
    # dieselbe Einheit verwenden – beide basieren auf ISO-Kalenderwochen.
    # Vorher: wochen_gesamt = days // 7 (Ganzzahl-Division) vs. Django-Kalenderwochen
    # → führte zu Adherence > 100% wenn Trainings Wochengrenzen überbrücken.
    erste_training = alle_trainings.order_by("datum").first()
    if erste_training:
        erste_datum = erste_training.datum.date()
        heute_datum = heute.date()
        # Montag der Startwoche und Montag der aktuellen Woche
        erste_woche_montag = erste_datum - timedelta(days=erste_datum.weekday())
        heute_woche_montag = heute_datum - timedelta(days=heute_datum.weekday())
        # Anzahl Kalenderwochen inklusiv Start- und Endwoche
        wochen_gesamt = max(1, ((heute_woche_montag - erste_woche_montag).days // 7) + 1)
        wochen_mit_training = alle_trainings.dates("datum", "week").count()
        # min(100.0) als Sicherheitsnetz (darf nie über 100% liegen)
        adherence_rate = min(100.0, round((wochen_mit_training / wochen_gesamt) * 100, 1))
    else:
        adherence_rate = 0

    # Durchschnittliche Pause zwischen Trainings
    trainings_sorted = list(alle_trainings.order_by("datum").values_list("datum", flat=True))
    if len(trainings_sorted) > 1:
        pausen = []
        for i in range(1, len(trainings_sorted)):
            pause_tage = (trainings_sorted[i].date() - trainings_sorted[i - 1].date()).days
            pausen.append(pause_tage)
        avg_pause_tage = round(sum(pausen) / len(pausen), 1)
    else:
        avg_pause_tage = 0

    # Bewertung
    if aktueller_streak >= 12 and adherence_rate >= 85:
        bewertung = "Exzellent"
        bewertung_farbe = "success"
    elif aktueller_streak >= 8 and adherence_rate >= 70:
        bewertung = "Sehr gut"
        bewertung_farbe = "success"
    elif aktueller_streak >= 4 and adherence_rate >= 60:
        bewertung = "Gut"
        bewertung_farbe = "info"
    elif adherence_rate >= 40:
        bewertung = "Ausbaufähig"
        bewertung_farbe = "warning"
    else:
        bewertung = "Inkonsistent"
        bewertung_farbe = "danger"

    return {
        "aktueller_streak": aktueller_streak,
        "laengster_streak": laengster_streak,
        "adherence_rate": adherence_rate,
        "avg_pause_tage": avg_pause_tage,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
    }


def calculate_fatigue_index(weekly_volume_data, rpe_saetze, alle_trainings):
    """
    Calculates fatigue index and deload recommendations.

    Delegiert an die Dashboard-Helfer in training_stats.py (Phase 14 Konsolidierung),
    damit Dashboard und PDF-Export identische Fatigue-Berechnung verwenden.

    Die Dashboard-Version (Phase 9.4+) nutzt RPE-10-Verteilung statt einfachem
    RPE-Durchschnitt, berücksichtigt Cardio, und hat Block-Age-Awareness.

    Phase 23.4: Zeitfenster sind explizit dokumentiert in den Dashboard-Helfern
    (``training_stats.py``: ``FATIGUE_RPE_WINDOW_DAYS=14``,
    ``FATIGUE_FREQUENCY_WINDOW_DAYS=7``, ``FATIGUE_CARDIO_WINDOW_DAYS=7``).
    RPE-Komponente ist konsistent mit der RPE-Verteilung aus 23.1 (4-Wochen-
    Bewertung der Karten + 14-Tage-Fenster im Index = derselbe Trend-Bereich).

    Returns dict with:
    - fatigue_index, bewertung, bewertung_farbe, empfehlung
    - volumen_spike, rpe_steigend, deload_empfohlen
    - naechste_deload, warnungen
    """
    from core.utils.week_classification import select_comparable_weeks
    from core.views.training_stats import (
        _get_cardio_fatigue,
        _get_frequency_fatigue,
        _get_rpe_fatigue,
        _get_volume_spike_fatigue,
    )

    heute = timezone.now()

    # User aus QuerySet ableiten (alle_trainings ist user-gefiltert)
    user = None
    first_training = alle_trainings.first()
    if first_training:
        user = first_training.user

    fatigue_index = 0
    warnungen = []

    # Volumen-Spike: Vergleich nur über vergleichbare Wochen (Phase 24.1b).
    # Deload-Mehrheits-, Plan-Wechsel- und laufende Wochen werden über
    # ``select_comparable_weeks`` ausgefiltert – derselbe Klassifikator wie in
    # der 24.1-Volumen-Diagnose. Damit fällt die fälschliche „Sehr starker
    # Volumen-Anstieg"-Warnung bei Re-Aufbau nach Deload weg.
    comparable_weeks = select_comparable_weeks(weekly_volume_data)
    if len(comparable_weeks) >= 2:
        dashboard_volumes = [
            {"volume": comparable_weeks[-1].get("volumen", 0)},
            {"volume": comparable_weeks[-2].get("volumen", 0)},
        ]
        pts, warns = _get_volume_spike_fatigue(dashboard_volumes)
        fatigue_index += pts
        warnungen.extend(warns)

    volumen_spike = fatigue_index > 0

    # RPE + Frequenz + Cardio: nutzen User-Objekt
    rpe_steigend = False
    if user and alle_trainings.count() >= 4:
        rpe_pts, rpe_warns = _get_rpe_fatigue(user, heute)
        fatigue_index += rpe_pts
        warnungen.extend(rpe_warns)
        rpe_steigend = rpe_pts > 0

        freq_pts, freq_warns = _get_frequency_fatigue(user, heute)
        fatigue_index += freq_pts
        warnungen.extend(freq_warns)

    if user:
        cardio_pts, cardio_warns, _, _ = _get_cardio_fatigue(user, heute)
        fatigue_index += cardio_pts
        warnungen.extend(cardio_warns)

    # Deload-Empfehlung + Bewertung (identisch mit Dashboard)
    deload_empfohlen = fatigue_index >= 50
    naechste_deload = heute + timedelta(weeks=6)

    if fatigue_index >= 60:
        bewertung = "Hoch"
        bewertung_farbe = "danger"
        empfehlung = "Deload-Woche empfohlen! Reduziere Volumen um 40-50%."
    elif fatigue_index >= 40:
        bewertung = "Moderat"
        bewertung_farbe = "warning"
        empfehlung = "Achte auf ausreichend Regeneration."
    elif fatigue_index >= 20:
        bewertung = "Niedrig"
        bewertung_farbe = "info"
        empfehlung = "Gute Balance zwischen Training und Erholung."
    else:
        bewertung = "Sehr niedrig"
        bewertung_farbe = "success"
        # Phase 23.x: vorher "Du kannst noch mehr trainieren!" – missverständlich,
        # klang nach Aufforderung zu mehr Volumen statt nach Belastbarkeits-Status.
        empfehlung = "Geringe Ermüdung – Belastung wird gut verkraftet."

    return {
        "fatigue_index": fatigue_index,
        "volumen_spike": volumen_spike,
        "rpe_steigend": rpe_steigend,
        "deload_empfohlen": deload_empfohlen,
        "naechste_deload": naechste_deload.strftime("%d.%m.%Y"),
        "warnungen": warnungen,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
        "empfehlung": empfehlung,
    }


def calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht=None):
    """
    Calculates 1RM estimates and compares against strength standards from database.
    Standards are now stored per-exercise in the Uebung model.

    Uses Epley Formula: 1RM = Gewicht × (1 + Wiederholungen/30)

    Returns list with:
    - uebung: Exercise name
    - muskelgruppe: Muscle group
    - geschaetzter_1rm: Estimated 1RM in kg
    - 1rm_entwicklung: List of dicts with 'monat' and '1rm' keys for 6-month progression
    - standard_info: Dict with level, progress, and standards
    """
    from core.models import Uebung

    if not alle_saetze.exists() or not top_uebungen:
        return []

    heute = timezone.now()

    ergebnisse = []

    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]

        # Hole Übung aus DB
        try:
            uebung_obj = Uebung.objects.get(bezeichnung=uebung_name)
        except Uebung.DoesNotExist:
            continue

        # Prüfe ob diese Übung Standards hat
        if not uebung_obj.standard_beginner:
            # Keine Standards definiert - überspringe
            continue

        # Hole alle Sätze für diese Übung
        uebung_saetze = alle_saetze.filter(uebung__bezeichnung=uebung_name)

        # 1RM berechnen für jeden Satz
        beste_1rm = 0
        for satz in uebung_saetze:
            if satz.wiederholungen and satz.wiederholungen > 0:
                gewicht = float(satz.gewicht or 0)
                # Epley Formel
                estimated_1rm = gewicht * (1 + satz.wiederholungen / 30.0)
                if estimated_1rm > beste_1rm:
                    beste_1rm = estimated_1rm

        if beste_1rm == 0:
            continue

        # 6-Monats-Entwicklung (Format für Template: Liste von Dicts)
        # Bugfix: Formel war `30 * (5 - i)`, so dass der letzte Slot (i=5)
        # monat_start = heute, monat_ende = heute + 30 ergab → Zukunft, keine Daten.
        # Fix: `30 * (6 - i)` → letzter Slot = heute-30 bis heute (aktueller Monat korrekt befüllt).
        # Monatslabel vom Ende-Datum (nicht Start), damit der aktuelle Monat korrekt beschriftet wird.
        entwicklung_liste = []
        for i in range(6):
            monat_start = heute - timedelta(days=30 * (6 - i))
            monat_ende = monat_start + timedelta(days=30)
            monat_saetze = uebung_saetze.filter(
                einheit__datum__gte=monat_start, einheit__datum__lte=monat_ende
            )

            monat_best_1rm = 0
            for satz in monat_saetze:
                if satz.wiederholungen and satz.wiederholungen > 0:
                    gewicht = float(satz.gewicht or 0)
                    estimated_1rm = gewicht * (1 + satz.wiederholungen / 30.0)
                    if estimated_1rm > monat_best_1rm:
                        monat_best_1rm = estimated_1rm

            # Label vom Ende-Datum, damit der aktuelle Monat korrekt angezeigt wird
            monat_name = monat_ende.strftime("%b")
            entwicklung_liste.append(
                {
                    "monat": monat_name,
                    "1rm": round(monat_best_1rm, 1) if monat_best_1rm > 0 else None,
                }
            )

        # Allometrische Skalierung (Jaric, 2002; Batterham & George, 1997)
        # Kraft skaliert NICHT linear mit Körpergewicht (lineares Modell ist ein bekannter Fehler).
        # Exponent 2/3 (≈ 0.667) ist der wissenschaftlich belegte Standard für
        # absolute Kraftleistung relativ zur Körpermasse.
        # Formel: skalierter_standard = basis_standard × (user_kg / 80.0) ^ (2/3)
        gewicht_float = float(user_gewicht) if user_gewicht else 80.0
        scaling_factor = (gewicht_float / 80.0) ** (2 / 3)

        standards = {
            "beginner": round(float(uebung_obj.standard_beginner) * scaling_factor, 1),
            "intermediate": round(float(uebung_obj.standard_intermediate) * scaling_factor, 1),
            "advanced": round(float(uebung_obj.standard_advanced) * scaling_factor, 1),
            "elite": round(float(uebung_obj.standard_elite) * scaling_factor, 1),
        }

        # Level bestimmen
        standard_level = "untrainiert"
        naechstes_level = None
        prozent_bis_naechstes = 0

        if beste_1rm < standards["beginner"]:
            standard_level = "untrainiert"
            naechstes_level = "beginner"
            naechstes_gewicht = standards["beginner"]
            prozent_bis_naechstes = round((beste_1rm / naechstes_gewicht) * 100, 1)
        else:
            levels_order = ["beginner", "intermediate", "advanced", "elite"]
            for level in levels_order:
                if beste_1rm >= standards[level]:
                    standard_level = level
                else:
                    naechstes_level = level
                    naechstes_gewicht = standards[level]
                    aktuelles_gewicht = standards[standard_level]
                    diff = naechstes_gewicht - aktuelles_gewicht
                    progress = beste_1rm - aktuelles_gewicht
                    prozent_bis_naechstes = round((progress / diff) * 100, 1) if diff > 0 else 0
                    break

        level_labels = {
            "untrainiert": "Untrainiert",
            "beginner": "Anfänger",
            "intermediate": "Fortgeschritten",
            "advanced": "Erfahren",
            "elite": "Elite",
        }

        if standard_level == "untrainiert":
            erreicht = []
        else:
            erreicht = [
                level_labels[lv] for lv in levels_order[: levels_order.index(standard_level) + 1]
            ]

        # Differenz zum nächsten Level berechnen (nicht absolutes Gewicht)
        if naechstes_level and naechstes_level in standards:
            diff_bis_naechstes = round(standards[naechstes_level] - beste_1rm, 1)
        else:
            diff_bis_naechstes = 0

        # Phase 24.6: "gerade erreicht" - Flag, wenn der User die untere Schwelle
        # des aktuellen Korridors gerade erst überschritten hat. Bei < 5 % Korridor-
        # Fortschritt liest sich die Prozent-Anzeige wie Stillstand (Mai-Beispiel:
        # Kniebeuge 73,3 kg knapp über Anfänger-Schwelle 73,2 kg → 0,4 %).
        # Das Template zeigt in diesem Fall einen positiven "Schwelle gerade
        # erreicht"-Text statt einer fast leeren Progress-Bar.
        gerade_erreicht = False
        if standard_level != "untrainiert" and naechstes_level and naechstes_level in standards:
            aktuelles_gewicht = standards[standard_level]
            naechstes_gewicht_val = standards[naechstes_level]
            korridor_diff = naechstes_gewicht_val - aktuelles_gewicht
            korridor_progress = beste_1rm - aktuelles_gewicht
            if korridor_diff > 0 and 0 <= korridor_progress / korridor_diff < 0.05:
                gerade_erreicht = True

        # Elite ist Endstufe – kein "nächstes Level"
        ist_endstufe = standard_level == "elite"

        standard_info = {
            "level": standard_level,
            "level_label": level_labels[standard_level],
            "naechstes_level": level_labels.get(naechstes_level, "Elite"),
            "naechstes_gewicht": diff_bis_naechstes,
            "prozent_bis_naechstes": prozent_bis_naechstes if naechstes_level else 100,
            "alle_levels": {level_labels[k]: v for k, v in standards.items()},
            "erreicht": erreicht,
            "gerade_erreicht": gerade_erreicht,
            "ist_endstufe": ist_endstufe,
        }

        # Muskelgruppe
        muskelgruppe_name = uebung.get("muskelgruppe_display", "")

        ergebnisse.append(
            {
                "uebung": uebung_name,
                "muskelgruppe": muskelgruppe_name,
                "geschaetzter_1rm": round(beste_1rm, 1),
                "1rm_entwicklung": entwicklung_liste,
                "standard_info": standard_info,
            }
        )

    return ergebnisse


def calculate_rpe_quality_analysis(alle_saetze):
    """
    Analyzes RPE distribution to detect junk volume and optimal intensity.

    Returns dict with:
    - optimal_intensity_rate: % of sets at RPE 7-9
    - junk_volume_rate: % of sets at RPE <6
    - failure_rate: % of sets at RPE 10
    - rpe_verteilung_prozent: Distribution across RPE ranges
    - bewertung: Overall training quality rating
    - empfehlungen: List of recommendations
    """
    # Aufwärmsätze explizit ausschließen: niedrige RPE ist beim Aufwärmen intentional,
    # nicht Junk Volume. Warmup-Sätze würden die Analyse systematisch verfälschen.
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, ist_aufwaermsatz=False)
    gesamt = rpe_saetze.count()

    if gesamt == 0:
        return None

    # Verteilung berechnen (Detail-Kategorien für Aufschlüsselung)
    rpe_sehr_leicht = rpe_saetze.filter(rpe__lt=5).count()  # RPE <5
    rpe_leicht = rpe_saetze.filter(rpe__gte=5, rpe__lt=7).count()  # RPE 5-6.9
    rpe_moderat = rpe_saetze.filter(rpe__gte=7, rpe__lte=8).count()  # RPE 7-8
    rpe_schwer = rpe_saetze.filter(rpe__gt=8, rpe__lte=9).count()  # RPE 8.1-9
    rpe_sehr_schwer = rpe_saetze.filter(rpe__gt=9, rpe__lt=10).count()  # RPE 9.1-9.9
    rpe_versagen = rpe_saetze.filter(rpe=10).count()  # RPE 10

    # Top-3 Metriken: Lückenlos (Summe = 100%)
    # Junk Volume: RPE < 7 (zu leicht für echten Muskelreiz)
    junk_count = rpe_saetze.filter(rpe__lt=7).count()
    # Optimal: RPE 7-9 (idealer Trainingsbereich)
    optimal_count = rpe_saetze.filter(rpe__gte=7, rpe__lt=10).count()
    # Versagen: RPE 10
    failure_count = rpe_versagen

    junk_volume_rate = round((junk_count / gesamt) * 100, 1)
    optimal_intensity_rate = round((optimal_count / gesamt) * 100, 1)
    failure_rate = round((failure_count / gesamt) * 100, 1)

    rpe_verteilung_prozent = {
        "sehr_leicht": round((rpe_sehr_leicht / gesamt) * 100, 1),
        "leicht": round((rpe_leicht / gesamt) * 100, 1),
        "moderat": round((rpe_moderat / gesamt) * 100, 1),
        "schwer": round((rpe_schwer / gesamt) * 100, 1),
        "sehr_schwer": round((rpe_sehr_schwer / gesamt) * 100, 1),
        "versagen": round((rpe_versagen / gesamt) * 100, 1),
    }

    # Empfehlungen generieren
    empfehlungen = []

    if junk_volume_rate > 20:
        empfehlungen.append(
            f'Zu viel "Junk Volume" ({junk_volume_rate}%) - Reduziere Aufwärmsätze oder erhöhe Intensität'
        )

    if optimal_intensity_rate < 50:
        empfehlungen.append(
            f"Zu wenig intensive Sätze ({optimal_intensity_rate}%) - Trainiere näher ans Versagen (RPE 7-9)"
        )

    if failure_rate > 10:
        empfehlungen.append(
            f"Zu oft bis zum Versagen ({failure_rate}%) - Risiko für Übertraining. Ziel: <5%"
        )

    if optimal_intensity_rate >= 60 and failure_rate <= 5 and junk_volume_rate <= 15:
        empfehlungen.append("Optimale Trainingsintensität! Weiter so.")

    # Bewertung
    if optimal_intensity_rate >= 70 and junk_volume_rate <= 10 and failure_rate <= 5:
        bewertung = "Exzellent"
        bewertung_farbe = "success"
    elif optimal_intensity_rate >= 60 and junk_volume_rate <= 20 and failure_rate <= 10:
        bewertung = "Gut"
        bewertung_farbe = "success"
    elif optimal_intensity_rate >= 40:
        bewertung = "Ausbaufähig"
        bewertung_farbe = "warning"
    else:
        bewertung = "Verbesserung nötig"
        bewertung_farbe = "danger"

    return {
        "optimal_intensity_rate": optimal_intensity_rate,
        "junk_volume_rate": junk_volume_rate,
        "failure_rate": failure_rate,
        "rpe_verteilung_prozent": rpe_verteilung_prozent,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
        "empfehlungen": empfehlungen,
        "gesamt_saetze": gesamt,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 23: Zeitfenster-basierte Trainingsanalysen
# ──────────────────────────────────────────────────────────────────────────────


def _normalize_date_pair(reference_date, plan_start):
    """Bring reference_date and plan_start to the same date/datetime kind.

    Caller-side ``reference_date`` may be ``datetime`` (PDF path) or ``date``
    (live-stats view). ``plan_start`` from :func:`get_active_plan_start_date`
    is a ``datetime``. We coerce ``plan_start`` to match ``reference_date``'s
    kind so comparisons in :func:`get_time_windows` work without TypeError.
    """
    if plan_start is None:
        return reference_date, plan_start
    ref_is_dt = isinstance(reference_date, datetime)
    ps_is_dt = isinstance(plan_start, datetime)
    if ref_is_dt and not ps_is_dt:
        # plan_start is date → expand to start-of-day datetime in current tz
        plan_start = datetime.combine(plan_start, datetime.min.time(), tzinfo=reference_date.tzinfo)
    elif not ref_is_dt and ps_is_dt:
        # plan_start is datetime → drop time component
        plan_start = plan_start.date()
    return reference_date, plan_start


def get_time_windows(reference_date=None, plan_start=None):
    """
    Liefert Standard-Zeitfenster für Phase-23-Analysen.

    Drei Fenster:
      - "2w": kurzfristig (14 Tage), aktueller Zustand
      - "4w": mittelfristig (28 Tage), primäre Steuerungsgröße
      - "all": all-time (Start = None), historischer Kontext

    Optional ``plan_start``: clamped Window-Starts auf ``max(start, plan_start)`` –
    so respektieren Auswertungen den aktiven Plan-Block (Phase-22-Konsistenz).
    "all" wird **nicht** geclamped – All-Time soll All-Time bleiben.

    ``reference_date`` und ``plan_start`` dürfen je ``date`` oder ``datetime``
    sein – beide werden intern auf denselben Typ normalisiert.

    Returns:
        dict[str, tuple[date|datetime|None, date|datetime]]:
            {"2w": (start, end), "4w": (start, end), "all": (None, end)}
    """
    if reference_date is None:
        reference_date = timezone.now()

    reference_date, plan_start = _normalize_date_pair(reference_date, plan_start)

    two_w_start = reference_date - timedelta(days=WINDOW_2W_DAYS)
    four_w_start = reference_date - timedelta(days=WINDOW_4W_DAYS)

    if plan_start is not None:
        if plan_start > two_w_start:
            two_w_start = plan_start
        if plan_start > four_w_start:
            four_w_start = plan_start

    return {
        "2w": (two_w_start, reference_date),
        "4w": (four_w_start, reference_date),
        "all": (None, reference_date),
    }


def _filter_saetze_by_window(alle_saetze, start, end):
    """Apply einheit__datum window filter to a Satz queryset.

    Bug-Fix nach Code-Review: ``Satz.einheit.datum`` ist DateTimeField. Wenn der
    Aufrufer ``end`` als ``date`` übergibt (Live-Stats-View nutzt
    ``timezone.now().date()``), interpretiert Django ``__lte=date`` als
    Mitternacht des Tages → heutige Sätze nach Mitternacht werden ausgeschlossen,
    User sieht sein gerade geloggtes Training nicht in den Karten.
    Lösung: bei date-Werten exklusiver Vergleich gegen den Folgetag.
    """
    if end is not None and not isinstance(end, datetime):
        # `end` ist ein date – inklusive bis Ende des Tages
        qs = alle_saetze.filter(einheit__datum__lt=end + timedelta(days=1))
    else:
        qs = alle_saetze.filter(einheit__datum__lte=end)
    if start is not None:
        qs = qs.filter(einheit__datum__gte=start)
    return qs


def _evaluate_rpe_failure_rate(failure_rate, primary_label):
    """
    Map failure_rate (RPE-10 percent) to (evaluation, recommendation).

    Schwellenwerte aus Phase 9.3 (unverändert in Phase 23):
        <5%   → "optimal"
        5-15% → "akzeptabel"
        >15%  → "risiko"
    """
    if failure_rate < 5:
        return (
            "optimal",
            f"{primary_label}: {failure_rate}% RPE-10 – innerhalb Ziel (<5 %).",
        )
    if failure_rate <= 15:
        return (
            "akzeptabel",
            f"{primary_label}: {failure_rate}% RPE-10 – im akzeptablen Bereich (<15 %).",
        )
    return (
        "risiko",
        f"{primary_label}: {failure_rate}% RPE-10 – Übertrainings-Risiko.",
    )


def calculate_rpe_quality_analysis_windowed(
    alle_saetze,
    reference_date=None,
    plan_start=None,
    min_sets=MIN_SETS_FOR_WINDOW,
):
    """
    RPE-Qualitätsanalyse für drei gestaffelte Zeitfenster (2w / 4w / all).

    Wrapper um :func:`calculate_rpe_quality_analysis` – pro Fenster ein Aufruf.
    Bewertung und Empfehlung leiten sich vom **4-Wochen-Wert** ab. Bei zu wenig
    Daten im 4-Wochen-Fenster fällt der primäre Window auf "all" zurück, der
    4w-Wert bleibt aber zur Anzeige erhalten (mit ``insufficient_data``-Flag).

    Das 2-Wochen-Fenster zeigt in der Karte "n.a." wenn unter ``min_sets``
    Sätze (Konzept 3.4), die rohen Werte in ``raw_results["2w"]`` bleiben aber
    erhalten – Divergenz-Check (``MIN_SETS_FOR_DIVERGENCE=10``) kann sie für
    den Trend-Hinweis weiter nutzen (Konzept 3.3).

    Args:
        alle_saetze: Satz-Queryset (User-vorgefiltert, sonst beliebig).
        reference_date: Stichtag (default: ``timezone.now()``).
        plan_start: Optionaler Plan-Startzeitpunkt (Phase 22) zum Clamping.
        min_sets: Schwelle, ab der ein Fenster valide auswertbar ist.

    Returns:
        dict mit:
            - ``windows``: {"2w": result|None, "4w": result|None, "all": result|None}
            - ``primary_window``: "4w" oder "all"
            - ``evaluation``: "optimal" | "akzeptabel" | "risiko" | None
            - ``recommendation``: Empfehlungstext mit Zeitraum-Zitat oder None
            - ``divergence_hint``: Hinweis bei Trend-Wechsel zwischen 2w/4w oder None
            - ``window_meta``: pro Fenster {"start", "end", "n_sets", "insufficient_data"}
            - ``insufficient_4w``: True wenn 4w unter min_sets
            - ``plan_clamped``: True wenn plan_start das 4w-Fenster verkürzt hat
        Returns ``None`` wenn in keinem Fenster RPE-Daten vorliegen.
    """
    if reference_date is None:
        reference_date = timezone.now()

    windows = get_time_windows(reference_date, plan_start=plan_start)
    raw_results = {}
    meta = {}

    for key, (start, end) in windows.items():
        qs = _filter_saetze_by_window(alle_saetze, start, end)
        result = calculate_rpe_quality_analysis(qs)
        n_sets = result["gesamt_saetze"] if result else 0
        raw_results[key] = result
        meta[key] = {
            "start": start,
            "end": end,
            "n_sets": n_sets,
            "insufficient_data": False,
        }

    # Wenn überhaupt keine RPE-Daten existieren: None zurückgeben.
    if all(r is None for r in raw_results.values()):
        return None

    # 2w mit zu wenig Daten → Card zeigt "n.a." (Konzept 3.4), Wert bleibt aber
    # in raw_results, damit der Divergenz-Check (MIN_SETS_FOR_DIVERGENCE=10)
    # ihn weiter nutzen kann (Konzept 3.3 fordert Trend-Hinweis ab 10 Sätzen).
    # Vorher wurde raw_results["2w"] zu früh auf None gesetzt → Trend-Hinweis
    # blieb für 10–29 Sätze stumm. Bug-Fix nach Code-Review.
    if raw_results["2w"] is not None and meta["2w"]["n_sets"] < min_sets:
        meta["2w"]["insufficient_data"] = True
        # raw_results["2w"] bleibt für Divergenz-Logik erhalten.

    # 4w mit zu wenig Daten → 4w-Werte bleiben zur Anzeige erhalten,
    # aber primary fällt auf "all" zurück (Konzept 3.4).
    insufficient_4w = raw_results["4w"] is None or meta["4w"]["n_sets"] < min_sets
    if insufficient_4w and raw_results["4w"] is not None:
        meta["4w"]["insufficient_data"] = True

    primary = "all" if insufficient_4w else "4w"
    primary_result = raw_results[primary]
    if primary_result is None:
        # Kann passieren, wenn 4w insufficient und all leer (theoretisch).
        primary_result = raw_results["4w"] or raw_results["2w"] or raw_results["all"]

    evaluation = None
    recommendation = None
    if primary_result is not None:
        primary_label = "Letzte 4 Wochen" if primary == "4w" else "Gesamt"
        evaluation, recommendation = _evaluate_rpe_failure_rate(
            primary_result["failure_rate"], primary_label
        )
        if insufficient_4w and primary == "all":
            recommendation = (
                f"Zu wenig Daten für 4-Wochen-Auswertung "
                f"(n={meta['4w']['n_sets']}/{min_sets}) – Bewertung basiert "
                f"auf Gesamtzeitraum: {primary_result['failure_rate']}% RPE-10."
            )

    # Trend-Hinweis: 2w-Wert weicht spürbar vom 4w-Wert ab.
    divergence_hint = None
    res_2w = raw_results["2w"]
    res_4w = raw_results["4w"]
    if (
        res_2w is not None
        and res_4w is not None
        and meta["2w"]["n_sets"] >= MIN_SETS_FOR_DIVERGENCE
        and abs(res_2w["failure_rate"] - res_4w["failure_rate"]) > DIVERGENCE_THRESHOLD_PCT
    ):
        if res_2w["failure_rate"] < res_4w["failure_rate"]:
            divergence_hint = (
                f"Trend verbessert sich (2 Wochen: {res_2w['failure_rate']}%, "
                f"4 Wochen: {res_4w['failure_rate']}%)."
            )
        else:
            divergence_hint = (
                f"Trend verschlechtert sich (2 Wochen: {res_2w['failure_rate']}%, "
                f"4 Wochen: {res_4w['failure_rate']}%)."
            )

    # plan_start clamped das 4w-Fenster, wenn es jünger ist als der Standard-Start.
    plan_clamped = False
    if plan_start is not None:
        _ref, _ps = _normalize_date_pair(reference_date, plan_start)
        plan_clamped = _ps > _ref - timedelta(days=WINDOW_4W_DAYS)

    # Vorberechnete Karten-Daten für Templates – vermeidet dict-key-access-Filter.
    # Bei 2w-insufficient_data wird das Result für die Anzeige unterdrückt
    # (Konzept 3.4: "n.a." anzeigen) – die rohen Werte in raw_results bleiben
    # für den Divergenz-Check intakt.
    window_label_map = {"2w": "2 Wochen", "4w": "4 Wochen", "all": "Gesamt"}
    cards = [
        {
            "key": key,
            "label": window_label_map[key],
            "is_primary": key == primary,
            "result": (
                None if (key == "2w" and meta[key]["insufficient_data"]) else raw_results[key]
            ),
            "n_sets": meta[key]["n_sets"],
            "insufficient_data": meta[key]["insufficient_data"],
        }
        for key in ("2w", "4w", "all")
    ]

    return {
        "windows": raw_results,
        "primary_window": primary,
        "primary_result": raw_results[primary],
        "evaluation": evaluation,
        "recommendation": recommendation,
        "divergence_hint": divergence_hint,
        "window_meta": meta,
        "insufficient_4w": insufficient_4w,
        "plan_clamped": plan_clamped,
        "cards": cards,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 23.2: Effektives Volumen + Diagnose-Tabelle
# ──────────────────────────────────────────────────────────────────────────────


def is_effective_volume_set(satz):
    """True wenn der Satz zum produktiven Volumen zählt (RPE 7–9, gewichtet)."""
    if satz.gewicht is None or not satz.wiederholungen or satz.rpe is None:
        return False
    rpe = float(satz.rpe)
    return EFFECTIVE_VOLUME_RPE_MIN <= rpe <= EFFECTIVE_VOLUME_RPE_MAX


def classify_volume_trend(prev_value, curr_value, stable_pct=VOLUME_TREND_STABLE_PCT):
    """Klassifiziert eine Wert-Veränderung als ``"sinkt" | "stabil" | "steigt"``.

    Default-Schwelle: 5 % Δ. Bei prev_value=0 oder None wird ``"unklar"`` zurückgegeben
    (kein Vergleich möglich).
    """
    if not prev_value or prev_value <= 0 or curr_value is None:
        return "unklar"
    delta_pct = (curr_value - prev_value) / prev_value * 100
    if abs(delta_pct) < stable_pct:
        return "stabil"
    return "steigt" if delta_pct > 0 else "sinkt"


# Diagnose-Tabelle aus Konzept 4.3 – als (tonnage_trend, eff_trend) → diag-key.
_VOLUME_DIAGNOSIS_MAP = {
    ("sinkt", "sinkt"): {
        "key": "regression",
        "label": "Echte Regression",
        "severity": "warning",
        "message": (
            "Tonnage und effektives Volumen sinken beide – echte Leistungs-Regression. "
            "Recovery, Schlaf und Ernährung prüfen."
        ),
    },
    ("sinkt", "stabil"): {
        "key": "intensity_correction",
        "label": "Intensitäts-Korrektur",
        "severity": "info",
        "message": (
            "Tonnage sinkt, effektives Volumen bleibt stabil – bewusste Intensitäts-Reduktion "
            "ohne Qualitätsverlust. Kein Anlass zur Sorge."
        ),
    },
    ("sinkt", "steigt"): {
        "key": "quality_improvement",
        "label": "Qualitäts-Verbesserung",
        "severity": "success",
        "message": (
            "Tonnage sinkt, effektives Volumen steigt – Junk-/Failure-Volumen wird "
            "abgebaut, produktives Volumen wächst. Sehr gute Entwicklung."
        ),
    },
    ("steigt", "sinkt"): {
        "key": "junk_increase",
        "label": "Mehr Junk-/Failure-Volumen",
        "severity": "warning",
        "message": (
            "Tonnage steigt, effektives Volumen sinkt – mehr unproduktive Sätze "
            "(zu leicht oder bis zum Versagen). Effizienz prüfen."
        ),
    },
    ("steigt", "steigt"): {
        "key": "growth",
        "label": "Volumen-Wachstum",
        "severity": "success",
        "message": "Tonnage und effektives Volumen steigen – produktive Aufbauphase.",
    },
    ("stabil", "stabil"): {
        "key": "stable",
        "label": "Stabile Phase",
        "severity": "info",
        "message": "Tonnage und effektives Volumen stabil – Phase der Konsolidierung.",
    },
}


def diagnose_volume_trend(
    prev_tonnage,
    curr_tonnage,
    prev_effective,
    curr_effective,
    is_deload_week=False,
):
    """Diagnostiziert die Wochenvolumen-Veränderung gemäß Konzept 4.3.

    Args:
        prev_tonnage, curr_tonnage: Tonnage-Werte zwei aufeinanderfolgender Wochen
        prev_effective, curr_effective: Effektives Volumen analog
        is_deload_week: Hybrid-Block-Typ-Awareness (Phase 23.2 / Frage 8.5).
            Wenn True und beide Trends "sinkt", wird die Regression-Diagnose
            durch eine "deload"-Diagnose ersetzt – kein Falsch-Positiv.

    Returns:
        dict mit ``key``, ``label``, ``severity``, ``message``,
        ``tonnage_trend``, ``effective_trend``, ``suppressed_due_to_deload``
        oder None wenn Vergleich nicht möglich.
    """
    tonnage_trend = classify_volume_trend(prev_tonnage, curr_tonnage)
    effective_trend = classify_volume_trend(prev_effective, curr_effective)

    if tonnage_trend == "unklar" or effective_trend == "unklar":
        return None

    suppressed = False
    if is_deload_week and tonnage_trend == "sinkt" and effective_trend == "sinkt":
        # Deload-Woche: bewusste Volumen-Reduktion, kein Regressions-Signal.
        suppressed = True
        diag = {
            "key": "deload_expected",
            "label": "Deload-Woche",
            "severity": "info",
            "message": (
                "Tonnage und effektives Volumen sinken – erwartetes Verhalten "
                "in einer Deload-Woche. Keine Regression."
            ),
        }
    else:
        diag = _VOLUME_DIAGNOSIS_MAP.get((tonnage_trend, effective_trend))
        if diag is None:
            # Kombinationen ohne expliziten Eintrag → neutral
            diag = {
                "key": "neutral",
                "label": "Keine eindeutige Diagnose",
                "severity": "secondary",
                "message": "",
            }

    return {
        **diag,
        "tonnage_trend": tonnage_trend,
        "effective_trend": effective_trend,
        "suppressed_due_to_deload": suppressed,
    }
