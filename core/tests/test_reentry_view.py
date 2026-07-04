"""Tests für Phase 33.3 – Wiedereinstiegs-UI (View + Dashboard-Hinweis).

Deckt ab (Konzept §33.3):
- Auth erzwungen, strikt user-scoped,
- neutrale Anzeige ohne aktive Pause,
- Empfehlung mit Übung + Gewicht wird gerendert,
- medizinische Pause → prominenter ärztlicher-Freigabe-Disclaimer,
- Dashboard setzt `reentry_pause` im Kontext (Banner-Trigger).
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

import pytest

from core.models import Trainingseinheit
from core.tests.factories import (
    SatzFactory,
    TrainingseinheitFactory,
    TrainingsPauseFactory,
    UebungFactory,
    UserFactory,
)


def _session_am(user, tage_vor_heute, uebung, gewicht):
    """Trainingseinheit vor `tage_vor_heute` Tagen mit einem Working-Set."""
    when = timezone.localdate() - timedelta(days=tage_vor_heute)
    aware = timezone.make_aware(datetime(when.year, when.month, when.day, 12, 0))
    einheit = TrainingseinheitFactory(user=user, plan=None, ist_deload=False)
    Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
    SatzFactory(
        einheit=einheit,
        uebung=uebung,
        gewicht=Decimal(str(gewicht)),
        wiederholungen=8,
        ist_aufwaermsatz=False,
    )


def _frische_pause(user, *, medizinisch=False):
    """16-Tage-Pause, die vor 5 Tagen endete → aktiver Wiedereinstieg (Rampe 2 Wo.)."""
    heute = timezone.localdate()
    return TrainingsPauseFactory(
        user=user,
        start_datum=heute - timedelta(days=20),
        end_datum=heute - timedelta(days=5),
        grund="verletzung",
        aerztliche_freigabe_noetig=medizinisch,
    )


@pytest.mark.django_db
class TestReentryView:
    def test_erfordert_login(self, client):
        response = client.get(reverse("reentry_detail"))
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_ohne_pause_neutraler_hinweis(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("reentry_detail"))
        assert response.status_code == 200
        assert response.context["empfehlung"] is None
        assert "keine frische Trainingspause" in response.content.decode()

    def test_mit_pause_rendert_uebung_und_gewicht(self, client):
        user = UserFactory()
        bank = UebungFactory(bezeichnung="Bankdrücken")
        _session_am(user, 25, bank, 100)  # vor der Pause (Start vor 20 Tagen)
        _frische_pause(user)
        client.force_login(user)
        response = client.get(reverse("reentry_detail"))
        assert response.status_code == 200
        rec = response.context["empfehlung"]
        assert rec is not None
        assert rec["uebungen"][0]["uebung"] == bank
        body = response.content.decode()
        assert "Bankdrücken" in body

    def test_medizinische_pause_zeigt_aerztlichen_disclaimer(self, client):
        user = UserFactory()
        bank = UebungFactory(bezeichnung="Bankdrücken")
        _session_am(user, 25, bank, 100)
        _frische_pause(user, medizinisch=True)
        client.force_login(user)
        response = client.get(reverse("reentry_detail"))
        body = response.content.decode()
        assert response.context["empfehlung"]["medizinisch"] is True
        assert "ärztlicher Freigabe" in body

    def test_user_isolation(self, client):
        owner = UserFactory()
        other = UserFactory()
        _frische_pause(owner)
        client.force_login(other)
        response = client.get(reverse("reentry_detail"))
        # Fremde Pause darf keine Empfehlung erzeugen
        assert response.context["empfehlung"] is None


@pytest.mark.django_db
class TestDashboardHinweis:
    def test_dashboard_setzt_reentry_pause(self, client):
        user = UserFactory()
        pause = _frische_pause(user)
        client.force_login(user)
        response = client.get(reverse("dashboard"))
        assert response.status_code == 200
        assert response.context["reentry_pause"] == pause

    def test_dashboard_ohne_pause_kein_hinweis(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("dashboard"))
        assert response.status_code == 200
        assert response.context["reentry_pause"] is None
