"""
Tests für N+1 Query Elimination in kritischen Views.

Verifikation: Query-Anzahl wächst NICHT linear mit der Anzahl von
Übungen oder Trainings (d.h. kein N+1-Problem mehr vorhanden).

Strategie: Jeder Test vergleicht Query-Counts mit 5 Items vs. 10 Items.
Bei korrekter Implementierung muss die Anzahl identisch sein.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from core.models import Plan, Trainingseinheit, Uebung
from core.tests.factories import (
    PlanFactory,
    PlanUebungFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)


def _add_exercises_to_plan(plan: Plan, count: int) -> list[Uebung]:
    """Fügt `count` Übungen zum Plan hinzu und gibt die Übungs-Objekte zurück."""
    uebungen = []
    for i in range(count):
        uebung = UebungFactory(bezeichnung=f"Übung N+1 Test {plan.id}-{i}")
        PlanUebungFactory(plan=plan, uebung=uebung, reihenfolge=i + 1)
        uebungen.append(uebung)
    return uebungen


def _add_sets_to_training(training: Trainingseinheit, uebungen: list[Uebung]) -> None:
    """Fügt für jede Übung 3 Sätze zum Training hinzu."""
    for i, uebung in enumerate(uebungen):
        for satz_nr in range(1, 4):
            SatzFactory(
                einheit=training,
                uebung=uebung,
                satz_nr=satz_nr,
                gewicht=80.0,
                wiederholungen=10,
                ist_aufwaermsatz=False,
                rpe=7.5,
            )


# ---------------------------------------------------------------------------
# training_list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainingListNoNPlusOne:
    """training_list darf nicht pro Training separate Satz-Queries absetzen."""

    def _count_queries_for_n_trainings(self, client, user, n: int) -> int:
        """Erstellt n Trainings und misst Query-Count für training_list."""
        uebung = UebungFactory(bezeichnung=f"Bankdrücken-{n}")
        for _ in range(n):
            training = TrainingseinheitFactory(user=user)
            _add_sets_to_training(training, [uebung])

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("training_list"))
        assert response.status_code == 200
        return len(ctx)

    def test_query_count_stable_with_more_trainings(self, client):
        """Query-Anzahl bei 5 Trainings == Query-Anzahl bei 10 Trainings."""
        user = UserFactory()
        client.force_login(user)

        queries_5 = self._count_queries_for_n_trainings(client, user, 5)

        # Reset: neuer User mit 10 Trainings
        user2 = UserFactory()
        client.force_login(user2)
        queries_10 = self._count_queries_for_n_trainings(client, user2, 10)

        assert queries_5 == queries_10, (
            f"N+1 erkannt in training_list: {queries_5} Queries für 5 Trainings, "
            f"{queries_10} Queries für 10 Trainings"
        )

    def test_query_count_bounded(self, client):
        """training_list darf nicht mehr als 15 Queries für 20 Trainings ausführen."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory(bezeichnung="Kniebeuge-Bound")
        for _ in range(20):
            training = TrainingseinheitFactory(user=user)
            _add_sets_to_training(training, [uebung])

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("training_list"))
        assert response.status_code == 200
        assert len(ctx) <= 15, f"Zu viele Queries für training_list mit 20 Trainings: {len(ctx)}"


# ---------------------------------------------------------------------------
# plan_details
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPlanDetailsNoNPlusOne:
    """plan_details darf nicht pro Übung separate Last-Set-Queries absetzen."""

    def _count_queries_for_n_exercises(self, client, user, n: int) -> int:
        """Erstellt Plan mit n Übungen und misst Query-Count für plan_details."""
        plan = PlanFactory(user=user)
        _add_exercises_to_plan(plan, n)

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("plan_details", args=[plan.id]))
        assert response.status_code == 200
        return len(ctx)

    def test_query_count_stable_with_more_exercises(self, client):
        """Query-Anzahl bei 5 Übungen == Query-Anzahl bei 10 Übungen."""
        user = UserFactory()
        client.force_login(user)

        queries_5 = self._count_queries_for_n_exercises(client, user, 5)
        queries_10 = self._count_queries_for_n_exercises(client, user, 10)

        assert queries_5 == queries_10, (
            f"N+1 erkannt in plan_details: {queries_5} Queries für 5 Übungen, "
            f"{queries_10} Queries für 10 Übungen"
        )

    def test_query_count_bounded(self, client):
        """plan_details darf nicht mehr als 15 Queries für 20 Übungen ausführen."""
        user = UserFactory()
        client.force_login(user)
        plan = PlanFactory(user=user)
        _add_exercises_to_plan(plan, 20)

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("plan_details", args=[plan.id]))
        assert response.status_code == 200
        assert len(ctx) <= 15, f"Zu viele Queries für plan_details mit 20 Übungen: {len(ctx)}"


# ---------------------------------------------------------------------------
# training_session (Gewichtsempfehlungen)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainingSessionNoNPlusOne:
    """training_session darf nicht pro Übung separate Empfehlungs-Queries absetzen."""

    def _setup_training_with_history(self, user, n_exercises: int):
        """
        Erstellt Training mit n Übungen + vorherige Sätze als Trainingshistorie.
        Gibt das aktuelle Training zurück.
        """
        plan = PlanFactory(user=user)
        uebungen = _add_exercises_to_plan(plan, n_exercises)

        # Vorherige Trainingseinheit für Empfehlungslogik
        prev_training = TrainingseinheitFactory(user=user, plan=plan)
        _add_sets_to_training(prev_training, uebungen)

        # Aktuelles Training (noch leer)
        current = Trainingseinheit.objects.create(user=user, plan=plan)
        return current

    def test_query_count_stable_with_more_exercises(self, client):
        """Query-Anzahl bei 5 Übungen == Query-Anzahl bei 8 Übungen."""
        user = UserFactory()
        client.force_login(user)

        training_5 = self._setup_training_with_history(user, 5)
        with CaptureQueriesContext(connection) as ctx_5:
            response = client.get(reverse("training_session", args=[training_5.id]))
        assert response.status_code == 200
        queries_5 = len(ctx_5)

        training_8 = self._setup_training_with_history(user, 8)
        with CaptureQueriesContext(connection) as ctx_8:
            response = client.get(reverse("training_session", args=[training_8.id]))
        assert response.status_code == 200
        queries_8 = len(ctx_8)

        assert queries_5 == queries_8, (
            f"N+1 erkannt in training_session: {queries_5} Queries für 5 Übungen, "
            f"{queries_8} Queries für 8 Übungen"
        )


# ---------------------------------------------------------------------------
# training_stats
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrainingStatsNoNPlusOne:
    """training_stats darf nicht pro Training separate Satz-Queries absetzen."""

    def _count_queries_for_n_trainings(self, client, user, n: int) -> int:
        uebung = UebungFactory(bezeichnung=f"Deadlift-Stats-{n}")
        for _ in range(n):
            training = TrainingseinheitFactory(user=user)
            _add_sets_to_training(training, [uebung])

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("training_stats"))
        assert response.status_code == 200
        return len(ctx)

    def test_query_count_stable_with_more_trainings(self, client):
        """Query-Anzahl bei 5 Trainings == Query-Anzahl bei 10 Trainings."""
        user = UserFactory()
        client.force_login(user)

        queries_5 = self._count_queries_for_n_trainings(client, user, 5)

        user2 = UserFactory()
        client.force_login(user2)
        queries_10 = self._count_queries_for_n_trainings(client, user2, 10)

        assert queries_5 == queries_10, (
            f"N+1 erkannt in training_stats: {queries_5} Queries für 5 Trainings, "
            f"{queries_10} Queries für 10 Trainings"
        )
