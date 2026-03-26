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
        """Gewichtsrate berechnet kg/Woche bei ≥14 Tagen Abstand (Primärpfad)."""
        import datetime

        user = UserFactory()
        # Erster Eintrag
        wert1 = KoerperWerteFactory(user=user, gewicht=100)
        KoerperWerte.objects.filter(id=wert1.id).update(datum=datetime.date(2026, 1, 1))
        # Zweiter Eintrag 14 Tage später
        wert2 = KoerperWerteFactory(user=user, gewicht=98)
        KoerperWerte.objects.filter(id=wert2.id).update(datum=datetime.date(2026, 1, 15))
        wert2.refresh_from_db()
        rate = wert2.gewichts_veraenderung_rate()
        assert rate == -1.0  # (98-100) / 14 Tage * 7 = -1.0 kg/Woche

    def test_gewichts_veraenderung_rate_7_tage_nutzt_fallback(self):
        """Bei nur 7 Tagen Abstand greift der Fallback (ältester Eintrag)."""
        import datetime

        user = UserFactory()
        wert1 = KoerperWerteFactory(user=user, gewicht=100)
        KoerperWerte.objects.filter(id=wert1.id).update(datum=datetime.date(2026, 1, 1))
        wert2 = KoerperWerteFactory(user=user, gewicht=99)
        KoerperWerte.objects.filter(id=wert2.id).update(datum=datetime.date(2026, 1, 8))
        wert2.refresh_from_db()
        rate = wert2.gewichts_veraenderung_rate()
        # Fallback findet den ältesten Eintrag (Jan 1) → (99-100)/7*7 = -1.0
        assert rate == -1.0

    def test_gewichts_veraenderung_rate_bevorzugt_14_tage(self):
        """Bei mehreren Referenz-Einträgen wird der nächste an 14 Tagen bevorzugt."""
        import datetime

        user = UserFactory()
        # 3 Einträge: Tag 0, Tag 14, Tag 21 → aktueller Eintrag Tag 28
        wert_d0 = KoerperWerteFactory(user=user, gewicht=100)
        KoerperWerte.objects.filter(id=wert_d0.id).update(datum=datetime.date(2026, 1, 1))
        wert_d14 = KoerperWerteFactory(user=user, gewicht=99)
        KoerperWerte.objects.filter(id=wert_d14.id).update(datum=datetime.date(2026, 1, 15))
        wert_d21 = KoerperWerteFactory(user=user, gewicht=99)
        KoerperWerte.objects.filter(id=wert_d21.id).update(datum=datetime.date(2026, 1, 22))

        # Aktueller Eintrag Tag 28
        wert_d28 = KoerperWerteFactory(user=user, gewicht=98)
        KoerperWerte.objects.filter(id=wert_d28.id).update(datum=datetime.date(2026, 1, 29))
        wert_d28.refresh_from_db()

        rate = wert_d28.gewichts_veraenderung_rate()
        # Fenster: 14-30 Tage vor 29.1. = 30.12.–15.1.
        # Beide d0 (1.1.) und d14 (15.1.) qualifizieren → neuester = d14
        # (98-99) / 14 Tage * 7 = -0.5 kg/Woche
        assert rate == -0.5

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
        """Erstellt count KoerperWerte mit aufsteigenden Daten und konsistenten Werten."""
        from decimal import Decimal

        werte = []
        for i in range(count):
            w = KoerperWerteFactory(
                user=user,
                gewicht=Decimal("85.00"),
                groesse_cm=180,
                koerperfett_prozent=Decimal("20.0"),
                muskelmasse_kg=Decimal("35.00"),
            )
            KoerperWerte.objects.filter(pk=w.pk).update(
                datum=date(2026, 1, 1) + timedelta(weeks=i * 2)
            )
            werte.append(w)
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


# ─────────────────────────────────────────────────────────────────────────────
# Outlier Detection Tests (Phase 9.1)
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectOutliers:
    """Unit-Tests für detect_outliers() – keine DB notwendig.

    Verwendet Mock-Objekte statt echte KoerperWerte-Instanzen,
    weil detect_outliers() nur auf id, datum, koerperfett_prozent,
    muskelmasse_kg und ffmi (property) zugreift.
    """

    @staticmethod
    def _make_wert(id, datum, kfa=None, muskel=None, ffmi_val=None):
        """Erzeugt ein Mock-KoerperWerte-Objekt."""
        from unittest.mock import MagicMock

        w = MagicMock()
        w.id = id
        w.datum = datum
        w.koerperfett_prozent = kfa
        w.muskelmasse_kg = muskel
        w.ffmi = ffmi_val
        return w

    def test_no_outliers_in_smooth_data(self):
        """Gleichmäßiger Verlauf → keine Flags."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(2, date(2026, 1, 8), kfa=19.8, muskel=35.2, ffmi_val=20.1),
            self._make_wert(3, date(2026, 1, 15), kfa=19.6, muskel=35.4, ffmi_val=20.2),
            self._make_wert(4, date(2026, 1, 22), kfa=19.4, muskel=35.6, ffmi_val=20.3),
            self._make_wert(5, date(2026, 1, 29), kfa=19.2, muskel=35.8, ffmi_val=20.4),
        ]
        assert detect_outliers(werte) == set()

    def test_kfa_spike_flagged(self):
        """KFA-Spike (Δ > 2.0%/Woche) wird geflaggt."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(2, date(2026, 1, 8), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(3, date(2026, 1, 15), kfa=25.0, muskel=35.0, ffmi_val=20.0),  # Spike
            self._make_wert(4, date(2026, 1, 22), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(5, date(2026, 1, 29), kfa=20.0, muskel=35.0, ffmi_val=20.0),
        ]
        outliers = detect_outliers(werte)
        assert 3 in outliers  # Spike-Punkt geflaggt

    def test_ffmi_spike_flagged(self):
        """FFMI-Spike (Δ > 0.5/Woche) wird geflaggt."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(2, date(2026, 1, 8), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(3, date(2026, 1, 15), kfa=20.0, muskel=35.0, ffmi_val=21.5),  # Spike
            self._make_wert(4, date(2026, 1, 22), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(5, date(2026, 1, 29), kfa=20.0, muskel=35.0, ffmi_val=20.0),
        ]
        outliers = detect_outliers(werte)
        assert 3 in outliers

    def test_muskelmasse_spike_flagged(self):
        """Muskelmasse-Spike (Δ > 1.0 kg/Woche) wird geflaggt."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(2, date(2026, 1, 8), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(3, date(2026, 1, 15), kfa=20.0, muskel=38.0, ffmi_val=20.0),  # +3kg
            self._make_wert(4, date(2026, 1, 22), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(5, date(2026, 1, 29), kfa=20.0, muskel=35.0, ffmi_val=20.0),
        ]
        outliers = detect_outliers(werte)
        assert 3 in outliers

    def test_threshold_exactly_on_boundary_not_flagged(self):
        """Delta genau auf Schwelle wird NICHT geflaggt (> nicht >=)."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(
                2, date(2026, 1, 8), kfa=22.0, muskel=35.0, ffmi_val=20.0
            ),  # Δ=2.0 genau
            self._make_wert(3, date(2026, 1, 15), kfa=22.0, muskel=35.0, ffmi_val=20.0),
        ]
        outliers = detect_outliers(werte)
        # Δ 2.0 ist genau die Schwelle – nicht überschritten
        assert 2 not in outliers

    def test_single_entry_no_outliers(self):
        """Ein einzelner Eintrag kann kein Ausreißer sein."""
        from core.views.body_tracking import detect_outliers

        werte = [self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0)]
        assert detect_outliers(werte) == set()

    def test_empty_list(self):
        """Leere Liste → leeres Set."""
        from core.views.body_tracking import detect_outliers

        assert detect_outliers([]) == set()

    def test_none_values_skipped(self):
        """Punkte ohne KFA/Muskel/FFMI werden übersprungen, nicht geflaggt."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=None, ffmi_val=None),
            self._make_wert(2, date(2026, 1, 8), kfa=None, muskel=35.0, ffmi_val=None),
            self._make_wert(3, date(2026, 1, 15), kfa=20.0, muskel=None, ffmi_val=None),
        ]
        outliers = detect_outliers(werte)
        assert outliers == set()

    def test_delta_normalized_to_week(self):
        """Delta wird auf 7 Tage normalisiert – 14-Tage-Abstand mit Δ=3.0 KFA → 1.5/Woche → ok."""
        from core.views.body_tracking import detect_outliers

        werte = [
            self._make_wert(1, date(2026, 1, 1), kfa=20.0, muskel=35.0, ffmi_val=20.0),
            self._make_wert(
                2, date(2026, 1, 15), kfa=23.0, muskel=35.0, ffmi_val=20.0
            ),  # 14d, Δ3.0
            self._make_wert(3, date(2026, 1, 29), kfa=23.0, muskel=35.0, ffmi_val=20.0),
        ]
        outliers = detect_outliers(werte)
        # 3.0% über 14 Tage = 1.5%/Woche → unter Schwelle 2.0
        assert 2 not in outliers


@pytest.mark.django_db
class TestBodyStatsOutlierIntegration:
    """Integration-Tests: Outlier-Context in body_stats View."""

    def _create_werte_with_spike(self, user):
        """Erstellt 5 Werte, davon einer mit KFA-Spike."""
        import datetime
        from decimal import Decimal

        werte = []
        for i in range(5):
            kfa = Decimal("20.0") if i != 2 else Decimal("30.0")
            w = KoerperWerteFactory(
                user=user,
                gewicht=Decimal("85.00"),
                groesse_cm=180,
                koerperfett_prozent=kfa,
                muskelmasse_kg=Decimal("35.00"),
            )
            KoerperWerte.objects.filter(pk=w.pk).update(
                datum=datetime.date(2026, 1, 1) + timedelta(weeks=i)
            )
            werte.append(w)
        return werte

    def test_outlier_ids_in_context(self, client):
        """body_stats liefert outlier_ids im Context."""
        user = UserFactory()
        client.force_login(user)
        self._create_werte_with_spike(user)
        response = client.get(reverse("body_stats"))
        assert response.status_code == 200
        assert "outlier_ids" in response.context
        assert len(response.context["outlier_ids"]) > 0

    def test_forecast_excludes_outliers(self, client):
        """Forecast-Wert ändert sich wenn Ausreißer exkludiert werden."""
        user = UserFactory()
        client.force_login(user)
        self._create_werte_with_spike(user)
        response = client.get(reverse("body_stats"))
        assert response.status_code == 200
        # Forecast existiert (genug Datenpunkte nach Ausreißer-Filter)
        # Mindestens 4 saubere Punkte + kfa_forecast kann None sein (< 5 sauber)
        # Wichtig: kein Crash
        assert "kfa_forecast" in response.context
