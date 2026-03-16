"""
Saleria API – Read-only JSON-Endpoints für den Elder-Berry AI-Assistenten.

Authentifizierung via Bearer-Token (kein Session/Cookie).
Token wird als SALERIA_API_TOKEN in settings/.env konfiguriert.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import KoerperWerte, Satz, Trainingseinheit

logger = logging.getLogger("core")


# ---------------------------------------------------------------------------
# Token-Auth Decorator
# ---------------------------------------------------------------------------


def saleria_token_required(view_func):
    """Prüft Authorization: Bearer <token> gegen settings.SALERIA_API_TOKEN."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        token = settings.SALERIA_API_TOKEN
        if not token:
            logger.warning("Saleria API: SALERIA_API_TOKEN nicht konfiguriert")
            return JsonResponse({"error": "API not configured"}, status=503)

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse({"error": "Authentication required"}, status=401)

        provided_token = auth_header[7:]  # Strip "Bearer "
        if provided_token != token:
            return JsonResponse({"error": "Invalid token"}, status=403)

        # User aus Settings laden
        try:
            request.saleria_user = User.objects.get(pk=settings.SALERIA_API_USER_ID)
        except User.DoesNotExist:
            return JsonResponse({"error": "Configured user not found"}, status=500)

        return view_func(request, *args, **kwargs)

    return _wrapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_to_float(val):
    """Konvertiert Decimal → float für JSON-Serialisierung."""
    if isinstance(val, Decimal):
        return float(val)
    return val


# ---------------------------------------------------------------------------
# GET /api/saleria/summary/
# ---------------------------------------------------------------------------


@require_GET
@saleria_token_required
def saleria_summary(request):
    """Zusammenfassung: letztes Training, Trainings diese Woche, aktuelles Gewicht."""
    user = request.saleria_user
    now = timezone.now()

    # Letztes abgeschlossenes Training
    letztes = (
        Trainingseinheit.objects.filter(user=user, abgeschlossen=True).order_by("-datum").first()
    )

    letztes_training = None
    if letztes:
        uebungen_count = (
            Satz.objects.filter(einheit=letztes, ist_aufwaermsatz=False)
            .values("uebung")
            .distinct()
            .count()
        )
        letztes_training = {
            "datum": letztes.datum.isoformat(),
            "dauer_minuten": letztes.dauer_minuten,
            "uebungen_anzahl": uebungen_count,
        }

    # Trainings diese Woche (Montag 00:00 bis jetzt)
    montag = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    trainings_diese_woche = Trainingseinheit.objects.filter(
        user=user, abgeschlossen=True, datum__gte=montag
    ).count()

    # Aktuelles Gewicht
    letzter_wert = KoerperWerte.objects.filter(user=user).order_by("-datum").first()
    aktuelles_gewicht = None
    if letzter_wert:
        aktuelles_gewicht = {
            "gewicht_kg": _decimal_to_float(letzter_wert.gewicht),
            "datum": letzter_wert.datum.isoformat(),
        }

    return JsonResponse(
        {
            "letztes_training": letztes_training,
            "trainings_diese_woche": trainings_diese_woche,
            "aktuelles_gewicht": aktuelles_gewicht,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/saleria/last-training/
# ---------------------------------------------------------------------------


@require_GET
@saleria_token_required
def saleria_last_training(request):
    """Letztes Training mit allen Sätzen (Übung, Gewicht, Wdh, RPE)."""
    user = request.saleria_user

    training = (
        Trainingseinheit.objects.filter(user=user, abgeschlossen=True).order_by("-datum").first()
    )

    if not training:
        return JsonResponse({"training": None})

    saetze = (
        Satz.objects.filter(einheit=training)
        .select_related("uebung")
        .order_by("uebung__bezeichnung", "satz_nr")
    )

    saetze_data = [
        {
            "uebung": s.uebung.bezeichnung,
            "gewicht_kg": _decimal_to_float(s.gewicht),
            "wiederholungen": s.wiederholungen,
            "rpe": _decimal_to_float(s.rpe),
            "ist_aufwaermsatz": s.ist_aufwaermsatz,
            "satz_nr": s.satz_nr,
        }
        for s in saetze
    ]

    return JsonResponse(
        {
            "training": {
                "datum": training.datum.isoformat(),
                "dauer_minuten": training.dauer_minuten,
                "kommentar": training.kommentar or "",
                "ist_deload": training.ist_deload,
                "saetze": saetze_data,
            }
        }
    )


# ---------------------------------------------------------------------------
# GET /api/saleria/week/
# ---------------------------------------------------------------------------


@require_GET
@saleria_token_required
def saleria_week(request):
    """Trainings der letzten 7 Tage (Datum, Dauer, Übungen-Anzahl)."""
    user = request.saleria_user
    seit = timezone.now() - timedelta(days=7)

    trainings = (
        Trainingseinheit.objects.filter(user=user, abgeschlossen=True, datum__gte=seit)
        .annotate(uebungen_anzahl=Count("saetze__uebung", distinct=True))
        .order_by("-datum")
    )

    data = [
        {
            "datum": t.datum.isoformat(),
            "dauer_minuten": t.dauer_minuten,
            "uebungen_anzahl": t.uebungen_anzahl,
        }
        for t in trainings
    ]

    return JsonResponse({"trainings": data})


# ---------------------------------------------------------------------------
# GET /api/saleria/prs/
# ---------------------------------------------------------------------------


@require_GET
@saleria_token_required
def saleria_prs(request):
    """Personal Records – Top estimated 1RM pro Übung, letzte 30 Tage.

    Epley-Formel: 1RM = Gewicht × (1 + Wiederholungen / 30)
    """
    user = request.saleria_user
    seit = timezone.now() - timedelta(days=30)

    saetze = Satz.objects.filter(
        einheit__user=user,
        einheit__abgeschlossen=True,
        einheit__datum__gte=seit,
        ist_aufwaermsatz=False,
        gewicht__gt=0,
    ).select_related("uebung", "einheit")

    # Beste 1RM pro Übung berechnen
    best_per_exercise = {}
    for s in saetze:
        wdh = s.wiederholungen or 1
        estimated_1rm = float(s.gewicht) * (1 + wdh / 30.0)
        name = s.uebung.bezeichnung

        if (
            name not in best_per_exercise
            or estimated_1rm > best_per_exercise[name]["estimated_1rm"]
        ):
            best_per_exercise[name] = {
                "uebung": name,
                "estimated_1rm": round(estimated_1rm, 1),
                "gewicht_kg": _decimal_to_float(s.gewicht),
                "wiederholungen": s.wiederholungen,
                "datum": s.einheit.datum.isoformat(),
            }

    # Nach 1RM absteigend sortieren
    prs = sorted(best_per_exercise.values(), key=lambda x: x["estimated_1rm"], reverse=True)

    return JsonResponse({"prs": prs})
