"""
Tests für core/views/config.py und core/views/notifications.py
"""

import json
from unittest.mock import mock_open, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Equipment, Plan, Satz, Trainingseinheit, Uebung


# ─────────────────────────────────────────────────────────────────────────────
# config.py – statische Seiten
# ─────────────────────────────────────────────────────────────────────────────
class TestStaticPages(TestCase):
    def test_impressum_get(self):
        response = self.client.get(reverse("impressum"))
        self.assertEqual(response.status_code, 200)

    def test_datenschutz_get(self):
        response = self.client.get(reverse("datenschutz"))
        self.assertEqual(response.status_code, 200)

    def test_metriken_help_login_required(self):
        response = self.client.get(reverse("metriken_help"))
        self.assertRedirects(
            response,
            "/accounts/login/?next=/help/metriken/",
            fetch_redirect_response=False,
        )

    def test_metriken_help_eingeloggt(self):
        user = User.objects.create_user(username="muser", password="pass1234")
        self.client.force_login(user)
        response = self.client.get(reverse("metriken_help"))
        self.assertEqual(response.status_code, 200)


class TestPwaEndpoints(TestCase):
    @patch("builtins.open", mock_open(read_data="self.skipWaiting();"))
    @patch("os.path.join", return_value="/fake/service-worker.js")
    def test_service_worker_gefunden(self, mock_join):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("os.path.join", return_value="/fake/service-worker.js")
    def test_service_worker_nicht_gefunden(self, mock_join, mock_open_fn):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 404)

    @patch("builtins.open", mock_open(read_data='{"name":"HomeGym"}'))
    @patch("os.path.join", return_value="/fake/manifest.json")
    def test_manifest_gefunden(self, mock_join):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("os.path.join", return_value="/fake/manifest.json")
    def test_manifest_nicht_gefunden(self, mock_join, mock_open_fn):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 404)

    @patch("os.path.join", return_value="/fake/icon.png")
    def test_favicon_nicht_gefunden_gibt_204(self, mock_join):
        response = self.client.get(reverse("favicon"))
        self.assertEqual(response.status_code, 204)


# ─────────────────────────────────────────────────────────────────────────────
# config.py – get_last_set API
# ─────────────────────────────────────────────────────────────────────────────
class TestGetLastSetApi(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="pass1234")
        self.client.force_login(self.user)
        eq = Equipment.objects.create(name="KOERPER")
        self.uebung = Uebung.objects.create(
            bezeichnung="Liegestütz",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        self.uebung.equipment.add(eq)
        self.plan = Plan.objects.create(name="Plan", user=self.user)

    def _session(self):
        return Trainingseinheit.objects.create(user=self.user, plan=self.plan, dauer_minuten=30)

    def test_kein_satz_vorhanden(self):
        response = self.client.get(reverse("get_last_set", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    def test_letzter_satz_zurueck(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        data = self.client.get(reverse("get_last_set", args=[self.uebung.id])).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["letztes_gewicht"], 80.0)

    def test_progression_bei_ziel_wdh_erreicht(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=12,
            ist_aufwaermsatz=False,
        )
        data = self.client.get(reverse("get_last_set", args=[self.uebung.id]) + "?ziel=8-12").json()
        self.assertTrue(data["success"])
        self.assertEqual(data["gewicht"], 82.5)  # +2.5 kg

    def test_progression_hint_bei_niedriger_rpe(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=70,
            wiederholungen=8,
            rpe=6.0,
            ist_aufwaermsatz=False,
        )
        data = self.client.get(reverse("get_last_set", args=[self.uebung.id])).json()
        self.assertIn("+2.5kg", data["progression_hint"])

    def test_aufwaermsatz_wird_ignoriert(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=40,
            wiederholungen=15,
            ist_aufwaermsatz=True,
        )
        data = self.client.get(reverse("get_last_set", args=[self.uebung.id])).json()
        self.assertFalse(data["success"])

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("get_last_set", args=[self.uebung.id]))
        self.assertEqual(response.status_code, 302)

    def test_ziel_einzelwert(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        response = self.client.get(reverse("get_last_set", args=[self.uebung.id]) + "?ziel=10")
        self.assertTrue(response.json()["success"])

    def test_ziel_ungueltig_fallback(self):
        session = self._session()
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=80,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        response = self.client.get(reverse("get_last_set", args=[self.uebung.id]) + "?ziel=abc")
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# notifications.py
# ─────────────────────────────────────────────────────────────────────────────
class TestPushNotifications(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="push_user", password="pass1234")
        self.client.force_login(self.user)

    def _sub_payload(self, endpoint="https://push.example.com/sub1"):
        return json.dumps(
            {
                "subscription": {
                    "endpoint": endpoint,
                    "keys": {"p256dh": "key123", "auth": "auth456"},
                }
            }
        )

    def test_subscribe_erfolg(self):
        response = self.client.post(
            reverse("subscribe_push"),
            data=self._sub_payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_subscribe_kein_body(self):
        response = self.client.post(
            reverse("subscribe_push"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_subscribe_login_required(self):
        self.client.logout()
        response = self.client.post(
            reverse("subscribe_push"), data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 302)

    def test_subscribe_update_bei_doppeltem_endpoint(self):
        # Zweimal gleicher Endpoint → update_or_create, kein Fehler
        payload = self._sub_payload("https://push.example.com/doppelt")
        self.client.post(reverse("subscribe_push"), data=payload, content_type="application/json")
        response = self.client.post(
            reverse("subscribe_push"), data=payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

    def test_unsubscribe_erfolg(self):
        self.client.post(
            reverse("subscribe_push"),
            data=self._sub_payload("https://push.example.com/sub2"),
            content_type="application/json",
        )
        response = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({"endpoint": "https://push.example.com/sub2"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_unsubscribe_kein_endpoint(self):
        response = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_nicht_vorhandener_endpoint(self):
        response = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({"endpoint": "https://gibt.es.nicht/xyz"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)

    def test_vapid_key_nicht_konfiguriert(self):
        with self.settings(VAPID_PUBLIC_KEY=None):
            response = self.client.get(reverse("get_vapid_public_key"))
        self.assertEqual(response.status_code, 503)

    def test_vapid_key_gibt_public_key(self):
        import base64

        # 91-Byte DER-Struktur simulieren (26 Byte Header + 65 Byte EC-Point)
        fake_der = b"\x00" * 26 + b"\x04" + b"\xab" * 64
        fake_pem = (
            "-----BEGIN PUBLIC KEY-----\n"
            + base64.b64encode(fake_der).decode()
            + "\n-----END PUBLIC KEY-----"
        )
        with self.settings(VAPID_PUBLIC_KEY=fake_pem):
            response = self.client.get(reverse("get_vapid_public_key"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("publicKey", response.json())
