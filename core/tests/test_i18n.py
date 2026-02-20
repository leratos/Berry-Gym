"""
Tests für Phase 7.5 – i18n Framework

Testet:
- Language-Switcher DE→EN funktioniert (set_language endpoint)
- Deutsch bleibt Standard (kein /de/ Präfix)
- Englisch bekommt /en/ Präfix
- Übersetzungen werden angewendet (Login-Seite)
- {% trans %} Tags im Header rendern korrekt
"""

import pytest  # noqa: F401
from django.test import Client, TestCase, override_settings  # noqa: F401
from django.urls import reverse  # noqa: F401
from django.contrib.auth import get_user_model

User = get_user_model()


class LanguageSwitcherTest(TestCase):
    """Testet den Language-Switcher und URL-Routing."""

    def setUp(self):
        self.client = Client()

    def test_set_language_endpoint_exists(self):
        """set_language endpoint muss erreichbar sein."""
        response = self.client.post(
            "/i18n/setlang/",
            {"language": "en", "next": "/"},
        )
        # 302 Redirect erwartet
        self.assertIn(response.status_code, [302, 200])

    def test_german_is_default_no_prefix(self):
        """Deutsche URLs haben kein /de/ Präfix."""
        response = self.client.get("/accounts/login/")
        self.assertNotEqual(response.status_code, 404)

    def test_english_url_prefix(self):
        """Englische URLs haben /en/ Präfix."""
        response = self.client.get(
            "/en/accounts/login/",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertNotEqual(response.status_code, 404)

    def test_switch_to_english_via_post(self):
        """Sprache kann via POST auf Englisch gestellt werden."""
        response = self.client.post(
            "/i18n/setlang/",
            {"language": "en", "next": "/accounts/login/"},
        )
        self.assertEqual(response.status_code, 302)

    def test_switch_to_german_via_post(self):
        """Sprache kann via POST auf Deutsch gestellt werden."""
        response = self.client.post(
            "/i18n/setlang/",
            {"language": "de", "next": "/accounts/login/"},
        )
        self.assertEqual(response.status_code, 302)


class LoginPageTranslationTest(TestCase):
    """Testet ob Übersetzungen auf der Login-Seite aktiv sind."""

    def setUp(self):
        self.client = Client()

    def test_login_page_german_default(self):
        """Login-Seite auf Deutsch zeigt deutschen Text."""
        response = self.client.get(
            "/accounts/login/",
            HTTP_ACCEPT_LANGUAGE="de",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Deutscher Text muss vorhanden sein
        self.assertIn("Anmelden", content)

    def test_login_page_english_translation(self):
        """Login-Seite auf Englisch zeigt englischen Text."""
        # Session auf Englisch setzen
        session = self.client.session
        session["_language"] = "en"
        session.save()

        response = self.client.get(
            "/en/accounts/login/",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Englischer Text muss vorhanden sein
        self.assertIn("Sign In", content)

    def test_login_page_has_language_info(self):
        """Login-Seite hat i18n geladen (kein Template-Error)."""
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        # Kein Template-Fehler = i18n tags korrekt geladen
        self.assertNotIn("TemplateSyntaxError", response.content.decode("utf-8"))


class I18nSettingsTest(TestCase):
    """Testet die i18n Django-Einstellungen."""

    def test_use_i18n_enabled(self):
        """USE_I18N muss True sein."""
        from django.conf import settings

        self.assertTrue(settings.USE_I18N)

    def test_languages_configured(self):
        """LANGUAGES muss de und en enthalten."""
        from django.conf import settings

        language_codes = [code for code, name in settings.LANGUAGES]
        self.assertIn("de", language_codes)
        self.assertIn("en", language_codes)

    def test_default_language_is_german(self):
        """Standardsprache muss Deutsch sein."""
        from django.conf import settings

        self.assertEqual(settings.LANGUAGE_CODE, "de")

    def test_locale_paths_configured(self):
        """LOCALE_PATHS muss konfiguriert sein."""
        from django.conf import settings

        self.assertTrue(len(settings.LOCALE_PATHS) > 0)

    def test_mo_file_exists(self):
        """Kompilierte .mo Datei für Englisch muss existieren."""
        import os
        from django.conf import settings

        mo_path = settings.LOCALE_PATHS[0] / "en" / "LC_MESSAGES" / "django.mo"
        self.assertTrue(
            os.path.exists(mo_path), f".mo Datei fehlt: {mo_path} – 'compilemessages' ausführen!"
        )
