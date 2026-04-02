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
    assert "Linear" in prompt_none and "Deload" in prompt_none


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

    Uebung.objects.create(
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


# ─────────────────────────────────────────────────────────────────────────────
# 13.3: Dynamische Periodisierungs-Beschreibung
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildPeriodizationNote:
    """Phase 13.3: _build_periodization_note erzeugt profilabhängige Texte."""

    def test_kraft_linear(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("linear", "kraft")
        assert "Linear" in note
        assert "RPE < 7.5" in note
        assert "150-180s" in note

    def test_hypertrophie_linear(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("linear", "hypertrophie")
        assert "Linear" in note
        assert ">12 Wdh" in note
        assert "+1 Satz" in note

    def test_definition_linear(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("linear", "definition")
        assert "Linear" in note
        assert "Halte Gewicht" in note
        assert "60-90s" in note

    def test_wellenfoermig_hypertrophie(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("wellenfoermig", "hypertrophie")
        assert "Wellenförmig" in note
        assert "Heavy/Medium/Light" in note

    def test_block_kraft(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("block", "kraft")
        assert "Blockperiodisierung" in note
        assert "Block 1 Volumen" in note
        assert "RPE < 7.5" in note

    def test_unknown_profile_uses_hypertrophie_defaults(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("linear", "custom")
        assert ">12 Wdh" in note

    def test_deload_always_mentioned(self):
        from ai_coach.prompt_builder import _build_periodization_note

        for p in ("linear", "wellenfoermig", "block"):
            for t in ("kraft", "hypertrophie", "definition"):
                note = _build_periodization_note(p, t)
                assert "Deload" in note, f"Deload fehlt für {p}/{t}"

    def test_duration_weeks_changes_deload_text(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note_8 = _build_periodization_note("linear", "hypertrophie", duration_weeks=8)
        assert "Woche 4/8" in note_8
        assert "12" not in note_8.split("Woche")[1].split(".")[0]

        note_6 = _build_periodization_note("linear", "hypertrophie", duration_weeks=6)
        assert "Woche 6" in note_6

    def test_wellenfoermig_short_plan_block_length(self):
        from ai_coach.prompt_builder import _build_periodization_note

        note = _build_periodization_note("wellenfoermig", "hypertrophie", duration_weeks=6)
        assert "6-Wochen-Blocks" in note


# ─────────────────────────────────────────────────────────────────────────────
# Phase 17.2: Dynamische Deload-Berechnung
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateDeloadWeeks:
    """Phase 17.2: calculate_deload_weeks platziert Deloads dynamisch."""

    def test_4_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(4) == [4]

    def test_5_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(5) == [5]

    def test_6_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(6) == [6]

    def test_8_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(8) == [4, 8]

    def test_10_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(10) == [4, 8, 10]

    def test_12_wochen_standard(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(12) == [4, 8, 12]

    def test_16_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(16) == [4, 8, 12, 16]

    def test_9_wochen_kein_extra_deload(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        # 9 - 8 = 1 Woche Abstand → kein extra Deload
        assert calculate_deload_weeks(9) == [4, 8]

    def test_14_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        # 14 - 12 = 2 Wochen Abstand → extra Deload
        assert calculate_deload_weeks(14) == [4, 8, 12, 14]

    def test_0_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        assert calculate_deload_weeks(0) == []

    def test_7_wochen(self):
        from ai_coach.prompt_builder import calculate_deload_weeks

        # 7 Wochen: Deload bei 4, aber < 8 Wochen → kein finaler Deload
        assert calculate_deload_weeks(7) == [4]
