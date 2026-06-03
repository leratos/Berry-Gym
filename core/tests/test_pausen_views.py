"""Tests für Phase 32.2 – CRUD-UI Trainingspausen + Cache-Invalidierung.

Deckt ab (Konzept §32.2 / §9.1+§9.7):
- Auth erzwungen (login_required) für alle vier Views,
- strikte User-Isolation (fremde Pausen → 404, nicht editier-/löschbar),
- rückwirkendes Anlegen, offene Pause anlegbar,
- Pause-vs-Pause-Overlap blockt (Fehler, kein Write),
- Overlap mit Wochen, die Sessions haben → Warnung, aber NICHT blockiert,
- Anlegen UND Löschen invalidieren `dashboard_computed_<user>` (⑬).
"""

from datetime import date, timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

import pytest

from core.models import TrainingsPause
from core.tests.factories import TrainingseinheitFactory, TrainingsPauseFactory, UserFactory


def _messages(response):
    return [m.message for m in response.context["messages"]]


@pytest.mark.django_db
class TestAuthUndIsolation:
    def test_list_erfordert_login(self, client):
        response = client.get(reverse("pausen_list"))
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_add_erfordert_login(self, client):
        response = client.get(reverse("pausen_add"))
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_edit_fremde_pause_404(self, client):
        owner = UserFactory()
        fremd = UserFactory()
        pause = TrainingsPauseFactory(user=owner)
        client.force_login(fremd)
        response = client.get(reverse("pausen_edit", args=[pause.id]))
        assert response.status_code == 404

    def test_delete_fremde_pause_404(self, client):
        owner = UserFactory()
        fremd = UserFactory()
        pause = TrainingsPauseFactory(user=owner)
        client.force_login(fremd)
        response = client.post(reverse("pausen_delete", args=[pause.id]))
        assert response.status_code == 404
        assert TrainingsPause.objects.filter(pk=pause.pk).exists()

    def test_list_zeigt_nur_eigene_pausen(self, client):
        owner = UserFactory()
        other = UserFactory()
        TrainingsPauseFactory(user=owner, notiz="MEINE")
        TrainingsPauseFactory(user=other, notiz="FREMDE")
        client.force_login(owner)
        response = client.get(reverse("pausen_list"))
        assert response.status_code == 200
        pausen = list(response.context["pausen"])
        assert all(p.user_id == owner.id for p in pausen)
        assert len(pausen) == 1


@pytest.mark.django_db
class TestAnlegen:
    def test_rueckwirkendes_anlegen(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("pausen_add"),
            {
                "start_datum": "2026-01-05",
                "end_datum": "2026-01-15",
                "grund": "krankheit",
                "notiz": "Grippe",
            },
            follow=True,
        )
        assert response.status_code == 200
        pause = TrainingsPause.objects.get(user=user)
        assert pause.start_datum == date(2026, 1, 5)
        assert pause.end_datum == date(2026, 1, 15)

    def test_offene_pause_anlegbar(self, client):
        user = UserFactory()
        client.force_login(user)
        client.post(
            reverse("pausen_add"),
            {"start_datum": "2026-01-05", "end_datum": "", "grund": "krankheit"},
        )
        pause = TrainingsPause.objects.get(user=user)
        assert pause.end_datum is None

    def test_overlap_pause_blockt(self, client):
        user = UserFactory()
        client.force_login(user)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10))
        response = client.post(
            reverse("pausen_add"),
            {"start_datum": "2026-01-05", "end_datum": "2026-01-20", "grund": "urlaub"},
        )
        # Re-Render des Formulars (kein Redirect), Pause NICHT angelegt
        assert response.status_code == 200
        assert TrainingsPause.objects.filter(user=user).count() == 1

    def test_end_vor_start_blockt(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("pausen_add"),
            {"start_datum": "2026-01-10", "end_datum": "2026-01-05", "grund": "urlaub"},
        )
        assert response.status_code == 200
        assert not TrainingsPause.objects.filter(user=user).exists()

    def test_fehlendes_startdatum_blockt(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("pausen_add"),
            {"start_datum": "", "end_datum": "", "grund": "urlaub"},
        )
        assert response.status_code == 200
        assert not TrainingsPause.objects.filter(user=user).exists()

    def test_overlap_mit_sessions_warnt_blockt_aber_nicht(self, client):
        """Pause über eine Woche mit bereits geloggter Session: Warnung, kein Block."""
        from datetime import datetime, time

        from core.models import Trainingseinheit

        user = UserFactory()
        client.force_login(user)
        heute = timezone.now().date()
        # Session-Datum EXPLIZIT in den Pausenzeitraum legen (Codex PR #201, P2):
        # TrainingseinheitFactory.datum ist zufällig; datum ist auto_now_add, daher
        # per .update() forcen (Repo-Pattern), statt auf Zufall/auto_now_add zu bauen.
        e = TrainingseinheitFactory(user=user)
        Trainingseinheit.objects.filter(pk=e.pk).update(
            datum=timezone.make_aware(datetime.combine(heute - timedelta(days=1), time(12, 0)))
        )
        response = client.post(
            reverse("pausen_add"),
            {
                "start_datum": (heute - timedelta(days=3)).isoformat(),
                "end_datum": heute.isoformat(),
                "grund": "krankheit",
            },
            follow=True,
        )
        assert response.status_code == 200
        assert TrainingsPause.objects.filter(user=user).count() == 1  # trotzdem angelegt
        assert any("bereits Trainings" in m for m in _messages(response))


@pytest.mark.django_db
class TestBearbeitenLoeschen:
    def test_edit_aktualisiert(self, client):
        user = UserFactory()
        client.force_login(user)
        pause = TrainingsPauseFactory(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        client.post(
            reverse("pausen_edit", args=[pause.id]),
            {"start_datum": "2026-01-01", "end_datum": "2026-01-12", "grund": "verletzung"},
        )
        pause.refresh_from_db()
        assert pause.end_datum == date(2026, 1, 12)
        assert pause.grund == "verletzung"

    def test_delete_entfernt_pause(self, client):
        user = UserFactory()
        client.force_login(user)
        pause = TrainingsPauseFactory(user=user)
        client.post(reverse("pausen_delete", args=[pause.id]))
        assert not TrainingsPause.objects.filter(pk=pause.pk).exists()


@pytest.mark.django_db
class TestFormularRenderUndFehlerpfade:
    """GET-Formulare + Fehlerpfade (Coverage der Render-/Except-Zweige)."""

    def test_add_get_rendert_formular(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse("pausen_add"))
        assert resp.status_code == 200

    def test_add_ungueltiges_datumsformat_rerender(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.post(reverse("pausen_add"), {"start_datum": "kaputt", "grund": "urlaub"})
        assert resp.status_code == 200  # Re-Render mit Fehlermeldung (ValueError-Zweig)
        assert not TrainingsPause.objects.filter(user=user).exists()

    def test_edit_get_rendert_formular(self, client):
        user = UserFactory()
        client.force_login(user)
        p = TrainingsPauseFactory(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10)
        )
        resp = client.get(reverse("pausen_edit", args=[p.id]))
        assert resp.status_code == 200

    def test_edit_offene_pause_get_rendert(self, client):
        """Edit-GET einer offenen Pause (end_datum=None) – deckt den ''-Zweig ab."""
        user = UserFactory()
        client.force_login(user)
        p = TrainingsPauseFactory(user=user, start_datum=date(2026, 1, 1), end_datum=None)
        resp = client.get(reverse("pausen_edit", args=[p.id]))
        assert resp.status_code == 200

    def test_edit_fehlendes_startdatum_rerender(self, client):
        user = UserFactory()
        client.force_login(user)
        p = TrainingsPauseFactory(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10)
        )
        resp = client.post(
            reverse("pausen_edit", args=[p.id]), {"start_datum": "", "grund": "urlaub"}
        )
        assert resp.status_code == 200  # Re-Render (ValidationError-Zweig im Edit)
        p.refresh_from_db()
        assert p.start_datum == date(2026, 1, 1)  # unverändert


@pytest.mark.django_db
class TestCacheInvalidierung:
    def test_anlegen_invalidiert_dashboard_cache(self, client):
        user = UserFactory()
        client.force_login(user)
        key = f"dashboard_computed_{user.id}"
        cache.set(key, "stale")
        client.post(
            reverse("pausen_add"),
            {"start_datum": "2026-01-05", "end_datum": "2026-01-15", "grund": "krankheit"},
        )
        assert cache.get(key) is None

    def test_loeschen_invalidiert_dashboard_cache(self, client):
        user = UserFactory()
        client.force_login(user)
        pause = TrainingsPauseFactory(user=user)
        key = f"dashboard_computed_{user.id}"
        cache.set(key, "stale")  # nach dem Anlegen setzen
        client.post(reverse("pausen_delete", args=[pause.id]))
        assert cache.get(key) is None
