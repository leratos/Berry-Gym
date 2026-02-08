"""
Offline data synchronization module for HomeGym.

This module handles synchronization of offline-stored training data to the server,
including set creation and updates with proper validation and access control.
"""

import json
import re
import logging
from decimal import Decimal

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Max

from ..models import Trainingseinheit, Uebung, Satz

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def sync_offline_data(request):
    """Synced offline gespeicherte Sätze zum Server."""
    try:
        data = json.loads(request.body)
        results = []

        for item in data:
            try:
                # Validiere Training-Zugriff
                training = Trainingseinheit.objects.get(
                    id=item['training_id'],
                    user=request.user
                )

                # Hole Übung
                uebung = Uebung.objects.get(id=item['uebung_id'])

                # Prüfe ob es ein Update ist (URL enthält /update/)
                is_update = item.get('is_update', False)
                action_url = item.get('action', '')

                if is_update or '/update/' in action_url:
                    # Update: Versuche Satz zu finden und aktualisieren
                    # Extrahiere Satz-ID aus URL (z.B. /set/123/update/)
                    # Safe regex with bounded quantifier
                    match = re.search(r'/set/(\d{1,10})/update/', action_url)

                    if match:
                        satz_id = int(match.group(1))
                        try:
                            satz = Satz.objects.get(id=satz_id, einheit__user=request.user)

                            # Update existierenden Satz
                            satz.gewicht = Decimal(str(item['gewicht']))
                            satz.wiederholungen = int(item['wiederholungen'])
                            satz.rpe = int(item['rpe']) if item.get('rpe') else None
                            satz.ist_aufwaermsatz = item.get('is_warmup', False)
                            satz.superset_gruppe = int(item.get('superset_gruppe', 0))
                            satz.notiz = item.get('notiz', '') or None
                            satz.save()

                            results.append({
                                'id': item['id'],
                                'success': True,
                                'satz_id': satz.id,
                                'updated': True
                            })
                            continue

                        except Satz.DoesNotExist:
                            # Satz existiert nicht mehr, erstelle neuen
                            pass

                # Erstelle neuen Satz (entweder Add oder Update fehlgeschlagen)
                max_satz = training.saetze.filter(uebung=uebung).aggregate(Max('satz_nr'))['satz_nr__max']
                neue_nr = (max_satz or 0) + 1

                neuer_satz = Satz.objects.create(
                    einheit=training,
                    uebung=uebung,
                    satz_nr=neue_nr,
                    gewicht=Decimal(str(item['gewicht'])),
                    wiederholungen=int(item['wiederholungen']),
                    rpe=int(item['rpe']) if item.get('rpe') else None,
                    ist_aufwaermsatz=item.get('is_warmup', False),
                    superset_gruppe=int(item.get('superset_gruppe', 0)),
                    notiz=item.get('notiz', '') or None
                )

                results.append({
                    'id': item['id'],
                    'success': True,
                    'satz_id': neuer_satz.id,
                    'updated': False
                })

            except Trainingseinheit.DoesNotExist:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Training nicht gefunden oder keine Berechtigung'
                })
            except Uebung.DoesNotExist:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Übung nicht gefunden'
                })
            except Exception as e:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Fehler beim Verarbeiten dieses Eintrags'
                })

        return JsonResponse({
            'success': True,
            'results': results,
            'synced_count': sum(1 for r in results if r['success'])
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        logger.error(f'Offline data sync error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Offline-Daten konnten nicht synchronisiert werden.'}, status=500)
