"""
Test Suite für Body Tracking Views.

Tests für:
- KoerperWerte CRUD (add, edit, delete, view)
- ProgressPhoto CRUD (upload, delete, view)
- Permission Checks (User Isolation)
"""

from io import BytesIO

from django.urls import reverse

import pytest
from PIL import Image

from core.models import KoerperWerte, ProgressPhoto
from core.tests.factories import KoerperWerteFactory, UserFactory


@pytest.mark.django_db
class TestAddKoerperwert:
    """Tests für add_koerperwert View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        url = reverse("add_koerperwert")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_form_anzeigen(self, client):
        """Test: Formular wird angezeigt."""
        user = UserFactory()
        client.force_login(user)

        url = reverse("add_koerperwert")
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context or b"Gewicht" in response.content

    def test_koerperwert_hinzufuegen(self, client):
        """Test: Körperwert erfolgreich hinzufügen."""
        user = UserFactory()
        client.force_login(user)

        url = reverse("add_koerperwert")
        data = {
            "groesse": "180",  # Feldname ist "groesse" nicht "groesse_cm"
            "gewicht": "85.5",
            "kfa": "15.0",
        }

        response = client.post(url, data=data)

        # Redirect nach Erfolg
        assert response.status_code == 302

        # Körperwert wurde erstellt
        wert = KoerperWerte.objects.filter(user=user).first()
        assert wert is not None
        assert wert.groesse_cm == 180
        assert float(wert.gewicht) == 85.5


@pytest.mark.django_db
class TestBodyStats:
    """Tests für body_stats View."""

    def test_body_stats_anzeigen(self, client):
        """Test: Körperstatistiken werden angezeigt."""
        user = UserFactory()
        KoerperWerteFactory(user=user)  # Wert erstellen
        client.force_login(user)

        url = reverse("body_stats")
        response = client.get(url)

        assert response.status_code == 200
        assert "koerperwerte" in response.context or "werte" in response.context


@pytest.mark.django_db
class TestEditKoerperwert:
    """Tests für edit_koerperwert View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        wert = KoerperWerteFactory()
        url = reverse("edit_koerperwert", kwargs={"wert_id": wert.id})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_eigenen_wert_bearbeiten(self, client):
        """Test: Eigenen Körperwert bearbeiten."""
        user = UserFactory()
        wert = KoerperWerteFactory(user=user, gewicht=80, groesse_cm=180)
        client.force_login(user)

        url = reverse("edit_koerperwert", kwargs={"wert_id": wert.id})
        data = {
            "groesse_cm": "180",  # Explizit als String
            "gewicht": "85.0",
            "koerperfett_prozent": "15.0",
        }

        response = client.post(url, data=data)

        assert response.status_code == 302

        # Wert wurde aktualisiert
        wert.refresh_from_db()
        assert float(wert.gewicht) == 85.0

    def test_fremden_wert_bearbeiten_verboten(self, client):
        """Test: Fremden Körperwert bearbeiten verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        wert_user2 = KoerperWerteFactory(user=user2)
        client.force_login(user1)

        url = reverse("edit_koerperwert", kwargs={"wert_id": wert_user2.id})
        response = client.get(url)

        # Sollte 404 sein
        assert response.status_code == 404


@pytest.mark.django_db
class TestDeleteKoerperwert:
    """Tests für delete_koerperwert View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        wert = KoerperWerteFactory()
        url = reverse("delete_koerperwert", kwargs={"wert_id": wert.id})
        response = client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_eigenen_wert_loeschen(self, client):
        """Test: Eigenen Körperwert löschen."""
        user = UserFactory()
        wert = KoerperWerteFactory(user=user)
        client.force_login(user)

        wert_id = wert.id
        url = reverse("delete_koerperwert", kwargs={"wert_id": wert.id})
        response = client.post(url)

        assert response.status_code == 302

        # Wert wurde gelöscht
        assert not KoerperWerte.objects.filter(id=wert_id).exists()

    def test_fremden_wert_loeschen_verboten(self, client):
        """Test: Fremden Körperwert löschen verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        wert_user2 = KoerperWerteFactory(user=user2)
        client.force_login(user1)

        url = reverse("delete_koerperwert", kwargs={"wert_id": wert_user2.id})
        response = client.post(url)

        # Sollte 404 sein
        assert response.status_code == 404

        # Wert existiert noch
        assert KoerperWerte.objects.filter(id=wert_user2.id).exists()


@pytest.mark.django_db
class TestProgressPhotos:
    """Tests für progress_photos View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        url = reverse("progress_photos")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_progress_photos_anzeigen(self, client):
        """Test: Fortschrittsfotos werden angezeigt."""
        user = UserFactory()
        client.force_login(user)

        url = reverse("progress_photos")
        response = client.get(url)

        assert response.status_code == 200


def create_test_image():
    """Helper: Erstellt ein Test-Bild für Upload-Tests."""
    file = BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file, "PNG")
    file.name = "test_photo.png"
    file.seek(0)
    return file


@pytest.mark.django_db
class TestUploadProgressPhoto:
    """Tests für upload_progress_photo View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        url = reverse("upload_progress_photo")
        response = client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_foto_hochladen(self, client):
        """Test: Fortschrittsfoto erfolgreich hochladen."""
        user = UserFactory()
        client.force_login(user)

        url = reverse("upload_progress_photo")
        data = {
            "foto": create_test_image(),
            "notiz": "Start",
            "gewicht_kg": "80.5",
        }

        response = client.post(url, data=data)

        # Redirect oder Success
        assert response.status_code in [200, 302]

        # Foto wurde erstellt
        photo = ProgressPhoto.objects.filter(user=user).first()
        assert photo is not None
        assert photo.notiz == "Start"


@pytest.mark.django_db
class TestDeleteProgressPhoto:
    """Tests für delete_progress_photo View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        user = UserFactory()
        photo = ProgressPhoto.objects.create(user=user, foto="test.jpg", notiz="Test")
        url = reverse("delete_progress_photo", kwargs={"photo_id": photo.id})
        response = client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_eigenes_foto_loeschen(self, client):
        """Test: Eigenes Fortschrittsfoto löschen."""
        user = UserFactory()
        photo = ProgressPhoto.objects.create(user=user, foto="test.jpg", notiz="Test")
        client.force_login(user)

        photo_id = photo.id
        url = reverse("delete_progress_photo", kwargs={"photo_id": photo.id})
        response = client.post(url)

        assert response.status_code == 302

        # Foto wurde gelöscht
        assert not ProgressPhoto.objects.filter(id=photo_id).exists()

    def test_fremdes_foto_loeschen_verboten(self, client):
        """Test: Fremdes Fortschrittsfoto löschen verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        photo_user2 = ProgressPhoto.objects.create(user=user2, foto="test.jpg", notiz="Test")
        client.force_login(user1)

        url = reverse("delete_progress_photo", kwargs={"photo_id": photo_user2.id})
        response = client.post(url)

        # Sollte 404 sein
        assert response.status_code == 404

        # Foto existiert noch
        assert ProgressPhoto.objects.filter(id=photo_user2.id).exists()
