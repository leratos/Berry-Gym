"""Tests für KIApiLog – Modell, Logging-Methode, Integrationspfade."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from core.models import KIApiLog


@pytest.mark.django_db
class TestKIApiLogModel:
    """Grundlegende Modell-Tests."""

    def test_create_minimal(self, django_user_model):
        user = django_user_model.objects.create_user("log_user", password="pw")
        log = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
            model_name="google/gemini-2.5-flash",
            tokens_input=1200,
            tokens_output=800,
            cost_eur=Decimal("0.002300"),
        )
        assert log.pk is not None
        assert log.success is True
        assert log.is_retry is False
        assert log.error_message == ""

    def test_tokens_total_property(self, django_user_model):
        user = django_user_model.objects.create_user("log_user2", password="pw")
        log = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.LIVE_GUIDANCE,
            tokens_input=500,
            tokens_output=300,
        )
        assert log.tokens_total == 800

    def test_str_representation(self, django_user_model):
        user = django_user_model.objects.create_user("log_user3", password="pw")
        log = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_OPTIMIZE,
            cost_eur=Decimal("0.001500"),
        )
        s = str(log)
        assert "log_user3" in s
        assert "plan_optimize" in s

    def test_user_null_allowed(self):
        """Anonyme Calls (z.B. CLI) dürfen user=None haben."""
        log = KIApiLog.objects.create(
            endpoint=KIApiLog.Endpoint.OTHER,
            user=None,
        )
        assert log.pk is not None
        assert log.user is None

    def test_ordering_newest_first(self, django_user_model):
        from datetime import timedelta

        from django.utils import timezone

        user = django_user_model.objects.create_user("log_user4", password="pw")
        old = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
            created_at=timezone.now() - timedelta(hours=1),
        )
        new = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
            created_at=timezone.now(),
        )
        logs = list(KIApiLog.objects.filter(user=user))
        assert logs[0].pk == new.pk
        assert logs[1].pk == old.pk

    def test_retry_flag(self, django_user_model):
        user = django_user_model.objects.create_user("log_user5", password="pw")
        log = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
            is_retry=True,
            success=False,
            error_message="halluzinierte Übung",
        )
        assert log.is_retry is True
        assert log.success is False
        assert "halluzinierte" in log.error_message

    def test_cost_precision(self, django_user_model):
        """Kosten werden mit 6 Dezimalstellen gespeichert."""
        user = django_user_model.objects.create_user("log_user6", password="pw")
        log = KIApiLog.objects.create(
            user=user,
            endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
            cost_eur=Decimal("0.000123"),
        )
        log.refresh_from_db()
        assert log.cost_eur == Decimal("0.000123")

    def test_filter_by_user_and_endpoint(self, django_user_model):
        user_a = django_user_model.objects.create_user("log_a", password="pw")
        user_b = django_user_model.objects.create_user("log_b", password="pw")
        KIApiLog.objects.create(user=user_a, endpoint=KIApiLog.Endpoint.PLAN_GENERATE)
        KIApiLog.objects.create(user=user_a, endpoint=KIApiLog.Endpoint.LIVE_GUIDANCE)
        KIApiLog.objects.create(user=user_b, endpoint=KIApiLog.Endpoint.PLAN_GENERATE)

        user_a_plans = KIApiLog.objects.filter(
            user=user_a, endpoint=KIApiLog.Endpoint.PLAN_GENERATE
        )
        assert user_a_plans.count() == 1

    def test_monthly_cost_aggregation(self, django_user_model):
        """Einfache Kostenaufsummierung pro User."""
        from django.db.models import Sum

        user = django_user_model.objects.create_user("log_agg", password="pw")
        KIApiLog.objects.create(user=user, cost_eur=Decimal("0.002000"))
        KIApiLog.objects.create(user=user, cost_eur=Decimal("0.001500"))
        KIApiLog.objects.create(user=user, cost_eur=Decimal("0.000500"))

        total = KIApiLog.objects.filter(user=user).aggregate(Sum("cost_eur"))["cost_eur__sum"]
        assert total == Decimal("0.004000")


@pytest.mark.django_db
class TestPlanGeneratorLogKiCost:
    """Tests für _log_ki_cost in PlanGenerator."""

    def _make_generator(self, user_id: int):
        from ai_coach.plan_generator import PlanGenerator

        return PlanGenerator(
            user_id=user_id,
            plan_type="3er-split",
            use_openrouter=True,
        )

    def test_log_ki_cost_creates_db_entry(self, django_user_model):
        user = django_user_model.objects.create_user("gen_user1", password="pw")
        gen = self._make_generator(user.id)

        llm_result = {
            "model": "google/gemini-2.5-flash",
            "cost": 0.0023,
            "usage": {"prompt_tokens": 1100, "completion_tokens": 900},
        }
        gen._log_ki_cost(llm_result)

        log = KIApiLog.objects.get(user=user)
        assert log.endpoint == KIApiLog.Endpoint.PLAN_GENERATE
        assert log.model_name == "google/gemini-2.5-flash"
        assert log.tokens_input == 1100
        assert log.tokens_output == 900
        assert float(log.cost_eur) == pytest.approx(0.0023, abs=1e-6)
        assert log.success is True
        assert log.is_retry is False

    def test_log_ki_cost_retry_flag(self, django_user_model):
        user = django_user_model.objects.create_user("gen_user2", password="pw")
        gen = self._make_generator(user.id)

        gen._log_ki_cost({"model": "test", "cost": 0.001, "usage": {}}, is_retry=True)

        log = KIApiLog.objects.get(user=user)
        assert log.is_retry is True

    def test_log_ki_cost_missing_usage_does_not_crash(self, django_user_model):
        """Fehlendes 'usage'-Dict darf _log_ki_cost nicht zum Absturz bringen."""
        user = django_user_model.objects.create_user("gen_user3", password="pw")
        gen = self._make_generator(user.id)

        gen._log_ki_cost({"model": "test", "cost": 0.0})  # kein 'usage' key

        log = KIApiLog.objects.get(user=user)
        assert log.tokens_input == 0
        assert log.tokens_output == 0

    def test_log_ki_cost_db_error_is_silent(self, django_user_model):
        """Logging-Fehler dürfen den Plan-Flow nicht unterbrechen."""
        user = django_user_model.objects.create_user("gen_user4", password="pw")
        gen = self._make_generator(user.id)

        with patch("core.models.KIApiLog.objects.create", side_effect=Exception("DB kaputt")):
            # Darf keine Exception werfen
            gen._log_ki_cost({"model": "test", "cost": 0.001, "usage": {}})
