"""Tests für Phase 2 – PR-System.

Abgedeckt:
- _check_pr(): erster Satz, neuer 1RM, kein PR
- is_pr / pr_type / pr_previous_value werden in DB gesetzt
- finish_training context enthält session_prs
- exercise_stats context enthält pr_history
- dashboard context enthält prs_diese_woche
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Satz, Trainingseinheit, Uebung
from core.views.training_session import _check_pr


class TestCheckPrFunction(TestCase):
    """Unit-Tests für _check_pr()."""

    def setUp(self):
        self.user = User.objects.create_user("pr_user", password="x")
        self.uebung = Uebung.objects.create(
            bezeichnung="Test Übung PR",
            muskelgruppe="BRUST",
            gewichts_typ="GESAMT",
        )
        self.training = Trainingseinheit.objects.create(
            user=self.user,
            datum=timezone.now(),
            ist_deload=False,
            abgeschlossen=False,
        )

    def _make_satz(self, gewicht, wdh, ist_aufwaermsatz=False):
        return Satz.objects.create(
            einheit=self.training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=gewicht,
            wiederholungen=wdh,
            ist_aufwaermsatz=ist_aufwaermsatz,
        )

    def test_erster_satz_ist_pr(self):
        satz = self._make_satz(80, 8)
        msg = _check_pr(self.user, self.uebung, satz, 80.0, 8)
        self.assertIsNotNone(msg)
        self.assertIn("Erster Rekord", msg)
        satz.refresh_from_db()
        self.assertTrue(satz.is_pr)
        self.assertEqual(satz.pr_type, "first")
        self.assertIsNone(satz.pr_previous_value)

    def test_neuer_1rm_ist_pr(self):
        # Ersten (schwächeren) Satz anlegen
        self._make_satz(80, 8)  # 1RM ≈ 101.3
        # Neuen stärkeren Satz anlegen
        neuer_satz = self._make_satz(100, 5)  # 1RM ≈ 116.7
        msg = _check_pr(self.user, self.uebung, neuer_satz, 100.0, 5)
        self.assertIsNotNone(msg)
        self.assertIn("NEUER REKORD", msg)
        neuer_satz.refresh_from_db()
        self.assertTrue(neuer_satz.is_pr)
        self.assertEqual(neuer_satz.pr_type, "best_1rm")
        self.assertIsNotNone(neuer_satz.pr_previous_value)

    def test_kein_pr_wenn_schlechter(self):
        self._make_satz(100, 5)  # 1RM ≈ 116.7
        schlechterer_satz = self._make_satz(80, 5)  # 1RM ≈ 93.3
        msg = _check_pr(self.user, self.uebung, schlechterer_satz, 80.0, 5)
        self.assertIsNone(msg)
        schlechterer_satz.refresh_from_db()
        self.assertFalse(schlechterer_satz.is_pr)

    def test_deload_saetze_werden_ignoriert(self):
        """Deload-Trainings sollen beim PR-Check nicht berücksichtigt werden."""
        deload_training = Trainingseinheit.objects.create(
            user=self.user,
            ist_deload=True,
            abgeschlossen=True,
        )
        # Sehr starker Satz im Deload – soll trotzdem ignoriert werden
        Satz.objects.create(
            einheit=deload_training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=200,
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        # Normaler Satz → sollte als "Erster" erkannt werden (Deload zählt nicht)
        normaler_satz = self._make_satz(80, 8)
        msg = _check_pr(self.user, self.uebung, normaler_satz, 80.0, 8)
        self.assertIsNotNone(msg)
        self.assertIn("Erster Rekord", msg)


class TestFinishTrainingSessionPRs(TestCase):
    """Integrationstest: finish_training zeigt PRs im Context."""

    def setUp(self):
        self.user = User.objects.create_user("finish_pr_user", password="x")
        self.client.force_login(self.user)
        self.uebung = Uebung.objects.filter(is_custom=False).first()
        if self.uebung is None:
            self.uebung = Uebung.objects.create(
                bezeichnung="Test Übung",
                muskelgruppe="BRUST",
                gewichts_typ="GESAMT",
            )

    def test_finish_zeigt_session_prs(self):
        training = Trainingseinheit.objects.create(
            user=self.user,
            datum=timezone.now(),
            ist_deload=False,
            abgeschlossen=False,
        )
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
            is_pr=True,
            pr_type="first",
        )
        url = reverse("finish_training", args=[training.id])
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("session_prs", resp.context)
        self.assertEqual(len(list(resp.context["session_prs"])), 1)

    def test_finish_ohne_prs_zeigt_leere_liste(self):
        training = Trainingseinheit.objects.create(
            user=self.user,
            datum=timezone.now(),
            ist_deload=False,
            abgeschlossen=False,
        )
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
            is_pr=False,
        )
        url = reverse("finish_training", args=[training.id])
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(list(resp.context["session_prs"]))


class TestDashboardPRWidget(TestCase):
    """Dashboard zeigt PRs der letzten 7 Tage."""

    def setUp(self):
        self.user = User.objects.create_user("dash_pr_user", password="x")
        self.client.force_login(self.user)
        self.uebung = Uebung.objects.filter(is_custom=False).first()
        if self.uebung is None:
            self.uebung = Uebung.objects.create(
                bezeichnung="Test Übung",
                muskelgruppe="BRUST",
                gewichts_typ="GESAMT",
            )

    def test_dashboard_zeigt_aktuelle_prs(self):
        training = Trainingseinheit.objects.create(
            user=self.user,
            ist_deload=False,
            abgeschlossen=True,
        )
        Trainingseinheit.objects.filter(pk=training.pk).update(
            datum=timezone.now() - timedelta(days=2)
        )
        training.refresh_from_db()
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=100,
            wiederholungen=5,
            ist_aufwaermsatz=False,
            is_pr=True,
            pr_type="best_1rm",
        )
        resp = self.client.get(reverse("dashboard"), secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("prs_diese_woche", resp.context)
        self.assertEqual(len(list(resp.context["prs_diese_woche"])), 1)

    def test_dashboard_zeigt_keine_alten_prs(self):
        """PRs älter als 7 Tage sollen nicht im Widget erscheinen."""
        training = Trainingseinheit.objects.create(
            user=self.user,
            ist_deload=False,
            abgeschlossen=True,
        )
        # auto_now_add überschreiben über update()
        Trainingseinheit.objects.filter(pk=training.pk).update(
            datum=timezone.now() - timedelta(days=10)
        )
        training.refresh_from_db()
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=100,
            wiederholungen=5,
            ist_aufwaermsatz=False,
            is_pr=True,
            pr_type="best_1rm",
        )
        resp = self.client.get(reverse("dashboard"), secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(list(resp.context["prs_diese_woche"]))


class TestExerciseStatsPRHistory(TestCase):
    """exercise_stats zeigt PR-Geschichte im Context."""

    def setUp(self):
        self.user = User.objects.create_user("exstats_pr_user", password="x")
        self.client.force_login(self.user)
        self.uebung = Uebung.objects.filter(is_custom=False).first()
        if self.uebung is None:
            self.uebung = Uebung.objects.create(
                bezeichnung="Test Übung",
                muskelgruppe="BRUST",
                gewichts_typ="GESAMT",
            )

    def test_exercise_stats_enthaelt_pr_history(self):
        training = Trainingseinheit.objects.create(
            user=self.user,
            ist_deload=False,
            abgeschlossen=True,
        )
        # Normaler Satz (kein PR)
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
            is_pr=False,
        )
        # PR-Satz
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=2,
            gewicht=100,
            wiederholungen=5,
            ist_aufwaermsatz=False,
            is_pr=True,
            pr_type="best_1rm",
        )
        url = reverse("exercise_stats", args=[self.uebung.id])
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("pr_history", resp.context)
        self.assertEqual(len(list(resp.context["pr_history"])), 1)
