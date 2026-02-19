"""
Tests für Phase 7.4 – Wochenübersicht im Dashboard.

Prüft:
- _get_week_overview: 7 Einträge, korrektes has_training, is_today, is_future
- trainings_pro_woche Feld auf UserProfile
- Dashboard-Context enthält week_overview und trainings_ziel
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Plan, Trainingseinheit, UserProfile  # noqa: F401

# ===========================================================================
# ===========================================================================
# _get_week_overview Helper
# ===========================================================================


class TestGetWeekOverview(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("week_user", password="pw")

    def _call(self, heute=None):
        from core.views.training_stats import _get_week_overview

        if heute is None:
            heute = timezone.now()
        return _get_week_overview(self.user, heute)

    def test_returns_seven_days(self):
        result = self._call()
        self.assertEqual(len(result), 7)

    def test_first_day_is_monday(self):
        result = self._call()
        self.assertEqual(result[0]["label"], "Mo")

    def test_last_day_is_sunday(self):
        result = self._call()
        self.assertEqual(result[6]["label"], "So")

    def test_today_is_marked(self):
        result = self._call()
        today_entries = [d for d in result if d["is_today"]]
        self.assertEqual(len(today_entries), 1)

    def test_no_training_no_has_training(self):
        result = self._call()
        for day in result:
            self.assertFalse(day["has_training"])

    def test_abgeschlossenes_training_sichtbar(self):
        """Abgeschlossene Trainings werden als has_training markiert."""
        heute = timezone.now()
        training = Trainingseinheit.objects.create(user=self.user, abgeschlossen=True, datum=heute)
        result = self._call(heute)
        today_entry = next(d for d in result if d["is_today"])
        self.assertTrue(today_entry["has_training"])
        self.assertEqual(today_entry["training_id"], training.id)

    def test_nicht_abgeschlossenes_training_unsichtbar(self):
        """Nicht abgeschlossene Trainings zählen nicht."""
        heute = timezone.now()
        Trainingseinheit.objects.create(user=self.user, abgeschlossen=False, datum=heute)
        result = self._call(heute)
        today_entry = next(d for d in result if d["is_today"])
        self.assertFalse(today_entry["has_training"])

    def test_vergangener_tag_ohne_training_ist_future_false(self):
        """Vergangener Tag ohne Training: is_future=False, has_training=False."""
        # Mittwoch dieser Woche
        heute = timezone.now()
        result = self._call(heute)
        montag_entry = result[0]  # Montag
        if montag_entry["date"] < heute.date():
            self.assertFalse(montag_entry["is_future"])
            self.assertFalse(montag_entry["has_training"])

    def test_training_anderer_user_nicht_sichtbar(self):
        """Trainings anderer User erscheinen nicht."""
        anderer = User.objects.create_user("anderer", password="pw")
        heute = timezone.now()
        Trainingseinheit.objects.create(user=anderer, abgeschlossen=True, datum=heute)
        result = self._call(heute)
        today_entry = next(d for d in result if d["is_today"])
        self.assertFalse(today_entry["has_training"])


# ===========================================================================
# UserProfile.trainings_pro_woche
# ===========================================================================


class TestTrainingsProWoche(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ziel_user", password="pw")

    def test_default_ist_drei(self):
        self.assertEqual(self.user.profile.trainings_pro_woche, 3)

    def test_kann_gesetzt_werden(self):
        self.user.profile.trainings_pro_woche = 5
        self.user.profile.save()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.trainings_pro_woche, 5)


# ===========================================================================
# Dashboard-Context
# ===========================================================================


class TestDashboardWochenContext(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("dash_week_user", password="pw")
        self.client.login(username="dash_week_user", password="pw")

    def test_week_overview_in_context(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("week_overview", response.context)
        self.assertEqual(len(response.context["week_overview"]), 7)

    def test_trainings_ziel_in_context(self):
        response = self.client.get(reverse("dashboard"))
        self.assertIn("trainings_ziel", response.context)
        self.assertEqual(response.context["trainings_ziel"], 3)

    def test_trainings_ziel_aus_profil(self):
        self.user.profile.trainings_pro_woche = 4
        self.user.profile.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["trainings_ziel"], 4)

    def test_wochenkarte_im_html(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Diese Woche")
        self.assertContains(response, "Mo")
        self.assertContains(response, "So")
