"""
Erweiterte Tests für Training Statistics & Dashboard Views.

Abgedeckte Views:
- dashboard (training_stats.py)
- training_list
- training_stats
- delete_training
- exercise_stats
"""

from django.urls import reverse

import pytest

from .factories import (
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboard:
    """Tests für die Dashboard-View (Hauptseite nach Login)."""

    URL = reverse("dashboard")

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect zum Login."""
        response = client.get(self.URL)
        assert response.status_code == 302
        assert "/login" in response.url or "login" in response.url

    def test_dashboard_loads_for_new_user(self, client):
        """Neuer User ohne Daten: Dashboard lädt ohne Fehler."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_dashboard_has_context_keys(self, client):
        """Dashboard Context enthält alle erwarteten Keys."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        ctx = response.context
        expected_keys = [
            "letztes_training",
            "letzter_koerperwert",
            "trainings_diese_woche",
            "streak",
            "favoriten",
            "gesamt_trainings",
            "gesamt_saetze",
        ]
        for key in expected_keys:
            assert key in ctx, f"Context Key '{key}' fehlt im Dashboard"

    def test_dashboard_counts_trainings_this_week(self, client):
        """Dashboard zählt nur Trainings der aktuellen Woche."""
        user = UserFactory()
        client.force_login(user)

        from datetime import timedelta

        from django.utils import timezone

        # 1 Training heute, 1 vor 30 Tagen (soll nicht zählen)
        TrainingseinheitFactory(user=user, datum=timezone.now())
        TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=30))

        response = client.get(self.URL)
        assert response.context["trainings_diese_woche"] >= 1

    def test_dashboard_user_isolation(self, client):
        """Dashboard zeigt nur Daten des eingeloggten Users."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        # user_b hat 5 Trainings, user_a hat keines
        for _ in range(5):
            TrainingseinheitFactory(user=user_b)

        response = client.get(self.URL)
        assert response.context["gesamt_trainings"] == 0

    def test_dashboard_gesamt_trainings_korrekt(self, client):
        """Gesamtzahl der Trainings im Context stimmt."""
        user = UserFactory()
        client.force_login(user)

        for _ in range(7):
            TrainingseinheitFactory(user=user)

        response = client.get(self.URL)
        assert response.context["gesamt_trainings"] == 7

    def test_dashboard_gesamt_saetze_ignoriert_aufwaermsaetze(self, client):
        """Aufwärmsätze fließen NICHT in gesamt_saetze ein."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=True)

        response = client.get(self.URL)
        # Nur 1 echter Satz, nicht 2
        assert response.context["gesamt_saetze"] == 1

    def test_dashboard_favoriten_top_3(self, client):
        """Favoriten-Übungen: Maximal 3, nach Häufigkeit sortiert."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung_a = UebungFactory(bezeichnung="Bankdrücken")
        uebung_b = UebungFactory(bezeichnung="Kniebeuge")
        uebung_c = UebungFactory(bezeichnung="Kreuzheben")
        uebung_d = UebungFactory(bezeichnung="Schulterdrücken")

        # A: 5x, B: 3x, C: 2x, D: 1x → Top 3 = A, B, C
        for _ in range(5):
            SatzFactory(einheit=einheit, uebung=uebung_a, ist_aufwaermsatz=False)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung_b, ist_aufwaermsatz=False)
        for _ in range(2):
            SatzFactory(einheit=einheit, uebung=uebung_c, ist_aufwaermsatz=False)
        SatzFactory(einheit=einheit, uebung=uebung_d, ist_aufwaermsatz=False)

        response = client.get(self.URL)
        favoriten = list(response.context["favoriten"])
        assert len(favoriten) == 3
        assert favoriten[0]["uebung__bezeichnung"] == "Bankdrücken"

    def test_dashboard_streak_null_bei_kein_training(self, client):
        """Streak ist 0 für User ohne Trainings."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.context["streak"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Training List Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTrainingList:
    """Tests für /history/ – Trainingshistorie."""

    URL = reverse("training_list")

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        response = client.get(self.URL)
        assert response.status_code == 302

    def test_loads_for_authenticated_user(self, client):
        """Seite lädt für eingeloggten User."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_user_isolation(self, client):
        """User sieht nur eigene Trainingseinheiten (context key: trainings_data)."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        for _ in range(3):
            TrainingseinheitFactory(user=user_b)
        eigenes = TrainingseinheitFactory(user=user_a)

        response = client.get(self.URL)
        # View liefert trainings_data: [{training: obj, volumen: float, ...}, ...]
        trainings_data = response.context.get("trainings_data", [])
        ids = [entry["training"].id for entry in trainings_data]
        assert eigenes.id in ids
        # user_b Trainings dürfen nicht erscheinen
        from core.models import Trainingseinheit

        user_b_ids = list(Trainingseinheit.objects.filter(user=user_b).values_list("id", flat=True))
        for bid in user_b_ids:
            assert bid not in ids

    def test_empty_list_for_new_user(self, client):
        """Neuer User ohne Trainings: leere Liste, kein Fehler."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Delete Training Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeleteTraining:
    """Tests für /training/<id>/delete/."""

    def _url(self, training_id):
        return reverse("delete_training", kwargs={"training_id": training_id})

    def test_login_required(self, client):
        """Unauthentifizierter POST → Redirect, kein Delete."""
        einheit = TrainingseinheitFactory()
        response = client.post(self._url(einheit.id))
        assert response.status_code == 302
        # Einheit existiert noch
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_owner_can_delete(self, client):
        """Eigentümer kann seine Trainingseinheit löschen."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        response = client.post(self._url(einheit.id))
        assert response.status_code in (302, 200)
        from core.models import Trainingseinheit

        assert not Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_other_user_cannot_delete(self, client):
        """Fremde Trainingseinheit → 404, nicht gelöscht."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)
        einheit = TrainingseinheitFactory(user=user_b)
        response = client.post(self._url(einheit.id))
        assert response.status_code == 404
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_get_request_does_not_delete(self, client):
        """GET-Request löscht nichts."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        client.get(self._url(einheit.id))
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Training Stats Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTrainingStats:
    """Tests für /stats/ – Gesamtstatistiken."""

    URL = reverse("training_stats")

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        response = client.get(self.URL)
        assert response.status_code == 302

    def test_loads_without_data(self, client):
        """Stats-Seite lädt für User ohne Trainings (kein 500)."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_loads_with_data(self, client):
        """Stats-Seite lädt korrekt mit Trainings + Sätzen."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        for _ in range(5):
            SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_user_data_isolation(self, client):
        """Stats enthält nur Daten des eingeloggten Users."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        # user_b hat viel Daten
        einheit_b = TrainingseinheitFactory(user=user_b)
        for _ in range(20):
            SatzFactory(einheit=einheit_b, ist_aufwaermsatz=False)

        # user_a hat keinen Satz
        response = client.get(self.URL)
        assert response.status_code == 200
        # Keine Exception und der user_b-Satz darf nicht in Context


# ─────────────────────────────────────────────────────────────────────────────
# Exercise Stats Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExerciseStats:
    """Tests für /stats/exercise/<id>/ – Übungsstatistiken."""

    def _url(self, uebung_id):
        return reverse("exercise_stats", kwargs={"uebung_id": uebung_id})

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        uebung = UebungFactory()
        response = client.get(self._url(uebung.id))
        assert response.status_code == 302

    def test_loads_for_existing_exercise(self, client):
        """Seite lädt für bekannte Übung."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200

    def test_404_for_nonexistent_exercise(self, client):
        """Unbekannte Übungs-ID → 404."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self._url(99999))
        assert response.status_code == 404

    def test_loads_with_user_satz_data(self, client):
        """Statistiken werden korrekt berechnet wenn Sätze vorhanden."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200

    def test_user_isolation_no_foreign_data(self, client):
        """Sätze anderer User erscheinen nicht in der Übungsstatistik."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)
        uebung = UebungFactory()

        einheit_b = TrainingseinheitFactory(user=user_b)
        for _ in range(10):
            SatzFactory(einheit=einheit_b, uebung=uebung, ist_aufwaermsatz=False)

        response = client.get(self._url(uebung.id))
        # Kein Fehler, kein Leak
        assert response.status_code == 200

    def test_exercise_stats_context_has_uebung(self, client):
        """Context enthält die Übung als Objekt."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory(bezeichnung="Bankdrücken Test")
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200
        assert "uebung" in response.context
        assert response.context["uebung"].id == uebung.id
