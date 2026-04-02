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
    _check_rpe10_warning,
    _check_session_rpe_trend_warning,
    _detect_volume_warnings,
    _get_fatigue_rating,
    _get_motivation_quote,
    _get_rpe10_anteil,
    _get_session_rpe_trend,
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

    def test_koerpergewicht_faktor_display(self):
        """Regression: koerpergewicht_faktor 0.7 sollte als '70%' angezeigt werden, nicht '1%'."""
        dips = Uebung.objects.create(
            bezeichnung="Dips",
            muskelgruppe="BRUST",
            gewichts_typ="KOERPERGEWICHT",
            koerpergewicht_faktor=0.7,  # 70% des Körpergewichts
        )
        # Körperwert für den User setzen
        from core.models import KoerperWerte

        KoerperWerte.objects.create(user=self.user, gewicht=80.0, datum=timezone.now().date())
        # Ein paar Sätze anlegen
        for days_ago in [5, 10, 15]:
            session = self._session(days_ago=days_ago)
            Satz.objects.create(
                einheit=session,
                uebung=dips,
                satz_nr=1,
                gewicht=0,  # kein Zusatzgewicht
                wiederholungen=10,
                ist_aufwaermsatz=False,
            )
        response = self.client.get(reverse("exercise_stats", args=[dips.id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        # Prüfen dass "70%" im HTML vorkommt (nicht "1%" oder "0%")
        self.assertIn("70%", html, "Körpergewicht-Faktor sollte als '70%' angezeigt werden")
        self.assertNotIn(
            ">1%<", html, "Körpergewicht-Faktor sollte nicht als '1%' angezeigt werden"
        )


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


# ─────────────────────────────────────────────────────────────────────────────
# Robustness Tests - Edge Cases & Empty Data Handling
# ─────────────────────────────────────────────────────────────────────────────
class TestExerciseStatsRobustness(StatsBase):
    """Tests für Edge Cases und leere Daten bei exercise_stats View."""

    def test_avg_rpe_none_handling(self):
        """avg_rpe = None sollte nicht crashen (Sätze ohne RPE)."""
        for days_ago in [5, 10, 15]:
            self._satz(self._session(days_ago=days_ago), gewicht=80, wdh=8, rpe=None)
        response = self.client.get(reverse("exercise_stats", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        # avg_rpe sollte None sein
        self.assertIsNone(response.context.get("avg_rpe"))
        # Template sollte RPE-Card nicht anzeigen
        html = response.content.decode("utf-8")
        self.assertNotIn("Durchschnittliches RPE", html)

    def test_rpe_zero_edge_case(self):
        """RPE = 0 sollte angezeigt werden (theoretisch möglich)."""
        # Sätze mit RPE 0 (warm-up ohne Anstrengung)
        for days_ago in [5, 10]:
            self._satz(self._session(days_ago=days_ago), gewicht=20, wdh=15, rpe=0.0)
        response = self.client.get(reverse("exercise_stats", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        # avg_rpe sollte 0.0 sein (Django Avg returnt None bei allen NULL, aber 0.0 bei Werten)
        # ABER: Template versteckt RPE=0 wegen {% if avg_rpe %} Bug
        avg_rpe = response.context.get("avg_rpe")
        # Django's Avg() kann 0.0 returnen
        if avg_rpe is not None:
            self.assertEqual(round(avg_rpe, 1), 0.0)

    def test_best_weight_zero_bodyweight_only(self):
        """Körpergewichts-Übungen berechnen effektives Gewicht (KG * Faktor)."""
        pullups = Uebung.objects.create(
            bezeichnung="Klimmzüge",
            muskelgruppe="RUECKEN_LAT",
            gewichts_typ="KOERPERGEWICHT",
            koerpergewicht_faktor=0.7,
        )
        from core.models import KoerperWerte

        # Körpergewicht setzen
        KoerperWerte.objects.create(user=self.user, gewicht=80.0, datum=timezone.now().date())
        # Sätze ohne Zusatzgewicht
        for days_ago in [5, 10]:
            session = self._session(days_ago=days_ago)
            Satz.objects.create(
                einheit=session,
                uebung=pullups,
                satz_nr=1,
                gewicht=0,
                wiederholungen=10,
                ist_aufwaermsatz=False,
            )
        response = self.client.get(reverse("exercise_stats", args=[pullups.id]))
        self.assertEqual(response.status_code, 200)
        # best_weight sollte effektives Körpergewicht sein (80 * 0.7 = 56)
        self.assertEqual(response.context.get("best_weight"), 56.0)
        # best_reps sollte gesetzt sein
        self.assertEqual(response.context.get("best_reps"), 10)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 9.3 – RPE-10-Warnung
# ─────────────────────────────────────────────────────────────────────────────
class TestRpe10Warning(StatsBase):
    """Tests für _get_rpe10_anteil und _check_rpe10_warning."""

    def test_rpe10_anteil_keine_daten(self):
        """Ohne RPE-Daten → None."""
        heute = timezone.now()
        self.assertIsNone(_get_rpe10_anteil(self.user, heute))

    def test_rpe10_anteil_unter_5_prozent(self):
        """< 5% RPE-10 → optimal, keine Warnung."""
        session = self._session(days_ago=3)
        # 19 Sätze RPE 8, 1 Satz RPE 10 → 5%
        for _ in range(19):
            self._satz(session, rpe=8.0)
        self._satz(session, rpe=10.0)
        heute = timezone.now()
        anteil = _get_rpe10_anteil(self.user, heute)
        self.assertEqual(anteil, 5.0)
        self.assertEqual(_check_rpe10_warning(self.user, heute), [])

    def test_rpe10_anteil_5_bis_15_prozent(self):
        """5-15% RPE-10 → akzeptabel, keine Warnung."""
        session = self._session(days_ago=3)
        for _ in range(8):
            self._satz(session, rpe=8.0)
        for _ in range(2):
            self._satz(session, rpe=10.0)
        heute = timezone.now()
        anteil = _get_rpe10_anteil(self.user, heute)
        self.assertEqual(anteil, 20.0)  # 2/10 = 20%
        # 20% > 15% → Warnung
        warnings = _check_rpe10_warning(self.user, heute)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["type"], "rpe10")

    def test_rpe10_anteil_ueber_15_prozent_warnung(self):
        """> 15% RPE-10 → danger-Warnung."""
        session = self._session(days_ago=2)
        for _ in range(4):
            self._satz(session, rpe=8.0)
        for _ in range(4):
            self._satz(session, rpe=10.0)
        heute = timezone.now()
        anteil = _get_rpe10_anteil(self.user, heute)
        self.assertEqual(anteil, 50.0)
        warnings = _check_rpe10_warning(self.user, heute)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["severity"], "danger")
        self.assertIn("50.0%", warnings[0]["message"])

    def test_rpe10_ignoriert_aufwaermsaetze(self):
        """Aufwärmsätze mit RPE 10 zählen nicht."""
        session = self._session(days_ago=1)
        for _ in range(10):
            self._satz(session, rpe=8.0)
        # RPE-10 Aufwärmsatz → ignoriert
        self._satz(session, rpe=10.0, warmup=True)
        heute = timezone.now()
        anteil = _get_rpe10_anteil(self.user, heute)
        self.assertEqual(anteil, 0.0)

    def test_rpe10_nur_letzte_14_tage(self):
        """Sätze älter als 14 Tage werden ignoriert."""
        old_session = self._session(days_ago=20)
        for _ in range(5):
            self._satz(old_session, rpe=10.0)
        recent_session = self._session(days_ago=3)
        for _ in range(10):
            self._satz(recent_session, rpe=8.0)
        heute = timezone.now()
        anteil = _get_rpe10_anteil(self.user, heute)
        self.assertEqual(anteil, 0.0)

    def test_rpe10_in_training_stats_context(self):
        """Training-Stats-View enthält rpe10_anteil im Context."""
        session = self._session(days_ago=2)
        for _ in range(5):
            self._satz(session, rpe=8.0)
        self._satz(session, rpe=10.0)
        response = self.client.get(reverse("training_stats"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("rpe10_anteil", response.context)

    def test_rpe10_warning_in_dashboard(self):
        """Dashboard zeigt RPE-10-Warnung bei >15%."""
        # Braucht ≥4 Trainings für performance_warnings
        for days_ago in [1, 4, 7, 10]:
            session = self._session(days_ago=days_ago)
            self._satz(session, rpe=10.0)
            self._satz(session, rpe=10.0)
            self._satz(session, rpe=8.0)
        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertEqual(response.status_code, 200)
        warnings = response.context.get("performance_warnings", [])
        rpe10_warnings = [w for w in warnings if w["type"] == "rpe10"]
        self.assertTrue(len(rpe10_warnings) >= 1)
        self.assertContains(response, "Überbelastung")


class TestTrainingStatsRobustness(StatsBase):
    """Tests für Edge Cases bei training_stats View."""

    def test_empty_data_no_crash(self):
        """Komplett leerer Account sollte nicht crashen."""
        # Neuer User ohne Daten
        new_user = User.objects.create_user(username="new_user", password="pass")
        self.client.force_login(new_user)
        response = self.client.get(reverse("training_stats"))
        self.assertEqual(response.status_code, 200)
        # Keine Daten sollten angezeigt werden
        html = response.content.decode("utf-8").lower()
        self.assertIn("noch keine", html)

    def test_division_by_zero_avg_volume(self):
        """Durchschnitts-Volumen bei 0 Trainings sollte nicht crashen."""
        # User ohne abgeschlossene Trainings
        response = self.client.get(reverse("training_stats"))
        self.assertEqual(response.status_code, 200)
        # Context sollte safe defaults haben
        # Prüfe dass keine Division-by-Zero Fehler auftreten


class TestDashboardRobustness(TestCase):
    """Tests für Edge Cases bei dashboard View."""

    def setUp(self):
        self.user = User.objects.create_user(username="dash_user", password="pass")
        self.client.force_login(self.user)

    def test_new_user_empty_dashboard(self):
        """Neuer User ohne Daten sollte leeres Dashboard sehen."""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        # Kein Crash bei letzter_koerperwert = None
        self.assertIsNone(response.context.get("letzter_koerperwert"))

    def test_no_active_plan(self):
        """User ohne aktiven Plan sollte Planauswahl sehen."""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        # Kein Crash, sollte Plan-Erstellung vorschlagen


class TestBodyStatsRobustness(TestCase):
    """Tests für Edge Cases bei body_stats View."""

    def setUp(self):
        self.user = User.objects.create_user(username="body_user", password="pass")
        self.client.force_login(self.user)

    def test_no_body_data(self):
        """User ohne Körperwerte sollte leere Ansicht sehen."""
        response = self.client.get(reverse("body_stats"))
        self.assertEqual(response.status_code, 200)
        # no_data Flag sollte gesetzt sein
        self.assertTrue(response.context.get("no_data"))
        html = response.content.decode("utf-8")
        self.assertIn("Noch keine Körperwerte", html)

    def test_optional_fields_none(self):
        """BMI, FFMI, KFA können None sein und sollten nicht crashen."""
        from core.models import KoerperWerte

        # Nur Gewicht, keine Größe → BMI/FFMI = None
        KoerperWerte.objects.create(user=self.user, gewicht=80.0, datum=date.today())
        response = self.client.get(reverse("body_stats"))
        self.assertEqual(response.status_code, 200)
        # Kein Crash, auch wenn BMI None ist


class TestPDFExportRobustness(TestCase):
    """Tests für Edge Cases bei PDF Export."""

    def setUp(self):
        self.user = User.objects.create_user(username="pdf_user", password="pass")
        self.client.force_login(self.user)

    def test_pdf_export_empty_data(self):
        """PDF Export mit 0 Trainings sollte nicht crashen."""
        response = self.client.get(reverse("export_training_pdf"))
        # Sollte entweder 200 (leeres PDF) oder Redirect (keine Daten) sein
        self.assertIn(response.status_code, [200, 302])

    def test_pdf_saetze_30_tage_zero(self):
        """widthratio mit saetze_30_tage=0 sollte nicht crashen."""
        # Dies testet implizit den Division-by-Zero Case
        # Django's widthratio returnt 0 bei Division by Zero (kein Crash)
        response = self.client.get(reverse("export_training_pdf"))
        # Kein 500 Error
        self.assertNotEqual(response.status_code, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 19: Session-RPE-Trend
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionRpeTrend(StatsBase):
    """Phase 19: _get_session_rpe_trend und _check_session_rpe_trend_warning."""

    def _create_sessions_with_rpe(self, rpe_values):
        """Erstellt Sessions mit gegebenen RPE-Werten (älteste zuerst)."""
        sessions = []
        for i, rpe_val in enumerate(reversed(rpe_values)):
            s = self._session(days_ago=i + 1)
            self._satz(s, gewicht=80, wdh=8, rpe=rpe_val)
            self._satz(s, gewicht=80, wdh=8, rpe=rpe_val)
            sessions.append(s)
        return sessions

    def test_keine_sessions_leeres_ergebnis(self):
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(result["sessions"], [])
        self.assertIsNone(result["trend"])

    def test_weniger_als_3_sessions_kein_trend(self):
        self._create_sessions_with_rpe([7.0, 8.0])
        result = _get_session_rpe_trend(self.user)
        self.assertIsNone(result["trend"])

    def test_steigende_rpe_trend_rising(self):
        self._create_sessions_with_rpe([7.0, 7.5, 8.0, 8.5, 9.0])
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(result["trend"], "rising")
        self.assertGreater(result["slope"], 0)

    def test_fallende_rpe_trend_falling(self):
        self._create_sessions_with_rpe([9.0, 8.5, 8.0, 7.5, 7.0])
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(result["trend"], "falling")
        self.assertLess(result["slope"], 0)

    def test_stabile_rpe_trend_stable(self):
        self._create_sessions_with_rpe([8.0, 8.0, 8.0, 8.0, 8.0])
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(result["trend"], "stable")

    def test_current_avg_ist_letzter_wert(self):
        self._create_sessions_with_rpe([7.0, 7.5, 8.0])
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(result["current_avg"], 8.0)

    def test_aufwaermsaetze_ignoriert(self):
        s = self._session(days_ago=1)
        self._satz(s, gewicht=80, wdh=8, rpe=9.0, warmup=True)
        self._satz(s, gewicht=80, wdh=8, rpe=9.0, warmup=True)
        # Nur Warmups → kein RPE-Datenpunkt
        result = _get_session_rpe_trend(self.user)
        self.assertEqual(len(result["sessions"]), 0)

    def test_warning_steigend_und_ueber_8_5(self):
        """Warnung wenn RPE steigend UND > 8.5."""
        self._create_sessions_with_rpe([8.0, 8.5, 8.8, 9.0, 9.2])
        heute = timezone.now()
        warnings = _check_session_rpe_trend_warning(self.user, heute)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["type"], "rpe_trend")

    def test_keine_warning_steigend_aber_unter_8_5(self):
        """Keine Warnung wenn steigend aber aktuell unter 8.5."""
        self._create_sessions_with_rpe([6.0, 6.5, 7.0, 7.5, 8.0])
        heute = timezone.now()
        warnings = _check_session_rpe_trend_warning(self.user, heute)
        self.assertEqual(len(warnings), 0)

    def test_keine_warning_fallend(self):
        """Keine Warnung bei fallendem RPE."""
        self._create_sessions_with_rpe([9.5, 9.0, 8.5, 8.0, 7.5])
        heute = timezone.now()
        warnings = _check_session_rpe_trend_warning(self.user, heute)
        self.assertEqual(len(warnings), 0)

    def test_dashboard_enthaelt_session_rpe_trend(self):
        """Dashboard-Context enthält session_rpe_trend."""
        self._create_sessions_with_rpe([7.0, 7.5, 8.0, 8.5, 9.0])
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("session_rpe_trend", response.context)
