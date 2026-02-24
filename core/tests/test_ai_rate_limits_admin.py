"""
Tests für KI-Rate-Limiting mit Site-weiten und User-spezifischen Limits.
"""

import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Plan, SiteSettings, Trainingseinheit


class TestSiteSettings(TestCase):
    """Tests für das SiteSettings Singleton Model."""

    def test_singleton_creation(self):
        """SiteSettings sollte als Singleton nur einmal existieren."""
        settings1 = SiteSettings.load()
        settings2 = SiteSettings.load()
        self.assertEqual(settings1.pk, settings2.pk)
        self.assertEqual(settings1.pk, 1)

    def test_default_values(self):
        """SiteSettings sollte mit Defaults erstellt werden."""
        settings = SiteSettings.load()
        self.assertEqual(settings.ai_limit_plan_generation, 3)
        self.assertEqual(settings.ai_limit_live_guidance, 50)
        self.assertEqual(settings.ai_limit_analysis, 10)

    def test_update_values(self):
        """SiteSettings sollte aktualisierbar sein."""
        settings = SiteSettings.load()
        settings.ai_limit_plan_generation = 5
        settings.save()

        # Reload und prüfen
        settings = SiteSettings.load()
        self.assertEqual(settings.ai_limit_plan_generation, 5)

    def test_cannot_delete(self):
        """SiteSettings sollte nicht löschbar sein (Singleton)."""
        settings = SiteSettings.load()
        settings.delete()
        # Sollte noch existieren
        self.assertTrue(SiteSettings.objects.filter(pk=1).exists())


class TestUserCustomLimits(TestCase):
    """Tests für User-spezifische KI-Limit Overrides."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.client.force_login(self.user)

    def test_custom_limit_fields_exist(self):
        """UserProfile sollte custom limit Felder haben."""
        profile = self.user.profile
        self.assertIsNone(profile.custom_ai_limit_plan)
        self.assertIsNone(profile.custom_ai_limit_guidance)
        self.assertIsNone(profile.custom_ai_limit_analysis)

    def test_custom_limit_can_be_set(self):
        """User kann custom limits erhalten."""
        profile = self.user.profile
        profile.custom_ai_limit_plan = 10
        profile.custom_ai_limit_guidance = 100
        profile.custom_ai_limit_analysis = 50
        profile.save()

        # Reload und prüfen
        profile.refresh_from_db()
        self.assertEqual(profile.custom_ai_limit_plan, 10)
        self.assertEqual(profile.custom_ai_limit_guidance, 100)
        self.assertEqual(profile.custom_ai_limit_analysis, 50)


class TestAIRateLimitHierarchy(TestCase):
    """Tests für die Limit-Hierarchie: User-Custom > Site-Default > Settings-Fallback."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.client.force_login(self.user)

        # Plan erstellen für AI-Endpoints
        self.plan = Plan.objects.create(name="TestPlan", user=self.user)
        self.user.profile.active_plan_group = uuid.uuid4()
        self.user.profile.save()

        # Training erstellen
        self.training = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, abgeschlossen=True
        )

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_site_default_limits_used_without_custom(self, MockPlanAdapter):
        """Ohne User-Custom-Limit wird Site-Default verwendet."""
        # Mock PlanAdapter damit kein LLMClient initialisiert wird
        mock_instance = MockPlanAdapter.return_value
        mock_instance.suggest_optimizations.return_value = {"optimizations": []}

        # Site-Settings auf niedrige Werte setzen
        site_settings = SiteSettings.load()
        site_settings.ai_limit_analysis = 2
        site_settings.save()

        # 2 Requests sollten funktionieren (optimize_plan_api nutzt "analysis" limit)
        payload = {"plan_id": str(self.plan.id)}
        resp1 = self.client.post(
            reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
        )
        resp2 = self.client.post(
            reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        # 3. Request sollte 429 returnen
        resp3 = self.client.post(
            reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
        )
        self.assertEqual(resp3.status_code, 429)
        data = resp3.json()
        self.assertTrue(data["rate_limited"])
        self.assertIn("2 Analyse-Calls", data["error"])

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_user_custom_limit_overrides_site_default(self, MockPlanAdapter):
        """User-Custom-Limit überschreibt Site-Default."""
        # Mock PlanAdapter damit kein LLMClient initialisiert wird
        mock_instance = MockPlanAdapter.return_value
        mock_instance.suggest_optimizations.return_value = {"optimizations": []}

        # Site-Default auf 2 setzen
        site_settings = SiteSettings.load()
        site_settings.ai_limit_analysis = 2
        site_settings.save()

        # User-Custom auf 5 setzen
        profile = self.user.profile
        profile.custom_ai_limit_analysis = 5
        profile.save()

        # 5 Requests sollten funktionieren
        payload = {"plan_id": str(self.plan.id)}
        for _ in range(5):
            resp = self.client.post(
                reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
            )
            self.assertEqual(resp.status_code, 200)

        # 6. Request sollte 429 returnen
        resp = self.client.post(
            reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
        )
        self.assertEqual(resp.status_code, 429)
        data = resp.json()
        self.assertIn("5 Analyse-Calls", data["error"])

    @patch("ai_coach.plan_adapter.PlanAdapter")
    def test_beta_user_unlimited_limits(self, MockPlanAdapter):
        """Beta-User mit hohen Custom-Limits."""
        # Mock PlanAdapter damit kein LLMClient initialisiert wird
        mock_instance = MockPlanAdapter.return_value
        mock_instance.suggest_optimizations.return_value = {"optimizations": []}

        # User als Beta-Tester mit sehr hohen Limits
        profile = self.user.profile
        profile.custom_ai_limit_plan = 1000
        profile.custom_ai_limit_guidance = 1000
        profile.custom_ai_limit_analysis = 1000
        profile.save()

        # Mehrere Requests sollten funktionieren
        payload = {"plan_id": str(self.plan.id)}
        for _ in range(10):
            resp = self.client.post(
                reverse("optimize_plan_api"), payload, content_type="application/json", secure=True
            )
            self.assertEqual(resp.status_code, 200)
