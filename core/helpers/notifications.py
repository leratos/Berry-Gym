"""
Push notification utility functions for HomeGym application.
"""

import json
import logging
import os

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_push_notification(user, title, body, url="/", icon=None):
    """Sendet eine Push-Notification an alle Geräte eines Users"""
    from pywebpush import WebPushException, webpush

    from core.models import PushSubscription

    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured - push notifications disabled")
        return

    subscriptions = PushSubscription.objects.filter(user=user)

    if not subscriptions.exists():
        return

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
            "icon": icon or "/static/core/images/icon-192x192.png",
        }
    )

    # VAPID Private Key: Verwende Dateipfad statt String (robuster für pywebpush)
    vapid_private_key_path = os.path.join(settings.BASE_DIR, settings.VAPID_PRIVATE_KEY_FILE)

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=vapid_private_key_path,  # Dateipfad statt String!
                vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
            )
            subscription.last_used = timezone.now()
            subscription.save()  # Update last_used

        except WebPushException as e:
            logger.error(f"WebPush error for {subscription.id}: {e}")
            if e.response and e.response.status_code in [404, 410]:
                # Subscription expired or invalid
                subscription.delete()
        except Exception as e:
            logger.error(f"Push notification error: {e}", exc_info=True)
