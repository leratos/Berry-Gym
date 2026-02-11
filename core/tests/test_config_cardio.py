"""
Phase 2.8 - Config & Cardio Tests
Testet: impressum, datenschutz, metriken_help,
        service_worker, manifest, favicon, get_last_set,
        cardio_list, cardio_add, cardio_delete
"""

from datetime import date, timedelta

from django.urls import reverse

import pytest

from core.models import CardioEinheit
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory

# ==============================================================================
# Config Views - Statische Seiten
# ==============================================================================


@pytest.mark.django_db
class TestStaticPages:
    """Tests für öffentliche statische Seiten (kein Login nötig)"""

    def test_impressum_geladen(self, client):
        """Impressum ist ohne Login erreichbar"""
        response = client.get(reverse("impressum"))
        assert response.status_code == 200

    def test_datenschutz_geladen(self, client):
        """Datenschutz ist ohne Login erreichbar"""
        response = client.get(reverse("datenschutz"))
        assert response.status_code == 200

    def test_metriken_help_erfordert_login(self, client):
        """Metriken-Hilfe erfordert Login"""
        response = client.get(reverse("metriken_help"))
        assert response.status_code == 302
        assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]

    def test_metriken_help_geladen(self, client):
        """Metriken-Hilfe lädt für eingeloggten User"""
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("metriken_help"))
        assert response.status_code == 200


# ==============================================================================
# PWA Endpoints
# ==============================================================================


@pytest.mark.django_db
class TestPwaEndpoints:
    """Tests für Service Worker, Manifest und Favicon"""

    def test_service_worker_antwortet(self, client):
        """Service Worker gibt 200 oder 404 zurück (je nach Datei-Existenz)"""
        response = client.get(reverse("service_worker"))
        assert response.status_code in [200, 404]

    def test_service_worker_content_type(self, client):
        """Service Worker hat JavaScript Content-Type wenn vorhanden"""
        response = client.get(reverse("service_worker"))
        if response.status_code == 200:
            assert "javascript" in response["Content-Type"]

    def test_manifest_antwortet(self, client):
        """Manifest gibt 200 oder 404 zurück"""
        response = client.get(reverse("manifest"))
        assert response.status_code in [200, 404]

    def test_manifest_content_type(self, client):
        """Manifest hat JSON Content-Type wenn vorhanden"""
        response = client.get(reverse("manifest"))
        if response.status_code == 200:
            assert "json" in response["Content-Type"]

    def test_favicon_antwortet(self, client):
        """Favicon gibt 200 oder 204 zurück"""
        response = client.get(reverse("favicon"))
        assert response.status_code in [200, 204]


# ==============================================================================
# get_last_set API
# ==============================================================================


@pytest.mark.django_db
class TestGetLastSet:
    """Tests für den get_last_set API-Endpunkt"""

    def test_get_last_set_erfordert_login(self, client):
        """Endpunkt erfordert Login"""
        uebung = UebungFactory()
        url = reverse("get_last_set", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_get_last_set_kein_satz_vorhanden(self, client):
        """Gibt success=False zurück wenn kein Satz vorhanden"""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        url = reverse("get_last_set", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_get_last_set_mit_satz(self, client):
        """Gibt Satz-Daten zurück wenn Satz vorhanden"""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=100.0,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        url = reverse("get_last_set", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "gewicht" in data
        assert "wiederholungen" in data
        assert "progression_hint" in data

    def test_get_last_set_ignoriert_aufwaermsatz(self, client):
        """Aufwärmsätze werden ignoriert"""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        # Nur Aufwärmsatz vorhanden
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=50.0,
            wiederholungen=10,
            ist_aufwaermsatz=True,
        )
        url = reverse("get_last_set", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_get_last_set_user_isolation(self, client):
        """User sieht nur eigene Sätze, nicht fremde"""
        user = UserFactory()
        anderer_user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=anderer_user)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=150.0,
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )
        url = reverse("get_last_set", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        data = response.json()
        assert data["success"] is False


# ==============================================================================
# Cardio Views
# ==============================================================================


def create_cardio(user, aktivitaet="LAUFEN", dauer=30, intensitaet="MODERAT", datum=None):
    """Hilfsfunktion: CardioEinheit direkt erstellen."""
    return CardioEinheit.objects.create(
        user=user,
        datum=datum or date.today(),
        aktivitaet=aktivitaet,
        dauer_minuten=dauer,
        intensitaet=intensitaet,
        notiz="",
    )


@pytest.mark.django_db
class TestCardioList:
    """Tests für die Cardio-Übersicht"""

    def test_cardio_list_erfordert_login(self, client):
        """Cardio-Liste erfordert Login"""
        response = client.get(reverse("cardio_list"))
        assert response.status_code == 302

    def test_cardio_list_geladen(self, client):
        """Cardio-Liste lädt für eingeloggten User"""
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("cardio_list"))
        assert response.status_code == 200

    def test_cardio_list_zeigt_eigene_einheiten(self, client):
        """Nur eigene Cardio-Einheiten werden angezeigt"""
        user = UserFactory()
        anderer = UserFactory()
        client.force_login(user)
        create_cardio(user, dauer=45)
        create_cardio(anderer, dauer=60)  # fremde Einheit - NICHT sichtbar
        response = client.get(reverse("cardio_list"))
        assert response.status_code == 200
        cardio_einheiten = response.context["cardio_einheiten"]
        assert cardio_einheiten.count() == 1

    def test_cardio_list_statistiken_im_context(self, client):
        """Context enthält Statistik-Variablen"""
        user = UserFactory()
        client.force_login(user)
        create_cardio(user, dauer=30)
        create_cardio(user, dauer=45)
        response = client.get(reverse("cardio_list"))
        assert "total_minuten" in response.context
        assert "total_einheiten" in response.context
        assert response.context["total_minuten"] == 75
        assert response.context["total_einheiten"] == 2

    def test_cardio_list_filtert_letzte_30_tage(self, client):
        """Standard: Nur Einheiten der letzten 30 Tage"""
        user = UserFactory()
        client.force_login(user)
        create_cardio(user, datum=date.today())
        create_cardio(user, datum=date.today() - timedelta(days=60))  # zu alt
        response = client.get(reverse("cardio_list"))
        assert response.context["cardio_einheiten"].count() == 1

    def test_cardio_list_show_all(self, client):
        """Mit ?all=1 werden alle Einheiten angezeigt"""
        user = UserFactory()
        client.force_login(user)
        create_cardio(user, datum=date.today())
        create_cardio(user, datum=date.today() - timedelta(days=60))
        response = client.get(reverse("cardio_list") + "?all=1")
        assert response.context["cardio_einheiten"].count() == 2


@pytest.mark.django_db
class TestCardioAdd:
    """Tests für das Hinzufügen von Cardio-Einheiten"""

    def test_cardio_add_erfordert_login(self, client):
        """cardio_add erfordert Login"""
        response = client.get(reverse("cardio_add"))
        assert response.status_code == 302

    def test_cardio_add_get_zeigt_formular(self, client):
        """GET zeigt Formular mit korrektem Context"""
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("cardio_add"))
        assert response.status_code == 200
        assert "aktivitaeten" in response.context
        assert "intensitaeten" in response.context
        assert "heute" in response.context

    def test_cardio_add_post_erstellt_einheit(self, client):
        """POST erstellt neue CardioEinheit und leitet weiter"""
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("cardio_add"),
            {
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "30",
                "intensitaet": "MODERAT",
                "datum": date.today().isoformat(),
                "notiz": "Test-Cardio",
            },
        )
        assert response.status_code == 302
        assert CardioEinheit.objects.filter(user=user, aktivitaet="LAUFEN").count() == 1

    def test_cardio_add_post_ohne_aktivitaet_schlaegt_fehl(self, client):
        """POST ohne Aktivität → Redirect mit Fehlermeldung"""
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("cardio_add"),
            {"dauer_minuten": "30", "datum": date.today().isoformat()},
        )
        assert response.status_code == 302
        assert CardioEinheit.objects.filter(user=user).count() == 0

    def test_cardio_add_post_ungueltige_dauer(self, client):
        """POST mit ungültiger Dauer → Redirect mit Fehlermeldung"""
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "abc"},
        )
        assert response.status_code == 302
        assert CardioEinheit.objects.filter(user=user).count() == 0

    def test_cardio_add_post_dauer_null_schlaegt_fehl(self, client):
        """POST mit Dauer=0 → Redirect mit Fehlermeldung"""
        user = UserFactory()
        client.force_login(user)
        response = client.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "0"},
        )
        assert response.status_code == 302
        assert CardioEinheit.objects.filter(user=user).count() == 0


@pytest.mark.django_db
class TestCardioDelete:
    """Tests für das Löschen von Cardio-Einheiten"""

    def test_cardio_delete_erfordert_login(self, client):
        """Delete erfordert Login"""
        user = UserFactory()
        cardio = create_cardio(user)
        response = client.post(reverse("cardio_delete", kwargs={"cardio_id": cardio.id}))
        assert response.status_code == 302
        # Nicht gelöscht weil nicht eingeloggt
        assert CardioEinheit.objects.filter(id=cardio.id).exists()

    def test_cardio_delete_post_loescht_einheit(self, client):
        """POST löscht eigene Einheit"""
        user = UserFactory()
        client.force_login(user)
        cardio = create_cardio(user)
        response = client.post(reverse("cardio_delete", kwargs={"cardio_id": cardio.id}))
        assert response.status_code == 302
        assert not CardioEinheit.objects.filter(id=cardio.id).exists()

    def test_cardio_delete_fremde_einheit_404(self, client):
        """Fremde Einheit löschen → 404"""
        user = UserFactory()
        anderer = UserFactory()
        client.force_login(user)
        cardio = create_cardio(anderer)
        response = client.post(reverse("cardio_delete", kwargs={"cardio_id": cardio.id}))
        assert response.status_code == 404
        assert CardioEinheit.objects.filter(id=cardio.id).exists()

    def test_cardio_delete_get_leitet_weiter(self, client):
        """GET-Request leitet zur Liste weiter (kein echtes Delete-Formular)"""
        user = UserFactory()
        client.force_login(user)
        cardio = create_cardio(user)
        response = client.get(reverse("cardio_delete", kwargs={"cardio_id": cardio.id}))
        assert response.status_code == 302
        assert CardioEinheit.objects.filter(id=cardio.id).exists()
