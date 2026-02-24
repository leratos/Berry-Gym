import json
from unittest.mock import patch

from django.http import JsonResponse
from django.urls import reverse

import pytest

from core.tests.factories import PlanFactory, TrainingseinheitFactory, UserFactory


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json", secure=True)


def get_json(client, url, data=None):
    return client.get(url, data or {}, secure=True)


def assert_json_error_contract(response, expected_status, require_success_false=False):
    assert response.status_code == expected_status
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert data["error"].strip()
    if require_success_false:
        assert data.get("success") is False
    return data


@pytest.mark.django_db
class TestAiEndpointsExtended:
    def test_generate_plan_requires_post(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        resp = get_json(client, url)

        assert resp.status_code == 405
        data = resp.json()
        assert "error" in data
        assert "POST required" in data["error"]

    def test_generate_plan_invalid_plan_type_returns_400(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        resp = post_json(
            client,
            url,
            {
                "plan_type": "invalid-type",
                "sets_per_session": 18,
                "analysis_days": 30,
            },
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "Ungültiger Plan-Typ" in data["error"]

    @patch("core.views.ai_recommendations._check_ai_rate_limit")
    @patch("ai_coach.plan_generator.PlanGenerator")
    def test_generate_plan_save_cached_plan_bypasses_rate_limit(
        self, mock_generator_cls, mock_rate_limit, client
    ):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        mock_rate_limit.return_value = JsonResponse({"error": "should not happen"}, status=429)
        mock_generator_cls.return_value._save_plan_to_db.return_value = [101, 102]

        payload = {
            "saveCachedPlan": True,
            "plan_data": {
                "plan_name": "Preview Plan",
                "sessions": [{"day": "A"}, {"day": "B"}],
            },
        }
        resp = post_json(client, url, payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["plan_ids"] == [101, 102]
        mock_rate_limit.assert_not_called()

    @patch("core.views.ai_recommendations._check_ai_rate_limit")
    def test_generate_plan_rate_limited_contract_429(self, mock_rate_limit, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        mock_rate_limit.return_value = JsonResponse(
            {"error": "limit reached", "success": False, "rate_limited": True},
            status=429,
        )

        resp = post_json(
            client,
            url,
            {
                "plan_type": "3er-split",
                "sets_per_session": 18,
                "analysis_days": 30,
            },
        )

        data = assert_json_error_contract(resp, 429, require_success_false=True)
        assert data.get("rate_limited") is True

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    @patch("ai_coach.plan_generator.PlanGenerator", side_effect=RuntimeError("boom"))
    def test_generate_plan_internal_error_contract_500(
        self, _mock_generator, _mock_rate_limit, client
    ):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        resp = post_json(
            client,
            url,
            {
                "plan_type": "3er-split",
                "sets_per_session": 18,
                "analysis_days": 30,
            },
        )

        assert_json_error_contract(resp, 500, require_success_false=True)

    def test_analyze_plan_requires_get(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("analyze_plan_api")

        resp = post_json(client, url, {"plan_id": 1})
        assert resp.status_code == 405

    def test_analyze_plan_missing_plan_id_returns_400(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("analyze_plan_api")

        resp = get_json(client, url)
        assert resp.status_code == 400
        assert "plan_id required" in resp.json()["error"]

    def test_analyze_plan_foreign_plan_returns_404(self, client):
        owner = UserFactory()
        other = UserFactory()
        plan = PlanFactory(user=owner)
        client.force_login(other)
        url = reverse("analyze_plan_api")

        resp = get_json(client, url, {"plan_id": plan.id})
        assert resp.status_code == 404

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_analyze_plan_internal_error_contract_500(self, mock_adapter_cls, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        url = reverse("analyze_plan_api")

        mock_adapter_cls.return_value.analyze_plan_performance.side_effect = RuntimeError("boom")

        resp = get_json(client, url, {"plan_id": plan.id})

        assert_json_error_contract(resp, 500, require_success_false=True)

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_analyze_plan_success_returns_payload(self, mock_adapter_cls, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        url = reverse("analyze_plan_api")

        mock_adapter_cls.return_value.analyze_plan_performance.return_value = {
            "warnings": ["w1"],
            "suggestions": ["s1"],
            "metrics": {"score": 77},
        }

        resp = get_json(client, url, {"plan_id": plan.id, "days": 14})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["plan_id"] == plan.id
        assert data["warnings"] == ["w1"]

    def test_optimize_plan_missing_plan_id_returns_400(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("optimize_plan_api")

        resp = post_json(client, url, {"days": 10})
        assert resp.status_code == 400
        assert "plan_id required" in resp.json()["error"]

    def test_optimize_plan_requires_post(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("optimize_plan_api")

        resp = get_json(client, url)

        assert resp.status_code == 405
        assert "error" in resp.json()
        assert "POST request required" in resp.json()["error"]

    @patch("core.views.ai_recommendations._check_ai_rate_limit")
    def test_optimize_plan_rate_limited_contract_429(self, mock_rate_limit, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("optimize_plan_api")

        mock_rate_limit.return_value = JsonResponse(
            {"error": "analysis limit reached", "success": False, "rate_limited": True},
            status=429,
        )

        resp = post_json(client, url, {"plan_id": 1, "days": 30})

        data = assert_json_error_contract(resp, 429, require_success_false=True)
        assert data.get("rate_limited") is True

    def test_optimize_plan_foreign_plan_returns_404(self, client):
        owner = UserFactory()
        other = UserFactory()
        plan = PlanFactory(user=owner)
        client.force_login(other)
        url = reverse("optimize_plan_api")

        resp = post_json(client, url, {"plan_id": plan.id, "days": 30})
        assert resp.status_code == 404

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_optimize_plan_success_returns_payload(self, mock_adapter_cls, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        url = reverse("optimize_plan_api")

        mock_adapter_cls.return_value.suggest_optimizations.return_value = {
            "optimizations": [{"type": "adjust_volume"}],
            "cost": 0.003,
            "model": "Gemini 2.5 Flash",
        }

        resp = post_json(client, url, {"plan_id": plan.id, "days": 21})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["plan_id"] == plan.id
        assert data["optimizations"][0]["type"] == "adjust_volume"

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_optimize_plan_internal_error_contract_500(
        self, mock_adapter_cls, _mock_rate_limit, client
    ):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        url = reverse("optimize_plan_api")

        mock_adapter_cls.return_value.suggest_optimizations.side_effect = RuntimeError("boom")

        resp = post_json(client, url, {"plan_id": plan.id, "days": 30})

        assert_json_error_contract(resp, 500, require_success_false=True)

    def test_live_guidance_missing_fields_returns_400(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("live_guidance_api")

        resp = post_json(client, url, {"session_id": 1})
        assert resp.status_code == 400
        assert "session_id und question erforderlich" in resp.json()["error"]

    def test_live_guidance_requires_post(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("live_guidance_api")

        resp = get_json(client, url)

        assert resp.status_code == 405
        assert "error" in resp.json()
        assert "POST required" in resp.json()["error"]

    @patch("core.views.ai_recommendations._check_ai_rate_limit")
    def test_live_guidance_rate_limited_contract_429(self, mock_rate_limit, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("live_guidance_api")

        mock_rate_limit.return_value = JsonResponse(
            {"error": "guidance limit reached", "success": False, "rate_limited": True},
            status=429,
        )

        resp = post_json(client, url, {"session_id": 1, "question": "Hi"})

        data = assert_json_error_contract(resp, 429, require_success_false=True)
        assert data.get("rate_limited") is True

    def test_live_guidance_foreign_session_returns_404(self, client):
        owner = UserFactory()
        other = UserFactory()
        session = TrainingseinheitFactory(user=owner)
        client.force_login(other)
        url = reverse("live_guidance_api")

        resp = post_json(
            client,
            url,
            {
                "session_id": session.id,
                "question": "Soll ich Gewicht steigern?",
            },
        )
        assert resp.status_code == 404

    @patch("ai_coach.live_guidance.LiveGuidance")
    def test_live_guidance_invalid_result_structure_returns_500(self, mock_guidance_cls, client):
        user = UserFactory()
        session = TrainingseinheitFactory(user=user)
        client.force_login(user)
        url = reverse("live_guidance_api")

        mock_guidance_cls.return_value.get_guidance.return_value = "bad-structure"

        resp = post_json(
            client,
            url,
            {
                "session_id": session.id,
                "question": "Form-Check?",
            },
        )

        assert resp.status_code == 500
        assert "Ungültige Antwort" in resp.json()["error"]

    @patch("core.views.ai_recommendations._check_ai_rate_limit")
    def test_generate_plan_stream_rate_limited_returns_sse_429(self, mock_rate_limit, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_stream_api")

        mock_rate_limit.return_value = JsonResponse(
            {"success": False, "error": "Daily limit reached", "rate_limited": True},
            status=429,
        )

        resp = get_json(client, url)

        assert resp.status_code == 429
        assert "text/event-stream" in resp["Content-Type"]
        payload = b"".join(resp.streaming_content).decode("utf-8")
        assert "Daily limit reached" in payload
        assert '"success": false' in payload.lower()

    def test_generate_plan_stream_requires_get_plain_405(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_stream_api")

        resp = post_json(client, url, {"plan_type": "3er-split"})

        assert resp.status_code == 405
        assert "GET required" in resp.content.decode("utf-8")

    def test_apply_optimizations_requires_post(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("apply_optimizations_api")

        resp = get_json(client, url)

        assert_json_error_contract(resp, 405)
        assert "POST request required" in resp.json()["error"]

    def test_apply_optimizations_missing_plan_id_returns_400(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("apply_optimizations_api")

        resp = post_json(client, url, {"optimizations": []})

        assert_json_error_contract(resp, 400)
        assert "plan_id required" in resp.json()["error"]

    def test_apply_optimizations_foreign_plan_returns_json_404(self, client):
        owner = UserFactory()
        other = UserFactory()
        plan = PlanFactory(user=owner)
        client.force_login(other)
        url = reverse("apply_optimizations_api")

        resp = post_json(client, url, {"plan_id": plan.id, "optimizations": []})

        assert_json_error_contract(resp, 404)
        assert "Plan nicht gefunden" in resp.json()["error"]

    @patch("core.views.ai_recommendations.Plan.objects.filter", side_effect=RuntimeError("boom"))
    def test_apply_optimizations_internal_error_contract_500(self, _mock_filter, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("apply_optimizations_api")

        resp = client.post(
            url,
            json.dumps({"plan_id": 1, "optimizations": []}),
            content_type="application/json",
            secure=True,
        )

        assert_json_error_contract(resp, 500, require_success_false=True)
