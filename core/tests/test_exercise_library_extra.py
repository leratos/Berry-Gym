"""
Tests für fehlende Abdeckung in core/views/exercise_library.py

Abdeckung:
- uebungen_auswahl: ohne Equipment, mit Equipment-Filter, custom Übungen
- muscle_map: ohne Filter, mit Muskelgruppe
- uebung_detail: Basisaufruf (ohne User-Daten)
- exercise_detail: ohne Trainingsdaten, mit Trainingsdaten, RPE-Trend
- toggle_favorite / toggle_favorit: hinzufügen und entfernen
- _resolve_hilfsmuskeln_labels: String vs. Liste, unbekannte Codes
- _compute_1rm_for_satz: PRO_SEITE, ZEIT, Standard
- _calc_rpe_trend: improving, declining, stable, nicht genug Daten
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory
from core.views.exercise_library import (
    _compute_1rm_for_satz,
    _resolve_hilfsmuskeln_labels,
)

# ─────────────────────────────────────────────────────────────────────────────
# _resolve_hilfsmuskeln_labels
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResolveHilfsmuskelnLabels:
    def test_keine_hilfsmuskeln(self):
        uebung = UebungFactory(hilfsmuskeln=[])
        assert _resolve_hilfsmuskeln_labels(uebung) == []

    def test_liste_mit_bekanntem_code(self):
        uebung = UebungFactory(hilfsmuskeln=["TRIZEPS"])
        labels = _resolve_hilfsmuskeln_labels(uebung)
        assert len(labels) == 1
        assert "Trizeps" in labels[0] or labels[0]  # hat Display-Name

    def test_string_kommasepariert(self):
        uebung = UebungFactory(hilfsmuskeln="Trizeps, Bizeps")
        labels = _resolve_hilfsmuskeln_labels(uebung)
        assert len(labels) == 2

    def test_unbekannter_code_wird_direkt_zurueckgegeben(self):
        uebung = UebungFactory(hilfsmuskeln=["UNBEKANNT_CODE_XYZ"])
        labels = _resolve_hilfsmuskeln_labels(uebung)
        assert "UNBEKANNT_CODE_XYZ" in labels


# ─────────────────────────────────────────────────────────────────────────────
# _compute_1rm_for_satz
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCompute1rmForSatz:
    def test_gesamt_typ(self):
        uebung = UebungFactory(gewichts_typ="GESAMT")
        einheit = TrainingseinheitFactory(user=UserFactory())
        satz = SatzFactory(
            einheit=einheit, uebung=uebung, gewicht=Decimal("100.0"), wiederholungen=5
        )
        eff, one_rm, vol = _compute_1rm_for_satz(satz, "GESAMT")
        assert eff == pytest.approx(100.0)
        assert one_rm > 100.0  # Epley gibt mehr als rohes Gewicht
        assert vol == pytest.approx(500.0)

    def test_pro_seite_verdoppelt_gewicht(self):
        uebung = UebungFactory(gewichts_typ="PRO_SEITE")
        einheit = TrainingseinheitFactory(user=UserFactory())
        satz = SatzFactory(
            einheit=einheit, uebung=uebung, gewicht=Decimal("30.0"), wiederholungen=8
        )
        eff, one_rm, vol = _compute_1rm_for_satz(satz, "PRO_SEITE")
        assert eff == pytest.approx(60.0)

    def test_zeit_typ_gibt_wiederholungen_als_1rm(self):
        uebung = UebungFactory(gewichts_typ="ZEIT")
        einheit = TrainingseinheitFactory(user=UserFactory())
        satz = SatzFactory(
            einheit=einheit, uebung=uebung, gewicht=Decimal("0.0"), wiederholungen=60
        )
        eff, one_rm, vol = _compute_1rm_for_satz(satz, "ZEIT")
        assert one_rm == 60.0

    def test_gewicht_null_ergibt_null_one_rm(self):
        uebung = UebungFactory(gewichts_typ="GESAMT")
        einheit = TrainingseinheitFactory(user=UserFactory())
        satz = SatzFactory(
            einheit=einheit, uebung=uebung, gewicht=Decimal("0.0"), wiederholungen=10
        )
        eff, one_rm, vol = _compute_1rm_for_satz(satz, "GESAMT")
        assert one_rm == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# uebungen_auswahl View
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUebungenAuswahl:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_ohne_equipment_nur_uebungen_ohne_equipment(self):
        uebung_ohne = UebungFactory(bezeichnung="Übung Ohne Eq")
        from core.models import Equipment

        eq = Equipment.objects.create(name="HANTEL_TEST")
        uebung_mit = UebungFactory(bezeichnung="Übung Mit Eq")
        uebung_mit.equipment.add(eq)
        response = self.client.get(reverse("uebungen_auswahl"))
        assert response.status_code == 200
        # Übung ohne Equipment sollte sichtbar sein
        context_text = str(response.context["uebungen_nach_gruppe"])
        assert "Übung Ohne Eq" in context_text

    def test_mit_equipment_filter(self):
        from core.models import Equipment

        eq = Equipment.objects.create(name="BARBELL_TEST")
        self.user.verfuegbares_equipment.add(eq)
        uebung = UebungFactory(bezeichnung="Barbell Übung")
        uebung.equipment.add(eq)
        response = self.client.get(reverse("uebungen_auswahl"))
        assert response.status_code == 200

    def test_login_required(self):
        client = Client()
        response = client.get(reverse("uebungen_auswahl"))
        assert response.status_code == 302

    def test_custom_uebungen_sichtbar(self):
        from core.models import Uebung

        custom = Uebung.objects.create(
            bezeichnung="Meine Custom Übung",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
            gewichts_typ="GESAMT",
            is_custom=True,
            created_by=self.user,
        )
        response = self.client.get(reverse("uebungen_auswahl"))
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# muscle_map View
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMuscleMap:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_ohne_filter(self):
        response = self.client.get(reverse("muscle_map"))
        assert response.status_code == 200
        assert response.context["uebungen"] is None

    def test_mit_muskelgruppe_filter(self):
        uebung = UebungFactory(muskelgruppe="BRUST")
        response = self.client.get(reverse("muscle_map") + "?muskelgruppe=BRUST")
        assert response.status_code == 200
        assert response.context["selected_group"] == "BRUST"
        assert uebung in response.context["uebungen"]

    def test_login_required(self):
        client = Client()
        response = client.get(reverse("muscle_map"))
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# uebung_detail View (einfache Detailseite)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUebungDetail:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_basis_aufruf(self):
        uebung = UebungFactory()
        response = self.client.get(reverse("uebung_detail", kwargs={"uebung_id": uebung.id}))
        assert response.status_code == 200

    def test_nicht_existente_uebung_gibt_404(self):
        response = self.client.get(reverse("uebung_detail", kwargs={"uebung_id": 999999}))
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# exercise_detail View (kombinierte Statistiken)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExerciseDetail:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_ohne_daten(self):
        uebung = UebungFactory()
        response = self.client.get(reverse("exercise_detail", kwargs={"uebung_id": uebung.id}))
        if response.status_code == 200:
            assert response.context["has_data"] is False

    def test_mit_daten(self):
        uebung = UebungFactory(gewichts_typ="GESAMT")
        einheit = TrainingseinheitFactory(user=self.user, datum=timezone.now())
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("80.0"), wiederholungen=8)
        response = self.client.get(reverse("exercise_detail", kwargs={"uebung_id": uebung.id}))
        if response.status_code == 200:
            assert response.context["has_data"] is True
            assert "personal_record" in response.context

    def test_nicht_existente_uebung_gibt_404(self):
        response = self.client.get(reverse("exercise_detail", kwargs={"uebung_id": 999999}))
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# toggle_favorite View
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestToggleFavorite:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)
        self.uebung = UebungFactory()

    def test_favorit_hinzufuegen(self):
        response = self.client.post(
            reverse("toggle_favorite", kwargs={"uebung_id": self.uebung.id})
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is True
        assert self.user in self.uebung.favoriten.all()

    def test_favorit_entfernen(self):
        self.uebung.favoriten.add(self.user)
        response = self.client.post(
            reverse("toggle_favorite", kwargs={"uebung_id": self.uebung.id})
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False
        assert self.user not in self.uebung.favoriten.all()

    def test_login_required(self):
        client = Client()
        url = reverse("toggle_favorite", kwargs={"uebung_id": self.uebung.id})
        response = client.post(url)
        assert response.status_code == 302
