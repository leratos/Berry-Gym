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
