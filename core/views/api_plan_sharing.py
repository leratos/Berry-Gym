"""
API views for plan and group sharing functionality.

This module handles all API endpoints related to plan and group management,
including sharing, grouping, deletion, and retrieval of sharing permissions.
"""

import json as json_module
import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from ..models import Plan

logger = logging.getLogger(__name__)


# ============================================================
# PLAN GRUPPIERUNG API
# ============================================================


@login_required
@require_http_methods(["POST"])
def api_ungroup_plans(request):
    """Löst die Gruppierung von Plänen auf (entfernt gruppe_id)."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")

        if not gruppe_id:
            return JsonResponse({"success": False, "error": "Keine Gruppe angegeben"}, status=400)

        # Finde alle Pläne mit dieser gruppe_id und entferne die Gruppierung
        updated = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).update(
            gruppe_id=None, gruppe_name=""
        )

        return JsonResponse(
            {"success": True, "message": f"{updated} Pläne wurden aus der Gruppe entfernt"}
        )

    except Exception as e:
        logger.error(f"Ungroup plans error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Pläne konnten nicht aus der Gruppe entfernt werden."},
            status=500,
        )


@login_required
@require_http_methods(["POST"])
def api_group_plans(request):
    """Gruppiert mehrere Pläne unter einer neuen Gruppe."""
    try:
        data = json_module.loads(request.body)
        plan_ids = data.get("plan_ids", [])
        gruppe_name = data.get("gruppe_name", "Neue Gruppe")

        if len(plan_ids) < 2:
            return JsonResponse({"success": False, "error": "Mindestens 2 Pläne nötig"}, status=400)

        # Erstelle neue Gruppen-ID
        neue_gruppe_id = uuid.uuid4()

        # Aktualisiere alle angegebenen Pläne mit Reihenfolge
        plans = Plan.objects.filter(user=request.user, id__in=plan_ids).order_by(
            "name"
        )  # Alphabetisch sortieren für initiale Reihenfolge

        for i, plan in enumerate(plans):
            plan.gruppe_id = neue_gruppe_id
            plan.gruppe_name = gruppe_name
            plan.gruppe_reihenfolge = i
            plan.save(update_fields=["gruppe_id", "gruppe_name", "gruppe_reihenfolge"])

        return JsonResponse(
            {
                "success": True,
                "message": f"{plans.count()} Pläne wurden gruppiert",
                "gruppe_id": str(neue_gruppe_id),
            }
        )

    except Exception as e:
        logger.error(f"Group plans error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Pläne konnten nicht gruppiert werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_delete_plan(request):
    """Löscht einen einzelnen Plan."""
    try:
        data = json_module.loads(request.body)
        plan_id = data.get("plan_id")

        if not plan_id:
            return JsonResponse({"success": False, "error": "Keine Plan-ID angegeben"}, status=400)

        # Plan finden und prüfen ob er dem User gehört
        plan = Plan.objects.filter(id=plan_id, user=request.user).first()

        if not plan:
            return JsonResponse(
                {"success": False, "error": "Plan nicht gefunden oder keine Berechtigung"},
                status=404,
            )

        plan_name = plan.name
        plan.delete()

        return JsonResponse({"success": True, "message": f'Plan "{plan_name}" wurde gelöscht'})

    except Exception as e:
        logger.error(f"Delete plan error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Plan konnte nicht gelöscht werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_delete_group(request):
    """Löscht alle Pläne einer Gruppe."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")

        if not gruppe_id:
            return JsonResponse({"success": False, "error": "Keine Gruppe angegeben"}, status=400)

        # Alle Pläne dieser Gruppe finden (nur die des Users)
        plans_to_delete = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)

        count = plans_to_delete.count()

        if count == 0:
            return JsonResponse(
                {"success": False, "error": "Keine Pläne in dieser Gruppe gefunden"}, status=404
            )

        plans_to_delete.delete()

        return JsonResponse({"success": True, "message": f"{count} Pläne wurden gelöscht"})

    except Exception as e:
        logger.error(f"Delete group error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Gruppe konnte nicht gelöscht werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_rename_group(request):
    """Benennt eine Plan-Gruppe um."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")
        new_name = data.get("new_name", "").strip()

        if not gruppe_id:
            return JsonResponse({"success": False, "error": "Keine Gruppe angegeben"}, status=400)

        if not new_name:
            return JsonResponse({"success": False, "error": "Kein Name angegeben"}, status=400)

        # Alle Pläne dieser Gruppe umbenennen
        updated = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).update(
            gruppe_name=new_name
        )

        if updated == 0:
            return JsonResponse(
                {"success": False, "error": "Keine Pläne in dieser Gruppe gefunden"}, status=404
            )

        return JsonResponse({"success": True, "message": f'Gruppe wurde zu "{new_name}" umbenannt'})

    except Exception as e:
        logger.error(f"Rename group error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Gruppe konnte nicht umbenannt werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_reorder_group(request):
    """Ändert die Reihenfolge der Pläne innerhalb einer Gruppe."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")
        plan_id = data.get("plan_id")
        direction = data.get("direction")  # 'up' oder 'down'

        if not gruppe_id or not plan_id or not direction:
            return JsonResponse({"success": False, "error": "Fehlende Parameter"}, status=400)

        # Alle Pläne dieser Gruppe holen, sortiert nach Reihenfolge
        plans = list(
            Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).order_by(
                "gruppe_reihenfolge", "name"
            )
        )

        if not plans:
            return JsonResponse(
                {"success": False, "error": "Keine Pläne in dieser Gruppe"}, status=404
            )

        # Index des zu verschiebenden Plans finden
        current_index = None
        for i, p in enumerate(plans):
            if p.id == plan_id:
                current_index = i
                break

        if current_index is None:
            return JsonResponse({"success": False, "error": "Plan nicht gefunden"}, status=404)

        # Neuen Index berechnen
        if direction == "up" and current_index > 0:
            new_index = current_index - 1
        elif direction == "down" and current_index < len(plans) - 1:
            new_index = current_index + 1
        else:
            return JsonResponse({"success": True, "message": "Keine Änderung nötig"})

        # Pläne tauschen
        plans[current_index], plans[new_index] = plans[new_index], plans[current_index]

        # Neue Reihenfolge speichern
        for i, p in enumerate(plans):
            p.gruppe_reihenfolge = i
            p.save(update_fields=["gruppe_reihenfolge"])

        return JsonResponse({"success": True, "message": "Reihenfolge wurde aktualisiert"})

    except Exception as e:
        logger.error(f"Reorder group error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Reihenfolge konnte nicht aktualisiert werden."}, status=500
        )


# ========== TRAININGSPARTNER-SHARING API ==========


@login_required
@require_http_methods(["GET"])
def api_search_users(request):
    """Sucht User per Username für Trainingspartner-Einladung."""
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"users": []})

    # Suche nach Username (nicht eigenen User)
    users = (
        User.objects.filter(username__icontains=query)
        .exclude(id=request.user.id)
        .values("id", "username")[:10]
    )

    return JsonResponse({"users": list(users)})


@login_required
@require_http_methods(["POST"])
def api_share_plan_with_user(request):
    """Teilt einen Plan mit einem Trainingspartner."""
    try:
        data = json_module.loads(request.body)
        plan_id = data.get("plan_id")
        username = data.get("username", "").strip()

        if not plan_id or not username:
            return JsonResponse(
                {"success": False, "error": "Plan-ID und Username erforderlich"}, status=400
            )

        # Plan muss dem User gehören
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)

        # Ziel-User finden
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": f'User "{username}" nicht gefunden'}, status=404
            )

        if target_user == request.user:
            return JsonResponse(
                {"success": False, "error": "Du kannst nicht mit dir selbst teilen"}, status=400
            )

        # Bereits geteilt?
        if plan.shared_with.filter(id=target_user.id).exists():
            return JsonResponse(
                {"success": False, "error": f'Bereits mit "{username}" geteilt'}, status=400
            )

        # Teilen
        plan.shared_with.add(target_user)

        return JsonResponse(
            {
                "success": True,
                "message": f'Plan wurde mit "{username}" geteilt',
                "user": {"id": target_user.id, "username": target_user.username},
            }
        )

    except Exception as e:
        logger.error(f"Share plan with user error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Plan konnte nicht geteilt werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_unshare_plan_with_user(request):
    """Entfernt Trainingspartner-Freigabe."""
    try:
        data = json_module.loads(request.body)
        plan_id = data.get("plan_id")
        user_id = data.get("user_id")

        if not plan_id or not user_id:
            return JsonResponse(
                {"success": False, "error": "Plan-ID und User-ID erforderlich"}, status=400
            )

        # Plan muss dem User gehören
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)

        # Ziel-User finden
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User nicht gefunden"}, status=404)

        # Freigabe entfernen
        plan.shared_with.remove(target_user)

        return JsonResponse(
            {"success": True, "message": f'Freigabe für "{target_user.username}" wurde entfernt'}
        )

    except Exception as e:
        logger.error(f"Unshare plan with user error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Freigabe konnte nicht entfernt werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_share_group_with_user(request):
    """Teilt eine komplette Plan-Gruppe mit einem Trainingspartner."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")
        username = data.get("username", "").strip()

        if not gruppe_id or not username:
            return JsonResponse(
                {"success": False, "error": "Gruppe-ID und Username erforderlich"}, status=400
            )

        # Alle Pläne der Gruppe (müssen dem User gehören)
        plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)

        if not plans.exists():
            return JsonResponse(
                {"success": False, "error": "Keine Pläne in dieser Gruppe"}, status=404
            )

        # Ziel-User finden
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": f'User "{username}" nicht gefunden'}, status=404
            )

        if target_user == request.user:
            return JsonResponse(
                {"success": False, "error": "Du kannst nicht mit dir selbst teilen"}, status=400
            )

        # Alle Pläne der Gruppe teilen
        for plan in plans:
            plan.shared_with.add(target_user)

        return JsonResponse(
            {
                "success": True,
                "message": f'Gruppe wurde mit "{username}" geteilt ({plans.count()} Pläne)',
                "user": {"id": target_user.id, "username": target_user.username},
            }
        )

    except Exception as e:
        logger.error(f"Share group with user error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Gruppe konnte nicht geteilt werden."}, status=500
        )


@login_required
@require_http_methods(["POST"])
def api_unshare_group_with_user(request):
    """Entfernt Trainingspartner-Freigabe für eine komplette Gruppe."""
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get("gruppe_id")
        user_id = data.get("user_id")

        if not gruppe_id or not user_id:
            return JsonResponse(
                {"success": False, "error": "Gruppe-ID und User-ID erforderlich"}, status=400
            )

        # Alle Pläne der Gruppe
        plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)

        if not plans.exists():
            return JsonResponse(
                {"success": False, "error": "Keine Pläne in dieser Gruppe"}, status=404
            )

        # Ziel-User finden
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User nicht gefunden"}, status=404)

        # Freigabe für alle Pläne entfernen
        for plan in plans:
            plan.shared_with.remove(target_user)

        return JsonResponse(
            {"success": True, "message": f'Freigabe für "{target_user.username}" wurde entfernt'}
        )

    except Exception as e:
        logger.error(f"Unshare group with user error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Freigabe konnte nicht entfernt werden."}, status=500
        )


@login_required
def api_get_plan_shares(request, plan_id):
    """Gibt Liste der User zurück, mit denen ein Plan geteilt ist."""
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    shared_users = list(plan.shared_with.values("id", "username"))

    return JsonResponse({"success": True, "shared_with": shared_users})


@login_required
def api_get_group_shares(request, gruppe_id):
    """Gibt Liste der User zurück, mit denen eine Gruppe geteilt ist."""
    # Erster Plan der Gruppe
    plan = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).first()

    if not plan:
        return JsonResponse({"success": False, "error": "Gruppe nicht gefunden"}, status=404)

    shared_users = list(plan.shared_with.values("id", "username"))

    return JsonResponse({"success": True, "shared_with": shared_users})
