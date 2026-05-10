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


_PUSH_PULL_SHORT_LABEL = {
    "BRUST": "Brust",
    "SCHULTER_VORN": "Schulter-Vordere",
    "SCHULTER_SEIT": "Schulter-Seitliche",
    "SCHULTER_HINT": "Schulter-Hintere",
    "TRIZEPS": "Trizeps",
    "BIZEPS": "Bizeps",
    "RUECKEN_LAT": "Rücken-Lat",
    "RUECKEN_TRAPEZ": "Trapez",
    "RUECKEN_OBERER": "oberer Rücken",
    "RUECKEN_UNTEN": "unterer Rücken",
}


def _muscles_with_status(
    muskelgruppen_stats: list[dict], group_keys: list[str], status: str
) -> list[dict]:
    """Filter muskelgruppen_stats to entries inside group_keys with the given status."""
    return [mg for mg in muskelgruppen_stats if mg["key"] in group_keys and mg["status"] == status]


def _format_short_labels(stats_list: list[dict]) -> str:
    """Render a comma-separated list of short muscle labels for inline use."""
    return ", ".join(_PUSH_PULL_SHORT_LABEL.get(mg["key"], mg["name"]) for mg in stats_list)


def _build_context_recommendation(
    bewertung: str, ratio: float, push_over: list[dict], pull_over: list[dict]
) -> tuple[str, bool]:
    """Phase 24.2: condition the push/pull recommendation on the overtraining
    status of the participating muscles.

    Returns ``(empfehlung_text, context_override)`` where ``context_override``
    is True when the muscle-status context flipped the math-only recommendation.
    """
    if bewertung == "Pull-betont (gut)":
        if pull_over:
            return (
                f"Ratio {ratio}:1 – Pull-Volumen bereits hoch "
                f"({_format_short_labels(pull_over)} im Übertraining-Bereich). "
                f"Push ergänzen statt Pull weiter aufbauen.",
                True,
            )
        return (
            f"Ratio {ratio}:1 – Pull überwiegt leicht. Das ist positiv für "
            f"Schultergesundheit und Haltung.",
            False,
        )

    if bewertung == "Leicht Push-betont":
        if push_over:
            return (
                f"Ratio {ratio}:1 – Push-Volumen bereits hoch "
                f"({_format_short_labels(push_over)} im Übertraining-Bereich). "
                f"Pull aufstocken, um die Imbalance zu adressieren.",
                True,
            )
        return (
            f"Ratio {ratio}:1 – Leicht Push-betont, aber noch im tolerierbaren Bereich. "
            f"Mittelfristig mehr Pull-Übungen einbauen.",
            False,
        )

    if bewertung == "Zu viel Push":
        if pull_over:
            return (
                f"Ratio {ratio}:1 – Push überwiegt deutlich, gleichzeitig sind Pull-Muskeln "
                f"({_format_short_labels(pull_over)}) im Übertraining-Bereich. "
                f"Push-Volumen senken und Belastung auf der Pull-Seite (Frequenz/Intensität) "
                f"prüfen, statt mehr Pull aufzustocken.",
                True,
            )
        return (
            f"Ratio {ratio}:1 – Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!",
            False,
        )

    if bewertung == "Ausgewogen":
        warnings = []
        if push_over:
            warnings.append(f"Push: {_format_short_labels(push_over)} im Übertraining-Bereich")
        if pull_over:
            warnings.append(f"Pull: {_format_short_labels(pull_over)} im Übertraining-Bereich")
        if warnings:
            return (
                "Push/Pull mengenmäßig ausgeglichen, aber "
                + " und ".join(warnings)
                + ". Volumen pro Muskelgruppe einzeln prüfen.",
                True,
            )
        return ("Perfekt! Push/Pull-Verhältnis ist ausgeglichen.", False)

    return (f"Ratio {ratio}:1.", False)


def collect_push_pull(muskelgruppen_stats: list[dict]) -> dict:
    """Compute push/pull balance and return analysis dict.

    Phase 24.2: the recommendation text now consults the per-muscle
    overtraining status (from ``muskelgruppen_stats``) and inverts the
    math-only verdict when the side that the math wants to praise or
    reinforce is already overtrained. ``context_override`` flags this case.
    """
    push = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in PUSH_GROUPS)
    pull = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in PULL_GROUPS)

    push_over = _muscles_with_status(muskelgruppen_stats, PUSH_GROUPS, "uebertrainiert")
    pull_over = _muscles_with_status(muskelgruppen_stats, PULL_GROUPS, "uebertrainiert")

    if push == 0 and pull == 0:
        ratio, bewertung, empfehlung, override = (
            0,
            "Keine Daten",
            "Beginne mit ausgewogenem Push- und Pull-Training für optimale Muskelentwicklung.",
            False,
        )
    elif pull > 0:
        ratio = round(push / pull, 2)
        if 0.8 <= ratio <= 1.2:
            bewertung = "Ausgewogen"
        elif ratio > 2.0:
            bewertung = "Zu viel Push"
        elif ratio > 1.2:
            bewertung = "Leicht Push-betont"
        else:
            bewertung = "Pull-betont (gut)"
        empfehlung, override = _build_context_recommendation(bewertung, ratio, push_over, pull_over)
    else:
        ratio, bewertung, override = 0, "Nur Push", False
        if push_over:
            empfehlung = (
                f"Push überwiegt komplett und Push-Muskeln "
                f"({_format_short_labels(push_over)}) zeigen Übertraining-Status. "
                f"Pull-Training einführen UND Push-Volumen prüfen."
            )
            override = True
        else:
            empfehlung = "Füge Pull-Training (Rücken, Bizeps) hinzu für ausgeglichene Entwicklung!"

    return {
        "push_saetze": push,
        "pull_saetze": pull,
        "ratio": ratio,
        "bewertung": bewertung,
        "empfehlung": empfehlung,
        "push_overtrained": [_PUSH_PULL_SHORT_LABEL.get(mg["key"], mg["name"]) for mg in push_over],
        "pull_overtrained": [_PUSH_PULL_SHORT_LABEL.get(mg["key"], mg["name"]) for mg in pull_over],
        "context_override": override,
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


def _aggregate_weekly_volume(saetze_qs, user_kg: float) -> tuple[dict, dict]:
    """Compute (weekly_volume, weekly_effective) per ISO-week-key from a Satz queryset."""
    weekly_volume: dict[str, float] = defaultdict(float)
    weekly_effective: dict[str, float] = defaultdict(float)
    for satz in saetze_qs:
        if satz.gewicht is None or not satz.wiederholungen:
            continue
        iso_year, iso_week, _ = satz.einheit.datum.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        tonnage = effective_weight(satz, user_kg) * satz.wiederholungen
        weekly_volume[week_key] += tonnage
        if (
            satz.rpe is not None
            and EFFECTIVE_VOLUME_RPE_MIN <= float(satz.rpe) <= EFFECTIVE_VOLUME_RPE_MAX
        ):
            weekly_effective[week_key] += tonnage
    return weekly_volume, weekly_effective


def _classify_weeks_from_sessions(alle_trainings) -> tuple[set, set, dict]:
    """Return (deload_weeks, deload_majority_weeks, plans_per_week) from sessions."""
    deload_weeks: set[str] = set()
    deload_majority_weeks: set[str] = set()
    plans_per_week: dict[str, set] = defaultdict(set)
    if alle_trainings is None:
        return deload_weeks, deload_majority_weeks, plans_per_week
    sessions_per_week: dict[str, dict] = defaultdict(lambda: {"total": 0, "deload": 0})
    for t in alle_trainings.all():
        iso_year, iso_week, _ = t.datum.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        sessions_per_week[key]["total"] += 1
        if t.ist_deload:
            sessions_per_week[key]["deload"] += 1
            deload_weeks.add(key)
        if t.plan_id is not None:
            plans_per_week[key].add(t.plan_id)
    for key, counts in sessions_per_week.items():
        if (
            counts["total"]
            and (counts["deload"] / counts["total"]) * 100 >= DELOAD_WEEK_MAJORITY_PCT
        ):
            deload_majority_weeks.add(key)
    return deload_weeks, deload_majority_weeks, plans_per_week


def _fill_iso_week_range(weekly_volume: dict) -> list[str]:
    """Fill all ISO weeks between first and last seen week, return last 12."""
    from datetime import date

    all_keys = sorted(weekly_volume.keys())
    first_key, last_key = all_keys[0], all_keys[-1]
    fy, fw = int(first_key.split("-W")[0]), int(first_key.split("-W")[1])
    ly, lw = int(last_key.split("-W")[0]), int(last_key.split("-W")[1])
    filled: list[str] = []
    y, w = fy, fw
    while (y, w) <= (ly, lw):
        filled.append(f"{y}-W{w:02d}")
        w += 1
        max_week = date(y, 12, 28).isocalendar()[1]
        if w > max_week:
            w = 1
            y += 1
    return filled[-12:]


def _build_week_diagnose(weeks: list[dict]) -> dict | None:
    """Phase 24.1: produce trend diagnose over the last two *comparable* weeks.

    Comparable = not running, not deload-majority, not skip (zero volume),
    AND inside the *current plan epoch*. The current plan epoch starts after
    the most recent plan-change week: anything before that boundary belongs
    to a different plan and must not be compared with weeks of the new plan.

    Implementation: walk weeks from latest to earliest, collect candidates,
    stop as soon as we hit a plan-change week (which itself is not collected,
    and neither is anything before it).

    Returns an explanatory 'inconclusive' diagnose if fewer than two
    comparable weeks are available.
    """
    comparable: list[dict] = []
    for w in reversed(weeks):
        if w["ist_plan_wechsel"]:
            # Plan-Epoch-Grenze – stop. Diese Woche und alles davor zählen nicht.
            break
        if w["ist_laufend"] or w["ist_deload_majority"] or w["volumen"] <= 0:
            continue
        comparable.append(w)
    comparable.reverse()
    if len(comparable) >= 2:
        prev = comparable[-2]
        curr = comparable[-1]
        diag = diagnose_volume_trend(
            prev_tonnage=prev["volumen"],
            curr_tonnage=curr["volumen"],
            prev_effective=prev["effektives_volumen"],
            curr_effective=curr["effektives_volumen"],
            is_deload_week=False,
        )
        if diag is not None:
            diag["compared_weeks"] = (prev["woche"], curr["woche"])
        return diag

    last_week = weeks[-1]
    reasons = []
    if last_week["ist_laufend"]:
        reasons.append("Diese Woche läuft noch")
    if last_week["ist_deload_majority"]:
        reasons.append("Deload-Woche")
    if last_week["ist_plan_wechsel"]:
        reasons.append("Trainingsplan-Wechsel")
    reason_text = ", ".join(reasons) if reasons else "Zu wenig vergleichbare Wochen"
    return {
        "key": "inconclusive",
        "label": "Trend-Bewertung pausiert",
        "severity": "info",
        "message": (
            f"{reason_text}: Volumen-Trend wird erst wieder bewertet, sobald "
            "zwei aufeinanderfolgende Wochen ohne Deload, Plan-Wechsel und "
            "ohne laufende Woche vorliegen."
        ),
        "tonnage_trend": "",
        "effective_trend": "",
        "suppressed_due_to_deload": False,
        "compared_weeks": None,
    }


def collect_weekly_volume_pdf(
    alle_saetze, alle_trainings=None, user_kg: float = 0.0, heute=None
) -> list[dict]:
    """Build weekly volume progression (last 12 weeks) for PDF report.

    Includes deload weeks with their actual (reduced) volume, marked via
    'ist_deload' flag.  Fills gaps between calendar weeks with 0.

    Phase 23.2: Zusätzliche zweite Reihe ``effektives_volumen`` – nur Sätze
    mit RPE 7–9 zählen (ohne Junk-Volume <7 und Failure-Volume =10). Pro
    Woche wird zudem ``ist_deload_majority`` gesetzt (≥50 % der Sessions
    in dieser Woche sind ``ist_deload=True``), als Hybrid-Block-Typ-Awareness
    für die Diagnose-Tabelle.

    Phase 24.1: Diagnose vergleicht ausschließlich die letzten zwei
    *vergleichbaren* Wochen (nicht laufend, nicht Deload-Mehrheit, nicht
    Plan-Wechsel-Woche). Plan-Wechsel-Wochen werden über die Plan-IDs der
    Sessions ermittelt und als ``ist_plan_wechsel`` markiert. Wenn keine
    zwei vergleichbaren Wochen verfügbar sind, wird statt einer irreführenden
    Stabil-/Wachstums-Diagnose ein klarer Hinweis ``Trend-Bewertung pausiert``
    erzeugt.
    """
    saetze_qs = alle_saetze.filter(ist_aufwaermsatz=False).select_related("uebung")
    weekly_volume, weekly_effective = _aggregate_weekly_volume(saetze_qs, user_kg)
    if not weekly_volume:
        return []

    deload_weeks, deload_majority_weeks, plans_per_week = _classify_weeks_from_sessions(
        alle_trainings
    )

    if heute is None:
        heute = timezone.now()
    iy_now, iw_now, _ = heute.isocalendar()
    aktuelle_woche_key = f"{iy_now}-W{iw_now:02d}"

    labels = _fill_iso_week_range(weekly_volume)
    weeks: list[dict] = []
    prev_plans: set | None = None
    for label in labels:
        cur_plans = plans_per_week.get(label, set())
        ist_plan_wechsel = bool(
            prev_plans is not None and cur_plans and prev_plans and cur_plans != prev_plans
        )
        weeks.append(
            {
                "woche": f"KW{label.split('-W')[1]}",
                "_iso_key": label,
                "volumen": round(weekly_volume.get(label, 0), 0),
                "effektives_volumen": round(weekly_effective.get(label, 0), 0),
                "ist_deload": label in deload_weeks,
                "ist_deload_majority": label in deload_majority_weeks,
                "ist_laufend": label == aktuelle_woche_key,
                "ist_plan_wechsel": ist_plan_wechsel,
            }
        )
        if cur_plans:
            prev_plans = cur_plans

    if len(weeks) >= 2:
        weeks[-1]["diagnose"] = _build_week_diagnose(weeks)
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
    volumen_wochen = collect_weekly_volume_pdf(
        alle_saetze_inkl_deload, alle_trainings, user_kg, heute=heute
    )
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
