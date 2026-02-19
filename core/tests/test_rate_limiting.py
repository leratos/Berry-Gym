"""
Tests für KI Rate Limiting (Phase 7.1).

Prüft:
- check_and_increment_ai_limit: Zähler, Limit, Reset
- _reset_ai_counters_if_needed: täglicher Reset
- _check_ai_rate_limit Helper: Bypass in DEBUG, 429 wenn Limit erreicht
- Endpoints: generate_plan_api, optimize_plan_api, live_guidance_api
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from core.models import UserProfile  # noqa: F401 – needed for signal-created profile access


# ===========================================================================
# UserProfile Counter-Logik
# ===========================================================================


class TestAiCounterReset(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("counter_user", password="pw")
        self.profile = self.user.profile

    def test_counters_reset_on_new_day(self):
        """Zähler werden zurückgesetzt wenn ein neuer Tag beginnt."""
        yesterday = timezone.now().date() - timedelta(days=1)
        self.profile.ai_plan_count_today = 3
        self.profile.ai_guidance_count_today = 40
        self.profile.ai_analysis_count_today = 8
        self.profile.ai_counter_reset_date = yesterday
        self.profile.save()

        self.profile._reset_ai_counters_if_needed()
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.ai_plan_count_today, 0)
        self.assertEqual(self.profile.ai_guidance_count_today, 0)
        self.assertEqual(self.profile.ai_analysis_count_today, 0)
        self.assertEqual(self.profile.ai_counter_reset_date, timezone.now().date())

    def test_counters_not_reset_same_day(self):
        """Zähler werden NICHT zurückgesetzt wenn es noch derselbe Tag ist."""
        today = timezone.now().date()
        self.profile.ai_plan_count_today = 2
        self.profile.ai_counter_reset_date = today
        self.profile.save()

        self.profile._reset_ai_counters_if_needed()
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.ai_plan_count_today, 2)

    def test_reset_when_date_is_none(self):
        """Zähler werden zurückgesetzt wenn reset_date None ist (erster Aufruf)."""
        self.profile.ai_plan_count_today = 1
        self.profile.ai_counter_reset_date = None
        self.profile.save()

        self.profile._reset_ai_counters_if_needed()
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.ai_plan_count_today, 0)


class TestCheckAndIncrementAiLimit(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("limit_user", password="pw")
        self.profile = self.user.profile
        self.profile.ai_counter_reset_date = timezone.now().date()
        self.profile.save()

    def test_first_request_allowed(self):
        """Erster Request wird erlaubt und Zähler erhöht."""
        result = self.profile.check_and_increment_ai_limit("plan", 3)
        self.assertTrue(result)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ai_plan_count_today, 1)

    def test_request_at_limit_denied(self):
        """Request bei erreichtem Limit wird abgelehnt, Zähler bleibt."""
        self.profile.ai_plan_count_today = 3
        self.profile.save()
        result = self.profile.check_and_increment_ai_limit("plan", 3)
        self.assertFalse(result)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ai_plan_count_today, 3)

    def test_request_below_limit_increments(self):
        """Request unterhalb Limit erhöht Zähler."""
        self.profile.ai_plan_count_today = 2
        self.profile.save()
        result = self.profile.check_and_increment_ai_limit("plan", 3)
        self.assertTrue(result)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ai_plan_count_today, 3)

    def test_guidance_counter_independent(self):
        """guidance- und plan-Counter sind unabhängig voneinander."""
        self.profile.ai_plan_count_today = 3
        self.profile.save()
        plan_result = self.profile.check_and_increment_ai_limit("plan", 3)
        self.assertFalse(plan_result)
        guidance_result = self.profile.check_and_increment_ai_limit("guidance", 50)
        self.assertTrue(guidance_result)

    def test_unknown_limit_type_allowed(self):
        """Unbekannter limit_type wird immer erlaubt (fail-open)."""
        result = self.profile.check_and_increment_ai_limit("unknown_type", 5)
        self.assertTrue(result)

    def test_all_three_types(self):
        """Alle drei Counter-Typen funktionieren korrekt."""
        for limit_type, field in [
            ("plan", "ai_plan_count_today"),
            ("guidance", "ai_guidance_count_today"),
            ("analysis", "ai_analysis_count_today"),
        ]:
            result = self.profile.check_and_increment_ai_limit(limit_type, 5)
            self.assertTrue(result, f"Typ {limit_type} sollte erlaubt sein")
            self.profile.refresh_from_db()
            self.assertEqual(getattr(self.profile, field), 1)


# ===========================================================================
# _check_ai_rate_limit Helper
# ===========================================================================


class TestCheckAiRateLimitHelper(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("helper_user", password="pw")
        self.profile = self.user.profile
        self.profile.ai_counter_reset_date = timezone.now().date()
        self.profile.save()

    def _make_request(self):
        request = MagicMock()
        request.user = self.user
        return request

    @patch("core.views.ai_recommendations.settings")
    def test_bypass_returns_none(self, mock_settings):
        """Im Bypass-Modus (DEBUG/Test) wird immer None zurückgegeben."""
        mock_settings.RATELIMIT_BYPASS = True
        from core.views.ai_recommendations import _check_ai_rate_limit

        result = _check_ai_rate_limit(self._make_request(), "plan")
        self.assertIsNone(result)

    @patch("core.views.ai_recommendations.settings")
    def test_below_limit_returns_none(self, mock_settings):
        """Unterhalb des Limits wird None zurückgegeben."""
        mock_settings.RATELIMIT_BYPASS = False
        mock_settings.AI_RATE_LIMIT_PLAN_GENERATION = 5
        mock_settings.AI_RATE_LIMIT_LIVE_GUIDANCE = 50
        mock_settings.AI_RATE_LIMIT_ANALYSIS = 10
        from core.views.ai_recommendations import _check_ai_rate_limit

        result = _check_ai_rate_limit(self._make_request(), "plan")
        self.assertIsNone(result)

    @patch("core.views.ai_recommendations.settings")
    def test_at_limit_returns_429(self, mock_settings):
        """Bei erreichtem Limit wird 429-Response zurückgegeben."""
        mock_settings.RATELIMIT_BYPASS = False
        mock_settings.AI_RATE_LIMIT_PLAN_GENERATION = 1
        mock_settings.AI_RATE_LIMIT_LIVE_GUIDANCE = 50
        mock_settings.AI_RATE_LIMIT_ANALYSIS = 10
        self.profile.ai_plan_count_today = 1
        self.profile.save()

        from core.views.ai_recommendations import _check_ai_rate_limit

        result = _check_ai_rate_limit(self._make_request(), "plan")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 429)
        data = json.loads(result.content)
        self.assertFalse(data["success"])
        self.assertTrue(data["rate_limited"])
        self.assertIn("Limit", data["error"])

    @patch("core.views.ai_recommendations.settings")
    def test_guidance_429_message_contains_limit(self, mock_settings):
        """429-Nachricht erwähnt das konkrete Limit."""
        mock_settings.RATELIMIT_BYPASS = False
        mock_settings.AI_RATE_LIMIT_PLAN_GENERATION = 3
        mock_settings.AI_RATE_LIMIT_LIVE_GUIDANCE = 50
        mock_settings.AI_RATE_LIMIT_ANALYSIS = 10
        self.profile.ai_guidance_count_today = 50
        self.profile.save()

        from core.views.ai_recommendations import _check_ai_rate_limit

        result = _check_ai_rate_limit(self._make_request(), "guidance")
        data = json.loads(result.content)
        self.assertIn("50", data["error"])


# ===========================================================================
# Endpoint-Integration
# ===========================================================================


class TestRateLimitEndpoints(TestCase):
    """Prüft Basis-Verhalten der Rate-Limited-Endpoints (BYPASS=True in Tests)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("endpoint_user", password="pw")
        self.client.login(username="endpoint_user", password="pw")

    def test_generate_plan_api_requires_post(self):
        response = self.client.get("/api/generate-plan/")
        self.assertEqual(response.status_code, 405)

    def test_optimize_plan_api_requires_post(self):
        response = self.client.get("/api/optimize-plan/")
        self.assertEqual(response.status_code, 405)

    def test_live_guidance_api_requires_post(self):
        response = self.client.get("/api/live-guidance/")
        self.assertEqual(response.status_code, 405)

    def test_generate_plan_stream_requires_login(self):
        anon_client = Client()
        response = anon_client.get("/api/generate-plan/stream/")
        self.assertIn(response.status_code, [302, 403])
