"""
Phase 2.6 - Exercise Library Tests
Testet: uebungen_auswahl, muscle_map, uebung_detail, exercise_detail,
        toggle_favorit, toggle_favorite, create_custom_uebung, get_alternative_exercises
"""

import json

from django.urls import reverse

import pytest

from core.tests.factories import UebungFactory, UserFactory


@pytest.mark.django_db
class TestUebungenAuswahlView:
    """Tests für die Übungsübersicht (Bibliothek)"""

    def test_uebungen_auswahl_erfordert_login(self, client):
        """Nicht eingeloggte User werden zu Login weitergeleitet"""
        url = reverse("uebungen_auswahl")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]

    def test_uebungen_auswahl_geladen(self, client):
        """Seite lädt erfolgreich für eingeloggten User"""
        user = UserFactory()
        UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST")
        client.force_login(user)
        url = reverse("uebungen_auswahl")
        response = client.get(url)
        assert response.status_code == 200

    def test_uebungen_auswahl_zeigt_globale_uebungen(self, client):
        """Globale Übungen (is_custom=False) erscheinen in der Übersicht"""
        user = UserFactory()
        UebungFactory(bezeichnung="Kniebeugen", muskelgruppe="BEINE_QUAD", is_custom=False)
        client.force_login(user)
        url = reverse("uebungen_auswahl")
        response = client.get(url)
        assert response.status_code == 200
        assert "uebungen_nach_gruppe" in response.context

    def test_uebungen_auswahl_zeigt_eigene_custom_uebungen(self, client):
        """Eigene Custom-Übungen des Users erscheinen in der Bibliothek"""
        user = UserFactory()
        custom = UebungFactory(
            bezeichnung="Meine Übung",
            is_custom=True,
            created_by=user,
            muskelgruppe="BRUST",
        )
        client.force_login(user)
        url = reverse("uebungen_auswahl")
        response = client.get(url)
        assert response.status_code == 200
        # Custom-Übung des Users muss in irgendeiner Gruppe erscheinen
        alle_uebungen = [
            u for gruppe in response.context["uebungen_nach_gruppe"].values() for u in gruppe
        ]
        ids = [u.id for u in alle_uebungen]
        assert custom.id in ids

    def test_fremde_custom_uebungen_nicht_sichtbar(self, client):
        """Custom-Übungen anderer User sind NICHT sichtbar"""
        user = UserFactory()
        other_user = UserFactory()
        fremde = UebungFactory(
            bezeichnung="Fremde Übung",
            is_custom=True,
            created_by=other_user,
            muskelgruppe="BRUST",
        )
        client.force_login(user)
        url = reverse("uebungen_auswahl")
        response = client.get(url)
        alle_uebungen = [
            u for gruppe in response.context["uebungen_nach_gruppe"].values() for u in gruppe
        ]
        ids = [u.id for u in alle_uebungen]
        assert fremde.id not in ids


@pytest.mark.django_db
class TestMuscleMapView:
    """Tests für die interaktive Muskel-Karte"""

    def test_muscle_map_erfordert_login(self, client):
        url = reverse("muscle_map")
        response = client.get(url)
        assert response.status_code == 302

    def test_muscle_map_geladen(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("muscle_map")
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestUebungDetailView:
    """Tests für die Übungs-Detailseite"""

    def test_uebung_detail_erfordert_login(self, client):
        uebung = UebungFactory()
        url = reverse("uebung_detail", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_uebung_detail_geladen(self, client):
        user = UserFactory()
        uebung = UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST")
        client.force_login(user)
        url = reverse("uebung_detail", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200

    def test_uebung_detail_404_bei_unbekannter_id(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("uebung_detail", kwargs={"uebung_id": 99999})
        response = client.get(url)
        assert response.status_code == 404

    def test_exercise_detail_geladen(self, client):
        """Zweite Detail-View (exercise_detail) funktioniert ebenfalls"""
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BIZEPS")
        client.force_login(user)
        url = reverse("exercise_detail", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestToggleFavoritViews:
    """Tests für Favoriten-Toggle (beide Endpoints)"""

    def test_toggle_favorit_erfordert_login(self, client):
        uebung = UebungFactory()
        url = reverse("toggle_favorit", kwargs={"uebung_id": uebung.id})
        response = client.post(url)
        assert response.status_code == 302

    def test_toggle_favorit_hinzufuegen(self, client):
        """Übung wird zu Favoriten hinzugefügt"""
        user = UserFactory()
        uebung = UebungFactory()
        client.force_login(user)
        url = reverse("toggle_favorit", kwargs={"uebung_id": uebung.id})
        response = client.post(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["is_favorit"] is True
        assert user in uebung.favoriten.all()

    def test_toggle_favorit_entfernen(self, client):
        """Übung wird aus Favoriten entfernt wenn bereits drin"""
        user = UserFactory()
        uebung = UebungFactory()
        uebung.favoriten.add(user)
        client.force_login(user)
        url = reverse("toggle_favorit", kwargs={"uebung_id": uebung.id})
        response = client.post(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["is_favorit"] is False
        assert user not in uebung.favoriten.all()

    def test_toggle_favorit_message_enthalten(self, client):
        """JSON-Antwort enthält eine message"""
        user = UserFactory()
        uebung = UebungFactory()
        client.force_login(user)
        url = reverse("toggle_favorit", kwargs={"uebung_id": uebung.id})
        response = client.post(url)
        data = json.loads(response.content)
        assert "message" in data

    def test_toggle_favorite_json_response(self, client):
        """Zweiter Toggle-Endpoint gibt is_favorite zurück"""
        user = UserFactory()
        uebung = UebungFactory()
        client.force_login(user)
        url = reverse("toggle_favorite", kwargs={"uebung_id": uebung.id})
        response = client.post(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "is_favorite" in data

    def test_toggle_favorit_404_unbekannte_uebung(self, client):
        """404 bei nicht existierender Übung"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("toggle_favorit", kwargs={"uebung_id": 99999})
        response = client.post(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestCreateCustomUebung:
    """Tests für das Erstellen eigener Übungen"""

    def _post_json(self, client, url, data):
        return client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_create_custom_erfordert_login(self, client):
        url = reverse("create_custom_uebung")
        response = self._post_json(client, url, {"bezeichnung": "Test"})
        assert response.status_code == 302

    def test_create_custom_uebung_erfolg(self, client):
        """Neue Custom-Übung wird korrekt erstellt"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("create_custom_uebung")
        response = self._post_json(
            client,
            url,
            {
                "bezeichnung": "Mein Curl",
                "muskelgruppe": "BIZEPS",
                "gewichts_typ": "GESAMT",
                "bewegungstyp": "ISOLATION",
            },
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert "uebung_id" in data

    def test_create_custom_ohne_bezeichnung_schlaegt_fehl(self, client):
        """Fehlende Bezeichnung → 400 Bad Request"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("create_custom_uebung")
        response = self._post_json(
            client,
            url,
            {
                "bezeichnung": "",
                "muskelgruppe": "BRUST",
            },
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False

    def test_create_custom_ohne_muskelgruppe_schlaegt_fehl(self, client):
        """Fehlende Muskelgruppe → 400 Bad Request"""
        user = UserFactory()
        client.force_login(user)
        url = reverse("create_custom_uebung")
        response = self._post_json(
            client,
            url,
            {
                "bezeichnung": "Neues Gerät",
            },
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False

    def test_create_custom_duplikat_schlaegt_fehl(self, client):
        """Gleicher Name für denselben User → 400"""
        user = UserFactory()
        UebungFactory(
            bezeichnung="Mein Curl", is_custom=True, created_by=user, muskelgruppe="BIZEPS"
        )
        client.force_login(user)
        url = reverse("create_custom_uebung")
        response = self._post_json(
            client,
            url,
            {
                "bezeichnung": "Mein Curl",
                "muskelgruppe": "BIZEPS",
            },
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False

    def test_create_custom_anderer_user_gleicher_name_erlaubt(self, client):
        """Gleicher Name bei anderem User ist erlaubt"""
        user_a = UserFactory()
        user_b = UserFactory()
        UebungFactory(
            bezeichnung="Mein Curl", is_custom=True, created_by=user_a, muskelgruppe="BIZEPS"
        )
        client.force_login(user_b)
        url = reverse("create_custom_uebung")
        response = self._post_json(
            client,
            url,
            {
                "bezeichnung": "Mein Curl",
                "muskelgruppe": "BIZEPS",
            },
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True

    def test_create_custom_setzt_is_custom_flag(self, client):
        """Erstellte Übung hat is_custom=True und created_by=user"""
        from core.models import Uebung

        user = UserFactory()
        client.force_login(user)
        url = reverse("create_custom_uebung")
        self._post_json(
            client,
            url,
            {
                "bezeichnung": "Unique Übung XYZ",
                "muskelgruppe": "BAUCH",
            },
        )
        uebung = Uebung.objects.get(bezeichnung__iexact="Unique Übung XYZ", created_by=user)
        assert uebung.is_custom is True
        assert uebung.created_by == user


@pytest.mark.django_db
class TestGetAlternativeExercises:
    """Tests für den Alternativen-Empfehlungs-Endpoint"""

    def test_alternatives_erfordert_login(self, client):
        uebung = UebungFactory()
        url = reverse("get_alternative_exercises", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_alternatives_gibt_json_zurueck(self, client):
        """Endpoint gibt JSON mit alternatives-Liste zurück"""
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BRUST", bewegungstyp="DRUECKEN")
        client.force_login(user)
        url = reverse("get_alternative_exercises", kwargs={"uebung_id": uebung.id})
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "alternatives" in data or "exercises" in data or isinstance(data, list)

    def test_alternatives_404_bei_unbekannter_uebung(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("get_alternative_exercises", kwargs={"uebung_id": 99999})
        response = client.get(url)
        assert response.status_code == 404
