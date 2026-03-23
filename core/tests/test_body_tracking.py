"""
Test Suite für Body Tracking Views.

Tests für:
- KoerperWerte CRUD (add, edit, delete, view)
- ProgressPhoto CRUD (upload, delete, view)
- Permission Checks (User Isolation)
"""

from datetime import date, timedelta
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


@pytest.mark.django_db
class TestKoerperWerteProperties:
    """Tests für berechnete Properties auf KoerperWerte Model."""

    def test_lbm_kg_aus_fettmasse(self):
        """LBM = Gewicht - Fettmasse."""
        wert = KoerperWerteFactory(
            gewicht=90, fettmasse_kg=20, koerperfett_prozent=None, muskelmasse_kg=30
        )
        assert wert.lbm_kg == 70.0

    def test_lbm_kg_aus_kfa_prozent(self):
        """LBM berechnet aus KFA% wenn fettmasse_kg fehlt."""
        wert = KoerperWerteFactory(
            gewicht=100, fettmasse_kg=None, koerperfett_prozent=25, muskelmasse_kg=40
        )
        assert wert.lbm_kg == 75.0

    def test_lbm_kg_none_ohne_fettdaten(self):
        """LBM None wenn weder fettmasse_kg noch KFA%."""
        wert = KoerperWerteFactory(
            gewicht=90, fettmasse_kg=None, koerperfett_prozent=None, muskelmasse_kg=30
        )
        assert wert.lbm_kg is None

    def test_muskel_fett_ratio(self):
        """Muskel/Fett Ratio = Muskelmasse / Fettmasse."""
        wert = KoerperWerteFactory(
            gewicht=90, muskelmasse_kg=40, fettmasse_kg=20, koerperfett_prozent=None
        )
        assert wert.muskel_fett_ratio == 2.0

    def test_muskel_fett_ratio_none_ohne_fett(self):
        """Ratio None wenn keine Fettdaten."""
        wert = KoerperWerteFactory(
            gewicht=90, muskelmasse_kg=40, fettmasse_kg=None, koerperfett_prozent=None
        )
        assert wert.muskel_fett_ratio is None

    def test_get_fett_kg_priorisiert_direktwert(self):
        """_get_fett_kg bevorzugt fettmasse_kg über Prozent."""
        wert = KoerperWerteFactory(
            gewicht=100, fettmasse_kg=22, koerperfett_prozent=25, muskelmasse_kg=40
        )
        # Direktwert 22 hat Vorrang vor 25% von 100 = 25
        assert wert._get_fett_kg() == 22.0

    def test_gewichts_veraenderung_rate(self):
        """Gewichtsrate berechnet kg/Woche zwischen zwei Einträgen."""
        import datetime

        user = UserFactory()
        # Erster Eintrag
        wert1 = KoerperWerteFactory(user=user, gewicht=100)
        # Datum manuell setzen (auto_now_add umgehen)
        KoerperWerte.objects.filter(id=wert1.id).update(datum=datetime.date(2026, 1, 1))
        # Zweiter Eintrag 7 Tage später
        wert2 = KoerperWerteFactory(user=user, gewicht=99)
        KoerperWerte.objects.filter(id=wert2.id).update(datum=datetime.date(2026, 1, 8))
        wert2.refresh_from_db()
        rate = wert2.gewichts_veraenderung_rate()
        assert rate == -1.0  # (99-100) / 7 Tage * 7 = -1.0 kg/Woche

    def test_gewichts_veraenderung_rate_erster_eintrag(self):
        """Rate None wenn kein vorheriger Eintrag."""
        wert = KoerperWerteFactory()
        assert wert.gewichts_veraenderung_rate() is None

    def test_neue_felder_speicherbar(self):
        """Viszeralfett, Grundumsatz, Wasser% können gespeichert werden."""
        wert = KoerperWerteFactory(
            viszeralfett=8,
            grundumsatz_kcal=1850,
            koerperwasser_prozent=55.0,
            koerperwasser_kg=49.5,
        )
        wert.refresh_from_db()
        assert wert.viszeralfett == 8
        assert wert.grundumsatz_kcal == 1850
        assert float(wert.koerperwasser_prozent) == 55.0
        assert float(wert.koerperwasser_kg) == 49.5


# ─────────────────────────────────────────────────────────────────────────────
# Forecasting Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLinearForecastBodyTracking:
    """Unit-Tests für _linear_forecast() in body_tracking – keine DB notwendig."""

    def test_returns_none_with_fewer_than_5_points(self):
        from core.views.body_tracking import _linear_forecast

        pairs = [(date(2026, 1, i), float(i * 80)) for i in range(1, 5)]
        assert _linear_forecast(pairs, 42) is None

    def test_returns_value_with_enough_points(self):
        from core.views.body_tracking import _linear_forecast

        # Leicht sinkendes Gewicht (Diät): 90, 89.5, 89, 88.5, 88 kg
        pairs = [(date(2026, 1, 1) + timedelta(weeks=i), 90.0 - i * 0.5) for i in range(6)]
        result = _linear_forecast(pairs, 42)
        assert result is not None
        assert result < 88  # Trend weiter sinkend


@pytest.mark.django_db
class TestBodyStatsForecast:
    """Integration-Tests: Forecast-Context in body_stats View."""

    def _create_werte(self, user, count=5):
        """Erstellt count KoerperWerte mit aufsteigenden Daten via update()."""
        werte = [KoerperWerteFactory(user=user) for _ in range(count)]
        for i, wert in enumerate(werte):
            KoerperWerte.objects.filter(pk=wert.pk).update(
                datum=date(2026, 1, 1) + timedelta(weeks=i * 2)
            )
        return werte

    def test_forecast_present_with_enough_data(self, client):
        """5 Messungen → gewicht_forecast im Context."""
        user = UserFactory()
        client.force_login(user)
        self._create_werte(user, count=5)
        response = client.get(reverse("body_stats"))
        assert response.status_code == 200
        assert response.context["gewicht_forecast"] is not None

    def test_kfa_forecast_present_with_enough_data(self, client):
        """5 Messungen mit KFA → kfa_forecast im Context."""
        user = UserFactory()
        client.force_login(user)
        self._create_werte(user, count=5)
        response = client.get(reverse("body_stats"))
        assert response.status_code == 200
        assert response.context["kfa_forecast"] is not None

    def test_forecast_absent_with_few_data(self, client):
        """Weniger als 5 Messungen → kein Forecast."""
        user = UserFactory()
        client.force_login(user)
        KoerperWerteFactory(user=user)
        response = client.get(reverse("body_stats"))
        assert response.status_code == 200
        assert response.context["gewicht_forecast"] is None
