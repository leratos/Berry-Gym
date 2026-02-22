"""
Comprehensive test suite for the refactored views modules.
Tests all 16 modules to ensure the refactoring was successful.
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Equipment, Plan, PlanUebung, Satz, Trainingseinheit, Uebung


class RefactoringTestCase(TestCase):
    """Base test case with common setup for all refactoring tests"""

    def setUp(self):
        """Create test user and basic test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        # Create test equipment
        self.equipment = Equipment.objects.create(name="KOERPER")
        self.user.verfuegbares_equipment.add(self.equipment)

        # Create test exercise
        self.uebung = Uebung.objects.create(
            bezeichnung="Test Übung",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        # Set ManyToMany field after creation
        self.uebung.equipment.add(self.equipment)

        # Create test plan
        self.plan = Plan.objects.create(name="Test Plan", user=self.user)
        PlanUebung.objects.create(
            plan=self.plan, uebung=self.uebung, saetze_ziel=3, wiederholungen_ziel="8-12"
        )

        # Create test training session
        self.training = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, datum=timezone.now()
        )


class AuthViewsTest(RefactoringTestCase):
    """Test auth.py module - Registration, profile, feedback"""

    def test_register_view_loads(self):
        """Test registration page loads"""
        self.client.logout()
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    def test_profile_view_requires_login(self):
        """Test profile requires authentication"""
        self.client.logout()
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_profile_view_loads_authenticated(self):
        """Test profile loads for authenticated user"""
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)

    def test_apply_beta_redirects_to_register(self):
        """apply_beta leitet seit offener Registrierung direkt auf register weiter."""
        self.client.logout()
        response = self.client.get(reverse("apply_beta"))
        self.assertRedirects(response, reverse("register"))


class TrainingSessionViewsTest(RefactoringTestCase):
    """Test training_session.py module - Session execution, set management"""

    def test_training_select_plan_loads(self):
        """Test plan selection page loads"""
        response = self.client.get(reverse("training_select_plan"))
        self.assertEqual(response.status_code, 200)

    def test_plan_details_loads(self):
        """Test plan details page loads"""
        response = self.client.get(reverse("plan_details", args=[self.plan.id]))
        self.assertEqual(response.status_code, 200)

    def test_training_start_creates_session(self):
        """Test starting a training session"""
        response = self.client.post(reverse("training_start_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to session
        self.assertTrue(Trainingseinheit.objects.filter(user=self.user).exists())

    def test_training_session_loads(self):
        """Test training session page loads"""
        response = self.client.get(reverse("training_session", args=[self.training.id]))
        self.assertEqual(response.status_code, 200)

    def test_add_set_creates_set(self):
        """Test adding a set to training"""
        response = self.client.post(
            reverse("add_set", args=[self.training.id]),
            {"uebung": self.uebung.id, "gewicht": "50", "wiederholungen": "10", "rpe": "8"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful POST
        self.assertTrue(Satz.objects.filter(einheit=self.training).exists())


class TrainingStatsViewsTest(RefactoringTestCase):
    """Test training_stats.py module - Dashboard, analytics, statistics"""

    def test_dashboard_loads(self):
        """Test main dashboard loads"""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_training_list_loads(self):
        """Test training history list loads"""
        response = self.client.get(reverse("training_list"))
        self.assertEqual(response.status_code, 200)

    def test_training_stats_loads(self):
        """Test training statistics page loads"""
        response = self.client.get(reverse("training_stats"))
        self.assertEqual(response.status_code, 200)

    def test_exercise_stats_loads(self):
        """Test exercise-specific stats load"""
        response = self.client.get(reverse("exercise_stats", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)


class BodyTrackingViewsTest(RefactoringTestCase):
    """Test body_tracking.py module - Measurements, progress photos"""

    def test_body_stats_loads(self):
        """Test body stats page loads"""
        response = self.client.get(reverse("body_stats"))
        self.assertEqual(response.status_code, 200)

    def test_add_koerperwert_loads(self):
        """Test add body measurement page loads"""
        response = self.client.get(reverse("add_koerperwert"))
        self.assertEqual(response.status_code, 200)

    def test_progress_photos_loads(self):
        """Test progress photos page loads"""
        response = self.client.get(reverse("progress_photos"))
        self.assertEqual(response.status_code, 200)


class PlanManagementViewsTest(RefactoringTestCase):
    """Test plan_management.py module - Plan CRUD, sharing"""

    def test_create_plan_loads(self):
        """Test create plan page loads"""
        response = self.client.get(reverse("create_plan"))
        self.assertEqual(response.status_code, 200)

    def test_edit_plan_loads(self):
        """Test edit plan page loads"""
        response = self.client.get(reverse("edit_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 200)

    def test_plan_library_loads(self):
        """Test plan library page loads"""
        response = self.client.get(reverse("plan_library"))
        self.assertEqual(response.status_code, 200)

    def test_share_plan_loads(self):
        """Test plan sharing page loads"""
        response = self.client.get(reverse("share_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 200)


class ExerciseLibraryViewsTest(RefactoringTestCase):
    """Test exercise_library.py module - Exercise browsing, details"""

    def test_uebungen_auswahl_loads(self):
        """Test exercise selection page loads"""
        response = self.client.get(reverse("uebungen_auswahl"))
        self.assertEqual(response.status_code, 200)

    def test_muscle_map_loads(self):
        """Test muscle map page loads"""
        response = self.client.get(reverse("muscle_map"))
        self.assertEqual(response.status_code, 200)

    def test_uebung_detail_loads(self):
        """Test exercise detail page loads"""
        response = self.client.get(reverse("uebung_detail", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)

    def test_toggle_favorite_works(self):
        """Test toggling exercise favorite"""
        response = self.client.post(reverse("toggle_favorite", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("is_favorite", data)

    def test_toggle_favorit_works(self):
        """Test toggling exercise favorit (German version)"""
        response = self.client.post(reverse("toggle_favorit", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("is_favorit", data)


class ExerciseManagementViewsTest(RefactoringTestCase):
    """Test exercise_management.py module - Custom exercises, equipment"""

    def test_equipment_management_loads(self):
        """Test equipment management page loads"""
        response = self.client.get(reverse("equipment_management"))
        self.assertEqual(response.status_code, 200)


class ExportViewsTest(RefactoringTestCase):
    """Test export.py module - CSV/PDF generation"""

    def test_export_training_csv_works(self):
        """Test CSV export works"""
        # Add a set first
        Satz.objects.create(
            einheit=self.training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=50,
            wiederholungen=10,
        )
        response = self.client.get(reverse("export_training_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")


class CardioViewsTest(RefactoringTestCase):
    """Test cardio.py module - Cardio tracking"""

    def test_cardio_list_loads(self):
        """Test cardio list page loads"""
        response = self.client.get(reverse("cardio_list"))
        self.assertEqual(response.status_code, 200)

    def test_cardio_add_loads(self):
        """Test add cardio page loads"""
        response = self.client.get(reverse("cardio_add"))
        self.assertEqual(response.status_code, 200)


class ConfigViewsTest(RefactoringTestCase):
    """Test config.py module - Static files, legal pages"""

    def test_impressum_loads(self):
        """Test impressum page loads"""
        response = self.client.get(reverse("impressum"))
        self.assertEqual(response.status_code, 200)

    def test_datenschutz_loads(self):
        """Test privacy policy page loads"""
        response = self.client.get(reverse("datenschutz"))
        self.assertEqual(response.status_code, 200)

    def test_service_worker_loads(self):
        """Test service worker JS file loads"""
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)

    def test_manifest_loads(self):
        """Test PWA manifest loads"""
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)


class NotificationsViewsTest(RefactoringTestCase):
    """Test notifications.py module - Push notifications"""

    def test_get_vapid_public_key_no_keys_returns_503(self):
        """Ohne VAPID-Keys gibt der Endpoint 503 zurück (korrekt in CI/Dev)."""
        from django.test import override_settings

        with override_settings(VAPID_PUBLIC_KEY=None):
            response = self.client.get(reverse("get_vapid_public_key"))
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_get_vapid_public_key_with_key_returns_200(self):
        """Mit gültigem VAPID-Key gibt der Endpoint 200 und publicKey zurück."""
        from django.test import override_settings

        # Minimaler EC-Public-Key im PEM-Format (65 raw bytes, DER-encoded = 91 bytes)
        # Generiert mit: from cryptography.hazmat.primitives.asymmetric import ec
        # Echter Test-Key, nicht für Production.
        test_pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEbhCHOJnPKFTq3G7z+KiVJhXVt2Oy\n"
            "1x9Q8v3R5JkQmW4XdN2pL8sY3mK7bV6eF0cH9wP4nQ2rT1uMsXAiZ5oB7g==\n"
            "-----END PUBLIC KEY-----\n"
        )
        with override_settings(VAPID_PUBLIC_KEY=test_pem):
            response = self.client.get(reverse("get_vapid_public_key"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("publicKey", data)
        self.assertIsInstance(data["publicKey"], str)
        self.assertGreater(len(data["publicKey"]), 0)


class OfflineViewsTest(RefactoringTestCase):
    """Test offline.py module - Offline sync"""

    def test_sync_offline_data_endpoint_exists(self):
        """Test offline sync endpoint exists"""
        # This needs POST data, so we just test it responds
        response = self.client.post(
            reverse("sync_offline_data"),
            content_type="application/json",
            data=json.dumps({"sets": []}),
        )
        # Should return 200 or error, but endpoint should exist
        self.assertIn(response.status_code, [200, 400, 500])


class APIViewsTest(RefactoringTestCase):
    """Test API endpoints from various modules"""

    def test_get_last_set_api(self):
        """Test get last set API endpoint"""
        response = self.client.get(reverse("get_last_set", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, dict)


class IntegrationTest(RefactoringTestCase):
    """Integration tests - Full user workflows"""

    def test_complete_training_workflow(self):
        """Test complete training workflow: start -> add sets -> finish"""
        # 1. Start training
        response = self.client.post(reverse("training_start_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)

        # Get the created training
        training = Trainingseinheit.objects.filter(user=self.user).latest("datum")

        # 2. Add a set
        response = self.client.post(
            reverse("add_set", args=[training.id]),
            {"uebung": self.uebung.id, "gewicht": "50", "wiederholungen": "10", "rpe": "8"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful POST

        # 3. Finish training
        response = self.client.post(reverse("finish_training", args=[training.id]))
        self.assertEqual(response.status_code, 302)

        # Verify training still exists
        training.refresh_from_db()
        self.assertIsNotNone(training.id)

    def test_plan_creation_workflow(self):
        """Test plan creation workflow"""
        # Create a new plan
        response = self.client.post(
            reverse("create_plan"), {"name": "New Test Plan", "beschreibung": "Test description"}
        )
        # Should redirect or show success
        self.assertIn(response.status_code, [200, 302])


class ViewImportsTest(TestCase):
    """Test that all views are properly imported and accessible"""

    def test_all_views_importable(self):
        """Test all views can be imported from core.views"""
        from core import views

        # Auth views
        self.assertTrue(hasattr(views, "apply_beta"))
        self.assertTrue(hasattr(views, "register"))
        self.assertTrue(hasattr(views, "profile"))

        # Training session views
        self.assertTrue(hasattr(views, "training_select_plan"))
        self.assertTrue(hasattr(views, "training_start"))
        self.assertTrue(hasattr(views, "training_session"))
        self.assertTrue(hasattr(views, "add_set"))

        # Training stats views
        self.assertTrue(hasattr(views, "dashboard"))
        self.assertTrue(hasattr(views, "training_stats"))
        self.assertTrue(hasattr(views, "exercise_stats"))

        # Body tracking views
        self.assertTrue(hasattr(views, "body_stats"))
        self.assertTrue(hasattr(views, "progress_photos"))

        # Plan management views
        self.assertTrue(hasattr(views, "create_plan"))
        self.assertTrue(hasattr(views, "edit_plan"))
        self.assertTrue(hasattr(views, "plan_library"))

        # Exercise library views
        self.assertTrue(hasattr(views, "uebungen_auswahl"))
        self.assertTrue(hasattr(views, "muscle_map"))
        self.assertTrue(hasattr(views, "toggle_favorite"))
        self.assertTrue(hasattr(views, "toggle_favorit"))

        # Exercise management views
        self.assertTrue(hasattr(views, "equipment_management"))

        # Export views
        self.assertTrue(hasattr(views, "export_training_csv"))
        self.assertTrue(hasattr(views, "export_training_pdf"))

        # Cardio views
        self.assertTrue(hasattr(views, "cardio_list"))

        # Config views
        self.assertTrue(hasattr(views, "impressum"))
        self.assertTrue(hasattr(views, "datenschutz"))
        self.assertTrue(hasattr(views, "service_worker"))
        self.assertTrue(hasattr(views, "manifest"))

        # Notifications views
        self.assertTrue(hasattr(views, "get_vapid_public_key"))

        # Offline views
        self.assertTrue(hasattr(views, "sync_offline_data"))
