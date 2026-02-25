"""Onboarding Views - Guided Tour für neue User"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)


@require_POST
@login_required
def mark_onboarding_complete(request):
    """
    Markiert das Onboarding als abgeschlossen für den aktuellen User.

    AJAX-Endpoint der vom Onboarding-Script aufgerufen wird.
    """
    try:
        profile = request.user.profile
        profile.has_seen_onboarding = True
        profile.save(update_fields=["has_seen_onboarding"])

        return JsonResponse({"success": True, "message": "Onboarding abgeschlossen"})
    except Exception:
        logger.exception("Error while marking onboarding as complete")
        return JsonResponse(
            {"success": False, "error": "Ein interner Fehler ist aufgetreten."},
            status=500,
        )


@login_required
def restart_onboarding(request):
    """
    Ermöglicht dem User das Onboarding erneut zu starten.

    Setzt das has_seen_onboarding Flag zurück.
    """
    try:
        profile = request.user.profile
        profile.has_seen_onboarding = False
        profile.save(update_fields=["has_seen_onboarding"])

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "message": "Onboarding zurückgesetzt"})
        else:
            # Redirect zum Dashboard wenn nicht AJAX
            from django.shortcuts import redirect

            return redirect("dashboard")

    except Exception:
        logger.exception("Error while restarting onboarding")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Ein interner Fehler ist aufgetreten."},
                status=500,
            )
        else:
            from django.shortcuts import redirect

            return redirect("dashboard")
