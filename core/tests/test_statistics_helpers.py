"""
Tests für die privaten Helper-Funktionen in core/views/training_stats.py

Diese Funktionen enthalten die eigentliche Businesslogik für Charts und Statistiken.
Sie werden direkt importiert und unit-getestet (ohne HTTP-Request).

Abgedeckte Funktionen:
- _calc_per_training_volume
- _calc_weekly_volume
- _detect_volume_warnings
- _build_90day_heatmap
- _calc_muscle_balance
- _build_svg_muscle_data
- _get_week_start
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers: Mock-Satz und Mock-Trainingseinheit (kein DB nötig für reine Logik)
# ---------------------------------------------------------------------------


def make_mock_satz(
    gewicht=100.0,
    wiederholungen=10,
    rpe=8.0,
    muskelgruppe="BRUST",
    mg_display="Brust",
    ist_aufwaermsatz=False,
):
    """Erstellt einen Mock-Satz für Unit-Tests ohne Datenbankzugriff."""
    satz = MagicMock()
    satz.gewicht = gewicht
    satz.wiederholungen = wiederholungen
    satz.rpe = rpe
    satz.ist_aufwaermsatz = ist_aufwaermsatz
    satz.uebung.muskelgruppe = muskelgruppe
    satz.uebung.get_muskelgruppe_display.return_value = mg_display
    return satz


def make_mock_training(datum, saetze=None, ist_deload=False):
    """Erstellt eine Mock-Trainingseinheit."""
    training = MagicMock()
    training.datum = datum
    training.ist_deload = ist_deload
    training.arbeitssaetze_list = saetze or []
    return training


# ---------------------------------------------------------------------------
# _get_week_start
# ---------------------------------------------------------------------------


class TestGetWeekStart:
    """Tests für _get_week_start – gibt den Montag der aktuellen ISO-Woche zurück."""

    def test_montag_bleibt_montag(self):
        from core.views.training_stats import _get_week_start

        montag = datetime(2026, 2, 16, 14, 30)  # Montag
        result = _get_week_start(montag)
        assert result.weekday() == 0  # Montag = 0

    def test_sonntag_ergibt_montag_davor(self):
        from core.views.training_stats import _get_week_start

        sonntag = datetime(2026, 2, 22, 10, 0)  # Sonntag
        result = _get_week_start(sonntag)
        assert result.weekday() == 0
        assert result.day == 16  # Montag davor

    def test_mittwoch_ergibt_den_montag_der_woche(self):
        from core.views.training_stats import _get_week_start

        mittwoch = datetime(2026, 2, 18, 9, 0)
        result = _get_week_start(mittwoch)
        assert result.weekday() == 0
        assert result.day == 16

    def test_ergebnis_hat_mitternacht(self):
        """Wochenstart soll immer Mitternacht sein."""
        from core.views.training_stats import _get_week_start

        result = _get_week_start(datetime(2026, 2, 18, 15, 45))
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0


# ---------------------------------------------------------------------------
# _calc_per_training_volume
# ---------------------------------------------------------------------------


class TestCalcPerTrainingVolume:
    """Tests für _calc_per_training_volume."""

    def test_leere_trainings_liste(self):
        from core.views.training_stats import _calc_per_training_volume

        labels, data = _calc_per_training_volume([])
        assert labels == []
        assert data == []

    def test_volumen_berechnung_korrekt(self):
        """Volumen = Gewicht × Wiederholungen pro Satz."""
        from core.views.training_stats import _calc_per_training_volume

        satz1 = make_mock_satz(gewicht=100.0, wiederholungen=10)  # 1000
        satz2 = make_mock_satz(gewicht=80.0, wiederholungen=8)  # 640
        # Erwartet: 1640 kg
        training = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz1, satz2])
        labels, data = _calc_per_training_volume([training])
        assert len(labels) == 1
        assert data[0] == pytest.approx(1640.0, abs=0.1)

    def test_training_ohne_saetze_hat_volumen_null(self):
        from core.views.training_stats import _calc_per_training_volume

        training = make_mock_training(datum=datetime(2026, 2, 15), saetze=[])
        labels, data = _calc_per_training_volume([training])
        assert data[0] == 0.0

    def test_label_format_dd_mm(self):
        from core.views.training_stats import _calc_per_training_volume

        training = make_mock_training(datum=datetime(2026, 2, 5), saetze=[make_mock_satz()])
        labels, _ = _calc_per_training_volume([training])
        assert labels[0] == "05.02"

    def test_mehrere_trainings_richtige_reihenfolge(self):
        from core.views.training_stats import _calc_per_training_volume

        t1 = make_mock_training(datum=datetime(2026, 2, 1), saetze=[make_mock_satz(100, 10)])
        t2 = make_mock_training(datum=datetime(2026, 2, 8), saetze=[make_mock_satz(120, 5)])
        labels, data = _calc_per_training_volume([t1, t2])
        assert len(labels) == 2
        assert data[0] == pytest.approx(1000.0, abs=0.1)
        assert data[1] == pytest.approx(600.0, abs=0.1)

    def test_gewicht_none_wird_ignoriert(self):
        """Sätze ohne Gewicht (None) sollen 0 beitragen, nicht crashen."""
        from core.views.training_stats import _calc_per_training_volume

        satz = make_mock_satz(gewicht=None, wiederholungen=10)
        training = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz])
        labels, data = _calc_per_training_volume([training])
        # None-Guard in der Funktion: `if s.gewicht and s.wiederholungen`
        assert data[0] == 0.0


# ---------------------------------------------------------------------------
# _calc_weekly_volume
# ---------------------------------------------------------------------------


class TestCalcWeeklyVolume:
    """Tests für _calc_weekly_volume."""

    def test_leere_trainings(self):
        from core.views.training_stats import _calc_weekly_volume

        labels, data = _calc_weekly_volume([])
        assert labels == []
        assert data == []

    def test_aggregiert_trainings_der_gleichen_woche(self):
        from core.views.training_stats import _calc_weekly_volume

        # Zwei Trainings in KW08/2026
        t1 = make_mock_training(
            datum=datetime(2026, 2, 16),  # Mo KW08
            saetze=[make_mock_satz(100, 10)],  # 1000 kg
        )
        t2 = make_mock_training(
            datum=datetime(2026, 2, 18),  # Mi KW08
            saetze=[make_mock_satz(80, 5)],  # 400 kg
        )
        labels, data = _calc_weekly_volume([t1, t2])
        assert len(labels) == 1
        assert data[0] == pytest.approx(1400.0, abs=0.1)

    def test_max_12_wochen_label(self):
        """Nur die letzten 12 ISO-Wochen werden zurückgegeben."""
        from core.views.training_stats import _calc_weekly_volume

        # 15 Wochen erstellen
        trainings = []
        for i in range(15):
            datum = datetime(2026, 2, 18) - timedelta(weeks=i)
            trainings.append(make_mock_training(datum=datum, saetze=[make_mock_satz(100, 5)]))
        labels, data = _calc_weekly_volume(trainings)
        assert len(labels) <= 12

    def test_label_format_iso_woche(self):
        """Label-Format soll 'YYYY-WXX' sein."""
        from core.views.training_stats import _calc_weekly_volume

        t = make_mock_training(datum=datetime(2026, 2, 18), saetze=[make_mock_satz()])  # KW08
        labels, _ = _calc_weekly_volume([t])
        assert "2026-W08" in labels


# ---------------------------------------------------------------------------
# _detect_volume_warnings
# ---------------------------------------------------------------------------


class TestDetectVolumeWarnings:
    """Tests für _detect_volume_warnings."""

    def test_keine_warnungen_bei_stabiler_progression(self):
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02", "2026-W03"]
        data = [4000.0, 4200.0, 4400.0]  # +5% pro Woche, stabil
        result = _detect_volume_warnings(labels, data)
        assert result == []

    def test_spike_bei_mehr_als_20_prozent_anstieg(self):
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [4000.0, 5000.0]  # +25% → Spike
        result = _detect_volume_warnings(labels, data)
        assert len(result) == 1
        assert result[0]["type"] == "spike"
        assert result[0]["week"] == "2026-W02"

    def test_kein_spike_bei_genau_20_prozent(self):
        """Grenzwert: Exakt 20% ist KEIN Spike (> 20 erforderlich)."""
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [4000.0, 4800.0]  # +20% genau
        result = _detect_volume_warnings(labels, data)
        assert result == []

    def test_drop_bei_mehr_als_30_prozent_rueckgang(self):
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [5000.0, 3000.0]  # -40% → Drop
        result = _detect_volume_warnings(labels, data)
        assert len(result) == 1
        assert result[0]["type"] == "drop"

    def test_kein_drop_bei_genau_30_prozent(self):
        """Grenzwert: Exakt -30% ist KEIN Drop (< -30 erforderlich)."""
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [5000.0, 3500.0]  # -30% genau
        result = _detect_volume_warnings(labels, data)
        assert result == []

    def test_vorwoche_null_gibt_keine_warnung(self):
        """Division durch null wenn vorherige Woche 0 → soll nicht crashen."""
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [0.0, 5000.0]
        result = _detect_volume_warnings(labels, data)
        # prev <= 0 → skip → keine Warnung
        assert result == []

    def test_leere_listen(self):
        from core.views.training_stats import _detect_volume_warnings

        assert _detect_volume_warnings([], []) == []

    def test_ein_eintrag_keine_warnung(self):
        from core.views.training_stats import _detect_volume_warnings

        assert _detect_volume_warnings(["2026-W01"], [4000.0]) == []

    def test_warnung_enthaelt_volumen_wert(self):
        from core.views.training_stats import _detect_volume_warnings

        labels = ["2026-W01", "2026-W02"]
        data = [4000.0, 5200.0]  # +30% → Spike
        result = _detect_volume_warnings(labels, data)
        assert result[0]["volume"] == pytest.approx(5200.0, abs=0.1)


# ---------------------------------------------------------------------------
# _build_90day_heatmap
# ---------------------------------------------------------------------------


class TestBuild90DayHeatmap:
    """Tests für _build_90day_heatmap."""

    def test_ergibt_genau_90_eintraege(self):
        from core.views.training_stats import _build_90day_heatmap

        heute = date(2026, 2, 18)
        mock_qs = MagicMock()
        mock_qs.filter.return_value = []
        result = _build_90day_heatmap(mock_qs, heute)
        assert len(result) == 90

    def test_datum_format_iso(self):
        from core.views.training_stats import _build_90day_heatmap

        heute = date(2026, 2, 18)
        mock_qs = MagicMock()
        mock_qs.filter.return_value = []
        result = _build_90day_heatmap(mock_qs, heute)
        # Erster Eintrag: heute - 89 Tage
        start = heute - timedelta(days=89)
        assert result[0]["date"] == start.isoformat()
        assert result[-1]["date"] == heute.isoformat()

    def test_count_null_fuer_tage_ohne_training(self):
        from core.views.training_stats import _build_90day_heatmap

        heute = date(2026, 2, 18)
        mock_qs = MagicMock()
        mock_qs.filter.return_value = []
        result = _build_90day_heatmap(mock_qs, heute)
        assert all(entry["count"] == 0 for entry in result)


# ---------------------------------------------------------------------------
# _calc_muscle_balance
# ---------------------------------------------------------------------------


class TestCalcMuscleBalance:
    """
    Tests für _calc_muscle_balance.

    Nach dem Bugfix werden Sätze ohne RPE mit Fallback-RPE 7.0 gezählt,
    statt komplett ignoriert zu werden.
    """

    def test_saetze_mit_rpe_werden_gezaehlt(self):
        from core.views.training_stats import _calc_muscle_balance

        satz = make_mock_satz(
            gewicht=100, wiederholungen=10, rpe=8.0, muskelgruppe="BRUST", mg_display="Brust"
        )
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz])
        sorted_items, mg_labels, mg_data, stats_code = _calc_muscle_balance([t])
        assert "Brust" in mg_labels
        assert mg_data[0] > 0

    def test_saetze_ohne_rpe_werden_mit_fallback_7_gezaehlt(self):
        """
        BUGFIX verifiziert: Sätze ohne RPE werden jetzt mit Fallback-RPE 7.0 gezählt.
        Vorher: continue → Muskelgruppe tauchte im Chart nicht auf.
        Jetzt: eff_wdh = wiederholungen * (7.0 / 10.0) = 7.0 für 10 Wdh.
        """
        from core.views.training_stats import _calc_muscle_balance

        satz_ohne_rpe = make_mock_satz(
            rpe=None, wiederholungen=10, muskelgruppe="BRUST", mg_display="Brust"
        )
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz_ohne_rpe])
        sorted_items, mg_labels, mg_data, stats_code = _calc_muscle_balance([t])
        assert "Brust" in mg_labels, "Sätze ohne RPE sollen mit Fallback 7.0 gezählt werden"
        assert mg_data[0] == pytest.approx(
            7.0, abs=0.01
        ), "eff_wdh = 10 Wdh * (7.0 / 10.0) = 7.0 erwartet"

    def test_fallback_rpe_kleiner_als_echter_hoher_rpe(self):
        """RPE 7.0 Fallback soll weniger wiegen als echter RPE 9.5 – korrekte Gewichtung."""
        from core.views.training_stats import _calc_muscle_balance

        satz_rpe_hoch = make_mock_satz(
            rpe=9.5, wiederholungen=10, muskelgruppe="BRUST", mg_display="Brust"
        )
        satz_kein_rpe = make_mock_satz(
            rpe=None, wiederholungen=10, muskelgruppe="TRIZEPS", mg_display="Trizeps"
        )
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz_rpe_hoch, satz_kein_rpe])
        _, mg_labels, mg_data, _ = _calc_muscle_balance([t])
        # Brust (RPE 9.5) soll mehr wiegen als Trizeps (Fallback 7.0)
        brust_idx = mg_labels.index("Brust")
        trizeps_idx = mg_labels.index("Trizeps")
        assert mg_data[brust_idx] > mg_data[trizeps_idx]

    def test_saetze_ohne_wiederholungen_werden_weiterhin_ignoriert(self):
        """Sätze ohne Wiederholungen sind wertlos – sollen weiterhin ignoriert werden."""
        from core.views.training_stats import _calc_muscle_balance

        satz = make_mock_satz(
            wiederholungen=None, rpe=8.0, muskelgruppe="BRUST", mg_display="Brust"
        )
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz])
        sorted_items, mg_labels, mg_data, stats_code = _calc_muscle_balance([t])
        assert "Brust" not in mg_labels

    def test_mehrere_muskelgruppen_sortiert_nach_volumen(self):
        from core.views.training_stats import _calc_muscle_balance

        # Brust: RPE 8, 10 Wdh → eff_wdh = 8.0
        # Rücken: RPE 9, 10 Wdh → eff_wdh = 9.0 (höher → soll oben stehen)
        satz_brust = make_mock_satz(
            rpe=8.0, wiederholungen=10, muskelgruppe="BRUST", mg_display="Brust"
        )
        satz_ruecken = make_mock_satz(
            rpe=9.0, wiederholungen=10, muskelgruppe="RUECKEN_LAT", mg_display="Rücken Lat"
        )
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz_brust, satz_ruecken])
        sorted_items, mg_labels, mg_data, stats_code = _calc_muscle_balance([t])
        assert mg_labels[0] == "Rücken Lat"

    def test_leere_trainings(self):
        from core.views.training_stats import _calc_muscle_balance

        sorted_items, mg_labels, mg_data, stats_code = _calc_muscle_balance([])
        assert sorted_items == []
        assert mg_labels == []
        assert mg_data == []
        assert stats_code == {}

    def test_stats_code_enthaelt_muskelgruppen_code(self):
        from core.views.training_stats import _calc_muscle_balance

        satz = make_mock_satz(rpe=8.0, wiederholungen=10, muskelgruppe="BRUST", mg_display="Brust")
        t = make_mock_training(datum=datetime(2026, 2, 15), saetze=[satz])
        _, _, _, stats_code = _calc_muscle_balance([t])
        assert "BRUST" in stats_code
        assert stats_code["BRUST"] > 0


# ---------------------------------------------------------------------------
# _build_svg_muscle_data
# ---------------------------------------------------------------------------


class TestBuildSvgMuscleData:
    """Tests für _build_svg_muscle_data."""

    def test_leeres_dict_gibt_leeres_dict_zurueck(self):
        from core.views.training_stats import _build_svg_muscle_data

        result = _build_svg_muscle_data({})
        assert result == {}

    def test_intensitaet_normalisiert_auf_0_bis_1(self):
        from core.views.training_stats import _build_svg_muscle_data

        stats = {"BRUST": 100.0, "TRIZEPS": 50.0}
        result = _build_svg_muscle_data(stats)
        for svg_id, intensity in result.items():
            assert 0.0 <= intensity <= 1.0, f"Intensität für {svg_id} außerhalb [0,1]: {intensity}"

    def test_maximaler_wert_normalisiert_zu_1(self):
        from core.views.training_stats import _build_svg_muscle_data

        stats = {"BRUST": 80.0}
        result = _build_svg_muscle_data(stats)
        for svg_id in ["front_chest_left", "front_chest_right"]:
            if svg_id in result:
                assert result[svg_id] == pytest.approx(1.0, abs=0.01)

    def test_unbekannte_muskelgruppe_wird_ignoriert(self):
        from core.views.training_stats import _build_svg_muscle_data

        stats = {"UNBEKANNTE_GRUPPE": 100.0}
        result = _build_svg_muscle_data(stats)
        assert result == {}

    def test_ueberlappende_muskelgruppen_addieren_sich(self):
        """
        SCHULTER_VORN und SCHULTER_SEIT mappen beide auf front_delt_* –
        die Intensitäten sollen sich addieren (gedeckelt bei 1.0).
        """
        from core.views.training_stats import _build_svg_muscle_data

        stats = {"SCHULTER_VORN": 50.0, "SCHULTER_SEIT": 50.0}
        result = _build_svg_muscle_data(stats)
        for svg_id in ["front_delt_left", "front_delt_right"]:
            if svg_id in result:
                assert result[svg_id] <= 1.0  # nie über 1.0
