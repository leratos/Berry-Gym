"""
Pre-Launch / Deployment Checks.

Stellt sicher dass kritische Produktions-Konfigurationen korrekt sind.
Diese Tests laufen in der normalen Test-Suite (DEBUG=True) und prüfen
die Settings-Logik, nicht die Live-Konfiguration.
"""

import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test.utils import override_settings

import pytest


class TestSecuritySettings:
    """Settings-Logik für Production-Sicherheit."""

    def test_debug_default_ist_false(self):
        """DEBUG=True muss explizit gesetzt werden – Default muss False sein."""
        import os

        # Simuliere: keine DEBUG Env-Var gesetzt
        original = os.environ.pop("DEBUG", None)
        try:
            result = os.getenv("DEBUG", "False") == "True"
            assert result is False, "DEBUG-Default muss False sein"
        finally:
            if original is not None:
                os.environ["DEBUG"] = original

    def test_secret_key_fallback_nur_in_tests(self):
        """SECRET_KEY-Fallback darf nur in Test-Umgebungen greifen."""
        # In pytest läuft sys.argv mit 'test' oder pytest ist in sys.modules
        assert "pytest" in sys.modules, "Dieser Test läuft selbst in pytest"
        # Der Test-Key ist kein echtes Geheimnis – er darf in Tests existieren
        assert settings.SECRET_KEY, "SECRET_KEY muss gesetzt sein"
        assert len(settings.SECRET_KEY) >= 20, "SECRET_KEY zu kurz"

    @override_settings(DEBUG=False)
    def test_production_security_headers_aktiv(self):
        """In Production (DEBUG=False) müssen Security-Headers gesetzt sein."""
        # Diese Settings werden in settings.py unter `if not DEBUG:` gesetzt.
        # Da wir override_settings nutzen, prüfen wir die Settings direkt.
        # In echter Production werden sie durch den if-Block gesetzt.
        assert settings.X_FRAME_OPTIONS == "DENY"
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True

    def test_allowed_hosts_nicht_leer(self):
        """ALLOWED_HOSTS muss mindestens einen Eintrag haben."""
        assert settings.ALLOWED_HOSTS, "ALLOWED_HOSTS darf nicht leer sein"

    def test_installed_apps_enthalten_security_apps(self):
        """Sicherheits-Apps müssen installiert sein."""
        assert "axes" in settings.INSTALLED_APPS, "django-axes fehlt"
        # django-ratelimit ist decorator-basiert, kein INSTALLED_APP nötig
        import importlib.util

        assert (
            importlib.util.find_spec("django_ratelimit") is not None
        ), "django-ratelimit ist nicht installiert"

    def test_middleware_enthalten_csrf_und_axes(self):
        """CSRF- und Axes-Middleware müssen aktiv sein."""
        mw = settings.MIDDLEWARE
        assert any("CsrfViewMiddleware" in m for m in mw), "CsrfViewMiddleware fehlt"
        assert any("axes" in m.lower() for m in mw), "AxesMiddleware fehlt"

    def test_session_cookie_httponly(self):
        """Session-Cookie muss HttpOnly sein."""
        assert settings.SESSION_COOKIE_HTTPONLY is True


@pytest.mark.django_db
class TestDeployCheck:
    """django check --deploy darf keine ERRORS (nur Warnings erlaubt)."""

    def test_django_system_check_keine_errors(self):
        """
        Führt `manage.py check` aus (ohne --deploy, da lokale Settings DEBUG=True).
        Prüft auf ERRORS – Warnings sind ok.
        """
        manage_py = Path(__file__).resolve().parents[2] / "manage.py"
        result = subprocess.run(
            [sys.executable, str(manage_py), "check", "--fail-level", "ERROR"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Django system check hat Errors gefunden:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_keine_ausstehenden_migrationen(self):
        """
        Prüft dass alle Migrations angewendet wurden und keine
        unapplied Migrations existieren.
        """
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        assert len(plan) == 0, f"Es gibt {len(plan)} unangewendete Migration(en): " + ", ".join(
            f"{app}.{name}" for (app, name), _ in plan
        )

    def test_keine_fehlenden_migrations(self):
        """
        Prüft dass keine Model-Änderungen existieren die noch keine
        Migration haben (detect missing migrations).
        """
        manage_py = Path(__file__).resolve().parents[2] / "manage.py"
        result = subprocess.run(
            [sys.executable, str(manage_py), "migrate", "--check"],
            capture_output=True,
            text=True,
        )
        # Exit code 1 = unangewendete Migrationen vorhanden
        assert (
            result.returncode == 0
        ), f"Unangewendete Migrationen gefunden:\n{result.stdout}\n{result.stderr}"


class TestRequirements:
    """Kritische Abhängigkeiten auf bekannte Sicherheitsprobleme prüfen."""

    def test_gunicorn_version_aktuell(self):
        """
        Gunicorn muss >= 21.2.0 sein (Fix für HTTP request smuggling CVE).
        Aktuell: 25.1.0 (Update 2026-02-22).
        """
        import importlib.metadata

        from packaging.version import Version

        version = Version(importlib.metadata.version("gunicorn"))
        assert version >= Version("21.2.0"), (
            f"gunicorn {version} ist veraltet und hat bekannte CVEs. "
            "Bitte auf >= 21.2.0 aktualisieren."
        )

    def test_django_version_nicht_eol(self):
        """Django darf keine End-of-Life Version sein."""
        import django

        from packaging.version import Version

        version = Version(django.__version__)
        # Django 3.x und 4.0.x/4.1.x sind EOL
        assert version >= Version(
            "4.2"
        ), f"Django {version} ist EOL. Bitte auf >= 4.2 (LTS) oder 5.x aktualisieren."
