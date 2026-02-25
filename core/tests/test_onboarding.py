"""Quick Test für Onboarding Feature"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase


class OnboardingTest(TestCase):
    """Test Onboarding-Funktionalität"""

    def setUp(self):
        """Setup für alle Tests"""
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

    def test_new_user_has_not_seen_onboarding(self):
        """Neue User sollten has_seen_onboarding=False haben"""
        user = User.objects.create_user(username="newuser", password="testpass")
        profile = user.profile
        self.assertFalse(profile.has_seen_onboarding)

    def test_mark_onboarding_complete(self):
        """Onboarding kann als abgeschlossen markiert werden"""
        profile = self.user.profile

        # Initial False
        self.assertFalse(profile.has_seen_onboarding)

        # Markieren
        profile.has_seen_onboarding = True
        profile.save()

        # Neu laden und prüfen
        profile.refresh_from_db()
        self.assertTrue(profile.has_seen_onboarding)

    def test_mark_onboarding_complete_view(self):
        """View zum Markieren funktioniert"""
        # POST Request
        response = self.client.post("/onboarding/complete/")

        # Check Response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        # Check DB
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.has_seen_onboarding)

    def test_mark_onboarding_complete_error(self):
        """View behandelt Fehler korrekt"""
        # Mock profile.save um Exception zu werfen
        with patch.object(type(self.user.profile), "save", side_effect=Exception("Test error")):
            response = self.client.post("/onboarding/complete/")

            # Check Error Response
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()["success"], False)
            self.assertIn("error", response.json())

    def test_restart_onboarding_ajax(self):
        """Restart-View funktioniert mit AJAX"""
        # Erst als completed markieren
        self.user.profile.has_seen_onboarding = True
        self.user.profile.save()

        # AJAX Request zum Zurücksetzen
        response = self.client.get("/onboarding/restart/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # Check Response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        # Check DB
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.has_seen_onboarding)

    def test_restart_onboarding_redirect(self):
        """Restart-View redirected ohne AJAX"""
        # Erst als completed markieren
        self.user.profile.has_seen_onboarding = True
        self.user.profile.save()

        # Normal Request (kein AJAX)
        response = self.client.get("/onboarding/restart/")

        # Check Redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")  # dashboard URL

        # Check DB
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.has_seen_onboarding)

    def test_restart_onboarding_ajax_error(self):
        """Restart-View behandelt AJAX-Fehler"""
        with patch.object(type(self.user.profile), "save", side_effect=Exception("Test error")):
            response = self.client.get(
                "/onboarding/restart/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
            )

            # Check Error Response
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()["success"], False)

    def test_restart_onboarding_redirect_error(self):
        """Restart-View behandelt Redirect-Fehler"""
        with patch.object(type(self.user.profile), "save", side_effect=Exception("Test error")):
            response = self.client.get("/onboarding/restart/")

            # Check Redirect auch bei Error
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")
