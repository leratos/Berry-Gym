import json
import runpy
import types
from datetime import timedelta

from django.utils import timezone

import pytest

from ai_coach.data_analyzer import TrainingAnalyzer
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestTrainingAnalyzerCore:
    def test_analyze_returns_empty_without_sessions(self):
        user = UserFactory()
        analyzer = TrainingAnalyzer(user_id=user.id, days=30)

        result = analyzer.analyze()

        assert result["user_id"] == user.id
        assert result["training_stats"]["total_sessions"] == 0
        assert result["weaknesses"] == ["Keine Trainingsdaten vorhanden"]

    def test_analyze_with_sessions_computes_metrics(self):
        user = UserFactory()
        brust = UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="Brust")
        ruecken = UebungFactory(bezeichnung="Rudern", muskelgruppe="Rücken")
        beine = UebungFactory(bezeichnung="Kniebeuge", muskelgruppe="Beine")
        schulter = UebungFactory(bezeichnung="Schulterdrücken", muskelgruppe="Schultern")

        session1 = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=6), dauer_minuten=60
        )
        session2 = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=2), dauer_minuten=90
        )

        # Übung mit >=2 Records (Trend-Pfad)
        SatzFactory(
            einheit=session1,
            uebung=brust,
            gewicht=80,
            wiederholungen=8,
            rpe=8.0,
            ist_aufwaermsatz=False,
        )
        SatzFactory(
            einheit=session2,
            uebung=brust,
            gewicht=85,
            wiederholungen=8,
            rpe=8.5,
            ist_aufwaermsatz=False,
        )

        # Pull-Volumen
        SatzFactory(
            einheit=session2,
            uebung=ruecken,
            gewicht=70,
            wiederholungen=10,
            rpe=7.5,
            ist_aufwaermsatz=False,
        )

        # <2 Records-Pfad mit Record
        SatzFactory(
            einheit=session1,
            uebung=schulter,
            gewicht=40,
            wiederholungen=10,
            rpe=7.0,
            ist_aufwaermsatz=False,
        )

        # continue-Pfad (fehlende reps/rpe)
        SatzFactory(
            einheit=session1,
            uebung=beine,
            gewicht=100,
            wiederholungen=8,
            rpe=None,
            ist_aufwaermsatz=False,
        )

        analyzer = TrainingAnalyzer(user_id=user.id, days=30)
        result = analyzer.analyze()

        assert result["training_stats"]["total_sessions"] == 2
        assert result["training_stats"]["avg_duration_minutes"] == 75
        assert result["training_stats"]["frequency_per_week"] == 0.5

        ex = result["exercise_performance"]["Bankdrücken"]
        assert ex["trend"].startswith("+")
        assert ex["last_1rm"] > 0

        ex_single = result["exercise_performance"]["Schulterdrücken"]
        assert ex_single["trend"] == "Nicht genug Daten"
        assert ex_single["avg_rpe"] == 7.0

        balance = result["push_pull_balance"]
        assert balance["push_volume"] > 0
        assert balance["pull_volume"] > 0
        assert isinstance(balance["balanced"], bool)

        assert "Brust" in result["muscle_groups"]
        assert result["muscle_groups"]["Brust"]["avg_rpe"] > 0
        assert isinstance(result["muscle_groups"]["Brust"]["last_trained"], str)

    def test_analyze_ratio_zero_when_no_pull(self):
        user = UserFactory()
        brust = UebungFactory(bezeichnung="Dips", muskelgruppe="Brust")
        session = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=1), dauer_minuten=45
        )

        SatzFactory(
            einheit=session,
            uebung=brust,
            gewicht=20,
            wiederholungen=12,
            rpe=8.0,
            ist_aufwaermsatz=False,
        )

        result = TrainingAnalyzer(user_id=user.id, days=30).analyze()
        assert result["push_pull_balance"]["pull_volume"] == 0
        assert result["push_pull_balance"]["ratio"] == 0
        assert result["push_pull_balance"]["balanced"] is False


@pytest.mark.django_db
class TestTrainingAnalyzerHelpers:
    def test_identify_weaknesses_volume_and_stale_exercises(self):
        analyzer = TrainingAnalyzer(user_id=1, days=30)

        muscle_volume = {
            "Brust": {"effective_reps": 200},
            "Rücken": {"effective_reps": 50},
        }
        old_date = (timezone.now() - timedelta(days=20)).replace(tzinfo=None).isoformat()
        exercise_performance = {
            "Bankdrücken": {"records": [{"date": old_date}]},
            "Rudern": {"records": []},
        }

        weaknesses = analyzer._identify_weaknesses(muscle_volume, exercise_performance)

        assert any("Rücken: Untertrainiert" in text for text in weaknesses)
        assert any("Bankdrücken: Nicht mehr trainiert" in text for text in weaknesses)

    def test_identify_weaknesses_empty_inputs(self):
        analyzer = TrainingAnalyzer(user_id=1, days=30)
        assert analyzer._identify_weaknesses({}, {}) == []

    def test_to_json_with_and_without_input(self):
        analyzer = TrainingAnalyzer(user_id=1, days=30)

        as_json = analyzer.to_json({"x": 1})
        assert json.loads(as_json)["x"] == 1

        auto_json = analyzer.to_json()
        parsed = json.loads(auto_json)
        assert "training_stats" in parsed

    def test_print_summary_with_and_without_weaknesses(self, capsys):
        analyzer = TrainingAnalyzer(user_id=1, days=30)

        analyzer.print_summary(
            {
                "user_id": 1,
                "analysis_period": "30 days",
                "training_stats": {
                    "total_sessions": 2,
                    "avg_duration_minutes": 60,
                    "frequency_per_week": 3.0,
                },
                "muscle_groups": {
                    "Brust": {"effective_reps": 120, "avg_rpe": 8.1},
                    "Rücken": {"effective_reps": 100, "avg_rpe": 7.9},
                },
                "exercise_performance": {
                    "Bankdrücken": {"last_1rm": 105.5, "trend": "+2.0kg"},
                    "Rudern": {"last_1rm": 95.0, "trend": "-1.0kg"},
                },
                "push_pull_balance": {
                    "push_volume": 120,
                    "pull_volume": 100,
                    "ratio": 1.2,
                    "balanced": False,
                },
                "weaknesses": ["Brust: Untertrainiert"],
            }
        )

        out = capsys.readouterr().out
        assert "TRAININGSANALYSE" in out
        assert "Schwachstellen" in out

        analyzer.print_summary(
            {
                "user_id": 1,
                "analysis_period": "30 days",
                "training_stats": {
                    "total_sessions": 0,
                    "avg_duration_minutes": 0,
                    "frequency_per_week": 0,
                },
                "muscle_groups": {},
                "exercise_performance": {},
                "push_pull_balance": {
                    "push_volume": 0,
                    "pull_volume": 0,
                    "ratio": 0,
                    "balanced": False,
                },
                "weaknesses": [],
            }
        )

        out2 = capsys.readouterr().out
        assert "Schwachstellen" not in out2

    def test_print_summary_without_argument_calls_analyze(self, capsys):
        analyzer = TrainingAnalyzer(user_id=1, days=30)

        analyzer.print_summary()

        out = capsys.readouterr().out
        assert "TRAININGSANALYSE" in out


@pytest.mark.django_db
class TestTrainingAnalyzerMainGuard:
    def test_module_main_guard_success(self, monkeypatch):
        class _DbCtx:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_db_module = types.SimpleNamespace(DatabaseClient=lambda: _DbCtx())

        monkeypatch.setitem(__import__("sys").modules, "db_client", fake_db_module)

        runpy.run_module("ai_coach.data_analyzer", run_name="__main__")

    def test_module_main_guard_exception_path(self, monkeypatch):
        class _DbCtxFail:
            def __enter__(self):
                raise RuntimeError("db-fail")

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_db_module = types.SimpleNamespace(DatabaseClient=lambda: _DbCtxFail())

        monkeypatch.setitem(__import__("sys").modules, "db_client", fake_db_module)

        runpy.run_module("ai_coach.data_analyzer", run_name="__main__")
