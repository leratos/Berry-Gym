"""
Tests für Plan-Template Views.

Abgedeckt:
- get_plan_templates: Listet verfügbare Templates
- get_template_detail: Details + Equipment-Check pro Template
- create_plan_from_template: Erstellt Pläne aus Template
"""

from django.test import Client
from django.urls import reverse

import pytest

from core.tests.factories import EquipmentFactory, UserFactory


@pytest.mark.django_db
class TestGetPlanTemplates:
    """Tests für GET /api/plan-templates/"""

    def setup_method(self):
        self.client = Client()
        self.url = reverse("get_plan_templates")

    def test_returns_templates_without_login(self):
        """Endpoint ist öffentlich zugänglich."""
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_returns_json(self):
        """Antwort ist JSON."""
        resp = self.client.get(self.url)
        data = resp.json()
        assert isinstance(data, dict)

    def test_known_template_keys_present(self):
        """Bekannte Template-Keys sind vorhanden."""
        resp = self.client.get(self.url)
        data = resp.json()
        assert "full_body_3day" in data
        assert "upper_lower_4day" in data
        assert "push_pull_legs_6day" in data

    def test_template_has_metadata(self):
        """Jedes Template enthält die Pflichtfelder."""
        resp = self.client.get(self.url)
        data = resp.json()
        template = data["full_body_3day"]
        for key in (
            "name",
            "description",
            "frequency_per_week",
            "difficulty",
            "goal",
            "days_count",
        ):
            assert key in template, f"Pflichtfeld '{key}' fehlt"

    def test_no_exercises_in_list_view(self):
        """Listenansicht enthält keine Übungsdetails."""
        resp = self.client.get(self.url)
        data = resp.json()
        template = data["full_body_3day"]
        assert "days" not in template  # Übungen nur in Detail-Ansicht


@pytest.mark.django_db
class TestGetTemplateDetail:
    """Tests für GET /api/plan-templates/<key>/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect."""
        c = Client()
        url = reverse("get_template_detail", args=["full_body_3day"])
        resp = c.get(url)
        assert resp.status_code == 302

    def test_valid_template_returns_200(self):
        """Gültiger Key → 200 mit Template-Daten."""
        url = reverse("get_template_detail", args=["full_body_3day"])
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "days_adapted" in data

    def test_invalid_template_key_returns_404(self):
        """Ungültiger Key → 404."""
        url = reverse("get_template_detail", args=["gibts_nicht_xyz"])
        resp = self.client.get(url)
        assert resp.status_code == 404

    def test_exercise_has_availability_flag(self):
        """Jede Übung hat 'available' Flag."""
        url = reverse("get_template_detail", args=["full_body_3day"])
        resp = self.client.get(url)
        data = resp.json()
        for day in data["days_adapted"]:
            for ex in day["exercises"]:
                assert "available" in ex, f"'available' fehlt bei Übung: {ex.get('name')}"

    def test_koerpergewicht_always_available(self):
        """Körpergewicht-Übungen sind immer verfügbar (kein Equipment nötig)."""
        url = reverse("get_template_detail", args=["full_body_3day"])
        resp = self.client.get(url)
        data = resp.json()
        # Suche nach Übungen mit Equipment = körpergewicht
        for day in data["days_adapted"]:
            for ex in day["exercises"]:
                if ex.get("equipment", "").strip().lower() == "körpergewicht":
                    assert ex["available"] is True

    def test_user_with_equipment_has_more_available(self):
        """User mit Equipment hat mehr verfügbare Übungen als User ohne."""
        # User ohne Equipment
        user_no_equip = UserFactory()
        c_no = Client()
        c_no.force_login(user_no_equip)

        # User mit Equipment (Kurzhantel)
        user_with_equip = UserFactory()
        equip = EquipmentFactory(name="kurzhanteln")
        equip.users.add(user_with_equip)
        c_with = Client()
        c_with.force_login(user_with_equip)

        url = reverse("get_template_detail", args=["full_body_3day"])

        resp_no = c_no.get(url)
        resp_with = c_with.get(url)

        def count_available(data):
            return sum(
                1 for day in data["days_adapted"] for ex in day["exercises"] if ex.get("available")
            )

        count_no = count_available(resp_no.json())
        count_with = count_available(resp_with.json())
        assert count_with >= count_no  # Mit Equipment mindestens gleich viel verfügbar

    def test_upper_lower_template_works(self):
        """Upper/Lower Template funktioniert."""
        url = reverse("get_template_detail", args=["upper_lower_4day"])
        resp = self.client.get(url)
        assert resp.status_code == 200

    def test_push_pull_legs_template_works(self):
        """Push/Pull/Legs Template funktioniert."""
        url = reverse("get_template_detail", args=["push_pull_legs_6day"])
        resp = self.client.get(url)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCreatePlanFromTemplate:
    """Tests für POST /api/plan-templates/<key>/create/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect."""
        c = Client()
        url = reverse("create_plan_from_template", args=["full_body_3day"])
        resp = c.post(url)
        assert resp.status_code == 302

    def test_get_not_allowed(self):
        """GET → 405."""
        url = reverse("create_plan_from_template", args=["full_body_3day"])
        resp = self.client.get(url)
        assert resp.status_code == 405

    def test_invalid_key_returns_404(self):
        """Ungültiger Template-Key → 404."""
        url = reverse("create_plan_from_template", args=["gibts_nicht_xyz"])
        resp = self.client.post(url)
        assert resp.status_code == 404

    def test_creates_plans_for_each_day(self):
        """Für jeden Tag im Template wird ein Plan erstellt."""
        url = reverse("create_plan_from_template", args=["full_body_3day"])
        resp = self.client.post(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # full_body_3day hat 3 Tage
        assert data["plan_count"] == 3
        assert len(data["plan_ids"]) == 3

    def test_created_plan_ids_are_unique(self):
        """Erstellte Plan-IDs sind eindeutig."""
        url = reverse("create_plan_from_template", args=["upper_lower_4day"])
        resp = self.client.post(url)
        data = resp.json()
        ids = data["plan_ids"]
        assert len(ids) == len(set(ids))

    def test_plans_belong_to_user(self):
        """Erstellte Pläne gehören dem eingeloggten User."""
        from core.models import Plan

        url = reverse("create_plan_from_template", args=["full_body_3day"])
        resp = self.client.post(url)
        data = resp.json()
        for plan_id in data["plan_ids"]:
            plan = Plan.objects.get(id=plan_id)
            assert plan.user == self.user

    def test_different_users_get_separate_plans(self):
        """Zwei User erstellen Plans unabhängig voneinander."""
        from core.models import Plan

        user2 = UserFactory()
        c2 = Client()
        c2.force_login(user2)

        url = reverse("create_plan_from_template", args=["full_body_3day"])
        self.client.post(url)
        c2.post(url)

        assert Plan.objects.filter(user=self.user).count() == 3
        assert Plan.objects.filter(user=user2).count() == 3
