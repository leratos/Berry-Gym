"""
Test Suite für Plan & PlanUebung Models - FIXED VERSION.

Tests für:
- Plan CRUD Operations
- PlanUebung Relationships
- Reihenfolge & Sortierung
- Plan Gruppen
- Plan Sharing (is_public, shared_with)
- Validierung & Edge Cases
"""

import pytest

from core.models import Equipment, Plan, PlanUebung, Uebung
from core.tests.factories import PlanFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestPlanModel:
    """Tests für das Plan Model."""

    def test_create_basic_plan(self):
        """Test: Plan mit Mindestangaben erstellen."""
        user = UserFactory()
        plan = Plan.objects.create(user=user, name="PPL Split")

        assert plan.name == "PPL Split"
        assert plan.user == user
        assert plan.is_public is False
        assert str(plan) == "PPL Split"

    def test_plan_user_isolation(self):
        """Test: User sehen nur ihre eigenen Pläne."""
        user1 = UserFactory()
        user2 = UserFactory()

        plan1 = Plan.objects.create(user=user1, name="User1 Plan")
        plan2 = Plan.objects.create(user=user2, name="User2 Plan")

        user1_plans = Plan.objects.filter(user=user1)
        user2_plans = Plan.objects.filter(user=user2)

        assert plan1 in user1_plans
        assert plan1 not in user2_plans
        assert plan2 in user2_plans
        assert plan2 not in user1_plans

    def test_plan_public_sharing(self):
        """Test: Plan kann öffentlich geteilt werden."""
        user = UserFactory()
        plan = Plan.objects.create(user=user, name="Öffentlicher Plan", is_public=True)

        assert plan.is_public is True
        # Öffentliche Pläne sollten für alle sichtbar sein
        public_plans = Plan.objects.filter(is_public=True)
        assert plan in public_plans

    def test_plan_gruppe(self):
        """Test: Pläne können zu Gruppen zusammengefasst werden."""
        user = UserFactory()
        import uuid

        gruppe_id = uuid.uuid4()

        plan1 = Plan.objects.create(
            user=user,
            name="Push Day",
            gruppe_id=gruppe_id,
            gruppe_name="PPL Split",
            gruppe_reihenfolge=1,
        )
        plan2 = Plan.objects.create(
            user=user,
            name="Pull Day",
            gruppe_id=gruppe_id,
            gruppe_name="PPL Split",
            gruppe_reihenfolge=2,
        )
        plan3 = Plan.objects.create(
            user=user,
            name="Leg Day",
            gruppe_id=gruppe_id,
            gruppe_name="PPL Split",
            gruppe_reihenfolge=3,
        )

        # Gruppierung prüfen
        ppl_plans = Plan.objects.filter(gruppe_id=gruppe_id).order_by("gruppe_reihenfolge")
        assert list(ppl_plans) == [plan1, plan2, plan3]

    def test_plan_shared_with_users(self):
        """Test: Plan kann mit spezifischen Usern geteilt werden."""
        owner = UserFactory()
        friend1 = UserFactory()
        friend2 = UserFactory()

        plan = Plan.objects.create(user=owner, name="Shared Plan")
        plan.shared_with.add(friend1, friend2)

        assert friend1 in plan.shared_with.all()
        assert friend2 in plan.shared_with.all()
        assert plan.shared_with.count() == 2

    def test_plan_delete_cascade(self):
        """Test: Plan löschen löscht auch PlanUebungen."""
        user = UserFactory()
        plan = Plan.objects.create(user=user, name="Test Plan")
        uebung = UebungFactory()
        plan_uebung = PlanUebung.objects.create(
            plan=plan, uebung=uebung, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="8-12"
        )

        plan_uebung_id = plan_uebung.id

        # Plan löschen
        plan.delete()

        # PlanUebung sollte auch gelöscht sein
        assert not PlanUebung.objects.filter(id=plan_uebung_id).exists()


@pytest.mark.django_db
class TestPlanUebungModel:
    """Tests für das PlanUebung Model."""

    def test_create_basic_planuebung(self):
        """Test: PlanUebung mit Pflichtfeldern erstellen."""
        plan = PlanFactory()
        uebung = UebungFactory()

        plan_uebung = PlanUebung.objects.create(
            plan=plan, uebung=uebung, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="8-12"
        )

        assert plan_uebung.plan == plan
        assert plan_uebung.uebung == uebung
        assert plan_uebung.saetze_ziel == 3
        assert plan_uebung.wiederholungen_ziel == "8-12"
        assert plan_uebung.reihenfolge == 1

    def test_planuebung_reihenfolge_sortierung(self):
        """Test: PlanUebungen werden nach Reihenfolge sortiert."""
        plan = PlanFactory()
        uebung1 = UebungFactory(bezeichnung="Übung 1")
        uebung2 = UebungFactory(bezeichnung="Übung 2")
        uebung3 = UebungFactory(bezeichnung="Übung 3")

        # Bewusst in falscher Reihenfolge erstellen
        pu3 = PlanUebung.objects.create(
            plan=plan, uebung=uebung3, reihenfolge=3, saetze_ziel=3, wiederholungen_ziel="10"
        )
        pu1 = PlanUebung.objects.create(
            plan=plan, uebung=uebung1, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="10"
        )
        pu2 = PlanUebung.objects.create(
            plan=plan, uebung=uebung2, reihenfolge=2, saetze_ziel=3, wiederholungen_ziel="10"
        )

        # Nach Reihenfolge sortiert abrufen
        plan_uebungen = PlanUebung.objects.filter(plan=plan).order_by("reihenfolge")

        assert list(plan_uebungen) == [pu1, pu2, pu3]

    def test_planuebung_optional_fields(self):
        """Test: Optional Felder (Pausenzeit, Trainingstag, Superset)."""
        plan = PlanFactory()
        uebung = UebungFactory()

        plan_uebung = PlanUebung.objects.create(
            plan=plan,
            uebung=uebung,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            pausenzeit=90,
            trainingstag="Tag 1",
            superset_gruppe=1,
        )

        assert plan_uebung.pausenzeit == 90
        assert plan_uebung.trainingstag == "Tag 1"
        assert plan_uebung.superset_gruppe == 1

    def test_planuebung_superset_grouping(self):
        """Test: Mehrere Übungen in Superset gruppieren."""
        plan = PlanFactory()
        uebung1 = UebungFactory(bezeichnung="Bankdrücken")
        uebung2 = UebungFactory(bezeichnung="Rudern")

        # Beide Übungen in Superset Gruppe 1
        pu1 = PlanUebung.objects.create(
            plan=plan,
            uebung=uebung1,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            superset_gruppe=1,
        )
        pu2 = PlanUebung.objects.create(
            plan=plan,
            uebung=uebung2,
            reihenfolge=2,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            superset_gruppe=1,
        )

        # Superset Gruppe abfragen
        superset_gruppe = PlanUebung.objects.filter(plan=plan, superset_gruppe=1)

        assert superset_gruppe.count() == 2
        assert pu1 in superset_gruppe
        assert pu2 in superset_gruppe

    def test_planuebung_trainingstag_filtering(self):
        """Test: Übungen nach Trainingstag filtern."""
        plan = PlanFactory()
        uebung1 = UebungFactory(bezeichnung="Übung Tag 1")
        uebung2 = UebungFactory(bezeichnung="Übung Tag 2")
        uebung3 = UebungFactory(bezeichnung="Übung Tag 1 (2)")

        PlanUebung.objects.create(
            plan=plan,
            uebung=uebung1,
            reihenfolge=1,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            trainingstag="Tag 1",
        )
        PlanUebung.objects.create(
            plan=plan,
            uebung=uebung2,
            reihenfolge=2,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            trainingstag="Tag 2",
        )
        PlanUebung.objects.create(
            plan=plan,
            uebung=uebung3,
            reihenfolge=3,
            saetze_ziel=3,
            wiederholungen_ziel="10",
            trainingstag="Tag 1",
        )

        # Tag 1 Übungen
        tag1_uebungen = PlanUebung.objects.filter(plan=plan, trainingstag="Tag 1")
        assert tag1_uebungen.count() == 2

        # Tag 2 Übungen
        tag2_uebungen = PlanUebung.objects.filter(plan=plan, trainingstag="Tag 2")
        assert tag2_uebungen.count() == 1

    def test_planuebung_delete_does_not_delete_uebung(self):
        """Test: PlanUebung löschen löscht nicht die Übung."""
        plan = PlanFactory()
        uebung = UebungFactory()

        plan_uebung = PlanUebung.objects.create(
            plan=plan, uebung=uebung, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="10"
        )

        uebung_id = uebung.id
        plan_uebung.delete()

        # Übung sollte noch existieren
        assert Uebung.objects.filter(id=uebung_id).exists()


@pytest.mark.django_db
class TestPlanEquipmentIntegration:
    """Tests für Plan-Equipment Integration."""

    def test_plan_respects_user_equipment(self):
        """Test: Pläne sollten User-Equipment berücksichtigen."""
        user = UserFactory()

        # Equipment hinzufügen
        hantel = Equipment.objects.create(name="KURZHANTEL")
        bank = Equipment.objects.create(name="BANK")

        # Übung mit Hantel-Requirement
        uebung_hantel = UebungFactory(bezeichnung="Bankdrücken")
        uebung_hantel.equipment.add(hantel)

        # Equipment dem User zuweisen
        hantel.users.add(user)
        bank.users.add(user)

        # Plan erstellen
        plan = Plan.objects.create(user=user, name="Hantel-Plan")
        PlanUebung.objects.create(
            plan=plan, uebung=uebung_hantel, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="10"
        )

        # Prüfen ob User das Equipment hat
        uebung_equipment = uebung_hantel.equipment.all()
        user_equipment = Equipment.objects.filter(users=user)

        assert all(eq in user_equipment for eq in uebung_equipment)
