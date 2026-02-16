"""
Tests für ai_coach/plan_generator.py – _save_plan_to_db Methode.

Fokus:
- Batch-Lookup: genau 1 DB-Query für alle Übungen (kein N+1)
- Fuzzy-Match: case-insensitiv + strip-whitespace findet Übungen
- Not-found: fehlerhafte Namen werden still übersprungen (kein Crash)
- Korrekte Plan/PlanUebung-Erstellung
- LLM-Client: JSON-Mode und Reasoning-Off für Gemini 2.5 Flash
"""

from unittest.mock import MagicMock, patch

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


class TestOpenRouterGeminiConfig:
    """
    Stellt sicher dass _generate_with_openrouter die Gemini-2.5-Flash-spezifischen
    Parameter korrekt setzt: JSON-Mode und Reasoning-Off (kein Thinking-Overhead).
    """

    def _make_mock_response(self, content: str = '{"plan_name": "Test", "sessions": []}'):
        """Minimal-Mock für OpenAI chat.completions.create Response."""
        mock_choice = MagicMock()
        mock_choice.message.content = content

        mock_usage = MagicMock()
        mock_usage.total_tokens = 100
        mock_usage.prompt_tokens = 80
        mock_usage.completion_tokens = 20

        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = mock_usage
        return mock_resp

    def test_json_mode_is_set(self):
        """response_format muss {"type": "json_object"} sein – kein Markdown-Wrapping."""
        from ai_coach.llm_client import LLMClient

        client = LLMClient(use_openrouter=True)

        with patch.object(client, "_get_openrouter_client") as mock_get_client:
            mock_openai = MagicMock()
            mock_openai.chat.completions.create.return_value = self._make_mock_response()
            mock_get_client.return_value = mock_openai

            client.generate_training_plan([{"role": "user", "content": "Test"}], max_tokens=100)

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            assert call_kwargs.get("response_format") == {
                "type": "json_object"
            }, "response_format muss json_object sein – verhindert Markdown-Wrapping"

    def test_reasoning_effort_none_is_set(self):
        """extra_body.reasoning.effort muss 'none' sein – deaktiviert Thinking-Tokens."""
        from ai_coach.llm_client import LLMClient

        client = LLMClient(use_openrouter=True)

        with patch.object(client, "_get_openrouter_client") as mock_get_client:
            mock_openai = MagicMock()
            mock_openai.chat.completions.create.return_value = self._make_mock_response()
            mock_get_client.return_value = mock_openai

            client.generate_training_plan([{"role": "user", "content": "Test"}], max_tokens=100)

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            extra_body = call_kwargs.get("extra_body", {})
            assert (
                extra_body.get("reasoning", {}).get("effort") == "none"
            ), "reasoning.effort=none muss gesetzt sein – verhindert versteckte Thinking-Tokens"

    def test_default_model_is_gemini_2_5_flash(self):
        """Standard-Modell muss google/gemini-2.5-flash sein (nicht Llama 3.1 70B)."""
        from ai_coach import ai_config
        from ai_coach.llm_client import LLMClient

        client = LLMClient(use_openrouter=True)

        with patch.object(client, "_get_openrouter_client") as mock_get_client:
            mock_openai = MagicMock()
            mock_openai.chat.completions.create.return_value = self._make_mock_response()
            mock_get_client.return_value = mock_openai

            client.generate_training_plan([{"role": "user", "content": "Test"}], max_tokens=100)

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            assert call_kwargs.get("model") == ai_config.OPENROUTER_MODEL
            assert "gemini-2.5-flash" in call_kwargs.get(
                "model", ""
            ), f"Erwartet Gemini 2.5 Flash, gefunden: {call_kwargs.get('model')}"


@pytest.mark.django_db
class TestSmartRetry:
    """
    _fix_invalid_exercises() soll halluzinierte Übungen korrekt ersetzen.

    Wichtigster Fix: generate_training_plan() gibt {"response": {...}} zurück –
    der Code muss result["response"] auspacken, nicht result direkt als replacements
    verwenden.
    """

    def _make_llm_client_mock(self, replacements: dict):
        """
        Erstellt einen gemockten LLMClient der generate_training_plan() mit
        {"response": replacements, ...} beantwortet.
        """
        mock_client = MagicMock()
        mock_client.generate_training_plan.return_value = {
            "response": replacements,
            "cost": 0.001,
            "model": "google/gemini-2.5-flash",
        }
        return mock_client

    def test_hallucinated_exercise_is_replaced(self):
        """
        Halluzinierte Übung wird korrekt durch valide Alternative ersetzt.
        Prüft insbesondere: result["response"] wird ausgepackt, nicht result selbst.
        """
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test-Plan",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [
                        {"exercise_name": "Cable Fly (Halluziniert)", "sets": 3, "reps": "10-12"},
                        {"exercise_name": "Bankdrücken (Langhantel)", "sets": 4, "reps": "6-8"},
                    ],
                }
            ],
        }

        errors = [
            "Session 1, Übung 1: 'Cable Fly (Halluziniert)' nicht verfügbar "
            "(Equipment fehlt oder Übung existiert nicht)"
        ]
        available = ["Bankdrücken (Langhantel)", "Fliegende (Kurzhantel)", "Kniebeuge (Langhantel)"]

        mock_client = self._make_llm_client_mock(
            {"Cable Fly (Halluziniert)": "Fliegende (Kurzhantel)"}
        )

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=available,
            llm_client=mock_client,
        )

        exercises = result["sessions"][0]["exercises"]
        names = [ex["exercise_name"] for ex in exercises]

        assert "Fliegende (Kurzhantel)" in names, "Ersetzte Übung muss im Plan sein"
        assert (
            "Cable Fly (Halluziniert)" not in names
        ), "Halluzinierte Übung darf nicht mehr im Plan sein"
        assert "Bankdrücken (Langhantel)" in names, "Valide Übungen dürfen nicht verändert werden"
        mock_client.generate_training_plan.assert_called_once()

    def test_no_invalid_exercises_means_no_retry(self):
        """
        Wenn keine 'nicht verfügbar'-Fehler in der Fehlerliste sind,
        wird generate_training_plan() gar nicht aufgerufen.
        """
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test-Plan",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [
                        {"exercise_name": "Bankdrücken (Langhantel)", "sets": 4, "reps": "6-8"}
                    ],
                }
            ],
        }

        # Fehler der kein "nicht verfügbar" enthält (z.B. Duplikat)
        errors = ["Session 1: Doppelte Übungen gefunden: Bankdrücken (Langhantel)"]

        mock_client = MagicMock()

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=["Bankdrücken (Langhantel)"],
            llm_client=mock_client,
        )

        mock_client.generate_training_plan.assert_not_called()
        # Plan bleibt unverändert
        assert result == plan_json

    def test_multiple_hallucinations_all_replaced(self):
        """Mehrere halluzinierte Übungen werden in einem Retry alle ersetzt."""
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [
                        {"exercise_name": "Fake Übung A", "sets": 3, "reps": "10-12"},
                        {"exercise_name": "Fake Übung B", "sets": 3, "reps": "10-12"},
                    ],
                }
            ],
        }

        errors = [
            "Session 1, Übung 1: 'Fake Übung A' nicht verfügbar (Equipment fehlt oder Übung existiert nicht)",
            "Session 1, Übung 2: 'Fake Übung B' nicht verfügbar (Equipment fehlt oder Übung existiert nicht)",
        ]
        available = ["Fliegende (Kurzhantel)", "Seitheben (Kurzhantel)"]

        mock_client = self._make_llm_client_mock(
            {
                "Fake Übung A": "Fliegende (Kurzhantel)",
                "Fake Übung B": "Seitheben (Kurzhantel)",
            }
        )

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=available,
            llm_client=mock_client,
        )

        names = [ex["exercise_name"] for ex in result["sessions"][0]["exercises"]]
        assert names == ["Fliegende (Kurzhantel)", "Seitheben (Kurzhantel)"]
        # Nur 1 LLM-Call – alle Halluzinationen auf einmal
        mock_client.generate_training_plan.assert_called_once()
