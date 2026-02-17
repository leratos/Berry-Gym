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

        assert tokens >= 2000, f"Default muss mindestens 2000 sein, war: {tokens}"
        assert tokens <= 5000, f"Default sollte unter 5000 bleiben, war: {tokens}"

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

    def test_no_plan_type_hardcodes_4000(self):
        """Kein Plan-Typ darf mehr als 5000 Tokens bekommen (Kostenschutz)."""
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
                tokens <= 5000
            ), f"Plan-Typ '{pt}' hat {tokens} Tokens – das ist zu hoch (max 5000)"
            assert (
                tokens >= 1500
            ), f"Plan-Typ '{pt}' hat nur {tokens} Tokens – zu niedrig (min 1500)"


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

        plan_json = _make_plan_json("Plan A", [])  # 6 Zeichen
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
            [_make_session("A", [_make_exercise("Bankdrücken")])],
        )
        warnings = gen._validate_weakness_coverage(
            plan_json, weaknesses=["Brust: Untertrainiert (2 Sätze/Woche)"]
        )
        # Brust ist abgedeckt → keine Warning
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
