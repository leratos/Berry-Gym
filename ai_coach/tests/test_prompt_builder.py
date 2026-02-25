import runpy
import sys
import types

from django.contrib.auth.models import User

import pytest

from ai_coach.prompt_builder import PromptBuilder
from core.models import Equipment, Uebung


def _analysis_data(freq=3.0, weaknesses=None):
    if weaknesses is None:
        weaknesses = ["Bauch: Untertrainiert (nur 10 eff. Wdh vs. Ø 50)"]
    return {
        "user_id": 42,
        "analysis_period": "30 days",
        "training_stats": {
            "total_sessions": 12,
            "frequency_per_week": freq,
            "avg_duration_minutes": 62,
        },
        "muscle_groups": {
            "Brust": {"effective_reps": 140},
            "Rücken": {"effective_reps": 120},
            "Beine": {"effective_reps": 100},
            "Schultern": {"effective_reps": 90},
            "Bizeps": {"effective_reps": 80},
            "Trizeps": {"effective_reps": 70},
        },
        "push_pull_balance": {
            "push_volume": 300,
            "pull_volume": 250,
            "ratio": 1.2,
            "balanced": False,
        },
        "weaknesses": weaknesses,
    }


class _FakeFilterResult:
    def __init__(self, values):
        self.values = values

    def values_list(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self.values


class _FakeUebungModel:
    class objects:
        @staticmethod
        def filter(**kwargs):
            requested = set(kwargs.get("bezeichnung__in", []))
            vals = sorted([name for name in requested if "Crunch" in name or "Plank" in name])
            return _FakeFilterResult(vals)


class _RaisingUebungModel:
    class objects:
        @staticmethod
        def filter(**kwargs):
            raise RuntimeError("db-fail")


def test_system_prompt_initialization_contains_rules():
    builder = PromptBuilder()
    assert "ABSOLUTE REGEL #1" in builder.system_prompt
    assert "JSON" in builder.system_prompt


def test_get_exercises_for_keys_success_and_exception(monkeypatch):
    builder = PromptBuilder()

    fake_core_models = types.SimpleNamespace(Uebung=_FakeUebungModel)
    monkeypatch.setitem(sys.modules, "core.models", fake_core_models)
    found = builder._get_exercises_for_keys(["BAUCH"], ["Crunch", "Plank", "Bankdrücken"])
    assert found == ["Crunch", "Plank"]

    fake_core_models_raising = types.SimpleNamespace(Uebung=_RaisingUebungModel)
    monkeypatch.setitem(sys.modules, "core.models", fake_core_models_raising)
    fallback = builder._get_exercises_for_keys(["BAUCH"], ["Crunch"])
    assert fallback == []


def test_build_weakness_block_variants(monkeypatch):
    builder = PromptBuilder()

    assert builder._build_weakness_block([], ["Crunch"]) is None

    def _fake_get_exercises(keys, available):
        if "BAUCH" in keys:
            return ["Crunch", "Plank"]
        return []

    monkeypatch.setattr(builder, "_get_exercises_for_keys", _fake_get_exercises)
    block = builder._build_weakness_block(
        [
            "Bauch: Untertrainiert (nur 10 eff. Wdh vs. Ø 50)",
            "Adduktoren: Untertrainiert (nur 5 eff. Wdh vs. Ø 50)",
            "Bankdrücken: Nicht mehr trainiert seit 16 Tagen",
            "Unbekannt: Untertrainiert (nur 1 eff. Wdh vs. Ø 50)",
        ],
        ["Crunch", "Plank"],
    )

    assert block is not None
    assert "PFLICHT-ANFORDERUNG" in block
    assert "BAUCH / CORE" in block
    assert "ADDUKTOREN" in block


def test_build_user_prompt_covers_frequency_and_periodization_branches(monkeypatch):
    builder = PromptBuilder()
    available = [
        "Bankdrücken (Langhantel)",
        "Kniebeuge (Langhantel, Back Squat)",
        "Kreuzheben (Konventionell)",
        "Crunch",
    ]

    prompt_low = builder.build_user_prompt(
        _analysis_data(freq=1.0),
        available,
        plan_type="unknown-type",
        sets_per_session=18,
        target_profile="hypertrophie",
        periodization="linear",
    )
    assert "Ganzkörper-Plan empfohlen" in prompt_low
    assert "12 Wochen" in prompt_low

    prompt_mid = builder.build_user_prompt(
        _analysis_data(freq=2.5, weaknesses=["Bauch: Untertrainiert (nur 10 eff. Wdh vs. Ø 50)"]),
        available,
        plan_type="ppl",
        sets_per_session=16,
        target_profile="kraft",
        periodization="wellenfoermig",
    )
    assert "2er- oder 3er-Split optimal" in prompt_mid
    assert "Wellenförmig" in prompt_mid

    prompt_high = builder.build_user_prompt(
        _analysis_data(freq=5.2, weaknesses=["Kein Doppelpunkt Eintrag"]),
        ["Übung A", "Übung B", "Übung C"],
        plan_type="ganzkörper",
        sets_per_session=12,
        target_profile="unknown-profile",
        periodization="block",
    )
    assert "PPL oder 4er-Split optimal" in prompt_high
    assert "Blockperiodisierung" in prompt_high
    assert "unknown-profile" in prompt_high

    monkeypatch.setattr(builder, "_build_weakness_block", lambda w, e: None)
    prompt_none = builder.build_user_prompt(
        _analysis_data(freq=4.0, weaknesses=[]),
        ["Übung X", "Übung Y", "Übung Z"],
        periodization="unknown",
    )
    assert "3er- oder 4er-Split optimal" in prompt_none
    assert "Linear mit Deload 4/8/12" in prompt_none


def test_build_messages_structure(monkeypatch):
    builder = PromptBuilder()
    monkeypatch.setattr(builder, "build_user_prompt", lambda *args, **kwargs: "USER_PROMPT")

    messages = builder.build_messages(_analysis_data(), ["Crunch"])

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "USER_PROMPT"


@pytest.mark.django_db
def test_get_available_exercises_for_user_filters_by_equipment():
    user = User.objects.create_user(username="pb_user", password="pass1234")
    eq_hantel = Equipment.objects.create(name="HANTEL")
    eq_rack = Equipment.objects.create(name="RACK")

    ex_no_req = Uebung.objects.create(
        bezeichnung="Crunch",
        muskelgruppe="BAUCH",
        bewegungstyp="DRUECKEN",
        gewichts_typ="GESAMT",
    )
    ex_with_owned = Uebung.objects.create(
        bezeichnung="Bankdrücken",
        muskelgruppe="BRUST",
        bewegungstyp="DRUECKEN",
        gewichts_typ="GESAMT",
    )
    ex_with_missing = Uebung.objects.create(
        bezeichnung="Kniebeuge",
        muskelgruppe="BEINE_QUAD",
        bewegungstyp="DRUECKEN",
        gewichts_typ="GESAMT",
    )

    ex_with_owned.equipment.add(eq_hantel)
    ex_with_missing.equipment.add(eq_rack)
    user.verfuegbares_equipment.add(eq_hantel)

    available = PromptBuilder().get_available_exercises_for_user(user.id)

    assert "Crunch" in available
    assert "Bankdrücken" in available
    assert "Kniebeuge" not in available
    assert available == sorted(available)


@pytest.mark.django_db
def test_main_guard_success_and_exception_paths(monkeypatch):
    User.objects.create_user(username="u1", password="pass1234")
    User.objects.create_user(username="u2", password="pass1234")

    class _DbCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Analyzer:
        def __init__(self, user_id, days):
            self.user_id = user_id
            self.days = days

        def analyze(self):
            return _analysis_data(freq=3.0)

    fake_data_analyzer = types.SimpleNamespace(TrainingAnalyzer=_Analyzer)
    fake_db_client = types.SimpleNamespace(DatabaseClient=lambda: _DbCtx())

    monkeypatch.setitem(sys.modules, "data_analyzer", fake_data_analyzer)
    monkeypatch.setitem(sys.modules, "db_client", fake_db_client)

    runpy.run_module("ai_coach.prompt_builder", run_name="__main__")

    class _DbCtxFail:
        def __enter__(self):
            raise RuntimeError("db-fail")

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_db_client_fail = types.SimpleNamespace(DatabaseClient=lambda: _DbCtxFail())
    monkeypatch.setitem(sys.modules, "db_client", fake_db_client_fail)

    runpy.run_module("ai_coach.prompt_builder", run_name="__main__")
