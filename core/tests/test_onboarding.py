"""Quick Test für Onboarding Feature"""

from django.contrib.auth.models import User
from django.test import TestCase


class OnboardingTest(TestCase):
    """Test Onboarding-Funktionalität"""

    def test_new_user_has_not_seen_onboarding(self):
        """Neue User sollten has_seen_onboarding=False haben"""
        user = User.objects.create_user(username="testuser", password="testpass")
        profile = user.profile
        self.assertFalse(profile.has_seen_onboarding)

    def test_mark_onboarding_complete(self):
        """Onboarding kann als abgeschlossen markiert werden"""
        user = User.objects.create_user(username="testuser", password="testpass")
        profile = user.profile

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
        user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        # POST Request
        response = self.client.post("/onboarding/complete/")

        # Check Response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

        # Check DB
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.has_seen_onboarding)
