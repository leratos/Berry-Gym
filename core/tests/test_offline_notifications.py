"""
Tests für Offline-Sync und Push-Notification Views.

Abgedeckt:
- sync_offline_data: Login-Schutz, JSON-Sync, Update, Fehlerbehandlung
- subscribe_push / unsubscribe_push: Login, Subscription-CRUD
- get_vapid_public_key: VAPID-Key-Ausgabe
"""

import json

from django.test import Client
from django.urls import reverse

import pytest

from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestSyncOfflineData:
    """Tests für POST /api/sync-offline/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.url = reverse("sync_offline_data")

    def _post(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect."""
        c = Client()
        resp = c.post(self.url, data=json.dumps([]), content_type="application/json")
        assert resp.status_code == 302

    def test_empty_list_returns_success(self):
        """Leere Liste → success True, 0 synced."""
        resp = self._post([])
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["synced_count"] == 0

    def test_create_new_satz(self):
        """Neuer Satz wird korrekt angelegt."""
        training = TrainingseinheitFactory(user=self.user)
        uebung = UebungFactory()

        payload = [
            {
                "id": "offline-1",
                "training_id": training.id,
                "uebung_id": uebung.id,
                "gewicht": "80.0",
                "wiederholungen": 10,
                "rpe": 8,
                "is_warmup": False,
                "superset_gruppe": 0,
                "notiz": "",
            }
        ]
        resp = self._post(payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        assert data["results"][0]["success"] is True
        assert data["results"][0]["updated"] is False

    def test_update_existing_satz(self):
        """Satz wird per Update-URL aktualisiert."""
        training = TrainingseinheitFactory(user=self.user)
        uebung = UebungFactory()
        satz = SatzFactory(einheit=training, uebung=uebung, gewicht=70, wiederholungen=8)

        payload = [
            {
                "id": "offline-2",
                "training_id": training.id,
                "uebung_id": uebung.id,
                "gewicht": "85.0",
                "wiederholungen": 6,
                "rpe": 9,
                "is_warmup": False,
                "superset_gruppe": 0,
                "notiz": "",
                "is_update": True,
                "action": f"/set/{satz.id}/update/",
            }
        ]
        resp = self._post(payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["success"] is True
        assert data["results"][0]["updated"] is True

    def test_training_not_found(self):
        """Fremdes Training → success False im Result."""
        uebung = UebungFactory()
        payload = [
            {
                "id": "offline-3",
                "training_id": 99999,
                "uebung_id": uebung.id,
                "gewicht": "60.0",
                "wiederholungen": 5,
            }
        ]
        resp = self._post(payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 0
        assert data["results"][0]["success"] is False

    def test_uebung_not_found(self):
        """Nicht-existierende Übung → success False."""
        training = TrainingseinheitFactory(user=self.user)
        payload = [
            {
                "id": "offline-4",
                "training_id": training.id,
                "uebung_id": 99999,
                "gewicht": "60.0",
                "wiederholungen": 5,
            }
        ]
        resp = self._post(payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["success"] is False

    def test_invalid_json_returns_400(self):
        """Invalides JSON → 400."""
        resp = self.client.post(self.url, data="kein-json", content_type="application/json")
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_user_isolation(self):
        """Fremdes Training kann nicht synchronisiert werden."""
        other_user = UserFactory()
        training = TrainingseinheitFactory(user=other_user)
        uebung = UebungFactory()
        payload = [
            {
                "id": "offline-5",
                "training_id": training.id,
                "uebung_id": uebung.id,
                "gewicht": "60.0",
                "wiederholungen": 5,
            }
        ]
        resp = self._post(payload)
        assert resp.json()["synced_count"] == 0

    def test_get_request_not_allowed(self):
        """GET → 405 Method Not Allowed."""
        resp = self.client.get(self.url)
        assert resp.status_code in (302, 405)  # Redirect (login) oder 405


@pytest.mark.django_db
class TestPushNotifications:
    """Tests für Push-Notification-Endpunkte."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def _subscribe_payload(self, endpoint="https://push.example.com/sub1"):
        return {
            "subscription": {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "test-p256dh-key",
                    "auth": "test-auth-secret",
                },
            }
        }

    # --- subscribe_push ---

    def test_subscribe_login_required(self):
        """Unauthentifizierter Zugriff → Redirect."""
        c = Client()
        url = reverse("subscribe_push")
        resp = c.post(url, data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 302

    def test_subscribe_creates_subscription(self):
        """POST erstellt PushSubscription."""
        url = reverse("subscribe_push")
        resp = self.client.post(
            url,
            data=json.dumps(self._subscribe_payload()),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "aktiviert" in data["message"]

    def test_subscribe_updates_existing(self):
        """Zweimaliger Subscribe-Aufruf → Update statt Fehler."""
        url = reverse("subscribe_push")
        payload = json.dumps(self._subscribe_payload("https://push.example.com/same"))
        self.client.post(url, data=payload, content_type="application/json")
        resp = self.client.post(url, data=payload, content_type="application/json")
        assert resp.status_code == 200
        assert "aktualisiert" in resp.json()["message"]

    def test_subscribe_missing_subscription_data(self):
        """POST ohne subscription-Key → 400."""
        url = reverse("subscribe_push")
        resp = self.client.post(url, data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 400

    # --- unsubscribe_push ---

    def test_unsubscribe_login_required(self):
        c = Client()
        url = reverse("unsubscribe_push")
        resp = c.post(url, data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 302

    def test_unsubscribe_deletes_subscription(self):
        """Löscht bestehende Subscription."""
        sub_url = reverse("subscribe_push")
        unsub_url = reverse("unsubscribe_push")
        endpoint = "https://push.example.com/to-delete"

        self.client.post(
            sub_url,
            data=json.dumps(self._subscribe_payload(endpoint)),
            content_type="application/json",
        )

        resp = self.client.post(
            unsub_url,
            data=json.dumps({"endpoint": endpoint}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_unsubscribe_missing_endpoint(self):
        """POST ohne endpoint → 400."""
        url = reverse("unsubscribe_push")
        resp = self.client.post(url, data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 400

    # --- get_vapid_public_key ---

    def test_vapid_key_login_required(self):
        c = Client()
        url = reverse("get_vapid_public_key")
        resp = c.get(url)
        assert resp.status_code == 302

    def test_vapid_key_returns_503_when_not_configured(self, settings):
        """VAPID-Key nicht konfiguriert → 503."""
        settings.VAPID_PUBLIC_KEY = None
        url = reverse("get_vapid_public_key")
        resp = self.client.get(url)
        assert resp.status_code == 503
