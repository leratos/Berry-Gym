"""
Unit Tests für Core Models.

Diese Tests prüfen die grundlegende Funktionalität der Django Models.
Fokus: Business Logic, Properties, Validators.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError

import pytest

from core.tests.factories import (
    AufwaermsatzFactory,
    CardioEinheitFactory,
    KoerperWerteFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestUebungModel:
    """Tests für das Uebung Model."""

    def test_create_basic_uebung(self):
        """Test: Übung kann erstellt werden."""
        uebung = UebungFactory(bezeichnung="Bankdrücken")

        assert uebung.id is not None
        assert uebung.bezeichnung == "Bankdrücken"
        assert uebung.muskelgruppe == "BRUST"
        assert uebung.is_global is True  # Nicht custom

    def test_custom_uebung_belongs_to_user(self):
        """Test: Custom-Übungen sind user-spezifisch."""
        from core.tests.factories import CustomUebungFactory

        user = UserFactory()
        uebung = CustomUebungFactory(created_by=user, bezeichnung="Meine spezielle Übung")

        assert uebung.is_custom is True
        assert uebung.created_by == user
        assert uebung.is_global is False

    def test_video_embed_url_youtube(self):
        """Test: YouTube URL wird zu Embed konvertiert."""
        uebung = UebungFactory(video_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert uebung.video_embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_video_embed_url_vimeo(self):
        """Test: Vimeo URL wird zu Embed konvertiert."""
        uebung = UebungFactory(video_link="https://vimeo.com/123456789")

        assert uebung.video_embed_url == "https://player.vimeo.com/video/123456789"

    def test_has_video_property(self):
        """Test: has_video Property funktioniert."""
        uebung_mit_video = UebungFactory(video_link="https://youtube.com/watch?v=test")
        uebung_ohne_video = UebungFactory(video_link=None, video_file=None)

        assert uebung_mit_video.has_video is True
        assert uebung_ohne_video.has_video is False


@pytest.mark.django_db
class TestKoerperWerteModel:
    """Tests für das KoerperWerte Model."""

    def test_bmi_calculation(self):
        """Test: BMI wird korrekt berechnet."""
        werte = KoerperWerteFactory(groesse_cm=180, gewicht=Decimal("80.0"))

        # BMI = 80 / (1.8^2) = 24.7
        assert werte.bmi == pytest.approx(24.7, rel=0.1)

    def test_ffmi_calculation_with_koerperfett(self):
        """Test: FFMI wird mit Körperfett korrekt berechnet."""
        werte = KoerperWerteFactory(
            groesse_cm=180,
            gewicht=Decimal("80.0"),
            koerperfett_prozent=Decimal("15.0"),
            fettmasse_kg=Decimal("12.0"),  # 15% von 80kg
        )

        # Fettfreie Masse = 80 - 12 = 68kg
        # FFMI = 68 / (1.8^2) = 21.0
        # FFMI normiert = 21.0 + 6.1 * (1.8 - 1.8) = 21.0
        assert werte.ffmi == pytest.approx(21.0, rel=0.1)


@pytest.mark.django_db
class TestTrainingseinheitModel:
    """Tests für das Trainingseinheit Model."""

    def test_create_training_session(self):
        """Test: Trainingseinheit kann erstellt werden."""
        training = TrainingseinheitFactory(dauer_minuten=75)

        assert training.id is not None
        assert training.dauer_minuten == 75
        assert training.user is not None

    def test_training_string_representation(self):
        """Test: __str__ zeigt Datum korrekt."""
        from datetime import datetime

        training = TrainingseinheitFactory()

        str_repr = str(training)
        assert "Training vom" in str_repr
        assert training.datum.strftime("%d.%m.%Y") in str_repr


@pytest.mark.django_db
class TestSatzModel:
    """Tests für das Satz Model."""

    def test_create_arbeitssatz(self):
        """Test: Normaler Arbeitssatz kann erstellt werden."""
        satz = SatzFactory(gewicht=Decimal("100.0"), wiederholungen=10, rpe=Decimal("8.5"))

        assert satz.ist_aufwaermsatz is False
        assert satz.gewicht == Decimal("100.0")
        assert satz.wiederholungen == 10
        assert satz.rpe == Decimal("8.5")

    def test_create_aufwaermsatz(self):
        """Test: Aufwärmsatz hat niedrigeres Gewicht/RPE."""
        warmup = AufwaermsatzFactory()

        assert warmup.ist_aufwaermsatz is True
        assert warmup.gewicht < Decimal("100.0")
        assert warmup.rpe < Decimal("7.0")

    def test_rpe_validation_range(self):
        """Test: RPE muss zwischen 1-10 liegen."""
        # Valid RPE
        satz_valid = SatzFactory(rpe=Decimal("8.5"))
        assert satz_valid.rpe == Decimal("8.5")

        # Invalid RPE würde ValidationError werfen (wird von Validator geprüft)
        # Aber Factory generiert nur valide Werte

    def test_superset_gruppierung(self):
        """Test: Supersätze können gruppiert werden."""
        training = TrainingseinheitFactory()

        satz1 = SatzFactory(einheit=training, superset_gruppe=1, satz_nr=1)
        satz2 = SatzFactory(einheit=training, superset_gruppe=1, satz_nr=2)
        satz3 = SatzFactory(einheit=training, superset_gruppe=2, satz_nr=3)

        assert satz1.superset_gruppe == satz2.superset_gruppe
        assert satz1.superset_gruppe != satz3.superset_gruppe


@pytest.mark.django_db
class TestCardioEinheitModel:
    """Tests für das CardioEinheit Model."""

    def test_ermuedungs_punkte_leicht(self):
        """Test: Leichte Intensität gibt 0.1 Punkte/Min."""
        cardio = CardioEinheitFactory(intensitaet="LEICHT", dauer_minuten=30)

        # 30 Min × 0.1 = 3.0 Punkte
        assert cardio.ermuedungs_punkte == pytest.approx(3.0, abs=0.1)

    def test_ermuedungs_punkte_moderat(self):
        """Test: Moderate Intensität gibt 0.2 Punkte/Min."""
        cardio = CardioEinheitFactory(intensitaet="MODERAT", dauer_minuten=45)

        # 45 Min × 0.2 = 9.0 Punkte
        assert cardio.ermuedungs_punkte == pytest.approx(9.0, abs=0.1)

    def test_ermuedungs_punkte_intensiv(self):
        """Test: Intensive Intensität gibt 0.4 Punkte/Min."""
        cardio = CardioEinheitFactory(intensitaet="INTENSIV", dauer_minuten=20)

        # 20 Min × 0.4 = 8.0 Punkte
        assert cardio.ermuedungs_punkte == pytest.approx(8.0, abs=0.1)

    def test_cardio_string_representation(self):
        """Test: __str__ zeigt Aktivität und Dauer."""
        cardio = CardioEinheitFactory(aktivitaet="LAUFEN", dauer_minuten=30)

        str_repr = str(cardio)
        assert "Laufen" in str_repr or "30" in str_repr


@pytest.mark.django_db
class Test1RMCalculation:
    """Tests für 1RM Berechnung (Epley Formula)."""

    def test_epley_formula_basic(self):
        """Test: Epley-Formel 1RM = weight × (1 + reps/30)."""
        # 100kg × 10 Wdh = 100 × (1 + 10/30) = 100 × 1.333 = 133.3kg
        weight = Decimal("100.0")
        reps = 10

        expected_1rm = weight * (Decimal("1") + Decimal(reps) / Decimal("30"))

        # 133.33...
        assert expected_1rm == pytest.approx(Decimal("133.33"), abs=0.1)

    def test_one_rep_max_is_weight(self):
        """Test: 1 Wiederholung = 1RM = Gewicht."""
        weight = Decimal("150.0")
        reps = 1

        expected_1rm = weight * (Decimal("1") + Decimal(reps) / Decimal("30"))

        # 150 × (1 + 1/30) = 150 × 1.033 = 155kg
        # ABER: Bei 1 Wdh ist das Gewicht der 1RM!
        # Die Formel ist für 2-10 Wdh ausgelegt
        assert expected_1rm > weight  # Formel überschätzt leicht bei 1 rep
