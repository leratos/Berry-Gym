"""
Push notification utility functions for HomeGym application.
"""

import json
import logging
import os

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _build_push_payload(title: str, body: str, url: str = "/", icon: str | None = None) -> str:
    """Erstellt den JSON-Payload für eine Push-Notification.

    Reine Funktion ohne I/O – direkt testbar.
    """
    return json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
            "icon": icon or "/static/core/images/icon-192x192.png",
        }
    )


def _send_single_push(subscription, payload: str, vapid_key_path: str) -> bool:
    """Sendet eine Push-Notification an eine einzelne Subscription.

    Returns:
        True  – Versand erfolgreich (oder recoverable Fehler, Subscription noch gültig)
        False – Subscription abgelaufen/ungültig (404/410), Caller soll sie löschen

    Der Caller ist verantwortlich für last_used-Update und Löschung.
    Logik bewusst aus dem Exception-Handler herausgezogen damit
    _send_single_push isoliert testbar ist.
    """
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=vapid_key_path,
            vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
        )
        return True
    except WebPushException as e:
        if e.response and e.response.status_code in [404, 410]:
            logger.info(
                f"Subscription {subscription.id} abgelaufen (HTTP {e.response.status_code})"
            )
            return False  # Signal: Subscription ist tot → Caller löscht
        logger.error(f"WebPush error for {subscription.id}: {e}")
        return True  # Anderer Fehler – Subscription noch gültig
    except Exception as e:
        logger.error(f"Push notification error: {e}", exc_info=True)
        return True  # Subscription nicht löschen bei unbekannten Fehlern


def send_push_notification(user, title: str, body: str, url: str = "/", icon: str | None = None):
    """Sendet eine Push-Notification an alle Geräte eines Users.

    Orchestriert _build_push_payload und _send_single_push.
    Enthält selbst keine eigene Logik außer Vorbedingungsprüfungen.
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured - push notifications disabled")
        return

    from core.models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        return

    payload = _build_push_payload(title, body, url, icon)
    vapid_key_path = os.path.join(settings.BASE_DIR, settings.VAPID_PRIVATE_KEY_FILE)

    for subscription in subscriptions:
        still_valid = _send_single_push(subscription, payload, vapid_key_path)
        if still_valid:
            subscription.last_used = timezone.now()
            subscription.save()
        else:
            subscription.delete()
