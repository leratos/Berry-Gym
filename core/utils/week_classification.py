"""Wochen-Klassifikation und Volumen-Übersicht für Dashboard und PDF.

Phase 24.1c: Aus ``core/export/stats_collector.py`` herausgezogen, weil die
Helper nicht export-spezifisch sind und auch vom Dashboard
(``core/views/training_stats.py``) sowie indirekt von
``calculate_fatigue_index`` benötigt werden. Eine gemeinsame Quelle stellt
sicher, dass PDF und Dashboard dieselbe Diagnose-Logik anwenden – vorher
hatte das Dashboard eine parallele Inline-Klassifikation, die laufende
Wochen fälschlich als „Echte Regression" werten konnte.

Öffentliche API (von Konsumenten genutzt):

- :func:`build_weekly_volume_overview` – baut die einheitliche
  ``weeks: list[dict]``-Struktur inkl. Diagnose. Wird vom PDF-Pfad
  (``stats_collector.collect_pdf_stats``) und vom Dashboard
  (``training_stats``-View) verwendet.
- :func:`select_comparable_weeks` – filtert vergleichbare Wochen für
  Trend-Vergleiche (genutzt zusätzlich von
  ``advanced_stats.calculate_fatigue_index``).
"""

from collections import defaultdict
from datetime import date

from django.utils import timezone

from core.helpers.volume import effective_weight
from core.utils.advanced_stats import (
    DELOAD_WEEK_MAJORITY_PCT,
    EFFECTIVE_VOLUME_RPE_MAX,
    EFFECTIVE_VOLUME_RPE_MIN,
    diagnose_volume_trend,
)


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


def select_comparable_weeks(weeks: list[dict]) -> list[dict]:
    """Phase 24.1 helper: return the comparable weeks from a weekly-volume list.

    Comparable = not running, not deload-majority, not skip (zero volume),
    AND inside the *current plan epoch*. The current plan epoch starts after
    the most recent plan-change week: anything before that boundary belongs
    to a different plan and must not be compared with weeks of the new plan.

    Walks ``weeks`` from latest to earliest, collects candidates, and stops
    as soon as a plan-change week is hit (the plan-change week itself is not
    collected, and nothing before it).

    Wird sowohl von ``_build_week_diagnose`` (Volumen-Diagnose, 24.1) als
    auch von ``calculate_fatigue_index`` (Volumen-Spike-Komponente, 24.1b)
    genutzt, damit beide denselben Klassifikator anwenden.
    """
    comparable: list[dict] = []
    for w in reversed(weeks):
        if w.get("ist_plan_wechsel"):
            # Plan-Epoch-Grenze – stop. Diese Woche und alles davor zählen nicht.
            break
        if w.get("ist_laufend") or w.get("ist_deload_majority") or w.get("volumen", 0) <= 0:
            continue
        comparable.append(w)
    comparable.reverse()
    return comparable


def _build_week_diagnose(weeks: list[dict]) -> dict | None:
    """Phase 24.1: produce trend diagnose over the last two *comparable* weeks.

    Returns an explanatory 'inconclusive' diagnose if fewer than two
    comparable weeks are available.
    """
    comparable = select_comparable_weeks(weeks)
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


def build_weekly_volume_overview(
    alle_saetze, alle_trainings=None, user_kg: float = 0.0, heute=None
) -> list[dict]:
    """Build weekly volume progression (last 12 weeks) inkl. Diagnose.

    Phase 24.1c: vorher ``collect_weekly_volume_pdf`` in
    ``core/export/stats_collector.py``. Wird jetzt sowohl vom PDF-Export
    als auch von der Dashboard-View (Statistik-Volumen-Chart) verwendet,
    damit die Diagnose-Logik nicht mehr doppelt existiert.

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
