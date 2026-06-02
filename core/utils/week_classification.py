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
from datetime import date, timedelta

from django.utils import timezone

from core.helpers.volume import effective_weight
from core.utils.advanced_stats import (
    DELOAD_WEEK_MAJORITY_PCT,
    EFFECTIVE_VOLUME_RPE_MAX,
    EFFECTIVE_VOLUME_RPE_MIN,
    PAUSE_BOUNDARY_MIN_DAYS,
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


def _iso_key(d: date) -> str:
    """ISO-Wochen-Key 'YYYY-Www' für ein Datum."""
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _clamp_pausen(pausen, heute_date: date) -> list[tuple[date, date, int]]:
    """Analyse-Repräsentation der Pausen: ``[(start, end_clamped, dauer_tage), ...]``.

    Phase 32.3 (§32.3.2, ⑦+⑰): jede Pause wird auf ``heute`` geclamped –
    ``end_clamped = min(end_datum or heute, heute)``. Das gilt **nicht nur** für
    offene Pausen (``end_datum=None``), sondern auch für geschlossene
    Zukunfts-Ranges; sonst emittiert die Wochen-union Zukunfts-Null-Wochen.
    Vollständig in der Zukunft liegende Pausen (``start > heute``) werden
    verworfen. ``dauer_tage`` ist **inklusiv** ((end-start).days + 1).
    """
    result: list[tuple[date, date, int]] = []
    if not pausen:
        return result
    for p in pausen:
        start = p.start_datum
        if start is None or start > heute_date:
            continue
        end = p.end_datum if p.end_datum is not None else heute_date
        end = min(end, heute_date)
        if end < start:
            continue
        dauer_tage = (end - start).days + 1
        result.append((start, end, dauer_tage))
    return result


def _pausen_wochen_keys(pausen_clamped: list[tuple[date, date, int]]) -> set[str]:
    """Menge aller ISO-Wochen-Keys, die von einer geclampten Pause berührt werden.

    Schreitet vom Montag der Start-Woche wochenweise bis ``end`` – trifft so jede
    berührte ISO-Woche genau einmal (keine ausgelassene Woche, kein Tag-für-Tag).
    """
    keys: set[str] = set()
    for start, end, _ in pausen_clamped:
        montag = start - timedelta(days=start.weekday())  # weekday(): Mo=0
        cur = montag
        while cur <= end:
            keys.add(_iso_key(cur))
            cur += timedelta(days=7)
    return keys


def _classify_week_pause(
    iso_key: str,
    pausen_clamped: list[tuple[date, date, int]],
    hat_sessions: bool,
    min_boundary_days: int = PAUSE_BOUNDARY_MIN_DAYS,
) -> tuple[bool, bool, bool]:
    """Zwei orthogonale Achsen für eine ISO-Woche (§32.3.1, ⑤/⑥/⑭/⑯).

    Achse 1 (Label/Abdeckung):
    - ``ist_ausfall``  ⇔ eine Pause deckt die **komplette** ISO-Woche (Mo–So) ab
      **und** die Woche hat **0 Sessions**. Impliziert ``ist_pausen_grenze``.
    - ``teilweise_ausfall`` ⇔ Woche überlappt eine Pause, ist aber **nicht**
      ``ist_ausfall``. Deckt damit partiellen Overlap (mit/ohne Sessions) **und**
      Voll-Overlap *mit* trotzdem geloggter Session ab (⑯).

    Achse 2 (Dauer/Grenze):
    - ``ist_pausen_grenze`` ⇔ Woche überlappt eine Pause **≥ min_boundary_days**
      – **unabhängig** von Abdeckung **und** Session-Zahl (⑭: NICHT auf 0-Sessions
      gaten).
    """
    iso_year, iso_week = int(iso_key.split("-W")[0]), int(iso_key.split("-W")[1])
    montag = date.fromisocalendar(iso_year, iso_week, 1)
    sonntag = date.fromisocalendar(iso_year, iso_week, 7)

    overlaps = False
    voll_abdeckung = False
    grenze = False
    for start, end, dauer in pausen_clamped:
        if start <= sonntag and end >= montag:  # Overlap [start,end] ∩ [Mo,So]
            overlaps = True
            if start <= montag and end >= sonntag:
                voll_abdeckung = True
            if dauer >= min_boundary_days:
                grenze = True

    ist_ausfall = voll_abdeckung and not hat_sessions
    teilweise_ausfall = overlaps and not ist_ausfall
    ist_pausen_grenze = grenze or ist_ausfall  # ist_ausfall impliziert die Grenze
    return ist_ausfall, teilweise_ausfall, ist_pausen_grenze


def _classify_weeks_from_sessions(alle_trainings) -> tuple[set, set, dict, set]:
    """Return (deload_weeks, deload_majority_weeks, routines_per_week) from sessions.

    Phase 25.8: ``routines_per_week`` maps each ISO-week-key to the set of
    *routine identities* trained that week – not raw plan IDs. A routine
    identity is the plan's ``gruppe_id`` when set (a split routine spreads its
    days over several ``Plan`` rows that share one ``gruppe_id``), otherwise
    the plan's own id (a standalone, ungrouped plan).

    Collapsing all split days of one routine onto a single key is what keeps a
    *partially logged* split week from looking like a plan change: a week with
    only ``{Push}`` logged so far and a full week with ``{Push, Pull, Legs}``
    both reduce to the same single ``gruppe_id``. See ``build_weekly_volume_overview``.
    """
    deload_weeks: set[str] = set()
    deload_majority_weeks: set[str] = set()
    routines_per_week: dict[str, set] = defaultdict(set)
    if alle_trainings is None:
        return deload_weeks, deload_majority_weeks, routines_per_week, set()
    sessions_per_week: dict[str, dict] = defaultdict(lambda: {"total": 0, "deload": 0})
    # ``select_related("plan")`` joins the routine's ``gruppe_id`` into the same
    # query – avoids an N+1 on ``t.plan`` while keeping the query count flat.
    for t in alle_trainings.select_related("plan").all():
        iso_year, iso_week, _ = t.datum.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        sessions_per_week[key]["total"] += 1
        if t.ist_deload:
            sessions_per_week[key]["deload"] += 1
            deload_weeks.add(key)
        if t.plan_id is not None:
            # gruppe_id identifies the routine across all of its split days;
            # fall back to the plan id for ungrouped standalone plans.
            routines_per_week[key].add(t.plan.gruppe_id or t.plan_id)
    for key, counts in sessions_per_week.items():
        if (
            counts["total"]
            and (counts["deload"] / counts["total"]) * 100 >= DELOAD_WEEK_MAJORITY_PCT
        ):
            deload_majority_weeks.add(key)
    # ``sessions_per_week`` enthält jeden Key mit ≥1 Session – die Quelle für
    # ``hat_sessions`` in der Pausen-Klassifikation (ist_ausfall nur bei 0 Sessions).
    sessions_week_keys = set(sessions_per_week.keys())
    return deload_weeks, deload_majority_weeks, routines_per_week, sessions_week_keys


def _fill_iso_week_range(seed_keys) -> list[str]:
    """Fill all ISO weeks between first and last seed week, return last 12.

    Phase 32.3: ``seed_keys`` ist die **union** aus Wochen-mit-Volumen UND
    Wochen-mit-Pausen-Overlap (auf heute geclamped). Dadurch erscheint eine
    komplett leere Krankheitswoche als gelabelte Lücke im Chart statt zu fehlen.
    """
    all_keys = sorted(seed_keys)
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
        if w.get("ist_plan_wechsel") or w.get("ist_pausen_grenze"):
            # Epoch-Grenze (Plan-Wechsel ODER dokumentierte Pause ≥ Mindestdauer,
            # Phase 32.4, ⑥): stop. Diese Woche und alles davor zählen nicht – so
            # überquert KEIN Vergleich die Pause (kein falscher Comeback-Spike).
            break
        if (
            w.get("ist_laufend")
            or w.get("ist_deload_majority")
            or w.get("ist_ausfall")
            or w.get("teilweise_ausfall")
            or w.get("volumen", 0) <= 0
        ):
            # Kurze teilweise_ausfall-Wochen (ohne Grenz-Flag): Volumen bleibt
            # erhalten, aber kein Trend-Anker (§32.3.3) – nur continue, kein break.
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
    if (
        last_week.get("ist_pausen_grenze")
        or last_week.get("ist_ausfall")
        or last_week.get("teilweise_ausfall")
    ):
        reasons.append("Trainingspause")
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
    alle_saetze, alle_trainings=None, user_kg: float = 0.0, heute=None, pausen=None
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
    Plan-Wechsel-Woche). Wenn keine zwei vergleichbaren Wochen verfügbar
    sind, wird statt einer irreführenden Stabil-/Wachstums-Diagnose ein
    klarer Hinweis ``Trend-Bewertung pausiert`` erzeugt.

    Phase 25.8: Plan-Wechsel-Wochen werden über die *Routine-Identität*
    (``Plan.gruppe_id``, Fallback ``plan_id``) aufeinanderfolgender Wochen
    ermittelt und als ``ist_plan_wechsel`` markiert – nicht mehr über rohe
    Plan-IDs. Sonst sieht jede noch nicht vollständig geloggte Splitwoche
    (z.B. erst Push geloggt, Pull/Legs offen) wie ein Plan-Wechsel aus.

    Phase 32.3: ``pausen`` (Iterable von ``TrainingsPause``) macht die Übersicht
    pause-bewusst. Die Wochenliste wird aus ``union(Wochen-mit-Sessions,
    Wochen-mit-Pausen-Overlap)`` emittiert (jede Pause auf ``heute`` geclamped),
    damit eine komplett leere Krankheitswoche als gelabelte Lücke erscheint statt
    zu fehlen (#481). Jede Woche erhält ``ist_ausfall`` / ``teilweise_ausfall``
    (Abdeckung) und ``ist_pausen_grenze`` (Dauer-Grenze) – siehe
    ``_classify_week_pause``. Ohne ``pausen`` ist das Verhalten unverändert.
    """
    # ``einheit`` muss mit-gejoined werden, weil ``_aggregate_weekly_volume``
    # pro Satz auf ``satz.einheit.datum`` zugreift – sonst eine Query pro Satz.
    saetze_qs = alle_saetze.filter(ist_aufwaermsatz=False).select_related("uebung", "einheit")
    weekly_volume, weekly_effective = _aggregate_weekly_volume(saetze_qs, user_kg)
    if not weekly_volume:
        return []

    deload_weeks, deload_majority_weeks, routines_per_week, sessions_week_keys = (
        _classify_weeks_from_sessions(alle_trainings)
    )

    if heute is None:
        heute = timezone.now()
    iy_now, iw_now, _ = heute.isocalendar()
    aktuelle_woche_key = f"{iy_now}-W{iw_now:02d}"

    # Phase 32.3: Pausen auf heute clampen + ihre ISO-Wochen in die Emission-union.
    heute_date = heute.date() if hasattr(heute, "date") else heute
    pausen_clamped = _clamp_pausen(pausen, heute_date)
    seed_keys = set(weekly_volume.keys()) | _pausen_wochen_keys(pausen_clamped)

    labels = _fill_iso_week_range(seed_keys)
    weeks: list[dict] = []
    prev_routines: set | None = None
    for label in labels:
        cur_routines = routines_per_week.get(label, set())
        # Phase 25.8: a plan change is a week whose set of routine identities
        # differs from the previous routine-bearing week. Comparing routine
        # identities (gruppe_id) instead of raw plan IDs means a partially
        # logged split week – only some of the routine's split days done so
        # far – is no longer mistaken for a plan change.
        ist_plan_wechsel = bool(
            prev_routines is not None
            and cur_routines
            and prev_routines
            and cur_routines != prev_routines
        )
        ist_ausfall, teilweise_ausfall, ist_pausen_grenze = _classify_week_pause(
            label,
            pausen_clamped,
            hat_sessions=label in sessions_week_keys,
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
                "ist_ausfall": ist_ausfall,
                "teilweise_ausfall": teilweise_ausfall,
                "ist_pausen_grenze": ist_pausen_grenze,
            }
        )
        if cur_routines:
            prev_routines = cur_routines

    if len(weeks) >= 2:
        weeks[-1]["diagnose"] = _build_week_diagnose(weeks)
    return weeks
