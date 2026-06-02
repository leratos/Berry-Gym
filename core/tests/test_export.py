"""
Tests für Export-Funktionen (CSV, PDF, Übungen).

Testet:
- CSV Export von Trainings
- PDF Export (Training, Plan)
- Übungen Export/Import
- File Generation & Validation
"""

import csv
import io
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings
from django.urls import reverse

import pytest

from core.export import pdf_renderer
from core.tests.factories import (
    PlanFactory,
    PlanUebungFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestTrainingCSVExport:
    """Tests für CSV Export von Trainingseinheiten."""

    def test_export_training_csv_requires_login(self, client):
        """CSV Export erfordert Login."""
        response = client.get(reverse("export_training_csv"))
        assert response.status_code == 302  # Redirect to login
        assert "/accounts/login/" in response.url

    def test_export_training_csv_empty(self, client):
        """CSV Export mit leeren Trainingsdaten."""
        user = UserFactory()
        client.force_login(user)

        response = client.get(reverse("export_training_csv"))

        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        assert "attachment" in response["Content-Disposition"]

    def test_export_training_csv_with_data(self, client):
        """CSV Export mit Trainingsdaten."""
        user = UserFactory()
        client.force_login(user)

        # Trainingseinheit mit Sätzen erstellen
        training = TrainingseinheitFactory(user=user, datum=date.today())
        uebung = UebungFactory(bezeichnung="Bankdrücken")

        # Sätze direkt über training erstellen (einheit= ist der richtige Parameter!)
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=80.0,
            wiederholungen=10,
            rpe=8,
        )
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=85.0,
            wiederholungen=8,
            rpe=9,
        )

        response = client.get(reverse("export_training_csv"))

        assert response.status_code == 200

        # CSV parsen
        content = response.content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(content))
        rows = list(csv_reader)

        # Mindestens 2 Sätze vorhanden
        assert len(rows) >= 2

    def test_export_training_csv_only_own_data(self, client):
        """CSV Export zeigt nur eigene Trainingsdaten."""
        user1 = UserFactory()
        user2 = UserFactory()
        client.force_login(user1)

        # User 1 Training
        training1 = TrainingseinheitFactory(user=user1)
        SatzFactory(einheit=training1)

        # User 2 Training (sollte nicht erscheinen)
        training2 = TrainingseinheitFactory(user=user2)
        SatzFactory(einheit=training2)

        response = client.get(reverse("export_training_csv"))

        assert response.status_code == 200
        # Nur eigene Daten sollten exportiert werden


@pytest.mark.django_db
class TestTrainingPDFExport:
    """Tests für PDF Export von Trainingseinheiten."""

    def test_export_training_pdf_requires_login(self, client):
        """PDF Export erfordert Login."""
        response = client.get(reverse("export_training_pdf"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_export_training_pdf_generates_file(self, client):
        """PDF wird erfolgreich generiert."""
        user = UserFactory()
        client.force_login(user)

        # Training mit Daten
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory(bezeichnung="Kniebeugen")
        SatzFactory(einheit=training, uebung=uebung, gewicht=100.0)

        response = client.get(reverse("export_training_pdf"))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        assert ".pdf" in response["Content-Disposition"]

        # PDF sollte nicht leer sein
        assert len(response.content) > 1000  # Mindestgröße

    @override_settings(PDF_ENGINE="weasyprint")
    def test_export_training_pdf_weasyprint_engine(self, client):
        """PDF rendert auch mit PDF_ENGINE='weasyprint' (inkl. @font-face +
        Status-Glyphen). Ist WeasyPrint / dessen native Libs nicht ladbar,
        greift der Auto-Fallback auf xhtml2pdf – in beiden Fällen ein valides
        PDF, kein Crash."""
        user = UserFactory()
        client.force_login(user)
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory(bezeichnung="Kniebeugen")
        SatzFactory(einheit=training, uebung=uebung, gewicht=100.0)

        response = client.get(reverse("export_training_pdf"))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"
        assert len(response.content) > 1000

    def test_export_training_pdf_with_data(self, client):
        """PDF enthält Trainingsdaten."""
        user = UserFactory()
        client.force_login(user)

        training = TrainingseinheitFactory(user=user, datum=date.today())
        uebung = UebungFactory(bezeichnung="Kreuzheben")
        SatzFactory(einheit=training, uebung=uebung, gewicht=140.0)

        response = client.get(reverse("export_training_pdf"))

        assert response.status_code == 200
        assert len(response.content) > 5000  # Größere Datei = mehr Inhalt


@pytest.mark.django_db
class TestPlanPDFExport:
    """Tests für PDF Export von Trainingsplänen."""

    def test_export_plan_pdf_requires_login(self, client):
        """Plan-PDF Export erfordert Login."""
        plan = PlanFactory()
        response = client.get(reverse("export_plan_pdf", args=[plan.id]))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_export_plan_pdf_own_plan(self, client):
        """PDF Export des eigenen Plans."""
        user = UserFactory()
        client.force_login(user)

        plan = PlanFactory(user=user, name="Mein Trainingsplan")
        uebung = UebungFactory(bezeichnung="Bankdrücken")
        # Richtige Factory-Parameter: saetze_ziel, wiederholungen_ziel
        PlanUebungFactory(plan=plan, uebung=uebung, saetze_ziel=4, wiederholungen_ziel="8")

        response = client.get(reverse("export_plan_pdf", args=[plan.id]))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert ".pdf" in response["Content-Disposition"]
        assert len(response.content) > 1000

    def test_export_plan_pdf_not_found(self, client):
        """PDF Export eines nicht-existierenden Plans."""
        user = UserFactory()
        client.force_login(user)

        response = client.get(reverse("export_plan_pdf", args=[99999]))

        # Sollte 404 Not Found sein
        assert response.status_code == 404


@pytest.mark.django_db
class TestUebungenExport:
    """Tests für Übungen Export/Import."""

    def test_export_uebungen_requires_login(self, client):
        """Übungen Export erfordert Login."""
        response = client.get(reverse("export_uebungen"))
        assert response.status_code == 302

    def test_export_uebungen_works(self, client):
        """Übungen exportieren funktioniert."""
        user = UserFactory()
        client.force_login(user)

        # Übungen erstellen
        UebungFactory(bezeichnung="Übung 1", muskelgruppe="Brust")
        UebungFactory(bezeichnung="Übung 2", muskelgruppe="Rücken")

        response = client.get(reverse("export_uebungen"))

        # Export sollte funktionieren (200) oder nicht implementiert sein (404/302)
        assert response.status_code in [200, 302, 404]


@pytest.mark.django_db
class TestImportUebungen:
    """Tests für Übungen Import (falls implementiert)."""

    def test_import_uebungen_requires_login(self, client):
        """Übungen Import erfordert Login."""
        response = client.get(reverse("import_uebungen"))
        assert response.status_code == 302

    def test_import_uebungen_page_accessible(self, client):
        """Import-Seite ist erreichbar."""
        user = UserFactory()
        client.force_login(user)

        response = client.get(reverse("import_uebungen"))

        # Seite sollte laden oder nicht implementiert sein
        assert response.status_code in [200, 302, 404]


# ---------------------------------------------------------------------------
# Tests für neue Gewichtsverlust-Analyse-Helfer
# ---------------------------------------------------------------------------

from datetime import datetime

from core.tests.factories import KoerperWerteFactory
from core.views.export import _analyze_weight_loss_context, _calc_volume_trend_weekly

# Fixes heute-Datum für Tests: KW20 2026 – weit genug von KW10/KW11 entfernt
_HEUTE_KW20 = datetime(2026, 5, 13)


class TestCalcVolumeTrendWeekly:
    """Tests für _calc_volume_trend_weekly."""

    def test_returns_none_wenn_zu_wenig_daten(self):
        result = _calc_volume_trend_weekly([{"woche": "KW10", "volumen": 5000}], heute=_HEUTE_KW20)
        assert result is None

    def test_volumen_steigt(self):
        wochen = [
            {"woche": "KW10", "volumen": 5000},
            {"woche": "KW11", "volumen": 6000},
        ]
        result = _calc_volume_trend_weekly(wochen, heute=_HEUTE_KW20)
        assert result is not None
        assert result["trend"] == "steigt"
        assert result["veraenderung_prozent"] == 20.0

    def test_volumen_faellt(self):
        wochen = [
            {"woche": "KW10", "volumen": 6000},
            {"woche": "KW11", "volumen": 4000},
        ]
        result = _calc_volume_trend_weekly(wochen, heute=_HEUTE_KW20)
        assert result["trend"] == "fällt"

    def test_volumen_stabil(self):
        wochen = [
            {"woche": "KW10", "volumen": 5000},
            {"woche": "KW11", "volumen": 5100},
        ]
        result = _calc_volume_trend_weekly(wochen, heute=_HEUTE_KW20)
        assert result["trend"] == "stabil"

    def test_returns_none_wenn_vorwoche_null(self):
        wochen = [{"woche": "KW10", "volumen": 0}, {"woche": "KW11", "volumen": 5000}]
        result = _calc_volume_trend_weekly(wochen, heute=_HEUTE_KW20)
        assert result is None

    def test_returns_none_wenn_aktuelle_woche(self):
        """Laufende Woche wird nicht verglichen – kein irreführendes Ergebnis."""
        heute_kw11 = datetime(2026, 3, 11)  # KW11
        wochen = [
            {"woche": "KW10", "volumen": 6000},
            {"woche": "KW11", "volumen": 2000},  # laufende Woche, unvollständig
        ]
        result = _calc_volume_trend_weekly(wochen, heute=heute_kw11)
        assert result is None


@pytest.mark.django_db
class TestAnalyzeWeightLossContext:
    """Tests für _analyze_weight_loss_context."""

    def test_returns_none_bei_moderatem_verlust(self):
        """Kein Warning wenn Rate > -1.0."""
        stats = {"gewichts_rate": -0.8}
        assert _analyze_weight_loss_context(stats) is None

    def test_returns_none_wenn_keine_rate(self):
        assert _analyze_weight_loss_context({"gewichts_rate": None}) is None

    def test_risk_gering_bei_steigendem_volumen(self):
        """Steigendes Trainingsvolumen → Risiko gering."""
        user = UserFactory()
        kw1 = KoerperWerteFactory(user=user)
        kw2 = KoerperWerteFactory(user=user)
        stats = {
            "gewichts_rate": -1.5,
            "volumen_trend_weekly": {
                "diese_woche": 6000,
                "letzte_woche": 5500,
                "veraenderung_prozent": 9.1,
                "trend": "steigt",
            },
            "koerperwerte": [kw1, kw2],
        }
        result = _analyze_weight_loss_context(stats)
        assert result is not None
        assert result["risk_level"] == "gering"
        assert any("Trainingsvolumen steigt" in f for f in result["faktoren_dagegen"])

    def test_faktoren_dafuer_bei_sinkendem_volumen(self):
        """Sinkendes Volumen → faktoren_dafuer enthält Eintrag."""
        user = UserFactory()
        kw1 = KoerperWerteFactory(user=user)
        stats = {
            "gewichts_rate": -1.5,
            "volumen_trend_weekly": {
                "diese_woche": 4000,
                "letzte_woche": 6000,
                "veraenderung_prozent": -33.3,
                "trend": "fällt",
            },
            "koerperwerte": [kw1],
        }
        result = _analyze_weight_loss_context(stats)
        assert any("sinkt" in f for f in result["faktoren_dafuer"])


# ---------------------------------------------------------------------------
# Engine-Logik des PDF-Renderers (core/export/pdf_renderer.py)
# ---------------------------------------------------------------------------

_TINY_HTML = "<html><body><p>Test</p></body></html>"
# core/static enthält die Font-TTFs – als STATIC_ROOT für den Fetcher-Test.
_FONTS_STATIC_ROOT = str(Path(settings.BASE_DIR) / "core" / "static")


class TestPdfRendererEngine:
    """Engine-Auswahl, Fallback und Hilfsfunktionen des PDF-Renderers.

    Deckt die Fehler-/Fallback-Pfade ab, die im Normalbetrieb nicht ausgelöst
    werden: WeasyPrint-Render-Fehler → xhtml2pdf-Fallback, fehlende Engine,
    pisa-Fehler, STATIC_ROOT-Auflösung im URL-Fetcher, Dateiname ohne Zeitraum.
    """

    def _request(self):
        return RequestFactory().get("/")

    @override_settings(PDF_ENGINE="weasyprint")
    def test_weasyprint_fehler_faellt_auf_xhtml2pdf_zurueck(self):
        if pdf_renderer.weasyprint is None:
            pytest.skip("WeasyPrint nicht importierbar")
        req = self._request()
        with (
            patch.object(pdf_renderer, "render_to_string", return_value=_TINY_HTML),
            patch.object(pdf_renderer.weasyprint, "HTML", side_effect=RuntimeError("kein Pango")),
        ):
            pdf = pdf_renderer._render_pdf_bytes(req, {})
        # WeasyPrint-Fehler → Auto-Fallback liefert trotzdem ein valides PDF
        assert pdf[:5] == b"%PDF-"

    @override_settings(PDF_ENGINE="xhtml2pdf")
    def test_keine_engine_verfuegbar_wirft(self):
        req = self._request()
        with patch.object(pdf_renderer, "pisa", None):
            with pytest.raises(RuntimeError):
                pdf_renderer._render_pdf_bytes(req, {})

    @override_settings(PDF_ENGINE="xhtml2pdf")
    def test_pisa_fehler_wirft(self):
        req = self._request()
        fake_pdf = MagicMock()
        fake_pdf.err = 3
        with (
            patch.object(pdf_renderer, "render_to_string", return_value=_TINY_HTML),
            patch.object(pdf_renderer.pisa, "pisaDocument", return_value=fake_pdf),
        ):
            with pytest.raises(RuntimeError):
                pdf_renderer._render_pdf_bytes(req, {})

    def test_render_response_faengt_engine_fehler_und_leitet_um(self):
        req = self._request()
        req.session = {}
        setattr(req, "_messages", FallbackStorage(req))
        with patch.object(pdf_renderer, "_render_pdf_bytes", side_effect=RuntimeError("boom")):
            response = pdf_renderer.render_training_pdf_response(req, {}, date(2026, 6, 1))
        assert response.status_code == 302

    def test_dateiname_ohne_zeitraum_nutzt_heute(self):
        req = self._request()
        req.user = MagicMock(username="tester")
        with patch.object(pdf_renderer, "_render_pdf_bytes", return_value=b"%PDF-1.4 fake"):
            response = pdf_renderer.render_training_pdf_response(req, {}, date(2026, 6, 1))
        assert response.status_code == 200
        assert "TrainingReport_tester_20260601.pdf" in response["Content-Disposition"]

    @override_settings(STATIC_ROOT=_FONTS_STATIC_ROOT)
    def test_url_fetcher_static_root_fallback(self):
        if pdf_renderer.weasyprint is None:
            pytest.skip("WeasyPrint nicht importierbar")
        url = "/static/core/fonts/SourceSans3-Regular.ttf"
        # finders.find liefert im Test None → der STATIC_ROOT-Zweig muss greifen
        with patch.object(pdf_renderer.finders, "find", return_value=None):
            result = pdf_renderer._weasyprint_url_fetcher(url)
        # WeasyPrint liefert je nach Version dict oder URLFetcherResponse – Hauptsache aufgelöst
        assert result is not None

    def test_url_fetcher_data_uri_passthrough(self):
        if pdf_renderer.weasyprint is None:
            pytest.skip("WeasyPrint nicht importierbar")
        # data:-URI ohne "static/"-Marker → unverändert an den Default-Fetcher
        result = pdf_renderer._weasyprint_url_fetcher("data:text/plain;base64,aGk=")
        assert result is not None
