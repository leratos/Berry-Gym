"""
Tests für core/views/plan_management.py

Hilfsfunktionen (pure/near-pure):
  - _validate_cycle_params()
  - _ensure_gruppe_id()

Views (Django TestClient):
  - create_plan, edit_plan, delete_plan, copy_plan
  - toggle_plan_public, plan_library
  - set_active_plan_group
"""

import uuid

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.models import Equipment, Plan, PlanUebung, Uebung, UserProfile
from core.views.plan_management import _ensure_gruppe_id, _validate_cycle_params


# ─────────────────────────────────────────────────────────────────────────────
# Shared Fixtures
# ─────────────────────────────────────────────────────────────────────────────
class PlanBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="plan_user", password="pass1234")
        self.client.force_login(self.user)
        eq = Equipment.objects.create(name="HANTEL")
        self.uebung = Uebung.objects.create(
            bezeichnung="Kniebeuge",
            muskelgruppe="BEINE",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        self.uebung.equipment.add(eq)
        self.plan = Plan.objects.create(name="TestPlan", user=self.user)
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="8-12",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)


# ─────────────────────────────────────────────────────────────────────────────
# Pure Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────
class TestValidateCycleParams(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cv_user", password="pass1234")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.factory = RequestFactory()

    def _post(self, data):
        req = self.factory.post("/fake/", data=data)
        req.user = self.user
        return req

    def test_standard_zyklus(self):
        req = self._post({"cycle_length": "4"})
        result = _validate_cycle_params(req, self.profile)
        self.assertEqual(result, 4)
        self.assertEqual(self.profile.cycle_length, 4)

    def test_zu_kurz_wird_auf_2_geklemmt(self):
        result = _validate_cycle_params(self._post({"cycle_length": "1"}), self.profile)
        self.assertEqual(result, 2)

    def test_zu_lang_wird_auf_12_geklemmt(self):
        result = _validate_cycle_params(self._post({"cycle_length": "99"}), self.profile)
        self.assertEqual(result, 12)

    def test_ungueltig_fallback_auf_4(self):
        result = _validate_cycle_params(self._post({"cycle_length": "abc"}), self.profile)
        self.assertEqual(result, 4)

    def test_kein_parameter_fallback_auf_4(self):
        result = _validate_cycle_params(self._post({}), self.profile)
        self.assertEqual(result, 4)

    def test_deload_volume_factor_wird_gesetzt(self):
        req = self._post({"cycle_length": "4", "deload_volume_factor": "0.7"})
        _validate_cycle_params(req, self.profile)
        self.assertAlmostEqual(float(self.profile.deload_volume_factor), 0.7, places=5)

    def test_deload_factor_zu_niedrig_geklemmt(self):
        req = self._post({"cycle_length": "4", "deload_volume_factor": "0.1"})
        _validate_cycle_params(req, self.profile)
        self.assertGreaterEqual(float(self.profile.deload_volume_factor), 0.5)

    def test_deload_faktor_ungueltig_bleibt_unveraendert(self):
        old_val = self.profile.deload_volume_factor
        req = self._post({"cycle_length": "4", "deload_volume_factor": "abc"})
        _validate_cycle_params(req, self.profile)
        self.assertEqual(self.profile.deload_volume_factor, old_val)


class TestEnsureGruppeId(PlanBase):
    def test_plan_ohne_gruppe_bekommt_neue_id(self):
        plan = Plan.objects.create(name="Einzelplan", user=self.user)
        self.assertFalse(plan.gruppe_id)
        gruppe_id = _ensure_gruppe_id(plan)
        self.assertTrue(gruppe_id)
        self.assertIsInstance(uuid.UUID(gruppe_id), uuid.UUID)

    def test_plan_mit_gruppe_unveraendert(self):
        fixed_id = uuid.uuid4()
        self.plan.gruppe_id = fixed_id
        self.plan.save()
        result = _ensure_gruppe_id(self.plan)
        self.assertEqual(result, str(fixed_id))

    def test_gruppe_name_wird_aus_plan_name_gesetzt(self):
        plan = Plan.objects.create(name="MeinPlan", user=self.user)
        _ensure_gruppe_id(plan)
        plan.refresh_from_db()
        self.assertEqual(plan.gruppe_name, "MeinPlan")


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────
class TestCreatePlanView(PlanBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("create_plan")).status_code, 302)

    def test_get_zeigt_formular(self):
        self.assertEqual(self.client.get(reverse("create_plan")).status_code, 200)

    def test_post_erstellt_plan(self):
        response = self.client.post(
            reverse("create_plan"),
            {
                "name": "Neuer Plan",
                "beschreibung": "Test",
                "uebungen": [str(self.uebung.id)],
                f"saetze_{self.uebung.id}": "4",
                f"wdh_{self.uebung.id}": "6-10",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Plan.objects.filter(name="Neuer Plan", user=self.user).exists())

    def test_post_ohne_name_kein_plan(self):
        count_vor = Plan.objects.filter(user=self.user).count()
        self.client.post(
            reverse("create_plan"),
            {
                "name": "",
                "uebungen": [str(self.uebung.id)],
            },
        )
        self.assertEqual(Plan.objects.filter(user=self.user).count(), count_vor)

    def test_post_ohne_uebungen_kein_plan(self):
        count_vor = Plan.objects.filter(user=self.user).count()
        self.client.post(reverse("create_plan"), {"name": "Nur Name"})
        self.assertEqual(Plan.objects.filter(user=self.user).count(), count_vor)


class TestEditPlanView(PlanBase):
    def test_login_required(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("edit_plan", args=[self.plan.id])).status_code, 302
        )

    def test_get_zeigt_plan(self):
        self.assertEqual(
            self.client.get(reverse("edit_plan", args=[self.plan.id])).status_code, 200
        )

    def test_post_aendert_name(self):
        self.client.post(
            reverse("edit_plan", args=[self.plan.id]),
            {
                "name": "Geänderter Name",
                "beschreibung": "",
            },
        )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.name, "Geänderter Name")

    def test_fremder_plan_404(self):
        other = User.objects.create_user(username="other2", password="pass1234")
        fremder = Plan.objects.create(name="Fremd", user=other)
        self.assertEqual(self.client.get(reverse("edit_plan", args=[fremder.id])).status_code, 404)


class TestDeletePlanView(PlanBase):
    def test_post_loescht_eigenen_plan(self):
        plan_id = self.plan.id
        response = self.client.post(reverse("delete_plan", args=[plan_id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Plan.objects.filter(id=plan_id).exists())

    def test_fremden_plan_loeschen_404(self):
        other = User.objects.create_user(username="other3", password="pass1234")
        fremder = Plan.objects.create(name="Fremd", user=other)
        self.assertEqual(
            self.client.post(reverse("delete_plan", args=[fremder.id])).status_code, 404
        )

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(
            self.client.post(reverse("delete_plan", args=[self.plan.id])).status_code, 302
        )


class TestCopyPlanView(PlanBase):
    def test_kopiert_eigenen_plan(self):
        count_vor = Plan.objects.filter(user=self.user).count()
        response = self.client.post(reverse("copy_plan", args=[self.plan.id]))
        self.assertEqual(response.status_code, 302)
        self.assertGreater(Plan.objects.filter(user=self.user).count(), count_vor)

    def test_fremden_plan_kopieren_404(self):
        other = User.objects.create_user(username="other4", password="pass1234")
        fremder = Plan.objects.create(name="Fremd", user=other)
        self.assertEqual(self.client.post(reverse("copy_plan", args=[fremder.id])).status_code, 404)


class TestTogglePlanPublicView(PlanBase):
    def test_toggle_macht_plan_public(self):
        self.assertFalse(self.plan.is_public)
        self.client.post(reverse("toggle_plan_public", args=[self.plan.id]))
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_public)

    def test_toggle_zweimal_macht_plan_wieder_privat(self):
        self.client.post(reverse("toggle_plan_public", args=[self.plan.id]))
        self.client.post(reverse("toggle_plan_public", args=[self.plan.id]))
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.is_public)


class TestPlanLibraryView(PlanBase):
    def test_oeffentlich_zugaenglich_ohne_login(self):
        # plan_library hat kein @login_required – öffentliche Seite
        self.client.logout()
        self.assertEqual(self.client.get(reverse("plan_library")).status_code, 200)

    def test_get_200(self):
        self.assertEqual(self.client.get(reverse("plan_library")).status_code, 200)

    def test_zeigt_oeffentliche_plaene(self):
        other = User.objects.create_user(username="pub_user", password="pass1234")
        Plan.objects.create(name="Öffentlich", user=other, is_public=True)
        response = self.client.get(reverse("plan_library"))
        self.assertEqual(response.status_code, 200)


class TestSetActivePlanGroupView(PlanBase):
    def test_get_200(self):
        self.assertEqual(self.client.get(reverse("set_active_plan_group")).status_code, 200)

    def test_post_setzt_gruppe_bei_einzelplan(self):
        response = self.client.post(
            reverse("set_active_plan_group"),
            {
                "gruppe_id": "",
                "plan_id": str(self.plan.id),
                "cycle_length": "4",
            },
        )
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.active_plan_group)

    def test_post_entfernt_gruppe_wenn_leer(self):
        self.profile.active_plan_group = uuid.uuid4()
        self.profile.save()
        self.client.post(
            reverse("set_active_plan_group"),
            {
                "gruppe_id": "",
                "plan_id": "",
                "cycle_length": "4",
            },
        )
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.active_plan_group)
