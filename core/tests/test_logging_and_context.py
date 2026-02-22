"""
Tests für core/utils/logging_helper.py und core/context_processors.py
"""

import logging

from django.test import RequestFactory, TestCase

from core.context_processors import disclaimers, global_context
from core.models_disclaimer import ScientificDisclaimer
from core.utils.logging_helper import (
    get_logger,
    log_error_with_context,
    log_performance,
    log_security_event,
    log_user_action,
)


# ──────────────────────────────────────────────────────────────────────────────
# logging_helper.py
# ──────────────────────────────────────────────────────────────────────────────
class TestGetLogger(TestCase):
    def test_gibt_logger_instanz_zurueck(self):
        logger = get_logger(__name__)
        self.assertIsInstance(logger, logging.Logger)

    def test_name_wird_uebernommen(self):
        logger = get_logger("mein.modul")
        self.assertEqual(logger.name, "mein.modul")


class TestLogPerformanceDecorator(TestCase):
    def test_gibt_rueckgabewert_weiter(self):
        @log_performance
        def addiere(a, b):
            return a + b

        result = addiere(2, 3)
        self.assertEqual(result, 5)

    def test_exception_wird_weitergeworfen(self):
        @log_performance
        def wirft():
            raise ValueError("kaputt")

        with self.assertRaises(ValueError):
            wirft()

    def test_funktionsname_bleibt_erhalten(self):
        @log_performance
        def meine_funktion():
            return 42

        self.assertEqual(meine_funktion.__name__, "meine_funktion")

    def test_ohne_argumente(self):
        @log_performance
        def keine_args():
            return "ok"

        self.assertEqual(keine_args(), "ok")


class TestLogUserAction(TestCase):
    def test_loggt_ohne_absturz(self):
        logger = get_logger("test.useraction")
        # Darf nicht werfen
        log_user_action(logger, "Training erstellt", user_id=42, training_id=99)

    def test_loggt_ohne_user_id(self):
        logger = get_logger("test.useraction")
        log_user_action(logger, "Anonym", user_id=None)

    def test_loggt_ohne_context(self):
        logger = get_logger("test.useraction")
        log_user_action(logger, "Minimale Aktion")


class TestLogErrorWithContext(TestCase):
    def test_loggt_mit_exception(self):
        logger = get_logger("test.error")
        try:
            raise RuntimeError("Testfehler")
        except RuntimeError as e:
            # Darf nicht werfen
            log_error_with_context(logger, "Fehler aufgetreten", exception=e, user_id=1)

    def test_loggt_ohne_exception(self):
        logger = get_logger("test.error")
        log_error_with_context(logger, "Warnung ohne Exception")

    def test_loggt_mit_zusatzcontext(self):
        logger = get_logger("test.error")
        log_error_with_context(logger, "Fehler", operation="test_op", user_id=5)


class TestLogSecurityEvent(TestCase):
    def test_loggt_warning(self):
        # Darf nicht werfen
        log_security_event("failed_login", severity="WARNING", username="attacker")

    def test_loggt_critical(self):
        log_security_event("permission_violation", severity="CRITICAL", user_id=99)

    def test_loggt_error(self):
        log_security_event("suspicious_access", severity="ERROR")


# ──────────────────────────────────────────────────────────────────────────────
# context_processors.py
# ──────────────────────────────────────────────────────────────────────────────
class TestGlobalContext(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_current_year_vorhanden(self):
        request = self.factory.get("/")
        result = global_context(request)
        self.assertIn("current_year", result)

    def test_current_year_ist_int(self):
        request = self.factory.get("/")
        result = global_context(request)
        self.assertIsInstance(result["current_year"], int)

    def test_current_year_plausibel(self):
        request = self.factory.get("/")
        result = global_context(request)
        self.assertGreaterEqual(result["current_year"], 2025)


class TestDisclaimersContextProcessor(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_keine_disclaimers_gibt_leere_liste(self):
        request = self.factory.get("/stats/")
        result = disclaimers(request)
        self.assertEqual(result["active_disclaimers"], [])

    def test_inaktiver_disclaimer_nicht_enthalten(self):
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Inaktiv",
            message="Test",
            is_active=False,
            show_on_pages=[],
        )
        request = self.factory.get("/stats/")
        result = disclaimers(request)
        self.assertEqual(len(result["active_disclaimers"]), 0)

    def test_globaler_disclaimer_auf_jeder_seite(self):
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Global",
            message="Immer anzeigen",
            is_active=True,
            show_on_pages=[],  # leer = global
        )
        for path in ["/", "/stats/", "/training/"]:
            request = self.factory.get(path)
            result = disclaimers(request)
            self.assertEqual(len(result["active_disclaimers"]), 1, f"Fehlend auf {path}")

    def test_seitenspezifischer_disclaimer(self):
        ScientificDisclaimer.objects.create(
            category="TRAINING_VOLUME",
            title="Nur Stats",
            message="Statistik-Hinweis",
            is_active=True,
            show_on_pages=["stats/"],
        )
        # Soll auf /stats/ erscheinen
        request = self.factory.get("/stats/uebersicht/")
        result = disclaimers(request)
        self.assertEqual(len(result["active_disclaimers"]), 1)

        # Soll NICHT auf /training/ erscheinen
        request = self.factory.get("/training/")
        result = disclaimers(request)
        self.assertEqual(len(result["active_disclaimers"]), 0)

    def test_mehrere_aktive_disclaimers(self):
        ScientificDisclaimer.objects.create(
            category="GENERAL", title="D1", message="M1", is_active=True, show_on_pages=[]
        )
        ScientificDisclaimer.objects.create(
            category="FATIGUE_INDEX", title="D2", message="M2", is_active=True, show_on_pages=[]
        )
        request = self.factory.get("/")
        result = disclaimers(request)
        self.assertEqual(len(result["active_disclaimers"]), 2)
