"""
Tests für Phase 11 – KI-Planvalidierung.

Testet alle 5 Sub-Tasks:
- 11.1: Cross-Session-Duplikate
- 11.2: Verbotene Kombinationen
- 11.3: Anatomische Pflichtgruppen
- 11.4: Compound-vor-Isolation Reihenfolge
- 11.5: Pausenzeiten-Plausibilität
"""

import pytest

from core.tests.factories import UebungFactory

from ai_coach.plan_validator import (
    _check_anatomical_requirements,
    _check_cross_session_duplicates,
    _check_forbidden_combinations,
    _fix_exercise_order,
    _fix_rest_times,
    validate_plan_structure,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test-Helfer (analog zu test_plan_generator.py)
# ─────────────────────────────────────────────────────────────────────────────


def _make_plan(sessions: list[dict]) -> dict:
    return {
        "plan_name": "Test-Plan",
        "plan_description": "Test",
        "sessions": sessions,
    }


def _make_session(day_name: str, exercises: list[dict]) -> dict:
    return {"day_name": day_name, "exercises": exercises}


def _make_exercise(name: str, sets: int = 3, order: int = 1, rest_seconds: int = 90) -> dict:
    return {
        "exercise_name": name,
        "order": order,
        "sets": sets,
        "reps": "8-10",
        "rest_seconds": rest_seconds,
        "rpe_target": 7,
        "notes": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11.1: Cross-Session-Duplikate
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossSessionDuplicates:
    def test_duplikat_bei_3_sessions_warnt(self):
        plan = _make_plan(
            [
                _make_session("Push", [_make_exercise("Bankdrücken")]),
                _make_session("Pull", [_make_exercise("Kreuzheben")]),
                _make_session("Legs", [_make_exercise("Bankdrücken")]),
            ]
        )
        warnings = _check_cross_session_duplicates(plan)
        assert len(warnings) == 1
        assert "Bankdrücken" in warnings[0]
        assert "Session 1" in warnings[0]
        assert "Session 3" in warnings[0]

    def test_keine_warnung_bei_5_sessions(self):
        plan = _make_plan(
            [_make_session(f"Day {i}", [_make_exercise("Bankdrücken")]) for i in range(5)]
        )
        warnings = _check_cross_session_duplicates(plan)
        assert warnings == []

    def test_keine_duplikate_kein_warning(self):
        plan = _make_plan(
            [
                _make_session("Push", [_make_exercise("Bankdrücken")]),
                _make_session("Pull", [_make_exercise("Kreuzheben")]),
                _make_session("Legs", [_make_exercise("Kniebeuge")]),
            ]
        )
        warnings = _check_cross_session_duplicates(plan)
        assert warnings == []

    def test_4_sessions_grenze_warnt(self):
        plan = _make_plan(
            [
                _make_session("A", [_make_exercise("RDL")]),
                _make_session("B", [_make_exercise("Bankdrücken")]),
                _make_session("C", [_make_exercise("RDL")]),
                _make_session("D", [_make_exercise("Kniebeuge")]),
            ]
        )
        warnings = _check_cross_session_duplicates(plan)
        assert len(warnings) == 1
        assert "RDL" in warnings[0]

    def test_leerer_plan_kein_crash(self):
        warnings = _check_cross_session_duplicates({"sessions": []})
        assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# 11.2: Verbotene Kombinationen
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestForbiddenCombinations:
    def test_front_raises_mit_bankdruecken_warnt(self):
        front_raises = UebungFactory(
            bezeichnung="Front Raises (Kurzhantel)",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="ISOLATION",
        )
        bankdruecken = UebungFactory(
            bezeichnung="Bankdrücken (Langhantel)",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {
            front_raises.bezeichnung: front_raises,
            bankdruecken.bezeichnung: bankdruecken,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken (Langhantel)"),
                        _make_exercise("Front Raises (Kurzhantel)"),
                    ],
                )
            ]
        )
        warnings = _check_forbidden_combinations(plan, uebungen_map)
        assert len(warnings) == 1
        assert "Front Raises" in warnings[0]
        assert "Bankdrücken" in warnings[0]

    def test_front_raises_mit_schulterdruecken_warnt(self):
        front_raises = UebungFactory(
            bezeichnung="Front Raises (Kurzhantel)",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="ISOLATION",
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken (Kurzhantel)",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {
            front_raises.bezeichnung: front_raises,
            schulter.bezeichnung: schulter,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Schulterdrücken (Kurzhantel)"),
                        _make_exercise("Front Raises (Kurzhantel)"),
                    ],
                )
            ]
        )
        warnings = _check_forbidden_combinations(plan, uebungen_map)
        assert len(warnings) == 1

    def test_front_raises_ohne_pressing_ok(self):
        front_raises = UebungFactory(
            bezeichnung="Front Raises (Kurzhantel)",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="ISOLATION",
        )
        seitheben = UebungFactory(
            bezeichnung="Seitheben",
            muskelgruppe="SCHULTER_SEIT",
            bewegungstyp="ISOLATION",
        )
        uebungen_map = {
            front_raises.bezeichnung: front_raises,
            seitheben.bezeichnung: seitheben,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Schultern",
                    [
                        _make_exercise("Front Raises (Kurzhantel)"),
                        _make_exercise("Seitheben"),
                    ],
                )
            ]
        )
        warnings = _check_forbidden_combinations(plan, uebungen_map)
        assert warnings == []

    def test_uebung_nicht_in_map_wird_uebersprungen(self):
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Unbekannte Übung"),
                        _make_exercise("Noch eine"),
                    ],
                )
            ]
        )
        warnings = _check_forbidden_combinations(plan, {})
        assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# 11.3: Anatomische Pflichtgruppen
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAnatomicalRequirements:
    def test_keine_hintere_schulter_warnt(self):
        brust = UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {brust.bezeichnung: brust}
        plan = _make_plan([_make_session("Push", [_make_exercise("Bankdrücken", sets=4)])])
        warnings = _check_anatomical_requirements(plan, uebungen_map)
        assert any("Hintere Schulter" in w for w in warnings)
        assert any("0 Sätze" in w for w in warnings)

    def test_genuegend_hintere_schulter_ok(self):
        face_pull = UebungFactory(
            bezeichnung="Face Pull",
            muskelgruppe="SCHULTER_HINT",
            bewegungstyp="ZIEHEN",
        )
        uebungen_map = {face_pull.bezeichnung: face_pull}
        plan = _make_plan([_make_session("Pull", [_make_exercise("Face Pull", sets=3)])])
        warnings = _check_anatomical_requirements(plan, uebungen_map)
        assert not any("Hintere Schulter" in w for w in warnings)

    def test_pull_tag_ohne_lat_warnt(self):
        bizeps = UebungFactory(
            bezeichnung="Bizepscurls",
            muskelgruppe="BIZEPS",
            bewegungstyp="ISOLATION",
        )
        face_pull = UebungFactory(
            bezeichnung="Face Pull",
            muskelgruppe="SCHULTER_HINT",
            bewegungstyp="ZIEHEN",
        )
        uebungen_map = {
            bizeps.bezeichnung: bizeps,
            face_pull.bezeichnung: face_pull,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Pull (Rücken/Bizeps)",
                    [
                        _make_exercise("Bizepscurls", sets=3),
                        _make_exercise("Face Pull", sets=3),
                    ],
                )
            ]
        )
        warnings = _check_anatomical_requirements(plan, uebungen_map)
        assert any("Lat" in w for w in warnings)

    def test_pull_tag_mit_lat_ok(self):
        latziehen = UebungFactory(
            bezeichnung="Latziehen",
            muskelgruppe="RUECKEN_LAT",
            bewegungstyp="ZIEHEN",
        )
        face_pull = UebungFactory(
            bezeichnung="Face Pull",
            muskelgruppe="SCHULTER_HINT",
            bewegungstyp="ZIEHEN",
        )
        uebungen_map = {
            latziehen.bezeichnung: latziehen,
            face_pull.bezeichnung: face_pull,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Pull",
                    [
                        _make_exercise("Latziehen", sets=3),
                        _make_exercise("Face Pull", sets=2),
                    ],
                )
            ]
        )
        warnings = _check_anatomical_requirements(plan, uebungen_map)
        # Kein Lat-Warning
        assert not any("Lat" in w for w in warnings)
        # Kein Hintere-Schulter-Warning (2 Sätze)
        assert not any("Hintere Schulter" in w for w in warnings)

    def test_nicht_pull_session_wird_ignoriert(self):
        brust = UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        face_pull = UebungFactory(
            bezeichnung="Face Pull",
            muskelgruppe="SCHULTER_HINT",
            bewegungstyp="ZIEHEN",
        )
        uebungen_map = {
            brust.bezeichnung: brust,
            face_pull.bezeichnung: face_pull,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push (Brust/Schultern)",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Face Pull", sets=2),
                    ],
                )
            ]
        )
        warnings = _check_anatomical_requirements(plan, uebungen_map)
        # Kein Lat-Warning für Push-Tag
        assert not any("Lat" in w for w in warnings)


# ─────────────────────────────────────────────────────────────────────────────
# 11.4: Compound-vor-Isolation Reihenfolge
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExerciseOrder:
    def test_isolation_vor_compound_wird_korrigiert(self):
        isolation = UebungFactory(
            bezeichnung="Seitheben",
            muskelgruppe="SCHULTER_SEIT",
            bewegungstyp="ISOLATION",
        )
        compound = UebungFactory(
            bezeichnung="Schulterdrücken",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {
            isolation.bezeichnung: isolation,
            compound.bezeichnung: compound,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Schultern",
                    [
                        _make_exercise("Seitheben", order=1),
                        _make_exercise("Schulterdrücken", order=2),
                    ],
                )
            ]
        )
        fixed = _fix_exercise_order(plan, uebungen_map)
        assert fixed == 1
        exercises = plan["sessions"][0]["exercises"]
        assert exercises[0]["exercise_name"] == "Schulterdrücken"
        assert exercises[1]["exercise_name"] == "Seitheben"

    def test_korrekte_reihenfolge_bleibt(self):
        compound = UebungFactory(
            bezeichnung="Kniebeuge",
            muskelgruppe="BEINE_QUAD",
            bewegungstyp="BEUGEN",
        )
        isolation = UebungFactory(
            bezeichnung="Beinstrecker",
            muskelgruppe="BEINE_QUAD",
            bewegungstyp="ISOLATION",
        )
        uebungen_map = {
            compound.bezeichnung: compound,
            isolation.bezeichnung: isolation,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", order=1),
                        _make_exercise("Beinstrecker", order=2),
                    ],
                )
            ]
        )
        fixed = _fix_exercise_order(plan, uebungen_map)
        assert fixed == 0

    def test_order_werte_nach_fix_fortlaufend(self):
        iso1 = UebungFactory(
            bezeichnung="Seitheben",
            muskelgruppe="SCHULTER_SEIT",
            bewegungstyp="ISOLATION",
        )
        comp1 = UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        comp2 = UebungFactory(
            bezeichnung="Schulterdrücken",
            muskelgruppe="SCHULTER_VORN",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {
            iso1.bezeichnung: iso1,
            comp1.bezeichnung: comp1,
            comp2.bezeichnung: comp2,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Seitheben", order=1),
                        _make_exercise("Bankdrücken", order=2),
                        _make_exercise("Schulterdrücken", order=3),
                    ],
                )
            ]
        )
        _fix_exercise_order(plan, uebungen_map)
        orders = [ex["order"] for ex in plan["sessions"][0]["exercises"]]
        assert orders == [1, 2, 3]


# ─────────────────────────────────────────────────────────────────────────────
# 11.5: Pausenzeiten-Plausibilität
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRestTimes:
    def test_compound_mit_60s_wird_korrigiert(self):
        compound = UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        uebungen_map = {compound.bezeichnung: compound}
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [_make_exercise("Bankdrücken", rest_seconds=60)],
                )
            ]
        )
        fixed = _fix_rest_times(plan, uebungen_map)
        assert fixed == 1
        assert plan["sessions"][0]["exercises"][0]["rest_seconds"] == 150

    def test_isolation_mit_180s_wird_korrigiert(self):
        isolation = UebungFactory(
            bezeichnung="Bizepscurls",
            muskelgruppe="BIZEPS",
            bewegungstyp="ISOLATION",
        )
        uebungen_map = {isolation.bezeichnung: isolation}
        plan = _make_plan(
            [
                _make_session(
                    "Pull",
                    [_make_exercise("Bizepscurls", rest_seconds=180)],
                )
            ]
        )
        fixed = _fix_rest_times(plan, uebungen_map)
        assert fixed == 1
        assert plan["sessions"][0]["exercises"][0]["rest_seconds"] == 75

    def test_korrekte_pausen_bleiben(self):
        compound = UebungFactory(
            bezeichnung="Kniebeuge",
            muskelgruppe="BEINE_QUAD",
            bewegungstyp="BEUGEN",
        )
        isolation = UebungFactory(
            bezeichnung="Beinstrecker",
            muskelgruppe="BEINE_QUAD",
            bewegungstyp="ISOLATION",
        )
        uebungen_map = {
            compound.bezeichnung: compound,
            isolation.bezeichnung: isolation,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", rest_seconds=150),
                        _make_exercise("Beinstrecker", rest_seconds=75),
                    ],
                )
            ]
        )
        fixed = _fix_rest_times(plan, uebungen_map)
        assert fixed == 0

    def test_alle_gleich_werden_differenziert(self):
        compound = UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        isolation = UebungFactory(
            bezeichnung="Fliegende",
            muskelgruppe="BRUST",
            bewegungstyp="ISOLATION",
        )
        uebungen_map = {
            compound.bezeichnung: compound,
            isolation.bezeichnung: isolation,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", rest_seconds=90),
                        _make_exercise("Fliegende", rest_seconds=90),
                    ],
                )
            ]
        )
        fixed = _fix_rest_times(plan, uebungen_map)
        # Compound 90s < 120 → 150, Isolation 90s im Bereich → bleibt
        assert fixed == 1
        assert plan["sessions"][0]["exercises"][0]["rest_seconds"] == 150
        assert plan["sessions"][0]["exercises"][1]["rest_seconds"] == 90


# ─────────────────────────────────────────────────────────────────────────────
# Entry-Point Integration
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestValidatePlanStructure:
    def test_integration_alle_checks_laufen(self):
        """Plan mit mehreren Problemen: Warnings + Fixes."""
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        UebungFactory(
            bezeichnung="Seitheben",
            muskelgruppe="SCHULTER_SEIT",
            bewegungstyp="ISOLATION",
        )
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Seitheben", order=1, rest_seconds=60),
                        _make_exercise("Bankdrücken", order=2, rest_seconds=60),
                    ],
                ),
                _make_session(
                    "Pull",
                    [_make_exercise("Bankdrücken", order=1, rest_seconds=90)],
                ),
            ]
        )
        warnings, fixes = validate_plan_structure(plan)
        # Cross-Session-Duplikat (Bankdrücken in 2 Sessions)
        assert any("Bankdrücken" in w for w in warnings)
        # Hintere Schulter fehlt
        assert any("Hintere Schulter" in w for w in warnings)
        # Order wurde korrigiert
        assert fixes.get("order_fixed", 0) >= 1
        # Rest wurde korrigiert
        assert fixes.get("rest_fixed", 0) >= 1

    def test_leerer_plan_kein_crash(self):
        warnings, fixes = validate_plan_structure({"sessions": []})
        assert warnings == []
        assert fixes == {}

    def test_plan_ohne_sessions_key(self):
        warnings, fixes = validate_plan_structure({})
        assert warnings == []
        assert fixes == {}
