"""
Tests für core/views/training_session.py

Hilfsfunktionen (pure/near-pure):
  - _build_plan_gruppen()
  - _parse_ziel_wdh()
  - _calculate_empfohlene_pause()
  - _determine_empfehlung_hint()
  - _parse_set_post_data()
  - _check_pr()
  - _build_intensity_suggestion()

Views (Django TestClient):
  - training_select_plan, training_start
  - add_set, delete_set, update_set
  - finish_training
"""

from datetime import timedelta
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Equipment, Plan, PlanUebung, Satz, Trainingseinheit, Uebung, UserProfile
from core.views.training_session import (
    _build_intensity_suggestion,
    _build_plan_gruppen,
    _calculate_empfohlene_pause,
    _check_pr,
    _determine_empfehlung_hint,
    _parse_set_post_data,
    _parse_ziel_wdh,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared Fixtures
# ─────────────────────────────────────────────────────────────────────────────
class SessionBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sess_user", password="pass1234")
        self.client.force_login(self.user)
        eq = Equipment.objects.create(name="HANTEL")
        self.uebung = Uebung.objects.create(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        self.uebung.equipment.add(eq)
        self.plan = Plan.objects.create(name="Testplan", user=self.user)
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="8-12",
        )
        UserProfile.objects.get_or_create(user=self.user)

    def _training(self, abgeschlossen=False, days_ago=0):
        t = Trainingseinheit.objects.create(
            user=self.user,
            plan=self.plan,
            dauer_minuten=45,
            abgeschlossen=abgeschlossen,
        )
        if days_ago:
            t.datum = timezone.now() - timedelta(days=days_ago)
            t.save()
        return t

    def _satz(self, training, gewicht=80, wdh=8, rpe=None, warmup=False):
        return Satz.objects.create(
            einheit=training,
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
class TestBuildPlanGruppen(TestCase):
    def _plan(self, gruppe_id=None, gruppe_name=None):
        p = MagicMock()
        p.gruppe_id = gruppe_id
        p.gruppe_name = gruppe_name
        return p

    def test_plan_ohne_gruppe_geht_in_einzelne(self):
        p = self._plan()
        aktiv, andere, einzeln = _build_plan_gruppen([p], None)
        self.assertEqual(len(einzeln), 1)
        self.assertEqual(len(aktiv), 0)

    def test_plan_mit_aktiver_gruppe(self):
        import uuid

        gid = str(uuid.uuid4())
        p = self._plan(gruppe_id=gid, gruppe_name="Gruppe A")
        aktiv, andere, einzeln = _build_plan_gruppen([p], gid)
        self.assertIn(gid, aktiv)
        self.assertEqual(len(andere), 0)

    def test_plan_mit_inaktiver_gruppe(self):
        import uuid

        gid = str(uuid.uuid4())
        p = self._plan(gruppe_id=gid, gruppe_name="Gruppe B")
        aktiv, andere, einzeln = _build_plan_gruppen([p], "andere-id")
        self.assertIn(gid, andere)

    def test_leere_liste(self):
        aktiv, andere, einzeln = _build_plan_gruppen([], None)
        self.assertEqual(len(aktiv) + len(andere) + len(einzeln), 0)

    def test_mehrere_plaene_gleiche_gruppe_werden_gruppiert(self):
        import uuid

        gid = str(uuid.uuid4())
        p1 = self._plan(gruppe_id=gid, gruppe_name="G")
        p2 = self._plan(gruppe_id=gid, gruppe_name="G")
        _, andere, _ = _build_plan_gruppen([p1, p2], "x")
        self.assertEqual(len(andere[gid]["plaene"]), 2)


class TestParseZielWdh(TestCase):
    def test_bereich_8_12(self):
        self.assertEqual(_parse_ziel_wdh("8-12"), (8, 12))

    def test_einzelwert_10(self):
        self.assertEqual(_parse_ziel_wdh("10"), (10, 10))

    def test_ungueltig_gibt_8_12_fallback(self):
        self.assertEqual(_parse_ziel_wdh("abc"), (8, 12))

    def test_leerer_string_fallback(self):
        self.assertEqual(_parse_ziel_wdh(""), (8, 12))


class TestCalculateEmpfohlenePause(TestCase):
    def test_plan_pausenzeit_hat_vorrang(self):
        self.assertEqual(_calculate_empfohlene_pause("+2.5kg", 60), 60)

    def test_gewichtssteigerung_hint_180s(self):
        self.assertEqual(_calculate_empfohlene_pause("+2.5kg", None), 180)

    def test_wdh_hint_90s(self):
        self.assertEqual(_calculate_empfohlene_pause("mehr Wdh", None), 90)

    def test_standard_hint_120s(self):
        self.assertEqual(_calculate_empfohlene_pause("Niveau halten", None), 120)


class TestDetermineEmpfehlungHint(TestCase):
    def _satz(self, gewicht=80.0, wdh=8, rpe=None):
        s = MagicMock()
        s.gewicht = gewicht
        s.wiederholungen = wdh
        s.rpe = rpe
        return s

    def test_niedrige_rpe_gewichtssteigerung(self):
        s = self._satz(rpe=6.0)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12)
        self.assertAlmostEqual(g, 82.5)
        self.assertIn("+2.5kg", hint)

    def test_ziel_wdh_erreicht_gewichtssteigerung(self):
        s = self._satz(gewicht=80.0, wdh=12)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12)
        self.assertAlmostEqual(g, 82.5)

    def test_hohe_rpe_mehr_wdh(self):
        s = self._satz(gewicht=80.0, wdh=8, rpe=9.5)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12)
        self.assertEqual(g, 80.0)
        self.assertIn("mehr Wdh", hint)

    def test_niveau_halten(self):
        s = self._satz(gewicht=80.0, wdh=8, rpe=7.5)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12)
        self.assertEqual(g, 80.0)
        self.assertIn("Niveau", hint)

    def test_koerpergewicht_ohne_zusatz_wdh_progression(self):
        s = self._satz(gewicht=0.0, wdh=8, rpe=None)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12, is_kg_uebung=True)
        self.assertEqual(g, 0.0)

    def test_koerpergewicht_ziel_erreicht_naechste_stufe(self):
        s = self._satz(gewicht=0.0, wdh=12)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12, is_kg_uebung=True)
        self.assertIn("nächste", hint)


class TestParseSetPostData(TestCase):
    def _post(self, **kwargs):
        from django.http import QueryDict

        q = QueryDict(mutable=True)
        q.update(kwargs)
        return q

    def test_valide_felder_werden_geparst(self):
        g, w, r = _parse_set_post_data(self._post(gewicht="80.5", wiederholungen="10", rpe="7.5"))
        self.assertAlmostEqual(g, 80.5)
        self.assertEqual(w, 10)
        self.assertAlmostEqual(r, 7.5)

    def test_leere_felder_geben_none(self):
        g, w, r = _parse_set_post_data(self._post())
        self.assertIsNone(g)
        self.assertIsNone(w)
        self.assertIsNone(r)

    def test_komma_als_dezimaltrennzeichen(self):
        g, w, r = _parse_set_post_data(self._post(gewicht="82,5"))
        self.assertAlmostEqual(g, 82.5)

    def test_gewicht_zu_hoch_raises(self):
        with self.assertRaises(ValueError):
            _parse_set_post_data(self._post(gewicht="1001"))

    def test_wdh_zu_hoch_raises(self):
        with self.assertRaises(ValueError):
            _parse_set_post_data(self._post(wiederholungen="1000"))

    def test_rpe_ausserhalb_raises(self):
        with self.assertRaises(ValueError):
            _parse_set_post_data(self._post(rpe="11"))


class TestBuildIntensitySuggestion(TestCase):
    def test_niedrige_rpe_gibt_intensitaets_hint(self):
        result = _build_intensity_suggestion(6.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "intensity")
        self.assertEqual(result["color"], "info")

    def test_hohe_rpe_gibt_regenerations_hint(self):
        result = _build_intensity_suggestion(9.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["color"], "warning")

    def test_mittlere_rpe_gibt_none(self):
        self.assertIsNone(_build_intensity_suggestion(7.5))

    def test_grenzwert_6_5_gibt_none(self):
        self.assertIsNone(_build_intensity_suggestion(6.5))

    def test_grenzwert_8_5_gibt_none(self):
        self.assertIsNone(_build_intensity_suggestion(8.5))


class TestCheckPr(SessionBase):
    def test_erster_satz_ergibt_ersten_rekord(self):
        training = self._training()
        satz = self._satz(training, gewicht=100, wdh=5)
        msg = _check_pr(self.user, self.uebung, satz, 100.0, 5)
        self.assertIsNotNone(msg)
        self.assertIn("Rekord", msg)

    def test_neuer_pr_wird_erkannt(self):
        alte_session = self._training(days_ago=7)
        self._satz(alte_session, gewicht=80, wdh=8)
        neue_session = self._training()
        neuer_satz = self._satz(neue_session, gewicht=100, wdh=8)
        msg = _check_pr(self.user, self.uebung, neuer_satz, 100.0, 8)
        self.assertIsNotNone(msg)
        self.assertIn("REKORD", msg)

    def test_kein_pr_gibt_none(self):
        alte_session = self._training(days_ago=7)
        self._satz(alte_session, gewicht=100, wdh=8)
        neue_session = self._training()
        neuer_satz = self._satz(neue_session, gewicht=70, wdh=5)
        msg = _check_pr(self.user, self.uebung, neuer_satz, 70.0, 5)
        self.assertIsNone(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────
class TestTrainingSelectPlanView(SessionBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("training_select_plan")).status_code, 302)

    def test_get_200(self):
        self.assertEqual(self.client.get(reverse("training_select_plan")).status_code, 200)

    def test_zeigt_eigene_plaene(self):
        response = self.client.get(reverse("training_select_plan"))
        self.assertIn(self.plan, response.context.get("einzelne_plaene", []))


class TestTrainingStartView(SessionBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("training_start_plan", args=[self.plan.id])).status_code, 302
        )

    def test_startet_training_und_redirectet(self):
        response = self.client.get(reverse("training_start_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Trainingseinheit.objects.filter(user=self.user, plan=self.plan).exists())

    def test_fremder_plan_404(self):
        other = User.objects.create_user(username="other_ts", password="pass1234")
        fremder = Plan.objects.create(name="Fremd", user=other)
        self.assertEqual(
            self.client.get(reverse("training_start_plan", args=[fremder.id])).status_code, 404
        )

    def test_startet_aktiven_plan_setzt_cycle_start_auf_montag_wenn_leer(self):
        """Fallback: Beim Start aktiver Gruppe wird fehlender Zyklusstart auf Montag gesetzt."""
        import uuid

        gid = uuid.uuid4()
        self.plan.gruppe_id = gid
        self.plan.gruppe_name = "Testgruppe"
        self.plan.save(update_fields=["gruppe_id", "gruppe_name"])

        profile = self.user.profile
        profile.active_plan_group = gid
        profile.cycle_start_date = None
        profile.save(update_fields=["active_plan_group", "cycle_start_date"])

        self.client.get(reverse("training_start_plan", args=[self.plan.id]), secure=True)

        profile.refresh_from_db()
        today = timezone.now().date()
        monday_this_week = today - timedelta(days=today.weekday())
        self.assertEqual(profile.cycle_start_date, monday_this_week)


class TestAddSetView(SessionBase):
    def test_login_required(self):
        self.client.logout()
        t = self._training()
        self.assertEqual(self.client.post(reverse("add_set", args=[t.id])).status_code, 302)

    def test_post_erstellt_satz(self):
        training = self._training()
        response = self.client.post(
            reverse("add_set", args=[training.id]),
            {
                "uebung": str(self.uebung.id),
                "gewicht": "80",
                "wiederholungen": "8",
                "rpe": "7",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Satz.objects.filter(einheit=training, uebung=self.uebung).exists())

    def test_ajax_post_gibt_json(self):
        training = self._training()
        response = self.client.post(
            reverse("add_set", args=[training.id]),
            {
                "uebung": str(self.uebung.id),
                "gewicht": "80",
                "wiederholungen": "8",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_fremdes_training_404(self):
        other = User.objects.create_user(username="other_add", password="pass1234")
        other_plan = Plan.objects.create(name="OP", user=other)
        other_t = Trainingseinheit.objects.create(user=other, plan=other_plan, dauer_minuten=30)
        self.assertEqual(self.client.post(reverse("add_set", args=[other_t.id])).status_code, 404)


class TestDeleteSetView(SessionBase):
    def test_loescht_eigenen_satz(self):
        training = self._training()
        satz = self._satz(training)
        response = self.client.post(reverse("delete_set", args=[satz.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Satz.objects.filter(id=satz.id).exists())

    def test_fremden_satz_loeschen_404(self):
        other = User.objects.create_user(username="other_del", password="pass1234")
        other_plan = Plan.objects.create(name="OP", user=other)
        other_t = Trainingseinheit.objects.create(user=other, plan=other_plan, dauer_minuten=30)
        fremder_satz = Satz.objects.create(
            einheit=other_t,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=50,
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )
        self.assertEqual(
            self.client.post(reverse("delete_set", args=[fremder_satz.id])).status_code, 404
        )


class TestUpdateSetView(SessionBase):
    def test_update_aendert_gewicht(self):
        training = self._training()
        satz = self._satz(training, gewicht=80)
        self.client.post(
            reverse("update_set", args=[satz.id]),
            {
                "gewicht": "90",
                "wiederholungen": "8",
                "rpe": "",
            },
        )
        satz.refresh_from_db()
        self.assertAlmostEqual(float(satz.gewicht), 90.0)

    def test_update_fremder_satz_302_zu_dashboard(self):
        # BUG: update_set verschluckt Http404 durch äußeres except Exception
        # und redirectet zu dashboard (302) statt 404 zurückzugeben.
        # Test dokumentiert das tatsächliche Verhalten bis der Bug gefixt ist.
        other = User.objects.create_user(username="other_upd", password="pass1234")
        other_plan = Plan.objects.create(name="OP", user=other)
        other_t = Trainingseinheit.objects.create(user=other, plan=other_plan, dauer_minuten=30)
        fremder_satz = Satz.objects.create(
            einheit=other_t,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=50,
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )
        response = self.client.post(
            reverse("update_set", args=[fremder_satz.id]),
            {
                "gewicht": "999",
            },
        )
        # Aktuelles Verhalten: Http404 wird zu dashboard-Redirect
        self.assertEqual(response.status_code, 302)
        # Eigenes Gewicht darf NICHT geändert worden sein
        fremder_satz.refresh_from_db()
        self.assertAlmostEqual(float(fremder_satz.gewicht), 50.0)

    def test_login_required(self):
        self.client.logout()
        training = self._training()
        satz = self._satz(training)
        self.assertEqual(self.client.post(reverse("update_set", args=[satz.id])).status_code, 302)


class TestFinishTrainingView(SessionBase):
    def test_login_required(self):
        self.client.logout()
        t = self._training()
        self.assertEqual(self.client.post(reverse("finish_training", args=[t.id])).status_code, 302)

    def test_post_schliesst_training_ab(self):
        training = self._training()
        self._satz(training, gewicht=80, wdh=8, rpe=7.5)
        response = self.client.post(
            reverse("finish_training", args=[training.id]),
            {
                "notizen": "Gutes Training",
            },
        )
        self.assertEqual(response.status_code, 302)
        training.refresh_from_db()
        self.assertTrue(training.abgeschlossen)

    def test_fremdes_training_404(self):
        other = User.objects.create_user(username="other_fin", password="pass1234")
        other_plan = Plan.objects.create(name="OP", user=other)
        other_t = Trainingseinheit.objects.create(user=other, plan=other_plan, dauer_minuten=30)
        self.assertEqual(
            self.client.post(reverse("finish_training", args=[other_t.id])).status_code, 404
        )

    def test_fremdes_finish_veraendert_eigene_offene_session_nicht(self):
        other = User.objects.create_user(username="other_fin_2", password="pass1234")
        other_plan = Plan.objects.create(name="OP2", user=other)
        other_t = Trainingseinheit.objects.create(user=other, plan=other_plan, dauer_minuten=30)

        eigene_offen = self._training(abgeschlossen=False)

        response = self.client.post(reverse("finish_training", args=[other_t.id]), secure=True)
        self.assertEqual(response.status_code, 404)

        eigene_offen.refresh_from_db()
        self.assertFalse(eigene_offen.abgeschlossen)
