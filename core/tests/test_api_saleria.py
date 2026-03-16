"""
Tests für die Saleria read-only API (Elder-Berry AI-Assistent).
"""

from datetime import timedelta
from decimal import Decimal

from django.test import Client
from django.utils import timezone

import pytest

from core.models import Trainingseinheit
from core.tests.factories import (
    KoerperWerteFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)

SALERIA_TOKEN = "test-saleria-token-abc123"


def _set_training_date(training, dt):
    """Setzt datum trotz auto_now_add via QuerySet.update()."""
    Trainingseinheit.objects.filter(pk=training.pk).update(datum=dt)
    training.refresh_from_db()
    return training


@pytest.fixture
def saleria_settings(settings):
    """Konfiguriert Saleria-API-Settings für Tests."""
    settings.SALERIA_API_TOKEN = SALERIA_TOKEN
    settings.SALERIA_API_USER_ID = None  # Wird pro Test gesetzt
    return settings


@pytest.fixture
def api_user():
    """User für die Saleria API."""
    return UserFactory()


@pytest.fixture
def configured_settings(saleria_settings, api_user):
    """Settings mit konfiguriertem User."""
    saleria_settings.SALERIA_API_USER_ID = api_user.pk
    return saleria_settings


@pytest.fixture
def auth_client(configured_settings):
    """Client mit korrektem Bearer-Token."""
    client = Client()
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {SALERIA_TOKEN}"
    return client


@pytest.fixture
def anon_client():
    """Client ohne Auth-Header."""
    return Client()


# ---------------------------------------------------------------------------
# Auth-Tests
# ---------------------------------------------------------------------------


class TestSaleriaAuth:
    """Token-Authentifizierung für alle Endpoints."""

    ENDPOINTS = [
        "/api/saleria/summary/",
        "/api/saleria/last-training/",
        "/api/saleria/week/",
        "/api/saleria/prs/",
    ]

    def test_missing_auth_header_returns_401(self, anon_client, configured_settings):
        for url in self.ENDPOINTS:
            resp = anon_client.get(url)
            assert resp.status_code == 401, f"{url} should return 401 without auth"

    def test_invalid_token_returns_403(self, configured_settings):
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = "Bearer wrong-token"
        for url in self.ENDPOINTS:
            resp = client.get(url)
            assert resp.status_code == 403, f"{url} should return 403 with wrong token"

    def test_non_bearer_scheme_returns_401(self, configured_settings):
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = f"Basic {SALERIA_TOKEN}"
        for url in self.ENDPOINTS:
            resp = client.get(url)
            assert resp.status_code == 401, f"{url} should reject non-Bearer scheme"

    def test_unconfigured_token_returns_503(self, settings, api_user):
        settings.SALERIA_API_TOKEN = ""
        settings.SALERIA_API_USER_ID = api_user.pk
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = "Bearer anything"
        resp = client.get("/api/saleria/summary/")
        assert resp.status_code == 503

    def test_invalid_user_id_returns_500(self, settings):
        settings.SALERIA_API_TOKEN = SALERIA_TOKEN
        settings.SALERIA_API_USER_ID = 99999
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {SALERIA_TOKEN}"
        resp = client.get("/api/saleria/summary/")
        assert resp.status_code == 500

    def test_post_not_allowed(self, auth_client):
        for url in self.ENDPOINTS:
            resp = auth_client.post(url)
            assert resp.status_code == 405, f"{url} should reject POST"

    def test_valid_token_returns_200(self, auth_client):
        for url in self.ENDPOINTS:
            resp = auth_client.get(url)
            assert resp.status_code == 200, f"{url} should return 200"


# ---------------------------------------------------------------------------
# /api/saleria/summary/
# ---------------------------------------------------------------------------


class TestSaleriaSummary:

    def test_empty_data(self, auth_client):
        resp = auth_client.get("/api/saleria/summary/")
        data = resp.json()
        assert data["letztes_training"] is None
        assert data["trainings_diese_woche"] == 0
        assert data["aktuelles_gewicht"] is None

    def test_with_training_and_weight(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="Bankdrücken")
        training = TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            dauer_minuten=60,
        )
        SatzFactory(einheit=training, uebung=uebung, ist_aufwaermsatz=False)
        SatzFactory(einheit=training, uebung=uebung, ist_aufwaermsatz=True)
        KoerperWerteFactory(user=api_user, gewicht=Decimal("82.50"))

        resp = auth_client.get("/api/saleria/summary/")
        data = resp.json()

        assert data["letztes_training"] is not None
        assert data["letztes_training"]["dauer_minuten"] == 60
        # Nur 1 distinct Übung (Aufwärmsatz same Übung)
        assert data["letztes_training"]["uebungen_anzahl"] == 1
        assert data["trainings_diese_woche"] >= 1
        assert data["aktuelles_gewicht"]["gewicht_kg"] == 82.5

    def test_only_counts_completed_trainings(self, auth_client, api_user):
        TrainingseinheitFactory(user=api_user, abgeschlossen=False)
        resp = auth_client.get("/api/saleria/summary/")
        data = resp.json()
        assert data["letztes_training"] is None
        assert data["trainings_diese_woche"] == 0

    def test_does_not_leak_other_users(self, auth_client):
        other_user = UserFactory()
        TrainingseinheitFactory(user=other_user, abgeschlossen=True)
        KoerperWerteFactory(user=other_user, gewicht=Decimal("90.0"))

        resp = auth_client.get("/api/saleria/summary/")
        data = resp.json()
        assert data["letztes_training"] is None
        assert data["aktuelles_gewicht"] is None


# ---------------------------------------------------------------------------
# /api/saleria/last-training/
# ---------------------------------------------------------------------------


class TestSaleriaLastTraining:

    def test_no_training(self, auth_client):
        resp = auth_client.get("/api/saleria/last-training/")
        data = resp.json()
        assert data["training"] is None

    def test_returns_sets(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="Kniebeugen")
        training = TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            dauer_minuten=45,
            kommentar="Gutes Training",
        )
        SatzFactory(
            einheit=training,
            uebung=uebung,
            satz_nr=1,
            gewicht=Decimal("100.00"),
            wiederholungen=5,
            rpe=Decimal("8.0"),
            ist_aufwaermsatz=False,
        )
        SatzFactory(
            einheit=training,
            uebung=uebung,
            satz_nr=2,
            gewicht=Decimal("100.00"),
            wiederholungen=5,
            rpe=Decimal("8.5"),
            ist_aufwaermsatz=False,
        )

        resp = auth_client.get("/api/saleria/last-training/")
        data = resp.json()["training"]

        assert data["dauer_minuten"] == 45
        assert data["kommentar"] == "Gutes Training"
        assert data["ist_deload"] is False
        assert len(data["saetze"]) == 2
        assert data["saetze"][0]["uebung"] == "Kniebeugen"
        assert data["saetze"][0]["gewicht_kg"] == 100.0
        assert data["saetze"][0]["wiederholungen"] == 5
        assert data["saetze"][0]["rpe"] == 8.0

    def test_returns_latest_training(self, auth_client, api_user):
        old = TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            kommentar="Alt",
        )
        _set_training_date(old, timezone.now() - timedelta(days=3))

        TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            kommentar="Neu",
        )
        # new hat auto_now_add = now(), also neuer als old

        resp = auth_client.get("/api/saleria/last-training/")
        data = resp.json()["training"]
        assert data["kommentar"] == "Neu"


# ---------------------------------------------------------------------------
# /api/saleria/week/
# ---------------------------------------------------------------------------


class TestSaleriaWeek:

    def test_empty(self, auth_client):
        resp = auth_client.get("/api/saleria/week/")
        data = resp.json()
        assert data["trainings"] == []

    def test_returns_recent_trainings(self, auth_client, api_user):
        uebung1 = UebungFactory(bezeichnung="Bankdrücken")
        uebung2 = UebungFactory(bezeichnung="Rudern")

        t1 = TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            dauer_minuten=50,
        )
        _set_training_date(t1, timezone.now() - timedelta(days=1))
        SatzFactory(einheit=t1, uebung=uebung1)
        SatzFactory(einheit=t1, uebung=uebung2)

        t2 = TrainingseinheitFactory(
            user=api_user,
            abgeschlossen=True,
            dauer_minuten=40,
        )
        _set_training_date(t2, timezone.now() - timedelta(days=3))
        SatzFactory(einheit=t2, uebung=uebung1)

        resp = auth_client.get("/api/saleria/week/")
        data = resp.json()["trainings"]

        assert len(data) == 2
        # Sortiert nach Datum absteigend
        assert data[0]["dauer_minuten"] == 50
        assert data[0]["uebungen_anzahl"] == 2
        assert data[1]["dauer_minuten"] == 40
        assert data[1]["uebungen_anzahl"] == 1

    def test_excludes_old_trainings(self, auth_client, api_user):
        old = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        _set_training_date(old, timezone.now() - timedelta(days=10))

        resp = auth_client.get("/api/saleria/week/")
        assert resp.json()["trainings"] == []

    def test_excludes_incomplete_trainings(self, auth_client, api_user):
        TrainingseinheitFactory(user=api_user, abgeschlossen=False)
        resp = auth_client.get("/api/saleria/week/")
        assert resp.json()["trainings"] == []


# ---------------------------------------------------------------------------
# /api/saleria/prs/
# ---------------------------------------------------------------------------


class TestSaleriaPRs:

    def test_empty(self, auth_client):
        resp = auth_client.get("/api/saleria/prs/")
        data = resp.json()
        assert data["prs"] == []

    def test_calculates_1rm(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="Kreuzheben")
        training = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal("140.00"),
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )

        resp = auth_client.get("/api/saleria/prs/")
        prs = resp.json()["prs"]

        assert len(prs) == 1
        assert prs[0]["uebung"] == "Kreuzheben"
        # Epley: 140 * (1 + 5/30) = 140 * 1.1667 = 163.3
        assert prs[0]["estimated_1rm"] == pytest.approx(163.3, abs=0.1)
        assert prs[0]["gewicht_kg"] == 140.0
        assert prs[0]["wiederholungen"] == 5

    def test_picks_best_1rm_per_exercise(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="Bankdrücken")
        training = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        # Leichterer Satz
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal("60.00"),
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        # Schwerer Satz -> höherer 1RM
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal("80.00"),
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )

        prs = auth_client.get("/api/saleria/prs/").json()["prs"]
        assert len(prs) == 1
        # 80 * (1 + 5/30) = 93.3 > 60 * (1 + 10/30) = 80.0
        assert prs[0]["gewicht_kg"] == 80.0

    def test_excludes_warmup_sets(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="Curls")
        training = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal("30.00"),
            wiederholungen=10,
            ist_aufwaermsatz=True,
        )

        prs = auth_client.get("/api/saleria/prs/").json()["prs"]
        assert prs == []

    def test_excludes_old_data(self, auth_client, api_user):
        uebung = UebungFactory(bezeichnung="OHP")
        training = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        _set_training_date(training, timezone.now() - timedelta(days=60))
        SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal("50.00"),
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )

        prs = auth_client.get("/api/saleria/prs/").json()["prs"]
        assert prs == []

    def test_sorted_by_1rm_descending(self, auth_client, api_user):
        uebung_a = UebungFactory(bezeichnung="AAA Leicht")
        uebung_b = UebungFactory(bezeichnung="BBB Schwer")
        training = TrainingseinheitFactory(user=api_user, abgeschlossen=True)
        SatzFactory(
            einheit=training,
            uebung=uebung_a,
            gewicht=Decimal("40.00"),
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        SatzFactory(
            einheit=training,
            uebung=uebung_b,
            gewicht=Decimal("120.00"),
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )

        prs = auth_client.get("/api/saleria/prs/").json()["prs"]
        assert len(prs) == 2
        assert prs[0]["uebung"] == "BBB Schwer"
        assert prs[1]["uebung"] == "AAA Leicht"
