"""
Offline data synchronization module for HomeGym.

This module handles synchronization of offline-stored training data to the server,
including set creation and updates with proper validation and access control.
"""

import json
import logging
import re
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import Satz, Trainingseinheit, Uebung

logger = logging.getLogger(__name__)


def _apply_item_to_satz(satz: Satz, item: dict) -> None:
    """Setzt Felder eines Satz-Objekts aus einem Sync-Item-Dict.

    Wird sowohl beim Update als auch beim Neuanlegen verwendet.
    Der Caller ist verantwortlich für satz.save().
    """
    satz.gewicht = Decimal(str(item["gewicht"]))
    satz.wiederholungen = int(item["wiederholungen"])
    satz.rpe = int(item["rpe"]) if item.get("rpe") else None
    satz.ist_aufwaermsatz = item.get("is_warmup", False)
    satz.superset_gruppe = int(item.get("superset_gruppe", 0))
    satz.notiz = item.get("notiz", "") or None


def _process_single_item(user, item: dict) -> dict:
    """Verarbeitet ein einzelnes Sync-Item: Update oder Neu-Anlage.

    Returns:
        Result-Dict mit id, success, satz_id / error.
    """
    try:
        training = Trainingseinheit.objects.get(id=item["training_id"], user=user)
        uebung = Uebung.objects.get(id=item["uebung_id"])
    except Trainingseinheit.DoesNotExist:
        return {
            "id": item["id"],
            "success": False,
            "error": "Training nicht gefunden oder keine Berechtigung",
        }
    except Uebung.DoesNotExist:
        return {"id": item["id"], "success": False, "error": "Übung nicht gefunden"}

    is_update = item.get("is_update", False)
    action_url = item.get("action", "")

    if is_update or "/update/" in action_url:
        result = _process_update_item(user, item)
        if result is not None:
            return result

    # Neuen Satz erstellen (Add oder Update-Fallthrough)
    max_satz = training.saetze.filter(uebung=uebung).aggregate(Max("satz_nr"))["satz_nr__max"]
    neuer_satz = Satz(einheit=training, uebung=uebung, satz_nr=(max_satz or 0) + 1)
    _apply_item_to_satz(neuer_satz, item)
    neuer_satz.save()
    return {"id": item["id"], "success": True, "satz_id": neuer_satz.id, "updated": False}


def _process_update_item(user, item: dict) -> dict | None:
    """Versucht einen existierenden Satz per URL-ID zu aktualisieren.

    Returns:
        Result-Dict wenn Update erfolgreich, None wenn Fallthrough zu Create.
    """
    action_url = item.get("action", "")
    match = re.search(r"/set/(\d{1,10})/update/", action_url)
    if not match:
        return None

    satz_id = int(match.group(1))
    try:
        satz = Satz.objects.get(id=satz_id, einheit__user=user)
    except Satz.DoesNotExist:
        return None  # Satz weg → neuen erstellen

    _apply_item_to_satz(satz, item)
    satz.save()
    return {"id": item["id"], "success": True, "satz_id": satz.id, "updated": True}


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def sync_offline_data(request: HttpRequest) -> JsonResponse:
    """Synced offline gespeicherte Sätze zum Server."""
    try:
        data = json.loads(request.body)
        results = []

        for item in data:
            try:
                results.append(_process_single_item(request.user, item))
            except Exception:
                results.append(
                    {
                        "id": item["id"],
                        "success": False,
                        "error": "Fehler beim Verarbeiten dieses Eintrags",
                    }
                )

        return JsonResponse(
            {
                "success": True,
                "results": results,
                "synced_count": sum(1 for r in results if r["success"]),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Ungültiges JSON"}, status=400)
    except Exception as e:
        logger.error(f"Offline data sync error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Offline-Daten konnten nicht synchronisiert werden."},
            status=500,
        )
