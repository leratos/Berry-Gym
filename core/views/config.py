"""
Configuration and static file serving views.

This module handles site configuration pages (impressum, datenschutz),
metrics help, PWA-related endpoints (service worker, manifest, favicon),
and the get_last_set API endpoint for training set information.
"""

import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control

from ..models import Satz

logger = logging.getLogger(__name__)


def impressum(request):
    """Impressum-Seite"""
    return render(request, "core/impressum.html")


def datenschutz(request):
    """Datenschutzerklärung-Seite"""
    return render(request, "core/datenschutz.html")


@login_required
def metriken_help(request):
    """
    Hilfsseite mit Erklärungen zu allen Metriken und Kennzahlen
    """
    return render(request, "core/metriken_help.html")


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """Serve the service worker from root path."""
    sw_path = os.path.join(settings.BASE_DIR, "core", "static", "core", "service-worker.js")

    try:
        with open(sw_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HttpResponse(content, content_type="application/javascript")
    except FileNotFoundError:
        return HttpResponse("Service Worker not found", status=404)


def favicon(request):
    """Serve favicon.ico from static files."""
    favicon_path = os.path.join(
        settings.BASE_DIR, "core", "static", "core", "images", "icon-192x192.png"
    )

    try:
        return FileResponse(open(favicon_path, "rb"), content_type="image/png")
    except FileNotFoundError:
        return HttpResponse(status=204)  # No Content


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def manifest(request):
    """Serve the manifest from root path."""
    manifest_path = os.path.join(settings.BASE_DIR, "core", "static", "core", "manifest.json")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HttpResponse(content, content_type="application/json")
    except FileNotFoundError:
        return HttpResponse("Manifest not found", status=404)


@login_required
def get_last_set(request, uebung_id):
    """API: Liefert die Werte des letzten 'echten' Satzes einer Übung zurück."""
    # Optionales Wiederholungsziel aus Query-Parameter (z.B. ?ziel=8-10)
    ziel_wdh_str = request.GET.get("ziel", "8-12")
    try:
        if "-" in ziel_wdh_str:
            ziel_wdh_max = int(ziel_wdh_str.split("-")[1])
            ziel_wdh_min = int(ziel_wdh_str.split("-")[0])
        else:
            ziel_wdh_max = int(ziel_wdh_str)
            ziel_wdh_min = int(ziel_wdh_str)
    except ValueError:
        ziel_wdh_max = 12
        ziel_wdh_min = 8

    # Wir suchen den allerletzten Satz dieser Übung (trainingübergreifend)
    # Wichtig: Wir ignorieren Aufwärmsätze (ist_aufwaermsatz=False)
    letzter_satz = (
        Satz.objects.filter(einheit__user=request.user, uebung_id=uebung_id, ist_aufwaermsatz=False)
        .order_by("-einheit__datum", "-satz_nr")
        .first()
    )

    if letzter_satz:
        # Progressive Overload Logik - berücksichtigt Planziel
        empfohlenes_gewicht = float(letzter_satz.gewicht)
        empfohlene_wdh = letzter_satz.wiederholungen

        if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
            # RPE zu leicht → mehr Gewicht
            empfohlenes_gewicht += 2.5
            progression_hint = f"RPE {letzter_satz.rpe} war leicht → versuch +2.5kg!"
        elif letzter_satz.wiederholungen >= ziel_wdh_max:
            # Obere Zielgrenze erreicht → mehr Gewicht, Wdh zurück auf Minimum
            empfohlenes_gewicht += 2.5
            empfohlene_wdh = ziel_wdh_min
            progression_hint = f"{ziel_wdh_max}+ Wdh geschafft → Zeit für +2.5kg!"
        elif letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
            # RPE hoch aber noch im Wdh-Bereich → Wdh erhöhen (max bis Ziel)
            empfohlene_wdh = min(empfohlene_wdh + 1, ziel_wdh_max)
            progression_hint = f"RPE {letzter_satz.rpe} → versuch mehr Wiederholungen!"
        else:
            progression_hint = "Halte das Niveau oder steigere dich leicht"

        return JsonResponse(
            {
                "success": True,
                "gewicht": empfohlenes_gewicht,
                "wiederholungen": empfohlene_wdh,
                "rpe": letzter_satz.rpe,
                "progression_hint": progression_hint,
                "letztes_gewicht": float(letzter_satz.gewicht),
                "letzte_wdh": letzter_satz.wiederholungen,
            }
        )
    else:
        return JsonResponse({"success": False})
