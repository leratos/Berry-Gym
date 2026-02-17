"""
Tests für ml_coach/ml_trainer.py – Phase 5.3.

Abgedeckt:
- get_training_data(): effective_weight Berechnung für KG/PRO_SEITE/GESAMT
- get_training_data(): Fallback 80kg bei fehlenden KoerperWerten
- get_training_data(): None bei zu wenig Daten (<10 Sätze)
- train_model(): trainiert korrekt bei ausreichend Daten
- train_model(): Fehler-Dict bei zu wenig Daten
- train_all_user_models(): findet Übungen mit genug Daten
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

import numpy as np
import pytest

from core.tests.factories import (
    KoerperWerteFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)
from ml_coach.ml_trainer import MLTrainer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def uebung_gesamt():
    return UebungFactory(
        bezeichnung="Bankdrücken ML", gewichts_typ="GESAMT", koerpergewicht_faktor=1.0
    )


@pytest.fixture
def uebung_kg():
    return UebungFactory(
        bezeichnung="Dips ML", gewichts_typ="KOERPERGEWICHT", koerpergewicht_faktor=0.70
    )


@pytest.fixture
def uebung_pro_seite():
    return UebungFactory(
        bezeichnung="KH Curl ML", gewichts_typ="PRO_SEITE", koerpergewicht_faktor=1.0
    )


def _create_saetze(user, uebung, n, gewicht=80.0, wdh=10, days_back=180):
    """Erstellt n Arbeitssätze verteilt über die letzten days_back Tage."""
    saetze = []
    for i in range(n):
        datum = timezone.now() - timedelta(days=days_back - i * (days_back // n))
        training = TrainingseinheitFactory(user=user, datum=datum, plan=None)
        s = SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal(str(gewicht + i * 2.5)),
            wiederholungen=wdh,
            ist_aufwaermsatz=False,
            rpe=Decimal("7.5"),
        )
        saetze.append(s)
    return saetze


# ---------------------------------------------------------------------------
# get_training_data – Datenmenge
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetTrainingDataMenge:
    def test_zu_wenig_daten_gibt_none(self, user, uebung_gesamt):
        """< 10 Sätze → (None, None)"""
        _create_saetze(user, uebung_gesamt, n=5)
        trainer = MLTrainer(user, uebung_gesamt)
        X, y = trainer.get_training_data()
        assert X is None
        assert y is None

    def test_genug_daten_gibt_arrays(self, user, uebung_gesamt):
        """≥ 10 Sätze → numpy arrays mit korrekter Form"""
        _create_saetze(user, uebung_gesamt, n=15)
        trainer = MLTrainer(user, uebung_gesamt)
        X, y = trainer.get_training_data()
        assert X is not None
        assert y is not None
        assert isinstance(X, np.ndarray)
        assert isinstance(y, np.ndarray)
        assert X.shape[1] == 5  # 5 Features: effective_weight, reps, days, rpe, set_number

    def test_nur_letzte_6_monate(self, user, uebung_gesamt):
        """Sätze älter als 6 Monate werden ignoriert.

        Trainingseinheit.datum ist auto_now_add → datum per update() backfill-en.
        """
        from core.models import Trainingseinheit

        # 8 aktuelle Sätze (innerhalb 6 Monate)
        _create_saetze(user, uebung_gesamt, n=8, days_back=30)

        # 5 Sätze die über 6 Monate alt sind → per update() rückdatieren
        for _ in range(5):
            t = TrainingseinheitFactory(user=user, plan=None)
            SatzFactory(einheit=t, uebung=uebung_gesamt, ist_aufwaermsatz=False)
            # Datum auf > 180 Tage zurücksetzen
            Trainingseinheit.objects.filter(pk=t.pk).update(
                datum=timezone.now() - timedelta(days=200)
            )

        trainer = MLTrainer(user, uebung_gesamt)
        X, y = trainer.get_training_data()
        # Nur 8 aktuelle Sätze → zu wenig (< 10) → None
        assert X is None


# ---------------------------------------------------------------------------
# get_training_data – effective_weight Berechnung
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetTrainingDataEffectiveWeight:
    def test_gesamt_uebung_nimmt_rohes_gewicht(self, user, uebung_gesamt):
        """GESAMT: effective_weight == satz.gewicht"""
        _create_saetze(user, uebung_gesamt, n=15, gewicht=100.0)
        trainer = MLTrainer(user, uebung_gesamt)
        X, y = trainer.get_training_data()
        # Erstes Feature = effective_weight, sollte nahe 100 sein (± Progression)
        assert X[0, 0] >= 100.0

    def test_kg_uebung_berechnet_effective_weight(self, user, uebung_kg):
        """KOERPERGEWICHT: effective_weight = (user_kg * faktor) + zusatz"""
        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        # 15 Sätze ohne Zusatz
        _create_saetze(user, uebung_kg, n=15, gewicht=0.0)
        trainer = MLTrainer(user, uebung_kg)
        X, y = trainer.get_training_data()
        assert X is not None
        # effective_weight = 80 * 0.70 + 0 = 56.0
        assert X[0, 0] == pytest.approx(56.0, abs=0.01)

    def test_kg_uebung_fallback_80kg(self, user, uebung_kg):
        """Kein KoerperWerte-Eintrag → Fallback 80kg"""
        _create_saetze(user, uebung_kg, n=15, gewicht=0.0)
        trainer = MLTrainer(user, uebung_kg)
        X, y = trainer.get_training_data()
        assert X is not None
        # 80 * 0.70 = 56.0
        assert X[0, 0] == pytest.approx(56.0, abs=0.01)

    def test_pro_seite_verdoppelt_gewicht(self, user, uebung_pro_seite):
        """PRO_SEITE: effective_weight = zusatz * 2"""
        _create_saetze(user, uebung_pro_seite, n=15, gewicht=20.0)
        trainer = MLTrainer(user, uebung_pro_seite)
        X, y = trainer.get_training_data()
        assert X is not None
        # 20 * 2 = 40.0
        assert X[0, 0] == pytest.approx(40.0, abs=0.01)

    def test_kg_mit_zusatz_addiert_korrekt(self, user, uebung_kg):
        """KOERPERGEWICHT + Zusatz: (80 * 0.70) + 10 = 66"""
        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        _create_saetze(user, uebung_kg, n=15, gewicht=10.0)
        trainer = MLTrainer(user, uebung_kg)
        X, y = trainer.get_training_data()
        assert X is not None
        assert X[0, 0] == pytest.approx(66.0, abs=0.01)


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainModel:
    def test_zu_wenig_daten_gibt_fehler_dict(self, user, uebung_gesamt):
        """< 10 Sätze → (None, error-dict)"""
        _create_saetze(user, uebung_gesamt, n=5)
        trainer = MLTrainer(user, uebung_gesamt)
        model, metrics = trainer.train_model()
        assert model is None
        assert "error" in metrics

    def test_genug_daten_erstellt_ml_model(self, user, uebung_gesamt):
        """≥ 10 Sätze → MLPredictionModel wird erstellt/aktualisiert"""
        _create_saetze(user, uebung_gesamt, n=20)
        trainer = MLTrainer(user, uebung_gesamt)
        model, metrics = trainer.train_model()
        assert model is not None
        assert "r2_score" in metrics
        assert "mae" in metrics
        assert "samples" in metrics
        assert metrics["samples"] >= 10

    def test_metrics_sind_sinnvoll(self, user, uebung_gesamt):
        """Bei ausreichend Daten: MAE ist nicht negativ, samples korrekt"""
        _create_saetze(user, uebung_gesamt, n=20)
        trainer = MLTrainer(user, uebung_gesamt)
        _, metrics = trainer.train_model()
        assert metrics["mae"] >= 0
        assert metrics["samples"] >= 10

    def test_modell_wird_in_db_gespeichert(self, user, uebung_gesamt):
        """Nach training: MLPredictionModel existiert in DB"""
        from core.models import MLPredictionModel

        _create_saetze(user, uebung_gesamt, n=20)
        trainer = MLTrainer(user, uebung_gesamt)
        trainer.train_model()
        assert MLPredictionModel.objects.filter(
            user=user, uebung=uebung_gesamt, model_type="STRENGTH"
        ).exists()

    def test_zweites_training_aktualisiert_statt_duplizieren(self, user, uebung_gesamt):
        """update_or_create: zweites Training überschreibt, kein Duplikat"""
        from core.models import MLPredictionModel

        _create_saetze(user, uebung_gesamt, n=20)
        trainer = MLTrainer(user, uebung_gesamt)
        trainer.train_model()
        trainer.train_model()
        count = MLPredictionModel.objects.filter(user=user, uebung=uebung_gesamt).count()
        assert count == 1


# ---------------------------------------------------------------------------
# train_all_user_models
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainAllUserModels:
    def test_findet_uebungen_mit_genug_daten(self, user, uebung_gesamt):
        """Übung mit ≥ 10 Sätzen wird trainiert"""
        _create_saetze(user, uebung_gesamt, n=15)
        results = MLTrainer.train_all_user_models(user, min_samples=10)
        trainierten_uebungen = [r[0] for r in results]
        assert uebung_gesamt in trainierten_uebungen

    def test_ignoriert_uebungen_mit_wenig_daten(self, user):
        """Übung mit < min_samples wird nicht trainiert"""
        uebung_klein = UebungFactory(bezeichnung="Wenig Daten ML", gewichts_typ="GESAMT")
        _create_saetze(user, uebung_klein, n=3)
        results = MLTrainer.train_all_user_models(user, min_samples=10)
        trainierten_uebungen = [r[0] for r in results]
        assert uebung_klein not in trainierten_uebungen

    def test_aufwaermsaetze_werden_nicht_gezaehlt(self, user):
        """Aufwärmsätze zählen nicht zur Datenbasis."""
        from core.tests.factories import AufwaermsatzFactory

        uebung = UebungFactory(bezeichnung="Nur Aufwaerm ML", gewichts_typ="GESAMT")
        t = TrainingseinheitFactory(user=user, plan=None)
        for _ in range(15):
            AufwaermsatzFactory(einheit=t, uebung=uebung)

        results = MLTrainer.train_all_user_models(user, min_samples=10)
        trainierten_uebungen = [r[0] for r in results]
        assert uebung not in trainierten_uebungen
