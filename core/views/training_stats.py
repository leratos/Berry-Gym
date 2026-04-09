"""
Training Analytics and Statistics Module

This module handles training analytics, statistics, and the main dashboard view.
It provides comprehensive performance analysis, progress tracking, and workout history management.

Functions:
- dashboard: Main dashboard with performance metrics and analytics
- training_list: List of all past training sessions
- delete_training: Remove a training session from history
- training_stats: Detailed training statistics with volume progression
- exercise_stats: Performance analysis for individual exercises
"""

import json
import logging
import os
import random
from collections import defaultdict
from datetime import datetime as _dt
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..helpers.volume import calc_volume, get_user_kg
from ..models import (
    MUSKELGRUPPEN,
    CardioEinheit,
    KoerperWerte,
    Plan,
    Satz,
    Trainingsblock,
    Trainingseinheit,
    Uebung,
    UserProfile,
)
from ..utils.periodization import get_block_age_warning
from .body_tracking import _prepare_body_chart_data

logger = logging.getLogger(__name__)

# TTL für gecachte Dashboard-Berechnungen (pro User)
# Wird invalidiert wenn der User ein neues Training speichert (signals.py)
DASHBOARD_CACHE_TTL = 300  # 5 Minuten


# ---------------------------------------------------------------------------
# Private helpers for dashboard view
# ---------------------------------------------------------------------------


def _get_week_start(heute):
    """Return the Monday midnight of the week containing 'heute'."""
    iso_weekday = heute.isoweekday()
    ws = heute - timedelta(days=iso_weekday - 1)
    return ws.replace(hour=0, minute=0, second=0, microsecond=0)


def _get_active_trainingsblock(user):
    """Gibt den aktuell aktiven Trainingsblock (end_datum=None) zurück oder None."""
    return (
        Trainingsblock.objects.filter(user=user, end_datum__isnull=True)
        .order_by("-start_datum")
        .first()
    )


def _count_trainings_this_week(user, heute) -> int:
    """Count training sessions in the current ISO week (Mon–Sun)."""
    start_woche = _get_week_start(heute)
    return Trainingseinheit.objects.filter(user=user, datum__gte=start_woche).count()


def _get_week_overview(user, heute) -> list[dict]:
    """Gibt Mo–So der aktuellen Woche zurück mit Training-Status.

    Jeder Eintrag:
      date        (date)  – Datum des Tages
      label       (str)   – "Mo", "Di", …
      is_today    (bool)
      is_future   (bool)
      training_id (int|None) – ID des ersten abgeschlossenen Trainings (für Link)
      has_training (bool)
    """
    LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    woche_start = _get_week_start(heute).date()
    heute_date = heute.date()

    # Alle Trainings dieser Woche auf einmal laden
    trainings = (
        Trainingseinheit.objects.filter(
            user=user,
            datum__date__gte=woche_start,
            datum__date__lte=woche_start + timedelta(days=6),
            abgeschlossen=True,
        )
        .order_by("datum")
        .values("id", "datum")
    )

    # Datum → training_id mapping (erstes Training des Tages)
    training_map: dict = {}
    for t in trainings:
        d = t["datum"].date()
        if d not in training_map:
            training_map[d] = t["id"]

    result = []
    for i in range(7):
        day = woche_start + timedelta(days=i)
        result.append(
            {
                "date": day,
                "label": LABELS[i],
                "is_today": day == heute_date,
                "is_future": day > heute_date,
                "has_training": day in training_map,
                "training_id": training_map.get(day),
            }
        )
    return result


def _calculate_streak(user, heute) -> int:
    """Count consecutive weeks with at least one training session."""
    streak = 0
    check_date = heute
    while streak <= 52:
        week_start = _get_week_start(check_date)
        week_end = week_start + timedelta(days=7)
        if not Trainingseinheit.objects.filter(
            user=user, datum__gte=week_start, datum__lt=week_end
        ).exists():
            break
        streak += 1
        check_date = week_start - timedelta(days=1)
    return streak


def _get_favoriten(user):
    """Return top-3 most-trained exercises (excluding warmup/deload sets)."""
    return (
        Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False, einheit__ist_deload=False)
        .values("uebung__bezeichnung", "uebung__id")
        .annotate(anzahl=Count("id"))
        .order_by("-anzahl")[:3]
    )


def _get_rpe_score(user, heute) -> tuple[int, float | None]:
    """Compute RPE form score (0-25) and raw avg_rpe for the last 2 weeks."""
    two_weeks_ago = heute - timedelta(days=14)
    recent_saetze = Satz.objects.filter(
        einheit__datum__gte=two_weeks_ago,
        einheit__user=user,
        ist_aufwaermsatz=False,
        einheit__ist_deload=False,
        rpe__isnull=False,
    )
    if not recent_saetze.exists():
        return 0, None
    avg_rpe = recent_saetze.aggregate(Avg("rpe"))["rpe__avg"]
    if not avg_rpe:
        return 0, None
    if 7 <= avg_rpe <= 8:
        return 25, avg_rpe
    if 6 <= avg_rpe <= 9:
        return 20, avg_rpe
    if 5 <= avg_rpe <= 9.5:
        return 15, avg_rpe
    return 10, avg_rpe


def _get_volume_trend_score(user, heute) -> int:
    """Compute volume-trend form score (0-20) based on last 4 weeks."""
    user_kg = get_user_kg(user)
    last_4_weeks = []
    for i in range(4):
        week_start = heute - timedelta(days=heute.isoweekday() - 1 + (i * 7))
        week_end = week_start + timedelta(days=7)
        saetze = Satz.objects.filter(
            einheit__datum__gte=week_start,
            einheit__datum__lt=week_end,
            ist_aufwaermsatz=False,
            einheit__user=user,
            einheit__ist_deload=False,
        ).select_related("uebung")
        vol = calc_volume(saetze, user_kg)
        if vol:
            last_4_weeks.append(vol)
    if len(last_4_weeks) < 2:
        return 0
    if last_4_weeks[0] >= last_4_weeks[1]:
        return 20
    if last_4_weeks[0] >= last_4_weeks[1] * 0.8:
        return 15
    return 10


def _calculate_form_index(
    user, heute, trainings_diese_woche: int, streak: int, gesamt_trainings: int
) -> tuple[int, str, str, list]:
    """Return (form_index, form_rating, form_color, form_factors)."""
    if gesamt_trainings < 4:
        return 0, "Nicht verfügbar", "secondary", []

    freq_score = min(trainings_diese_woche * 7.5, 30)
    streak_score = min(streak * 2.5, 25)
    rpe_score, _ = _get_rpe_score(user, heute)
    volume_score = _get_volume_trend_score(user, heute)

    form_factors = [
        ("Trainingsfrequenz", round(freq_score, 1)),
        ("Konsistenz", round(streak_score, 1)),
        ("Volumen-Trend", volume_score),
    ]
    if rpe_score:
        form_factors.insert(2, ("Trainingsintensität (RPE)", rpe_score))

    form_index = round(freq_score + streak_score + rpe_score + volume_score)

    if form_index >= 80:
        return form_index, "Ausgezeichnet", "success", form_factors
    if form_index >= 60:
        return form_index, "Gut", "info", form_factors
    if form_index >= 40:
        return form_index, "Solide", "warning", form_factors
    return form_index, "Ausbaufähig", "danger", form_factors


def _calculate_weekly_volumes(user, heute, active_block=None) -> list[dict]:
    """Return volume data for the last 4 weeks.

    Ergänzt jede Woche um:
    - ``avg_1rm``: Durchschnittliches geschätztes 1RM (Epley) aller Arbeitssätze
      → ermöglicht Intensitäts-Vergleich über Phasengrenzen hinweg
    - ``before_block``: True wenn diese Woche vor dem aktuellen Block-Start liegt
      → Volumen-Warnungen werden für solche Wochen deaktiviert
    """
    block_start_date = active_block.start_datum if active_block else None

    weekly_volumes = []
    for i in range(4):
        week_start = _get_week_start(heute - timedelta(days=i * 7))
        week_end = week_start + timedelta(days=7)
        week_saetze = list(
            Satz.objects.filter(
                einheit__user=user,
                einheit__datum__gte=week_start,
                einheit__datum__lt=week_end,
                ist_aufwaermsatz=False,
                einheit__ist_deload=False,
            ).only("gewicht", "wiederholungen")
        )

        # Volumen (Tonnage): Gewicht × Wdh
        week_total = sum(
            float(s.gewicht) * int(s.wiederholungen)
            for s in week_saetze
            if s.gewicht and s.wiederholungen
        )
        saetze_count = len(week_saetze)

        # Durchschnittliches 1RM nach Epley-Formel: w × (1 + reps/30)
        # Ermöglicht Vergleich zwischen Definitions- und Massephasen
        est_1rms = [
            float(s.gewicht) * (1 + int(s.wiederholungen) / 30)
            for s in week_saetze
            if s.gewicht and s.wiederholungen and int(s.wiederholungen) > 0
        ]
        avg_1rm = round(sum(est_1rms) / len(est_1rms), 1) if est_1rms else 0

        # Prüfen ob es in dieser Woche Deload-Trainings gab
        hat_deload = Trainingseinheit.objects.filter(
            user=user,
            datum__gte=week_start,
            datum__lt=week_end,
            ist_deload=True,
        ).exists()

        # Liegt diese Woche vor dem aktuellen Block-Start?
        before_block = bool(block_start_date and week_start.date() < block_start_date)

        labels = {0: "Diese Woche", 1: "Letzte Woche"}
        week_label = labels.get(i, f"Vor {i} Wochen")
        weekly_volumes.append(
            {
                "label": week_label,
                "volume": round(week_total, 0),
                "saetze": saetze_count,
                "avg_1rm": avg_1rm,
                "week_num": i,
                "ist_deload": hat_deload,
                "before_block": before_block,
            }
        )
    return weekly_volumes


def _get_volume_spike_fatigue(
    weekly_volumes: list[dict], block_age_weeks: int | None = None
) -> tuple[int, list[str]]:
    """Return (points, warnings) for a volume spike in the last 2 weeks.

    Wenn ein neuer Trainingsblock kürzer als 3 Wochen alt ist, werden
    Volumen-Warnungen unterdrückt – ein Phasenwechsel verändert das
    Volumen natürlicherweise, ohne dass Ermüdung dahintersteckt.
    """
    # Erste 3 Wochen eines neuen Blocks: keine Volumen-Warnungen
    if block_age_weeks is not None and block_age_weeks < 3:
        return 0, []

    if len(weekly_volumes) < 2:
        return 0, []

    # Woche vor aktuellem Block nicht für Vergleiche nutzen
    current_vol = weekly_volumes[0]["volume"]
    last_week = weekly_volumes[1]
    if last_week.get("before_block"):
        return 0, []
    last_vol = last_week["volume"]
    if last_vol <= 0:
        return 0, []
    vol_change = ((current_vol - last_vol) / last_vol) * 100
    if vol_change > 30:
        return 40, ["Sehr starker Volumen-Anstieg"]
    if vol_change > 20:
        return 30, ["Starker Volumen-Anstieg"]
    if vol_change > 10:
        return 15, []
    return 0, []


def _get_rpe_fatigue(user, heute) -> tuple[int, list[str]]:
    """Return (points, warnings) based on RPE-10 distribution and avg RPE.

    Primary factor: RPE-10 percentage (via _get_rpe10_anteil).
    Secondary factor: average RPE (kept for cases where RPE-10 is low but
    overall intensity is high).  Result = max(primary, secondary).
    """
    warnings: list[str] = []

    # Primary: RPE-10 distribution
    anteil = _get_rpe10_anteil(user, heute)
    if anteil is not None and anteil > 20:
        primary = 50
        warnings.append(f"Sehr hoher RPE-10-Anteil ({anteil}%)")
    elif anteil is not None and anteil > 15:
        primary = 30
        warnings.append(f"Hoher RPE-10-Anteil ({anteil}%)")
    elif anteil is not None and anteil > 5:
        primary = 10
    else:
        primary = 0

    # Secondary: average RPE
    _, avg_rpe = _get_rpe_score(user, heute)
    if avg_rpe and avg_rpe > 8.5:
        secondary = 30
        warnings.append("Sehr hohe Trainingsintensität")
    elif avg_rpe and avg_rpe > 8:
        secondary = 20
        warnings.append("Hohe Trainingsintensität")
    else:
        secondary = 0

    return max(primary, secondary), warnings


def _get_frequency_fatigue(user, heute) -> tuple[int, list[str]]:
    """Return (points, warnings) based on training frequency in the last 7 days."""
    count = Trainingseinheit.objects.filter(user=user, datum__gte=heute - timedelta(days=7)).count()
    if count >= 6:
        return 30, ["Sehr hohe Trainingsfrequenz"]
    if count >= 5:
        return 15, []
    return 0, []


def _get_cardio_fatigue(user, heute) -> tuple[int, list[str], int, int]:
    """Return (points, warnings, session_count, total_minutes) from cardio last 7 days."""
    sessions = CardioEinheit.objects.filter(user=user, datum__gte=heute - timedelta(days=7))
    total = sum(c.ermuedungs_punkte for c in sessions)
    if total >= 120:
        return (
            20,
            [f"Hohes Cardio-Volumen ({total:.0f} Punkte)"],
            sessions.count(),
            sum(c.dauer_minuten for c in sessions),
        )
    if total >= 60:
        return (
            10,
            [f"Moderates Cardio-Volumen ({total:.0f} Punkte)"],
            sessions.count(),
            sum(c.dauer_minuten for c in sessions),
        )
    if total >= 30:
        return 5, [], sessions.count(), sum(c.dauer_minuten for c in sessions)
    return 0, [], sessions.count(), sum(c.dauer_minuten for c in sessions)


def _get_fatigue_rating(fatigue_index: int) -> tuple[str, str, str]:
    """Return (rating, color, message) for a given fatigue index."""
    if fatigue_index >= 60:
        return "Hoch", "danger", "Deload-Woche empfohlen! Reduziere Volumen um 40-50%."
    if fatigue_index >= 40:
        return "Moderat", "warning", "Achte auf ausreichend Regeneration."
    if fatigue_index >= 20:
        return "Niedrig", "info", "Gute Balance zwischen Training und Erholung."
    return "Sehr niedrig", "success", "Du kannst noch mehr trainieren!"


def _calculate_fatigue_index(
    user,
    heute,
    weekly_volumes: list[dict],
    gesamt_trainings: int,
    block_age_weeks: int | None = None,
) -> dict:
    """Compute fatigue index and related display data. Returns a dict."""
    fatigue_index = 0
    fatigue_warnings: list[str] = []

    if gesamt_trainings >= 4:
        for pts, warns in [
            _get_volume_spike_fatigue(weekly_volumes, block_age_weeks),
            _get_rpe_fatigue(user, heute),
            _get_frequency_fatigue(user, heute),
        ]:
            fatigue_index += pts
            fatigue_warnings.extend(warns)

    cardio_pts, cardio_warns, cardio_count, cardio_mins = _get_cardio_fatigue(user, heute)
    fatigue_index += cardio_pts
    fatigue_warnings.extend(cardio_warns)

    rating, color, message = _get_fatigue_rating(fatigue_index)
    return {
        "fatigue_index": fatigue_index,
        "fatigue_rating": rating,
        "fatigue_color": color,
        "fatigue_message": message,
        "fatigue_warnings": fatigue_warnings,
        "cardio_diese_woche": cardio_count,
        "cardio_minuten_diese_woche": cardio_mins,
    }


def _get_motivation_quote(form_index: int, fatigue_index: int) -> str:
    """Return a motivational quote based on form and fatigue."""
    quotes = {
        "high_performance": [
            "💪 Du bist auf Feuer! Weiter so!",
            "🔥 Unglaubliche Leistung! Dein Fortschritt ist beeindruckend.",
            "⚡ Du zerlegst deine Ziele! Keep crushing it!",
            "🏆 Champion-Mindset! Deine Konsistenz zahlt sich aus.",
        ],
        "good_performance": [
            "✨ Solide Arbeit! Du bist auf dem richtigen Weg.",
            "📈 Guter Progress! Bleib dran und die Ergebnisse kommen.",
            "💯 Starke Performance! Dein Training zeigt Wirkung.",
            "🎯 Du machst es richtig! Konsistenz ist der Schlüssel.",
        ],
        "need_motivation": [
            "🌟 Jeder Tag ist eine neue Chance! Du schaffst das.",
            "💪 Klein anfangen ist besser als gar nicht! Los geht's.",
            "🔋 Lade deine Batterien auf und komm stärker zurück!",
            "🎯 Ein Training nach dem anderen. Du bist stärker als du denkst!",
        ],
        "high_fatigue": [
            "🛌 Dein Körper braucht Erholung! Gönne dir eine Pause.",
            "⚠️ Regeneration ist Training! Nimm dir Zeit zum Erholen.",
            "🧘 Recovery ist Progress! Dein Körper braucht Zeit.",
            "💤 Qualität über Quantität! Weniger kann mehr sein.",
        ],
    }
    if fatigue_index >= 60:
        return random.choice(quotes["high_fatigue"])
    if form_index >= 70:
        return random.choice(quotes["high_performance"])
    if form_index >= 40:
        return random.choice(quotes["good_performance"])
    return random.choice(quotes["need_motivation"])


def _get_smart_motivation_quote(user, next_plan, fallback: str) -> str:
    """Datenbasisierter Motivationstext basierend auf dem letzten Training mit next_plan.

    Gibt z.B. "Letztes Mal: Bankdrücken 85 kg × 6 – heute PR-Versuch? 💪" zurück.
    Fällt auf den generischen fallback zurück wenn kein Plan oder keine Daten vorhanden.
    """
    if not next_plan:
        return fallback

    last_same_plan = (
        Trainingseinheit.objects.filter(
            user=user,
            plan=next_plan,
            abgeschlossen=True,
        )
        .order_by("-datum")
        .first()
    )
    if not last_same_plan:
        return fallback

    best_satz = (
        Satz.objects.filter(
            einheit=last_same_plan,
            ist_aufwaermsatz=False,
            gewicht__isnull=False,
            wiederholungen__isnull=False,
        )
        .select_related("uebung")
        .order_by("-gewicht")
        .first()
    )
    if not best_satz or not best_satz.gewicht or not best_satz.uebung:
        return fallback

    uebung = best_satz.uebung.bezeichnung
    gewicht = best_satz.gewicht
    wdh = best_satz.wiederholungen
    return f"Letztes Mal: {uebung} {gewicht} kg × {wdh} – heute PR-Versuch? 💪"


def _get_training_heatmap(user, heute) -> str:
    """Return JSON string of training counts per day for the last 365 days.

    Each entry has the format {"count": int, "deload": bool}.
    """
    start_date = heute - timedelta(days=364)
    trainings = Trainingseinheit.objects.filter(user=user, datum__gte=start_date)
    heatmap: dict[str, dict] = {}
    for t in trainings:
        key = t.datum.date().strftime("%Y-%m-%d") if hasattr(t.datum, "date") else str(t.datum)
        if key not in heatmap:
            heatmap[key] = {"count": 0, "deload": False}
        heatmap[key]["count"] += 1
        if t.ist_deload:
            heatmap[key]["deload"] = True
    return json.dumps(heatmap)


def _check_plateau_warnings(user, heute, favoriten) -> list[dict]:
    """Check for plateaus (no progress in top exercises over 4 weeks).

    Berücksichtigt RPE-Trend: sinkender RPE bei gleichem Gewicht ist
    Konsolidierung (kein Plateau). Nur bei stagnierendem/steigendem RPE
    wird ein echtes Plateau gemeldet.
    """
    warnings = []
    four_weeks_ago = heute - timedelta(days=28)
    two_weeks_ago = heute - timedelta(days=14)
    for fav in favoriten[:3]:
        uebung_id = fav["uebung__id"]
        uebung_name = fav["uebung__bezeichnung"]
        base_filter = dict(
            einheit__user=user,
            uebung_id=uebung_id,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        recent_max = float(
            Satz.objects.filter(**base_filter, einheit__datum__gte=two_weeks_ago).aggregate(
                max_gewicht=Max("gewicht")
            )["max_gewicht"]
            or 0
        )
        older_max = float(
            Satz.objects.filter(
                **base_filter, einheit__datum__gte=four_weeks_ago, einheit__datum__lt=two_weeks_ago
            ).aggregate(max_gewicht=Max("gewicht"))["max_gewicht"]
            or 0
        )
        if older_max > 0 and recent_max > 0 and recent_max <= older_max:
            # RPE-Trend prüfen: sinkender RPE = Konsolidierung, kein Plateau
            older_rpes = list(
                Satz.objects.filter(
                    **base_filter,
                    einheit__datum__gte=four_weeks_ago,
                    einheit__datum__lt=two_weeks_ago,
                    rpe__isnull=False,
                ).values_list("rpe", flat=True)
            )
            recent_rpes = list(
                Satz.objects.filter(
                    **base_filter, einheit__datum__gte=two_weeks_ago, rpe__isnull=False
                ).values_list("rpe", flat=True)
            )
            if older_rpes and recent_rpes:
                avg_older = sum(float(r) for r in older_rpes) / len(older_rpes)
                avg_recent = sum(float(r) for r in recent_rpes) / len(recent_rpes)
                if avg_older - avg_recent >= 0.5:
                    # RPE sinkt bei gleichem Gewicht → Konsolidierung
                    continue

            warnings.append(
                {
                    "type": "plateau",
                    "severity": "warning",
                    "exercise": uebung_name,
                    "message": "Kein Progress seit 4 Wochen",
                    "suggestion": "Versuche Intensitätstechniken wie Drop-Sets oder erhöhe das Volumen um 10-15%",
                    "icon": "bi-graph-down",
                    "color": "warning",
                }
            )
    return warnings


def _check_regression_warnings(user, heute) -> list[dict]:
    """Check for performance regressions (>15% weight drop) in recent exercises."""
    warnings = []
    two_weeks_ago = heute - timedelta(days=14)
    recent_exercises = (
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=two_weeks_ago,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values("uebung__bezeichnung", "uebung_id")
        .annotate(avg_gewicht=Avg("gewicht"))
        .filter(avg_gewicht__isnull=False)
    )
    for ex in recent_exercises:
        current_avg = float(ex["avg_gewicht"])
        previous_avg = float(
            Satz.objects.filter(
                einheit__user=user,
                uebung_id=ex["uebung_id"],
                ist_aufwaermsatz=False,
                einheit__ist_deload=False,
                einheit__datum__gte=heute - timedelta(days=28),
                einheit__datum__lt=two_weeks_ago,
            ).aggregate(Avg("gewicht"))["gewicht__avg"]
            or 0
        )
        if previous_avg > 0 and current_avg < previous_avg * 0.85:
            drop_percent = round(((previous_avg - current_avg) / previous_avg) * 100)
            # Finde betroffene Trainings (nicht als Deload markiert, aber mit Regression)
            affected_trainings = list(
                Trainingseinheit.objects.filter(
                    user=user,
                    datum__gte=two_weeks_ago,
                    ist_deload=False,
                    saetze__uebung_id=ex["uebung_id"],
                    saetze__ist_aufwaermsatz=False,
                )
                .distinct()
                .values_list("id", flat=True)[:5]
            )
            warnings.append(
                {
                    "type": "regression",
                    "severity": "danger",
                    "exercise": ex["uebung__bezeichnung"],
                    "message": f"Leistungsabfall von {drop_percent}%",
                    "suggestion": "Prüfe Regeneration, Ernährung und Schlaf. Erwäge eine Deload-Woche.",
                    "icon": "bi-arrow-down-circle",
                    "color": "danger",
                    "training_ids": affected_trainings,
                }
            )
    return warnings


def _check_stagnation_warnings(user, heute) -> list[dict]:
    """Check for muscle groups not trained in the last 14 days."""
    warnings = []
    all_muscle_groups = dict(MUSKELGRUPPEN)
    trained_recently = set(
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=heute - timedelta(days=14),
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        ).values_list("uebung__muskelgruppe", flat=True)
    )
    user_muscle_groups = set(
        Uebung.objects.filter(Q(is_custom=False) | Q(created_by=user)).values_list(
            "muskelgruppe", flat=True
        )
    )
    for mg in user_muscle_groups:
        if mg in trained_recently:
            continue
        last_training = (
            Satz.objects.filter(
                einheit__user=user,
                uebung__muskelgruppe=mg,
                ist_aufwaermsatz=False,
                einheit__ist_deload=False,
            )
            .order_by("-einheit__datum")
            .first()
        )
        if not last_training:
            continue
        days_ago = (heute.date() - last_training.einheit.datum.date()).days
        if days_ago >= 14:
            warnings.append(
                {
                    "type": "stagnation",
                    "severity": "info",
                    "exercise": all_muscle_groups.get(mg, mg),
                    "message": f"Seit {days_ago} Tagen nicht trainiert",
                    "suggestion": "Integriere diese Muskelgruppe wieder in deinen Trainingsplan",
                    "icon": "bi-pause-circle",
                    "color": "info",
                }
            )
    return warnings


_PUSH_MUSCLES = {"BRUST", "TRIZEPS", "SCHULTER_VORN", "SCHULTER_SEIT"}
_PULL_MUSCLES = {"RUECKEN_LAT", "RUECKEN_TRAPEZ", "BIZEPS", "SCHULTER_HINT"}


def _check_balance_warnings(user, heute) -> list[dict]:
    """Check for push/pull imbalance over the last 14 days.

    Vergleicht Arbeitssätze in Push- vs. Pull-Muskelgruppen.
    Warnt wenn das Verhältnis > 2.5:1 oder < 1:2.5 ist.
    """
    two_weeks_ago = heute - timedelta(days=14)
    muscle_counts = (
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=two_weeks_ago,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values("uebung__muskelgruppe")
        .annotate(count=Count("id"))
    )
    counts = {r["uebung__muskelgruppe"]: r["count"] for r in muscle_counts}
    push = sum(counts.get(mg, 0) for mg in _PUSH_MUSCLES)
    pull = sum(counts.get(mg, 0) for mg in _PULL_MUSCLES)

    if push < 3 or pull < 3:
        return []

    ratio = push / pull
    if ratio > 2.5:
        return [
            {
                "type": "balance",
                "severity": "warning",
                "exercise": "Push/Pull-Balance",
                "message": f"Push-Sätze ({push}) deutlich höher als Pull-Sätze ({pull})",
                "suggestion": "Ergänze Rücken- und Bizeps-Übungen für eine ausgeglichene Belastung",
                "icon": "bi-arrow-left-right",
                "color": "warning",
            }
        ]
    if ratio < 0.4:
        return [
            {
                "type": "balance",
                "severity": "warning",
                "exercise": "Push/Pull-Balance",
                "message": f"Pull-Sätze ({pull}) deutlich höher als Push-Sätze ({push})",
                "suggestion": "Ergänze Brust-, Schulter- und Trizeps-Übungen für eine ausgeglichene Belastung",
                "icon": "bi-arrow-left-right",
                "color": "warning",
            }
        ]
    return []


def _get_rpe10_anteil(user, heute) -> float | None:
    """Return RPE-10 percentage over the last 14 days (work sets only), or None."""
    two_weeks_ago = heute - timedelta(days=14)
    base = Satz.objects.filter(
        einheit__user=user,
        einheit__datum__gte=two_weeks_ago,
        ist_aufwaermsatz=False,
        einheit__ist_deload=False,
        rpe__isnull=False,
    )
    gesamt = base.count()
    if gesamt == 0:
        return None
    rpe10_count = base.filter(rpe=10).count()
    return round((rpe10_count / gesamt) * 100, 1)


def _check_rpe10_warning(user, heute) -> list[dict]:
    """Warn if >15% of work sets in the last 14 days were RPE 10."""
    anteil = _get_rpe10_anteil(user, heute)
    if anteil is not None and anteil > 15:
        return [
            {
                "type": "rpe10",
                "severity": "danger",
                "exercise": "RPE-10-Anteil",
                "message": (
                    f"{anteil}% deiner Arbeitssätze waren RPE 10 (Muskelversagen). "
                    f"Ziel: unter 5%."
                ),
                "suggestion": (
                    "Reduziere Sätze bis zum Versagen – halte 1-2 Reps in Reserve (RIR). "
                    "Zu viel RPE 10 erhöht Verletzungsrisiko und verlängert die Regeneration."
                ),
                "icon": "bi-exclamation-triangle-fill",
                "color": "danger",
            }
        ]
    return []


def _get_session_rpe_trend(user, num_sessions: int = 12) -> dict:
    """Phase 19: Berechnet Session-RPE-Trend für die letzten N Sessions.

    Aggregiert den gewichteten Durchschnitts-RPE (nach Sätzen) pro Session.
    Berechnet eine lineare Regression um steigende/fallende/stabile Trends zu erkennen.

    Returns:
        {
            "sessions": [{date_str, avg_rpe, session_id}, ...],
            "trend": "rising" | "falling" | "stable" | None,
            "slope": float | None,
            "current_avg": float | None,
        }
    """
    # Letzte N abgeschlossene Sessions mit RPE-Daten
    sessions_qs = Trainingseinheit.objects.filter(
        user=user,
        abgeschlossen=True,
    ).order_by(
        "-datum"
    )[:num_sessions]

    session_data = []
    for session in sessions_qs:
        rpe_agg = Satz.objects.filter(
            einheit=session,
            ist_aufwaermsatz=False,
            rpe__isnull=False,
        ).aggregate(avg_rpe=Avg("rpe"), count=Sum(1))

        if rpe_agg["avg_rpe"] is not None and rpe_agg["count"] and rpe_agg["count"] >= 2:
            session_data.append(
                {
                    "date": (
                        session.datum.date() if hasattr(session.datum, "date") else session.datum
                    ),
                    "date_str": session.datum.strftime("%d.%m"),
                    "avg_rpe": round(float(rpe_agg["avg_rpe"]), 1),
                    "session_id": session.id,
                }
            )

    # Chronologisch sortieren (älteste zuerst)
    session_data.sort(key=lambda x: x["date"])

    # date-Feld entfernen – nicht JSON-serialisierbar (datetime.date),
    # wird im Template via |safe direkt als JS ausgegeben.
    for entry in session_data:
        del entry["date"]

    if len(session_data) < 3:
        return {"sessions": session_data, "trend": None, "slope": None, "current_avg": None}

    current_avg = session_data[-1]["avg_rpe"]

    # Lineare Regression über Session-Index → RPE
    n = len(session_data)
    xs = list(range(n))
    ys = [s["avg_rpe"] for s in session_data]
    s_x = sum(xs)
    s_y = sum(ys)
    s_xy = sum(x * y for x, y in zip(xs, ys))
    s_xx = sum(x * x for x in xs)
    denom = n * s_xx - s_x**2

    if denom == 0:
        return {
            "sessions": session_data,
            "trend": "stable",
            "slope": 0.0,
            "current_avg": current_avg,
        }

    slope = (n * s_xy - s_x * s_y) / denom

    # Trend-Klassifikation: > 0.1 RPE/Session = steigend
    if slope > 0.1:
        trend = "rising"
    elif slope < -0.1:
        trend = "falling"
    else:
        trend = "stable"

    return {
        "sessions": session_data,
        "trend": trend,
        "slope": round(slope, 3),
        "current_avg": current_avg,
    }


def _check_session_rpe_trend_warning(user, heute) -> list[dict]:
    """Phase 19.3: Warnt wenn Session-RPE über 3+ Sessions steigend und > 8.5."""
    trend_data = _get_session_rpe_trend(user, num_sessions=8)

    if trend_data["trend"] != "rising" or trend_data["current_avg"] is None:
        return []

    if trend_data["current_avg"] <= 8.5:
        return []

    # Prüfe ob die letzten 3 Sessions tatsächlich steigend sind
    sessions = trend_data["sessions"]
    if len(sessions) < 3:
        return []

    last_3 = [s["avg_rpe"] for s in sessions[-3:]]
    if not (last_3[0] < last_3[1] < last_3[2]):
        return []

    return [
        {
            "type": "rpe_trend",
            "severity": "warning",
            "exercise": "Session-RPE",
            "message": (
                f"Deine Trainingsintensität steigt seit 3+ Sessions "
                f"(aktuell Ø RPE {trend_data['current_avg']}). "
            ),
            "suggestion": (
                "Steigender RPE ist ein Frühindikator für Ermüdung. "
                "Erwäge einen Deload oder reduziere Gewicht/Volumen für 1-2 Sessions."
            ),
            "icon": "bi-graph-up-arrow",
            "color": "warning",
        }
    ]


def _get_weakness_progress(user, active_block) -> list[dict]:
    """Berechne laufenden Fortschritt pro Schwachstelle aus dem Block-Snapshot.

    Für jede Muskelgruppe im Snapshot: aktuelle Arbeitssätze im laufenden
    Monat zählen und gegen Soll-Bereich vergleichen.

    Returns:
        Liste von Dicts mit muskelgruppe, label, ist_saetze, soll_min, soll_max,
        prozent, status ('erreicht', 'auf_kurs', 'hinter_plan'),
        baseline_saetze (Ausgangswert bei Snapshot).
    """
    if not active_block or not active_block.schwachstellen_snapshot:
        return []

    from ai_coach.plan_generator import _humanize_muskelgruppe

    snapshot = active_block.schwachstellen_snapshot
    # Aktuelle Arbeitssätze pro Muskelgruppe (letzte 30 Tage)
    seit = timezone.now() - timedelta(days=30)
    mg_counts = dict(
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=seit,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values_list("uebung__muskelgruppe")
        .annotate(count=Count("id"))
        .values_list("uebung__muskelgruppe", "count")
    )

    result = []
    for entry in snapshot:
        mg = entry["muskelgruppe"]
        soll_min = entry["soll_min"]
        soll_max = entry["soll_max"]
        baseline = entry["ist_saetze"]
        ist = mg_counts.get(mg, 0)

        # Fortschritt als % des Soll-Min
        prozent = round((ist / soll_min) * 100) if soll_min > 0 else 100

        if ist >= soll_min:
            status = "erreicht"
        elif soll_min > 0 and (ist / soll_min) >= 0.6:
            status = "auf_kurs"
        else:
            status = "hinter_plan"

        result.append(
            {
                "muskelgruppe": mg,
                "label": _humanize_muskelgruppe(mg),
                "ist_saetze": ist,
                "soll_min": soll_min,
                "soll_max": soll_max,
                "prozent": min(prozent, 100),
                "status": status,
                "baseline_saetze": baseline,
            }
        )

    return result


def get_weakness_comparison(user) -> list[dict]:
    """Monatsende-Vergleich: aktuelle Sätze vs. Ausgangswert aus dem Snapshot.

    Returns:
        Liste von Dicts mit muskelgruppe, label, baseline, aktuell, behoben (bool),
        zusammenfassung (str).
    """
    from ai_coach.plan_generator import _humanize_muskelgruppe

    active_block = _get_active_trainingsblock(user)
    if not active_block or not active_block.schwachstellen_snapshot:
        return []

    seit = timezone.now() - timedelta(days=30)
    mg_counts = dict(
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=seit,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values_list("uebung__muskelgruppe")
        .annotate(count=Count("id"))
        .values_list("uebung__muskelgruppe", "count")
    )

    result = []
    for entry in active_block.schwachstellen_snapshot:
        mg = entry["muskelgruppe"]
        baseline = entry["ist_saetze"]
        soll_min = entry["soll_min"]
        aktuell = mg_counts.get(mg, 0)
        behoben = aktuell >= soll_min
        label = _humanize_muskelgruppe(mg)
        symbol = "\u2713" if behoben else "\u2717"
        status_text = "Behoben" if behoben else "Noch untertrainiert"
        result.append(
            {
                "muskelgruppe": mg,
                "label": label,
                "baseline": baseline,
                "aktuell": aktuell,
                "soll_min": soll_min,
                "behoben": behoben,
                "zusammenfassung": f"{label}: {baseline} \u2192 {aktuell} Sätze {symbol} {status_text}",
            }
        )
    return result


def _get_performance_warnings(user, heute, favoriten, gesamt_trainings: int) -> list[dict]:
    """Aggregate performance warnings (plateau, regression, stagnation, balance, rpe10, rpe_trend), max 3."""
    if gesamt_trainings < 4:
        return []
    all_warnings = (
        _check_rpe10_warning(user, heute)
        + _check_session_rpe_trend_warning(user, heute)
        + _check_plateau_warnings(user, heute, favoriten)
        + _check_regression_warnings(user, heute)
        + _check_balance_warnings(user, heute)
        + _check_stagnation_warnings(user, heute)
    )
    priority = {
        "rpe10": 0,
        "rpe_trend": 1,
        "regression": 2,
        "plateau": 3,
        "balance": 4,
        "stagnation": 5,
    }
    return sorted(all_warnings, key=lambda w: priority[w["type"]])[:3]


def _linear_forecast(dates_values: list, forecast_days: int) -> float | None:
    """Lineare Regression auf (date, value)-Paaren → Prognose für forecast_days in der Zukunft.

    Args:
        dates_values: Liste von (date, float)-Tupeln, chronologisch sortiert.
        forecast_days: Tage in der Zukunft ab dem letzten Datenpunkt.

    Returns:
        Prognostizierter Wert oder None wenn < 5 Datenpunkte oder Nenner = 0.
    """
    if len(dates_values) < 5:
        return None
    t0 = dates_values[0][0]
    xs = [(d - t0).days for d, _ in dates_values]
    ys = [float(v) for _, v in dates_values]
    n = len(xs)
    s_x = sum(xs)
    s_y = sum(ys)
    s_xy = sum(x * y for x, y in zip(xs, ys))
    s_xx = sum(x * x for x in xs)
    denom = n * s_xx - s_x**2
    if denom == 0:
        return None
    slope = (n * s_xy - s_x * s_y) / denom
    intercept = (s_y - slope * s_x) / n
    return slope * (xs[-1] + forecast_days) + intercept


def _find_next_plan_idx(group_plans: list, user) -> int:
    """Return the index of the next plan in the rotation."""
    last_training = (
        Trainingseinheit.objects.filter(user=user, plan__in=group_plans)
        .select_related("plan")
        .order_by("-datum")
        .first()
    )
    if not (last_training and last_training.plan):
        return 0
    plan_ids = [p.id for p in group_plans]
    try:
        last_idx = plan_ids.index(last_training.plan.id)
        return (last_idx + 1) % len(group_plans)
    except ValueError:
        return 0


def _add_plan_group_context(user, context: dict) -> None:
    """Extend context dict with active plan-group data (mutates context in-place)."""
    try:
        profile = user.profile
        if not profile.active_plan_group:
            return
        group_plans = list(
            Plan.objects.filter(user=user, gruppe_id=profile.active_plan_group).order_by(
                "gruppe_reihenfolge", "name"
            )
        )
        if not group_plans:
            context["active_plan_group_stale"] = True
            return
        context["active_plan_group_name"] = group_plans[0].gruppe_name or "Unbenannte Gruppe"
        context["active_plan_group_id"] = str(profile.active_plan_group)
        next_idx = _find_next_plan_idx(group_plans, user)
        context["next_plan"] = group_plans[next_idx]
        context["next_plan_index"] = next_idx + 1
        context["group_plan_count"] = len(group_plans)
        current_week = profile.get_current_cycle_week()
        if current_week:
            context["cycle_week"] = current_week
            context["cycle_length"] = profile.cycle_length
            context["is_deload"] = profile.is_deload_week()
            context["deload_volume_pct"] = int((1 - profile.deload_volume_factor) * 100)
            context["deload_weight_pct"] = int((1 - profile.deload_weight_factor) * 100)
            context["deload_rpe_target"] = profile.deload_rpe_target
    except UserProfile.DoesNotExist:
        pass


# ---------------------------------------------------------------------------
# Dashboard view (orchestration only)
# ---------------------------------------------------------------------------


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    heute = timezone.now()

    # ----------------------------------------------------------------
    # Cached block: teure Berechnungen (Streak, Volumen, Fatigue, etc.)
    # Cache-Key ist user-spezifisch; wird in signals.py invalidiert
    # wenn der User ein neues Training speichert.
    # ----------------------------------------------------------------
    cache_key = f"dashboard_computed_{request.user.id}"
    computed = cache.get(cache_key)

    if computed is None:
        trainings_diese_woche = _count_trainings_this_week(request.user, heute)
        streak = _calculate_streak(request.user, heute)
        favoriten = list(_get_favoriten(request.user))  # list() → pickleable
        gesamt_trainings = Trainingseinheit.objects.filter(user=request.user).count()
        gesamt_saetze = Satz.objects.filter(
            einheit__user=request.user, ist_aufwaermsatz=False, einheit__ist_deload=False
        ).count()
        form_index, form_rating, form_color, form_factors = _calculate_form_index(
            request.user, heute, trainings_diese_woche, streak, gesamt_trainings
        )
        active_block = _get_active_trainingsblock(request.user)
        block_age_weeks = active_block.weeks_since_start if active_block else None
        weekly_volumes = _calculate_weekly_volumes(request.user, heute, active_block)
        fatigue_data = _calculate_fatigue_index(
            request.user, heute, weekly_volumes, gesamt_trainings, block_age_weeks
        )
        motivation_quote = _get_motivation_quote(form_index, fatigue_data["fatigue_index"])
        training_heatmap_json = _get_training_heatmap(request.user, heute)
        performance_warnings = _get_performance_warnings(
            request.user, heute, favoriten, gesamt_trainings
        )
        # Phase 19: Session-RPE-Trend
        session_rpe_trend = _get_session_rpe_trend(request.user)
        session_rpe_trend["sessions_json"] = json.dumps(session_rpe_trend["sessions"])
        # Phase 20: Schwachstellen-Fortschritt
        weakness_progress = _get_weakness_progress(request.user, active_block)
        computed = {
            "trainings_diese_woche": trainings_diese_woche,
            "streak": streak,
            "favoriten": favoriten,
            "gesamt_trainings": gesamt_trainings,
            "gesamt_saetze": gesamt_saetze,
            "form_index": form_index,
            "form_rating": form_rating,
            "form_color": form_color,
            "form_factors": form_factors,
            "weekly_volumes": weekly_volumes,
            # Trainingsblock-Kontext (Phase 3 + Phase 10)
            "active_block": active_block,
            "block_age_weeks": block_age_weeks,
            "block_age_warning": get_block_age_warning(active_block),
            **fatigue_data,
            "motivation_quote": motivation_quote,
            "training_heatmap_json": training_heatmap_json,
            "performance_warnings": performance_warnings,
            # Phase 19: Session-RPE-Trend
            "session_rpe_trend": session_rpe_trend,
            # Phase 20: Schwachstellen-Fortschritt
            "weakness_progress": weakness_progress,
        }
        cache.set(cache_key, computed, timeout=DASHBOARD_CACHE_TTL)

    # ----------------------------------------------------------------
    # Immer frisch: Model-Instanzen + settings-basierte Werte
    # ----------------------------------------------------------------
    letztes_training = Trainingseinheit.objects.filter(
        user=request.user, abgeschlossen=True
    ).first()
    letzter_koerperwert = KoerperWerte.objects.filter(user=request.user).first()
    use_openrouter = not settings.DEBUG or os.getenv("USE_OPENROUTER", "False").lower() == "true"

    # Offene (nicht abgeschlossene) Sessions – neueste zuerst
    offene_sessions = list(
        Trainingseinheit.objects.filter(user=request.user, abgeschlossen=False)
        .order_by("-datum")
        .values("id", "datum", "plan__name")
    )
    offene_session = offene_sessions[0] if offene_sessions else None
    offene_sessions_anzahl = len(offene_sessions)

    # Wochenübersicht (immer frisch – ändert sich intraday)
    week_overview = _get_week_overview(request.user, heute)
    trainings_ziel = 3
    try:
        trainings_ziel = request.user.profile.trainings_pro_woche
    except UserProfile.DoesNotExist:
        pass

    # PRs der letzten 7 Tage (immer frisch)
    week_ago = heute - timedelta(days=7)
    prs_diese_woche = (
        Satz.objects.filter(
            einheit__user=request.user,
            einheit__datum__gte=week_ago,
            is_pr=True,
            ist_aufwaermsatz=False,
        )
        .select_related("uebung", "einheit")
        .order_by("-einheit__datum")
    )

    context = {
        "letztes_training": letztes_training,
        "letzter_koerperwert": letzter_koerperwert,
        "use_openrouter": use_openrouter,
        "offene_session": offene_session,
        "offene_sessions_anzahl": offene_sessions_anzahl,
        "week_overview": week_overview,
        "trainings_ziel": trainings_ziel,
        "prs_diese_woche": prs_diese_woche,
        **computed,
    }
    _add_plan_group_context(request.user, context)
    # Überschreibe gecachten Generic-Quote mit datenbasisiertem Text (4.3)
    context["motivation_quote"] = _get_smart_motivation_quote(
        request.user, context.get("next_plan"), computed["motivation_quote"]
    )
    return render(request, "core/dashboard.html", context)


@login_required
def training_list(request: HttpRequest) -> HttpResponse:
    """Zeigt eine Liste aller vergangenen Trainings."""
    from django.db.models import BooleanField, ExpressionWrapper

    trainings = (
        Trainingseinheit.objects.filter(user=request.user)
        .select_related("plan")
        .annotate(
            satz_count=Count("saetze"),
            hat_prs=ExpressionWrapper(
                Q(saetze__is_pr=True, saetze__ist_aufwaermsatz=False),
                output_field=BooleanField(),
            ),
        )
        .prefetch_related(
            Prefetch(
                "saetze",
                queryset=Satz.objects.filter(ist_aufwaermsatz=False).select_related("uebung"),
                to_attr="arbeitssaetze_list",
            )
        )
        .order_by("-datum")
    )

    user_kg = get_user_kg(request.user)
    trainings_mit_volumen = []
    for training in trainings:
        arbeitssaetze = training.arbeitssaetze_list
        volumen = calc_volume(arbeitssaetze, user_kg)
        trainings_mit_volumen.append(
            {
                "training": training,
                "volumen": round(volumen, 1),
                "arbeitssaetze": len(arbeitssaetze),
                "hat_prs": bool(training.hat_prs),
            }
        )

    context = {"trainings_data": trainings_mit_volumen}
    return render(request, "core/training_list.html", context)


@login_required
def delete_training(request: HttpRequest, training_id: int) -> HttpResponse:
    """Löscht ein komplettes Training aus der Historie."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    if request.method == "POST":
        training.delete()
    # Wir leiten zurück zur Liste (History)
    return redirect("training_list")


# ---------------------------------------------------------------------------
# Private helpers for exercise_stats view
# ---------------------------------------------------------------------------


def _get_user_koerpergewicht(user) -> float:
    """Gibt das letzte erfasste Körpergewicht des Users zurück.

    Fallback: 80 kg wenn keine KoerperWerte vorhanden.
    Der Wert wird innerhalb eines Requests gecacht (über Closure/Arg).
    """
    eintrag = KoerperWerte.objects.filter(user=user).order_by("-datum").first()
    if eintrag and eintrag.gewicht:
        return float(eintrag.gewicht)
    return 80.0  # Trainings-Durchschnitt als Fallback


def _get_koerpergewicht_for_date(user, datum) -> float:
    """Gibt das Körpergewicht des Users am angegebenen Datum zurück.

    Sucht den nächsten KoerperWerte-Eintrag ≤ datum.
    Fallback: aktuellstes Gewicht, dann 80 kg.
    """
    eintrag = (
        KoerperWerte.objects.filter(user=user, datum__lte=datum)
        .order_by("-datum")
        .values_list("gewicht", flat=True)
        .first()
    )
    if eintrag:
        return float(eintrag)
    # Kein Eintrag vor datum → aktuellstes Gewicht als Fallback
    return _get_user_koerpergewicht(user)


def _get_koerpergewicht_map(user, dates) -> dict:
    """Batch-Lookup: Körpergewicht pro Datum für effiziente Verarbeitung.

    Vermeidet N+1-Queries bei vielen Trainingstagen.
    Gibt {datum: gewicht_float} zurück.

    Algorithmus: Alle KoerperWerte sortiert laden, dann per Bisect
    für jedes Datum den passenden Eintrag finden.
    """
    from bisect import bisect_right

    if not dates:
        return {}

    # Alle Gewichtseinträge chronologisch laden (eine Query)
    entries = list(
        KoerperWerte.objects.filter(user=user).order_by("datum").values_list("datum", "gewicht")
    )

    if not entries:
        fallback = 80.0
        return {d: fallback for d in dates}

    # Sicherstellen dass alle Datumsangaben date-Objekte sind (nicht datetime)
    from datetime import date as _date_type
    from datetime import datetime as _dt_type

    entry_dates = [
        (
            e[0]
            if isinstance(e[0], _date_type) and not isinstance(e[0], _dt_type)
            else e[0].date() if isinstance(e[0], _dt_type) else e[0]
        )
        for e in entries
    ]
    entry_weights = [float(e[1]) for e in entries]
    latest_weight = entry_weights[-1]

    result = {}
    for d in dates:
        # Normalisiere auf date (falls datetime übergeben wird)
        d_date = d.date() if isinstance(d, _dt_type) else d
        # bisect_right: Index des ersten Eintrags > d
        idx = bisect_right(entry_dates, d_date)
        if idx > 0:
            result[d] = entry_weights[idx - 1]  # Nächster Eintrag ≤ d_date
        else:
            result[d] = latest_weight  # Kein Eintrag vor d_date → aktuellstes
    return result


def _compute_1rm_and_weight(satz, uebung, user_koerpergewicht: float = 80.0) -> tuple[float, float]:
    """Return (estimated_1rm, effective_weight) for a single set.

    Formel: Epley (1985) – weight × (1 + reps/30)
    Genauigkeit:
    - 1–6 Wdh.: gute Schätzung (±5%)
    - 7–10 Wdh.: akzeptabel (±8%)
    - > 10 Wdh.: systematische Überschätzung – Brzycki-Formel wäre dort genauer.
    Für relative Vergleiche (Progression über Zeit) ist die Formel trotzdem konsistent.

    Körpergewichts-Übungen (KOERPERGEWICHT):
        ZUSATZ: effektives_gewicht = (user_kg * faktor) + zusatzgewicht
        GEGEN:  effektives_gewicht = (user_kg * faktor) - gegengewicht
        Beispiel Dips (Faktor 0.70, 80kg User, 0kg Zusatz): 80 * 0.70 = 56 kg effektiv
        Beispiel Assistierte Dips (GEGEN, 80kg, 20kg Hilfe): 80 * 0.70 - 20 = 36 kg effektiv
    """
    zusatzgewicht = float(satz.gewicht)

    if uebung.gewichts_typ == "PRO_SEITE":
        effektives_gewicht = zusatzgewicht * 2
    elif uebung.gewichts_typ == "KOERPERGEWICHT":
        faktor = getattr(uebung, "koerpergewicht_faktor", 1.0) or 1.0
        richtung = getattr(uebung, "gewichts_richtung", "ZUSATZ") or "ZUSATZ"
        basis = user_koerpergewicht * faktor
        if richtung == "GEGEN":
            effektives_gewicht = max(0.0, basis - zusatzgewicht)
        else:
            effektives_gewicht = basis + zusatzgewicht
    else:
        effektives_gewicht = zusatzgewicht

    if uebung.gewichts_typ == "ZEIT":
        return float(satz.wiederholungen), effektives_gewicht
    if effektives_gewicht > 0:
        return effektives_gewicht * (1 + satz.wiederholungen / 30), effektives_gewicht
    return 0.0, effektives_gewicht


def _calc_rpe_trend(saetze, avg_rpe) -> str | None:
    """Return 'improving', 'declining', or 'stable' based on 4-week vs 4-8-week RPE comparison.

    Returns None if insufficient data.
    Lower RPE for same weights = improving adaptation.
    """
    if not avg_rpe:
        return None
    heute = timezone.now()
    recent_rpe = saetze.filter(einheit__datum__gte=heute - timedelta(days=28)).aggregate(
        Avg("rpe")
    )["rpe__avg"]
    older_rpe = saetze.filter(
        einheit__datum__gte=heute - timedelta(days=56),
        einheit__datum__lt=heute - timedelta(days=28),
    ).aggregate(Avg("rpe"))["rpe__avg"]
    if not (recent_rpe and older_rpe):
        return None
    diff = recent_rpe - older_rpe
    if diff < -0.3:
        return "improving"
    if diff > 0.3:
        return "declining"
    return "stable"


@login_required
def exercise_stats(request: HttpRequest, uebung_id: int) -> HttpResponse:
    """Berechnet 1RM-Verlauf und Rekorde für eine Übung."""
    uebung = get_object_or_404(
        Uebung,
        Q(is_custom=False) | Q(created_by=request.user),
        id=uebung_id,
    )

    saetze = (
        Satz.objects.filter(
            einheit__user=request.user,
            uebung=uebung,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .select_related("einheit")
        .order_by("einheit__datum")
    )

    if not saetze.exists():
        return render(request, "core/stats_exercise.html", {"uebung": uebung, "no_data": True})

    # Phase 14.2: Historisches Körpergewicht pro Trainingstag laden
    is_kg_uebung = uebung.gewichts_typ == "KOERPERGEWICHT"
    if is_kg_uebung:
        training_dates = list(saetze.values_list("einheit__datum", flat=True).distinct())
        kg_map = _get_koerpergewicht_map(request.user, training_dates)
    else:
        kg_map = {}
    user_koerpergewicht = _get_user_koerpergewicht(request.user)

    # Best 1RM per day + overall records
    history_data: dict[str, float] = {}
    wdh_history: dict[str, int] = {}  # Wdh-Verlauf für KG-Übungen
    rpe_session: dict[str, list[float]] = {}  # RPE-Werte je Session-Tag
    personal_record = 0.0
    best_weight = 0.0
    best_reps = 0

    for satz in saetze:
        # Historisches Gewicht für KG-Übungen, aktuelles für andere
        kg = (
            kg_map.get(satz.einheit.datum, user_koerpergewicht)
            if is_kg_uebung
            else user_koerpergewicht
        )
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung, kg)
        datum_str = satz.einheit.datum.strftime("%d.%m.%Y")
        if datum_str not in history_data or one_rm > history_data[datum_str]:
            history_data[datum_str] = round(one_rm, 1)
        if one_rm > personal_record:
            personal_record = round(one_rm, 1)
        if eff_weight > best_weight:
            best_weight = eff_weight
        # Wdh-Verlauf für KG-Übungen ohne Zusatzgewicht
        if is_kg_uebung and float(satz.gewicht) == 0:
            wdh = satz.wiederholungen
            if datum_str not in wdh_history or wdh > wdh_history[datum_str]:
                wdh_history[datum_str] = wdh
            if wdh > best_reps:
                best_reps = wdh
        # RPE-Verlauf: Durchschnitt pro Trainingstag
        if satz.rpe is not None:
            rpe_session.setdefault(datum_str, []).append(float(satz.rpe))

    rpe_history = {d: round(sum(v) / len(v), 1) for d, v in rpe_session.items()}

    # 1RM-Prognose: lineare Regression auf bisherigem Verlauf (8 Wochen = 56 Tage)
    _history_pairs = [(_dt.strptime(d, "%d.%m.%Y").date(), v) for d, v in history_data.items()]
    _forecast_raw = _linear_forecast(_history_pairs, 56)
    _current_1rm_last = list(history_data.values())[-1] if history_data else 0
    forecast_1rm = (
        round(_forecast_raw, 1) if _forecast_raw and _forecast_raw > _current_1rm_last else None
    )

    avg_rpe = saetze.aggregate(Avg("rpe"))["rpe__avg"]

    # Wdh-Verlauf als primäre Chart-Metrik wenn KG-Übung UND ausschließlich
    # ohne Zusatzgewicht trainiert. Sobald irgendein Satz Zusatz hat → 1RM-Chart.
    hat_zusatzgewicht = saetze.filter(gewicht__gt=0).exists()
    show_reps_chart = is_kg_uebung and bool(wdh_history) and not hat_zusatzgewicht

    # PR-Geschichte: alle gespeicherten PRs dieser Übung (älteste zuerst für Timeline)
    pr_history = (
        Satz.objects.filter(
            einheit__user=request.user,
            uebung=uebung,
            is_pr=True,
            ist_aufwaermsatz=False,
        )
        .select_related("einheit")
        .order_by("einheit__datum")
    )

    context = {
        "uebung": uebung,
        "labels_json": json.dumps(list(history_data.keys())),
        "data_json": json.dumps(list(history_data.values())),
        "wdh_labels_json": json.dumps(list(wdh_history.keys())),
        "wdh_data_json": json.dumps(list(wdh_history.values())),
        "rpe_labels_json": json.dumps(list(rpe_history.keys())),
        "rpe_data_json": json.dumps(list(rpe_history.values())),
        "show_rpe_chart": len(rpe_history) >= 3,
        "show_reps_chart": show_reps_chart,
        "personal_record": personal_record,
        "best_weight": best_weight,
        "best_reps": best_reps,
        "user_koerpergewicht": user_koerpergewicht,
        "avg_rpe": round(avg_rpe, 1) if avg_rpe else None,
        "rpe_trend": _calc_rpe_trend(saetze, avg_rpe),
        "pr_history": pr_history,
        "forecast_1rm": forecast_1rm,
    }
    return render(request, "core/stats_exercise.html", context)


# ---------------------------------------------------------------------------
# Private helpers for training_stats view
# ---------------------------------------------------------------------------

_MUSCLE_MAPPING: dict[str, list[str]] = {
    "BRUST": ["front_chest_left", "front_chest_right"],
    "TRIZEPS": ["back_triceps_left", "back_triceps_right"],
    "BIZEPS": ["front_biceps_left", "front_biceps_right"],
    "SCHULTER_VORN": ["front_delt_left", "front_delt_right"],
    "SCHULTER_SEIT": ["front_delt_left", "front_delt_right"],
    "SCHULTER_HINT": ["back_delt_left", "back_delt_right"],
    "RUECKEN_LAT": ["back_lat_left", "back_lat_right"],
    "RUECKEN_TRAPEZ": ["back_trap_left", "back_trap_right"],
    "RUECKEN_UNTEN": ["back_lower_back"],
    "BEINE_QUAD": ["front_quad_left", "front_quad_right"],
    "BEINE_HAM": ["back_ham_left", "back_ham_right"],
    "WADEN": ["back_calves_left", "back_calves_right"],
    "PO": ["back_glutes_left", "back_glutes_right"],
    "BAUCH": ["front_abs"],
    "UNTERARME": ["front_forearm_left", "front_forearm_right"],
    "ADDUKTOREN": ["front_quad_left", "front_quad_right"],
    "ABDUKTOREN": ["back_glutes_left", "back_glutes_right"],
}


def _calc_per_training_volume(trainings, user_kg: float = 0.0) -> tuple[list, list, list]:
    """Return (date_labels, volumes, deload_flags) for every training session."""
    labels: list[str] = []
    data: list[float] = []
    deload_flags: list[bool] = []
    for training in trainings:
        vol = calc_volume(training.arbeitssaetze_list, user_kg)
        labels.append(training.datum.strftime("%d.%m"))
        data.append(round(vol, 1))
        deload_flags.append(bool(training.ist_deload))
    return labels, data, deload_flags


def _calc_weekly_volume(trainings, user_kg: float = 0.0) -> tuple[list, list]:
    """Return (iso_week_labels, volumes) for the last 12 ISO calendar weeks.

    Deload trainings are excluded so they don't distort volume trends.
    """
    weekly: defaultdict[str, float] = defaultdict(float)
    for training in trainings:
        if training.ist_deload:
            continue
        iso_year, iso_week, _ = training.datum.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weekly[key] += calc_volume(training.arbeitssaetze_list, user_kg)
    labels = sorted(weekly.keys())[-12:]
    return labels, [round(weekly[k], 1) for k in labels]


_DEFAULT_RPE = 7.0  # Fallback für Sätze ohne RPE-Bewertung (moderate Anstrengung)


def _calc_muscle_balance(trainings, user=None) -> tuple[list, list, list, dict]:
    """Return (sorted_items, mg_labels, mg_data, stats_by_code) for RPE-weighted muscle balance.

    Sätze ohne RPE-Bewertung werden mit einem Fallback-RPE von 7.0 gewichtet
    (moderate Anstrengung). Sätze ohne Wiederholungen werden weiterhin ignoriert.

    Phase 14.3: Tonnage für KOERPERGEWICHT-Übungen nutzt effektives Gewicht
    (Körpergewicht × Faktor ± Zusatzgewicht) statt nur Zusatzgewicht.
    """
    user_kg = _get_user_koerpergewicht(user) if user else 80.0
    stats: dict[str, dict] = {}
    stats_code: dict[str, float] = {}
    for training in trainings:
        if training.ist_deload:
            continue
        for satz in training.arbeitssaetze_list:
            if not satz.wiederholungen:
                continue
            rpe = float(satz.rpe) if satz.rpe else _DEFAULT_RPE
            mg_display = satz.uebung.get_muskelgruppe_display()
            mg_code = satz.uebung.muskelgruppe
            eff_wdh = satz.wiederholungen * (rpe / 10.0)
            # Phase 14.3: Tonnage mit effektivem Gewicht für KG-Übungen
            raw_gewicht = float(satz.gewicht) if satz.gewicht else 0.0
            if satz.uebung.gewichts_typ == "KOERPERGEWICHT":
                faktor = getattr(satz.uebung, "koerpergewicht_faktor", 1.0) or 1.0
                richtung = getattr(satz.uebung, "gewichts_richtung", "ZUSATZ") or "ZUSATZ"
                basis = user_kg * faktor
                if richtung == "GEGEN":
                    tonnage = max(0.0, basis - raw_gewicht) * satz.wiederholungen
                else:
                    tonnage = (basis + raw_gewicht) * satz.wiederholungen
            else:
                tonnage = raw_gewicht * satz.wiederholungen
            if mg_display not in stats:
                stats[mg_display] = {"saetze": 0, "volumen": 0.0, "tonnage": 0.0}
            stats[mg_display]["saetze"] += 1
            stats[mg_display]["volumen"] += eff_wdh
            stats[mg_display]["tonnage"] += tonnage
            stats_code[mg_code] = stats_code.get(mg_code, 0.0) + eff_wdh
    sorted_items = sorted(stats.items(), key=lambda x: x[1]["volumen"], reverse=True)
    mg_labels = [mg[0] for mg in sorted_items]
    mg_data = [round(mg[1]["volumen"], 1) for mg in sorted_items]
    return sorted_items, mg_labels, mg_data, stats_code


def _build_svg_muscle_data(stats_code: dict) -> dict:
    """Map muscle group codes → SVG-element intensities (0.0–1.0)."""
    max_vol = max(stats_code.values()) if stats_code else 1
    intensity = {code: round(vol / max_vol, 2) for code, vol in stats_code.items()}
    svg_data: dict[str, float] = {}
    for code, intens in intensity.items():
        for svg_id in _MUSCLE_MAPPING.get(code, []):
            svg_data[svg_id] = min(1.0, svg_data.get(svg_id, 0.0) + intens)
    return svg_data


def _detect_volume_warnings(
    weekly_labels: list, weekly_data: list, aktuelle_kw: str | None = None
) -> list[dict]:
    """Flag weeks with >20 % volume spike or >30 % volume drop vs. prior week.

    Die laufende (noch nicht abgeschlossene) Woche wird grundsätzlich nicht
    bewertet – ein Vergleich von z.B. 2 Trainingstagen gegen eine volle Woche
    liefert irreführende Ergebnisse. Stattdessen wird sie als 'laufend' markiert.
    """
    warnings: list[dict] = []
    for i in range(1, len(weekly_data)):
        label = weekly_labels[i]
        # Laufende Woche: neutralen Hinweis statt Warnung
        if aktuelle_kw and label == aktuelle_kw:
            warnings.append(
                {
                    "week": label,
                    "volume": round(weekly_data[i], 1),
                    "type": "laufend",
                }
            )
            continue
        prev = weekly_data[i - 1]
        if prev <= 0:
            continue
        change = ((weekly_data[i] - prev) / prev) * 100
        if change > 20:
            warnings.append(
                {
                    "week": label,
                    "increase": round(change, 1),
                    "volume": round(weekly_data[i], 1),
                    "type": "spike",
                }
            )
        elif change < -30:
            warnings.append(
                {
                    "week": label,
                    "decrease": abs(round(change, 1)),
                    "volume": round(weekly_data[i], 1),
                    "type": "drop",
                }
            )
    return warnings


def _build_90day_heatmap(trainings, heute) -> list[dict]:
    """Return per-day training count for the last 90 days (as list of {date, count} dicts)."""
    start = heute - timedelta(days=89)
    counts: dict[str, int] = {}
    for t in trainings.filter(datum__gte=start):
        key = t.datum.date().isoformat()
        counts[key] = counts.get(key, 0) + 1
    result = []
    d = start
    while d <= heute:
        result.append({"date": d.isoformat(), "count": counts.get(d.isoformat(), 0)})
        d += timedelta(days=1)
    return result


def _calc_muscle_soll_bereiche(stats_code: dict, user) -> list[dict]:
    """Calculate target volume ranges per muscle group for 21.1 overlay.

    Returns list of dicts with: muskelgruppe (display), code, saetze (actual),
    soll_min, soll_max, status ('ok', 'unter', 'ueber').
    """
    from ..utils.periodization import MUSKELGRUPPEN_GROESSE, get_volumen_schwellenwerte

    active_block = _get_active_trainingsblock(user)
    block_typ = active_block.typ if active_block else None

    # stats_code has mg_code -> eff_wdh, but we need set counts per mg
    # We'll count actual sets from DB for the last 30 days
    heute = timezone.now()
    dreissig_tage = heute - timedelta(days=30)
    muscle_counts = (
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=dreissig_tage,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values("uebung__muskelgruppe")
        .annotate(count=Count("id"))
    )
    counts = {r["uebung__muskelgruppe"]: r["count"] for r in muscle_counts}

    mg_display_map = dict(MUSKELGRUPPEN)
    result = []
    for mg_code, groesse in MUSKELGRUPPEN_GROESSE.items():
        if groesse == "spezial":
            continue
        schwelle = get_volumen_schwellenwerte(mg_code, block_typ)
        if not schwelle:
            continue
        saetze = counts.get(mg_code, 0)
        soll_min, soll_max = schwelle
        if saetze < soll_min:
            status = "unter"
        elif saetze > soll_max:
            status = "ueber"
        else:
            status = "ok"
        result.append(
            {
                "muskelgruppe": mg_display_map.get(mg_code, mg_code),
                "code": mg_code,
                "saetze": saetze,
                "soll_min": soll_min,
                "soll_max": soll_max,
                "status": status,
            }
        )
    result.sort(key=lambda x: x["saetze"], reverse=True)
    return result


def _calc_push_pull_ratio(user) -> dict | None:
    """Calculate push/pull ratio for current month (21.2).

    Returns dict with: push, pull, ratio, farbe, status_text.
    """
    heute = timezone.now()
    dreissig_tage = heute - timedelta(days=30)
    muscle_counts = (
        Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=dreissig_tage,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values("uebung__muskelgruppe")
        .annotate(count=Count("id"))
    )
    counts = {r["uebung__muskelgruppe"]: r["count"] for r in muscle_counts}
    push = sum(counts.get(mg, 0) for mg in _PUSH_MUSCLES)
    pull = sum(counts.get(mg, 0) for mg in _PULL_MUSCLES)

    if push == 0 and pull == 0:
        return None

    ratio = round(push / pull, 2) if pull > 0 else (99.0 if push > 0 else 0.0)
    if ratio <= 1.3:
        farbe = "success"
        status_text = "Ausgeglichen"
    elif ratio <= 1.5:
        farbe = "warning"
        status_text = "Leicht Push-lastig"
    else:
        farbe = "danger"
        status_text = "Push-Dominanz"

    return {
        "push": push,
        "pull": pull,
        "ratio": ratio,
        "farbe": farbe,
        "status_text": status_text,
    }


def _calc_plateau_live(user) -> list[dict]:
    """Calculate plateau data for top-5 favorite exercises (21.3).

    Returns list of dicts with: uebung, tage_seit_pr, status, farbe, letzter_pr_datum.
    Uses Satz.is_pr field for PR detection.
    """
    heute = timezone.now()

    # Top 5 exercises by set count
    top_uebungen = (
        Satz.objects.filter(
            einheit__user=user,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .values("uebung__bezeichnung", "uebung__id")
        .annotate(anzahl=Count("id"))
        .order_by("-anzahl")[:5]
    )

    result = []
    for uebung in top_uebungen:
        uebung_name = uebung["uebung__bezeichnung"]
        uebung_id = uebung["uebung__id"]

        # Find last PR via is_pr flag first, fallback to max weight
        letzter_pr_satz = (
            Satz.objects.filter(
                einheit__user=user,
                uebung_id=uebung_id,
                is_pr=True,
            )
            .select_related("einheit")
            .order_by("-einheit__datum")
            .first()
        )

        if not letzter_pr_satz:
            # Fallback: find the set with highest estimated 1RM
            alle_saetze = Satz.objects.filter(
                einheit__user=user,
                uebung_id=uebung_id,
                ist_aufwaermsatz=False,
                gewicht__isnull=False,
            ).select_related("einheit")
            best_1rm = 0
            best_satz = None
            for satz in alle_saetze:
                wdh = satz.wiederholungen or 1
                est = float(satz.gewicht) * (1 + wdh / 30.0)
                if est > best_1rm:
                    best_1rm = est
                    best_satz = satz
            letzter_pr_satz = best_satz

        if not letzter_pr_satz:
            continue

        pr_datum = letzter_pr_satz.einheit.datum
        tage_seit_pr = (heute.date() - pr_datum.date()).days

        if tage_seit_pr <= 14:
            status = "Kürzlich"
            farbe = "success"
        elif tage_seit_pr <= 42:
            status = "Stagnierend"
            farbe = "warning"
        else:
            status = "Lange kein PR"
            farbe = "danger"

        result.append(
            {
                "uebung": uebung_name,
                "tage_seit_pr": tage_seit_pr,
                "status": status,
                "farbe": farbe,
                "letzter_pr_datum": pr_datum.strftime("%d.%m.%Y"),
            }
        )

    return result


def _calc_kraftstandards_live(user) -> list[dict]:
    """Calculate 1RM strength standards for top exercises (21.4).

    Returns list of dicts with: uebung, geschaetzter_1rm, level, level_label,
    naechstes_level, prozent, farbe, diff_kg.
    """
    user_gewicht = _get_user_koerpergewicht(user)

    top_uebungen = (
        Satz.objects.filter(
            einheit__user=user,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
            gewicht__isnull=False,
        )
        .values("uebung__bezeichnung", "uebung__id")
        .annotate(anzahl=Count("id"))
        .order_by("-anzahl")[:10]
    )

    result = []
    for uebung in top_uebungen:
        uebung_name = uebung["uebung__bezeichnung"]
        uebung_id = uebung["uebung__id"]

        try:
            uebung_obj = Uebung.objects.get(id=uebung_id)
        except Uebung.DoesNotExist:
            continue

        if not uebung_obj.standard_beginner:
            continue

        # Calculate best 1RM
        saetze = Satz.objects.filter(
            einheit__user=user,
            uebung_id=uebung_id,
            ist_aufwaermsatz=False,
            gewicht__isnull=False,
        )
        beste_1rm = 0
        for satz in saetze:
            wdh = satz.wiederholungen or 1
            est = float(satz.gewicht) * (1 + wdh / 30.0)
            if est > beste_1rm:
                beste_1rm = est

        if beste_1rm == 0:
            continue

        # Allometric scaling
        scaling_factor = (float(user_gewicht) / 80.0) ** (2 / 3)
        standards = {
            "beginner": round(float(uebung_obj.standard_beginner) * scaling_factor, 1),
            "intermediate": round(float(uebung_obj.standard_intermediate) * scaling_factor, 1),
            "advanced": round(float(uebung_obj.standard_advanced) * scaling_factor, 1),
            "elite": round(float(uebung_obj.standard_elite) * scaling_factor, 1),
        }

        level_labels = {
            "untrainiert": "Untrainiert",
            "beginner": "Anfänger",
            "intermediate": "Fortgeschritten",
            "advanced": "Erfahren",
            "elite": "Elite",
        }
        levels_order = ["beginner", "intermediate", "advanced", "elite"]

        level = "untrainiert"
        naechstes_level = "beginner"
        prozent = (
            round((beste_1rm / standards["beginner"]) * 100, 1) if standards["beginner"] else 0
        )

        if beste_1rm >= standards["beginner"]:
            for lv in levels_order:
                if beste_1rm >= standards[lv]:
                    level = lv
                else:
                    naechstes_level = lv
                    prev_std = standards[levels_order[levels_order.index(lv) - 1]]
                    diff = standards[lv] - prev_std
                    progress = beste_1rm - prev_std
                    prozent = round((progress / diff) * 100, 1) if diff > 0 else 0
                    break
            else:
                naechstes_level = None
                prozent = 100

        diff_kg = round(standards[naechstes_level] - beste_1rm, 1) if naechstes_level else 0

        farben = {
            "untrainiert": "secondary",
            "beginner": "info",
            "intermediate": "primary",
            "advanced": "warning",
            "elite": "success",
        }

        result.append(
            {
                "uebung": uebung_name,
                "geschaetzter_1rm": round(beste_1rm, 1),
                "level": level,
                "level_label": level_labels[level],
                "naechstes_level": level_labels.get(naechstes_level, "—"),
                "prozent": min(prozent, 100),
                "farbe": farben.get(level, "secondary"),
                "diff_kg": diff_kg,
                "standards": {level_labels[k]: v for k, v in standards.items()},
            }
        )

    return result[:5]


@login_required
def training_stats(request: HttpRequest) -> HttpResponse:
    """Erweiterte Trainingsstatistiken mit Volumen-Progression und Analyse."""
    trainings = (
        Trainingseinheit.objects.filter(user=request.user)
        .prefetch_related(
            Prefetch(
                "saetze",
                queryset=Satz.objects.filter(ist_aufwaermsatz=False).select_related("uebung"),
                to_attr="arbeitssaetze_list",
            )
        )
        .order_by("datum")
    )
    if not trainings.exists():
        return render(request, "core/training_stats.html", {"no_data": True})

    user_kg = get_user_kg(request.user)
    volumen_labels, volumen_data, deload_flags = _calc_per_training_volume(trainings, user_kg)
    weekly_labels, weekly_data = _calc_weekly_volume(trainings, user_kg)
    muskelgruppen_sorted, mg_labels, mg_data, stats_code = _calc_muscle_balance(
        trainings, request.user
    )
    svg_muscle_data = _build_svg_muscle_data(stats_code)
    heute = timezone.now().date()
    deload_warnings = _detect_volume_warnings(
        weekly_labels,
        weekly_data,
        aktuelle_kw=f"{heute.isocalendar()[0]}-W{heute.isocalendar()[1]:02d}",
    )
    heatmap_data = _build_90day_heatmap(trainings, heute)

    gesamt_volumen = sum(volumen_data)
    durchschnitt = round(gesamt_volumen / len(volumen_data), 1) if volumen_data else 0
    gesamt_saetze = sum(len(t.arbeitssaetze_list) for t in trainings)

    # RPE-10 metric (Phase 9.3)
    rpe10_anteil = _get_rpe10_anteil(request.user, heute)

    # Phase 21.1: Muskelgruppen-Balance Soll-Bereich
    muscle_soll = _calc_muscle_soll_bereiche(stats_code, request.user)

    # Phase 21.2: Push/Pull-Ratio
    push_pull = _calc_push_pull_ratio(request.user)

    # Phase 21.3: Plateau-Tracking
    plateau_live = _calc_plateau_live(request.user)

    # Phase 21.4: Kraftstandards
    kraftstandards = _calc_kraftstandards_live(request.user)

    # Body stats trend data (optional – only if measurements exist)
    body_werte = KoerperWerte.objects.filter(user=request.user).order_by("datum")
    body_chart_ctx = {}
    if body_werte.exists():
        raw = _prepare_body_chart_data(body_werte)
        # Prefix keys with body_ to avoid collisions with training chart vars
        body_chart_ctx = {f"body_{k}": v for k, v in raw.items()}
        body_chart_ctx["has_body_data"] = True

    context = {
        "trainings_count": trainings.count(),
        "gesamt_saetze": gesamt_saetze,
        "gesamt_volumen": round(gesamt_volumen, 1),
        "durchschnitt_volumen": durchschnitt,
        "volumen_labels_json": json.dumps(volumen_labels),
        "volumen_data_json": json.dumps(volumen_data),
        "deload_flags_json": json.dumps(deload_flags),
        "weekly_labels_json": json.dumps(weekly_labels),
        "weekly_data_json": json.dumps(weekly_data),
        "aktuelle_kw": f"{heute.isocalendar()[0]}-W{heute.isocalendar()[1]:02d}",
        "mg_labels_json": json.dumps(mg_labels),
        "mg_data_json": json.dumps(mg_data),
        "muskelgruppen_stats": muskelgruppen_sorted,
        "heatmap_data_json": json.dumps(heatmap_data),
        "deload_warnings": deload_warnings,
        "svg_muscle_data_json": json.dumps(svg_muscle_data),
        "rpe10_anteil": rpe10_anteil,
        # Phase 21
        "muscle_soll_json": json.dumps(muscle_soll),
        "push_pull": push_pull,
        "push_pull_json": json.dumps(push_pull),
        "plateau_live": plateau_live,
        "kraftstandards": kraftstandards,
        **body_chart_ctx,
    }
    return render(request, "core/training_stats.html", context)
