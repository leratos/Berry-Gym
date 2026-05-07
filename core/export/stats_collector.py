"""
PDF stats collection: all data-gathering helpers for the training PDF report.

Collects training statistics, muscle balance, push/pull ratio, strength
progression, intensity data, weekly volume, weight trends and more.
"""

from collections import defaultdict
from datetime import timedelta

from django.db import models
from django.db.models import Avg, Count, F, Max, Sum
from django.utils import timezone

from core.export.constants import EMPFOHLENE_SAETZE, PULL_GROUPS, PUSH_GROUPS
from core.helpers.volume import calc_volume, effective_weight, get_user_kg
from core.models import MUSKELGRUPPEN, KoerperWerte, Satz, Trainingseinheit
from core.utils.advanced_stats import (
    DELOAD_WEEK_MAJORITY_PCT,
    EFFECTIVE_VOLUME_RPE_MAX,
    EFFECTIVE_VOLUME_RPE_MIN,
    calculate_1rm_standards,
    calculate_consistency_metrics,
    calculate_fatigue_index,
    calculate_plateau_analysis,
    calculate_rpe_quality_analysis,
    calculate_rpe_quality_analysis_windowed,
    diagnose_volume_trend,
)
from core.utils.plan_helpers import (
    get_active_plan_exercise_ids,
    get_active_plan_start_date,
    is_active_plan_too_new,
)


def muscle_status(anzahl: int, min_s: int, max_s: int, wenig_daten: bool) -> tuple[str, str, str]:
    """Return (status_key, status_label, erklaerung) for one muscle group."""
    if anzahl == 0:
        expl = (
            f"Noch keine Sätze erfasst. Empfehlung: {min_s}-{max_s} Sätze/Monat"
            if wenig_daten
            else f"Diese Muskelgruppe wurde nicht trainiert. Empfehlung: {min_s}-{max_s} Sätze/Monat"
        )
        return "nicht_trainiert", "Nicht trainiert", expl
    if anzahl < min_s:
        if wenig_daten:
            return (
                "untertrainiert",
                "Wenig trainiert",
                f"{anzahl} Sätze in 30 Tagen. Empfehlung: {min_s}-{max_s} Sätze/Monat "
                "(mehr Daten für genauere Analyse)",
            )
        return (
            "untertrainiert",
            "Untertrainiert",
            f"Nur {anzahl} Sätze in 30 Tagen. Empfehlung: {min_s}-{max_s} Sätze für optimales Wachstum",
        )
    if anzahl > max_s:
        if wenig_daten:
            return (
                "uebertrainiert",
                "Viel trainiert",
                f"{anzahl} Sätze - intensiver Start! Beobachte Regeneration. "
                f"Empfehlung: {min_s}-{max_s} Sätze/Monat",
            )
        return (
            "uebertrainiert",
            "Mögl. Übertraining",
            f"{anzahl} Sätze könnten zu viel sein. Empfehlung: {min_s}-{max_s} Sätze. Regeneration prüfen!",
        )
    return "optimal", "Optimal", f"{anzahl} Sätze liegen im optimalen Bereich ({min_s}-{max_s})"


def collect_muscle_balance(
    alle_saetze, letzte_30_tage, trainings_30_tage: int, user_kg: float = 0.0
) -> list[dict]:
    """Build muscle group balance stats with evidence-based set recommendations."""
    wenig_daten = trainings_30_tage < 8
    result = []
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        gruppe_saetze = alle_saetze.filter(
            uebung__muskelgruppe=gruppe_key, einheit__datum__gte=letzte_30_tage
        ).select_related("uebung")
        anzahl = gruppe_saetze.count()
        min_s, max_s = EMPFOHLENE_SAETZE.get(gruppe_key, (12, 20))
        status, status_label, erklaerung = muscle_status(anzahl, min_s, max_s, wenig_daten)
        if anzahl > 0:
            volumen = calc_volume(gruppe_saetze, user_kg)
            avg_rpe_r = gruppe_saetze.aggregate(Avg("rpe"))["rpe__avg"]
            result.append(
                {
                    "key": gruppe_key,
                    "name": gruppe_name,
                    "saetze": anzahl,
                    "volumen": float(round(volumen, 0)),
                    "avg_rpe": float(round(avg_rpe_r, 1)) if avg_rpe_r else 0.0,
                    "status": status,
                    "status_label": status_label,
                    "erklaerung": erklaerung,
                    "empfehlung_min": min_s,
                    "empfehlung_max": max_s,
                    "prozent_von_optimal": float(round((anzahl / ((min_s + max_s) / 2)) * 100, 0)),
                }
            )
    return sorted(result, key=lambda x: x["saetze"], reverse=True)


def collect_push_pull(muskelgruppen_stats: list[dict]) -> dict:
    """Compute push/pull balance and return analysis dict."""
    push = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in PUSH_GROUPS)
    pull = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in PULL_GROUPS)
    if push == 0 and pull == 0:
        ratio, bewertung, empfehlung = (
            0,
            "Keine Daten",
            "Beginne mit ausgewogenem Push- und Pull-Training für optimale Muskelentwicklung.",
        )
    elif pull > 0:
        ratio = round(push / pull, 2)
        if 0.8 <= ratio <= 1.2:
            bewertung, empfehlung = "Ausgewogen", "Perfekt! Push/Pull-Verhältnis ist ausgeglichen."
        elif ratio > 2.0:
            # Erst ab 2:1 ist das Ungleichgewicht klinisch relevant (Schulterimpingement-Risiko)
            bewertung = "Zu viel Push"
            empfehlung = (
                f"Ratio {ratio}:1 - Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!"
            )
        elif ratio > 1.2:
            # 1.2–2.0: leichtes Push-Übergewicht, aber noch tolerabel
            bewertung = "Leicht Push-betont"
            empfehlung = (
                f"Ratio {ratio}:1 - Leicht Push-betont, aber noch im tolerierbaren Bereich. "
                "Mittelfristig mehr Pull-Übungen einbauen."
            )
        else:
            # ratio < 0.8: mehr Pull als Push – kein Problem, im Gegenteil empfohlen
            bewertung = "Pull-betont (gut)"
            empfehlung = f"Ratio {ratio}:1 - Pull überwiegt leicht. Das ist positiv für Schultergesundheit und Haltung."
    else:
        ratio, bewertung, empfehlung = (
            0,
            "Nur Push",
            "Füge Pull-Training (Rücken, Bizeps) hinzu für ausgeglichene Entwicklung!",
        )
    return {
        "push_saetze": push,
        "pull_saetze": pull,
        "ratio": ratio,
        "bewertung": bewertung,
        "empfehlung": empfehlung,
    }


def collect_strength_progression(
    alle_saetze,
    top_uebungen: list,
    muskelgruppen_dict: dict,
    *,
    plan_start_date=None,
    fallback_session_count: int | None = None,
) -> list[dict]:
    """Extract top-5 exercises with measurable strength progression.

    Phase 22: Vergleichsfenster richtet sich nach aktivem Plan:
    - `plan_start_date` gesetzt + `fallback_session_count=None`:
      Vergleich seit Plan-Start (Steigerung im aktuellen Plan).
    - `plan_start_date=None` + `fallback_session_count=N`:
      Vergleich über die letzten N absolvierten Sessions pro Übung
      (Fallback bei zu neuem Plan).
    - Beide None (Backwards-compat): erste 3 Sätze ever vs. letzte 3 Sätze ever.

    Im Ergebnis-Dict wird `mode_label` mitgegeben, damit das Template
    transparent kennzeichnen kann, welches Fenster die Steigerung beschreibt.
    """
    result = []
    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]
        uebung_saetze_qs = alle_saetze.filter(uebung__bezeichnung=uebung_name).order_by(
            "einheit__datum"
        )

        if plan_start_date is not None:
            relevante_saetze = uebung_saetze_qs.filter(einheit__datum__gte=plan_start_date)
            mode_label = "im aktuellen Plan"
        elif fallback_session_count is not None:
            session_dates = sorted(set(uebung_saetze_qs.values_list("einheit__datum", flat=True)))[
                -fallback_session_count:
            ]
            if not session_dates:
                continue
            relevante_saetze = uebung_saetze_qs.filter(einheit__datum__in=session_dates)
            mode_label = f"letzte {len(session_dates)} Sessions"
        else:
            # Backwards-compat: alle Sätze
            relevante_saetze = uebung_saetze_qs
            mode_label = "Gesamt"

        if relevante_saetze.count() < 3:
            continue
        erste_saetze = list(relevante_saetze[:3])
        letzte_saetze = list(relevante_saetze)[-3:]
        erstes_max = max((s.gewicht or 0) for s in erste_saetze)
        letztes_max = max((s.gewicht or 0) for s in letzte_saetze)
        if erstes_max > 0:
            progression_prozent = round(
                ((float(letztes_max) - float(erstes_max)) / float(erstes_max)) * 100, 1
            )
            result.append(
                {
                    "uebung": uebung_name,
                    "start_gewicht": float(erstes_max),
                    "aktuell_gewicht": float(letztes_max),
                    "progression": float(progression_prozent),
                    "muskelgruppe": muskelgruppen_dict.get(
                        uebung["uebung__muskelgruppe"], uebung["uebung__muskelgruppe"]
                    ),
                    "mode_label": mode_label,
                }
            )
    return sorted(result, key=lambda x: x["progression"], reverse=True)[:5]


def collect_intensity_data(alle_saetze, letzte_30_tage) -> tuple[float, dict]:
    """Return (avg_rpe, rpe_verteilung) for the last 30 days."""
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, einheit__datum__gte=letzte_30_tage)
    if not rpe_saetze.exists():
        return 0.0, {"leicht": 0, "mittel": 0, "schwer": 0}
    avg_rpe_val = rpe_saetze.aggregate(Avg("rpe"))["rpe__avg"]
    avg_rpe = float(round(avg_rpe_val, 1)) if avg_rpe_val else 0.0
    rpe_verteilung = {
        "leicht": int(rpe_saetze.filter(rpe__lte=6).count()),
        "mittel": int(rpe_saetze.filter(rpe__gt=6, rpe__lte=8).count()),
        "schwer": int(rpe_saetze.filter(rpe__gt=8).count()),
    }
    return avg_rpe, rpe_verteilung


def collect_weekly_volume_pdf(alle_saetze, alle_trainings=None, user_kg: float = 0.0) -> list[dict]:
    """Build weekly volume progression (last 12 weeks) for PDF report.

    Includes deload weeks with their actual (reduced) volume, marked via
    'ist_deload' flag.  Fills gaps between calendar weeks with 0.

    Phase 23.2: Zusätzliche zweite Reihe ``effektives_volumen`` – nur Sätze
    mit RPE 7–9 zählen (ohne Junk-Volume <7 und Failure-Volume =10). Pro
    Woche wird zudem ``ist_deload_majority`` gesetzt (≥50 % der Sessions
    in dieser Woche sind ``ist_deload=True``), als Hybrid-Block-Typ-Awareness
    für die Diagnose-Tabelle.
    """
    # Use ALL sets (incl. deload) for volume so deload weeks aren't 0
    saetze_qs = alle_saetze.filter(ist_aufwaermsatz=False).select_related("uebung")

    weekly_volume: dict[str, float] = defaultdict(float)
    weekly_effective: dict[str, float] = defaultdict(float)
    for satz in saetze_qs:
        if satz.gewicht is not None and satz.wiederholungen:
            iso_year, iso_week, _ = satz.einheit.datum.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            tonnage = effective_weight(satz, user_kg) * satz.wiederholungen
            weekly_volume[week_key] += tonnage
            if (
                satz.rpe is not None
                and EFFECTIVE_VOLUME_RPE_MIN <= float(satz.rpe) <= EFFECTIVE_VOLUME_RPE_MAX
            ):
                weekly_effective[week_key] += tonnage

    if not weekly_volume:
        return []

    # Identify deload weeks – Hybrid-Awareness: ≥50 % der Sessions ist_deload=True
    deload_weeks: set[str] = set()
    deload_majority_weeks: set[str] = set()
    if alle_trainings is not None:
        sessions_per_week: dict[str, dict] = defaultdict(lambda: {"total": 0, "deload": 0})
        for t in alle_trainings.all():
            iso_year, iso_week, _ = t.datum.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            sessions_per_week[key]["total"] += 1
            if t.ist_deload:
                sessions_per_week[key]["deload"] += 1
                deload_weeks.add(key)
        for key, counts in sessions_per_week.items():
            if (
                counts["total"]
                and (counts["deload"] / counts["total"]) * 100 >= DELOAD_WEEK_MAJORITY_PCT
            ):
                deload_majority_weeks.add(key)

    # Fill gaps between first and last week
    all_keys = sorted(weekly_volume.keys())
    first_key, last_key = all_keys[0], all_keys[-1]
    first_year, first_week = int(first_key.split("-W")[0]), int(first_key.split("-W")[1])
    last_year, last_week = int(last_key.split("-W")[0]), int(last_key.split("-W")[1])

    filled: list[str] = []
    y, w = first_year, first_week
    while (y, w) <= (last_year, last_week):
        key = f"{y}-W{w:02d}"
        filled.append(key)
        # Advance to next ISO week
        w += 1
        # ISO weeks: most years have 52, some have 53
        from datetime import date

        max_week = date(y, 12, 28).isocalendar()[1]
        if w > max_week:
            w = 1
            y += 1

    labels = filled[-12:]
    weeks = [
        {
            "woche": f"KW{label.split('-W')[1]}",
            "volumen": round(weekly_volume.get(label, 0), 0),
            "effektives_volumen": round(weekly_effective.get(label, 0), 0),
            "ist_deload": label in deload_weeks,
            "ist_deload_majority": label in deload_majority_weeks,
        }
        for label in labels
    ]

    # Phase 23.2: Diagnose der letzten Woche (Trend gegenüber Vorwoche)
    if len(weeks) >= 2:
        prev = weeks[-2]
        curr = weeks[-1]
        diag = diagnose_volume_trend(
            prev_tonnage=prev["volumen"],
            curr_tonnage=curr["volumen"],
            prev_effective=prev["effektives_volumen"],
            curr_effective=curr["effektives_volumen"],
            is_deload_week=curr["ist_deload_majority"],
        )
        curr["diagnose"] = diag
    return weeks


def collect_weight_trend(koerperwerte: list) -> dict | None:
    """Return weight trend dict (diff + direction) or None if insufficient data."""
    if len(koerperwerte) < 2:
        return None
    gewichts_diff = koerperwerte[0].gewicht - koerperwerte[-1].gewicht
    return {
        "diff": round(gewichts_diff, 1),
        "richtung": "zugenommen" if gewichts_diff > 0 else "abgenommen",
    }


def calc_trainings_per_week(alle_trainings, heute) -> float:
    """Calculate average training frequency per week from all sessions."""
    gesamt = alle_trainings.count()
    if gesamt == 0:
        return 0.0
    erste = alle_trainings.order_by("datum").first()
    if not erste:
        return 0.0
    tage_aktiv = max(1, (heute - erste.datum).days)
    return round((gesamt / tage_aktiv) * 7, 1)


def build_top_uebungen(
    alle_saetze,
    muskelgruppen_dict: dict,
    active_uebung_ids: set[int] | None = None,
) -> list[dict]:
    """Query top 10 exercises by set count, annotated with display name.

    Phase 22: Optional auf Übungen des aktiven Plans filtern. Bei
    `active_uebung_ids=None` bleibt das alte Verhalten (alle Übungen).
    """
    qs = alle_saetze
    if active_uebung_ids is not None:
        qs = qs.filter(uebung_id__in=active_uebung_ids)

    raw = (
        qs.values("uebung__bezeichnung", "uebung__muskelgruppe")
        .annotate(
            anzahl=Count("id"),
            max_gewicht=Max("gewicht"),
            avg_gewicht=Avg("gewicht"),
            total_volumen=Sum(F("gewicht") * F("wiederholungen"), output_field=models.FloatField()),
        )
        .order_by("-anzahl")[:10]
    )
    result = []
    for uebung in raw:
        uebung_dict = dict(uebung)
        uebung_dict["muskelgruppe_display"] = muskelgruppen_dict.get(
            uebung["uebung__muskelgruppe"], uebung["uebung__muskelgruppe"]
        )
        result.append(uebung_dict)
    return result


def sum_volume(saetze_qs, user_kg: float = 0.0) -> float:
    """Summiert Volumen (effektives Gewicht × Wdh) aus einem Satz-QuerySet."""
    return calc_volume(saetze_qs.select_related("uebung"), user_kg)


def calc_volume_trend_weekly(volumen_wochen: list[dict], heute=None) -> dict | None:
    """Vergleicht Trainingsvolumen der letzten beiden **abgeschlossenen** Wochen.

    Eine laufende (noch nicht beendete) Woche wird bewusst ignoriert, da ein
    Vergleich von z.B. 2 Trainingstagen (aktuell) mit 4 Trainingstagen
    (Vorwoche) irreführende Ergebnisse liefern würde.

    Args:
        volumen_wochen: Liste von dicts mit 'woche' (z.B. 'KW10') und 'volumen'.
        heute: datetime-Objekt für die Bestimmung der aktuellen KW (default: now).

    Returns:
        dict mit diese_woche, letzte_woche, veraenderung_prozent, trend
        oder None wenn zu wenig abgeschlossene Daten vorliegen.
    """
    if len(volumen_wochen) < 2:
        return None

    if heute is None:
        heute = timezone.now()

    aktuelle_kw = f"KW{heute.isocalendar()[1]:02d}"

    # Laufende Woche aus dem Vergleich ausschließen
    kandidaten = [w for w in volumen_wochen if w["woche"] != aktuelle_kw]
    if len(kandidaten) < 2:
        return None

    letzte = float(kandidaten[-1]["volumen"])
    vorletzte = float(kandidaten[-2]["volumen"])
    if vorletzte == 0:
        return None
    veraenderung = round(((letzte - vorletzte) / vorletzte) * 100, 1)
    trend = "steigt" if veraenderung > 3 else ("fällt" if veraenderung < -3 else "stabil")
    return {
        "diese_woche": letzte,
        "letzte_woche": vorletzte,
        "veraenderung_prozent": veraenderung,
        "trend": trend,
    }


def calc_vormonats_delta(aktuell, vormonat) -> dict:
    """Berechnet Deltas zwischen aktuellem und Vormonats-Körperwert."""

    def _delta(akt_val, vor_val):
        if akt_val is not None and vor_val is not None:
            diff = float(akt_val) - float(vor_val)
            return round(diff, 1) if diff != 0.0 else None
        return None

    return {
        "datum": vormonat.datum,
        "gewicht": _delta(aktuell.gewicht, vormonat.gewicht),
        "kfa": _delta(aktuell.koerperfett_prozent, vormonat.koerperfett_prozent),
        "muskelmasse_kg": _delta(aktuell.muskelmasse_kg, vormonat.muskelmasse_kg),
        "muskelmasse_pct": _delta(aktuell.muskelmasse_prozent, vormonat.muskelmasse_prozent),
        "koerperwasser_pct": _delta(aktuell.koerperwasser_prozent, vormonat.koerperwasser_prozent),
    }


def collect_training_heatmap_data(alle_trainings, alle_saetze) -> list[dict]:
    """Collect per-day training dates with intensity for the heatmap chart.

    Intensity is derived from average RPE of the session (normalized to 0-1).
    Sessions without RPE data get intensity 0.5 (moderate).
    """
    from django.db.models import Avg

    result = []
    for training in alle_trainings.order_by("datum"):
        session_saetze = alle_saetze.filter(einheit=training)
        avg_rpe = session_saetze.filter(rpe__isnull=False).aggregate(Avg("rpe"))["rpe__avg"]
        if avg_rpe:
            intensitaet = min(float(avg_rpe) / 10.0, 1.0)
        else:
            intensitaet = 0.5
        result.append({"datum": training.datum.date(), "intensitaet": intensitaet})
    return result


def collect_exercise_detail_data(alle_saetze, top_uebungen: list) -> list[dict]:
    """Collect per-session weight progression for top 5 exercises.

    Returns list of dicts with 'uebung', 'muskelgruppe', and 'verlauf' (list of
    date/max_weight entries).
    """
    result = []
    for uebung_info in top_uebungen[:5]:
        uebung_name = uebung_info["uebung__bezeichnung"]
        mg_display = uebung_info.get("muskelgruppe_display", "")

        # Get all sessions for this exercise, grouped by date
        saetze = (
            alle_saetze.filter(uebung__bezeichnung=uebung_name)
            .values("einheit__datum")
            .annotate(max_gewicht=Max("gewicht"))
            .order_by("einheit__datum")
        )

        verlauf = []
        for entry in saetze:
            if entry["max_gewicht"] and float(entry["max_gewicht"]) > 0:
                verlauf.append(
                    {
                        "datum": entry["einheit__datum"].strftime("%d.%m.%y"),
                        "max_gewicht": float(entry["max_gewicht"]),
                    }
                )

        if len(verlauf) >= 2:
            result.append(
                {
                    "uebung": uebung_name,
                    "muskelgruppe": mg_display,
                    "verlauf": verlauf,
                }
            )
    return result


def collect_pdf_stats(user, letzte_30_tage, heute) -> dict:
    """Sammelt alle Statistiken für den PDF-Report.

    Returns dict mit allen Daten für den Template-Kontext.
    """
    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    trainings = Trainingseinheit.objects.filter(user=user, datum__gte=letzte_30_tage).order_by(
        "-datum"
    )[:20]

    alle_trainings = Trainingseinheit.objects.filter(user=user)
    gesamt_trainings = alle_trainings.count()
    trainings_30_tage = alle_trainings.filter(datum__gte=letzte_30_tage).count()

    alle_saetze = Satz.objects.filter(
        einheit__user=user,
        ist_aufwaermsatz=False,
        einheit__ist_deload=False,
    )
    gesamt_saetze = alle_saetze.count()
    saetze_30_tage = alle_saetze.filter(einheit__datum__gte=letzte_30_tage).count()

    user_kg = get_user_kg(user)
    gesamt_volumen = sum_volume(alle_saetze, user_kg)
    volumen_30_tage = sum_volume(alle_saetze.filter(einheit__datum__gte=letzte_30_tage), user_kg)

    trainings_pro_woche = calc_trainings_per_week(alle_trainings, heute)
    consistency_metrics = calculate_consistency_metrics(alle_trainings)

    # Phase 22: Aktiver-Plan-Filter für übungsbezogene Statistiken
    active_uebung_ids = get_active_plan_exercise_ids(user)
    plan_start_date = get_active_plan_start_date(user)
    plan_too_new = is_active_plan_too_new(user)

    top_uebungen = build_top_uebungen(alle_saetze, muskelgruppen_dict, active_uebung_ids)
    plateau_analysis = calculate_plateau_analysis(alle_saetze, top_uebungen)

    # Kraftentwicklung: seit Plan-Start (Default), oder letzte 5 Sessions (Fallback)
    if active_uebung_ids is not None and not plan_too_new:
        kraft_progression = collect_strength_progression(
            alle_saetze,
            top_uebungen,
            muskelgruppen_dict,
            plan_start_date=plan_start_date,
        )
    elif active_uebung_ids is not None and plan_too_new:
        kraft_progression = collect_strength_progression(
            alle_saetze,
            top_uebungen,
            muskelgruppen_dict,
            fallback_session_count=5,
        )
    else:
        # Kein Plan verknüpft → altes Verhalten
        kraft_progression = collect_strength_progression(
            alle_saetze, top_uebungen, muskelgruppen_dict
        )
    muskelgruppen_stats = collect_muscle_balance(
        alle_saetze, letzte_30_tage, trainings_30_tage, user_kg
    )
    push_pull_balance = collect_push_pull(muskelgruppen_stats)

    schwachstellen_status = {"untertrainiert", "nicht_trainiert"}
    schwachstellen = sorted(
        [mg for mg in muskelgruppen_stats if mg["status"] in schwachstellen_status],
        key=lambda x: x["saetze"],
    )[:5]
    staerken = [mg for mg in muskelgruppen_stats if mg["status"] == "optimal"]

    avg_rpe, rpe_verteilung = collect_intensity_data(alle_saetze, letzte_30_tage)
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, einheit__datum__gte=letzte_30_tage)
    rpe_quality = calculate_rpe_quality_analysis(alle_saetze)
    # Phase 23.1: Zeitfenster-basierte RPE-Verteilung (2w / 4w / all).
    # Plan-Clamping nur, wenn Plan nicht zu jung – konsistent mit Phase 22.
    rpe_window_plan_start = (
        plan_start_date if (active_uebung_ids is not None and not plan_too_new) else None
    )
    rpe_quality_windowed = calculate_rpe_quality_analysis_windowed(
        alle_saetze, reference_date=heute, plan_start=rpe_window_plan_start
    )
    # Volume chart uses ALL sets (incl. deload) so deload weeks show real volume
    alle_saetze_inkl_deload = Satz.objects.filter(
        einheit__user=user,
        ist_aufwaermsatz=False,
    )
    volumen_wochen = collect_weekly_volume_pdf(alle_saetze_inkl_deload, alle_trainings, user_kg)
    fatigue_analysis = calculate_fatigue_index(volumen_wochen, rpe_saetze, alle_trainings)

    koerperwerte_qs = KoerperWerte.objects.filter(user=user).order_by("-datum")
    koerperwerte = list(koerperwerte_qs[:10])  # letzte 10 für Verlaufstabelle im PDF
    # Alle Einträge (chronologisch) für den Trend-Chart
    koerperwerte_chart = list(koerperwerte_qs.order_by("datum"))
    letzter_koerperwert = koerperwerte[0] if koerperwerte else None
    user_gewicht = letzter_koerperwert.gewicht if letzter_koerperwert else None

    # Vormonats-Delta für Executive Summary
    vormonats_delta = None
    if letzter_koerperwert:
        vormonat_grenze = heute - timedelta(days=25)
        vormonat_kw = koerperwerte_qs.filter(datum__lte=vormonat_grenze.date()).first()
        if vormonat_kw:
            vormonats_delta = calc_vormonats_delta(letzter_koerperwert, vormonat_kw)
    gewichts_rate = (
        letzter_koerperwert.gewichts_veraenderung_rate() if letzter_koerperwert else None
    )
    rm_standards = calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht)
    gewichts_trend = collect_weight_trend(koerperwerte)

    # Phase D: Heatmap + Übungsdetail-Daten
    training_heatmap_data = collect_training_heatmap_data(alle_trainings, alle_saetze)
    exercise_detail_data = collect_exercise_detail_data(alle_saetze, top_uebungen)

    push_saetze = int(push_pull_balance.get("push_saetze", 0))
    pull_saetze = int(push_pull_balance.get("pull_saetze", 0))

    return {
        "start_datum": letzte_30_tage,
        "end_datum": heute,
        "current_date": heute,
        "trainings": trainings,
        "gesamt_trainings": gesamt_trainings,
        "gesamt_saetze": gesamt_saetze,
        "gesamt_volumen": round(gesamt_volumen, 0),
        "trainings_30_tage": trainings_30_tage,
        "saetze_30_tage": saetze_30_tage,
        "volumen_30_tage": round(volumen_30_tage, 0),
        "trainings_pro_woche": trainings_pro_woche,
        "top_uebungen": top_uebungen,
        "kraft_progression": kraft_progression,
        "kraftentwicklung": kraft_progression,
        "muskelgruppen_stats": muskelgruppen_stats,
        "push_pull_balance": push_pull_balance,
        "push_saetze": push_saetze,
        "pull_saetze": pull_saetze,
        "push_pull_ratio": float(push_pull_balance.get("ratio", 0)),
        "push_pull_bewertung": str(push_pull_balance.get("bewertung", "")),
        "push_pull_empfehlung": str(push_pull_balance.get("empfehlung", "")),
        "schwachstellen": schwachstellen,
        "staerken": staerken,
        "total_einheiten": gesamt_trainings,
        "total_saetze": gesamt_saetze,
        "total_volumen": round(gesamt_volumen, 0),
        "avg_rpe": avg_rpe,
        "rpe_verteilung": rpe_verteilung,
        "volumen_wochen": volumen_wochen[-8:],
        "koerperwerte": koerperwerte,
        "any_viszeral": any(kw.viszeralfett for kw in koerperwerte),
        "koerperwerte_chart": koerperwerte_chart,
        "letzter_koerperwert": letzter_koerperwert,
        "gewichts_rate": gewichts_rate,
        "gewichts_trend": gewichts_trend,
        "vormonats_delta": vormonats_delta,
        "plateau_analysis": plateau_analysis,
        "consistency_metrics": consistency_metrics,
        "fatigue_analysis": fatigue_analysis,
        "rm_standards": rm_standards,
        "rpe_quality": rpe_quality,
        "rpe_quality_windowed": rpe_quality_windowed,
        "training_heatmap_data": training_heatmap_data,
        "exercise_detail_data": exercise_detail_data,
    }
