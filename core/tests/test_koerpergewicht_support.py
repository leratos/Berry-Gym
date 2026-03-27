"""
Tests für Phase 5.2b – Körpergewicht-Support in Statistics und Training Session.

Abgedeckt:
- _compute_1rm_and_weight(): alle Gewichtstypen (GESAMT, KOERPERGEWICHT, PRO_SEITE, ZEIT)
- koerpergewicht_faktor Anwendung (Dips 0.70, Crunch 0.30)
- Fallback 80kg wenn keine KoerperWerte vorhanden
- _get_user_koerpergewicht() mit und ohne KoerperWerte-Eintrag
- show_reps_chart Logik: reine KG vs. mit Zusatz
- _determine_empfehlung_hint() für KG-Übungen (Wdh statt +2.5kg)
- _determine_empfehlung_hint() für GESAMT-Übungen (unveraendert)
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from core.tests.factories import (
    KoerperWerteFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)
from core.views.training_session import _determine_empfehlung_hint
from core.views.training_stats import (
    _compute_1rm_and_weight,
    _get_koerpergewicht_for_date,
    _get_koerpergewicht_map,
    _get_user_koerpergewicht,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def uebung_gesamt():
    return UebungFactory(
        bezeichnung="Bankdrücken", gewichts_typ="GESAMT", koerpergewicht_faktor=1.0
    )


@pytest.fixture
def uebung_pro_seite():
    return UebungFactory(
        bezeichnung="Kurzhantel Curl", gewichts_typ="PRO_SEITE", koerpergewicht_faktor=1.0
    )


@pytest.fixture
def uebung_zeit():
    return UebungFactory(bezeichnung="Plank", gewichts_typ="ZEIT", koerpergewicht_faktor=0.0)


@pytest.fixture
def uebung_dips():
    return UebungFactory(
        bezeichnung="Dips (Barren)", gewichts_typ="KOERPERGEWICHT", koerpergewicht_faktor=0.70
    )


@pytest.fixture
def uebung_crunch():
    return UebungFactory(
        bezeichnung="Crunch", gewichts_typ="KOERPERGEWICHT", koerpergewicht_faktor=0.30
    )


@pytest.fixture
def uebung_klimmzug():
    return UebungFactory(
        bezeichnung="Klimmzüge", gewichts_typ="KOERPERGEWICHT", koerpergewicht_faktor=0.70
    )


# ---------------------------------------------------------------------------
# _get_user_koerpergewicht
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetUserKoerpergewicht:
    def test_gibt_letztes_gewicht_zurueck(self, user):
        KoerperWerteFactory(user=user, gewicht=Decimal("85.0"))
        result = _get_user_koerpergewicht(user)
        assert result == 85.0

    def test_fallback_80kg_ohne_eintraege(self, user):
        result = _get_user_koerpergewicht(user)
        assert result == 80.0

    def test_neuester_eintrag_wird_gewaehlt(self, user):
        """Wenn mehrere Einträge: neuester (höchste PK) gewinnt.

        datum ist auto_now_add → kann nicht explizit gesetzt werden.
        Stattdessen: nach Erstellung datum via update() backfill-en.
        """
        from datetime import date, timedelta

        from core.models import KoerperWerte

        alt = KoerperWerte.objects.create(user=user, gewicht=Decimal("70.0"), groesse_cm=175)
        neu = KoerperWerte.objects.create(user=user, gewicht=Decimal("90.0"), groesse_cm=175)

        # auto_now_add umgehen: datum per update() setzen
        KoerperWerte.objects.filter(pk=alt.pk).update(datum=date.today() - timedelta(days=10))
        KoerperWerte.objects.filter(pk=neu.pk).update(datum=date.today())

        result = _get_user_koerpergewicht(user)
        assert result == 90.0


# ---------------------------------------------------------------------------
# Phase 14.2: _get_koerpergewicht_for_date + _get_koerpergewicht_map
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetKoerpergewichtForDate:
    def test_gibt_gewicht_am_datum(self, user):
        from datetime import date

        from core.models import KoerperWerte

        kw = KoerperWerte.objects.create(user=user, gewicht=Decimal("90.0"), groesse_cm=175)
        KoerperWerte.objects.filter(pk=kw.pk).update(datum=date(2026, 1, 15))

        result = _get_koerpergewicht_for_date(user, date(2026, 1, 20))
        assert result == 90.0

    def test_waehlt_naechsten_eintrag_vor_datum(self, user):
        from datetime import date

        from core.models import KoerperWerte

        kw1 = KoerperWerte.objects.create(user=user, gewicht=Decimal("100.0"), groesse_cm=175)
        kw2 = KoerperWerte.objects.create(user=user, gewicht=Decimal("85.0"), groesse_cm=175)
        KoerperWerte.objects.filter(pk=kw1.pk).update(datum=date(2026, 1, 1))
        KoerperWerte.objects.filter(pk=kw2.pk).update(datum=date(2026, 3, 1))

        # Datum zwischen beiden → der ältere Eintrag (100 kg)
        result = _get_koerpergewicht_for_date(user, date(2026, 2, 15))
        assert result == 100.0

        # Datum nach beiden → der neuere Eintrag (85 kg)
        result = _get_koerpergewicht_for_date(user, date(2026, 3, 15))
        assert result == 85.0

    def test_fallback_aktuellstes_wenn_kein_eintrag_vor_datum(self, user):
        from datetime import date

        from core.models import KoerperWerte

        kw = KoerperWerte.objects.create(user=user, gewicht=Decimal("90.0"), groesse_cm=175)
        KoerperWerte.objects.filter(pk=kw.pk).update(datum=date(2026, 6, 1))

        # Datum vor dem einzigen Eintrag → Fallback auf aktuellstes Gewicht
        result = _get_koerpergewicht_for_date(user, date(2026, 1, 1))
        assert result == 90.0

    def test_fallback_80kg_ohne_eintraege(self, user):
        from datetime import date

        result = _get_koerpergewicht_for_date(user, date(2026, 1, 1))
        assert result == 80.0


@pytest.mark.django_db
class TestGetKoerpergewichtMap:
    def test_batch_lookup_korrekt(self, user):
        from datetime import date

        from core.models import KoerperWerte

        kw1 = KoerperWerte.objects.create(user=user, gewicht=Decimal("100.0"), groesse_cm=175)
        kw2 = KoerperWerte.objects.create(user=user, gewicht=Decimal("85.0"), groesse_cm=175)
        KoerperWerte.objects.filter(pk=kw1.pk).update(datum=date(2026, 1, 1))
        KoerperWerte.objects.filter(pk=kw2.pk).update(datum=date(2026, 3, 1))

        dates = [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)]
        result = _get_koerpergewicht_map(user, dates)

        assert result[date(2026, 1, 15)] == 100.0  # Nach kw1, vor kw2
        assert result[date(2026, 2, 15)] == 100.0  # Immer noch kw1
        assert result[date(2026, 3, 15)] == 85.0  # Nach kw2

    def test_leere_dates_gibt_leeres_dict(self, user):
        result = _get_koerpergewicht_map(user, [])
        assert result == {}

    def test_ohne_eintraege_fallback_80(self, user):
        from datetime import date

        result = _get_koerpergewicht_map(user, [date(2026, 1, 1)])
        assert result[date(2026, 1, 1)] == 80.0


# ---------------------------------------------------------------------------
# _compute_1rm_and_weight – GESAMT
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompute1rmGesamt:
    def test_epley_formel_korrekt(self, user, uebung_gesamt):
        """100kg × 10 Wdh → 1RM = 100 × (1 + 10/30) = 133.33"""
        satz = MagicMock()
        satz.gewicht = 100.0
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_gesamt, 80.0)
        assert eff_weight == 100.0
        assert abs(one_rm - 133.33) < 0.1

    def test_gewicht_null_ergibt_null_1rm(self, user, uebung_gesamt):
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_gesamt, 80.0)
        assert one_rm == 0.0
        assert eff_weight == 0.0


# ---------------------------------------------------------------------------
# _compute_1rm_and_weight – PRO_SEITE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompute1rmProSeite:
    def test_pro_seite_verdoppelt_gewicht(self, uebung_pro_seite):
        """20kg KH je Seite → 40kg effektiv"""
        satz = MagicMock()
        satz.gewicht = 20.0
        satz.wiederholungen = 12
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_pro_seite, 80.0)
        assert eff_weight == 40.0
        assert abs(one_rm - 40.0 * (1 + 12 / 30)) < 0.01

    def test_pro_seite_ignoriert_koerpergewicht(self, uebung_pro_seite):
        """koerpergewicht_parameter hat keinen Einfluss bei PRO_SEITE"""
        satz = MagicMock()
        satz.gewicht = 20.0
        satz.wiederholungen = 10
        _, eff_60 = _compute_1rm_and_weight(satz, uebung_pro_seite, 60.0)
        _, eff_100 = _compute_1rm_and_weight(satz, uebung_pro_seite, 100.0)
        assert eff_60 == eff_100 == 40.0


# ---------------------------------------------------------------------------
# _compute_1rm_and_weight – ZEIT
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompute1rmZeit:
    def test_zeit_gibt_sekunden_als_1rm(self, uebung_zeit):
        """Plank 60s → 1RM = 60 (Wiederholungen = Sekunden)"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 60
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_zeit, 80.0)
        assert one_rm == 60
        assert eff_weight == 0.0


# ---------------------------------------------------------------------------
# _compute_1rm_and_weight – KOERPERGEWICHT
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompute1rmKoerpergewicht:
    def test_dips_faktor_70_prozent(self, uebung_dips):
        """80kg User, Faktor 0.70, kein Zusatz → effektiv 56kg"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_dips, 80.0)
        assert eff_weight == pytest.approx(56.0, abs=0.01)
        assert one_rm == pytest.approx(56.0 * (1 + 10 / 30), abs=0.01)

    def test_dips_mit_zusatzgewicht(self, uebung_dips):
        """80kg User, Faktor 0.70, +20kg Zusatz → effektiv 76kg"""
        satz = MagicMock()
        satz.gewicht = 20.0
        satz.wiederholungen = 8
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_dips, 80.0)
        assert eff_weight == pytest.approx(76.0, abs=0.01)

    def test_crunch_faktor_30_prozent(self, uebung_crunch):
        """80kg User, Faktor 0.30 → effektiv 24kg"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 15
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_crunch, 80.0)
        assert eff_weight == pytest.approx(24.0, abs=0.01)

    def test_user_koerpergewicht_beeinflusst_1rm(self, uebung_dips):
        """Schwererer User → höheres effektives Gewicht"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 10
        _, eff_80 = _compute_1rm_and_weight(satz, uebung_dips, 80.0)
        _, eff_100 = _compute_1rm_and_weight(satz, uebung_dips, 100.0)
        assert eff_100 > eff_80
        assert eff_80 == pytest.approx(56.0, abs=0.01)
        assert eff_100 == pytest.approx(70.0, abs=0.01)

    def test_faktor_null_ergibt_null(self, uebung_zeit):
        """Plank (Faktor 0.0) → effektiv 0kg, egal wie schwer der User"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 60
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_zeit, 80.0)
        assert eff_weight == 0.0


# ---------------------------------------------------------------------------
# show_reps_chart Logik (via exercise_stats View)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShowRepsChart:
    def test_reine_kg_uebung_zeigt_wdh_chart(self, user, uebung_dips):
        """Nur Sätze ohne Zusatzgewicht → show_reps_chart=True"""
        from core.models import Satz

        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung_dips, gewicht=Decimal("0"), wiederholungen=10)
        SatzFactory(einheit=training, uebung=uebung_dips, gewicht=Decimal("0"), wiederholungen=12)

        saetze = Satz.objects.filter(einheit__user=user, uebung=uebung_dips, ist_aufwaermsatz=False)
        hat_zusatzgewicht = saetze.filter(gewicht__gt=0).exists()
        assert not hat_zusatzgewicht

    def test_kg_uebung_mit_zusatz_kein_wdh_chart(self, user, uebung_dips):
        """Ein Satz mit Zusatzgewicht → hat_zusatzgewicht=True → show_reps_chart=False"""
        from core.models import Satz

        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung_dips, gewicht=Decimal("0"), wiederholungen=10)
        SatzFactory(einheit=training, uebung=uebung_dips, gewicht=Decimal("10"), wiederholungen=8)

        saetze = Satz.objects.filter(einheit__user=user, uebung=uebung_dips, ist_aufwaermsatz=False)
        hat_zusatzgewicht = saetze.filter(gewicht__gt=0).exists()
        assert hat_zusatzgewicht

    def test_gesamt_uebung_nie_wdh_chart(self, user, uebung_gesamt):
        """GESAMT-Übung: is_kg_uebung=False → show_reps_chart immer False"""
        assert uebung_gesamt.gewichts_typ != "KOERPERGEWICHT"


# ---------------------------------------------------------------------------
# _determine_empfehlung_hint – KG-Übungen
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmpfehlungHintKoerpergewicht:
    def _make_satz(self, gewicht, wdh, rpe=None):
        satz = MagicMock()
        satz.gewicht = float(gewicht)
        satz.wiederholungen = wdh
        satz.rpe = rpe
        return satz

    def test_kg_ohne_zusatz_empfiehlt_wdh_steigerung(self):
        """KG-Übung, gewicht=0 → Wdh-Steigerung statt +2.5kg"""
        satz = self._make_satz(0, 8, rpe=None)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=True)
        assert ew == 0.0
        assert ewdh == 9  # +1 Wdh
        assert "+2.5kg" not in hint
        assert "Wdh" in hint or "wdh" in hint.lower() or "Stufe" in hint or "+" in hint

    def test_kg_ohne_zusatz_niedriger_rpe_mehr_wdh(self):
        """RPE < 7 bei KG-Übung → +2 Wdh"""
        satz = self._make_satz(0, 8, rpe=6.5)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=True)
        assert ew == 0.0
        assert ewdh == 10  # +2 Wdh

    def test_kg_ohne_zusatz_max_wdh_erreicht(self):
        """Ziel-Max erreicht bei KG-Übung → Hinweis auf nächste Stufe"""
        satz = self._make_satz(0, 12, rpe=None)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=True)
        assert ew == 0.0
        assert "Zusatzgewicht" in hint or "nächste" in hint or "Stufe" in hint

    def test_kg_mit_zusatz_empfiehlt_kg_steigerung(self):
        """KG-Übung MIT Zusatzgewicht → normale +2.5kg Logik"""
        satz = self._make_satz(10.0, 12, rpe=None)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=True)
        assert ew == 12.5  # +2.5kg
        assert "+2.5kg" in hint

    def test_gesamt_uebung_unveraendert(self):
        """GESAMT-Übung: is_kg_uebung=False → klassische Logik unberührt"""
        satz = self._make_satz(80.0, 12, rpe=None)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=False)
        assert ew == 82.5  # +2.5kg

    def test_gesamt_hoher_rpe_mehr_wdh(self):
        """RPE >= 9 bei GESAMT → mehr Wdh statt mehr Gewicht"""
        satz = self._make_satz(80.0, 8, rpe=9.5)
        ew, ewdh, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=False)
        assert ew == 80.0  # kein Gewicht-Anstieg
        assert "Wdh" in hint or "mehr" in hint.lower()


# ---------------------------------------------------------------------------
# Phase 14.1: Gegengewicht (GEGEN) Modus
# ---------------------------------------------------------------------------


@pytest.fixture
def uebung_assistierte_dips():
    return UebungFactory(
        bezeichnung="Assistierte Dips",
        gewichts_typ="KOERPERGEWICHT",
        koerpergewicht_faktor=0.70,
        gewichts_richtung="GEGEN",
    )


@pytest.mark.django_db
class TestGegengewicht:
    def test_gegen_subtrahiert_gewicht(self, uebung_assistierte_dips):
        """80kg User, Faktor 0.70, 20kg Gegengewicht → 56 - 20 = 36 kg effektiv"""
        satz = MagicMock()
        satz.gewicht = 20.0
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_assistierte_dips, 80.0)
        assert eff_weight == pytest.approx(36.0, abs=0.01)
        assert one_rm == pytest.approx(36.0 * (1 + 10 / 30), abs=0.01)

    def test_gegen_null_gegengewicht_gleich_normal(self, uebung_assistierte_dips):
        """Kein Gegengewicht (0kg) → gleich wie normaler KG-Faktor"""
        satz = MagicMock()
        satz.gewicht = 0.0
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_assistierte_dips, 80.0)
        assert eff_weight == pytest.approx(56.0, abs=0.01)

    def test_gegen_mehr_als_koerpergewicht_wird_null(self, uebung_assistierte_dips):
        """Gegengewicht > Basis-Last → effektives Gewicht = 0 (nicht negativ)"""
        satz = MagicMock()
        satz.gewicht = 70.0  # Mehr als 56 kg Basis
        satz.wiederholungen = 10
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_assistierte_dips, 80.0)
        assert eff_weight == 0.0
        assert one_rm == 0.0

    def test_zusatz_addiert_weiterhin(self, uebung_dips):
        """Normaler ZUSATZ-Modus bleibt unverändert"""
        satz = MagicMock()
        satz.gewicht = 20.0
        satz.wiederholungen = 8
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_dips, 80.0)
        assert eff_weight == pytest.approx(76.0, abs=0.01)

    def test_gegen_mit_schwerem_user(self, uebung_assistierte_dips):
        """100kg User, 30kg Gegengewicht → 70 - 30 = 40 kg effektiv"""
        satz = MagicMock()
        satz.gewicht = 30.0
        satz.wiederholungen = 8
        one_rm, eff_weight = _compute_1rm_and_weight(satz, uebung_assistierte_dips, 100.0)
        assert eff_weight == pytest.approx(40.0, abs=0.01)


# ---------------------------------------------------------------------------
# Phase 14.3: PR-Detection für Körpergewicht-Übungen
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPrDetectionKoerpergewicht:
    def test_erster_satz_kg_uebung_ist_pr(self, user, uebung_dips):
        """Erster Satz einer KG-Übung → PR 'first'."""
        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        training = TrainingseinheitFactory(user=user)
        satz = SatzFactory(
            einheit=training,
            uebung=uebung_dips,
            gewicht=Decimal("0"),
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        from core.views.training_session import _check_pr

        result = _check_pr(user, uebung_dips, satz, 0.0, 10)
        assert result is not None
        assert "Rekord" in result
        satz.refresh_from_db()
        assert satz.is_pr is True
        assert satz.pr_type == "first"

    def test_kg_uebung_pr_mit_mehr_wdh(self, user, uebung_dips):
        """Mehr Wdh bei gleicher KG-Übung → höherer 1RM → PR."""
        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        t1 = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=t1,
            uebung=uebung_dips,
            gewicht=Decimal("0"),
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        t2 = TrainingseinheitFactory(user=user)
        satz2 = SatzFactory(
            einheit=t2,
            uebung=uebung_dips,
            gewicht=Decimal("0"),
            wiederholungen=12,
            ist_aufwaermsatz=False,
        )
        from core.views.training_session import _check_pr

        result = _check_pr(user, uebung_dips, satz2, 0.0, 12)
        assert result is not None
        assert "NEUER REKORD" in result
        satz2.refresh_from_db()
        assert satz2.is_pr is True
        assert satz2.pr_type == "best_1rm"

    def test_kg_uebung_kein_pr_bei_weniger_wdh(self, user, uebung_dips):
        """Weniger Wdh → kein PR."""
        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        t1 = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=t1,
            uebung=uebung_dips,
            gewicht=Decimal("0"),
            wiederholungen=12,
            ist_aufwaermsatz=False,
        )
        t2 = TrainingseinheitFactory(user=user)
        satz2 = SatzFactory(
            einheit=t2,
            uebung=uebung_dips,
            gewicht=Decimal("0"),
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        from core.views.training_session import _check_pr

        result = _check_pr(user, uebung_dips, satz2, 0.0, 8)
        assert result is None


# ---------------------------------------------------------------------------
# Phase 14.3: Tonnage für Körpergewicht-Übungen
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTonnageKoerpergewicht:
    def test_kg_uebung_hat_tonnage(self, user, uebung_dips):
        """Dips ohne Zusatzgewicht sollen Tonnage > 0 haben."""
        from datetime import date

        from core.views.training_stats import _calc_muscle_balance

        KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        # Mock-Satz mit echtem Uebung-Objekt
        satz = MagicMock()
        satz.gewicht = Decimal("0")
        satz.wiederholungen = 10
        satz.rpe = Decimal("7.0")
        satz.uebung = uebung_dips
        satz.uebung.get_muskelgruppe_display = uebung_dips.get_muskelgruppe_display
        # Mock-Training
        training = MagicMock()
        training.datum = date.today()
        training.ist_deload = False
        training.arbeitssaetze_list = [satz]

        sorted_items, _, _, _ = _calc_muscle_balance([training], user)
        total_tonnage = sum(item[1]["tonnage"] for item in sorted_items)
        # 80 * 0.70 = 56 kg effektiv, * 10 Wdh = 560 kg Tonnage
        assert total_tonnage == pytest.approx(560.0, abs=1.0)

    def test_gesamt_uebung_tonnage_unveraendert(self, user):
        """GESAMT-Übungen berechnen Tonnage wie bisher."""
        from datetime import date

        from core.views.training_stats import _calc_muscle_balance

        uebung = UebungFactory(bezeichnung="Bankdrücken", gewichts_typ="GESAMT")
        satz = MagicMock()
        satz.gewicht = Decimal("80")
        satz.wiederholungen = 10
        satz.rpe = Decimal("7.0")
        satz.uebung = uebung
        satz.uebung.get_muskelgruppe_display = uebung.get_muskelgruppe_display
        training = MagicMock()
        training.datum = date.today()
        training.ist_deload = False
        training.arbeitssaetze_list = [satz]

        sorted_items, _, _, _ = _calc_muscle_balance([training], user)
        total_tonnage = sum(item[1]["tonnage"] for item in sorted_items)
        assert total_tonnage == pytest.approx(800.0, abs=0.1)  # 80 * 10
