"""
Tests für core/views/auth.py

Abdeckung:
- _validate_registration_fields(): pure Validierung
- _handle_update_profile(): DB-Mutation
- _handle_change_password(): Password-Check
- apply_beta(): Redirect
- register(): GET + POST (Erfolg/Fehler)
- profile(): GET + POST (Update + Passwort)

Login-Views werden durch Django's auth-System bereitgestellt (keine Tests nötig).
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.views.auth import (
    _handle_change_password,
    _handle_update_profile,
    _validate_registration_fields,
)


# ──────────────────────────────────────────────────────────────────────────────
# Pure Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────
class TestValidateRegistrationFields(TestCase):
    def test_alle_felder_korrekt_keine_fehler(self):
        errors = _validate_registration_fields("neuer_user", "neu@test.de", "pass1234", "pass1234")
        self.assertEqual(errors, [])

    def test_fehlender_benutzername(self):
        errors = _validate_registration_fields("", "neu@test.de", "pass1234", "pass1234")
        self.assertTrue(any("Benutzername" in e for e in errors))

    def test_benutzername_bereits_vergeben(self):
        User.objects.create_user(username="vorhandener", password="x", email="x@x.de")
        errors = _validate_registration_fields("vorhandener", "neu@test.de", "pass1234", "pass1234")
        self.assertTrue(any("vergeben" in e for e in errors))

    def test_fehlende_email(self):
        errors = _validate_registration_fields("new_user", "", "pass1234", "pass1234")
        self.assertTrue(any("E-Mail" in e for e in errors))

    def test_email_bereits_registriert(self):
        User.objects.create_user(username="anderer", password="x", email="doppelt@test.de")
        errors = _validate_registration_fields(
            "new_user", "doppelt@test.de", "pass1234", "pass1234"
        )
        self.assertTrue(any("E-Mail" in e for e in errors))

    def test_passwort_zu_kurz(self):
        errors = _validate_registration_fields("new_user", "neu@test.de", "kurz", "kurz")
        self.assertTrue(any("kurz" in e.lower() for e in errors))

    def test_passwort_nicht_identisch(self):
        errors = _validate_registration_fields("new_user", "neu@test.de", "pass1234", "anderes8")
        self.assertTrue(any("ungültig" in e or "identisch" in e for e in errors))

    def test_mehrere_fehler_gleichzeitig(self):
        errors = _validate_registration_fields("", "", "x", "y")
        self.assertGreater(len(errors), 1)


class TestHandleUpdateProfile(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="orig_user", email="orig@test.de", password="pass1234"
        )

    def test_keine_aenderung_kein_fehler(self):
        errors = _handle_update_profile(self.user, "orig_user", "orig@test.de")
        self.assertEqual(errors, [])

    def test_neuer_benutzername_gespeichert(self):
        errors = _handle_update_profile(self.user, "neuer_name", "orig@test.de")
        self.assertEqual(errors, [])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "neuer_name")

    def test_benutzername_zu_kurz(self):
        errors = _handle_update_profile(self.user, "ab", "orig@test.de")
        self.assertTrue(any("3 Zeichen" in e for e in errors))

    def test_benutzername_bereits_vergeben(self):
        User.objects.create_user(username="anderer_user", password="x", email="a@a.de")
        errors = _handle_update_profile(self.user, "anderer_user", "orig@test.de")
        self.assertTrue(any("vergeben" in e for e in errors))

    def test_neue_email_gespeichert(self):
        errors = _handle_update_profile(self.user, "orig_user", "neu@test.de")
        self.assertEqual(errors, [])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@test.de")

    def test_email_bereits_vergeben(self):
        User.objects.create_user(username="anderer", password="x", email="belegt@test.de")
        errors = _handle_update_profile(self.user, "orig_user", "belegt@test.de")
        self.assertTrue(any("E-Mail" in e for e in errors))


class TestHandleChangePassword(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pw_user", password="altes_pw_1234")

    def test_erfolgreich_geaendert(self):
        errors = _handle_change_password(
            self.user, "altes_pw_1234", "neues_pw_5678", "neues_pw_5678"
        )
        self.assertEqual(errors, [])

    def test_falsches_altes_passwort(self):
        errors = _handle_change_password(self.user, "falsch", "neues_pw_5678", "neues_pw_5678")
        self.assertTrue(any("falsch" in e.lower() for e in errors))

    def test_neues_passwort_zu_kurz(self):
        errors = _handle_change_password(self.user, "altes_pw_1234", "kurz", "kurz")
        self.assertTrue(any("8 Zeichen" in e for e in errors))

    def test_neue_passwoerter_nicht_gleich(self):
        errors = _handle_change_password(
            self.user, "altes_pw_1234", "neues_pw_5678", "anders_pw_99"
        )
        self.assertTrue(any("übereinstimm" in e.lower() or "stimmen" in e.lower() for e in errors))

    def test_leere_felder(self):
        errors = _handle_change_password(self.user, "", "", "")
        self.assertGreater(len(errors), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Views (Django TestClient)
# ──────────────────────────────────────────────────────────────────────────────
class TestApplyBetaView(TestCase):
    def test_redirect_zu_register(self):
        response = self.client.get(reverse("apply_beta"))
        self.assertRedirects(response, reverse("register"))


class TestRegisterView(TestCase):
    def test_get_zeigt_formular(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    def test_eingeloggter_user_wird_umgeleitet(self):
        user = User.objects.create_user(username="loggedin", password="pass1234")
        self.client.force_login(user)
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, reverse("dashboard"))

    @patch("core.views.auth.send_welcome_email")
    def test_post_erfolg_leitet_weiter(self, mock_email):
        mock_email.return_value = None
        response = self.client.post(
            reverse("register"),
            {
                "username": "brand_new_user",
                "email": "brand@new.de",
                "password1": "sicher_passwort_1",
                "password2": "sicher_passwort_1",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(User.objects.filter(username="brand_new_user").exists())

    def test_post_fehler_bleibt_auf_register(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "",  # Fehler
                "email": "x@x.de",
                "password1": "pass1234",
                "password2": "pass1234",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="x@x.de").exists())

    @patch("core.views.auth.send_welcome_email")
    def test_post_doppelter_username_fehler(self, mock_email):
        User.objects.create_user(username="existiert", password="x", email="alt@alt.de")
        response = self.client.post(
            reverse("register"),
            {
                "username": "existiert",
                "email": "neu@neu.de",
                "password1": "pass1234x",
                "password2": "pass1234x",
            },
        )
        self.assertEqual(response.status_code, 200)
        mock_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Feedback Views
# ──────────────────────────────────────────────────────────────────────────────
class TestFeedbackListView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fb_user", password="pass1234")
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("feedback_list"))
        self.assertEqual(response.status_code, 302)

    def test_get_200_leere_liste(self):
        response = self.client.get(reverse("feedback_list"))
        self.assertEqual(response.status_code, 200)

    def test_zeigt_nur_eigene_feedbacks(self):
        from core.models import Feedback

        other = User.objects.create_user(username="other_fb", password="pass1234")
        Feedback.objects.create(
            user=self.user, feedback_type="BUG", title="Mein Bug", description="Detail"
        )
        Feedback.objects.create(
            user=other, feedback_type="FEATURE", title="Anderer Bug", description="Detail"
        )
        response = self.client.get(reverse("feedback_list"))
        self.assertEqual(response.status_code, 200)
        feedbacks = response.context["feedbacks"]
        self.assertEqual(feedbacks.count(), 1)
        self.assertEqual(feedbacks.first().user, self.user)


class TestFeedbackCreateView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fbc_user", password="pass1234")
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("feedback_create"))
        self.assertEqual(response.status_code, 302)

    def test_get_200_zeigt_formular(self):
        response = self.client.get(reverse("feedback_create"))
        self.assertEqual(response.status_code, 200)

    def test_get_mit_type_parameter(self):
        response = self.client.get(reverse("feedback_create") + "?type=BUG")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["feedback_type"], "BUG")

    def test_post_erstellt_feedback(self):
        from core.models import Feedback

        response = self.client.post(
            reverse("feedback_create"),
            {
                "feedback_type": "FEATURE",
                "title": "Neues Feature",
                "description": "Das wäre toll",
            },
        )
        self.assertRedirects(response, reverse("feedback_list"), fetch_redirect_response=False)
        self.assertTrue(Feedback.objects.filter(user=self.user, title="Neues Feature").exists())

    def test_post_bug_feedback_erstellen(self):
        from core.models import Feedback

        self.client.post(
            reverse("feedback_create"),
            {
                "feedback_type": "BUG",
                "title": "Login kaputt",
                "description": "Kommt immer 500 Fehler",
            },
        )
        self.assertTrue(Feedback.objects.filter(user=self.user, feedback_type="BUG").exists())

    def test_post_ohne_title_kein_feedback(self):
        from core.models import Feedback

        count_vor = Feedback.objects.filter(user=self.user).count()
        response = self.client.post(
            reverse("feedback_create"),
            {"feedback_type": "BUG", "title": "", "description": "Detail"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(Feedback.objects.filter(user=self.user).count(), count_vor)

    def test_post_ohne_description_kein_feedback(self):
        from core.models import Feedback

        count_vor = Feedback.objects.filter(user=self.user).count()
        response = self.client.post(
            reverse("feedback_create"),
            {"feedback_type": "FEATURE", "title": "Irgendwas", "description": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feedback.objects.filter(user=self.user).count(), count_vor)


class TestFeedbackDetailView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fbd_user", password="pass1234")
        self.client.force_login(self.user)
        from core.models import Feedback

        self.feedback = Feedback.objects.create(
            user=self.user,
            feedback_type="FEATURE",
            title="Mein Feature",
            description="Beschreibung",
        )

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("feedback_detail", args=[self.feedback.id]))
        self.assertEqual(response.status_code, 302)

    def test_get_200_zeigt_detail(self):
        response = self.client.get(reverse("feedback_detail", args=[self.feedback.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["feedback"], self.feedback)

    def test_fremdes_feedback_404(self):
        other = User.objects.create_user(username="other_fbd", password="pass1234")
        from core.models import Feedback

        fremdes = Feedback.objects.create(
            user=other, feedback_type="BUG", title="Fremd", description="x"
        )
        response = self.client.get(reverse("feedback_detail", args=[fremdes.id]))
        self.assertEqual(response.status_code, 404)


# ──────────────────────────────────────────────────────────────────────────────
# Profile View
# ──────────────────────────────────────────────────────────────────────────────
class TestProfileView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile_user", email="profile@test.de", password="altes_pw_9876"
        )
        self.client.force_login(self.user)
        from core.models import UserProfile

        UserProfile.objects.get_or_create(user=self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_200(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)

    def test_post_update_profile_aendert_username(self):
        self.client.post(
            reverse("profile"),
            {
                "action": "update_profile",
                "username": "neuer_name_123",
                "email": "profile@test.de",
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "neuer_name_123")

    def test_post_update_profile_fehler_zeigt_meldung(self):
        User.objects.create_user(username="belegt_name", password="x", email="b@b.de")
        response = self.client.post(
            reverse("profile"),
            {
                "action": "update_profile",
                "username": "belegt_name",
                "email": "profile@test.de",
            },
        )
        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "profile_user")  # unverändert

    def test_post_change_password_erfolgreich(self):
        response = self.client.post(
            reverse("profile"),
            {
                "action": "change_password",
                "current_password": "altes_pw_9876",
                "new_password": "neues_pw_sicher_1",
                "confirm_password": "neues_pw_sicher_1",
            },
        )
        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("neues_pw_sicher_1"))

    def test_post_change_password_falsches_altes_pw(self):
        response = self.client.post(
            reverse("profile"),
            {
                "action": "change_password",
                "current_password": "falsch",
                "new_password": "neues_pw_sicher_1",
                "confirm_password": "neues_pw_sicher_1",
            },
        )
        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("altes_pw_9876"))  # unverändert

    def test_post_update_body_data_groesse_gesetzt(self):
        self.client.post(
            reverse("profile"),
            {"action": "update_body_data", "groesse_cm": "180"},
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.groesse_cm, 180)

    def test_post_update_body_data_zu_gross(self):
        self.client.post(
            reverse("profile"),
            {"action": "update_body_data", "groesse_cm": "300"},
        )
        self.user.profile.refresh_from_db()
        self.assertNotEqual(self.user.profile.groesse_cm, 300)

    def test_post_update_body_data_kein_wert(self):
        response = self.client.post(
            reverse("profile"),
            {"action": "update_body_data", "groesse_cm": ""},
        )
        # Redirect zurück zu profile – kein Crash
        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)

    def test_post_update_body_data_ungueltig(self):
        response = self.client.post(
            reverse("profile"),
            {"action": "update_body_data", "groesse_cm": "abc"},
        )
        self.assertRedirects(response, reverse("profile"), fetch_redirect_response=False)
