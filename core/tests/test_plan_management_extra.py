"""
Tests für fehlende Abdeckung in core/views/plan_management.py

Abdeckung:
- duplicate_plan: Duplikat des eigenen Plans
- duplicate_group: Duplikat einer Plan-Gruppe
- share_plan: für Owner und Nicht-Owner
- share_group: für Owner und Nicht-Owner, nicht gefundene Gruppe
- plan_library: Suche, Gruppen-Gruppierung, leere Bibliothek
- plan_library_group: Gruppe gefunden, nicht gefunden
- copy_group: öffentliche Gruppe kopieren, nicht gefunden
- toggle_group_public: Ein-/Ausschalten für gesamte Gruppe
- set_active_plan_group: GET und POST (Gruppe setzen/entfernen, Einzelplan)
- _start_new_trainingsblock: Trainingsblock-Erstellung
- _apply_gruppe_selection: Gruppe setzen mit und ohne Block-Typ
"""

import uuid

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import Plan, PlanUebung, Trainingsblock, Uebung, UserProfile
from core.tests.factories import PlanFactory, PlanUebungFactory, UebungFactory, UserFactory

# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────


def _create_gruppe(user, n_plaene=2, is_public=False):
    """Erstellt eine Plan-Gruppe mit n_plaene Plänen."""
    gruppe_id = uuid.uuid4()
    gruppe_name = f"Testgruppe {gruppe_id}"
    uebung = UebungFactory()
    plaene = []
    for i in range(n_plaene):
        plan = PlanFactory(
            user=user,
            gruppe_id=gruppe_id,
            gruppe_name=gruppe_name,
            gruppe_reihenfolge=i,
            is_public=is_public,
        )
        PlanUebungFactory(plan=plan, uebung=uebung)
        plaene.append(plan)
    return gruppe_id, gruppe_name, plaene


# ─────────────────────────────────────────────────────────────────────────────
# duplicate_plan
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDuplicatePlan:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)
        self.uebung = UebungFactory()
        self.plan = PlanFactory(user=self.user, name="Original")
        PlanUebungFactory(plan=self.plan, uebung=self.uebung)

    def test_dupliziert_eigenen_plan(self):
        response = self.client.post(reverse("duplicate_plan", kwargs={"plan_id": self.plan.id}))
        assert response.status_code == 302
        assert Plan.objects.filter(user=self.user, name__contains="Kopie").exists()

    def test_kopie_hat_selbe_uebungen(self):
        self.client.post(reverse("duplicate_plan", kwargs={"plan_id": self.plan.id}))
        kopie = Plan.objects.filter(user=self.user, name__contains="Kopie").first()
        assert kopie is not None
        assert kopie.uebungen.count() == 1

    def test_fremden_plan_gibt_404(self):
        anderer = UserFactory()
        fremder_plan = PlanFactory(user=anderer)
        response = self.client.post(reverse("duplicate_plan", kwargs={"plan_id": fremder_plan.id}))
        assert response.status_code == 404

    def test_login_required(self):
        client = Client()
        url = reverse("duplicate_plan", kwargs={"plan_id": self.plan.id})
        response = client.post(url)
        assert response.status_code == 302
        assert "/login" in response.url or "/en/" in response.url


# ─────────────────────────────────────────────────────────────────────────────
# duplicate_group
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDuplicateGroup:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_dupliziert_gruppe(self):
        gruppe_id, gruppe_name, _ = _create_gruppe(self.user, n_plaene=2)
        response = self.client.post(
            reverse("duplicate_group", kwargs={"gruppe_id": str(gruppe_id)})
        )
        assert response.status_code == 302
        # Original + Kopie = 4 Pläne
        assert Plan.objects.filter(user=self.user).count() == 4

    def test_kopie_bekommt_neue_gruppe_id(self):
        gruppe_id, gruppe_name, _ = _create_gruppe(self.user)
        self.client.post(reverse("duplicate_group", kwargs={"gruppe_id": str(gruppe_id)}))
        # Zwei unterschiedliche gruppe_ids
        ids = list(
            Plan.objects.filter(user=self.user).values_list("gruppe_id", flat=True).distinct()
        )
        assert len(ids) == 2

    def test_nicht_gefundene_gruppe_redirect(self):
        response = self.client.post(
            reverse("duplicate_group", kwargs={"gruppe_id": str(uuid.uuid4())})
        )
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# share_plan
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSharePlan:
    def setup_method(self):
        self.owner = UserFactory()
        self.other = UserFactory()
        self.plan = PlanFactory(user=self.owner, is_public=True)

    def test_owner_sieht_sharing_seite(self):
        client = Client()
        client.force_login(self.owner)
        response = client.get(reverse("share_plan", kwargs={"plan_id": self.plan.id}))
        assert response.status_code == 200
        assert response.context["is_owner"] is True

    def test_anderer_user_sieht_plan(self):
        client = Client()
        client.force_login(self.other)
        response = client.get(reverse("share_plan", kwargs={"plan_id": self.plan.id}))
        assert response.status_code == 200
        assert response.context["is_owner"] is False

    def test_privater_plan_gibt_404_fuer_fremde(self):
        plan_privat = PlanFactory(user=self.owner, is_public=False)
        client = Client()
        client.force_login(self.other)
        response = client.get(reverse("share_plan", kwargs={"plan_id": plan_privat.id}))
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# share_group
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestShareGroup:
    def setup_method(self):
        self.owner = UserFactory()
        self.client = Client()
        self.client.force_login(self.owner)

    def test_share_gruppe_owner(self):
        gruppe_id, _, _ = _create_gruppe(self.owner, is_public=True)
        response = self.client.get(reverse("share_group", kwargs={"gruppe_id": str(gruppe_id)}))
        assert response.status_code == 200
        assert response.context["is_owner"] is True

    def test_nicht_gefundene_gruppe_redirect(self):
        response = self.client.get(reverse("share_group", kwargs={"gruppe_id": str(uuid.uuid4())}))
        assert response.status_code == 302

    def test_eigene_private_gruppe_sichtbar(self):
        gruppe_id, _, _ = _create_gruppe(self.owner, is_public=False)
        response = self.client.get(reverse("share_group", kwargs={"gruppe_id": str(gruppe_id)}))
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# plan_library
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPlanLibrary:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_leere_bibliothek(self):
        response = self.client.get(reverse("plan_library"))
        assert response.status_code == 200
        assert response.context["total_count"] == 0

    def test_oeffentliche_plaene_sichtbar(self):
        anderer = UserFactory()
        PlanFactory(user=anderer, is_public=True)
        response = self.client.get(reverse("plan_library"))
        assert response.context["total_count"] == 1

    def test_private_plaene_nicht_sichtbar(self):
        anderer = UserFactory()
        PlanFactory(user=anderer, is_public=False)
        response = self.client.get(reverse("plan_library"))
        assert response.context["total_count"] == 0

    def test_suche_filtert_plaene(self):
        anderer = UserFactory()
        PlanFactory(user=anderer, name="Bankdrücken Plan", is_public=True)
        PlanFactory(user=anderer, name="Kniebeugen Plan", is_public=True)
        response = self.client.get(reverse("plan_library") + "?q=Bankdrücken")
        assert response.context["total_count"] == 1

    def test_plan_gruppe_wird_gruppiert(self):
        anderer = UserFactory()
        gruppe_id, _, _ = _create_gruppe(anderer, n_plaene=2, is_public=True)
        response = self.client.get(reverse("plan_library"))
        assert len(response.context["plan_gruppen"]) == 1

    def test_einzelne_plaene_erscheinen_separat(self):
        anderer = UserFactory()
        PlanFactory(user=anderer, is_public=True, gruppe_id=None)
        response = self.client.get(reverse("plan_library"))
        assert len(response.context["einzelne_plaene"]) == 1

    def test_ohne_login_zugaenglich(self):
        client = Client()
        response = client.get(reverse("plan_library"))
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# plan_library_group
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPlanLibraryGroup:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_gruppe_sichtbar(self):
        anderer = UserFactory()
        gruppe_id, gruppe_name, _ = _create_gruppe(anderer, is_public=True)
        response = self.client.get(
            reverse("plan_library_group", kwargs={"gruppe_id": str(gruppe_id)})
        )
        assert response.status_code == 200
        assert response.context["gruppe_name"] == gruppe_name

    def test_nicht_gefundene_gruppe_redirect(self):
        response = self.client.get(
            reverse("plan_library_group", kwargs={"gruppe_id": str(uuid.uuid4())})
        )
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# copy_group
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCopyGroup:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_oeffentliche_gruppe_kopieren(self):
        anderer = UserFactory()
        uebung = UebungFactory()
        gruppe_id, gruppe_name, plaene = _create_gruppe(anderer, is_public=True)
        # Sicherstellen dass die Gruppe öffentlich ist
        Plan.objects.filter(gruppe_id=gruppe_id).update(is_public=True)

        plan_count_before = Plan.objects.filter(user=self.user).count()
        response = self.client.post(reverse("copy_group", kwargs={"gruppe_id": str(gruppe_id)}))
        assert response.status_code == 302
        assert Plan.objects.filter(user=self.user).count() == plan_count_before + len(plaene)

    def test_nicht_gefundene_gruppe_redirect(self):
        response = self.client.post(reverse("copy_group", kwargs={"gruppe_id": str(uuid.uuid4())}))
        assert response.status_code == 302

    def test_login_required(self):
        client = Client()
        anderer = UserFactory()
        gruppe_id, _, _ = _create_gruppe(anderer, is_public=True)
        url = reverse("copy_group", kwargs={"gruppe_id": str(gruppe_id)})
        response = client.post(url)
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# toggle_group_public
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestToggleGroupPublic:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_toggle_macht_gruppe_oeffentlich(self):
        gruppe_id, _, plaene = _create_gruppe(self.user, is_public=False)
        self.client.post(reverse("toggle_group_public", kwargs={"gruppe_id": str(gruppe_id)}))
        assert Plan.objects.filter(gruppe_id=gruppe_id, is_public=True).count() == len(plaene)

    def test_toggle_macht_gruppe_privat(self):
        gruppe_id, _, plaene = _create_gruppe(self.user, is_public=True)
        self.client.post(reverse("toggle_group_public", kwargs={"gruppe_id": str(gruppe_id)}))
        assert Plan.objects.filter(gruppe_id=gruppe_id, is_public=False).count() == len(plaene)

    def test_nicht_gefundene_gruppe_redirect(self):
        response = self.client.post(
            reverse("toggle_group_public", kwargs={"gruppe_id": str(uuid.uuid4())})
        )
        assert response.status_code == 302

    def test_login_required(self):
        client = Client()
        gruppe_id, _, _ = _create_gruppe(self.user, is_public=False)
        url = reverse("toggle_group_public", kwargs={"gruppe_id": str(gruppe_id)})
        response = client.post(url)
        assert response.status_code == 302


# ─────────────────────────────────────────────────────────────────────────────
# set_active_plan_group
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSetActivePlanGroup:
    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_get_zeigt_formular(self):
        response = self.client.get(reverse("set_active_plan_group"))
        assert response.status_code == 200

    def test_post_setzt_gruppe(self):
        gruppe_id, gruppe_name, _ = _create_gruppe(self.user)
        Plan.objects.filter(gruppe_id=gruppe_id).update(gruppe_name=gruppe_name)
        response = self.client.post(
            reverse("set_active_plan_group"),
            {"gruppe_id": str(gruppe_id), "cycle_length": "4"},
        )
        assert response.status_code == 302
        self.profile.refresh_from_db()
        assert str(self.profile.active_plan_group) == str(gruppe_id)

    def test_post_entfernt_aktive_gruppe(self):
        gruppe_id, _, _ = _create_gruppe(self.user)
        self.profile.active_plan_group = gruppe_id
        self.profile.save()
        response = self.client.post(
            reverse("set_active_plan_group"),
            {"gruppe_id": "", "cycle_length": "4"},
        )
        assert response.status_code == 302
        self.profile.refresh_from_db()
        assert self.profile.active_plan_group is None

    def test_post_einzelplan_bekommt_gruppe_id(self):
        plan = PlanFactory(user=self.user, gruppe_id=None)
        response = self.client.post(
            reverse("set_active_plan_group"),
            {"gruppe_id": "", "plan_id": str(plan.id), "cycle_length": "4"},
        )
        assert response.status_code == 302
        plan.refresh_from_db()
        assert plan.gruppe_id is not None

    def test_post_mit_block_typ_startet_block(self):
        gruppe_id, gruppe_name, _ = _create_gruppe(self.user)
        Plan.objects.filter(gruppe_id=gruppe_id).update(gruppe_name=gruppe_name)
        self.client.post(
            reverse("set_active_plan_group"),
            {
                "gruppe_id": str(gruppe_id),
                "cycle_length": "4",
                "block_typ": "masse",
            },
        )
        assert Trainingsblock.objects.filter(user=self.user).exists()

    def test_get_zeigt_plan_gruppen_und_einzelplaene(self):
        gruppe_id, _, _ = _create_gruppe(self.user)
        einzelplan = PlanFactory(user=self.user, gruppe_id=None)
        response = self.client.get(reverse("set_active_plan_group"))
        assert response.status_code == 200
        # Plan-Gruppen und Einzelpläne im Context
        assert len(response.context["plan_gruppen"]) >= 1
        single_ids = [ep["id"] for ep in response.context["einzelplaene"]]
        assert einzelplan.id in single_ids

    def test_login_required(self):
        client = Client()
        response = client.get(reverse("set_active_plan_group"))
        assert response.status_code == 302
