"""
Tests für API Endpoints – Phase 5.5

Abgedeckte Views:
- core/views/api_plan_sharing.py (api_group_plans, api_ungroup_plans, api_delete_plan,
  api_delete_group, api_rename_group, api_reorder_group, api_search_users,
  api_share_plan_with_user, api_unshare_plan_with_user, api_share_group_with_user,
  api_unshare_group_with_user, api_get_plan_shares, api_get_group_shares,
  _find_plan_index, _calc_reorder_index)
- core/views/notifications.py (subscribe_push, unsubscribe_push, get_vapid_public_key)
- core/views/offline.py (sync_offline_data, _process_single_item, _process_update_item,
  _apply_item_to_satz)
"""

import json
import uuid
from decimal import Decimal

from django.urls import reverse

import pytest

from .factories import PlanFactory, SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory

# ---------------------------------------------------------------------------
# Helper: JSON POST
# ---------------------------------------------------------------------------


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


# ===========================================================================
# Unit-Tests: _find_plan_index & _calc_reorder_index (keine DB nötig)
# ===========================================================================


class TestFindPlanIndex:
    def test_plan_gefunden(self):
        from types import SimpleNamespace

        from core.views.api_plan_sharing import _find_plan_index

        p1 = SimpleNamespace(id=10)
        p2 = SimpleNamespace(id=20)
        p3 = SimpleNamespace(id=30)
        assert _find_plan_index([p1, p2, p3], 20) == 1

    def test_plan_nicht_gefunden(self):
        from types import SimpleNamespace

        from core.views.api_plan_sharing import _find_plan_index

        p = SimpleNamespace(id=99)
        assert _find_plan_index([p], 42) is None

    def test_leere_liste(self):
        from core.views.api_plan_sharing import _find_plan_index

        assert _find_plan_index([], 1) is None

    def test_erster_eintrag(self):
        from types import SimpleNamespace

        from core.views.api_plan_sharing import _find_plan_index

        p = SimpleNamespace(id=5)
        assert _find_plan_index([p], 5) == 0


class TestCalcReorderIndex:
    def test_up_von_mitte(self):
        from core.views.api_plan_sharing import _calc_reorder_index

        assert _calc_reorder_index("up", 2, 5) == 1

    def test_up_vom_anfang_nicht_moeglich(self):
        from core.views.api_plan_sharing import _calc_reorder_index

        assert _calc_reorder_index("up", 0, 5) is None

    def test_down_von_mitte(self):
        from core.views.api_plan_sharing import _calc_reorder_index

        assert _calc_reorder_index("down", 2, 5) == 3

    def test_down_vom_ende_nicht_moeglich(self):
        from core.views.api_plan_sharing import _calc_reorder_index

        assert _calc_reorder_index("down", 4, 5) is None

    def test_unbekannte_richtung_gibt_none(self):
        from core.views.api_plan_sharing import _calc_reorder_index

        assert _calc_reorder_index("sideways", 2, 5) is None


# ===========================================================================
# api_group_plans
# ===========================================================================


@pytest.mark.django_db
class TestApiGroupPlans:
    URL = reverse("api_group_plans")

    def test_login_required(self, client):
        resp = post_json(client, self.URL, {"plan_ids": [1, 2]})
        assert resp.status_code == 302

    def test_weniger_als_2_plaene_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"plan_ids": [1]})
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_leere_plan_ids_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"plan_ids": []})
        assert resp.status_code == 400

    def test_erfolgreiche_gruppierung(self, client):
        user = UserFactory()
        p1 = PlanFactory(user=user)
        p2 = PlanFactory(user=user)
        client.force_login(user)
        resp = post_json(client, self.URL, {"plan_ids": [p1.id, p2.id], "gruppe_name": "Push"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "gruppe_id" in data
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.gruppe_id == p2.gruppe_id

    def test_fremde_plaene_werden_nicht_gruppiert(self, client):
        user_a = UserFactory()
        user_b = UserFactory()
        p1 = PlanFactory(user=user_a)
        p_fremd = PlanFactory(user=user_b)
        client.force_login(user_a)
        # user_a versucht fremden Plan in Gruppe aufzunehmen
        resp = post_json(client, self.URL, {"plan_ids": [p1.id, p_fremd.id]})
        assert resp.status_code == 200
        # Fremder Plan darf nicht in Gruppe von user_a landen
        p_fremd.refresh_from_db()
        assert p_fremd.gruppe_id is None


# ===========================================================================
# api_ungroup_plans
# ===========================================================================


@pytest.mark.django_db
class TestApiUngroupPlans:
    URL = reverse("api_ungroup_plans")

    def test_login_required(self, client):
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 302

    def test_fehlende_gruppe_id_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 400

    def test_erfolgreiche_auflosung(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        p1 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_name="Test")
        p2 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_name="Test")
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(gruppe_id)})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.gruppe_id is None
        assert p2.gruppe_id is None


# ===========================================================================
# api_delete_plan
# ===========================================================================


@pytest.mark.django_db
class TestApiDeletePlan:
    URL = reverse("api_delete_plan")

    def test_login_required(self, client):
        resp = post_json(client, self.URL, {"plan_id": 1})
        assert resp.status_code == 302

    def test_fehlende_plan_id_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 400

    def test_fremder_plan_gibt_404(self, client):
        user_a = UserFactory()
        user_b = UserFactory()
        plan = PlanFactory(user=user_b)
        client.force_login(user_a)
        resp = post_json(client, self.URL, {"plan_id": plan.id})
        assert resp.status_code == 404

    def test_erfolgreiche_loeschung(self, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        plan_id = plan.id
        client.force_login(user)
        resp = post_json(client, self.URL, {"plan_id": plan_id})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        from core.models import Plan

        assert not Plan.objects.filter(id=plan_id).exists()

    def test_nicht_existierender_plan_gibt_404(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"plan_id": 99999})
        assert resp.status_code == 404


# ===========================================================================
# api_delete_group
# ===========================================================================


@pytest.mark.django_db
class TestApiDeleteGroup:
    URL = reverse("api_delete_group")

    def test_fehlende_gruppe_id_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 400

    def test_keine_plaene_in_gruppe_gibt_404(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_erfolgreiche_loeschung_der_gruppe(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        PlanFactory(user=user, gruppe_id=gruppe_id)
        PlanFactory(user=user, gruppe_id=gruppe_id)
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(gruppe_id)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        from core.models import Plan

        assert Plan.objects.filter(gruppe_id=gruppe_id).count() == 0


# ===========================================================================
# api_rename_group
# ===========================================================================


@pytest.mark.django_db
class TestApiRenameGroup:
    URL = reverse("api_rename_group")

    def test_fehlende_gruppe_id_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"new_name": "Neuer Name"})
        assert resp.status_code == 400

    def test_leerer_name_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(uuid.uuid4()), "new_name": ""})
        assert resp.status_code == 400

    def test_nur_whitespace_name_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(uuid.uuid4()), "new_name": "   "})
        assert resp.status_code == 400

    def test_keine_plaene_gibt_404(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(uuid.uuid4()), "new_name": "Push"})
        assert resp.status_code == 404

    def test_erfolgreiches_umbenennen(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        p1 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_name="Alt")
        p2 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_name="Alt")
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(gruppe_id), "new_name": "Neu"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.gruppe_name == "Neu"
        assert p2.gruppe_name == "Neu"


# ===========================================================================
# api_reorder_group
# ===========================================================================


@pytest.mark.django_db
class TestApiReorderGroup:
    URL = reverse("api_reorder_group")

    def test_fehlende_parameter_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"gruppe_id": str(uuid.uuid4())})
        assert resp.status_code == 400

    def test_keine_plaene_gibt_404(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(
            client,
            self.URL,
            {"gruppe_id": str(uuid.uuid4()), "plan_id": 99, "direction": "up"},
        )
        assert resp.status_code == 404

    def test_plan_nicht_in_gruppe_gibt_404(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        PlanFactory(user=user, gruppe_id=gruppe_id)
        client.force_login(user)
        resp = post_json(
            client,
            self.URL,
            {"gruppe_id": str(gruppe_id), "plan_id": 99999, "direction": "up"},
        )
        assert resp.status_code == 404

    def test_up_an_erster_position_keine_aenderung(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        p1 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_reihenfolge=0)
        PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_reihenfolge=1)
        client.force_login(user)
        resp = post_json(
            client,
            self.URL,
            {"gruppe_id": str(gruppe_id), "plan_id": p1.id, "direction": "up"},
        )
        assert resp.status_code == 200
        # Kein Fehler, aber keine Änderung
        assert resp.json()["success"] is True

    def test_down_verschiebt_plan(self, client):
        user = UserFactory()
        gruppe_id = uuid.uuid4()
        p1 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_reihenfolge=0)
        p2 = PlanFactory(user=user, gruppe_id=gruppe_id, gruppe_reihenfolge=1)
        client.force_login(user)
        resp = post_json(
            client,
            self.URL,
            {"gruppe_id": str(gruppe_id), "plan_id": p1.id, "direction": "down"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        p1.refresh_from_db()
        p2.refresh_from_db()
        # p1 soll jetzt Reihenfolge 1 haben, p2 Reihenfolge 0
        assert p1.gruppe_reihenfolge == 1
        assert p2.gruppe_reihenfolge == 0


# ===========================================================================
# api_search_users
# ===========================================================================


@pytest.mark.django_db
class TestApiSearchUsers:
    URL = reverse("api_search_users")

    def test_login_required(self, client):
        resp = client.get(self.URL, {"q": "test"})
        assert resp.status_code == 302

    def test_query_unter_2_zeichen_gibt_leere_liste(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL, {"q": "a"})
        assert resp.status_code == 200
        assert resp.json()["users"] == []

    def test_eigener_user_wird_nicht_zurueckgegeben(self, client):
        user = UserFactory(username="suchender")
        client.force_login(user)
        resp = client.get(self.URL, {"q": "such"})
        usernames = [u["username"] for u in resp.json()["users"]]
        assert "suchender" not in usernames

    def test_anderen_user_finden(self, client):
        user = UserFactory()
        UserFactory(username="trainingspartner_xyz")
        client.force_login(user)
        resp = client.get(self.URL, {"q": "trainingspartner"})
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()["users"]]
        assert "trainingspartner_xyz" in usernames

    def test_leere_query_gibt_leere_liste(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL, {"q": ""})
        assert resp.json()["users"] == []


# ===========================================================================
# api_share_plan_with_user & api_unshare_plan_with_user
# ===========================================================================


@pytest.mark.django_db
class TestApiSharePlanWithUser:
    SHARE_URL = reverse("api_share_plan_with_user")
    UNSHARE_URL = reverse("api_unshare_plan_with_user")

    def test_fehlende_parameter_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.SHARE_URL, {"plan_id": 1})
        assert resp.status_code == 400

    def test_user_nicht_gefunden_gibt_404(self, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        resp = post_json(
            client, self.SHARE_URL, {"plan_id": plan.id, "username": "gibts_nicht_xyz"}
        )
        assert resp.status_code == 404

    def test_mit_sich_selbst_teilen_gibt_400(self, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        resp = post_json(client, self.SHARE_URL, {"plan_id": plan.id, "username": user.username})
        assert resp.status_code == 400
        assert "selbst" in resp.json()["error"]

    def test_doppeltes_teilen_gibt_400(self, client):
        user = UserFactory()
        partner = UserFactory()
        plan = PlanFactory(user=user)
        plan.shared_with.add(partner)
        client.force_login(user)
        resp = post_json(client, self.SHARE_URL, {"plan_id": plan.id, "username": partner.username})
        assert resp.status_code == 400

    def test_erfolgreiches_teilen(self, client):
        user = UserFactory()
        partner = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        resp = post_json(client, self.SHARE_URL, {"plan_id": plan.id, "username": partner.username})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert plan.shared_with.filter(id=partner.id).exists()

    def test_unshare_entfernt_freigabe(self, client):
        user = UserFactory()
        partner = UserFactory()
        plan = PlanFactory(user=user)
        plan.shared_with.add(partner)
        client.force_login(user)
        resp = post_json(client, self.UNSHARE_URL, {"plan_id": plan.id, "user_id": partner.id})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not plan.shared_with.filter(id=partner.id).exists()

    def test_unshare_fehlende_parameter_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.UNSHARE_URL, {"plan_id": 1})
        assert resp.status_code == 400


# ===========================================================================
# api_get_plan_shares & api_get_group_shares
# ===========================================================================


@pytest.mark.django_db
class TestApiGetShares:
    def test_get_plan_shares_gibt_shared_users(self, client):
        user = UserFactory()
        partner = UserFactory()
        plan = PlanFactory(user=user)
        plan.shared_with.add(partner)
        client.force_login(user)
        url = reverse("api_get_plan_shares", args=[plan.id])
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        usernames = [u["username"] for u in data["shared_with"]]
        assert partner.username in usernames

    def test_get_plan_shares_fremder_plan_gibt_404(self, client):
        user_a = UserFactory()
        user_b = UserFactory()
        plan = PlanFactory(user=user_b)
        client.force_login(user_a)
        url = reverse("api_get_plan_shares", args=[plan.id])
        resp = client.get(url)
        assert resp.status_code == 404

    def test_get_group_shares_gruppe_nicht_gefunden(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("api_get_group_shares", args=[str(uuid.uuid4())])
        resp = client.get(url)
        assert resp.status_code == 404

    def test_get_group_shares_gibt_shared_users(self, client):
        user = UserFactory()
        partner = UserFactory()
        gruppe_id = uuid.uuid4()
        plan = PlanFactory(user=user, gruppe_id=gruppe_id)
        plan.shared_with.add(partner)
        client.force_login(user)
        url = reverse("api_get_group_shares", args=[str(gruppe_id)])
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        usernames = [u["username"] for u in data["shared_with"]]
        assert partner.username in usernames


# ===========================================================================
# notifications.py: subscribe_push, unsubscribe_push, get_vapid_public_key
# ===========================================================================


@pytest.mark.django_db
class TestSubscribePush:
    URL = reverse("subscribe_push")

    def test_login_required(self, client):
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 302

    def test_fehlende_subscription_data_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 400
        assert "missing" in resp.json()["error"].lower()

    def test_erfolgreiche_subscription(self, client):
        user = UserFactory()
        client.force_login(user)
        subscription_data = {
            "subscription": {
                "endpoint": "https://push.example.com/sub/abc123",
                "keys": {
                    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtWfelDmSz8wKxE8gJOhwuLuSBXa",
                    "auth": "tBHItJI5svbpez7KI4CCXg",
                },
            }
        }
        resp = post_json(client, self.URL, subscription_data)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_doppelte_subscription_wird_aktualisiert(self, client):
        """Gleicher Endpoint → update_or_create → kein Duplikat."""
        user = UserFactory()
        client.force_login(user)
        payload = {
            "subscription": {
                "endpoint": "https://push.example.com/same-endpoint",
                "keys": {"p256dh": "key1", "auth": "auth1"},
            }
        }
        resp1 = post_json(client, self.URL, payload)
        resp2 = post_json(client, self.URL, payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Zweiter Aufruf → "aktualisiert" statt "aktiviert"
        assert "aktualisiert" in resp2.json()["message"]

    def test_nur_post_erlaubt(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL)
        assert resp.status_code == 405


@pytest.mark.django_db
class TestUnsubscribePush:
    URL = reverse("unsubscribe_push")

    def test_login_required(self, client):
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 302

    def test_fehlender_endpoint_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {})
        assert resp.status_code == 400

    def test_nicht_existierender_endpoint_loescht_0(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, {"endpoint": "https://nicht-vorhanden.example.com"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "0" in resp.json()["message"]

    def test_erfolgreiche_deregistrierung(self, client):
        from core.models import PushSubscription

        user = UserFactory()
        endpoint = "https://push.example.com/del-me"
        PushSubscription.objects.create(
            user=user, endpoint=endpoint, p256dh="key", auth="auth", user_agent=""
        )
        client.force_login(user)
        resp = post_json(client, self.URL, {"endpoint": endpoint})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not PushSubscription.objects.filter(endpoint=endpoint).exists()


@pytest.mark.django_db
class TestGetVapidPublicKey:
    URL = reverse("get_vapid_public_key")

    def test_login_required(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 302

    def test_kein_vapid_key_gibt_503(self, client, settings):
        settings.VAPID_PUBLIC_KEY = ""
        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL)
        assert resp.status_code == 503

    def test_vapid_key_none_gibt_503(self, client, settings):
        settings.VAPID_PUBLIC_KEY = None
        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL)
        assert resp.status_code == 503

    def test_gueltiger_vapid_key_gibt_public_key(self, client, settings):
        """Testet den VAPID-Key-Endpunkt mit einem echten DER-formatierten Key."""
        import base64

        # Minimaler gültiger EC public key (65 Bytes uncompressed point, in DER verpackt)
        # DER-Header (26 Bytes) + uncompressed EC point (65 Bytes) = 91 Bytes
        raw_ec_point = b"\x04" + b"\xab" * 32 + b"\xcd" * 32  # 65 Bytes
        der_header = b"\x30\x59\x30\x13\x06\x07\x2a\x86\x48\xce\x3d\x02\x01\x06\x08\x2a\x86\x48\xce\x3d\x03\x01\x07\x03\x42\x00"
        der_bytes = der_header + raw_ec_point
        pem_body = base64.b64encode(der_bytes).decode()
        pem = f"-----BEGIN PUBLIC KEY-----\n{pem_body}\n-----END PUBLIC KEY-----"
        settings.VAPID_PUBLIC_KEY = pem

        user = UserFactory()
        client.force_login(user)
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "publicKey" in data
        # Kein Padding in URL-safe base64
        assert "=" not in data["publicKey"]


# ===========================================================================
# offline.py: _apply_item_to_satz, _process_update_item, sync_offline_data
# ===========================================================================


class TestApplyItemToSatz:
    """Unit-Test für _apply_item_to_satz – kein DB nötig."""

    def test_felder_werden_korrekt_gesetzt(self):
        from unittest.mock import MagicMock

        from core.views.offline import _apply_item_to_satz

        satz = MagicMock()
        item = {
            "gewicht": "80.5",
            "wiederholungen": 10,
            "rpe": 8,
            "is_warmup": True,
            "superset_gruppe": 2,
            "notiz": "Gut",
        }
        _apply_item_to_satz(satz, item)
        assert satz.gewicht == Decimal("80.5")
        assert satz.wiederholungen == 10
        assert satz.rpe == 8
        assert satz.ist_aufwaermsatz is True
        assert satz.superset_gruppe == 2
        assert satz.notiz == "Gut"

    def test_rpe_none_wird_zu_none(self):
        from unittest.mock import MagicMock

        from core.views.offline import _apply_item_to_satz

        satz = MagicMock()
        item = {"gewicht": "60", "wiederholungen": 5, "rpe": None}
        _apply_item_to_satz(satz, item)
        assert satz.rpe is None

    def test_leere_notiz_wird_zu_none(self):
        from unittest.mock import MagicMock

        from core.views.offline import _apply_item_to_satz

        satz = MagicMock()
        item = {"gewicht": "60", "wiederholungen": 5, "rpe": None, "notiz": ""}
        _apply_item_to_satz(satz, item)
        assert satz.notiz is None


@pytest.mark.django_db
class TestSyncOfflineData:
    URL = reverse("sync_offline_data")

    def _make_item(self, training_id, uebung_id, item_id="local-1"):
        return {
            "id": item_id,
            "training_id": training_id,
            "uebung_id": uebung_id,
            "gewicht": "100.0",
            "wiederholungen": 10,
            "rpe": 8,
            "is_warmup": False,
            "superset_gruppe": 0,
            "notiz": "",
            "is_update": False,
            "action": "/training/1/add_set/",
        }

    def test_login_required(self, client):
        resp = post_json(client, self.URL, [])
        assert resp.status_code == 302

    def test_ungültiges_json_gibt_400(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.post(self.URL, "kein json", content_type="application/json")
        assert resp.status_code == 400

    def test_leere_liste_gibt_success(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = post_json(client, self.URL, [])
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["synced_count"] == 0

    def test_satz_wird_erstellt(self, client):
        from core.models import Satz

        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        client.force_login(user)

        item = self._make_item(training.id, uebung.id)
        vorher = Satz.objects.filter(einheit=training, uebung=uebung).count()
        resp = post_json(client, self.URL, [item])
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        assert Satz.objects.filter(einheit=training, uebung=uebung).count() == vorher + 1

    def test_fremdes_training_schlaegt_fehl(self, client):
        user_a = UserFactory()
        user_b = UserFactory()
        training_b = TrainingseinheitFactory(user=user_b)
        uebung = UebungFactory()
        client.force_login(user_a)

        item = self._make_item(training_b.id, uebung.id)
        resp = post_json(client, self.URL, [item])
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 0
        assert data["results"][0]["success"] is False

    def test_nicht_existierende_uebung_schlaegt_fehl(self, client):
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        client.force_login(user)

        item = self._make_item(training.id, 99999)
        resp = post_json(client, self.URL, [item])
        assert resp.status_code == 200
        assert resp.json()["results"][0]["success"] is False

    def test_update_vorhandener_satz(self, client):
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        satz = SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("80"), wiederholungen=8)
        client.force_login(user)

        item = self._make_item(training.id, uebung.id, "local-upd")
        item["is_update"] = True
        item["action"] = f"/set/{satz.id}/update/"
        item["gewicht"] = "100.0"
        item["wiederholungen"] = 12

        resp = post_json(client, self.URL, [item])
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert result["success"] is True
        assert result["updated"] is True
        satz.refresh_from_db()
        assert satz.gewicht == Decimal("100.0")
        assert satz.wiederholungen == 12

    def test_mehrere_items_gemischt(self, client):
        """Ein valides Item + ein Item mit falscher Übung → synced_count=1."""
        user = UserFactory()
        training = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        client.force_login(user)

        items = [
            self._make_item(training.id, uebung.id, "ok"),
            self._make_item(training.id, 99999, "fail"),
        ]
        resp = post_json(client, self.URL, items)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        assert len(data["results"]) == 2
