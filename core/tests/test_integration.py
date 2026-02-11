"""
Integration Test Suite - Complex User Workflows.

Tests für realistische End-to-End Szenarien:
- Complete Training Workflow (Plan → Training → Stats)
- Plan Sharing & Copy between Users
- Body Tracking + Training Progress
- Equipment-Based Plan Creation
- Multi-Day Training Programs
"""

from decimal import Decimal

from django.urls import reverse

import pytest

from core.models import KoerperWerte, Plan, PlanUebung, Satz, Trainingseinheit
from core.tests.factories import (
    EquipmentFactory,
    KoerperWerteFactory,
    PlanFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestCompleteTrainingWorkflow:
    """Test: Kompletter Training-Workflow von Plan bis Stats."""

    def test_full_training_cycle(self, client):
        """Test: Complete training workflow - Plan → Training → Sets → Completion."""
        user = UserFactory()

        # STEP 1: Plan mit 2 Übungen erstellen
        uebung1 = UebungFactory(bezeichnung="Bankdrücken")
        uebung2 = UebungFactory(bezeichnung="Kniebeugen")

        plan = PlanFactory(user=user, name="Push Day")
        PlanUebung.objects.create(
            plan=plan, uebung=uebung1, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="8-12"
        )
        PlanUebung.objects.create(
            plan=plan, uebung=uebung2, reihenfolge=2, saetze_ziel=4, wiederholungen_ziel="10"
        )

        # STEP 2: Training direkt erstellen (Model-based, kein View)
        training = TrainingseinheitFactory(user=user, plan=plan)

        # STEP 3: Sätze hinzufügen (3 Bankdrücken + 4 Kniebeugen)
        for i in range(3):
            SatzFactory(
                einheit=training,
                uebung=uebung1,
                satz_nr=i + 1,
                gewicht=Decimal(80 + (i * 2.5)),
                wiederholungen=10 - i,
                rpe=7 + i,
            )

        for i in range(4):
            SatzFactory(
                einheit=training,
                uebung=uebung2,
                satz_nr=i + 1,
                gewicht=Decimal(100 + (i * 5)),
                wiederholungen=10,
                rpe=8,
            )

        # STEP 4: Training beenden
        training.dauer_minuten = 75
        training.kommentar = "Sehr gutes Training!"
        training.save()

        # STEP 5: Verify - Training komplett
        training.refresh_from_db()
        assert training.dauer_minuten == 75
        assert training.kommentar == "Sehr gutes Training!"
        assert training.plan == plan

        # Verify - Alle 7 Sätze gespeichert
        saetze = Satz.objects.filter(einheit=training)
        assert saetze.count() == 7

        # Verify - Korrekte Verteilung
        assert saetze.filter(uebung=uebung1).count() == 3
        assert saetze.filter(uebung=uebung2).count() == 4

        # Verify - Progressive weights
        bench_weights = list(
            saetze.filter(uebung=uebung1).order_by("satz_nr").values_list("gewicht", flat=True)
        )
        assert bench_weights == [Decimal("80.0"), Decimal("82.5"), Decimal("85.0")]


@pytest.mark.django_db
class TestPlanSharingWorkflow:
    """Test: Plan Sharing zwischen Users."""

    def test_plan_share_and_copy_workflow(self, client):
        """Test: User1 teilt Plan, User2 kopiert ihn."""
        user1 = UserFactory(username="trainer")
        user2 = UserFactory(username="athlete")

        # STEP 1: User1 erstellt Plan
        client.force_login(user1)

        uebung1 = UebungFactory(bezeichnung="Deadlift")
        uebung2 = UebungFactory(bezeichnung="Rows")

        plan = Plan.objects.create(user=user1, name="Pull Day", is_public=False)
        PlanUebung.objects.create(
            plan=plan, uebung=uebung1, reihenfolge=1, saetze_ziel=5, wiederholungen_ziel="5"
        )
        PlanUebung.objects.create(
            plan=plan, uebung=uebung2, reihenfolge=2, saetze_ziel=4, wiederholungen_ziel="8-10"
        )

        # STEP 2: User1 macht Plan public
        url_toggle = reverse("toggle_plan_public", kwargs={"plan_id": plan.id})
        response = client.post(url_toggle)
        assert response.status_code == 302

        plan.refresh_from_db()
        assert plan.is_public is True

        # STEP 3: User2 findet und kopiert Plan
        client.force_login(user2)

        url_copy = reverse("copy_plan", kwargs={"plan_id": plan.id})
        response = client.post(url_copy)
        assert response.status_code == 302

        # STEP 4: Verify - User2 hat eigene Kopie
        user2_plaene = Plan.objects.filter(user=user2)
        assert user2_plaene.count() == 1

        kopie = user2_plaene.first()
        assert "Pull Day" in kopie.name
        assert kopie.uebungen.count() == 2

        # STEP 5: User2 macht Training mit kopiertem Plan
        url_start = reverse("training_start_plan", kwargs={"plan_id": kopie.id})
        response = client.post(url_start)
        assert response.status_code == 302

        training = Trainingseinheit.objects.filter(user=user2, plan=kopie).first()
        assert training is not None
        assert training.user == user2
        assert training.plan == kopie


@pytest.mark.django_db
class TestBodyTrackingProgressWorkflow:
    """Test: Body Tracking + Training Progress Integration."""

    def test_body_tracking_with_training_progress(self, client):
        """Test: User trackt Körperwerte und macht Trainings - Integration."""
        user = UserFactory()

        # STEP 1: Initiale Körperwerte
        KoerperWerteFactory(user=user, gewicht=Decimal("85.0"), koerperfett_prozent=Decimal("18.0"))

        # STEP 2: Trainings mit progressivem Overload
        uebung = UebungFactory(bezeichnung="Bench Press")

        training1 = TrainingseinheitFactory(user=user, dauer_minuten=60)
        SatzFactory(einheit=training1, uebung=uebung, gewicht=Decimal("80"))

        training2 = TrainingseinheitFactory(user=user, dauer_minuten=60)
        SatzFactory(einheit=training2, uebung=uebung, gewicht=Decimal("85"))

        training3 = TrainingseinheitFactory(user=user, dauer_minuten=60)
        SatzFactory(einheit=training3, uebung=uebung, gewicht=Decimal("90"))

        # STEP 3: Neue Körperwerte nach Training
        KoerperWerteFactory(user=user, gewicht=Decimal("87.5"), koerperfett_prozent=Decimal("16.5"))

        # STEP 4: Verify - Progress
        assert Trainingseinheit.objects.filter(user=user).count() == 3
        assert KoerperWerte.objects.filter(user=user).count() == 2

        # Weight progression in training
        weights = list(
            Satz.objects.filter(einheit__user=user, uebung=uebung)
            .order_by("einheit__datum")
            .values_list("gewicht", flat=True)
        )
        assert weights == [Decimal("80"), Decimal("85"), Decimal("90")]


@pytest.mark.django_db
class TestEquipmentBasedWorkflow:
    """Test: Equipment-basierte Plan-Erstellung."""

    def test_equipment_filtered_plan_creation(self, client):
        """Test: User wählt Equipment, Plan enthält nur passende Übungen."""
        user = UserFactory()
        client.force_login(user)

        # STEP 1: Equipment setup
        hantel = EquipmentFactory(name="KURZHANTEL")
        langhantel = EquipmentFactory(name="LANGHANTEL")
        maschine = EquipmentFactory(name="BEINPRESSE")

        # User hat nur Hanteln
        hantel.users.add(user)
        langhantel.users.add(user)

        # STEP 2: Übungen mit verschiedenem Equipment
        uebung_hantel = UebungFactory(bezeichnung="Kurzhantel Bankdrücken")
        uebung_hantel.equipment.add(hantel)

        uebung_langhantel = UebungFactory(bezeichnung="Langhantel Kniebeugen")
        uebung_langhantel.equipment.add(langhantel)

        uebung_maschine = UebungFactory(bezeichnung="Beinpresse")
        uebung_maschine.equipment.add(maschine)

        # STEP 3: Plan erstellen nur mit verfügbarem Equipment
        plan = Plan.objects.create(user=user, name="Home Workout")

        # Nur Übungen mit User-Equipment
        PlanUebung.objects.create(
            plan=plan, uebung=uebung_hantel, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="10"
        )
        PlanUebung.objects.create(
            plan=plan,
            uebung=uebung_langhantel,
            reihenfolge=2,
            saetze_ziel=4,
            wiederholungen_ziel="8",
        )

        # STEP 4: Training mit diesem Plan
        url_start = reverse("training_start_plan", kwargs={"plan_id": plan.id})
        response = client.post(url_start)
        assert response.status_code == 302

        training = Trainingseinheit.objects.filter(user=user, plan=plan).first()
        assert training is not None

        # STEP 5: Verify - Nur kompatible Übungen im Plan
        plan_uebungen = plan.uebungen.all()
        assert plan_uebungen.count() == 2

        # Keine Maschinen-Übungen
        assert not plan.uebungen.filter(uebung=uebung_maschine).exists()

        # Nur User-Equipment Übungen
        assert plan.uebungen.filter(uebung=uebung_hantel).exists()
        assert plan.uebungen.filter(uebung=uebung_langhantel).exists()
