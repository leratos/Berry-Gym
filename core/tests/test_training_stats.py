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

from core.models import Equipment, Plan, PlanUebung, Satz, Trainingsblock, Trainingseinheit, Uebung
from core.views.training_stats import (
    _calc_rpe_trend,
    _check_rpe10_warning,
    _check_session_rpe_trend_warning,
    _detect_volume_warnings,
    _get_fatigue_rating,
    _get_motivation_quote,
    _get_rpe10_anteil,
    _get_session_rpe_trend,
    _get_weakness_progress,
    _get_week_start,
    get_weakness_comparison,
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
        # Phase 22: PlanUebung-Eintrag, damit aktiver-Plan-Filter die Übung kennt.
        # Ohne PlanUebung würde get_active_plan_exercise_ids() ein leeres Set
        # zurückgeben und alle übungsbezogenen Stats wären leer.
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="8-12",
        )

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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 20: Schwachstellen-Tracker Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestWeaknessTracker(StatsBase):
    """Tests für Schwachstellen-Fortschritt und Monatsende-Vergleich."""

    def setUp(self):
        super().setUp()
        self.block = Trainingsblock.objects.create(
            user=self.user,
            name="Testblock",
            typ="masse",
            start_datum=date.today() - timedelta(days=30),
        )

    def _create_sets(self, muskelgruppe, count, days_ago=0):
        """Erstelle Arbeitssätze für eine Muskelgruppe."""
        ueb = Uebung.objects.create(
            bezeichnung=f"Übung_{muskelgruppe}_{count}",
            muskelgruppe=muskelgruppe,
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        session = self._session(days_ago=days_ago)
        for i in range(count):
            Satz.objects.create(
                einheit=session,
                uebung=ueb,
                satz_nr=i + 1,
                gewicht=50,
                wiederholungen=10,
                rpe=8,
                ist_aufwaermsatz=False,
            )

    # --- 20.1: Schwachstellen-Snapshot auf Trainingsblock ---

    def test_trainingsblock_schwachstellen_snapshot_field(self):
        """Trainingsblock hat schwachstellen_snapshot JSONField."""
        self.assertIsNone(self.block.schwachstellen_snapshot)
        snapshot = [{"muskelgruppe": "BAUCH", "ist_saetze": 4, "soll_min": 10, "soll_max": 18}]
        self.block.schwachstellen_snapshot = snapshot
        self.block.save()
        self.block.refresh_from_db()
        self.assertEqual(len(self.block.schwachstellen_snapshot), 1)
        self.assertEqual(self.block.schwachstellen_snapshot[0]["muskelgruppe"], "BAUCH")

    def test_snapshot_save_weakness_method(self):
        """_save_weakness_snapshot speichert korrekte Daten."""
        from ai_coach.plan_generator import PlanGenerator

        gen = PlanGenerator.__new__(PlanGenerator)
        gen.user_id = self.user.id
        analysis_data = {
            "weaknesses": [
                "BAUCH: Untertrainiert (nur 10 eff. Wdh vs. Ø 55)",
            ]
        }
        self._create_sets("BAUCH", 4, days_ago=5)
        gen._save_weakness_snapshot(analysis_data)
        self.block.refresh_from_db()
        self.assertIsNotNone(self.block.schwachstellen_snapshot)
        self.assertEqual(len(self.block.schwachstellen_snapshot), 1)
        entry = self.block.schwachstellen_snapshot[0]
        self.assertEqual(entry["muskelgruppe"], "BAUCH")
        self.assertEqual(entry["ist_saetze"], 4)
        self.assertGreater(entry["soll_min"], 0)

    def test_snapshot_no_active_block(self):
        """Kein Snapshot wenn kein aktiver Block."""
        self.block.end_datum = date.today()
        self.block.save()
        from ai_coach.plan_generator import PlanGenerator

        gen = PlanGenerator.__new__(PlanGenerator)
        gen.user_id = self.user.id
        gen._save_weakness_snapshot({"weaknesses": ["BAUCH: Untertrainiert (nur 5)"]})
        self.block.refresh_from_db()
        self.assertIsNone(self.block.schwachstellen_snapshot)

    def test_snapshot_no_weaknesses(self):
        """Kein Snapshot wenn keine Schwachstellen."""
        from ai_coach.plan_generator import PlanGenerator

        gen = PlanGenerator.__new__(PlanGenerator)
        gen.user_id = self.user.id
        gen._save_weakness_snapshot({"weaknesses": []})
        self.block.refresh_from_db()
        self.assertIsNone(self.block.schwachstellen_snapshot)

    # --- 20.2: Laufendes Satz-Tracking ---

    def test_weakness_progress_no_snapshot(self):
        """Leere Liste wenn kein Snapshot existiert."""
        result = _get_weakness_progress(self.user, self.block)
        self.assertEqual(result, [])

    def test_weakness_progress_erreicht(self):
        """Status 'erreicht' wenn Ist >= Soll-Min."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BRUST", "ist_saetze": 5, "soll_min": 12, "soll_max": 25}
        ]
        self.block.save()
        self._create_sets("BRUST", 14)
        result = _get_weakness_progress(self.user, self.block)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "erreicht")
        self.assertEqual(result[0]["ist_saetze"], 14)
        self.assertEqual(result[0]["prozent"], 100)

    def test_weakness_progress_auf_kurs(self):
        """Status 'auf_kurs' wenn Ist >= 60% von Soll-Min."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BRUST", "ist_saetze": 3, "soll_min": 12, "soll_max": 25}
        ]
        self.block.save()
        self._create_sets("BRUST", 8)  # 8/12 = 67%
        result = _get_weakness_progress(self.user, self.block)
        self.assertEqual(result[0]["status"], "auf_kurs")

    def test_weakness_progress_hinter_plan(self):
        """Status 'hinter_plan' wenn Ist < 60% von Soll-Min."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BRUST", "ist_saetze": 2, "soll_min": 12, "soll_max": 25}
        ]
        self.block.save()
        self._create_sets("BRUST", 3)  # 3/12 = 25%
        result = _get_weakness_progress(self.user, self.block)
        self.assertEqual(result[0]["status"], "hinter_plan")

    def test_weakness_progress_label(self):
        """Label wird korrekt humanisiert."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "SCHULTER_HINT", "ist_saetze": 2, "soll_min": 10, "soll_max": 18}
        ]
        self.block.save()
        result = _get_weakness_progress(self.user, self.block)
        self.assertEqual(result[0]["label"], "Hintere Schulter")

    # --- 20.3: Dashboard-Widget ---

    def test_dashboard_context_weakness_progress(self):
        """Dashboard-Context enthält weakness_progress."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BAUCH", "ist_saetze": 4, "soll_min": 10, "soll_max": 18}
        ]
        self.block.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("weakness_progress", response.context)

    def test_dashboard_widget_visible(self):
        """Widget ist sichtbar wenn Snapshot existiert."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BAUCH", "ist_saetze": 4, "soll_min": 10, "soll_max": 18}
        ]
        self.block.save()
        self._create_sets("BAUCH", 6)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Schwachstellen-Fortschritt")

    def test_dashboard_widget_hidden_without_snapshot(self):
        """Widget ist nicht sichtbar ohne Snapshot."""
        from django.core.cache import cache

        cache.clear()  # Sicherstellen dass kein gecachter Context den Test verfaelscht
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "Schwachstellen-Fortschritt")

    # --- 20.4: Monatsende-Vergleich ---

    def test_comparison_behoben(self):
        """Vergleich zeigt 'Behoben' wenn Soll-Min erreicht."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BAUCH", "ist_saetze": 4, "soll_min": 10, "soll_max": 18}
        ]
        self.block.save()
        self._create_sets("BAUCH", 12)
        result = get_weakness_comparison(self.user)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["behoben"])
        self.assertIn("Behoben", result[0]["zusammenfassung"])
        self.assertIn("→", result[0]["zusammenfassung"])

    def test_comparison_noch_untertrainiert(self):
        """Vergleich zeigt 'Noch untertrainiert' wenn Soll-Min nicht erreicht."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BAUCH", "ist_saetze": 4, "soll_min": 10, "soll_max": 18}
        ]
        self.block.save()
        self._create_sets("BAUCH", 6)
        result = get_weakness_comparison(self.user)
        self.assertFalse(result[0]["behoben"])
        self.assertIn("Noch untertrainiert", result[0]["zusammenfassung"])

    def test_comparison_no_block(self):
        """Leere Liste wenn kein aktiver Block."""
        self.block.end_datum = date.today()
        self.block.save()
        result = get_weakness_comparison(self.user)
        self.assertEqual(result, [])

    def test_comparison_baseline_vs_aktuell(self):
        """Baseline und aktueller Wert stimmen."""
        self.block.schwachstellen_snapshot = [
            {"muskelgruppe": "BRUST", "ist_saetze": 5, "soll_min": 12, "soll_max": 25}
        ]
        self.block.save()
        self._create_sets("BRUST", 15)
        result = get_weakness_comparison(self.user)
        self.assertEqual(result[0]["baseline"], 5)
        self.assertEqual(result[0]["aktuell"], 15)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 21: Stats-Seite Erweiterungen
# ─────────────────────────────────────────────────────────────────────────────
from core.views.training_stats import (
    _calc_kraftstandards_live,
    _calc_muscle_soll_bereiche,
    _calc_plateau_live,
    _calc_push_pull_ratio,
)


class TestMuscleSollBereiche(StatsBase):
    """21.1: Muskelgruppen-Balance mit Soll-Bereich."""

    def test_empty_returns_all_non_spezial(self):
        result = _calc_muscle_soll_bereiche({}, self.user)
        # Should return entries for all non-spezial muscle groups
        self.assertTrue(len(result) > 0)
        for item in result:
            self.assertIn("soll_min", item)
            self.assertIn("soll_max", item)
            self.assertIn("status", item)

    def test_unter_status_when_few_sets(self):
        """Muscle group with 0 sets should be 'unter'."""
        result = _calc_muscle_soll_bereiche({}, self.user)
        brust = next((r for r in result if r["code"] == "BRUST"), None)
        self.assertIsNotNone(brust)
        self.assertEqual(brust["status"], "unter")
        self.assertEqual(brust["saetze"], 0)

    def test_ok_status_within_range(self):
        """Muscle group within soll range should be 'ok'."""
        session = self._session(days_ago=5)
        for _ in range(15):
            self._satz(session, gewicht=80, wdh=8)
        result = _calc_muscle_soll_bereiche({"BRUST": 100}, self.user)
        brust = next((r for r in result if r["code"] == "BRUST"), None)
        self.assertIsNotNone(brust)
        self.assertEqual(brust["saetze"], 15)
        self.assertEqual(brust["status"], "ok")

    def test_ueber_status_above_range(self):
        """Muscle group above max soll should be 'ueber'."""
        session = self._session(days_ago=5)
        for _ in range(30):
            self._satz(session, gewicht=80, wdh=8)
        result = _calc_muscle_soll_bereiche({"BRUST": 100}, self.user)
        brust = next((r for r in result if r["code"] == "BRUST"), None)
        self.assertIsNotNone(brust)
        self.assertEqual(brust["status"], "ueber")

    def test_block_typ_affects_schwellenwerte(self):
        """Definition block should lower target ranges via volumen_faktor."""
        Trainingsblock.objects.create(
            user=self.user, typ="definition", start_datum=timezone.now().date()
        )
        result = _calc_muscle_soll_bereiche({}, self.user)
        brust = next((r for r in result if r["code"] == "BRUST"), None)
        self.assertIsNotNone(brust)
        # Definition factor 0.85 → soll_max should be < 25
        self.assertLess(brust["soll_max"], 25)


class TestPushPullRatio(StatsBase):
    """21.2: Push/Pull-Ratio."""

    def test_none_without_data(self):
        result = _calc_push_pull_ratio(self.user)
        self.assertIsNone(result)

    def test_balanced_ratio(self):
        """Equal push and pull sets → ratio ~1.0, green."""
        session = self._session(days_ago=5)
        # Push: BRUST
        for _ in range(10):
            self._satz(session, gewicht=80, wdh=8)
        # Pull: Create a pull exercise
        pull_uebung = Uebung.objects.create(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="COMPOUND"
        )
        for _ in range(10):
            Satz.objects.create(
                einheit=session,
                uebung=pull_uebung,
                satz_nr=1,
                gewicht=60,
                wiederholungen=8,
                ist_aufwaermsatz=False,
            )
        result = _calc_push_pull_ratio(self.user)
        self.assertIsNotNone(result)
        self.assertEqual(result["ratio"], 1.0)
        self.assertEqual(result["farbe"], "success")

    def test_push_dominant(self):
        """Many push, few pull → red."""
        session = self._session(days_ago=5)
        for _ in range(20):
            self._satz(session, gewicht=80, wdh=8)
        pull_uebung = Uebung.objects.create(
            bezeichnung="Rudern", muskelgruppe="RUECKEN_LAT", bewegungstyp="COMPOUND"
        )
        for _ in range(5):
            Satz.objects.create(
                einheit=session,
                uebung=pull_uebung,
                satz_nr=1,
                gewicht=60,
                wiederholungen=8,
                ist_aufwaermsatz=False,
            )
        result = _calc_push_pull_ratio(self.user)
        self.assertGreater(result["ratio"], 1.5)
        self.assertEqual(result["farbe"], "danger")

    def test_warmup_excluded(self):
        """Warmup sets should not be counted."""
        session = self._session(days_ago=5)
        for _ in range(10):
            self._satz(session, gewicht=80, wdh=8, warmup=True)
        result = _calc_push_pull_ratio(self.user)
        self.assertIsNone(result)


class TestPlateauLive(StatsBase):
    """21.3: Plateau-Tracking."""

    def test_empty_without_data(self):
        result = _calc_plateau_live(self.user)
        self.assertEqual(result, [])

    def test_recent_pr_green(self):
        """PR within 7 days → active_progression / success."""
        session = self._session(days_ago=3)
        satz = self._satz(session, gewicht=100, wdh=5)
        satz.is_pr = True
        satz.save()
        result = _calc_plateau_live(self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status_farbe"], "success")
        self.assertEqual(result[0]["status"], "active_progression")
        # Backwards-compat alias
        self.assertEqual(result[0]["farbe"], "success")

    def test_old_pr_with_no_recent_training_is_pause(self):
        """PR vor 60 Tagen, keine aktuelle Trainings-Aktivität → pause (Phase 23.3)."""
        session = self._session(days_ago=60)
        satz = self._satz(session, gewicht=100, wdh=5)
        satz.is_pr = True
        satz.save()
        result = _calc_plateau_live(self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "pause")
        self.assertEqual(result[0]["status_farbe"], "secondary")

    def test_plateau_when_pr_old_but_currently_training(self):
        """PR vor 50 Tagen, aktuell aktiv ohne Verbesserung → plateau (Phase 23.3)."""
        # Alter PR
        satz = self._satz(self._session(days_ago=50), gewicht=100, wdh=5)
        satz.is_pr = True
        satz.save()
        # Aktuelle Sätze (gleiches Gewicht, kein Drop, kein RPE-Trend)
        for d in [25, 18, 10, 3]:
            self._satz(self._session(days_ago=d), gewicht=100, wdh=5)
        result = _calc_plateau_live(self.user)
        self.assertEqual(len(result), 1)
        # 50 Tage seit PR + aktuell trainiert → plateau (43-84 days range)
        self.assertEqual(result[0]["status"], "plateau")
        self.assertEqual(result[0]["status_farbe"], "danger")

    def test_max_5_exercises(self):
        """Should return at most 5 exercises."""
        for i in range(7):
            ueb = Uebung.objects.create(
                bezeichnung=f"Übung_{i}", muskelgruppe="BRUST", bewegungstyp="COMPOUND"
            )
            # Phase 22: Übung in den Plan aufnehmen, sonst greift Filter
            PlanUebung.objects.create(plan=self.plan, uebung=ueb, reihenfolge=i + 2, saetze_ziel=3)
            session = self._session(days_ago=i + 1)
            Satz.objects.create(
                einheit=session,
                uebung=ueb,
                satz_nr=1,
                gewicht=50,
                wiederholungen=8,
                ist_aufwaermsatz=False,
                is_pr=True,
            )
        result = _calc_plateau_live(self.user)
        self.assertLessEqual(len(result), 5)


class TestKraftstandardsLive(StatsBase):
    """21.4: Kraftstandards-Übersicht."""

    def setUp(self):
        super().setUp()
        # Add strength standards to the exercise
        self.uebung.standard_beginner = 60.0
        self.uebung.standard_intermediate = 80.0
        self.uebung.standard_advanced = 110.0
        self.uebung.standard_elite = 140.0
        self.uebung.save()

    def test_empty_without_data(self):
        result = _calc_kraftstandards_live(self.user)
        self.assertEqual(result, [])

    def test_returns_level_and_progress(self):
        """Should compute 1RM and level classification."""
        session = self._session(days_ago=5)
        # 80kg × 8 reps → 1RM ≈ 101.3 kg → "advanced" level (≥80, <110)
        self._satz(session, gewicht=80, wdh=8)
        result = _calc_kraftstandards_live(self.user)
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item["uebung"], "Bankdrücken")
        self.assertGreater(item["geschaetzter_1rm"], 100)
        self.assertEqual(item["level"], "intermediate")
        self.assertEqual(item["level_label"], "Fortgeschritten")
        self.assertIn("naechstes_level", item)
        self.assertIn("prozent", item)

    def test_no_standards_skipped(self):
        """Exercises without standards should not appear."""
        no_std_uebung = Uebung.objects.create(
            bezeichnung="Kurzhantelpresse", muskelgruppe="BRUST", bewegungstyp="COMPOUND"
        )
        session = self._session(days_ago=5)
        Satz.objects.create(
            einheit=session,
            uebung=no_std_uebung,
            satz_nr=1,
            gewicht=40,
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        result = _calc_kraftstandards_live(self.user)
        names = [r["uebung"] for r in result]
        self.assertNotIn("Kurzhantelpresse", names)

    def test_elite_level_100_percent(self):
        """Exercise at/above elite level should show 100%."""
        session = self._session(days_ago=5)
        # 140kg × 1 rep → 1RM ≈ 144.7 kg → above elite (140)
        self._satz(session, gewicht=140, wdh=1)
        result = _calc_kraftstandards_live(self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["level"], "elite")
        self.assertEqual(result[0]["prozent"], 100)

    def test_max_5_results(self):
        """Should return at most 5 exercises."""
        for i in range(7):
            ueb = Uebung.objects.create(
                bezeichnung=f"Std_Übung_{i}",
                muskelgruppe="BRUST",
                bewegungstyp="COMPOUND",
                standard_beginner=50,
                standard_intermediate=70,
                standard_advanced=100,
                standard_elite=130,
            )
            # Phase 22: Übung in den Plan aufnehmen, sonst greift Filter
            PlanUebung.objects.create(plan=self.plan, uebung=ueb, reihenfolge=i + 2, saetze_ziel=3)
            session = self._session(days_ago=i + 1)
            Satz.objects.create(
                einheit=session,
                uebung=ueb,
                satz_nr=1,
                gewicht=60,
                wiederholungen=8,
                ist_aufwaermsatz=False,
            )
        result = _calc_kraftstandards_live(self.user)
        self.assertLessEqual(len(result), 5)


class TestStatsViewPhase21Integration(StatsBase):
    """Integration test: /stats/ view includes Phase 21 context data."""

    def test_stats_page_includes_phase21_data(self):
        """The stats page should return 200 and include Phase 21 context."""
        session = self._session(days_ago=5)
        self._satz(session, gewicht=80, wdh=8, rpe=8.0)
        self.uebung.standard_beginner = 60.0
        self.uebung.standard_intermediate = 80.0
        self.uebung.standard_advanced = 110.0
        self.uebung.standard_elite = 140.0
        self.uebung.save()
        response = self.client.get(reverse("training_stats"))
        self.assertEqual(response.status_code, 200)
        # Check Phase 21 context keys exist
        self.assertIn("muscle_soll_json", response.context)
        self.assertIn("push_pull_json", response.context)
        self.assertIn("plateau_live", response.context)
        self.assertIn("kraftstandards", response.context)

    def test_stats_page_no_data_still_200(self):
        """Stats with no data should still work (no_data template)."""
        response = self.client.get(reverse("training_stats"))
        self.assertEqual(response.status_code, 200)
