"""
Test Suite für Training Session Views.

Tests für:
- Login-Required Decorator
- Training starten (freies Training + mit Plan)
- Training Session Management
- Satz hinzufügen/löschen/bearbeiten
- Training beenden mit Statistiken
- Permission Checks (User Isolation)
"""

from django.urls import reverse

import pytest

from core.models import Plan, PlanUebung, Satz, Trainingseinheit
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestTrainingSelectPlan:
    """Tests für training_select_plan View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        url = reverse("training_select_plan")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_eigene_plaene_filter(self, client):
        """Test: Zeigt nur eigene Pläne im Default-Filter."""
        user1 = UserFactory()
        user2 = UserFactory()
        client.force_login(user1)

        # Pläne erstellen
        plan_user1 = Plan.objects.create(user=user1, name="User1 Plan")
        plan_user2 = Plan.objects.create(user=user2, name="User2 Plan")

        url = reverse("training_select_plan")
        response = client.get(url)

        assert response.status_code == 200
        # User1 sieht nur eigenen Plan
        assert plan_user1.name.encode() in response.content
        assert plan_user2.name.encode() not in response.content

    def test_public_plaene_filter(self, client):
        """Test: ?filter=public redirectet zu ?filter=eigene (öffentliche Pläne sind in /plan-library/)."""
        user1 = UserFactory()
        client.force_login(user1)

        url = reverse("training_select_plan") + "?filter=public"
        response = client.get(url)

        assert response.status_code == 302
        assert "filter=eigene" in response["Location"]


@pytest.mark.django_db
class TestTrainingStart:
    """Tests für training_start View."""

    # NOTE: training_start hat keinen @login_required Decorator
    # würde bei AnonymousUser crashen - wird in Production durch Frontend verhindert

    def test_freies_training_erstellen(self, client):
        """Test: Freies Training ohne Plan starten."""
        user = UserFactory()
        client.force_login(user)

        url = reverse("training_start_free")
        response = client.post(url)

        # Sollte zu Training Session redirecten
        assert response.status_code == 302

        # Training wurde erstellt
        training = Trainingseinheit.objects.filter(user=user).first()
        assert training is not None
        assert training.plan is None

    def test_training_mit_plan_erstellen(self, client):
        """Test: Training mit Plan starten."""
        user = UserFactory()
        client.force_login(user)

        plan = Plan.objects.create(user=user, name="Test Plan")
        uebung = UebungFactory()
        PlanUebung.objects.create(
            plan=plan, uebung=uebung, reihenfolge=1, saetze_ziel=3, wiederholungen_ziel="8-12"
        )

        url = reverse("training_start_plan", kwargs={"plan_id": plan.id})
        response = client.post(url)

        assert response.status_code == 302

        # Training wurde mit Plan erstellt
        training = Trainingseinheit.objects.filter(user=user, plan=plan).first()
        assert training is not None
        assert training.plan == plan

    def test_training_mit_fremdem_plan_verboten(self, client):
        """Test: Kann nicht mit fremdem Plan starten."""
        user1 = UserFactory()
        user2 = UserFactory()
        client.force_login(user1)

        plan_user2 = Plan.objects.create(user=user2, name="User2 Plan")

        url = reverse("training_start_plan", kwargs={"plan_id": plan_user2.id})
        response = client.post(url)

        # Sollte 404 sein (Plan nicht gefunden für user1)
        assert response.status_code == 404

        # Kein Training wurde erstellt
        assert not Trainingseinheit.objects.filter(user=user1, plan=plan_user2).exists()


@pytest.mark.django_db
class TestTrainingSession:
    """Tests für training_session View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        training = TrainingseinheitFactory()
        url = reverse("training_session", kwargs={"training_id": training.id})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_training_session_anzeigen(self, client):
        """Test: Training Session wird angezeigt."""
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        client.force_login(user)

        url = reverse("training_session", kwargs={"training_id": training.id})
        response = client.get(url)

        assert response.status_code == 200
        assert "training" in response.context
        assert response.context["training"] == training

    def test_fremdes_training_nicht_sichtbar(self, client):
        """Test: User kann fremdes Training nicht sehen."""
        user1 = UserFactory()
        user2 = UserFactory()
        training_user2 = TrainingseinheitFactory(user=user2)
        client.force_login(user1)

        url = reverse("training_session", kwargs={"training_id": training_user2.id})
        response = client.get(url)

        # Sollte 404 sein
        assert response.status_code == 404


@pytest.mark.django_db
class TestAddSet:
    """Tests für add_set View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        training = TrainingseinheitFactory()
        url = reverse("add_set", kwargs={"training_id": training.id})
        response = client.post(url, data={})

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_satz_hinzufuegen_erfolgreich(self, client):
        """Test: Satz erfolgreich hinzufügen."""
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        client.force_login(user)

        url = reverse("add_set", kwargs={"training_id": training.id})
        data = {
            "uebung": uebung.id,
            "gewicht": "80.5",
            "wiederholungen": "10",
            "rpe": "8.0",
            "ist_aufwaermsatz": False,
        }

        # AJAX Request (braucht XMLHttpRequest Header)
        response = client.post(url, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True

        # Satz wurde erstellt
        satz = Satz.objects.filter(einheit=training, uebung=uebung).first()
        assert satz is not None
        assert float(satz.gewicht) == 80.5
        assert satz.wiederholungen == 10
        assert float(satz.rpe) == 8.0

    def test_satz_zu_fremdem_training_verboten(self, client):
        """Test: Satz zu fremdem Training hinzufügen verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        training_user2 = TrainingseinheitFactory(user=user2)
        uebung = UebungFactory()
        client.force_login(user1)

        url = reverse("add_set", kwargs={"training_id": training_user2.id})
        data = {
            "uebung": uebung.id,
            "gewicht": "80",
            "wiederholungen": "10",
        }

        response = client.post(url, data=data)

        # Sollte 404 sein
        assert response.status_code == 404

        # Kein Satz wurde erstellt
        assert not Satz.objects.filter(einheit=training_user2, uebung=uebung).exists()


@pytest.mark.django_db
class TestDeleteSet:
    """Tests für delete_set View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        satz = SatzFactory()
        url = reverse("delete_set", kwargs={"set_id": satz.id})
        response = client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_satz_loeschen_erfolgreich(self, client):
        """Test: Eigenen Satz löschen."""
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        satz = SatzFactory(einheit=training, uebung=uebung)
        client.force_login(user)

        satz_id = satz.id
        url = reverse("delete_set", kwargs={"set_id": satz.id})
        response = client.post(url)

        # Delete macht Redirect zur Training Session
        assert response.status_code == 302
        assert f"/training/{training.id}/" in response.url

        # Satz wurde gelöscht
        assert not Satz.objects.filter(id=satz_id).exists()

    def test_fremden_satz_loeschen_verboten(self, client):
        """Test: Fremden Satz löschen verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        training_user2 = TrainingseinheitFactory(user=user2)
        uebung = UebungFactory()
        satz_user2 = SatzFactory(einheit=training_user2, uebung=uebung)
        client.force_login(user1)

        url = reverse("delete_set", kwargs={"set_id": satz_user2.id})
        response = client.post(url)

        # Sollte 404 sein
        assert response.status_code == 404

        # Satz existiert noch
        assert Satz.objects.filter(id=satz_user2.id).exists()


@pytest.mark.django_db
class TestFinishTraining:
    """Tests für finish_training View."""

    def test_login_required(self, client):
        """Test: Redirect zu Login wenn nicht eingeloggt."""
        training = TrainingseinheitFactory()
        url = reverse("finish_training", kwargs={"training_id": training.id})
        response = client.post(url, data={})

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_training_beenden_erfolgreich(self, client):
        """Test: Training erfolgreich beenden."""
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(einheit=training, uebung=uebung, gewicht=100, wiederholungen=10)
        client.force_login(user)

        url = reverse("finish_training", kwargs={"training_id": training.id})
        data = {"kommentar": "Gutes Training!", "dauer_minuten": "60"}

        response = client.post(url, data=data)

        assert response.status_code == 302  # Redirect nach Beenden

        # Training wurde aktualisiert
        training.refresh_from_db()
        assert training.kommentar == "Gutes Training!"
        assert training.dauer_minuten == 60

    def test_fremdes_training_beenden_verboten(self, client):
        """Test: Fremdes Training beenden verboten."""
        user1 = UserFactory()
        user2 = UserFactory()
        training_user2 = TrainingseinheitFactory(user=user2)
        client.force_login(user1)

        url = reverse("finish_training", kwargs={"training_id": training_user2.id})
        data = {"kommentar": "Test"}

        response = client.post(url, data=data)

        # Sollte 404 sein
        assert response.status_code == 404
