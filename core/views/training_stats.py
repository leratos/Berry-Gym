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
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, DecimalField, F, Max, Prefetch, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    MUSKELGRUPPEN,
    CardioEinheit,
    KoerperWerte,
    Plan,
    Satz,
    Trainingseinheit,
    Uebung,
    UserProfile,
)

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


def _count_trainings_this_week(user, heute) -> int:
    """Count training sessions in the current ISO week (Mon–Sun)."""
    start_woche = _get_week_start(heute)
    return Trainingseinheit.objects.filter(user=user, datum__gte=start_woche).count()


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
    last_4_weeks = []
    for i in range(4):
        week_start = heute - timedelta(days=heute.isoweekday() - 1 + (i * 7))
        week_end = week_start + timedelta(days=7)
        result = Satz.objects.filter(
            einheit__datum__gte=week_start,
            einheit__datum__lt=week_end,
            ist_aufwaermsatz=False,
            einheit__user=user,
            einheit__ist_deload=False,
        ).aggregate(total=Sum(F("gewicht") * F("wiederholungen"), output_field=DecimalField()))
        if result["total"]:
            last_4_weeks.append(float(result["total"]))
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


def _calculate_weekly_volumes(user, heute) -> list[dict]:
    """Return volume data for the last 4 weeks."""
    weekly_volumes = []
    for i in range(4):
        week_start = _get_week_start(heute - timedelta(days=i * 7))
        week_end = week_start + timedelta(days=7)
        week_saetze = Satz.objects.filter(
            einheit__user=user,
            einheit__datum__gte=week_start,
            einheit__datum__lt=week_end,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        week_total = sum(
            float(s.gewicht) * int(s.wiederholungen)
            for s in week_saetze
            if s.gewicht and s.wiederholungen
        )
        labels = {0: "Diese Woche", 1: "Letzte Woche"}
        week_label = labels.get(i, f"Vor {i} Wochen")
        weekly_volumes.append({"label": week_label, "volume": round(week_total, 0), "week_num": i})
    return weekly_volumes


def _get_volume_spike_fatigue(weekly_volumes: list[dict]) -> tuple[int, list[str]]:
    """Return (points, warnings) for a volume spike in the last 2 weeks."""
    if len(weekly_volumes) < 2:
        return 0, []
    current_vol = weekly_volumes[0]["volume"]
    last_vol = weekly_volumes[1]["volume"]
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
    """Return (points, warnings) based on avg RPE over the last 2 weeks."""
    _, avg_rpe = _get_rpe_score(user, heute)
    if avg_rpe and avg_rpe > 8.5:
        return 30, ["Sehr hohe Trainingsintensität"]
    if avg_rpe and avg_rpe > 8:
        return 20, ["Hohe Trainingsintensität"]
    return 0, []


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
    user, heute, weekly_volumes: list[dict], gesamt_trainings: int
) -> dict:
    """Compute fatigue index and related display data. Returns a dict."""
    fatigue_index = 0
    fatigue_warnings: list[str] = []

    if gesamt_trainings >= 4:
        for pts, warns in [
            _get_volume_spike_fatigue(weekly_volumes),
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


def _get_training_heatmap(user, heute) -> str:
    """Return JSON string of training counts per day for the last 365 days."""
    start_date = heute - timedelta(days=364)
    trainings_by_date = (
        Trainingseinheit.objects.filter(user=user, datum__gte=start_date)
        .values("datum__date")
        .annotate(count=Count("id"))
    )
    heatmap = {
        entry["datum__date"].strftime("%Y-%m-%d"): entry["count"] for entry in trainings_by_date
    }
    return json.dumps(heatmap)


def _check_plateau_warnings(user, heute, favoriten) -> list[dict]:
    """Check for plateaus (no progress in top exercises over 4 weeks)."""
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
            warnings.append(
                {
                    "type": "regression",
                    "severity": "danger",
                    "exercise": ex["uebung__bezeichnung"],
                    "message": f"Leistungsabfall von {drop_percent}%",
                    "suggestion": "Prüfe Regeneration, Ernährung und Schlaf. Erwäge eine Deload-Woche.",
                    "icon": "bi-arrow-down-circle",
                    "color": "danger",
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


def _get_performance_warnings(user, heute, favoriten, gesamt_trainings: int) -> list[dict]:
    """Aggregate performance warnings (plateau, regression, stagnation), max 3."""
    if gesamt_trainings < 4:
        return []
    all_warnings = (
        _check_plateau_warnings(user, heute, favoriten)
        + _check_regression_warnings(user, heute)
        + _check_stagnation_warnings(user, heute)
    )
    priority = {"regression": 0, "plateau": 1, "stagnation": 2}
    return sorted(all_warnings, key=lambda w: priority[w["type"]])[:3]


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
        weekly_volumes = _calculate_weekly_volumes(request.user, heute)
        fatigue_data = _calculate_fatigue_index(
            request.user, heute, weekly_volumes, gesamt_trainings
        )
        motivation_quote = _get_motivation_quote(form_index, fatigue_data["fatigue_index"])
        training_heatmap_json = _get_training_heatmap(request.user, heute)
        performance_warnings = _get_performance_warnings(
            request.user, heute, favoriten, gesamt_trainings
        )
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
            **fatigue_data,
            "motivation_quote": motivation_quote,
            "training_heatmap_json": training_heatmap_json,
            "performance_warnings": performance_warnings,
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

    context = {
        "letztes_training": letztes_training,
        "letzter_koerperwert": letzter_koerperwert,
        "use_openrouter": use_openrouter,
        "offene_session": offene_session,
        "offene_sessions_anzahl": offene_sessions_anzahl,
        **computed,
    }
    _add_plan_group_context(request.user, context)
    return render(request, "core/dashboard.html", context)


@login_required
def training_list(request: HttpRequest) -> HttpResponse:
    """Zeigt eine Liste aller vergangenen Trainings."""
    # Wir holen NUR die Trainings des aktuellen Users, sortiert nach Datum (neu -> alt)
    # annotate(satz_count=Count('saetze')) zählt die Sätze für die Vorschau
    trainings = (
        Trainingseinheit.objects.filter(user=request.user)
        .annotate(satz_count=Count("saetze"))
        .prefetch_related(
            Prefetch(
                "saetze",
                queryset=Satz.objects.filter(ist_aufwaermsatz=False),
                to_attr="arbeitssaetze_list",
            )
        )
        .order_by("-datum")
    )

    # Volumen für jedes Training berechnen
    trainings_mit_volumen = []
    for training in trainings:
        arbeitssaetze = training.arbeitssaetze_list
        volumen = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)
        trainings_mit_volumen.append(
            {
                "training": training,
                "volumen": round(volumen, 1),
                "arbeitssaetze": len(arbeitssaetze),
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


def _compute_1rm_and_weight(satz, uebung, user_koerpergewicht: float = 80.0) -> tuple[float, float]:
    """Return (estimated_1rm, effective_weight) for a single set.

    Formel: Epley (1985) – weight × (1 + reps/30)
    Genauigkeit:
    - 1–6 Wdh.: gute Schätzung (±5%)
    - 7–10 Wdh.: akzeptabel (±8%)
    - > 10 Wdh.: systematische Überschätzung – Brzycki-Formel wäre dort genauer.
    Für relative Vergleiche (Progression über Zeit) ist die Formel trotzdem konsistent.

    Körpergewichts-Übungen (KOERPERGEWICHT):
        effektives_gewicht = (user_koerpergewicht * koerpergewicht_faktor) + zusatzgewicht
        Beispiel Dips (Faktor 0.70, 80kg User, 0kg Zusatz): 80 * 0.70 = 56 kg effektiv
    """
    zusatzgewicht = float(satz.gewicht)

    if uebung.gewichts_typ == "PRO_SEITE":
        effektives_gewicht = zusatzgewicht * 2
    elif uebung.gewichts_typ == "KOERPERGEWICHT":
        faktor = getattr(uebung, "koerpergewicht_faktor", 1.0) or 1.0
        effektives_gewicht = (user_koerpergewicht * faktor) + zusatzgewicht
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

    # Körpergewicht einmalig laden (für KOERPERGEWICHT-Übungen)
    user_koerpergewicht = _get_user_koerpergewicht(request.user)
    is_kg_uebung = uebung.gewichts_typ == "KOERPERGEWICHT"

    # Best 1RM per day + overall records
    history_data: dict[str, float] = {}
    wdh_history: dict[str, int] = {}  # Wdh-Verlauf für KG-Übungen
    personal_record = 0.0
    best_weight = 0.0
    best_reps = 0

    for satz in saetze:
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung, user_koerpergewicht)
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

    avg_rpe = saetze.aggregate(Avg("rpe"))["rpe__avg"]

    # Bei reinen Körpergewicht-Übungen (kein Zusatzgewicht je verwendet):
    # Wdh-Verlauf als primäre Chart-Metrik anzeigen
    show_reps_chart = (
        is_kg_uebung
        and bool(wdh_history)
        and best_weight
        == round(user_koerpergewicht * (getattr(uebung, "koerpergewicht_faktor", 1.0) or 1.0), 1)
    )

    context = {
        "uebung": uebung,
        "labels_json": json.dumps(list(history_data.keys())),
        "data_json": json.dumps(list(history_data.values())),
        "wdh_labels_json": json.dumps(list(wdh_history.keys())),
        "wdh_data_json": json.dumps(list(wdh_history.values())),
        "show_reps_chart": show_reps_chart,
        "personal_record": personal_record,
        "best_weight": best_weight,
        "best_reps": best_reps,
        "user_koerpergewicht": user_koerpergewicht,
        "avg_rpe": round(avg_rpe, 1) if avg_rpe else None,
        "rpe_trend": _calc_rpe_trend(saetze, avg_rpe),
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


def _calc_per_training_volume(trainings) -> tuple[list, list]:
    """Return (date_labels, volumes) for every training session."""
    labels: list[str] = []
    data: list[float] = []
    for training in trainings:
        arbeitssaetze = training.arbeitssaetze_list
        vol = sum(
            float(s.gewicht) * s.wiederholungen
            for s in arbeitssaetze
            if s.gewicht and s.wiederholungen
        )
        labels.append(training.datum.strftime("%d.%m"))
        data.append(round(vol, 1))
    return labels, data


def _calc_weekly_volume(trainings) -> tuple[list, list]:
    """Return (iso_week_labels, volumes) for the last 12 ISO calendar weeks."""
    weekly: defaultdict[str, float] = defaultdict(float)
    for training in trainings:
        iso_year, iso_week, _ = training.datum.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        arbeitssaetze = training.arbeitssaetze_list
        vol = sum(
            float(s.gewicht) * s.wiederholungen
            for s in arbeitssaetze
            if s.gewicht and s.wiederholungen
        )
        weekly[key] += vol
    labels = sorted(weekly.keys())[-12:]
    return labels, [round(weekly[k], 1) for k in labels]


def _calc_muscle_balance(trainings) -> tuple[list, list, list, dict]:
    """Return (sorted_items, mg_labels, mg_data, stats_by_code) for RPE-weighted muscle balance."""
    stats: dict[str, dict] = {}
    stats_code: dict[str, float] = {}
    for training in trainings:
        for satz in training.arbeitssaetze_list:
            if not satz.wiederholungen or not satz.rpe:
                continue
            mg_display = satz.uebung.get_muskelgruppe_display()
            mg_code = satz.uebung.muskelgruppe
            eff_wdh = satz.wiederholungen * (float(satz.rpe) / 10.0)
            if mg_display not in stats:
                stats[mg_display] = {"saetze": 0, "volumen": 0.0}
            stats[mg_display]["saetze"] += 1
            stats[mg_display]["volumen"] += eff_wdh
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


def _detect_volume_warnings(weekly_labels: list, weekly_data: list) -> list[dict]:
    """Flag weeks with >20 % volume spike or >30 % volume drop vs. prior week."""
    warnings: list[dict] = []
    for i in range(1, len(weekly_data)):
        prev = weekly_data[i - 1]
        if prev <= 0:
            continue
        change = ((weekly_data[i] - prev) / prev) * 100
        if change > 20:
            warnings.append(
                {
                    "week": weekly_labels[i],
                    "increase": round(change, 1),
                    "volume": round(weekly_data[i], 1),
                    "type": "spike",
                }
            )
        elif change < -30:
            warnings.append(
                {
                    "week": weekly_labels[i],
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

    volumen_labels, volumen_data = _calc_per_training_volume(trainings)
    weekly_labels, weekly_data = _calc_weekly_volume(trainings)
    muskelgruppen_sorted, mg_labels, mg_data, stats_code = _calc_muscle_balance(trainings)
    svg_muscle_data = _build_svg_muscle_data(stats_code)
    deload_warnings = _detect_volume_warnings(weekly_labels, weekly_data)
    heute = timezone.now().date()
    heatmap_data = _build_90day_heatmap(trainings, heute)

    gesamt_volumen = sum(volumen_data)
    durchschnitt = round(gesamt_volumen / len(volumen_data), 1) if volumen_data else 0

    context = {
        "trainings_count": trainings.count(),
        "gesamt_volumen": round(gesamt_volumen, 1),
        "durchschnitt_volumen": durchschnitt,
        "volumen_labels_json": json.dumps(volumen_labels),
        "volumen_data_json": json.dumps(volumen_data),
        "weekly_labels_json": json.dumps(weekly_labels),
        "weekly_data_json": json.dumps(weekly_data),
        "mg_labels_json": json.dumps(mg_labels),
        "mg_data_json": json.dumps(mg_data),
        "muskelgruppen_stats": muskelgruppen_sorted,
        "heatmap_data_json": json.dumps(heatmap_data),
        "deload_warnings": deload_warnings,
        "svg_muscle_data_json": json.dumps(svg_muscle_data),
    }
    return render(request, "core/training_stats.html", context)
