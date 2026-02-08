"""
Push notification management views.

This module handles push notification subscriptions and VAPID key management
for web push notifications.
"""

import json
import base64
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings

from ..models import PushSubscription
from ..helpers.notifications import send_push_notification

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(['POST'])
def subscribe_push(request):
    """Registriert eine neue Push-Subscription für den User"""
    try:
        data = json.loads(request.body)
        subscription = data.get('subscription')

        if not subscription:
            return JsonResponse({'error': 'Subscription data missing'}, status=400)

        # User Agent für Geräteerkennung
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        # Subscription speichern oder aktualisieren
        obj, created = PushSubscription.objects.update_or_create(
            endpoint=subscription['endpoint'],
            defaults={
                'user': request.user,
                'p256dh': subscription['keys']['p256dh'],
                'auth': subscription['keys']['auth'],
                'user_agent': user_agent,
            }
        )

        return JsonResponse({
            'success': True,
            'message': 'Push-Benachrichtigungen aktiviert' if created else 'Push-Benachrichtigungen aktualisiert'
        })

    except Exception as e:
        logger.error(f'Push subscription error: {e}', exc_info=True)
        return JsonResponse(
            {'error': 'An internal error has occurred while subscribing to push notifications.'},
            status=500
        )


@login_required
@require_http_methods(['POST'])
def unsubscribe_push(request):
    """Deaktiviert Push-Notifications für ein Gerät"""
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')

        if not endpoint:
            return JsonResponse({'error': 'Endpoint missing'}, status=400)

        deleted_count, _ = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint
        ).delete()

        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} Subscription(s) gelöscht'
        })

    except Exception as e:
        logger.error(f'Push unsubscribe error: {e}', exc_info=True)
        return JsonResponse({'error': 'An internal error has occurred while unsubscribing from push notifications.'}, status=500)


@login_required
def get_vapid_public_key(request):
    """Gibt den VAPID Public Key für die Frontend-Subscription zurück"""
    if not settings.VAPID_PUBLIC_KEY:
        return JsonResponse({'error': 'VAPID keys not configured'}, status=503)

    # Extrahiere nur den Key-Teil aus der PEM-Datei
    public_key_pem = settings.VAPID_PUBLIC_KEY
    # Entferne PEM Header/Footer und Zeilenumbrüche
    public_key_pem = public_key_pem.replace('-----BEGIN PUBLIC KEY-----', '')
    public_key_pem = public_key_pem.replace('-----END PUBLIC KEY-----', '')
    public_key_pem = public_key_pem.replace('\n', '').replace('\r', '').strip()

    # Dekodiere Base64 -> DER format (ASN.1 encoded)
    der_bytes = base64.b64decode(public_key_pem)

    # Extrahiere die rohen 65 Bytes des EC public key points
    # DER Format: 91 bytes total, die letzten 65 bytes sind der uncompressed point (0x04 + X + Y)
    # Der uncompressed point beginnt bei Byte 26 (0x1a) mit dem 0x04 prefix
    raw_public_key = der_bytes[-65:]

    # Zurück zu base64 für JavaScript (URL-safe)
    public_key_base64 = base64.urlsafe_b64encode(raw_public_key).decode('utf-8')
    # Entferne padding (wird von urlBase64ToUint8Array wieder hinzugefügt)
    public_key_base64 = public_key_base64.rstrip('=')

    return JsonResponse({
        'publicKey': public_key_base64
    })
