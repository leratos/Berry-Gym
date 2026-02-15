"""
Tests für ai_coach/plan_generator.py – _save_plan_to_db Methode.

Fokus:
- Batch-Lookup: genau 1 DB-Query für alle Übungen (kein N+1)
- Fuzzy-Match: case-insensitiv + strip-whitespace findet Übungen
- Not-found: fehlerhafte Namen werden still übersprungen (kein Crash)
- Korrekte Plan/PlanUebung-Erstellung
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from ai_coach.plan_generator import PlanGenerator
from core.models import Plan, PlanUebung
from core.tests.factories import UebungFactory, UserFactory


def _make_plan_json(plan_name: str, sessions: list[dict]) -> dict:
    """Minimal-Plan-JSON wie es der LLM-Output liefert."""
    return {
        "plan_name": plan_name,
        "plan_description": "Test-Beschreibung",
        "sessions": sessions,
    }


def _make_session(day_name: str, exercises: list[dict]) -> dict:
    return {
        "day_name": day_name,
        "exercises": exercises,
    }


def _make_exercise(name: str, sets: int = 3, reps: str = "8-10") -> dict:
    return {
        "exercise_name": name,
        "order": 1,
        "sets": sets,
        "reps": reps,
        "rest_seconds": 90,
        "rpe_target": 7,
        "notes": "",
    }


@pytest.mark.django_db
class TestSavePlanToDbBatchLookup:
    """_save_plan_to_db darf nicht pro Übung eine separate DB-Query absetzen."""

    def test_single_query_for_all_exercises(self):
        """Alle Übungen werden in exakt 1 Query geladen, unabhängig von der Anzahl."""
        user = UserFactory()
        uebungen = [UebungFactory(bezeichnung=f"Übung Batch {i}") for i in range(10)]

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Batch-Test-Plan",
            [
                _make_session(
                    "Tag A",
                    [_make_exercise(u.bezeichnung) for u in uebungen],
                )
            ],
        )

        # Queries während _save_plan_to_db zählen
        # Erwartete Queries: User laden (1) + Übungen laden (1) + Plan create (1)
        #                    + N × PlanUebung.create – letztere sind Writes, keine Reads
        # Wichtig: Übungen-Lookup = exakt 1 Query, nicht 10
        with CaptureQueriesContext(connection) as ctx:
            plan_ids = generator._save_plan_to_db(plan_json)

        uebung_queries = [
            q
            for q in ctx.captured_queries
            if "uebung" in q["sql"].lower() and "SELECT" in q["sql"].upper()
        ]
        assert (
            len(uebung_queries) == 1
        ), f"Erwartet: 1 Übungs-Query, gefunden: {len(uebung_queries)}\n" + "\n".join(
            q["sql"] for q in uebung_queries
        )

        assert len(plan_ids) == 1
        assert PlanUebung.objects.filter(plan_id=plan_ids[0]).count() == 10


@pytest.mark.django_db
class TestSavePlanToDbFuzzyMatch:
    """Fuzzy-Match (case-insensitiv + strip) findet Übungen trotz LLM-Abweichungen."""

    def test_lowercase_name_matches(self):
        """LLM liefert lowercase, DB hat Großschreibung → trotzdem Match."""
        user = UserFactory()
        uebung = UebungFactory(bezeichnung="Bankdrücken")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Fuzzy-Test",
            [_make_session("Tag A", [_make_exercise("bankdrücken")])],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        pu = PlanUebung.objects.filter(plan_id=plan_ids[0]).first()
        assert pu is not None, "PlanUebung wurde nicht erstellt (Fuzzy-Match fehlgeschlagen)"
        assert pu.uebung == uebung

    def test_whitespace_stripped(self):
        """LLM liefert Namen mit führenden/nachgestellten Leerzeichen."""
        user = UserFactory()
        uebung = UebungFactory(bezeichnung="Kniebeuge")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Whitespace-Test",
            [_make_session("Tag A", [_make_exercise("  Kniebeuge  ")])],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        pu = PlanUebung.objects.filter(plan_id=plan_ids[0]).first()
        assert pu is not None, "PlanUebung nicht erstellt (Whitespace-Strip fehlgeschlagen)"
        assert pu.uebung == uebung

    def test_mixed_case_and_whitespace(self):
        """Kombination aus Großschreibung-Abweichung und Whitespace."""
        user = UserFactory()
        uebung = UebungFactory(bezeichnung="Kreuzheben")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Mixed-Test",
            [_make_session("Tag A", [_make_exercise(" KREUZHEBEN ")])],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        pu = PlanUebung.objects.filter(plan_id=plan_ids[0]).first()
        assert pu is not None
        assert pu.uebung == uebung


@pytest.mark.django_db
class TestSavePlanToDbNotFound:
    """Nicht gefundene Übungen werden übersprungen – kein Crash, kein falsches Objekt."""

    def test_unknown_exercise_skipped(self):
        """LLM halluziniert eine Übung die nicht in der DB ist → wird übersprungen."""
        user = UserFactory()
        uebung_real = UebungFactory(bezeichnung="Klimmzug")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "NotFound-Test",
            [
                _make_session(
                    "Tag A",
                    [
                        _make_exercise("Klimmzug"),  # existiert
                        _make_exercise("Quanten-Burpee-Deluxe"),  # existiert nicht
                    ],
                )
            ],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        assert len(plan_ids) == 1
        plan_uebungen = PlanUebung.objects.filter(plan_id=plan_ids[0])
        assert (
            plan_uebungen.count() == 1
        ), "Nur die echte Übung darf im Plan sein, nicht die halluzinierte"
        assert plan_uebungen.first().uebung == uebung_real

    def test_all_unknown_creates_empty_plan(self):
        """Plan wird trotzdem angelegt, auch wenn alle Übungen fehlen."""
        user = UserFactory()

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Komplett-Unbekannt",
            [_make_session("Tag A", [_make_exercise("Nicht-Existent-Übung-123")])],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        assert len(plan_ids) == 1
        assert Plan.objects.filter(id=plan_ids[0]).exists()
        assert PlanUebung.objects.filter(plan_id=plan_ids[0]).count() == 0


@pytest.mark.django_db
class TestSavePlanToDbSplitPlan:
    """Split-Pläne (mehrere Sessions) bekommen gemeinsame gruppe_id."""

    def test_split_creates_multiple_plans_with_shared_gruppe(self):
        """3-Session-Split → 3 Plan-Objekte mit gleicher gruppe_id."""
        user = UserFactory()
        UebungFactory(bezeichnung="Schulterdrücken")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "PPL-Plan",
            [
                _make_session("Push", [_make_exercise("Schulterdrücken")]),
                _make_session("Pull", [_make_exercise("Schulterdrücken")]),
                _make_session("Legs", [_make_exercise("Schulterdrücken")]),
            ],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        assert len(plan_ids) == 3
        plans = Plan.objects.filter(id__in=plan_ids)

        gruppe_ids = set(p.gruppe_id for p in plans)
        assert len(gruppe_ids) == 1, "Alle Split-Pläne müssen dieselbe gruppe_id haben"

        namen = sorted(p.name for p in plans)
        assert namen == ["PPL-Plan - Legs", "PPL-Plan - Pull", "PPL-Plan - Push"]
