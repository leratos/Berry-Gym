"""
Tests für ai_coach/plan_generator.py – _save_plan_to_db Methode.

Fokus:
- Batch-Lookup: genau 1 DB-Query für alle Übungen (kein N+1)
- Fuzzy-Match: case-insensitiv + strip-whitespace findet Übungen
- Not-found: fehlerhafte Namen werden still übersprungen (kein Crash)
- Korrekte Plan/PlanUebung-Erstellung
- LLM-Client: JSON-Mode und Reasoning-Off für Gemini 2.5 Flash
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import pytest

from ai_coach.plan_generator import PlanGenerator
from core.models import Plan, PlanUebung
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


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

    def test_notes_branch_is_executed_for_existing_exercise(self):
        """Übungs-Notiz im JSON darf den Save-Pfad nicht stören (deckt notes-Branch ab)."""
        user = UserFactory()
        exercise = UebungFactory(bezeichnung="Rudern")

        generator = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Notes-Branch-Test",
            [
                _make_session(
                    "Tag A",
                    [
                        {
                            **_make_exercise("Rudern"),
                            "notes": "Ellbogen eng am Körper halten",
                        }
                    ],
                )
            ],
        )

        plan_ids = generator._save_plan_to_db(plan_json)

        pu = PlanUebung.objects.filter(plan_id=plan_ids[0]).first()
        assert pu is not None
        assert pu.uebung == exercise


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


@pytest.mark.django_db
class TestSavePlanToDbDefaults:
    """Default-Werte greifen, wenn optionale Felder im Exercise-JSON fehlen."""

    def test_missing_optional_fields_use_defaults(self):
        user = UserFactory()
        exercise = UebungFactory(bezeichnung="Kabelrudern")

        generator = PlanGenerator(user_id=user.id)
        plan_json = {
            "plan_name": "Defaults-Plan",
            "sessions": [
                {
                    "day_name": "Tag A",
                    "exercises": [
                        {
                            "exercise_name": "Kabelrudern",
                        }
                    ],
                }
            ],
        }

        plan_ids = generator._save_plan_to_db(plan_json)

        pu = PlanUebung.objects.filter(plan_id=plan_ids[0]).first()
        assert pu is not None
        assert pu.uebung == exercise
        assert pu.reihenfolge == 1
        assert pu.saetze_ziel == 3
        assert pu.wiederholungen_ziel == "8-10"
        assert pu.pausenzeit == 120


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

    def test_invalid_replacements_response_returns_original_plan(self):
        """Leere/ungültige Replacements-Response führt zu unverändertem Plan."""
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [{"exercise_name": "Fake Übung A", "sets": 3, "reps": "10-12"}],
                }
            ],
        }
        errors = [
            "Session 1, Übung 1: 'Fake Übung A' nicht verfügbar "
            "(Equipment fehlt oder Übung existiert nicht)"
        ]

        mock_client = MagicMock()
        mock_client.generate_training_plan.return_value = {"response": []}

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=["Bankdrücken (Langhantel)"],
            llm_client=mock_client,
        )

        assert result == plan_json

    def test_non_dict_replacements_response_returns_original_plan(self):
        """Nicht-Dict-Replacements werden ignoriert und geben den Plan unverändert zurück."""
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [{"exercise_name": "Fake Übung A", "sets": 3, "reps": "10-12"}],
                }
            ],
        }
        errors = [
            "Session 1, Übung 1: 'Fake Übung A' nicht verfügbar "
            "(Equipment fehlt oder Übung existiert nicht)"
        ]

        mock_client = MagicMock()
        mock_client.generate_training_plan.return_value = {"response": "not-a-dict"}

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=["Bankdrücken (Langhantel)"],
            llm_client=mock_client,
        )

        assert result == plan_json

    def test_retry_exception_returns_original_plan(self):
        """LLM-Fehler im Smart-Retry wird gefangen und gibt den ursprünglichen Plan zurück."""
        user = UserFactory()
        generator = PlanGenerator(user_id=user.id)

        plan_json = {
            "plan_name": "Test",
            "sessions": [
                {
                    "day_name": "Push",
                    "exercises": [{"exercise_name": "Fake Übung B", "sets": 3, "reps": "10-12"}],
                }
            ],
        }
        errors = [
            "Session 1, Übung 1: 'Fake Übung B' nicht verfügbar "
            "(Equipment fehlt oder Übung existiert nicht)"
        ]

        mock_client = MagicMock()
        mock_client.generate_training_plan.side_effect = RuntimeError("llm down")

        result = generator._fix_invalid_exercises(
            plan_json=plan_json,
            errors=errors,
            available_exercises=["Bankdrücken (Langhantel)"],
            llm_client=mock_client,
        )

        assert result == plan_json


class TestDynamicMaxTokens:
    """_get_max_tokens() gibt plan-typ-spezifische Werte zurück."""

    def test_ppl_gets_more_tokens_than_2er_split(self):
        """PPL hat bis zu 6 Sessions – braucht deutlich mehr Tokens als 2er-Split."""
        ppl = PlanGenerator(user_id=1, plan_type="ppl")
        split2 = PlanGenerator(user_id=1, plan_type="2er-split")

        assert ppl._get_max_tokens() > split2._get_max_tokens(), (
            f"PPL ({ppl._get_max_tokens()}) muss mehr Tokens bekommen als 2er-Split "
            f"({split2._get_max_tokens()})"
        )

    def test_unknown_plan_type_returns_safe_default(self):
        """Unbekannter plan_type fällt auf sicheren Default zurück (kein KeyError)."""
        gen = PlanGenerator(user_id=1, plan_type="irgendwas-unbekanntes")
        tokens = gen._get_max_tokens()

        # Phase 29.2: Default großzügig genug für einen mehrtägigen Plan.
        assert tokens >= 5000, f"Default muss mindestens 5000 sein, war: {tokens}"
        assert tokens <= 12000, f"Default sollte unter 12000 bleiben, war: {tokens}"

    def test_aliases_have_same_token_count(self):
        """ppl und push-pull-legs sind Aliase → gleiche Token-Anzahl."""
        ppl = PlanGenerator(user_id=1, plan_type="ppl")
        ppl_alias = PlanGenerator(user_id=1, plan_type="push-pull-legs")

        assert (
            ppl._get_max_tokens() == ppl_alias._get_max_tokens()
        ), "ppl und push-pull-legs müssen gleich viele Tokens bekommen"

    def test_4er_split_more_than_3er_split(self):
        """4er-Split hat eine Session mehr → mehr Tokens."""
        split3 = PlanGenerator(user_id=1, plan_type="3er-split")
        split4 = PlanGenerator(user_id=1, plan_type="4er-split")

        assert split4._get_max_tokens() > split3._get_max_tokens()

    def test_all_plan_types_have_sane_token_ceiling(self):
        """Jeder Plan-Typ bekommt eine plausible Token-Obergrenze.

        Phase 29.2: max_tokens ist eine Obergrenze, kein Kostenfaktor –
        abgerechnet werden nur tatsächlich erzeugte Tokens. Die Werte dürfen
        daher großzügig sein, müssen aber in einem plausiblen Rahmen bleiben.
        """
        plan_types = [
            "ganzkörper",
            "2er-split",
            "upper-lower",
            "3er-split",
            "4er-split",
            "ppl",
            "push-pull-legs",
        ]
        for pt in plan_types:
            gen = PlanGenerator(user_id=1, plan_type=pt)
            tokens = gen._get_max_tokens()
            assert (
                tokens <= 12000
            ), f"Plan-Typ '{pt}' hat {tokens} Tokens – unplausibel hoch (max 12000)"
            assert (
                tokens >= 3000
            ), f"Plan-Typ '{pt}' hat nur {tokens} Tokens – zu niedrig (min 3000)"

    def test_3er_split_has_headroom_for_three_full_days(self):
        """Phase 29.2 (F2): 3er-Split braucht deutlich mehr als das alte Limit.

        Der Live-Diagnose-Lauf lief mit completion_tokens exakt gegen das alte
        3000-Limit und schnitt den dritten Trainingstag ab.
        """
        gen = PlanGenerator(user_id=1, plan_type="3er-split")
        tokens = gen._get_max_tokens()
        assert (
            tokens >= 5000
        ), f"3er-Split muss klar über dem alten 3000-Limit liegen, war: {tokens}"


class TestPeriodizationHelpers:
    """Phase 4: Branch-Coverage für periodisierungsbezogene Helper."""

    def test_calculate_weekly_rpe_deload_and_floor(self):
        gen = PlanGenerator(user_id=1)

        # Deload reduziert, aber fällt nicht unter 6.5
        assert (
            gen._calculate_weekly_rpe("linear", 7.0, pos_in_block=2, block=1, is_deload=True) == 6.5
        )

    def test_calculate_weekly_rpe_wellenfoermig_and_block(self):
        gen = PlanGenerator(user_id=1)

        wellen = gen._calculate_weekly_rpe(
            "wellenfoermig", 7.8, pos_in_block=2, block=1, is_deload=False
        )
        block = gen._calculate_weekly_rpe("block", 7.8, pos_in_block=2, block=3, is_deload=False)

        assert wellen == 8.1
        assert block == 8.1

    def test_calculate_weekly_rpe_fallback_linear(self):
        gen = PlanGenerator(user_id=1)

        rpe = gen._calculate_weekly_rpe("unbekannt", 7.5, pos_in_block=3, block=1, is_deload=False)
        assert rpe == 7.8

    def test_week_focus_variants(self):
        gen = PlanGenerator(user_id=1)

        assert (
            gen._week_focus("linear", block=1, is_deload=True, profile="kraft")
            == "Deload & Technik"
        )
        assert "Welle Block 2" in gen._week_focus(
            "wellenfoermig", block=2, is_deload=False, profile="hypertrophie"
        )
        assert (
            gen._week_focus("block", block=2, is_deload=False, profile="kraft")
            == "Kraft/Intensität"
        )
        assert "Linearer Aufbau" in gen._week_focus(
            "linear", block=3, is_deload=False, profile="definition"
        )

    def test_periodization_note_variants(self):
        gen = PlanGenerator(user_id=1)

        assert "Wellenförmig" in gen._periodization_note("wellenfoermig", block=1, pos_in_block=2)
        assert gen._periodization_note("block", block=1, pos_in_block=2) == (
            "Volumen priorisieren, Technik stabilisieren"
        )
        assert gen._periodization_note("block", block=2, pos_in_block=2) == (
            "Kraftfokus: schwerere Compounds"
        )
        assert gen._periodization_note("block", block=3, pos_in_block=2) == (
            "Top-Phase: niedrigeres Volumen, höhere RPE"
        )
        assert (
            gen._periodization_note("linear", block=1, pos_in_block=2)
            == "Progressiv +0.5 RPE / Block"
        )


class TestProgressCallback:
    """progress_callback wird an den richtigen Stellen aufgerufen."""

    def test_callback_is_invoked_on_generate(self):
        """
        _progress() leitet Aufrufe an den übergebenen callback weiter.
        Ohne callback: keine Exception (no-op).
        """
        calls = []

        def callback(percent: int, step: str):
            calls.append((percent, step))

        gen = PlanGenerator(user_id=1, progress_callback=callback)
        gen._progress(35, "Test-Schritt")

        assert calls == [(35, "Test-Schritt")]

    def test_no_callback_is_noop(self):
        """Kein callback übergeben → _progress() löst keine Exception aus."""
        gen = PlanGenerator(user_id=1)  # kein progress_callback
        gen._progress(50, "Kein Callback vorhanden")  # darf nicht crashen

    def test_callback_receives_all_progress_stages(self):
        """Alle 6 definierten Stages (5, 20, 35, 70, 82, 90) werden gemeldet."""
        received = []

        def cb(percent, step):
            received.append(percent)

        gen = PlanGenerator(user_id=1, progress_callback=cb)

        # Alle definierten Stufen direkt aufrufen
        for percent, step in [
            (5, "Analysiere Trainingsdaten..."),
            (20, "Erstelle personalisierten Prompt..."),
            (35, "KI generiert Plan (kann 15–20s dauern)..."),
            (70, "Antwort erhalten – validiere Plan..."),
            (82, "Korrigiere halluzinierte Übungen..."),
            (90, "Speichere Plan in Datenbank..."),
        ]:
            gen._progress(percent, step)

        assert received == [
            5,
            20,
            35,
            70,
            82,
            90,
        ], f"Nicht alle Progress-Stufen wurden gemeldet. Erhalten: {received}"


class TestGenerateEntryPaths:
    """Phase 1: Frühe Guard-Rail-Pfade in generate() absichern."""

    def test_generate_uses_existing_django_context_without_db_client(self):
        """Wenn Django-Kontext erkannt wird, darf kein DatabaseClient gestartet werden."""
        gen = PlanGenerator(user_id=1)

        with (
            patch("ai_coach.plan_generator.hasattr", return_value=True),
            patch.object(
                gen, "_generate_with_existing_django", return_value={"success": True}
            ) as mock_gen,
            patch("ai_coach.plan_generator.DatabaseClient") as mock_db_client,
        ):
            result = gen.generate(save_to_db=False)

        assert result == {"success": True}
        mock_gen.assert_called_once_with(False)
        mock_db_client.assert_not_called()

    def test_generate_uses_database_client_in_cli_mode(self):
        """Ohne Django-Kontext wird der DatabaseClient-Kontextmanager verwendet."""
        gen = PlanGenerator(user_id=1)

        with (
            patch("ai_coach.plan_generator.hasattr", return_value=False),
            patch.object(
                gen, "_generate_with_existing_django", return_value={"success": True}
            ) as mock_gen,
            patch("ai_coach.plan_generator.DatabaseClient") as mock_db_client,
        ):
            result = gen.generate(save_to_db=False)

        assert result == {"success": True}
        mock_db_client.assert_called_once()
        mock_gen.assert_called_once_with(False)

    def test_generate_reraises_internal_errors(self):
        """Fehler im inneren Flow werden nach Logging erneut geworfen."""
        gen = PlanGenerator(user_id=1)

        with (
            patch("ai_coach.plan_generator.hasattr", return_value=True),
            patch.object(gen, "_generate_with_existing_django", side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                gen.generate(save_to_db=False)


class TestGenerateWithExistingDjangoGuardRails:
    """Phase 1: Frühe Exit-Pfade in _generate_with_existing_django()."""

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_empty_llm_response_returns_error_payload(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Leere LLM-Response soll als kontrollierter Fehler-Return enden."""
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [{"content": "system"}, {"content": "user"}]

        mock_llm = mock_llm_cls.return_value
        mock_llm.generate_training_plan.return_value = {"response": None, "usage": {}, "cost": 0.0}

        gen = PlanGenerator(user_id=1)
        with patch.object(gen, "_log_ki_cost") as mock_log_cost:
            result = gen._generate_with_existing_django(save_to_db=False)

        assert result["success"] is False
        assert result["plan_data"] is None
        assert "LLM Response war leer" in result["errors"][0]
        mock_log_cost.assert_called_once()


class TestGenerateWithExistingDjangoPhase2:
    """Phase 2: Fallback- und Validierungs-Fehlerpfade in _generate_with_existing_django()."""

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_schema_mismatch_uses_openrouter_fallback(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Schema-Mismatch im ersten Call triggert OpenRouter-Fallback und nutzt zweiten Response."""
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 5
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        first_client = MagicMock()
        first_client.generate_training_plan.return_value = {
            "response": {"unexpected": "schema"},
            "usage": {},
            "cost": 0.01,
        }
        first_client.validate_plan.return_value = (True, [])

        fallback_client = MagicMock()
        fallback_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "Fallback Plan",
                "sessions": [{"day_name": "A", "exercises": []}],
                "plan_description": "desc",
            },
            "usage": {},
            "cost": 0.02,
        }

        mock_llm_cls.side_effect = [first_client, fallback_client]

        gen = PlanGenerator(user_id=1, use_openrouter=False, fallback_to_openrouter=True)
        with (
            patch.object(gen, "_log_ki_cost") as mock_log_cost,
            patch.object(gen, "_validate_weakness_coverage", return_value=[]),
            patch.object(gen, "_format_macrocycle_summary", return_value="summary"),
        ):
            result = gen._generate_with_existing_django(save_to_db=False)

        assert result["success"] is True
        assert result["plan_data"]["plan_name"] == "Fallback Plan"
        assert mock_llm_cls.call_count == 2
        assert mock_log_cost.call_count == 2

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_invalid_after_retry_returns_error_payload(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Wenn Plan nach Smart-Retry weiter invalid bleibt, wird success=False mit Errors geliefert."""
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        plan_json = {
            "plan_name": "Invalid Plan",
            "sessions": [{"day_name": "A", "exercises": [{"exercise_name": "Fake"}]}],
        }
        llm_client.generate_training_plan.return_value = {
            "response": plan_json,
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.side_effect = [
            (False, ["erste Fehlerwelle"]),
            (False, ["zweite Fehlerwelle"]),
        ]

        gen = PlanGenerator(user_id=1)
        with patch.object(gen, "_fix_invalid_exercises", return_value=plan_json):
            result = gen._generate_with_existing_django(save_to_db=False)

        assert result["success"] is False
        assert result["errors"] == ["zweite Fehlerwelle"]
        assert result["plan_data"] == plan_json

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_coverage_warnings_trigger_hard_fail_and_no_save(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Phase 31.1: Coverage-Verletzung führt zu success=False + kein Save.

        Symmetrie zur 30.1-Cap-Hard-Fail-Logik. Vor 31.1 wurde der Plan
        trotz Coverage-Warnings gespeichert (success=True, warnings
        landeten in result["coverage_warnings"]). Das hat die UX-Lesart
        „ist trotzdem verwendbar" produziert – genau in dem Fall, wo
        eine echte Schwäche ohne Volumen bleibt, also das falsche Signal.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": ["Bauch: Untertrainiert (0)"]}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "trainingsplan",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.return_value = (True, [])

        coverage_warnings = [
            "⚠️ Untertrainiert-Volumen zu niedrig: BAUCH hat nur 4 Sätze (Ziel: mind. 6)",
            "⚠️ Untertrainiert-Volumen zu niedrig: BEINE_HAM hat nur 4 Sätze (Ziel: mind. 6)",
        ]

        gen = PlanGenerator(user_id=1, target_profile="hypertrophie", plan_type="3er-split")
        with (
            patch.object(gen, "_validate_weakness_coverage", return_value=coverage_warnings),
            patch.object(gen, "_save_plan_to_db", return_value=[11]) as mock_save,
            patch.object(gen, "_format_macrocycle_summary", return_value="summary"),
        ):
            result = gen._generate_with_existing_django(save_to_db=True)

        assert result["success"] is False
        assert result["errors"] == coverage_warnings
        # Plan wird NICHT gespeichert – Symmetrie zur Cap-Verletzung.
        mock_save.assert_not_called()

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_combined_coverage_and_cap_violations_both_in_errors(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Phase 31.1 / Konzept §5 F-31-4: bei gleichzeitiger Verletzung von
        Coverage UND Cap werden BEIDE Fehlerklassen in result["errors"]
        zurückgegeben, damit der User in einem Retry beide adressieren kann.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "Kombi-Fehler-Plan",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.return_value = (True, [])

        coverage_warnings = [
            "⚠️ Untertrainiert-Volumen zu niedrig: BAUCH hat nur 4 Sätze (Ziel: mind. 6)"
        ]
        cap_warnings = [
            "⚠️ Übertraining-Cap überschritten: Brust hat im Plan 8 Sätze/Woche (Cap: 5)"
        ]

        gen = PlanGenerator(user_id=1, plan_type="3er-split")
        with (
            patch.object(gen, "_validate_weakness_coverage", return_value=coverage_warnings),
            patch.object(gen, "_validate_overtraining_cap", return_value=cap_warnings),
            patch.object(gen, "_save_plan_to_db") as mock_save,
        ):
            result = gen._generate_with_existing_django(save_to_db=True)

        assert result["success"] is False
        # Beide Fehlerklassen werden gleichzeitig zurückgegeben (F-31-4).
        assert any("BAUCH" in err for err in result["errors"])
        assert any("Cap überschritten" in err for err in result["errors"])
        # Reihenfolge: erst Coverage, dann Cap.
        assert result["errors"][0] == coverage_warnings[0]
        assert result["errors"][-1] == cap_warnings[0]
        mock_save.assert_not_called()

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_success_path_without_warnings_saves_and_humanizes_name(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Erfolgs-Pfad ohne Coverage-/Cap-Warnings: generischer LLM-Name wird
        durch Profile/Split/Fokus ersetzt und der Plan landet in der DB.

        Vor 31.1 deckte ``test_success_path_with_coverage_warnings_and_save_to_db``
        diese Naming-Pfade in einem Test ab, der gleichzeitig Coverage-
        Warnings simulierte und trotzdem Save erwartete. Nach dem Hard-Fail-
        Switch ist beides nicht mehr kombinierbar – Naming + Save laufen
        nur noch ohne Warnings durch.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": ["Bauch: Untertrainiert (0)"]}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "trainingsplan",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.return_value = (True, [])

        gen = PlanGenerator(user_id=1, target_profile="hypertrophie", plan_type="3er-split")
        with (
            patch.object(gen, "_validate_weakness_coverage", return_value=[]),
            patch.object(gen, "_save_plan_to_db", return_value=[11]) as mock_save,
            patch.object(gen, "_format_macrocycle_summary", return_value="summary"),
        ):
            result = gen._generate_with_existing_django(save_to_db=True)

        assert result["success"] is True
        assert result["plan_ids"] == [11]
        assert "beschreibung" in result["plan_data"]
        assert result["plan_data"]["plan_name"] != "trainingsplan"
        assert "Hypertrophie-3ER/SPLIT" in result["plan_data"]["plan_name"]
        assert "Fokus Bauch" in result["plan_data"]["plan_name"]
        mock_save.assert_called_once()

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_truncated_response_returns_error_and_does_not_save(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Phase 29.2 (F2): abgeschnittene LLM-Antwort → success=False, kein Save.

        Ein als truncated markiertes llm_result darf nicht still als
        unvollständiger Plan in der DB landen.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "Abgeschnittener Plan",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
            "truncated": True,
        }

        gen = PlanGenerator(user_id=1, plan_type="3er-split")
        with patch.object(gen, "_save_plan_to_db") as mock_save:
            result = gen._generate_with_existing_django(save_to_db=True)

        assert result["success"] is False
        assert any("abgeschnitten" in err.lower() for err in result["errors"])
        mock_save.assert_not_called()

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_overtraining_cap_violation_returns_error_and_does_not_save(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Phase 30.1 (P1-Review): cap-Verletzung muss success=False ergeben
        und ein save_to_db=True darf NICHT zum Speichern führen – sonst ist
        die Cap nur eine kosmetische Warnung, keine Sicherheits-Regel.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {"weaknesses": []}

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 12
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "Cap-Verletzer",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.return_value = (True, [])

        fake_caps = [
            {
                "key": "BRUST",
                "name": "Brust",
                "ist_sets": 28,
                "soll_max": 25,
                "weekly_cap": 5,
            }
        ]
        fake_warning = (
            "⚠️ Übertraining-Cap überschritten: Brust hat im Plan 8 Sätze/Woche "
            "(Cap: 5, aktuell 28/30 T, Soll-Max 25)"
        )

        gen = PlanGenerator(user_id=1, plan_type="3er-split")
        with (
            patch.object(gen, "_compute_overtrained_caps", return_value=fake_caps),
            patch.object(gen, "_validate_weakness_coverage", return_value=[]),
            patch.object(gen, "_validate_overtraining_cap", return_value=[fake_warning]),
            patch.object(gen, "_save_plan_to_db") as mock_save,
        ):
            result = gen._generate_with_existing_django(save_to_db=True)

        assert result["success"] is False
        assert any("Cap überschritten" in err for err in result["errors"])
        mock_save.assert_not_called()

    @patch("ai_coach.plan_generator.LLMClient")
    @patch("ai_coach.plan_generator.PromptBuilder")
    @patch("ai_coach.plan_generator.TrainingAnalyzer")
    def test_undertrained_helper_failure_falls_back_to_analysis_weaknesses(
        self, mock_analyzer_cls, mock_builder_cls, mock_llm_cls
    ):
        """Phase 30.2 P1-Review: liefert ``_compute_undertrained_targets``
        ``None`` (Stats-Collector-Quelle nicht verfügbar), MUSS der Aufrufer
        auf ``analysis_data["weaknesses"]`` zurückfallen – sowohl für den
        Prompt-Pflicht-Block als auch für den Coverage-Check. Sonst wäre
        das Schwächen-Enforcement bei Helfer-Ausfall komplett aus.
        """
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.analyze.return_value = {
            "weaknesses": ["Bauch: Untertrainiert (data_analyzer-Fallback)"]
        }

        mock_builder = mock_builder_cls.return_value
        mock_builder.get_available_exercises_for_user.return_value = ["Übung A"] * 5
        mock_builder.build_messages.return_value = [
            {"content": "system"},
            {"content": "user"},
        ]

        llm_client = mock_llm_cls.return_value
        llm_client.generate_training_plan.return_value = {
            "response": {
                "plan_name": "Test Plan",
                "sessions": [{"day_name": "A", "exercises": []}],
            },
            "usage": {},
            "cost": 0.01,
        }
        llm_client.validate_plan.return_value = (True, [])

        gen = PlanGenerator(user_id=1, plan_type="3er-split")
        with (
            patch.object(gen, "_compute_undertrained_targets", return_value=None),
            patch.object(gen, "_compute_overtrained_caps", return_value=[]),
            patch.object(gen, "_validate_weakness_coverage", return_value=[]) as mock_validate,
            patch.object(gen, "_save_plan_to_db", return_value=[]),
            patch.object(gen, "_format_macrocycle_summary", return_value="summary"),
        ):
            gen._generate_with_existing_django(save_to_db=False)

        # build_messages soll mit undertrained=None aufgerufen werden,
        # damit prompt_builder den Fallback auf analysis_data["weaknesses"]
        # aktiviert.
        build_messages_kwargs = mock_builder.build_messages.call_args.kwargs
        assert build_messages_kwargs.get("undertrained") is None

        # Validator soll die data_analyzer-Fallback-Weakness sehen, NICHT eine
        # leere Liste (das wäre die regressionierte Pre-Fix-Variante).
        validate_args = mock_validate.call_args.args
        weaknesses_passed = (
            validate_args[1]
            if len(validate_args) > 1
            else mock_validate.call_args.kwargs.get("weaknesses", [])
        )
        assert any(
            "data_analyzer-Fallback" in w for w in weaknesses_passed
        ), f"Validator sollte data_analyzer-Liste sehen, bekam: {weaknesses_passed}"


# ---------------------------------------------------------------------------
# Phase 5.3 – Plan-Name Eindeutigkeit (inline-Logik in generate())
# ---------------------------------------------------------------------------


def _make_session_v2(name: str, exercises: list[dict]) -> dict:
    return {"session_name": name, "exercises": exercises}


def _make_exercise_v2(name: str) -> dict:
    return {"exercise_name": name, "sets": 3, "reps": "8-12", "rest_seconds": 90}


class TestPlanNameFallback:
    """
    Die Fallback-Logik in generate() ersetzt generische LLM-Namen.
    Da die Logik inline ist, testen wir über die Hilfsfunktion die
    denselben generic_names-Set und die Längen-Prüfung nachbildet.

    Wir testen das Verhalten der Klasse direkt: PlanGenerator kennt
    self.target_profile und self.plan_type – damit kann der Test
    zeigen, dass zwei verschiedene Profile verschiedene Namen erzeugen.
    """

    GENERIC_NAMES = {
        "mein trainingsplan",
        "trainingsplan",
        "3er split",
        "3er-split",
        "push pull legs",
        "push/pull/legs",
        "hypertrophie plan",
        "kraftplan",
    }

    def _apply_name_fallback(self, generator: "PlanGenerator", plan_json: dict) -> str:
        """
        Wendet dieselbe Fallback-Logik an die in generate() Schritt 5d steht,
        ohne generate() komplett aufzurufen (kein LLM nötig).
        """
        from datetime import date as _date

        raw_name = plan_json.get("plan_name", "").strip()
        if not raw_name or raw_name.lower() in self.GENERIC_NAMES or len(raw_name) < 10:
            weaknesses = plan_json.get("_test_weaknesses", [])
            focus = ""
            if weaknesses and ":" in weaknesses[0]:
                focus = f" – Fokus {weaknesses[0].split(':')[0].strip()}"
            profile_label = {
                "kraft": "Kraft",
                "hypertrophie": "Hypertrophie",
                "definition": "Definition",
            }.get(generator.target_profile, generator.target_profile.capitalize())
            plan_json["plan_name"] = (
                f"{profile_label}-{generator.plan_type.upper().replace('-', '/')}"
                f"{focus} ({_date.today().strftime('%d.%m.%Y')})"
            )
        return plan_json["plan_name"]

    def test_generischer_name_wird_ersetzt(self):
        """Generische LLM-Namen → Fallback mit Profil + Datum."""
        gen = PlanGenerator(user_id=999, target_profile="hypertrophie", plan_type="2er-split")

        for bad_name in ["Trainingsplan", "hypertrophie plan", "mein trainingsplan"]:
            plan_json = _make_plan_json(bad_name, [])
            result = self._apply_name_fallback(gen, plan_json)
            assert result != bad_name.lower(), f"Generischer Name '{bad_name}' wurde nicht ersetzt"
            assert len(result) >= 10

    def test_spezifischer_name_bleibt_erhalten(self):
        """Spezifischer Name mit ≥10 Zeichen wird nicht überschrieben."""
        gen = PlanGenerator(user_id=999, target_profile="kraft", plan_type="ganzkörper")

        plan_json = _make_plan_json("Push-Pull Fokus Schulter & Rücken", [])
        result = self._apply_name_fallback(gen, plan_json)
        assert result == "Push-Pull Fokus Schulter & Rücken"

    def test_zwei_profile_erzeugen_verschiedene_namen(self):
        """Kraft vs. Hypertrophie → unterschiedliche Fallback-Namen."""
        gen_kraft = PlanGenerator(user_id=999, target_profile="kraft", plan_type="ganzkörper")
        gen_hyp = PlanGenerator(user_id=999, target_profile="hypertrophie", plan_type="ganzkörper")

        p1 = _make_plan_json("trainingsplan", [])
        p2 = _make_plan_json("trainingsplan", [])
        n1 = self._apply_name_fallback(gen_kraft, p1)
        n2 = self._apply_name_fallback(gen_hyp, p2)
        assert n1 != n2, f"Beide haben denselben Namen: '{n1}'"

    def test_kurzer_name_unter_10_zeichen_wird_ersetzt(self):
        """Name < 10 Zeichen gilt als generisch."""
        gen = PlanGenerator(user_id=999, target_profile="definition", plan_type="ppl")

        plan_json = _make_plan_json("Plan A", [])
        result = self._apply_name_fallback(gen, plan_json)
        assert result != "Plan A"
        assert "Definition" in result


# ---------------------------------------------------------------------------
# Phase 5.3 – _validate_weakness_coverage (echte Methode)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateWeaknessCoverage:
    """
    _validate_weakness_coverage(plan_json, weaknesses: list[str]) → list[str]
    Signatur bestätigt: nimmt weaknesses-Liste direkt, nicht analysis_data.
    """

    def test_keine_schwachstellen_gibt_leere_liste(self):
        """weaknesses=[] → immer leere Warnings-Liste."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json("Test", [_make_session("A", [])])
        warnings = gen._validate_weakness_coverage(plan_json, weaknesses=[])
        assert warnings == []

    def test_unbekanntes_label_kein_false_positive(self):
        """Label das nicht in LABEL_TO_KEYS steht → keine Warning."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json("Test", [_make_session("A", [])])
        # "Griffkraft" ist kein bekanntes Label → soll ignoriert werden
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Griffkraft: Untertrainiert"]
        )
        assert warnings == []

    def test_abgedeckte_schwachstelle_keine_warning(self):
        """
        Plan enthält Bankdrücken (BRUST) → BRUST-Schwachstelle ist abgedeckt.
        Hinweis: _validate_weakness_coverage macht DB-Lookup für Übungsnamen.
        """
        UebungFactory(bezeichnung="Bankdrücken", gewichts_typ="GESAMT")
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("A", [_make_exercise("Bankdrücken", sets=6)])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Brust: Untertrainiert (2 Sätze/Woche)"]
        )
        # Brust abgedeckt UND mit genug Volumen (6 Sätze) → keine Warning
        assert len(warnings) == 0

    def test_fehlende_schwachstelle_erzeugt_warning(self):
        """
        Plan hat keine Bauch-Übung, aber 'Bauch' ist Schwachstelle → Warning.
        """
        UebungFactory(bezeichnung="Bankdrücken", gewichts_typ="GESAMT")
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("A", [_make_exercise("Bankdrücken")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Bauch: Untertrainiert (0 Sätze/Woche)"]
        )
        # Bauch fehlt im Plan → mindestens 1 Warning
        assert len(warnings) >= 1
        assert any("Bauch" in w or "bauch" in w.lower() for w in warnings)

    def test_weakness_without_colon_is_ignored(self):
        """Eintrag ohne ':' wird still ignoriert (Skip-Zweig)."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json("Test", [_make_session("A", [])])

        warnings = gen._validate_weakness_coverage(
            plan_json,
            weaknesses=["NurTextOhneDoppelpunkt"],
        )

        assert warnings == []

    def test_hilfsmuskeln_only_nicht_als_coverage(self):
        """Phase 13.2: Übung mit hilfsmuskeln=KEY aber muskelgruppe≠KEY ist NICHT covered."""
        # Hanging Leg Raises: muskelgruppe=BAUCH, hilfsmuskeln=["HUEFTBEUGER"]
        UebungFactory(
            bezeichnung="Hanging Leg Raises",
            muskelgruppe="BAUCH",
            hilfsmuskeln=["HUEFTBEUGER"],
            gewichts_typ="KOERPERGEWICHT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("Legs", [_make_exercise("Hanging Leg Raises")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Hüftbeuger: Untertrainiert (0 Sätze/Woche)"]
        )
        # Nur als Hilfsmuskel → Warning
        assert len(warnings) >= 1
        assert any("Hüftbeuger" in w for w in warnings)

    def test_primaere_muskelgruppe_ist_coverage(self):
        """Phase 13.2: Übung mit muskelgruppe=KEY gilt als Coverage."""
        UebungFactory(
            bezeichnung="Hüftbeuger-Stretch",
            muskelgruppe="HUEFTBEUGER",
            gewichts_typ="KOERPERGEWICHT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("Legs", [_make_exercise("Hüftbeuger-Stretch", sets=6)])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Hüftbeuger: Untertrainiert (0 Sätze/Woche)"]
        )
        assert len(warnings) == 0

    def test_abgedeckte_aber_zu_wenig_volumen_warnt(self):
        """Phase 29.3: Muskelgruppe vorhanden, aber unter MIN_SETS_PER_WEAKNESS
        Sätzen → explizite Volumen-Warnung (Präsenz allein reicht nicht)."""
        UebungFactory(
            bezeichnung="Crunch",
            muskelgruppe="BAUCH",
            gewichts_typ="KOERPERGEWICHT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        # Nur 3 Sätze Bauch – abgedeckt, aber zu wenig (Ziel: 6)
        plan_json = _make_plan_json(
            "Test",
            [_make_session("Core", [_make_exercise("Crunch", sets=3)])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["BAUCH: Untertrainiert (0 Sätze/Woche)"]
        )
        assert len(warnings) >= 1
        assert any("Volumen zu niedrig" in w for w in warnings)

    def test_auto_fix_fills_presence_but_volume_warns(self):
        """Phase 29.3 (P1-Review): wenn eine Muskelgruppe komplett fehlt und
        der Auto-Fix nur ~3 Sätze einfügt, muss die Volumen-Warnung trotzdem
        feuern – sonst entsteht ein falsches "covered"-Ergebnis ohne Hinweis,
        dass MIN_SETS_PER_WEAKNESS unterschritten ist.
        """
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        UebungFactory(
            bezeichnung="Crunch",
            muskelgruppe="BAUCH",
            gewichts_typ="KOERPERGEWICHT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        # Plan hat NUR Bankdrücken → BAUCH komplett fehlend
        plan_json = _make_plan_json(
            "Test",
            [_make_session("Push", [_make_exercise("Bankdrücken", sets=3)])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json,
            weaknesses=["BAUCH: Untertrainiert (0 Sätze/Woche)"],
            available_exercises=["Bankdrücken", "Crunch"],
        )

        # Auto-Fix sollte Crunch eingefügt haben (Präsenz hergestellt)
        all_ex = [e for s in plan_json["sessions"] for e in s["exercises"]]
        assert any(
            e["exercise_name"] == "Crunch" for e in all_ex
        ), "Auto-Fix sollte Crunch einsetzen"
        # ABER: < MIN_SETS_PER_WEAKNESS → Volumen-Warnung muss trotzdem feuern
        assert any(
            "Auto-Fix" in w and "Volumen" in w for w in warnings
        ), f"Volumen-Warnung nach Auto-Fix erwartet, bekam: {warnings}"

    def test_db_constant_label_hueftbeuger_resolves(self):
        """Bug-Fix: data_analyzer liefert 'HUEFTBEUGER: Untertrainiert' (DB-Konstante).
        LABEL_TO_KEYS muss auch 'hueftbeuger' (ohne Umlaut) als Key erkennen."""
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("Push", [_make_exercise("Bankdrücken")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["HUEFTBEUGER: Untertrainiert (nur 154 eff. Wdh vs. Ø 286)"]
        )
        # DB-Konstante als Label → muss erkannt werden und Warning erzeugen
        assert len(warnings) >= 1
        assert any("HUEFTBEUGER" in w for w in warnings)

    def test_db_constant_label_schulter_hint_resolves(self):
        """Bug-Fix: data_analyzer liefert 'SCHULTER_HINT: Untertrainiert' (DB-Konstante).
        LABEL_TO_KEYS muss auch 'schulter_hint' als Key erkennen."""
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("Push", [_make_exercise("Bankdrücken")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["SCHULTER_HINT: Untertrainiert (nur 26 eff. Wdh vs. Ø 286)"]
        )
        assert len(warnings) >= 1
        assert any("SCHULTER_HINT" in w for w in warnings)

    def test_hilfsmuskeln_only_warning_text(self):
        """Phase 13.2: Warning-Text enthält 'nur als Hilfsmuskel'."""
        UebungFactory(
            bezeichnung="Kreuzheben",
            muskelgruppe="BEINE_HAM",
            hilfsmuskeln=["RUECKEN_UNTEN", "PO"],
            gewichts_typ="GESAMT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        plan_json = _make_plan_json(
            "Test",
            [_make_session("Pull", [_make_exercise("Kreuzheben")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json,
            weaknesses=["Unterer Rücken: Untertrainiert (1 Satz/Woche)"],
        )
        assert len(warnings) >= 1
        assert any("Hilfsmuskel" in w for w in warnings)


# ---------------------------------------------------------------------------
# Phase 30.1: Übertraining-Cap (compute + validate)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComputeOvertrainedCaps:
    """``_compute_overtrained_caps`` liefert die Liste der überlasteten
    Muskelgruppen mit wöchentlichem Cap, gespeist aus dem Stats-Collector.
    """

    def _seed_brust_overtrained(self, user):
        """Hilfsmethode: legt 28 BRUST-Sätze in den letzten 30 Tagen an
        (gross-max 25 → Übertraining)."""
        uebung = UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=2), dauer_minuten=60
        )
        for _ in range(28):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=80, rpe=8)

    def test_compute_returns_brust_cap(self):
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        self._seed_brust_overtrained(user)

        caps = gen._compute_overtrained_caps()
        keys = [c["key"] for c in caps]
        assert "BRUST" in keys
        brust = next(c for c in caps if c["key"] == "BRUST")
        assert brust["ist_sets"] == 28
        assert brust["soll_max"] == 25  # gross-Klasse
        # Cap-Formel: max(2, 25 // 5) = 5
        assert brust["weekly_cap"] == 5

    def test_compute_empty_for_no_overtraining(self):
        """User ohne Überlast → leere Liste, keine Exception."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        # Keine Sätze in der DB
        caps = gen._compute_overtrained_caps()
        assert caps == []

    def test_compute_min_cap_floor_of_two(self):
        """Cap fällt nie unter 2 Sätze – sonst wäre die Muskelgruppe nicht
        mehr trainierbar."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        # haltung-Klasse (HUEFTBEUGER) hat soll_max 12 → 12//5 = 2 → floor greift
        uebung = UebungFactory(bezeichnung="Knee Raises", muskelgruppe="HUEFTBEUGER")
        einheit = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=2), dauer_minuten=45
        )
        for _ in range(15):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=0, rpe=7)

        caps = gen._compute_overtrained_caps()
        hueft = next((c for c in caps if c["key"] == "HUEFTBEUGER"), None)
        assert hueft is not None
        # 12 // 5 = 2, max(2, 2) = 2
        assert hueft["weekly_cap"] >= 2


@pytest.mark.django_db
class TestValidateOvertrainingCap:
    """``_validate_overtraining_cap`` summiert Sätze pro Muskelgruppe im
    Plan und warnt bei Cap-Überschreitung."""

    def test_empty_caps_returns_empty(self):
        gen = PlanGenerator(user_id=1)
        plan_json = _make_plan_json("Test", [_make_session("A", [])])
        assert gen._validate_overtraining_cap(plan_json, []) == []

    def test_violation_triggers_warning(self):
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        UebungFactory(
            bezeichnung="Schrägbankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        # Plan hat 4+4 = 8 Sätze Brust, Cap ist 5 → Verletzung
        plan_json = _make_plan_json(
            "Test",
            [
                _make_session(
                    "Push",
                    [
                        _make_exercise("Bankdrücken", sets=4),
                        _make_exercise("Schrägbankdrücken", sets=4),
                    ],
                )
            ],
        )
        caps = [
            {
                "key": "BRUST",
                "name": "Brust",
                "ist_sets": 28,
                "soll_max": 25,
                "weekly_cap": 5,
            }
        ]

        warnings = gen._validate_overtraining_cap(plan_json, caps)
        assert len(warnings) == 1
        assert "Brust" in warnings[0]
        assert "Cap überschritten" in warnings[0]

    def test_respected_cap_no_warning(self):
        UebungFactory(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)

        # Plan hat 4 Sätze Brust, Cap ist 5 → eingehalten
        plan_json = _make_plan_json(
            "Test",
            [_make_session("Push", [_make_exercise("Bankdrücken", sets=4)])],
        )
        caps = [
            {
                "key": "BRUST",
                "name": "Brust",
                "ist_sets": 28,
                "soll_max": 25,
                "weekly_cap": 5,
            }
        ]

        warnings = gen._validate_overtraining_cap(plan_json, caps)
        assert warnings == []


# ---------------------------------------------------------------------------
# Phase 30.2: Untertrainiert-Quelle aus collect_muscle_balance
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComputeUndertrainedTargets:
    """``_compute_undertrained_targets`` liest die Untertrainiert-Liste aus
    derselben ``collect_muscle_balance``-Quelle wie der PDF-Report.
    """

    def test_compute_returns_bauch_target(self):
        """BAUCH ist mittel (10–18); 9 Sätze < 10 → Untertrainiert."""
        uebung = UebungFactory(bezeichnung="Crunch", muskelgruppe="BAUCH")
        user = UserFactory()
        einheit = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=2), dauer_minuten=45
        )
        for _ in range(9):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=0, rpe=8)

        gen = PlanGenerator(user_id=user.id)
        targets = gen._compute_undertrained_targets()
        keys = [t["key"] for t in targets]
        assert "BAUCH" in keys
        bauch = next(t for t in targets if t["key"] == "BAUCH")
        assert bauch["ist_sets"] == 9
        assert bauch["soll_min"] == 10  # mittel-min

    def test_compute_empty_when_all_in_range(self):
        """Ohne Daten oder mit Sätzen im Optimum → leere Liste."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        assert gen._compute_undertrained_targets() == []

    def test_hueftbeuger_not_flagged_at_9_sets(self):
        """Phase 30.0-Konsequenz: HUEFTBEUGER ist `haltung` (6–12) – 9 Sätze
        liegen im Optimum und werden NICHT mehr als untertrainiert geflaggt
        (die alte Report-Default-Schwelle 12–20 hatte das fälschlich getan)."""
        uebung = UebungFactory(bezeichnung="Knee Raises", muskelgruppe="HUEFTBEUGER")
        user = UserFactory()
        einheit = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=2), dauer_minuten=30
        )
        for _ in range(9):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=0, rpe=7)

        gen = PlanGenerator(user_id=user.id)
        targets = gen._compute_undertrained_targets()
        keys = [t["key"] for t in targets]
        assert "HUEFTBEUGER" not in keys

    def test_compute_returns_none_on_exception(self):
        """Phase 30.2 P1-Review: bei Exception in collect_muscle_balance
        liefert der Helper ``None`` (Sentinel für Fallback), NICHT eine
        leere Liste. Damit kann der Aufrufer den Fehler vom Erfolgs-
        „keine Untertrainiert"-Fall unterscheiden und auf die
        data_analyzer-Heuristik zurückfallen, statt das Schwächen-
        Enforcement stillschweigend zu deaktivieren.
        """
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        with patch(
            "core.export.stats_collector.collect_muscle_balance",
            side_effect=RuntimeError("simulated stats-collector failure"),
        ):
            result = gen._compute_undertrained_targets()
        assert result is None


class TestUndertrainedTargetsToStrings:
    """``_undertrained_targets_to_strings`` formatiert strukturierte Targets
    in das von ``_build_weakness_block`` / ``_validate_weakness_coverage``
    erwartete String-Format (DB-Konstante + 'Untertrainiert')."""

    def test_format_contains_key_and_numbers(self):
        targets = [
            {"key": "BEINE_HAM", "name": "Hamstrings", "ist_sets": 9, "soll_min": 12},
            {"key": "BAUCH", "name": "Bauch", "ist_sets": 9, "soll_min": 10},
        ]
        strings = PlanGenerator._undertrained_targets_to_strings(targets)
        assert len(strings) == 2
        # DB-Konstante als Präfix (resolve_weakness_keys versteht das seit 29.3)
        assert strings[0].startswith("BEINE_HAM:")
        assert strings[1].startswith("BAUCH:")
        # "Untertrainiert" als Marker, Ist + Soll als Zahlen vorhanden
        for s in strings:
            assert "Untertrainiert" in s
        assert "9" in strings[0] and "12" in strings[0]
        assert "9" in strings[1] and "10" in strings[1]

    def test_empty_input_returns_empty_list(self):
        assert PlanGenerator._undertrained_targets_to_strings([]) == []


# ---------------------------------------------------------------------------
# Phase 30.3: Plateau-/Konsolidierungs-Hints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComputePlateauHints:
    """``_compute_plateau_hints`` filtert die Plateau-Analyse auf jene
    Status-Keys, bei denen Volumen-Steigerung kontraproduktiv ist."""

    def _fake_plateau(self, *statuses):
        return [
            {
                "uebung": f"Übung-{i}",
                "muskelgruppe": f"MG-{i}",
                "status": s,
                "status_label": f"Label-{s}",
            }
            for i, s in enumerate(statuses)
        ]

    def test_filters_to_no_volume_push_statuses(self):
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        # Status-Keys MÜSSEN exakt mit ``classify_progression_status``-Output
        # übereinstimmen (advanced_stats.py Docstring). Tippfehler hier =
        # Filter trifft in Produktion nie.
        fake = self._fake_plateau(
            "active_progression",  # gefiltert raus
            "consolidation",  # behalten
            "active_progression_paused",  # behalten
            "observe",  # gefiltert raus
            "plateau",  # behalten
            "plateau_long",  # behalten
            "regression",  # behalten
            "pause",  # gefiltert raus
        )
        with patch(
            "core.utils.advanced_stats.calculate_plateau_analysis",
            return_value=fake,
        ):
            hints = gen._compute_plateau_hints()
        kept = {h["status_label"] for h in hints}
        assert len(hints) == 5
        assert "Label-consolidation" in kept
        assert "Label-active_progression_paused" in kept
        assert "Label-plateau" in kept
        assert "Label-plateau_long" in kept
        assert "Label-regression" in kept
        # Diese dürfen NICHT in der Liste sein:
        assert "Label-active_progression" not in kept
        assert "Label-observe" not in kept
        assert "Label-pause" not in kept

    def test_no_volume_push_status_keys_are_canonical(self):
        """Schutz gegen die ursprüngliche 30.3-Bug-Klasse: alle Filter-Keys
        müssen vom ``classify_progression_status``-Klassifikator tatsächlich
        emittiert werden. Quelle: Docstring der Funktion (advanced_stats.py).
        Ohne diesen Test bleiben Tippfehler unentdeckt, weil sowohl
        Produktions-Code als auch parametrische Tests konsistent denselben
        falschen String verwenden können.
        """
        canonical = frozenset(
            {
                "regression",
                "active_progression",
                "observe",
                "pause",
                "consolidation",
                "active_progression_paused",
                "plateau_light",
                "plateau",
                "plateau_long",
                "no_data",
            }
        )
        non_canonical = PlanGenerator._PLATEAU_NO_VOLUME_PUSH_STATUS - canonical
        assert non_canonical == frozenset(), (
            "_PLATEAU_NO_VOLUME_PUSH_STATUS enthält Keys, die "
            "classify_progression_status nicht emittiert: "
            f"{sorted(non_canonical)}"
        )

    def test_returns_empty_on_exception(self):
        """Helfer-Fehler darf nicht hochpropagieren – pre-30.3 gab es
        keinen Plateau-Hint, Ausfall fällt also auf pre-30.3 zurück."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        with patch(
            "core.utils.advanced_stats.calculate_plateau_analysis",
            side_effect=RuntimeError("simulated plateau failure"),
        ):
            assert gen._compute_plateau_hints() == []

    def test_empty_plateau_analysis_returns_empty(self):
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        with patch(
            "core.utils.advanced_stats.calculate_plateau_analysis",
            return_value=[],
        ):
            assert gen._compute_plateau_hints() == []


# ---------------------------------------------------------------------------
# Phase 30.4: Trainings-Kontext (Fatigue + Frequency + Push/Pull)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComputeTrainingContext:
    """``_compute_training_context`` liefert drei unabhängige Adaptions-
    Hinweise. Jeder ist optional; Fehler in einer Komponente lässt die
    anderen unberührt."""

    def test_frequency_hint_emitted_below_two(self):
        """Bei < 2 Sessions/Woche und Nicht-Ganzkörper-Plan → Frequenz-Hint."""
        user = UserFactory()
        # 4 Sessions in 30 Tagen → ~0.9/Woche → < 2 → Hint erwartet
        for _ in range(4):
            TrainingseinheitFactory(
                user=user, datum=timezone.now() - timedelta(days=5), dauer_minuten=45
            )

        gen = PlanGenerator(user_id=user.id, plan_type="3er-split")
        # Andere Komponenten neutralisieren, damit der Test fokussiert ist.
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=[],
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={"fatigue_index": 0, "bewertung": "", "empfehlung": ""},
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["frequency_hint"] is not None
        assert "Ganzkörper" in ctx["frequency_hint"]

    def test_frequency_hint_skipped_for_ganzkoerper_plan(self):
        """Wenn der User bereits einen Ganzkörper-Plan generiert, ist
        die niedrige Frequenz schon adressiert → kein Frequenz-Hint."""
        user = UserFactory()
        for _ in range(4):
            TrainingseinheitFactory(
                user=user, datum=timezone.now() - timedelta(days=5), dauer_minuten=45
            )

        gen = PlanGenerator(user_id=user.id, plan_type="ganzkörper")
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=[],
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={"fatigue_index": 0, "bewertung": "", "empfehlung": ""},
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["frequency_hint"] is None

    def test_push_pull_hint_emitted_when_unbalanced(self):
        """collect_push_pull liefert ``empfehlung`` für nicht-„Ausgewogen"-
        Fälle – der wird 1:1 in den Hint übernommen."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        fake_balance = [
            {"key": "BRUST", "name": "Brust", "saetze": 28, "status": "uebertrainiert"},
            {"key": "RUECKEN_LAT", "name": "Lat", "saetze": 14, "status": "optimal"},
        ]
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=fake_balance,
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={"fatigue_index": 0, "bewertung": "", "empfehlung": ""},
            ),
        ):
            ctx = gen._compute_training_context()

        # Ratio 28/14 = 2.0 → "Leicht Push-betont" oder "Zu viel Push"
        # je nach Schwelle in collect_push_pull. Hauptsache: Hint da.
        assert ctx["push_pull_hint"] is not None
        # Empfehlung sollte „Pull" enthalten (Aufstockungs-Hinweis)
        assert "Pull" in ctx["push_pull_hint"]

    def test_push_pull_hint_suppressed_when_balanced(self):
        """„Ausgewogen" → kein Hint, der LLM hat nichts zu adressieren."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        fake_balance = [
            {"key": "BRUST", "name": "Brust", "saetze": 12, "status": "optimal"},
            {"key": "RUECKEN_LAT", "name": "Lat", "saetze": 12, "status": "optimal"},
        ]
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=fake_balance,
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={"fatigue_index": 0, "bewertung": "", "empfehlung": ""},
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["push_pull_hint"] is None

    def test_fatigue_hint_emitted_above_threshold(self):
        """Ermüdungs-Index ≥ 60 → Fatigue-Hint mit empfehlung-Text."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        fake_fatigue = {
            "fatigue_index": 75,
            "bewertung": "Hoch",
            "empfehlung": "Deload-Woche dringend empfohlen.",
        }
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=[],
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value=fake_fatigue,
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["fatigue_hint"] is not None
        assert "75" in ctx["fatigue_hint"]
        assert "Hoch" in ctx["fatigue_hint"]
        assert "Deload" in ctx["fatigue_hint"]

    def test_fatigue_hint_suppressed_below_threshold(self):
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                return_value=[],
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={
                    "fatigue_index": 30,
                    "bewertung": "Niedrig",
                    "empfehlung": "Alles im grünen Bereich.",
                },
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["fatigue_hint"] is None

    def test_components_are_independent(self):
        """Schlägt eine Komponente fehl (RuntimeError), bleiben die
        anderen unberührt – pro Komponente eigenes try/except."""
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        # Push/Pull lassen wir krachen; Frequenz und Fatigue sollen
        # trotzdem berechnet werden.
        with (
            patch(
                "core.export.stats_collector.collect_muscle_balance",
                side_effect=RuntimeError("push/pull failure"),
            ),
            patch(
                "core.utils.advanced_stats.calculate_fatigue_index",
                return_value={
                    "fatigue_index": 80,
                    "bewertung": "Hoch",
                    "empfehlung": "Pause.",
                },
            ),
        ):
            ctx = gen._compute_training_context()

        assert ctx["push_pull_hint"] is None  # gescheitert
        assert ctx["fatigue_hint"] is not None  # erfolgreich trotzdem


class TestHumanizePlanName:
    """Tests für _humanize_muskelgruppe und _humanize_plan_name."""

    def test_humanize_muskelgruppe_known(self):
        from ai_coach.plan_generator import _humanize_muskelgruppe

        assert _humanize_muskelgruppe("SCHULTER_HINT") == "Hintere Schulter"
        assert _humanize_muskelgruppe("HUEFTBEUGER") == "Hüftbeuger"
        assert _humanize_muskelgruppe("BAUCH") == "Bauch"

    def test_humanize_muskelgruppe_unknown_passthrough(self):
        from ai_coach.plan_generator import _humanize_muskelgruppe

        assert _humanize_muskelgruppe("UNKNOWN_KEY") == "UNKNOWN_KEY"

    def test_humanize_plan_name_db_constants(self):
        from ai_coach.plan_generator import _humanize_plan_name

        name = "Hypertrophie-UPPER/LOWER – Fokus BAUCH_HUEFTBEUGER_SCHULTER_HINT (28.03.2026)"
        result = _humanize_plan_name(name)
        assert "Bauch" in result
        assert "Hüftbeuger" in result
        assert "Hintere Schulter" in result
        assert "BAUCH" not in result
        assert "HUEFTBEUGER" not in result
        assert "SCHULTER_HINT" not in result

    def test_humanize_plan_name_already_clean(self):
        from ai_coach.plan_generator import _humanize_plan_name

        name = "Hypertrophie-3ER/SPLIT – Fokus Bauch (28.03.2026)"
        assert _humanize_plan_name(name) == name

    def test_humanize_plan_name_single_constant(self):
        from ai_coach.plan_generator import _humanize_plan_name

        name = "Plan – Fokus SCHULTER_HINT"
        result = _humanize_plan_name(name)
        assert result == "Plan – Fokus Hintere Schulter"


class TestPhase4HelperContracts:
    """Phase 4 (Welle 2): direkte Contracts für Mikrozyklus/Progression-Helper."""

    def test_build_microcycle_template_kraft_profile(self):
        gen = PlanGenerator(user_id=1)

        result = gen._build_microcycle_template("kraft")

        assert result["target_profile"] == "kraft"
        assert result["rep_range"] == "3-6"
        assert result["rpe_range"] == "7.5-9"
        assert "Woche 4/8/12" in result["deload_rules"]
        assert "Maximalkraft" in result["notes"]

    def test_build_microcycle_template_unknown_profile_uses_fallback_defaults(self):
        gen = PlanGenerator(user_id=1)

        result = gen._build_microcycle_template("custom")

        # target_profile bleibt Eingabe, Inhalte fallen auf hypertrophie-Defaults zurück
        assert result["target_profile"] == "custom"
        assert result["rep_range"] == "6-12"
        assert result["rpe_range"] == "7-8.5"
        assert "Muskelaufbau" in result["notes"]

    def test_build_progression_strategy_uses_profile_and_sets_per_session(self):
        gen = PlanGenerator(user_id=1, sets_per_session=22)

        result = gen._build_progression_strategy("definition")

        assert result["target_profile"] == "definition"
        assert "RPE Ziel 6.5-8" in result["rpe_guardrails"]
        assert "~22 Sätzen pro Tag" in result["volume"]
        assert "Deload" in result["progression"]


class TestFormatMacrocycleSummary:
    """Phase 13.3: _format_macrocycle_summary erzeugt profilabhängige Texte."""

    def _make_plan_with_meta(self, profile, periodization):
        gen = PlanGenerator(user_id=1, target_profile=profile, periodization=periodization)
        plan_json = {
            "target_profile": profile,
            "periodization": periodization,
            "deload_weeks": [4, 8, 12],
        }
        gen._ensure_periodization_metadata(plan_json)
        return gen, plan_json

    def test_kraft_hat_rpe_progression(self):
        gen, plan = self._make_plan_with_meta("kraft", "linear")
        summary = gen._format_macrocycle_summary(plan)
        assert "RPE" in summary
        assert "Gewicht priorisieren" in summary
        # Kein ">12 Wdh" für Kraft
        assert ">12 Wdh" not in summary

    def test_hypertrophie_hat_wdh_progression(self):
        gen, plan = self._make_plan_with_meta("hypertrophie", "linear")
        summary = gen._format_macrocycle_summary(plan)
        assert ">12 Wdh" in summary or ">12" in summary
        assert "+1 Satz" in summary

    def test_definition_hat_pausen_reduktion(self):
        gen, plan = self._make_plan_with_meta("definition", "linear")
        summary = gen._format_macrocycle_summary(plan)
        assert "Halte" in summary or "Pausen" in summary
        assert "60-90s" in summary

    def test_wellenfoermig_hat_heavy_medium_light(self):
        gen, plan = self._make_plan_with_meta("hypertrophie", "wellenfoermig")
        summary = gen._format_macrocycle_summary(plan)
        assert "Heavy" in summary
        assert "Medium" in summary
        assert "Light" in summary

    def test_block_hat_block_phasen(self):
        gen, plan = self._make_plan_with_meta("kraft", "block")
        summary = gen._format_macrocycle_summary(plan)
        assert "Block 1" in summary or "Volumen" in summary
        assert "Block 2" in summary or "Kraft" in summary

    def test_deload_volume_aus_macrocycle(self):
        gen, plan = self._make_plan_with_meta("hypertrophie", "linear")
        summary = gen._format_macrocycle_summary(plan)
        # Deload-Volumen sollte 80% sein (aus macrocycle abgeleitet)
        assert "80%" in summary


@pytest.mark.django_db
class TestPhase4CoverageValidatorErrorPath:
    """Phase 4 (Welle 2): DB-Fehlerpfad im Coverage-Validator darf nicht crashen."""

    def test_validate_weakness_coverage_db_error_returns_empty_list(self):
        user = UserFactory()
        gen = PlanGenerator(user_id=user.id)
        plan_json = _make_plan_json(
            "Test",
            [_make_session("A", [_make_exercise("Bankdrücken")])],
        )

        with patch("core.models.Uebung.objects.filter", side_effect=Exception("db down")):
            warnings = gen._validate_weakness_coverage(
                plan_json,
                weaknesses=["Brust: Untertrainiert (2 Sätze/Woche)"],
            )

        assert warnings == []


class TestMacrocycleSummaryFormatting:
    """Phase 5 (Welle 1): Abdeckung der Makrozyklus-Textformatierung."""

    def test_summary_without_macro_uses_defaults(self):
        gen = PlanGenerator(user_id=1, periodization="linear", target_profile="hypertrophie")

        summary = gen._format_macrocycle_summary(
            {
                "duration_weeks": 10,
                "periodization": "linear",
                "target_profile": "hypertrophie",
            }
        )

        assert "PLANÜBERSICHT: 10-Wochen-Plan" in summary
        assert "Linearer Aufbau für Muskelaufbau" in summary
        assert "DELOAD-WOCHEN (4, 8, 12)" in summary
        assert "BEISPIEL-WOCHENPLAN:" not in summary

    def test_summary_with_micro_and_macro_examples(self):
        gen = PlanGenerator(user_id=1, periodization="block", target_profile="kraft")

        summary = gen._format_macrocycle_summary(
            {
                "periodization": "block",
                "target_profile": "kraft",
                "deload_weeks": [4, 8],
                "microcycle_template": {"rep_range": "3-5", "rpe_range": "8-9"},
                "macrocycle": {
                    "duration_weeks": 12,
                    "weeks": [
                        {
                            "week": 1,
                            "focus": "Volumenbasis",
                            "volume_multiplier": 1.0,
                            "intensity_target_rpe": 8.0,
                            "is_deload": False,
                        },
                        {
                            "week": 4,
                            "focus": "Deload & Technik",
                            "volume_multiplier": 0.8,
                            "intensity_target_rpe": 7.0,
                            "is_deload": True,
                        },
                        {
                            "week": 5,
                            "focus": "Kraft/Intensität",
                            "volume_multiplier": 1.1,
                            "intensity_target_rpe": 8.4,
                            "is_deload": False,
                        },
                        {
                            "week": 8,
                            "focus": "Deload & Technik",
                            "volume_multiplier": 0.8,
                            "intensity_target_rpe": 7.0,
                            "is_deload": True,
                        },
                        {
                            "week": 9,
                            "focus": "Top-Phase",
                            "volume_multiplier": 1.15,
                            "intensity_target_rpe": 8.7,
                            "is_deload": False,
                        },
                    ],
                },
            }
        )

        assert "Blockperiodisierung für Maximalkraft" in summary
        assert "ZIEL PRO SATZ: 3-5 Wiederholungen bei RPE 8-9" in summary
        assert "DELOAD-WOCHEN (4, 8)" in summary
        assert "BEISPIEL-WOCHENPLAN:" in summary
        assert summary.count("   - Woche ") == 4


class TestMainCliEntry:
    """Phase 5 (Welle 1): CLI-Entry (`main`) mit Exit-Codes und Output-Datei."""

    def test_main_success_writes_output_and_exits_zero(self, tmp_path):
        from ai_coach import plan_generator as module

        output_file = tmp_path / "result.json"
        expected_result = {"success": True, "plan_ids": [1], "plan_data": {"plan_name": "T"}}

        with (
            patch(
                "sys.argv",
                [
                    "plan_generator.py",
                    "--user-id",
                    "7",
                    "--plan-type",
                    "fullbody",
                    "--no-save",
                    "--output",
                    str(output_file),
                ],
            ),
            patch("ai_coach.plan_generator.PlanGenerator") as mock_generator_cls,
        ):
            mock_generator = mock_generator_cls.return_value
            mock_generator.generate.return_value = expected_result

            with pytest.raises(SystemExit) as exc:
                module.main()

        assert exc.value.code == 0
        mock_generator.generate.assert_called_once_with(save_to_db=False)
        assert output_file.exists()

    def test_main_failure_exits_one(self):
        from ai_coach import plan_generator as module

        with (
            patch(
                "sys.argv",
                [
                    "plan_generator.py",
                    "--user-id",
                    "5",
                    "--plan-type",
                    "ppl",
                    "--no-save",
                ],
            ),
            patch("ai_coach.plan_generator.PlanGenerator") as mock_generator_cls,
        ):
            mock_generator = mock_generator_cls.return_value
            mock_generator.generate.return_value = {"success": False, "errors": ["boom"]}

            with pytest.raises(SystemExit) as exc:
                module.main()

        assert exc.value.code == 1
        mock_generator.generate.assert_called_once_with(save_to_db=False)

    def test_module_main_guard_executes_main(self):
        """`if __name__ == '__main__'` ruft main() auf (argparse endet erwartbar mit Exit 2)."""
        import runpy

        with patch("sys.argv", ["plan_generator.py"]):
            with pytest.raises(SystemExit) as exc:
                runpy.run_module("ai_coach.plan_generator", run_name="__main__")

        assert exc.value.code == 2
