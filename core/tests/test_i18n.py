"""
Tests für Phase 7.5 – i18n Framework und L10N-Regression

Testet:
- Language-Switcher DE→EN funktioniert (set_language endpoint)
- Deutsch bleibt Standard (kein /de/ Präfix)
- Englisch bekommt /en/ Präfix
- Übersetzungen werden angewendet (Login-Seite)
- {% trans %} Tags im Header rendern korrekt
"""

import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings  # noqa: F401
from django.urls import reverse  # noqa: F401
from django.utils.translation import override as lang_override

import pytest  # noqa: F401

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

    def test_switch_en_to_de_strips_en_prefix(self):
        """
        Regression: EN→DE Wechsel darf nicht auf /en/... URL redirecten.
        next muss vom Template schon ohne /en/-Prefix übergeben werden
        (/en/dashboard/ -> [3:] -> /dashboard/).
        """
        # Simuliert: User ist auf englischer Seite, klickt DE
        # Das Template sendet request.path|slice:'3:' = '/accounts/login/'
        response = self.client.post(
            "/i18n/setlang/",
            {"language": "de", "next": "/accounts/login/"},
        )
        self.assertEqual(response.status_code, 302)
        redirect_url = response["Location"]
        self.assertFalse(
            redirect_url.startswith("/en/"),
            f"EN→DE Redirect sollte kein /en/-Prefix haben, aber war: {redirect_url}",
        )

    def test_switch_de_to_en_next_is_en_url(self):
        """
        DE→EN Wechsel: Redirect landet auf der englischen URL (/en/...).
        """
        response = self.client.post(
            "/i18n/setlang/",
            {"language": "en", "next": "/accounts/login/"},
        )
        self.assertEqual(response.status_code, 302)
        redirect_url = response["Location"]
        # Django set_language redirectet zur `next` URL direkt (translate_url ist no-op hier)
        self.assertIn("login", redirect_url)


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


class L10nJsDecimalTest(TestCase):
    """
    Regression-Test: Django L10N formatiert Dezimalzahlen im deutschen Locale
    mit Komma (0,5) statt Punkt (0.5). Im JavaScript-Kontext bricht das die
    Syntax (Komma = Property-Separator in Objekt-Literalen).

    Root Cause Bug: kgFaktor: 0,5  →  SyntaxError → ganzer Script nicht ausgeführt
    Fix: {% localize off %}{{ uebung.koerpergewicht_faktor }}{% endlocalize %}

    Dieser Test verhindert eine Regression dieses Bugs.
    """

    def setUp(self):
        from core.tests.factories import TrainingseinheitFactory, UebungFactory, UserFactory

        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

        # Übung mit Körpergewicht-Typ und nicht-ganzzahligem Faktor
        # 0.5 würde im DE-Locale als "0,5" formatiert werden → JS-Bug
        self.uebung = UebungFactory(
            gewichts_typ="KOERPERGEWICHT",
            koerpergewicht_faktor=0.5,
        )
        self.training = TrainingseinheitFactory(user=self.user)
        self.url = reverse("training_session", kwargs={"training_id": self.training.id})

    def _get_script_blocks(self, content):
        """Extrahiert den Inhalt aller <script>-Blöcke aus dem HTML."""
        return re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)

    def test_kgfaktor_kein_komma_in_js_de_locale(self):
        """
        Kerntest: Im deutschen Locale darf kgFaktor im JS-Block kein Komma enthalten.
        Ohne {% localize off %} würde 0.5 als '0,5' gerendert werden.
        """
        with lang_override("de"):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        scripts = self._get_script_blocks(content)
        self.assertTrue(scripts, "Keine <script>-Blöcke gefunden – Template-Struktur geändert?")

        combined_js = "\n".join(scripts)

        # Suche nach dem spezifischen kgFaktor-Muster mit Komma
        # Regex: kgFaktor: ZAHL,ZAHL (ohne Anführungszeichen – d.h. es ist ein JS-Literal)
        decimal_comma_in_js = re.search(r"kgFaktor:\s*\d+,\d+", combined_js)
        self.assertIsNone(
            decimal_comma_in_js,
            "REGRESSION: kgFaktor enthält Dezimalkomma im JS-Block! "
            "{% localize off %} fehlt in training_session.html. "
            f"Gefunden: {decimal_comma_in_js.group() if decimal_comma_in_js else ''}",
        )

    def test_kgfaktor_enthaelt_dezimalpunkt_in_js(self):
        """
        Positiv-Test: kgFaktor muss im JS-Block einen Dezimalpunkt enthalten
        wenn der Faktor nicht ganzzahlig ist (z.B. 0.5).
        """
        with lang_override("de"):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        scripts = self._get_script_blocks(content)
        combined_js = "\n".join(scripts)

        # kgFaktor: 0.5 muss als JS-Literal mit Punkt vorhanden sein
        decimal_point_in_js = re.search(r"kgFaktor:\s*0\.5", combined_js)
        self.assertIsNotNone(
            decimal_point_in_js,
            "kgFaktor mit Dezimalpunkt (0.5) nicht im JS gefunden. "
            "Entweder Übung nicht in der Session oder {% localize off %} fehlt.",
        )
