"""
Phase 11 + 13: Erweiterte KI-Plan-Validierung.

Programmatische Post-Validierungen die nach der LLM-Antwort laufen.
Die bestehende validate_plan() in llm_client.py prüft nur Pflichtfelder,
Übungs-Existenz und Intra-Session-Duplikate. Dieses Modul ergänzt:

11.1: Cross-Session-Duplikat-Check
11.2: Verbotene Kombinationen
11.3: Anatomische Pflichtgruppen
11.4: Compound-vor-Isolation Reihenfolge (Auto-Fix)
11.5: Pausenzeiten-Plausibilität (Auto-Fix)
13.1: Muskelgruppen-Überrepräsentation pro Session (Auto-Fix)
"""

from __future__ import annotations

from core.models import Uebung

# ─────────────────────────────────────────────────────────────────────────────
# Konstanten
# ─────────────────────────────────────────────────────────────────────────────

_COMPOUND_BEWEGUNGSTYPEN = {"DRUECKEN", "ZIEHEN", "BEUGEN", "HEBEN"}

_COMPOUND_REST_RANGE = (120, 180)
_ISOLATION_REST_RANGE = (60, 90)
_COMPOUND_REST_DEFAULT = 150
_ISOLATION_REST_DEFAULT = 75

# 11.2: Verbotene Kombinationen
# Vordere-Schulter-Isolation (Front Raises) nicht mit schwerem Drücken kombinieren
_FORBIDDEN_COMBINATIONS = [
    {
        "forbidden_filter": {"muskelgruppe": "SCHULTER_VORN", "bewegungstyp": "ISOLATION"},
        "conflicts_with": [
            {"muskelgruppe": "BRUST", "bewegungstyp": "DRUECKEN"},
            {"muskelgruppe": "SCHULTER_VORN", "bewegungstyp": "DRUECKEN"},
        ],
        "reason": (
            "Vordere Schulter-Isolation (z.B. Front Raises) vor/nach schwerem "
            "Drücken erhöht das Verletzungsrisiko"
        ),
    },
]

# 11.3: Anatomische Pflichtgruppen
_MIN_SCHULTER_HINT_SETS = 2
_PULL_SESSION_KEYWORDS = ("pull", "zug", "ziehen")

# 13.1: Muskelgruppen-Überrepräsentation
_MAX_SETS_PER_MUSCLE_GROUP = 7


# ─────────────────────────────────────────────────────────────────────────────
# Entry-Point
# ─────────────────────────────────────────────────────────────────────────────


def validate_plan_structure(
    plan_json: dict,
    available_exercises: list[str] | None = None,
) -> tuple[list[str], dict]:
    """Führt alle Phase-11/13-Checks aus und wendet Auto-Fixes an.

    Args:
        plan_json: Plan-Dict mit sessions[].exercises[].
                   Wird bei Auto-Fixes (11.4, 11.5, 13.1) in-place modifiziert.
        available_exercises: Optionale Liste verfügbarer Übungen für Auto-Fix 13.1.

    Returns:
        (warnings, fixes_applied):
            warnings: Liste von Hinweis-Strings.
            fixes_applied: Dict mit Zählern (order_fixed, rest_fixed, overrep_fixed).
    """
    sessions = plan_json.get("sessions", [])
    if not sessions:
        return [], {}

    # Eine einzige DB-Query für alle Übungs-Metadaten
    uebungen_map = _build_uebungen_map(plan_json)

    warnings = []
    fixes = {}

    # 11.1: Cross-Session-Duplikate
    warnings.extend(_check_cross_session_duplicates(plan_json))

    # 11.2: Verbotene Kombinationen
    warnings.extend(_check_forbidden_combinations(plan_json, uebungen_map))

    # 11.3: Anatomische Pflichtgruppen
    warnings.extend(_check_anatomical_requirements(plan_json, uebungen_map))

    # 11.4: Compound-vor-Isolation (Auto-Fix)
    order_fixed = _fix_exercise_order(plan_json, uebungen_map)
    if order_fixed > 0:
        fixes["order_fixed"] = order_fixed

    # 11.5: Pausenzeiten (Auto-Fix)
    rest_fixed = _fix_rest_times(plan_json, uebungen_map)
    if rest_fixed > 0:
        fixes["rest_fixed"] = rest_fixed

    # 13.1: Muskelgruppen-Überrepräsentation (Auto-Fix)
    overrep_warnings, overrep_fixed = _check_muscle_overrepresentation(
        plan_json, uebungen_map, available_exercises
    )
    warnings.extend(overrep_warnings)
    if overrep_fixed > 0:
        fixes["overrep_fixed"] = overrep_fixed

    return warnings, fixes


# ─────────────────────────────────────────────────────────────────────────────
# DB-Helfer
# ─────────────────────────────────────────────────────────────────────────────


def _build_uebungen_map(plan_json: dict) -> dict[str, Uebung]:
    """Batch-lädt alle Übungen aus dem Plan in einer DB-Query.

    Returns:
        Dict {bezeichnung: Uebung-Instanz}
    """
    all_ex_names = {
        ex["exercise_name"]
        for session in plan_json.get("sessions", [])
        for ex in session.get("exercises", [])
        if ex.get("exercise_name")
    }
    if not all_ex_names:
        return {}
    return {
        u.bezeichnung: u
        for u in Uebung.objects.filter(bezeichnung__in=all_ex_names).only(
            "bezeichnung", "muskelgruppe", "bewegungstyp"
        )
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11.1: Cross-Session-Duplikat-Check
# ─────────────────────────────────────────────────────────────────────────────


def _check_cross_session_duplicates(plan_json: dict) -> list[str]:
    """Prüft ob identische Übungen in verschiedenen Sessions vorkommen.

    Nur bei <= 4 Sessions relevant (bei PPL 6x sind Duplikate erwünscht).
    """
    sessions = plan_json.get("sessions", [])
    if len(sessions) > 4:
        return []

    # {exercise_name: [(session_index, day_name), ...]}
    exercise_locations: dict[str, list[tuple[int, str]]] = {}
    for i, session in enumerate(sessions):
        day_name = session.get("day_name", f"Session {i + 1}")
        for ex in session.get("exercises", []):
            name = ex.get("exercise_name", "")
            if name:
                exercise_locations.setdefault(name, []).append((i + 1, day_name))

    warnings = []
    for name, locations in exercise_locations.items():
        if len(locations) > 1:
            session_names = ", ".join(f"Session {idx} ({day})" for idx, day in locations)
            warnings.append(f"Cross-Session-Duplikat: '{name}' kommt in {session_names} vor")
    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# 11.2: Verbotene Kombinationen
# ─────────────────────────────────────────────────────────────────────────────


def _check_forbidden_combinations(plan_json: dict, uebungen_map: dict[str, Uebung]) -> list[str]:
    """Prüft ob verbotene Übungskombinationen in derselben Session vorkommen."""
    warnings = []

    for i, session in enumerate(plan_json.get("sessions", [])):
        day_name = session.get("day_name", f"Session {i + 1}")
        exercises = session.get("exercises", [])

        # Übungsnamen → DB-Metadaten für diese Session
        session_ex_data = []
        for ex in exercises:
            name = ex.get("exercise_name", "")
            uebung = uebungen_map.get(name)
            if uebung:
                session_ex_data.append(
                    {
                        "name": name,
                        "muskelgruppe": uebung.muskelgruppe,
                        "bewegungstyp": uebung.bewegungstyp,
                    }
                )

        # Prüfe jede Regel
        for rule in _FORBIDDEN_COMBINATIONS:
            ff = rule["forbidden_filter"]
            forbidden_exercises = [
                ex
                for ex in session_ex_data
                if ex["muskelgruppe"] == ff["muskelgruppe"]
                and ex["bewegungstyp"] == ff["bewegungstyp"]
            ]
            if not forbidden_exercises:
                continue

            conflict_exercises = []
            for cw in rule["conflicts_with"]:
                conflict_exercises.extend(
                    ex
                    for ex in session_ex_data
                    if ex["muskelgruppe"] == cw["muskelgruppe"]
                    and ex["bewegungstyp"] == cw["bewegungstyp"]
                )

            if conflict_exercises:
                forbidden_names = ", ".join(f"'{ex['name']}'" for ex in forbidden_exercises)
                conflict_names = ", ".join(f"'{ex['name']}'" for ex in conflict_exercises)
                warnings.append(
                    f"Session '{day_name}': {forbidden_names} kollidiert mit "
                    f"{conflict_names} – {rule['reason']}"
                )

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# 11.3: Anatomische Pflichtgruppen
# ─────────────────────────────────────────────────────────────────────────────


def _check_anatomical_requirements(plan_json: dict, uebungen_map: dict[str, Uebung]) -> list[str]:
    """Prüft anatomische Mindestanforderungen.

    - Hintere Schulter (SCHULTER_HINT) muss >= 2 Sätze im Plan haben
    - Vertikaler Zug (RUECKEN_LAT) muss auf Pull-Tag vorhanden sein
    """
    warnings = []

    # Check 1: Hintere Schulter >= 2 Sätze
    schulter_hint_sets = 0
    for session in plan_json.get("sessions", []):
        for ex in session.get("exercises", []):
            uebung = uebungen_map.get(ex.get("exercise_name", ""))
            if uebung and uebung.muskelgruppe == "SCHULTER_HINT":
                schulter_hint_sets += ex.get("sets", 0)

    if schulter_hint_sets < _MIN_SCHULTER_HINT_SETS:
        warnings.append(
            f"Hintere Schulter: nur {schulter_hint_sets} Sätze im Plan "
            f"(mindestens {_MIN_SCHULTER_HINT_SETS} empfohlen)"
        )

    # Check 2: Vertikaler Zug auf Pull-Tag
    for i, session in enumerate(plan_json.get("sessions", [])):
        day_name = session.get("day_name", "")
        is_pull = any(kw in day_name.lower() for kw in _PULL_SESSION_KEYWORDS)
        if not is_pull:
            continue

        has_lat = False
        for ex in session.get("exercises", []):
            uebung = uebungen_map.get(ex.get("exercise_name", ""))
            if uebung and uebung.muskelgruppe == "RUECKEN_LAT":
                has_lat = True
                break

        if not has_lat:
            warnings.append(f"Session '{day_name}': Kein vertikaler Zug (Lat) gefunden")

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# 11.4: Compound-vor-Isolation Reihenfolge (Auto-Fix)
# ─────────────────────────────────────────────────────────────────────────────


def _fix_exercise_order(plan_json: dict, uebungen_map: dict[str, Uebung]) -> int:
    """Sortiert Compound-Übungen vor Isolation-Übungen.

    Modifiziert plan_json in-place.

    Returns:
        Anzahl der korrigierten Sessions.
    """
    fixed_count = 0

    for session in plan_json.get("sessions", []):
        exercises = session.get("exercises", [])
        if len(exercises) < 2:
            continue

        # Klassifiziere jede Übung
        compounds = []
        isolations = []
        for ex in exercises:
            uebung = uebungen_map.get(ex.get("exercise_name", ""))
            is_compound = uebung is not None and uebung.bewegungstyp in _COMPOUND_BEWEGUNGSTYPEN
            if is_compound:
                compounds.append(ex)
            else:
                isolations.append(ex)

        # Prüfe ob Reihenfolge bereits korrekt ist
        if not compounds or not isolations:
            continue

        max_compound_order = max(ex.get("order", 0) for ex in compounds)
        min_isolation_order = min(ex.get("order", 999) for ex in isolations)

        if max_compound_order <= min_isolation_order:
            continue  # Bereits korrekt

        # Auto-Fix: Compounds vor Isolations, neue order-Werte zuweisen
        reordered = compounds + isolations
        for idx, ex in enumerate(reordered, start=1):
            ex["order"] = idx
        session["exercises"] = reordered
        fixed_count += 1

    return fixed_count


# ─────────────────────────────────────────────────────────────────────────────
# 11.5: Pausenzeiten-Plausibilität (Auto-Fix)
# ─────────────────────────────────────────────────────────────────────────────


def _fix_rest_times(plan_json: dict, uebungen_map: dict[str, Uebung]) -> int:
    """Korrigiert unplausible Pausenzeiten.

    Compound (DRUECKEN/ZIEHEN/BEUGEN/HEBEN): 120-180s, Default 150s.
    Isolation: 60-90s, Default 75s.

    Modifiziert plan_json in-place.

    Returns:
        Anzahl der korrigierten Übungen.
    """
    fixed_count = 0

    for session in plan_json.get("sessions", []):
        for ex in session.get("exercises", []):
            uebung = uebungen_map.get(ex.get("exercise_name", ""))
            if uebung is None:
                continue

            rest = ex.get("rest_seconds")
            if rest is None:
                continue

            is_compound = uebung.bewegungstyp in _COMPOUND_BEWEGUNGSTYPEN

            if is_compound:
                min_rest, max_rest = _COMPOUND_REST_RANGE
                default_rest = _COMPOUND_REST_DEFAULT
            else:
                min_rest, max_rest = _ISOLATION_REST_RANGE
                default_rest = _ISOLATION_REST_DEFAULT

            if not (min_rest <= rest <= max_rest):
                ex["rest_seconds"] = default_rest
                fixed_count += 1

    return fixed_count


# ─────────────────────────────────────────────────────────────────────────────
# 13.1: Muskelgruppen-Überrepräsentation pro Session (Auto-Fix)
# ─────────────────────────────────────────────────────────────────────────────


def _check_muscle_overrepresentation(
    plan_json: dict,
    uebungen_map: dict[str, Uebung],
    available_exercises: list[str] | None = None,
) -> tuple[list[str], int]:
    """Prüft ob eine Muskelgruppe >7 Sätze pro Session hat.

    Verhindert z.B. 3× Quad (Kniebeuge + Bulgarian Split Squat + Frontkniebeuge = 10 Sätze).
    Auto-Fix (wenn available_exercises): überzählige Übung durch unterrepräsentierte ersetzen.

    Returns:
        (warnings, fix_count)
    """
    warnings: list[str] = []
    fix_count = 0

    for session in plan_json.get("sessions", []):
        day_name = session.get("day_name", "?")
        exercises = session.get("exercises", [])

        # Sätze pro primärer Muskelgruppe zählen
        group_sets: dict[str, int] = {}
        group_exercises: dict[str, list[tuple[int, dict]]] = {}

        for idx, ex in enumerate(exercises):
            uebung = uebungen_map.get(ex.get("exercise_name", ""))
            if not uebung:
                continue
            mg = uebung.muskelgruppe
            sets = ex.get("sets", 0)
            group_sets[mg] = group_sets.get(mg, 0) + sets
            group_exercises.setdefault(mg, []).append((idx, ex))

        for mg, total_sets in group_sets.items():
            if total_sets <= _MAX_SETS_PER_MUSCLE_GROUP:
                continue

            # Auto-Fix versuchen
            if available_exercises:
                fixed = _fix_overrepresentation(
                    session, mg, group_exercises[mg], group_sets, available_exercises
                )
                if fixed:
                    fix_count += 1
                    continue

            ex_names = [ex.get("exercise_name", "?") for _, ex in group_exercises[mg]]
            warnings.append(
                f"Session '{day_name}': {mg} hat {total_sets} Sätze "
                f"(max {_MAX_SETS_PER_MUSCLE_GROUP}) – Übungen: {', '.join(ex_names)}"
            )

    return warnings, fix_count


def _fix_overrepresentation(
    session: dict,
    overrep_mg: str,
    overrep_exercises: list[tuple[int, dict]],
    group_sets: dict[str, int],
    available_exercises: list[str],
) -> bool:
    """Ersetzt die kleinste Übung der überrepräsentierten Gruppe durch eine unterrepräsentierte.

    Wählt Ersatzübung nur aus Muskelgruppen die bereits in der Session vorkommen
    (kontextuell passend, z.B. kein Quad-Ersatz auf Push-Tag).
    """
    exercises = session.get("exercises", [])

    # Ersetzbare Übung finden (Position 3+, wenigste Sätze in über-rep. Gruppe)
    replaceable = [(idx, ex) for idx, ex in overrep_exercises if idx >= 3]
    if not replaceable:
        return False

    _, rep_ex = min(replaceable, key=lambda x: x[1].get("sets", 99))

    # Andere Gruppen in der Session, sortiert nach wenigsten Sätzen
    other_groups = sorted(
        [(mg, s) for mg, s in group_sets.items() if mg != overrep_mg],
        key=lambda x: x[1],
    )
    if not other_groups:
        return False

    session_ex_names = {ex.get("exercise_name") for ex in exercises}

    for target_mg, _ in other_groups:
        try:
            replacement = (
                Uebung.objects.filter(
                    muskelgruppe=target_mg,
                    bezeichnung__in=available_exercises,
                )
                .exclude(bezeichnung__in=session_ex_names)
                .values_list("bezeichnung", flat=True)
                .first()
            )
        except Exception:
            continue

        if replacement:
            old_name = rep_ex.get("exercise_name", "?")
            rep_ex["exercise_name"] = replacement
            rep_ex["notes"] = (
                f"Auto-Fix 13.1: '{old_name}' ersetzt (Überrepräsentation {overrep_mg})"
            )
            print(
                f"   🔧 Auto-Fix 13.1: '{old_name}' → '{replacement}' in "
                f"'{session.get('day_name', '?')}' ({overrep_mg} → {target_mg})"
            )
            return True

    return False
