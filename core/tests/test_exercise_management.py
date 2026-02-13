"""
Phase 2.7 - Exercise Management Tests
Testet: equipment_management, toggle_equipment,
        export_uebungen (JSON/CSV), import_uebungen
"""

import json
import tempfile

from django.urls import reverse

import pytest

from core.models import Equipment, Uebung
from core.tests.factories import UebungFactory, UserFactory


def create_equipment(name="LANGHANTEL"):
    """Hilfsfunktion: Equipment mit gültigem Choices-Namen erstellen."""
    return Equipment.objects.get_or_create(name=name)[0]


# ==============================================================================
# Equipment Management View
# ==============================================================================


@pytest.mark.django_db
class TestEquipmentManagement:
    """Tests für die Equipment-Verwaltungsseite"""

    def test_equipment_management_erfordert_login(self, client):
        """Nicht eingeloggte User werden weitergeleitet"""
        url = reverse("equipment_management")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]

    def test_equipment_management_geladen(self, client):
        """Seite lädt erfolgreich für eingeloggten User"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("equipment_management")
        response = client.get(url)
        assert response.status_code == 200

    def test_equipment_management_context_vorhanden(self, client):
        """Context enthält equipment-bezogene Variablen"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("equipment_management")
        response = client.get(url)
        assert response.status_code == 200
        assert "categorized_equipment" in response.context
        assert "user_equipment_ids" in response.context

    def test_equipment_management_statistiken_vorhanden(self, client):
        """Context enthält Übungs-Statistiken"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("equipment_management")
        response = client.get(url)
        assert "total_uebungen" in response.context
        assert "available_uebungen" in response.context
        assert "unavailable_uebungen" in response.context


# ==============================================================================
# Toggle Equipment View
# ==============================================================================


@pytest.mark.django_db
class TestToggleEquipment:
    """Tests für Equipment An/Aus-Schalten"""

    def test_toggle_equipment_erfordert_login(self, client):
        """Nicht eingeloggte User werden weitergeleitet"""
        eq = create_equipment("KURZHANTEL")
        url = reverse("toggle_equipment", kwargs={"equipment_id": eq.id})
        response = client.post(url)
        assert response.status_code == 302

    def test_toggle_equipment_hinzufuegen(self, client):
        """Equipment wird dem User hinzugefügt"""
        user = UserFactory()
        eq = create_equipment("LANGHANTEL")
        client.force_login(user)
        url = reverse("toggle_equipment", kwargs={"equipment_id": eq.id})
        client.post(url)
        assert user in eq.users.all()

    def test_toggle_equipment_entfernen(self, client):
        """Equipment wird vom User entfernt wenn bereits vorhanden"""
        user = UserFactory()
        eq = create_equipment("KETTLEBELL")
        eq.users.add(user)
        client.force_login(user)
        url = reverse("toggle_equipment", kwargs={"equipment_id": eq.id})
        client.post(url)
        assert user not in eq.users.all()

    def test_toggle_equipment_ajax_json_response(self, client):
        """AJAX-Request liefert JSON mit status und equipment_name"""
        user = UserFactory()
        eq = create_equipment("BANK")
        client.force_login(user)
        url = reverse("toggle_equipment", kwargs={"equipment_id": eq.id})
        response = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "status" in data
        assert data["status"] in ("added", "removed")
        assert "equipment_name" in data

    def test_toggle_equipment_nicht_ajax_redirect(self, client):
        """Normaler POST leitet zu equipment_management weiter"""
        user = UserFactory()
        eq = create_equipment("MATTE")
        client.force_login(user)
        url = reverse("toggle_equipment", kwargs={"equipment_id": eq.id})
        response = client.post(url)
        assert response.status_code == 302

    def test_toggle_equipment_404_unbekannt(self, client):
        """404 bei nicht existierendem Equipment"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("toggle_equipment", kwargs={"equipment_id": 99999})
        response = client.post(url)
        assert response.status_code == 404


# ==============================================================================
# Export Uebungen View
# ==============================================================================


@pytest.mark.django_db
class TestExportUebungen:
    """Tests für den Übungsexport (staff only)"""

    def test_export_erfordert_staff(self, client):
        """Normaler User wird abgewiesen (302 Redirect)"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("export_uebungen")
        response = client.get(url)
        assert response.status_code == 302

    def test_export_json_erfolg(self, client):
        """Staff-User kann Übungen als JSON exportieren"""
        staff = UserFactory(is_staff=True)
        UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST")
        client.force_login(staff)
        url = reverse("export_uebungen") + "?format=json"
        response = client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        data = json.loads(response.content)
        assert "exercises" in data
        assert len(data["exercises"]) >= 1

    def test_export_json_dateiname(self, client):
        """JSON-Export hat Content-Disposition Header"""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("export_uebungen") + "?format=json"
        response = client.get(url)
        assert "Content-Disposition" in response
        assert "uebungen_export" in response["Content-Disposition"]
        assert ".json" in response["Content-Disposition"]

    def test_export_csv_erfolg(self, client):
        """Staff-User kann Übungen als CSV exportieren"""
        staff = UserFactory(is_staff=True)
        UebungFactory(bezeichnung="Kniebeugen", muskelgruppe="BEINE_QUAD")
        client.force_login(staff)
        url = reverse("export_uebungen") + "?format=csv"
        response = client.get(url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_export_invalid_format_gibt_400(self, client):
        """Ungültiges Format-Param gibt 400 zurück"""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("export_uebungen") + "?format=xml"
        response = client.get(url)
        assert response.status_code == 400


# ==============================================================================
# Import Uebungen View
# ==============================================================================


@pytest.mark.django_db
class TestImportUebungen:
    """Tests für den Übungsimport (staff only)"""

    def test_import_erfordert_staff(self, client):
        """Normaler User wird abgewiesen"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("import_uebungen")
        response = client.post(url)
        assert response.status_code == 302

    def test_import_erfordert_post(self, client):
        """GET-Request wird mit 405 abgewiesen"""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")
        response = client.get(url)
        assert response.status_code == 405

    def test_import_ohne_datei_redirect(self, client):
        """POST ohne Datei leitet weiter (kein Absturz)"""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")
        response = client.post(url)
        assert response.status_code == 302

    def test_import_json_erstellt_uebungen(self, client):
        """Gültiges JSON importiert neue Übungen"""
        from core.models import Uebung

        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")

        import_data = json.dumps(
            {
                "exercises": [
                    {
                        "bezeichnung": "Import Test Übung XYZ",
                        "muskelgruppe": "BRUST",
                        "bewegungstyp": "COMPOUND",
                        "gewichts_typ": "GESAMT",
                        "equipment": [],
                    }
                ]
            }
        ).encode()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(import_data)
            f.seek(0)
            f.flush()
            response = client.post(url, {"import_file": f})

        assert response.status_code == 302
        assert Uebung.objects.filter(bezeichnung="Import Test Übung XYZ").exists()

    def test_import_ungueliges_json_redirect(self, client):
        """Ungültiges JSON leitet weiter ohne Absturz"""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")

        invalid_content = b"kein json {{{ungueltig"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(invalid_content)
            f.seek(0)
            f.flush()
            response = client.post(url, {"import_file": f})

        # Darf nicht crashen - Redirect zu uebungen_auswahl
        assert response.status_code == 302

    def test_import_dict_mit_exercises_key(self, client):
        """JSON als Dict mit 'exercises'-Key wird korrekt verarbeitet."""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")

        import_data = json.dumps(
            {"exercises": [{"bezeichnung": "Import Dict Test Übung", "muskelgruppe": "BRUST"}]}
        ).encode()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(import_data)
            f.seek(0)
            f.flush()
            response = client.post(url, {"import_file": f})

        assert response.status_code == 302
        assert Uebung.objects.filter(bezeichnung="Import Dict Test Übung").exists()

    def test_import_dry_run_erstellt_keine_uebungen(self, client):
        """dry_run=on führt keinen echten Import durch."""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")

        import_data = json.dumps(
            [{"bezeichnung": "Dry Run Test Übung", "muskelgruppe": "BRUST"}]
        ).encode()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(import_data)
            f.seek(0)
            f.flush()
            response = client.post(url, {"import_file": f, "dry_run": "on"})

        assert response.status_code == 302
        # Dry run darf keine Übung erstellt haben
        assert not Uebung.objects.filter(bezeichnung="Dry Run Test Übung").exists()

    def test_import_uebung_ohne_bezeichnung_wird_uebersprungen(self, client):
        """Übungs-Einträge ohne 'bezeichnung' werden übersprungen."""
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        url = reverse("import_uebungen")

        import_data = json.dumps(
            [
                {"muskelgruppe": "BRUST"},  # Kein bezeichnung → skip
                {"bezeichnung": "Gültige Übung Import", "muskelgruppe": "BRUST"},
            ]
        ).encode()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(import_data)
            f.seek(0)
            f.flush()
            response = client.post(url, {"import_file": f})

        assert response.status_code == 302
        # Nur die gültige Übung wurde importiert
        assert Uebung.objects.filter(bezeichnung="Gültige Übung Import").exists()
