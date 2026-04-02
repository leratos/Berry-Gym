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

import json
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Equipment, Plan, PlanUebung, Satz, Trainingseinheit, Uebung, UserProfile
from core.views.training_session import (
    _build_ai_suggestions,
    _build_empfehlung_from_satz,
    _build_intensity_suggestion,
    _build_plan_gruppen,
    _build_volume_suggestion,
    _calculate_empfohlene_pause,
    _calculate_single_empfehlung,
    _check_pr,
    _create_ghost_saetze,
    _determine_empfehlung_hint,
    _get_ai_training_suggestion,
    _get_deload_config,
    _get_gewichts_empfehlungen,
    _get_plan_ziele,
    _get_rpe_adjusted_weights,
    _get_sorted_saetze,
    _parse_set_post_data,
    _parse_ziel_wdh,
    finish_training,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared Fixtures
# ─────────────────────────────────────────────────────────────────────────────
class SessionBase(TestCase):
    def setUp(self):
        self.client.defaults["HTTP_X_FORWARDED_PROTO"] = "https"
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

    def test_max_wdh_bei_rpe_ueber_ziel_gewicht_halten(self):
        """Max-Wdh erreicht aber RPE 10 > Ziel 8 → Gewicht halten."""
        s = self._satz(gewicht=80.0, wdh=12, rpe=10.0)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12, rpe_ziel=8.0)
        self.assertEqual(g, 80.0)
        self.assertIn("Gewicht halten", hint)

    def test_max_wdh_bei_rpe_im_ziel_gewicht_hoch(self):
        """Max-Wdh erreicht bei RPE 7.5 ≤ Ziel 8 → Gewicht erhöhen."""
        s = self._satz(gewicht=80.0, wdh=12, rpe=7.5)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12, rpe_ziel=8.0)
        self.assertAlmostEqual(g, 82.5)
        self.assertIn("+2.5kg", hint)

    def test_max_wdh_rpe_gleich_ziel_gewicht_hoch(self):
        """Max-Wdh bei RPE == Ziel → Gewicht erhöhen (Grenzwert)."""
        s = self._satz(gewicht=80.0, wdh=12, rpe=8.0)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12, rpe_ziel=8.0)
        self.assertAlmostEqual(g, 82.5)
        self.assertIn("+2.5kg", hint)

    def test_max_wdh_rpe9_bei_kraftziel_rpe9_gewicht_hoch(self):
        """Kraft-Plan mit Ziel-RPE 9: RPE 9 → Gewicht erhöhen."""
        s = self._satz(gewicht=100.0, wdh=6, rpe=9.0)
        g, w, hint = _determine_empfehlung_hint(s, 4, 6, rpe_ziel=9.0)
        self.assertAlmostEqual(g, 102.5)
        self.assertIn("+2.5kg", hint)

    def test_default_rpe_ziel_ohne_plan(self):
        """Ohne Plan-RPE wird Default 8.5 verwendet. RPE 9.0 > 8.5 → halten."""
        s = self._satz(gewicht=80.0, wdh=12, rpe=9.0)
        g, w, hint = _determine_empfehlung_hint(s, 8, 12)
        self.assertEqual(g, 80.0)
        self.assertIn("Gewicht halten", hint)


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

    def test_post_invalid_dauer_keine_abschluss_markierung(self):
        training = self._training(abgeschlossen=False)

        response = self.client.post(
            reverse("finish_training", args=[training.id]),
            {
                "dauer_minuten": "abc",
                "kommentar": "test",
            },
        )

        self.assertEqual(response.status_code, 200)
        training.refresh_from_db()
        self.assertFalse(training.abgeschlossen)

    def test_post_dauer_ausserhalb_bereich_keine_abschluss_markierung(self):
        training = self._training(abgeschlossen=False)

        response = self.client.post(
            reverse("finish_training", args=[training.id]),
            {
                "dauer_minuten": "2000",
            },
        )

        self.assertEqual(response.status_code, 200)
        training.refresh_from_db()
        self.assertFalse(training.abgeschlossen)

    def test_post_valid_dauer_setzt_dauer(self):
        training = self._training(abgeschlossen=False)

        response = self.client.post(
            reverse("finish_training", args=[training.id]),
            {
                "dauer_minuten": "55",
                "kommentar": "Sauber",
            },
        )

        self.assertEqual(response.status_code, 302)
        training.refresh_from_db()
        self.assertEqual(training.dauer_minuten, 55)


class TestTrainingSessionExtendedCoverage(SessionBase):
    def test_active_group_name_fallback_and_missing_profile(self):
        import uuid

        gid = uuid.uuid4()
        self.plan.gruppe_id = gid
        self.plan.gruppe_name = ""
        self.plan.save(update_fields=["gruppe_id", "gruppe_name"])

        profile = self.user.profile
        profile.active_plan_group = gid
        profile.save(update_fields=["active_plan_group"])

        response = self.client.get(reverse("training_select_plan"))
        self.assertEqual(response.context["active_group_name"], "Unbenannte Gruppe")

        self.user.profile.delete()
        response_no_profile = self.client.get(reverse("training_select_plan"))
        self.assertEqual(response_no_profile.status_code, 200)

    def test_training_select_plan_public_filter_redirectet(self):
        response = self.client.get(reverse("training_select_plan"), {"filter": "public"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("filter=eigene", response.url)

    def test_training_select_plan_shared_filter_zeigt_geteilte_plaene(self):
        owner = User.objects.create_user(username="owner_shared", password="pass1234")
        shared_plan = Plan.objects.create(name="Shared Plan", user=owner)
        shared_plan.shared_with.add(self.user)

        response = self.client.get(reverse("training_select_plan"), {"filter": "shared"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(shared_plan, response.context["einzelne_plaene"])

    def test_training_select_plan_active_group_ohne_plan_setzt_reset(self):
        import uuid

        profile = self.user.profile
        profile.active_plan_group = uuid.uuid4()
        profile.save(update_fields=["active_plan_group"])

        response = self.client.get(reverse("training_select_plan"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_group_name"], None)
        self.assertEqual(len(response.context["active_plan_gruppen"]), 0)

    def test_plan_details_zeigt_historie_und_owner_flag(self):
        alte_einheit = self._training(days_ago=3)
        Satz.objects.create(
            einheit=alte_einheit,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=85,
            wiederholungen=9,
            ist_aufwaermsatz=False,
        )

        response = self.client.get(reverse("plan_details", args=[self.plan.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_owner"])
        self.assertEqual(len(response.context["uebungen_mit_historie"]), 1)
        self.assertIsNotNone(response.context["uebungen_mit_historie"][0]["letztes_gewicht"])

    def test_get_deload_config_defaults_und_active_group(self):
        import uuid

        self.user.profile.delete()
        is_deload, vol_factor, weight_factor, rpe_target = _get_deload_config(self.user, self.plan)
        self.assertEqual((is_deload, vol_factor, weight_factor, rpe_target), (False, 0.8, 0.9, 7.0))

        gid = uuid.uuid4()
        self.plan.gruppe_id = gid
        self.plan.gruppe_name = "Split"
        self.plan.save(update_fields=["gruppe_id", "gruppe_name"])

        profile = UserProfile.objects.create(user=self.user, active_plan_group=gid)
        profile.deload_volume_factor = 0.7
        profile.deload_weight_factor = 0.85
        profile.deload_rpe_target = 6.5
        profile.save()

        with patch.object(UserProfile, "is_deload_week", return_value=True):
            is_deload, vol_factor, weight_factor, rpe_target = _get_deload_config(
                self.user, self.plan
            )

        self.assertEqual((is_deload, vol_factor, weight_factor, rpe_target), (True, 0.7, 0.85, 6.5))
        profile.refresh_from_db()
        self.assertIsNotNone(profile.cycle_start_date)

    def test_get_deload_config_handles_missing_profile_exception(self):
        self.user.profile.delete()
        self.user.__dict__.pop("profile", None)

        with patch.object(User, "profile", new_callable=PropertyMock) as mock_profile:
            mock_profile.side_effect = UserProfile.DoesNotExist
            result = _get_deload_config(self.user, self.plan)

        self.assertEqual(result, (False, 0.8, 0.9, 7.0))

    def test_get_sorted_saetze_and_plan_ziele(self):
        training = self._training()
        second = Uebung.objects.create(
            bezeichnung="Rudern",
            muskelgruppe="RÜCKEN",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=second,
            reihenfolge=2,
            saetze_ziel=4,
            wiederholungen_ziel="6-8",
        )
        Satz.objects.create(
            einheit=training,
            uebung=second,
            satz_nr=1,
            gewicht=70,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=2,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )

        sorted_saetze = list(_get_sorted_saetze(training))
        self.assertEqual(sorted_saetze[0].uebung_id, self.uebung.id)

        plan_ziele = _get_plan_ziele(training)
        self.assertEqual(plan_ziele[self.uebung.id]["saetze_ziel"], 3)
        self.assertEqual(plan_ziele[second.id]["wiederholungen_ziel"], "6-8")

        training.plan = None
        training.save(update_fields=["plan"])
        sorted_no_plan = list(_get_sorted_saetze(training))
        self.assertGreaterEqual(len(sorted_no_plan), 2)

    def test_create_ghost_saetze_deload_and_fallback_paths(self):
        training = Trainingseinheit.objects.create(user=self.user, plan=self.plan, dauer_minuten=40)
        old = self._training(days_ago=5)
        Satz.objects.create(
            einheit=old,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=100,
            wiederholungen=7,
            ist_aufwaermsatz=False,
        )
        Satz.objects.create(
            einheit=old,
            uebung=self.uebung,
            satz_nr=2,
            gewicht=90,
            wiederholungen=6,
            ist_aufwaermsatz=False,
        )

        pu = self.plan.uebungen.get(uebung=self.uebung)
        pu.wiederholungen_ziel = "abc"
        pu.saetze_ziel = 3
        pu.save(update_fields=["wiederholungen_ziel", "saetze_ziel"])

        _create_ghost_saetze(
            training, self.plan, is_deload=True, deload_vol_factor=0.6, deload_weight_factor=0.8
        )
        created = list(training.saetze.filter(uebung=self.uebung).order_by("satz_nr"))
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].wiederholungen, 6)

    def test_training_start_deload_message_branch(self):
        with patch(
            "core.views.training_session._get_deload_config", return_value=(True, 0.5, 0.8, 6.5)
        ):
            response = self.client.get(reverse("training_start_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)
        # Verify ist_deload flag is persisted on the training
        training = Trainingseinheit.objects.filter(user=self.user).order_by("-datum").first()
        self.assertTrue(training.ist_deload, "ist_deload should be True when deload week is active")

    def test_training_start_non_deload_flag_false(self):
        """Wenn KEIN Deload: ist_deload muss False bleiben."""
        with patch(
            "core.views.training_session._get_deload_config", return_value=(False, 0.8, 0.9, 7.0)
        ):
            response = self.client.get(reverse("training_start_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)
        training = Trainingseinheit.objects.filter(user=self.user).order_by("-datum").first()
        self.assertFalse(training.ist_deload, "ist_deload should be False for normal training")

    def test_determine_empfehlung_hint_kg_low_rpe_plus2(self):
        satz = MagicMock()
        satz.gewicht = 0
        satz.wiederholungen = 8
        satz.rpe = 6.0

        _, reps, hint = _determine_empfehlung_hint(satz, 8, 12, is_kg_uebung=True)
        self.assertEqual(reps, 10)
        self.assertIn("+2 Wdh", hint)

    def test_calculate_single_empfehlung_and_batch_empfehlungen(self):
        training = self._training()
        alt = self._training(days_ago=7)
        Satz.objects.create(
            einheit=alt,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=90,
            wiederholungen=8,
            rpe=6.5,
            ist_aufwaermsatz=False,
        )

        PlanUebung.objects.filter(plan=self.plan, uebung=self.uebung).update(
            wiederholungen_ziel="8-12", pausenzeit=150
        )

        single = _calculate_single_empfehlung(self.user, self.uebung.id, training)
        self.assertIsNotNone(single)
        self.assertEqual(single["pause"], 150)
        self.assertTrue(single["pause_from_plan"])

        Satz.objects.create(
            einheit=training,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        recommendations = _get_gewichts_empfehlungen(self.user, training)
        self.assertIn(self.uebung.id, recommendations)

        empty_training = Trainingseinheit.objects.create(
            user=self.user, plan=None, dauer_minuten=30
        )
        self.assertEqual(_get_gewichts_empfehlungen(self.user, empty_training), {})

    def test_calculate_single_empfehlung_none_and_missing_uebung_lookup(self):
        training = self._training()
        no_history = _calculate_single_empfehlung(self.user, self.uebung.id, training)
        self.assertIsNone(no_history)

        old = self._training(days_ago=2)
        Satz.objects.create(
            einheit=old,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            rpe=7.0,
            ist_aufwaermsatz=False,
        )
        with patch("core.models.Uebung.objects.get", side_effect=Uebung.DoesNotExist):
            result = _calculate_single_empfehlung(self.user, self.uebung.id, training)
        self.assertIsNotNone(result)

    def test_build_empfehlung_from_satz_kg_uebung(self):
        kg = Uebung.objects.create(
            bezeichnung="Klimmzug",
            muskelgruppe="RÜCKEN",
            bewegungstyp="ZIEHEN",
            gewichts_typ="KOERPERGEWICHT",
        )
        pu = PlanUebung.objects.create(
            plan=self.plan,
            uebung=kg,
            reihenfolge=3,
            saetze_ziel=3,
            wiederholungen_ziel="6-10",
            pausenzeit=90,
        )
        training = self._training(days_ago=1)
        letzter_satz = Satz.objects.create(
            einheit=training,
            uebung=kg,
            satz_nr=1,
            gewicht=0,
            wiederholungen=10,
            rpe=8.0,
            ist_aufwaermsatz=False,
        )

        data = _build_empfehlung_from_satz(letzter_satz, pu)
        self.assertEqual(data["gewicht"], 0.0)
        self.assertIn("nächste Stufe", data["hint"])
        self.assertEqual(data["pause"], 90)

    def test_training_session_context_includes_hinweise(self):
        training = self._training()
        pu = self.plan.uebungen.get(uebung=self.uebung)
        pu.notiz = "Schulterblätter stabil halten"
        pu.save(update_fields=["notiz"])
        self._satz(training, gewicht=80, wdh=8, rpe=7.0)

        response = self.client.get(reverse("training_session", args=[training.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.uebung.id, response.context["plan_uebung_hinweise"])

    def test_training_session_handles_missing_profile_exception(self):
        training = self._training()
        self.user.profile.delete()
        self.user.__dict__.pop("profile", None)

        with patch.object(User, "profile", new_callable=PropertyMock) as mock_profile:
            mock_profile.side_effect = UserProfile.DoesNotExist
            response = self.client.get(reverse("training_session", args=[training.id]))

        self.assertEqual(response.status_code, 200)

    def test_update_set_ajax_validation_and_unexpected_error(self):
        training = self._training()
        satz = self._satz(training)

        bad = self.client.post(
            reverse("update_set", args=[satz.id]),
            {"gewicht": "abc"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(bad.status_code, 400)

        with patch(
            "core.views.training_session.get_object_or_404", side_effect=RuntimeError("boom")
        ):
            error = self.client.post(
                reverse("update_set", args=[satz.id]),
                {"gewicht": "80"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(error.status_code, 500)

    def test_update_set_ajax_success_and_nonajax_validation_redirect(self):
        training = self._training()
        satz = self._satz(training)

        ok = self.client.post(
            reverse("update_set", args=[satz.id]),
            {"gewicht": "85", "wiederholungen": "8", "rpe": "7.5", "superset_gruppe": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["success"])

        invalid = self.client.post(
            reverse("update_set", args=[satz.id]),
            {"gewicht": "abc"},
        )
        self.assertEqual(invalid.status_code, 302)

    def test_update_set_get_redirects(self):
        training = self._training()
        satz = self._satz(training)
        response = self.client.get(reverse("update_set", args=[satz.id]))
        self.assertEqual(response.status_code, 302)

    def test_toggle_deload_branches(self):
        training = self._training()

        valid = self.client.post(
            reverse("toggle_deload", args=[training.id]),
            data=json.dumps({"ist_deload": True}),
            content_type="application/json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.json()["ist_deload"])

        invalid = self.client.post(
            reverse("toggle_deload", args=[training.id]),
            data=json.dumps({"ist_deload": "ja"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)

        malformed = self.client.post(
            reverse("toggle_deload", args=[training.id]),
            data="{broken",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)

        with patch(
            "core.views.training_session.Trainingseinheit.save", side_effect=RuntimeError("boom")
        ):
            server_error = self.client.post(
                reverse("toggle_deload", args=[training.id]),
                data=json.dumps({"ist_deload": False}),
                content_type="application/json",
            )
        self.assertEqual(server_error.status_code, 500)

    def test_volume_and_ai_suggestion_helpers(self):
        trainings = [self._training(days_ago=d, abgeschlossen=True) for d in [1, 3, 5, 8, 10, 12]]
        for idx, t in enumerate(trainings, start=1):
            gewicht = 40 if idx <= 3 else 100
            Satz.objects.create(
                einheit=t,
                uebung=self.uebung,
                satz_nr=1,
                gewicht=gewicht,
                wiederholungen=8,
                rpe=7.0 if idx < 4 else 9.0,
                ist_aufwaermsatz=False,
            )

        recent_ids = [t.id for t in trainings[:3]]
        recent_sets = Satz.objects.filter(einheit_id__in=recent_ids, ist_aufwaermsatz=False)

        volume = _build_volume_suggestion(self.user, recent_ids, recent_sets)
        if volume is not None:
            self.assertEqual(volume["type"], "volume")

        suggestions = _build_ai_suggestions(self.user, recent_ids, recent_sets, avg_rpe=9.1)
        self.assertGreaterEqual(len(suggestions), 1)

    def test_build_volume_suggestion_drop_and_rise_with_mocks(self):
        previous_ids_chain = MagicMock()
        previous_ids_chain.order_by.return_value.values_list.return_value.__getitem__.return_value = [
            10,
            11,
            12,
        ]

        with patch(
            "core.views.training_session.Trainingseinheit.objects.filter",
            return_value=previous_ids_chain,
        ):
            with patch("core.views.training_session.Satz.objects.filter") as satz_filter:

                def drop_side_effect(*args, **kwargs):
                    m = MagicMock()
                    ids = kwargs.get("einheit_id__in", [])
                    m.aggregate.return_value = {"total": 100 if ids == [1, 2, 3] else 200}
                    return m

                satz_filter.side_effect = drop_side_effect
                drop = _build_volume_suggestion(self.user, [1, 2, 3], MagicMock())
                self.assertEqual(drop["type"], "volume")
                self.assertEqual(drop["color"], "danger")

                def rise_side_effect(*args, **kwargs):
                    m = MagicMock()
                    ids = kwargs.get("einheit_id__in", [])
                    m.aggregate.return_value = {"total": 300 if ids == [1, 2, 3] else 100}
                    return m

                satz_filter.side_effect = rise_side_effect
                rise = _build_volume_suggestion(self.user, [1, 2, 3], MagicMock())
                self.assertEqual(rise["type"], "volume")
                self.assertEqual(rise["color"], "warning")

                def neutral_side_effect(*args, **kwargs):
                    m = MagicMock()
                    m.aggregate.return_value = {"total": 100}
                    return m

                satz_filter.side_effect = neutral_side_effect
                neutral = _build_volume_suggestion(self.user, [1, 2, 3], MagicMock())
                self.assertIsNone(neutral)

                def zero_prev_side_effect(*args, **kwargs):
                    m = MagicMock()
                    ids = kwargs.get("einheit_id__in", [])
                    m.aggregate.return_value = {"total": 100 if ids == [1, 2, 3] else 0}
                    return m

                satz_filter.side_effect = zero_prev_side_effect
                zero_prev = _build_volume_suggestion(self.user, [1, 2, 3], MagicMock())
                self.assertIsNone(zero_prev)

    def test_get_ai_training_suggestion_branches(self):
        none_result, count = _get_ai_training_suggestion(self.user)
        self.assertIsNone(none_result)
        self.assertEqual(count, 0)

        for d in [1, 3, 5]:
            t = self._training(days_ago=d, abgeschlossen=True)
            Satz.objects.create(
                einheit=t,
                uebung=self.uebung,
                satz_nr=1,
                gewicht=80,
                wiederholungen=8,
                rpe=8.0,
                ist_aufwaermsatz=False,
            )

        with patch(
            "core.views.training_session._build_ai_suggestions",
            return_value=[
                {"color": "info", "type": "x"},
                {"color": "danger", "type": "y"},
            ],
        ):
            ai_suggestion, training_count = _get_ai_training_suggestion(self.user)

        self.assertEqual(training_count, 3)
        self.assertEqual(ai_suggestion["color"], "danger")

    def test_get_ai_training_suggestion_three_trainings_without_rpe(self):
        # Sätze ohne RPE → avg_rpe=None → kein Intensitäts-Vorschlag
        # Aber: nur 1 Übung (< 5) → Variety-Vorschlag wird geliefert
        for d in [1, 3, 5]:
            t = self._training(days_ago=d, abgeschlossen=True)
            Satz.objects.create(
                einheit=t,
                uebung=self.uebung,
                satz_nr=1,
                gewicht=80,
                wiederholungen=8,
                rpe=None,
                ist_aufwaermsatz=False,
            )

        suggestion, count = _get_ai_training_suggestion(self.user)
        # Variety-Vorschlag erwartet (1 Übung < 5), kein Intensitäts-Vorschlag (kein RPE)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["type"], "variety")
        self.assertEqual(count, 3)

    def test_finish_training_dauer_fallback_when_datum_missing(self):
        request = RequestFactory().get("/training/1/finish/")
        request.user = self.user

        fake_arbeit = MagicMock()
        fake_arbeit.count.return_value = 0
        fake_arbeit.__iter__.return_value = iter([])
        fake_warmup = MagicMock()
        fake_warmup.count.return_value = 0
        fake_prs = MagicMock()
        fake_prs.select_related.return_value.order_by.return_value = []

        fake_saetze_manager = MagicMock()
        fake_saetze_manager.filter.side_effect = [fake_arbeit, fake_warmup, fake_prs]
        fake_saetze_manager.values.return_value.distinct.return_value.count.return_value = 0

        fake_training = MagicMock()
        fake_training.saetze = fake_saetze_manager
        fake_training.datum = None
        fake_training.dauer_minuten = None  # kein gespeicherter Wert → historisch ohne Datum

        captured = {}

        def _fake_render(req, template, context):
            captured.update(context)
            return HttpResponse("ok")

        with (
            patch("core.views.training_session.get_object_or_404", return_value=fake_training),
            patch(
                "core.views.training_session._get_ai_training_suggestion", return_value=(None, 0)
            ),
            patch("core.views.training_session.render", side_effect=_fake_render),
        ):
            response = finish_training(request, training_id=1)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            captured["dauer_geschaetzt"]
        )  # historisch + kein Datum → None statt Fallback 60


# ─────────────────────────────────────────────────────────────────────────────
# Phase 18: RPE-korrigierte Startgewichte
# ─────────────────────────────────────────────────────────────────────────────


class TestRpeAdjustedWeights(SessionBase):
    """Phase 18: _get_rpe_adjusted_weights berechnet RPE-korrigierte Startgewichte."""

    def _create_history_sets(self, rpe_values, gewicht=80):
        """Erstellt historische Sätze mit gegebenem RPE."""
        for i, rpe_val in enumerate(rpe_values):
            t = self._training(abgeschlossen=True, days_ago=i + 1)
            self._satz(t, gewicht=gewicht, wdh=8, rpe=rpe_val)

    def test_keine_historie_gibt_leeres_dict(self):
        plan_ue_map = {self.uebung.id: self.plan.uebungen.first()}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertEqual(result, {})

    def test_weniger_als_3_saetze_gibt_leeres_dict(self):
        """Mindestens 3 historische RPE-Sätze nötig."""
        self._create_history_sets([9.0, 9.5])
        plan_ue_map = {self.uebung.id: self.plan.uebungen.first()}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertEqual(result, {})

    def test_rpe_unter_ziel_keine_empfehlung(self):
        """Wenn Avg-RPE ≤ Ziel-RPE → keine Reduktion nötig."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 9.0
        pu.save()
        self._create_history_sets([8.0, 8.5, 7.5])
        plan_ue_map = {self.uebung.id: pu}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertEqual(result, {})

    def test_rpe_ueber_ziel_reduktion(self):
        """Avg-RPE 9.5, Ziel-RPE 8.0 → 1.5 Punkte × 2.5% = 3.75% Reduktion."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 8.0
        pu.save()
        self._create_history_sets([9.5, 9.5, 9.5], gewicht=80)
        plan_ue_map = {self.uebung.id: pu}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertIn(self.uebung.id, result)
        empf = result[self.uebung.id]
        # 80 * (1 - 1.5*0.025) = 80 * 0.9625 = 77.0 → gerundet auf 1.25: 77.5
        self.assertEqual(empf["empfohlen_kg"], 77.5)
        self.assertEqual(empf["ziel_rpe"], 8.0)
        self.assertEqual(empf["avg_rpe"], 9.5)

    def test_max_20_prozent_reduktion(self):
        """RPE-Differenz > 8 Punkte → max 20% Reduktion."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 1.0
        pu.save()
        self._create_history_sets([10.0, 10.0, 10.0], gewicht=100)
        plan_ue_map = {self.uebung.id: pu}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        empf = result[self.uebung.id]
        # Max 20% Reduktion: 100 * 0.8 = 80 kg
        self.assertEqual(empf["empfohlen_kg"], 80.0)

    def test_kein_rpe_ziel_keine_empfehlung(self):
        """Wenn PlanUebung kein rpe_ziel hat → keine Empfehlung."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = None
        pu.save()
        self._create_history_sets([9.5, 9.5, 9.5])
        plan_ue_map = {self.uebung.id: pu}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertEqual(result, {})

    def test_aufwaermsaetze_werden_ignoriert(self):
        """Warmup-Sätze zählen nicht für RPE-Historie."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 8.0
        pu.save()
        # 3 Warmup-Sätze + 2 Arbeitssätze = nur 2 gültige → unter Minimum
        for i in range(3):
            t = self._training(abgeschlossen=True, days_ago=i + 1)
            Satz.objects.create(
                einheit=t,
                uebung=self.uebung,
                satz_nr=1,
                gewicht=80,
                wiederholungen=8,
                rpe=9.5,
                ist_aufwaermsatz=True,
            )
        for i in range(2):
            t = self._training(abgeschlossen=True, days_ago=i + 4)
            self._satz(t, gewicht=80, wdh=8, rpe=9.5)
        plan_ue_map = {self.uebung.id: pu}
        result = _get_rpe_adjusted_weights(self.user, [self.uebung.id], plan_ue_map)
        self.assertEqual(result, {})

    def test_ghost_saetze_nutzen_rpe_adjusted_weight(self):
        """Ghost-Sätze verwenden RPE-korrigiertes Gewicht statt letztem Gewicht."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 8.0
        pu.save()
        self._create_history_sets([9.5, 9.5, 9.5], gewicht=80)

        training = Trainingseinheit.objects.create(user=self.user, plan=self.plan)
        _create_ghost_saetze(
            training, self.plan, is_deload=False, deload_vol_factor=0.8, deload_weight_factor=0.9
        )

        ghost = training.saetze.filter(uebung=self.uebung).first()
        self.assertIsNotNone(ghost)
        # Sollte RPE-adjustiert sein: 77.5 kg statt 80 kg
        self.assertEqual(float(ghost.gewicht), 77.5)

    def test_plan_details_zeigt_empfehlung(self):
        """Plan-Details-View enthält rpe_empfehlung im Context."""
        pu = self.plan.uebungen.first()
        pu.rpe_ziel = 8.0
        pu.save()
        self._create_history_sets([9.5, 9.5, 9.5], gewicht=80)

        response = self.client.get(reverse("plan_details", args=[self.plan.id]), secure=True)
        self.assertEqual(response.status_code, 200)
        items = response.context["uebungen_mit_historie"]
        self.assertEqual(len(items), 1)
        self.assertIsNotNone(items[0]["rpe_empfehlung"])
        self.assertEqual(items[0]["rpe_empfehlung"]["empfohlen_kg"], 77.5)
