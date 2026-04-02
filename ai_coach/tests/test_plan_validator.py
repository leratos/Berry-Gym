"""
Tests für Phase 11 + 13 + 16 – KI-Planvalidierung.

Testet alle Sub-Tasks:
- 11.1: Cross-Session-Duplikate
- 11.2: Verbotene Kombinationen
- 11.3: Anatomische Pflichtgruppen
- 11.4: Compound-vor-Isolation Reihenfolge
- 11.5: Pausenzeiten-Plausibilität
- 13.1: Muskelgruppen-Überrepräsentation pro Session
- 16: Push/Pull-Balance über Gesamtplan
"""

import pytest

from ai_coach.plan_validator import (
    _check_anatomical_requirements,
    _check_cross_session_duplicates,
    _check_forbidden_combinations,
    _check_muscle_overrepresentation,
    _check_push_pull_ratio,
    _classify_push_pull,
    _count_push_pull_sets,
    _fix_exercise_order,
    _fix_rest_times,
    validate_plan_structure,
)
from core.tests.factories import UebungFactory

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


# ─────────────────────────────────────────────────────────────────────────────
# 13.1: Muskelgruppen-Überrepräsentation pro Session
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMuscleOverrepresentation:
    def test_8_saetze_gleiche_gruppe_warnt(self):
        """3× Quad-Übungen mit insgesamt 10 Sätzen → Warning."""
        kniebeuge = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        bss = UebungFactory(
            bezeichnung="Bulgarian Split Squat", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        front_kb = UebungFactory(
            bezeichnung="Frontkniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        uebungen_map = {
            kniebeuge.bezeichnung: kniebeuge,
            bss.bezeichnung: bss,
            front_kb.bezeichnung: front_kb,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", sets=4, order=1),
                        _make_exercise("Bulgarian Split Squat", sets=3, order=2),
                        _make_exercise("Frontkniebeuge", sets=3, order=3),
                    ],
                )
            ]
        )
        warnings, fix_count = _check_muscle_overrepresentation(plan, uebungen_map)
        assert len(warnings) == 1
        assert "BEINE_QUAD" in warnings[0]
        assert "10" in warnings[0]
        assert fix_count == 0

    def test_7_saetze_gleiche_gruppe_ok(self):
        """7 Sätze = genau am Limit → kein Warning."""
        kniebeuge = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        bss = UebungFactory(
            bezeichnung="Bulgarian Split Squat", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        uebungen_map = {
            kniebeuge.bezeichnung: kniebeuge,
            bss.bezeichnung: bss,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", sets=4, order=1),
                        _make_exercise("Bulgarian Split Squat", sets=3, order=2),
                    ],
                )
            ]
        )
        warnings, fix_count = _check_muscle_overrepresentation(plan, uebungen_map)
        assert warnings == []
        assert fix_count == 0

    def test_autofix_ersetzt_ueberrepraesentation(self):
        """Auto-Fix: 3× Quad → ersetzt letzte durch Hamstring-Übung."""
        kniebeuge = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        bss = UebungFactory(
            bezeichnung="Bulgarian Split Squat", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        front_kb = UebungFactory(
            bezeichnung="Frontkniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        rdl = UebungFactory(bezeichnung="RDL", muskelgruppe="BEINE_HAM", bewegungstyp="HEBEN")
        UebungFactory(bezeichnung="Beinbeuger", muskelgruppe="BEINE_HAM", bewegungstyp="ISOLATION")
        uebungen_map = {
            kniebeuge.bezeichnung: kniebeuge,
            bss.bezeichnung: bss,
            front_kb.bezeichnung: front_kb,
            rdl.bezeichnung: rdl,
        }
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", sets=4, order=1),
                        _make_exercise("RDL", sets=3, order=2),
                        _make_exercise("Bulgarian Split Squat", sets=3, order=3),
                        _make_exercise("Frontkniebeuge", sets=3, order=4),
                    ],
                )
            ]
        )
        available = [
            "Kniebeuge",
            "RDL",
            "Bulgarian Split Squat",
            "Frontkniebeuge",
            "Beinbeuger",
        ]
        warnings, fix_count = _check_muscle_overrepresentation(plan, uebungen_map, available)
        assert warnings == []
        assert fix_count == 1
        # Frontkniebeuge (wenigste Sätze ab Pos 3+) wurde ersetzt
        ex_names = [e["exercise_name"] for e in plan["sessions"][0]["exercises"]]
        assert "Frontkniebeuge" not in ex_names
        assert "Beinbeuger" in ex_names

    def test_autofix_schuetzt_erste_3_uebungen(self):
        """Compounds auf Pos 0-2 werden nicht ersetzt → Warning statt Fix."""
        u1 = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        u2 = UebungFactory(bezeichnung="BSS", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN")
        u3 = UebungFactory(bezeichnung="Front KB", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN")
        UebungFactory(bezeichnung="Beinbeuger", muskelgruppe="BEINE_HAM", bewegungstyp="ISOLATION")
        uebungen_map = {u.bezeichnung: u for u in [u1, u2, u3]}
        plan = _make_plan(
            [
                _make_session(
                    "Legs",
                    [
                        _make_exercise("Kniebeuge", sets=4, order=1),
                        _make_exercise("BSS", sets=3, order=2),
                        _make_exercise("Front KB", sets=3, order=3),
                    ],
                )
            ]
        )
        available = ["Kniebeuge", "BSS", "Front KB", "Beinbeuger"]
        warnings, fix_count = _check_muscle_overrepresentation(plan, uebungen_map, available)
        # Alle 3 Übungen auf Pos 0-2 → nicht ersetzbar → Warning
        assert len(warnings) == 1
        assert fix_count == 0

    def test_verschiedene_gruppen_kein_warning(self):
        """Verschiedene Muskelgruppen → kein Warning auch bei vielen Sätzen."""
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        trizeps = UebungFactory(
            bezeichnung="Trizeps Pushdown", muskelgruppe="TRIZEPS", bewegungstyp="ISOLATION"
        )
        uebungen_map = {u.bezeichnung: u for u in [brust, schulter, trizeps]}
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4, order=1),
                        _make_exercise("Schulterdrücken", sets=4, order=2),
                        _make_exercise("Trizeps Pushdown", sets=4, order=3),
                    ],
                )
            ]
        )
        warnings, fix_count = _check_muscle_overrepresentation(plan, uebungen_map)
        assert warnings == []
        assert fix_count == 0

    def test_leere_session_kein_crash(self):
        plan = _make_plan([_make_session("Empty", [])])
        warnings, fix_count = _check_muscle_overrepresentation(plan, {})
        assert warnings == []
        assert fix_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# 16: Push/Pull-Balance
# ─────────────────────────────────────────────────────────────────────────────


class TestClassifyPushPull:
    def test_push_gruppen(self):
        assert _classify_push_pull("BRUST") == "push"
        assert _classify_push_pull("SCHULTER_VORN") == "push"
        assert _classify_push_pull("SCHULTER_SEIT") == "push"
        assert _classify_push_pull("TRIZEPS") == "push"

    def test_pull_gruppen(self):
        assert _classify_push_pull("RUECKEN_LAT") == "pull"
        assert _classify_push_pull("BIZEPS") == "pull"
        assert _classify_push_pull("SCHULTER_HINT") == "pull"
        assert _classify_push_pull("RUECKEN_OBERER") == "pull"

    def test_neutral_gruppen(self):
        assert _classify_push_pull("BEINE_QUAD") is None
        assert _classify_push_pull("BAUCH") is None
        assert _classify_push_pull("PO") is None
        assert _classify_push_pull("GANZKOERPER") is None


@pytest.mark.django_db
class TestCountPushPullSets:
    def test_zaehlt_push_und_pull_korrekt(self):
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        ruecken = UebungFactory(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN"
        )
        quad = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        uebungen_map = {u.bezeichnung: u for u in [brust, ruecken, quad]}
        plan = _make_plan(
            [
                _make_session("Push", [_make_exercise("Bankdrücken", sets=4)]),
                _make_session("Pull", [_make_exercise("Rudern", sets=3)]),
                _make_session("Legs", [_make_exercise("Kniebeuge", sets=4)]),
            ]
        )
        push, pull = _count_push_pull_sets(plan, uebungen_map)
        assert push == 4
        assert pull == 3

    def test_leerer_plan(self):
        push, pull = _count_push_pull_sets({"sessions": []}, {})
        assert push == 0
        assert pull == 0


@pytest.mark.django_db
class TestPushPullRatio:
    def test_balanciert_keine_warnung(self):
        """Push 12 / Pull 10 → Ratio 1.2 → ok."""
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        ruecken = UebungFactory(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN"
        )
        bizeps = UebungFactory(
            bezeichnung="Bizepscurls", muskelgruppe="BIZEPS", bewegungstyp="ISOLATION"
        )
        uebungen_map = {u.bezeichnung: u for u in [brust, schulter, ruecken, bizeps]}
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Schulterdrücken", sets=4),
                    ],
                ),
                _make_session(
                    "Pull",
                    [
                        _make_exercise("Rudern", sets=4),
                        _make_exercise("Bizepscurls", sets=3),
                    ],
                ),
            ]
        )
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map)
        assert warnings == []
        assert fix_count == 0

    def test_leichte_imbalance_warnt(self):
        """Push 16 / Pull 10 → Ratio 1.6 → Warnung."""
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        seitheben = UebungFactory(
            bezeichnung="Seitheben", muskelgruppe="SCHULTER_SEIT", bewegungstyp="ISOLATION"
        )
        trizeps = UebungFactory(
            bezeichnung="Trizeps Pushdown", muskelgruppe="TRIZEPS", bewegungstyp="ISOLATION"
        )
        ruecken = UebungFactory(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN"
        )
        bizeps = UebungFactory(
            bezeichnung="Bizepscurls", muskelgruppe="BIZEPS", bewegungstyp="ISOLATION"
        )
        uebungen_map = {
            u.bezeichnung: u for u in [brust, schulter, seitheben, trizeps, ruecken, bizeps]
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Schulterdrücken", sets=4),
                        _make_exercise("Seitheben", sets=4),
                        _make_exercise("Trizeps Pushdown", sets=4),
                    ],
                ),
                _make_session(
                    "Pull",
                    [
                        _make_exercise("Rudern", sets=4),
                        _make_exercise("Bizepscurls", sets=3),
                    ],
                ),
            ]
        )
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map)
        assert len(warnings) == 1
        assert "Push/Pull-Imbalance" in warnings[0]
        assert "1.6" in warnings[0] or "Ratio" in warnings[0]
        assert fix_count == 0

    def test_starke_imbalance_autofix(self):
        """Push 20 / Pull 10 → Ratio 2.0 → Auto-Fix."""
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        seitheben = UebungFactory(
            bezeichnung="Seitheben", muskelgruppe="SCHULTER_SEIT", bewegungstyp="ISOLATION"
        )
        trizeps = UebungFactory(
            bezeichnung="Trizeps Pushdown", muskelgruppe="TRIZEPS", bewegungstyp="ISOLATION"
        )
        fliegende = UebungFactory(
            bezeichnung="Fliegende", muskelgruppe="BRUST", bewegungstyp="ISOLATION"
        )
        ruecken = UebungFactory(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN"
        )
        bizeps = UebungFactory(
            bezeichnung="Bizepscurls", muskelgruppe="BIZEPS", bewegungstyp="ISOLATION"
        )
        # Ersatz-Übung (DB-Seiteneffekt, wird von _find_pull_replacement gefunden)
        UebungFactory(
            bezeichnung="Face Pull", muskelgruppe="SCHULTER_HINT", bewegungstyp="ISOLATION"
        )
        uebungen_map = {
            u.bezeichnung: u
            for u in [brust, schulter, seitheben, trizeps, fliegende, ruecken, bizeps]
        }
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Schulterdrücken", sets=4),
                        _make_exercise("Seitheben", sets=4),
                        _make_exercise("Trizeps Pushdown", sets=4),
                        _make_exercise("Fliegende", sets=4),
                    ],
                ),
                _make_session(
                    "Pull",
                    [
                        _make_exercise("Rudern", sets=4),
                        _make_exercise("Bizepscurls", sets=3),
                    ],
                ),
            ]
        )
        available = [
            "Bankdrücken",
            "Schulterdrücken",
            "Seitheben",
            "Trizeps Pushdown",
            "Fliegende",
            "Rudern",
            "Bizepscurls",
            "Face Pull",
        ]
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map, available)
        assert warnings == []
        assert fix_count >= 1
        # Mindestens eine Push-Isolation wurde durch Pull-Isolation ersetzt
        ex_names = [ex["exercise_name"] for s in plan["sessions"] for ex in s["exercises"]]
        assert "Face Pull" in ex_names

    def test_compounds_werden_nicht_ersetzt(self):
        """Nur Isolation-Übungen werden beim Auto-Fix getauscht."""
        # Nur Compounds im Push-Teil → kein Auto-Fix möglich → Warnung
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        schulter = UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        ruecken = UebungFactory(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN"
        )
        UebungFactory(
            bezeichnung="Face Pull", muskelgruppe="SCHULTER_HINT", bewegungstyp="ISOLATION"
        )
        uebungen_map = {u.bezeichnung: u for u in [brust, schulter, ruecken]}
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=5),
                        _make_exercise("Schulterdrücken", sets=5),
                    ],
                ),
                _make_session(
                    "Pull",
                    [_make_exercise("Rudern", sets=3)],
                ),
            ]
        )
        available = ["Bankdrücken", "Schulterdrücken", "Rudern", "Face Pull"]
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map, available)
        # Kein Auto-Fix, da keine Push-Isolation vorhanden → Ratio > 1.8 → Warnung
        assert len(warnings) == 1
        assert fix_count == 0
        # Compounds bleiben unverändert
        ex_names = [ex["exercise_name"] for s in plan["sessions"] for ex in s["exercises"]]
        assert "Bankdrücken" in ex_names
        assert "Schulterdrücken" in ex_names

    def test_kein_pull_kein_crash(self):
        """Plan nur mit Push-Übungen → keine Division durch 0."""
        brust = UebungFactory(
            bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN"
        )
        uebungen_map = {brust.bezeichnung: brust}
        plan = _make_plan([_make_session("Push", [_make_exercise("Bankdrücken", sets=4)])])
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map)
        assert warnings == []
        assert fix_count == 0

    def test_nur_legs_kein_crash(self):
        """Plan nur mit Legs → keine Push/Pull-Warnung."""
        quad = UebungFactory(
            bezeichnung="Kniebeuge", muskelgruppe="BEINE_QUAD", bewegungstyp="BEUGEN"
        )
        uebungen_map = {quad.bezeichnung: quad}
        plan = _make_plan([_make_session("Legs", [_make_exercise("Kniebeuge", sets=4)])])
        warnings, fix_count = _check_push_pull_ratio(plan, uebungen_map)
        assert warnings == []
        assert fix_count == 0

    def test_integration_in_validate_plan_structure(self):
        """Push/Pull-Check läuft im Entry-Point mit."""
        UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST", bewegungstyp="DRUECKEN")
        UebungFactory(
            bezeichnung="Schulterdrücken", muskelgruppe="SCHULTER_VORN", bewegungstyp="DRUECKEN"
        )
        UebungFactory(
            bezeichnung="Seitheben", muskelgruppe="SCHULTER_SEIT", bewegungstyp="ISOLATION"
        )
        UebungFactory(bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="ZIEHEN")
        plan = _make_plan(
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Schulterdrücken", sets=4),
                        _make_exercise("Seitheben", sets=4),
                    ],
                ),
                _make_session(
                    "Pull",
                    [_make_exercise("Rudern", sets=3)],
                ),
            ]
        )
        warnings, fixes = validate_plan_structure(plan)
        assert any("Push/Pull" in w for w in warnings)
