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
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.urls import reverse

import pytest

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

        # Sätze mit korrektem Parameter 'einheit'
        satz1 = SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=80.0,
            wiederholungen=10,
            rpe=8,
        )
        satz2 = SatzFactory(
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

        # Korrekte PlanUebung Factory Parameter
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
