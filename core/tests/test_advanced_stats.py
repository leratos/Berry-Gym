"""
Tests für core/utils/advanced_stats.py

Abdeckung:
- calculate_plateau_analysis()
- calculate_consistency_metrics()
- calculate_fatigue_index()
- calculate_1rm_standards()
- calculate_rpe_quality_analysis()
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import Equipment, Plan, Satz, Trainingseinheit, Uebung
from core.utils.advanced_stats import (
    calculate_1rm_standards,
    calculate_consistency_metrics,
    calculate_fatigue_index,
    calculate_plateau_analysis,
    calculate_rpe_quality_analysis,
)


class StatsTestBase(TestCase):
    """Gemeinsames Setup: User, Plan, Übung, Equipment."""

    def setUp(self):
        self.user = User.objects.create_user(username="stats_user", password="pass")
        self.equipment = Equipment.objects.create(name="KOERPER")
        self.uebung = Uebung.objects.create(
            bezeichnung="Kniebeuge",
            muskelgruppe="BEINE",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
            standard_beginner=60,
            standard_intermediate=100,
            standard_advanced=140,
            standard_elite=180,
        )
        self.uebung.equipment.add(self.equipment)
        self.plan = Plan.objects.create(name="Test Plan", user=self.user)

    def _make_session(self, days_ago=0, dauer=45):
        datum = timezone.now() - timedelta(days=days_ago)
        session = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, dauer_minuten=dauer
        )
        # Manuelle Datumskorrektur (auto_now_add überschreibt)
        Trainingseinheit.objects.filter(pk=session.pk).update(datum=datum)
        return Trainingseinheit.objects.get(pk=session.pk)

    def _add_satz(self, session, gewicht=80, wiederholungen=8, rpe=None, warmup=False):
        return Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=gewicht,
            wiederholungen=wiederholungen,
            rpe=rpe,
            ist_aufwaermsatz=warmup,
        )


# ──────────────────────────────────────────────────────────────────────────────
# calculate_rpe_quality_analysis
# ──────────────────────────────────────────────────────────────────────────────
class TestRpeQualityAnalysis(StatsTestBase):

    def _alle_saetze(self):
        return Satz.objects.filter(einheit__user=self.user)

    def test_kein_rpe_gibt_none(self):
        session = self._make_session()
        self._add_satz(session, rpe=None)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertIsNone(result)

    def test_nur_warmup_saetze_gibt_none(self):
        session = self._make_session()
        self._add_satz(session, rpe=5.0, warmup=True)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertIsNone(result)

    def test_optimale_rpe_bewertung(self):
        session = self._make_session()
        for _ in range(8):
            self._add_satz(session, rpe=7.5)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["optimal_intensity_rate"], 70)
        self.assertIn("bewertung", result)

    def test_junk_volume_bei_niedriger_rpe(self):
        session = self._make_session()
        for _ in range(10):
            self._add_satz(session, rpe=4.0)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertGreater(result["junk_volume_rate"], 50)

    def test_failure_rate_bei_rpe_10(self):
        session = self._make_session()
        for _ in range(10):
            self._add_satz(session, rpe=10.0)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertAlmostEqual(result["failure_rate"], 100.0)

    def test_verteilung_summe_unter_100(self):
        session = self._make_session()
        for rpe in [5.0, 7.0, 8.5, 10.0]:
            self._add_satz(session, rpe=rpe)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        total = sum(result["rpe_verteilung_prozent"].values())
        self.assertAlmostEqual(total, 100.0, delta=0.5)

    def test_empfehlungen_bei_schlechter_verteilung(self):
        session = self._make_session()
        for _ in range(10):
            self._add_satz(session, rpe=4.0)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertGreater(len(result["empfehlungen"]), 0)

    def test_gesamt_saetze_korrekt(self):
        session = self._make_session()
        for _ in range(5):
            self._add_satz(session, rpe=7.5)
        result = calculate_rpe_quality_analysis(self._alle_saetze())
        self.assertEqual(result["gesamt_saetze"], 5)


# ──────────────────────────────────────────────────────────────────────────────
# calculate_consistency_metrics
# ──────────────────────────────────────────────────────────────────────────────
class TestConsistencyMetrics(StatsTestBase):

    def _alle_trainings(self):
        return Trainingseinheit.objects.filter(user=self.user)

    def test_keine_trainings_gibt_none(self):
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertIsNone(result)

    def test_ein_training_gibt_ergebnis(self):
        self._make_session(days_ago=0)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertIsNotNone(result)
        self.assertIn("aktueller_streak", result)

    def test_adherence_nie_ueber_100(self):
        # Viele Trainings, auch mehrere pro Woche
        for i in range(20):
            self._make_session(days_ago=i)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertLessEqual(result["adherence_rate"], 100.0)

    def test_adherence_positiv(self):
        for i in range(7):
            self._make_session(days_ago=i * 7)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertGreater(result["adherence_rate"], 0)

    def test_streak_mit_luecke(self):
        # Aktuelle Woche trainiert, dann 3 Wochen Lücke, dann wieder
        self._make_session(days_ago=0)
        self._make_session(days_ago=28)
        result = calculate_consistency_metrics(self._alle_trainings())
        # Aktueller Streak = 1 (nur diese Woche), längster = mind. 1
        self.assertEqual(result["aktueller_streak"], 1)

    def test_avg_pause_korrekt(self):
        self._make_session(days_ago=0)
        self._make_session(days_ago=4)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertGreater(result["avg_pause_tage"], 0)

    def test_bewertung_vorhanden(self):
        self._make_session(days_ago=0)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertIn("bewertung", result)
        self.assertIn("bewertung_farbe", result)

    def test_laengster_streak_groesser_gleich_aktueller(self):
        for i in range(5):
            self._make_session(days_ago=i * 7)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertGreaterEqual(result["laengster_streak"], result["aktueller_streak"])

    def test_einzel_training_hat_null_pause(self):
        self._make_session(days_ago=0)
        result = calculate_consistency_metrics(self._alle_trainings())
        self.assertEqual(result["avg_pause_tage"], 0)


# ──────────────────────────────────────────────────────────────────────────────
# calculate_fatigue_index
# ──────────────────────────────────────────────────────────────────────────────
class TestFatigueIndex(StatsTestBase):

    def _get_rpe_saetze(self):
        return Satz.objects.filter(einheit__user=self.user, rpe__isnull=False)

    def _alle_trainings(self):
        return Trainingseinheit.objects.filter(user=self.user)

    def test_ohne_daten_fatigue_null(self):
        result = calculate_fatigue_index([], self._get_rpe_saetze(), self._alle_trainings())
        self.assertEqual(result["fatigue_index"], 0)
        self.assertFalse(result["deload_empfohlen"])

    def test_volumen_spike_erhoehe_fatigue(self):
        volume_data = [
            {"woche": "KW1", "volumen": 1000},
            {"woche": "KW2", "volumen": 1400},  # +40% → spike
        ]
        result = calculate_fatigue_index(
            volume_data, self._get_rpe_saetze(), self._alle_trainings()
        )
        self.assertTrue(result["volumen_spike"])
        self.assertGreater(result["fatigue_index"], 0)

    def test_kein_volumen_spike_bei_kleinem_anstieg(self):
        volume_data = [
            {"woche": "KW1", "volumen": 1000},
            {"woche": "KW2", "volumen": 1050},  # +5% → kein spike
        ]
        result = calculate_fatigue_index(
            volume_data, self._get_rpe_saetze(), self._alle_trainings()
        )
        self.assertFalse(result["volumen_spike"])

    def test_kein_volumen_spike_wenn_vorwoche_null(self):
        volume_data = [
            {"woche": "KW1", "volumen": 0},
            {"woche": "KW2", "volumen": 900},
        ]
        result = calculate_fatigue_index(
            volume_data, self._get_rpe_saetze(), self._alle_trainings()
        )
        self.assertFalse(result["volumen_spike"])

    def test_rpe_ohne_altes_vergleichsfenster_steigt_nicht(self):
        session = self._make_session(days_ago=0)
        for index in range(10):
            Satz.objects.create(
                einheit=session,
                uebung=self.uebung,
                satz_nr=index + 1,
                gewicht=80,
                wiederholungen=6,
                rpe=9.0,
                ist_aufwaermsatz=False,
            )

        result = calculate_fatigue_index([], self._get_rpe_saetze(), self._alle_trainings())

        self.assertFalse(result["rpe_steigend"])

    def test_deload_empfohlen_bei_hohem_fatigue(self):
        # Täglich trainieren in letzten 7 Tagen → hoher Fatigue
        for i in range(7):
            self._make_session(days_ago=i)
        volume_data = [
            {"woche": "KW1", "volumen": 1000},
            {"woche": "KW2", "volumen": 1400},
        ]
        result = calculate_fatigue_index(
            volume_data, self._get_rpe_saetze(), self._alle_trainings()
        )
        self.assertGreaterEqual(result["fatigue_index"], 50)
        self.assertTrue(result["deload_empfohlen"])

    def test_warnungen_sind_liste(self):
        result = calculate_fatigue_index([], self._get_rpe_saetze(), self._alle_trainings())
        self.assertIsInstance(result["warnungen"], list)

    def test_bewertung_und_empfehlung_vorhanden(self):
        result = calculate_fatigue_index([], self._get_rpe_saetze(), self._alle_trainings())
        self.assertIn("bewertung", result)
        self.assertIn("empfehlung", result)

    def test_naechste_deload_string(self):
        result = calculate_fatigue_index([], self._get_rpe_saetze(), self._alle_trainings())
        # Muss ein Datum-String sein (DD.MM.YYYY)
        self.assertRegex(result["naechste_deload"], r"\d{2}\.\d{2}\.\d{4}")


# ──────────────────────────────────────────────────────────────────────────────
# calculate_plateau_analysis
# ──────────────────────────────────────────────────────────────────────────────
class TestPlateauAnalysis(StatsTestBase):

    def _alle_saetze(self):
        return Satz.objects.filter(einheit__user=self.user)

    def _top_uebungen(self, muskelgruppe_display="Beine"):
        return [{"uebung__bezeichnung": "Kniebeuge", "muskelgruppe_display": muskelgruppe_display}]

    def test_zu_wenig_saetze_gibt_leer(self):
        # Nur 1 Satz → braucht mindestens 2
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(result, [])

    def test_mit_zwei_saetzen_gibt_eintrag(self):
        for days_ago in [30, 0]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(len(result), 1)

    def test_ergebnis_felder_vorhanden(self):
        for days_ago in [30, 0]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        eintrag = result[0]
        for key in ("uebung", "letzter_pr", "tage_seit_pr", "status", "status_label"):
            self.assertIn(key, eintrag)

    def test_uebung_name_korrekt(self):
        for days_ago in [30, 0]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(result[0]["uebung"], "Kniebeuge")

    def test_tage_seit_pr_nicht_negativ(self):
        for days_ago in [30, 0]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertGreaterEqual(result[0]["tage_seit_pr"], 0)

    def test_regression_bei_gewichtsverlust(self):
        # Alte Session mit hohem Gewicht, neue mit stark reduziertem
        session_alt = self._make_session(days_ago=60)
        self._add_satz(session_alt, gewicht=120, wiederholungen=5)
        session_neu = self._make_session(days_ago=5)
        self._add_satz(session_neu, gewicht=60, wiederholungen=5)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "regression")

    def test_leere_top_uebungen_gibt_leer(self):
        result = calculate_plateau_analysis(self._alle_saetze(), [])
        self.assertEqual(result, [])

    def test_konsolidierung_bei_sinkendem_rpe(self):
        """Gleiches Gewicht über 4 Wochen aber sinkender RPE → Konsolidierung, kein Plateau."""
        # 4 Sessions über 4 Wochen, gleiches Gewicht, sinkender RPE
        for days_ago, rpe in [(25, 9.5), (18, 9.0), (10, 8.5), (3, 8.0)]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8, rpe=rpe)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "konsolidierung")
        self.assertIn("RPE sinkt", result[0]["status_label"])

    def test_echtes_plateau_bei_gleichbleibendem_rpe(self):
        """Gleiches Gewicht + gleichbleibender RPE über 4 Wochen → echtes Plateau."""
        for days_ago, rpe in [(25, 9.0), (18, 9.0), (10, 9.0), (3, 9.0)]:
            session = self._make_session(days_ago=days_ago)
            self._add_satz(session, gewicht=80, wiederholungen=8, rpe=rpe)
        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(len(result), 1)
        self.assertIn("plateau", result[0]["status"])

    def test_nur_null_1rm_werte_gibt_leer(self):
        for days_ago in [7, 0]:
            session = self._make_session(days_ago=days_ago)
            Satz.objects.create(
                einheit=session,
                uebung=self.uebung,
                satz_nr=1,
                gewicht=0,
                wiederholungen=8,
                rpe=7.0,
                ist_aufwaermsatz=False,
            )

        result = calculate_plateau_analysis(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(result, [])


# ──────────────────────────────────────────────────────────────────────────────
# calculate_1rm_standards
# ──────────────────────────────────────────────────────────────────────────────
class TestOneRmStandards(StatsTestBase):

    def _alle_saetze(self):
        return Satz.objects.filter(einheit__user=self.user)

    def _top_uebungen(self):
        return [{"uebung__bezeichnung": "Kniebeuge", "muskelgruppe_display": "Beine"}]

    def test_ohne_saetze_gibt_leer(self):
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen())
        self.assertEqual(result, [])

    def test_uebung_ohne_standards_wird_uebersprungen(self):
        uebung_ohne = Uebung.objects.create(
            bezeichnung="Ohne Standards",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
            # standard_beginner etc. bleiben NULL
        )
        session = self._make_session()
        Satz.objects.create(
            einheit=session, uebung=uebung_ohne, satz_nr=1, gewicht=80, wiederholungen=8
        )
        result = calculate_1rm_standards(
            self._alle_saetze(),
            [{"uebung__bezeichnung": "Ohne Standards", "muskelgruppe_display": "Brust"}],
        )
        self.assertEqual(result, [])

    def test_mit_standards_gibt_ergebnis(self):
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        self.assertEqual(len(result), 1)

    def test_ergebnis_felder_vorhanden(self):
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        eintrag = result[0]
        for key in ("uebung", "geschaetzter_1rm", "1rm_entwicklung", "standard_info"):
            self.assertIn(key, eintrag)

    def test_1rm_entwicklung_hat_6_eintraege(self):
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        self.assertEqual(len(result[0]["1rm_entwicklung"]), 6)

    def test_geschaetzter_1rm_epley_korrekt(self):
        # 80kg × 8 Wdh: Epley = 80 × (1 + 8/30) ≈ 101.3
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        expected = round(80 * (1 + 8 / 30.0), 1)
        self.assertAlmostEqual(result[0]["geschaetzter_1rm"], expected, delta=0.5)

    def test_allometrische_skalierung_bei_anderem_gewicht(self):
        session = self._make_session()
        self._add_satz(session, gewicht=80, wiederholungen=8)
        result_80 = calculate_1rm_standards(
            self._alle_saetze(), self._top_uebungen(), user_gewicht=80
        )
        result_60 = calculate_1rm_standards(
            self._alle_saetze(), self._top_uebungen(), user_gewicht=60
        )
        # Leichterer User hat niedrigere Standards
        std_80 = result_80[0]["standard_info"]["alle_levels"]["Anfänger"]
        std_60 = result_60[0]["standard_info"]["alle_levels"]["Anfänger"]
        self.assertGreater(std_80, std_60)

    def test_standard_level_beginner_bei_niedrigem_gewicht(self):
        session = self._make_session()
        self._add_satz(session, gewicht=30, wiederholungen=5)  # ~35kg 1RM < 60 Beginner-Standard
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        self.assertEqual(result[0]["standard_info"]["level"], "untrainiert")

    def test_standard_level_intermediate_bei_ausreichendem_gewicht(self):
        session = self._make_session()
        self._add_satz(session, gewicht=95, wiederholungen=8)  # ~1RM ≈ 120 kg → intermediate
        result = calculate_1rm_standards(self._alle_saetze(), self._top_uebungen(), user_gewicht=80)
        level = result[0]["standard_info"]["level"]
        self.assertIn(level, ("intermediate", "advanced", "elite"))
