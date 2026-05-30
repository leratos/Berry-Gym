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


def test_system_prompt_forbids_quantitative_coverage_claims_in_description():
    """Phase 31.3 Schicht A: Der System-Prompt weist das LLM an, in der
    plan_description keine quantitativen Schwachstellen-Coverage-Aussagen zu
    machen (z.B. '≥6 Arbeitssätze')."""
    builder = PromptBuilder()
    assert "plan_description" in builder.system_prompt
    assert "KEINE quantitativen Behauptungen über Schwachstellen-Coverage" in builder.system_prompt


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


def test_build_weakness_block_resolves_db_constants(monkeypatch):
    """Phase 29.3 (F3): data_analyzer liefert DB-Konstanten als Label
    ('BEINE_HAM'). Diese müssen aufgelöst werden, nicht still verworfen."""
    builder = PromptBuilder()
    monkeypatch.setattr(builder, "_get_exercises_for_keys", lambda keys, avail: ["Beinbeuger"])

    block = builder._build_weakness_block(
        ["BEINE_HAM: Untertrainiert (nur 82 eff. Wdh vs. Ø 176)"],
        ["Beinbeuger"],
    )

    assert block is not None, "DB-Konstanten-Label darf nicht still verworfen werden"
    assert "HAMSTRINGS" in block  # KEY_TO_DISPLAY["BEINE_HAM"] = "Hamstrings"


def test_build_weakness_block_demands_volume(monkeypatch):
    """Phase 29.3: Der Pflicht-Block fordert ein Satz-Volumen, nicht nur
    'mind. 1 Übung'."""
    from ai_coach.muscle_labels import MIN_SETS_PER_WEAKNESS

    builder = PromptBuilder()
    monkeypatch.setattr(builder, "_get_exercises_for_keys", lambda keys, avail: ["Crunch"])

    block = builder._build_weakness_block(
        ["BAUCH: Untertrainiert (nur 10 eff. Wdh vs. Ø 50)"],
        ["Crunch"],
    )

    assert block is not None
    assert "Arbeitssätze" in block
    assert "mind. 1 Übung" not in block
    assert str(MIN_SETS_PER_WEAKNESS) in block


# ─────────────────────────────────────────────────────────────────────────────
# Phase 30.1: Übertraining-Cap-Block
# ─────────────────────────────────────────────────────────────────────────────


def test_build_overtraining_cap_block_returns_none_for_empty():
    builder = PromptBuilder()
    assert builder._build_overtraining_cap_block([]) is None


def test_build_overtraining_cap_block_contains_cap_details():
    """Phase 30.1: Block muss Muskelgruppen-Name, Cap, Ist-Wert und Soll-Max
    enthalten, damit der Prompt klar ist."""
    builder = PromptBuilder()
    caps = [
        {
            "key": "BRUST",
            "name": "Brust (Pectoralis major)",
            "ist_sets": 28,
            "soll_max": 25,
            "weekly_cap": 5,
        },
        {
            "key": "TRIZEPS",
            "name": "Trizeps (Triceps brachii)",
            "ist_sets": 20,
            "soll_max": 18,
            "weekly_cap": 3,
        },
    ]
    block = builder._build_overtraining_cap_block(caps)

    assert block is not None
    assert "ÜBERTRAINING-CAP" in block
    # Beide Muskelgruppen (uppercase) vertreten
    assert "BRUST" in block
    assert "TRIZEPS" in block
    # Cap-Werte sichtbar
    assert "max. 5" in block  # Brust-Cap
    assert "max. 3" in block  # Trizeps-Cap
    # Ist-Werte und Soll-Max sichtbar
    assert "28" in block and "25" in block
    assert "20" in block and "18" in block


def test_build_user_prompt_inserts_overtrain_block_and_requirement():
    """Phase 30.1: bei nicht-leeren Caps muss der Prompt sowohl den
    Cap-Block als auch den Anforderungspunkt 0b enthalten."""
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        overtrained_caps=[
            {
                "key": "BRUST",
                "name": "Brust",
                "ist_sets": 28,
                "soll_max": 25,
                "weekly_cap": 5,
            }
        ],
    )

    assert "ÜBERTRAINING-CAP" in prompt
    assert "BRUST" in prompt
    assert "max. 5" in prompt
    # Anforderungspunkt 0b muss sichtbar sein
    assert "0b." in prompt


def test_build_user_prompt_without_overtrain_caps_omits_block():
    """Phase 30.1: ohne überlastete Muskelgruppen darf der Block NICHT im
    Prompt auftauchen (kein irreführender Hinweis auf einen leeren Block)."""
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        overtrained_caps=None,
    )

    assert "ÜBERTRAINING-CAP" not in prompt
    assert "0b." not in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Phase 30.2: undertrained-Parameter überschreibt data_analyzer-Heuristik
# ─────────────────────────────────────────────────────────────────────────────


def test_undertrained_param_takes_precedence_over_analysis_weaknesses(monkeypatch):
    """Phase 30.2: wenn der Aufrufer eine `undertrained`-Liste übergibt, wird
    NUR diese für den PFLICHT-Block verwendet – die alte data_analyzer-
    Heuristik in `analysis_data["weaknesses"]` darf den Pflicht-Block nicht
    mehr füllen."""
    builder = PromptBuilder()
    # Wir mocken _get_exercises_for_keys, damit der Block-Inhalt deterministisch ist.
    monkeypatch.setattr(builder, "_get_exercises_for_keys", lambda keys, avail: ["Crunch"])

    # analysis_data enthält eine "alte" Heuristik-Schwachstelle (Brust),
    # die NICHT mehr im PFLICHT-Block landen soll.
    analysis = _analysis_data(
        freq=3.0,
        weaknesses=["Brust: Untertrainiert (Heuristik-Altlast)"],
    )
    # Kanonische (Stats-Collector) Untertrainiert-Liste hat nur BAUCH.
    undertrained = ["BAUCH: Untertrainiert (aktuell 9 Sätze, Ziel min 10)"]

    prompt = builder.build_user_prompt(
        analysis,
        ["Crunch", "Bankdrücken (Langhantel)"],
        plan_type="3er-split",
        sets_per_session=22,
        undertrained=undertrained,
    )

    # PFLICHT-Block enthält Bauch (aus undertrained), NICHT Brust.
    assert "BAUCH" in prompt or "Bauch" in prompt
    # "PFLICHT" sollte nicht für Brust gelten – der Block-Text "❗ BRUST" ist
    # der Indikator. Der Header "Schwachstellen" zeigt Brust noch
    # informativ (data_analyzer), nur die ❗-Pflicht-Zeile darf nicht da sein.
    assert "❗ BRUST" not in prompt


def test_undertrained_none_falls_back_to_analysis_weaknesses(monkeypatch):
    """Phase 30.2: wird `undertrained` nicht übergeben (Backward-Compat),
    muss der Pflicht-Block weiterhin aus `analysis_data["weaknesses"]`
    gefüllt werden – sonst brechen Aufrufer ohne 30.2-Update."""
    builder = PromptBuilder()
    monkeypatch.setattr(builder, "_get_exercises_for_keys", lambda keys, avail: ["Crunch"])

    analysis = _analysis_data(
        freq=3.0,
        weaknesses=["Bauch: Untertrainiert (Heuristik-Fallback)"],
    )

    prompt = builder.build_user_prompt(
        analysis,
        ["Crunch", "Bankdrücken (Langhantel)"],
        plan_type="3er-split",
        sets_per_session=22,
        # undertrained NICHT übergeben → Fallback-Pfad
    )

    # Fallback funktioniert: Bauch landet im Pflicht-Block
    assert "❗ BAUCH" in prompt or "BAUCH" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Phase 30.3: Plateau-Soft-Hint-Block
# ─────────────────────────────────────────────────────────────────────────────


def test_build_plateau_hint_block_returns_none_for_empty():
    builder = PromptBuilder()
    assert builder._build_plateau_hint_block([]) is None


def test_build_plateau_hint_block_lists_exercises_with_status():
    """Block muss Übungs-Name, Muskelgruppe und Status-Label enthalten,
    damit der Prompt klar zeigt, welche Übungen Plateau haben."""
    builder = PromptBuilder()
    hints = [
        {
            "uebung": "Bankdrücken (Langhantel)",
            "muskelgruppe": "Brust (Pectoralis major)",
            "status_label": "📈 Aktive Progression (PR-Pause)",
        },
        {
            "uebung": "Hammer Curls (Kurzhantel)",
            "muskelgruppe": "Bizeps (Biceps brachii)",
            "status_label": "💪 Konsolidierung (RPE sinkt)",
        },
    ]
    block = builder._build_plateau_hint_block(hints)
    assert block is not None
    assert "TRAININGS-FORTSCHRITT-KONTEXT" in block
    assert "Bankdrücken (Langhantel)" in block
    assert "Hammer Curls (Kurzhantel)" in block
    assert "PR-Pause" in block
    assert "Konsolidierung" in block
    # Soft-Hint, nicht Pflicht-Constraint
    assert "Soft-Hint" in block or "nicht Pflicht-Block" in block


def test_build_user_prompt_inserts_plateau_block():
    """Phase 30.3: wird ``plateau_hints`` übergeben, taucht der
    Soft-Hint-Block im Prompt auf."""
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        plateau_hints=[
            {
                "uebung": "Bankdrücken (Langhantel)",
                "muskelgruppe": "Brust",
                "status_label": "📈 Aktive Progression (PR-Pause)",
            }
        ],
    )
    assert "TRAININGS-FORTSCHRITT-KONTEXT" in prompt
    assert "Bankdrücken (Langhantel)" in prompt


def test_build_user_prompt_without_plateau_hints_omits_block():
    """Ohne plateau_hints darf der Soft-Hint-Block NICHT im Prompt
    erscheinen (kein leerer Block)."""
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        plateau_hints=None,
    )
    assert "TRAININGS-FORTSCHRITT-KONTEXT" not in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Phase 30.4: Trainings-Kontext-Soft-Hints (Fatigue + Frequency + Push/Pull)
# ─────────────────────────────────────────────────────────────────────────────


def test_build_training_context_block_returns_none_for_none_or_empty():
    builder = PromptBuilder()
    assert builder._build_training_context_block(None) is None
    assert builder._build_training_context_block({}) is None
    # Alle drei None → kein Block
    assert (
        builder._build_training_context_block(
            {"fatigue_hint": None, "frequency_hint": None, "push_pull_hint": None}
        )
        is None
    )


def test_build_training_context_block_lists_only_present_hints():
    """Phase 30.4: nur nicht-None-Felder werden in der Reihenfolge
    Fatigue → Frequenz → Push/Pull aufgelistet."""
    builder = PromptBuilder()
    context = {
        "fatigue_hint": None,
        "frequency_hint": "Frequenz: 1.5x/Woche → Ganzkörper passender",
        "push_pull_hint": "Push/Pull-Balance: Leicht Push-betont – Pull aufstocken",
    }
    block = builder._build_training_context_block(context)
    assert block is not None
    assert "TRAININGS-KONTEXT" in block
    # Beide vorhandenen Hints sichtbar:
    assert "Frequenz: 1.5x" in block
    assert "Push-betont" in block
    # Fatigue darf NICHT auftauchen, war None:
    assert "Ermüdungs" not in block


def test_build_user_prompt_inserts_context_block():
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        training_context={
            "fatigue_hint": "Ermüdungs-Index: 75/100 (Hoch). Deload empfohlen.",
            "frequency_hint": None,
            "push_pull_hint": None,
        },
    )
    assert "TRAININGS-KONTEXT" in prompt
    assert "Ermüdungs-Index" in prompt


def test_build_user_prompt_without_training_context_omits_block():
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=22,
        training_context=None,
    )
    assert "TRAININGS-KONTEXT (Adaptions" not in prompt


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


def test_distribute_example_sets_sums_exactly():
    """Phase 29.2 (F1): _distribute_example_sets verteilt Sätze exakt."""
    from ai_coach.prompt_builder import _distribute_example_sets

    for total in (12, 16, 18, 20, 22, 26):
        dist = _distribute_example_sets(total, 6)
        assert len(dist) == 6
        assert sum(dist) == total, f"Summe {sum(dist)} != {total}"
        # Werte unterscheiden sich max. um 1, Rest landet vorne (Compounds)
        assert max(dist) - min(dist) <= 1
        assert dist == sorted(dist, reverse=True)


def test_build_user_prompt_uses_exact_set_target():
    """Phase 29.2 (F1): der Prompt nennt die exakte Zielzahl, kein 18er-Anker."""
    builder = PromptBuilder()
    available = [
        "Bankdrücken (Langhantel)",
        "Kniebeuge (Langhantel, Back Squat)",
        "Crunch",
    ]

    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        available,
        plan_type="3er-split",
        sets_per_session=22,
    )

    # Exakte Zielzahl statt 4-breiter Range
    assert "GENAU 22" in prompt
    assert "18-22" not in prompt
    # Kein hartcodierter 18-Sätze-Anker mehr
    assert "18 Sätze total" not in prompt
    # Beispiel-Tage skalieren mit → Summe = 22
    assert "Summe = 22 Sätze" in prompt
    assert "= 22 Sätze total" in prompt
    # Keine widersprüchliche ±1-Toleranz neben der "exakt"-Regel (Code-Review 29.2)
    assert "±1" not in prompt


def test_build_user_prompt_examples_scale_with_sets():
    """Phase 29.2 (F1): bei sets_per_session=16 zeigen die Beispiele 16, nicht 18."""
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(
        _analysis_data(freq=3.0),
        ["Bankdrücken (Langhantel)", "Crunch"],
        plan_type="3er-split",
        sets_per_session=16,
    )
    assert "GENAU 16" in prompt
    assert "= 16 Sätze total" in prompt
    assert "18 Sätze total" not in prompt


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
