"""
Tests für core/views/training_stats.py

Strategie:
- Pure Hilfsfunktionen direkt testen (kein HTTP)
- Views über Django-TestClient (GET-Antworten)
- dashboard / training_list / exercise_stats / delete_training
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Equipment, Plan, Satz, Trainingseinheit, Uebung
from core.views.training_stats import (
    _calc_rpe_trend,
    _detect_volume_warnings,
    _get_fatigue_rating,
    _get_motivation_quote,
    _get_week_start,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
class StatsBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stats_user", password="pass1234")
        self.client.force_login(self.user)
        eq = Equipment.objects.create(name="HANTEL")
        self.uebung = Uebung.objects.create(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        self.uebung.equipment.add(eq)
        self.plan = Plan.objects.create(name="TestPlan", user=self.user)

    def _session(self, days_ago=0, abgeschlossen=True):
        t = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, dauer_minuten=45, abgeschlossen=abgeschlossen
        )
        t.datum = timezone.now() - timedelta(days=days_ago)
        t.save()
        return t

    def _satz(self, session, gewicht=80, wdh=8, rpe=None, warmup=False):
        return Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=gewicht,
            wiederholungen=wdh,
            rpe=rpe,
            ist_aufwaermsatz=warmup,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pure Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────
class TestGetWeekStart(TestCase):
    def test_montag_bleibt_montag(self):
        monday = timezone.now().replace(
            year=2025, month=1, day=6, hour=10, minute=0, second=0, microsecond=0
        )
        self.assertEqual(_get_week_start(monday).date(), date(2025, 1, 6))

    def test_sonntag_geht_zurueck_auf_montag(self):
        sunday = timezone.now().replace(
            year=2025, month=1, day=12, hour=15, minute=0, second=0, microsecond=0
        )
        self.assertEqual(_get_week_start(sunday).date(), date(2025, 1, 6))

    def test_mittwoch_geht_zurueck_auf_montag(self):
        wednesday = timezone.now().replace(
            year=2025, month=1, day=8, hour=9, minute=0, second=0, microsecond=0
        )
        self.assertEqual(_get_week_start(wednesday).date(), date(2025, 1, 6))

    def test_ergebnis_hat_null_uhrzeit(self):
        result = _get_week_start(timezone.now())
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)
        self.assertEqual(result.second, 0)


class TestGetFatigueRating(TestCase):
    def test_sehr_niedrig(self):
        rating, color, _ = _get_fatigue_rating(0)
        self.assertEqual(rating, "Sehr niedrig")
        self.assertEqual(color, "success")

    def test_niedrig(self):
        rating, color, _ = _get_fatigue_rating(25)
        self.assertEqual(rating, "Niedrig")
        self.assertEqual(color, "info")

    def test_moderat(self):
        rating, color, _ = _get_fatigue_rating(45)
        self.assertEqual(rating, "Moderat")
        self.assertEqual(color, "warning")

    def test_hoch(self):
        rating, color, msg = _get_fatigue_rating(70)
        self.assertEqual(rating, "Hoch")
        self.assertEqual(color, "danger")
        self.assertIn("Deload", msg)

    def test_grenzwerte_exakt(self):
        self.assertEqual(_get_fatigue_rating(60)[0], "Hoch")
        self.assertEqual(_get_fatigue_rating(40)[0], "Moderat")
        self.assertEqual(_get_fatigue_rating(20)[0], "Niedrig")
        self.assertEqual(_get_fatigue_rating(19)[0], "Sehr niedrig")


class TestGetMotivationQuote(TestCase):
    def test_hohe_ermuedung_gibt_erholungs_quote(self):
        quote = _get_motivation_quote(form_index=80, fatigue_index=70)
        # Emoji kann mit oder ohne Variation Selector (U+FE0F) kommen
        self.assertTrue(
            any(quote.startswith(e) for e in ["🛌", "⚠", "🧘", "💤"]),
            f"Unerwartetes Emoji: {repr(quote[:2])}",
        )

    def test_hohe_form_gibt_performance_quote(self):
        quote = _get_motivation_quote(form_index=80, fatigue_index=10)
        self.assertIn(quote[0], ["💪", "🔥", "⚡", "🏆"])

    def test_gute_form_gibt_solide_quote(self):
        quote = _get_motivation_quote(form_index=50, fatigue_index=10)
        self.assertIn(quote[0], ["✨", "📈", "💯", "🎯"])

    def test_niedrige_form_gibt_motivations_quote(self):
        quote = _get_motivation_quote(form_index=20, fatigue_index=10)
        self.assertIn(quote[0], ["🌟", "💪", "🔋", "🎯"])

    def test_gibt_immer_string_zurueck(self):
        for form in [0, 40, 70, 100]:
            for fatigue in [0, 30, 60, 80]:
                result = _get_motivation_quote(form, fatigue)
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


class TestDetectVolumeWarnings(TestCase):
    def test_keine_daten_keine_warnungen(self):
        self.assertEqual(_detect_volume_warnings([], []), [])

    def test_zu_wenig_daten_keine_warnung(self):
        result = _detect_volume_warnings(["KW1", "KW2"], [1000, 1200])
        self.assertEqual(result, [])

    def test_spike_erzeugt_warnung(self):
        labels = ["KW1", "KW2", "KW3", "KW4"]
        data = [1000, 1000, 1000, 4000]  # KW4 massiver Spike
        result = _detect_volume_warnings(labels, data)
        self.assertGreater(len(result), 0)

    def test_stabiles_volumen_keine_warnung(self):
        labels = ["KW1", "KW2", "KW3", "KW4"]
        data = [1000, 1050, 1020, 1080]
        result = _detect_volume_warnings(labels, data)
        self.assertEqual(result, [])


class TestCalcRpeTrend(StatsBase):
    def test_keine_saetze_gibt_none(self):
        saetze = Satz.objects.filter(einheit__user=self.user)
        self.assertIsNone(_calc_rpe_trend(saetze, None))

    def test_nur_neuere_daten_gibt_none(self):
        session = self._session(days_ago=5)
        self._satz(session, rpe=7.0)
        saetze = Satz.objects.filter(einheit__user=self.user)
        self.assertIsNone(_calc_rpe_trend(saetze, 7.0))

    def test_improving_wenn_neueres_rpe_niedriger(self):
        for i in range(35, 57):
            self._satz(self._session(days_ago=i), rpe=8.5)
        for i in range(0, 14):
            self._satz(self._session(days_ago=i), rpe=7.0)
        saetze = Satz.objects.filter(einheit__user=self.user)
        self.assertEqual(_calc_rpe_trend(saetze, 7.5), "improving")

    def test_declining_wenn_neueres_rpe_hoeher(self):
        for i in range(35, 57):
            self._satz(self._session(days_ago=i), rpe=6.5)
        for i in range(0, 14):
            self._satz(self._session(days_ago=i), rpe=8.5)
        saetze = Satz.objects.filter(einheit__user=self.user)
        self.assertEqual(_calc_rpe_trend(saetze, 7.5), "declining")


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────
class TestDashboardView(StatsBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_leerer_dashboard_200(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_dashboard_mit_trainings(self):
        for days_ago in [1, 3, 7]:
            s = self._session(days_ago=days_ago)
            self._satz(s, gewicht=80, wdh=8, rpe=7.5)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class TestTrainingListView(StatsBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("training_list")).status_code, 302)

    def test_leere_liste_200(self):
        self.assertEqual(self.client.get(reverse("training_list")).status_code, 200)

    def test_mit_trainings_200(self):
        self._session(days_ago=2)
        self.assertEqual(self.client.get(reverse("training_list")).status_code, 200)


class TestDeleteTrainingView(StatsBase):
    def test_loescht_eigenes_training(self):
        session = self._session(days_ago=5)
        response = self.client.post(reverse("delete_training", args=[session.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Trainingseinheit.objects.filter(id=session.id).exists())

    def test_loescht_kein_fremdes_training(self):
        other = User.objects.create_user(username="other", password="pass1234")
        other_plan = Plan.objects.create(name="OP", user=other)
        other_session = Trainingseinheit.objects.create(
            user=other, plan=other_plan, dauer_minuten=30
        )
        response = self.client.post(reverse("delete_training", args=[other_session.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Trainingseinheit.objects.filter(id=other_session.id).exists())

    def test_login_required(self):
        session = self._session(days_ago=5)
        self.client.logout()
        self.assertEqual(
            self.client.post(reverse("delete_training", args=[session.id])).status_code, 302
        )


class TestExerciseStatsView(StatsBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("exercise_stats", args=[self.uebung.id])).status_code, 302
        )

    def test_ohne_saetze_no_data(self):
        response = self.client.get(reverse("exercise_stats", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["no_data"])

    def test_mit_saetzen_zeigt_stats(self):
        for days_ago in [10, 20, 30]:
            self._satz(self._session(days_ago=days_ago), gewicht=80, wdh=6, rpe=7.5)
        response = self.client.get(reverse("exercise_stats", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("no_data", False))

    def test_unbekannte_uebung_404(self):
        self.assertEqual(self.client.get(reverse("exercise_stats", args=[99999])).status_code, 404)


class TestTrainingStatsView(StatsBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("training_stats")).status_code, 302)

    def test_ohne_daten_200(self):
        self.assertEqual(self.client.get(reverse("training_stats")).status_code, 200)

    def test_mit_daten_200(self):
        for days_ago in [2, 9, 16, 23]:
            self._satz(self._session(days_ago=days_ago), gewicht=100, wdh=5, rpe=8.0)
        self.assertEqual(self.client.get(reverse("training_stats")).status_code, 200)
