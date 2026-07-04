"""Tests für Phase 33.1 – Flag `aerztliche_freigabe_noetig` auf TrainingsPause.

Deckt ab (Konzept §33.1):
- Default False (Bestandspausen bleiben nicht-medizinisch),
- Service create/update setzt das Flag,
- `update_pause` ohne Parameter lässt das Flag unverändert (Sentinel),
- View-POST mit/ohne Checkbox setzt True/False,
- Edit-Prefill hält das Flag und erlaubt Abwählen.
"""

from datetime import date

from django.urls import reverse

import pytest

from core.models import TrainingsPause
from core.services import pausen as pausen_service
from core.tests.factories import TrainingsPauseFactory, UserFactory


@pytest.mark.django_db
class TestFlagModelUndService:
    def test_default_ist_false(self):
        pause = TrainingsPauseFactory()
        pause.refresh_from_db()
        assert pause.aerztliche_freigabe_noetig is False

    def test_create_setzt_flag(self):
        user = UserFactory()
        pause = pausen_service.create_pause(
            user=user,
            start_datum=date(2026, 1, 1),
            end_datum=date(2026, 1, 10),
            grund="verletzung",
            aerztliche_freigabe_noetig=True,
        )
        pause.refresh_from_db()
        assert pause.aerztliche_freigabe_noetig is True

    def test_update_setzt_flag(self):
        user = UserFactory()
        pause = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        pausen_service.update_pause(pause, aerztliche_freigabe_noetig=True)
        pause.refresh_from_db()
        assert pause.aerztliche_freigabe_noetig is True

    def test_update_ohne_parameter_laesst_flag_unveraendert(self):
        """Sentinel-Semantik: ein Update anderer Felder darf das Flag nicht kippen."""
        user = UserFactory()
        pause = pausen_service.create_pause(
            user=user,
            start_datum=date(2026, 1, 1),
            end_datum=date(2026, 1, 10),
            grund="verletzung",
            aerztliche_freigabe_noetig=True,
        )
        pausen_service.update_pause(pause, notiz="nur die Notiz")
        pause.refresh_from_db()
        assert pause.aerztliche_freigabe_noetig is True


@pytest.mark.django_db
class TestFlagView:
    def test_post_mit_checkbox_setzt_true(self, client):
        user = UserFactory()
        client.force_login(user)
        client.post(
            reverse("pausen_add"),
            {
                "start_datum": "2026-01-05",
                "end_datum": "2026-01-15",
                "grund": "verletzung",
                "aerztliche_freigabe_noetig": "on",
            },
        )
        pause = TrainingsPause.objects.get(user=user)
        assert pause.aerztliche_freigabe_noetig is True

    def test_post_ohne_checkbox_setzt_false(self, client):
        user = UserFactory()
        client.force_login(user)
        client.post(
            reverse("pausen_add"),
            {"start_datum": "2026-01-05", "end_datum": "2026-01-15", "grund": "urlaub"},
        )
        pause = TrainingsPause.objects.get(user=user)
        assert pause.aerztliche_freigabe_noetig is False

    def test_edit_kann_flag_abwaehlen(self, client):
        user = UserFactory()
        client.force_login(user)
        pause = TrainingsPauseFactory(
            user=user,
            start_datum=date(2026, 1, 5),
            end_datum=date(2026, 1, 15),
            aerztliche_freigabe_noetig=True,
        )
        # POST ohne Checkbox → Flag wird abgewählt
        client.post(
            reverse("pausen_edit", args=[pause.id]),
            {"start_datum": "2026-01-05", "end_datum": "2026-01-15", "grund": "krankheit"},
        )
        pause.refresh_from_db()
        assert pause.aerztliche_freigabe_noetig is False

    def test_edit_prefill_enthaelt_flag(self, client):
        user = UserFactory()
        client.force_login(user)
        pause = TrainingsPauseFactory(user=user, aerztliche_freigabe_noetig=True)
        response = client.get(reverse("pausen_edit", args=[pause.id]))
        assert response.status_code == 200
        assert response.context["values"]["aerztliche_freigabe_noetig"] is True
