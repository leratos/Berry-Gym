"""
Template-based plan creation module.

This module handles template-based plan creation with equipment substitution.
It provides endpoints to retrieve available plan templates, get detailed template
information, and create plans from templates with automatic equipment substitution
when required equipment is not available.
"""

import json
import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse

from ..helpers.exercises import find_substitute_exercise
from ..models import Equipment, Plan, PlanUebung, Uebung

logger = logging.getLogger(__name__)

# Mapping von vereinfachten Template-Equipment-Namen zu DB Display-Namen
_EQUIPMENT_NAME_MAPPING: dict[str, str | None] = {
    "kurzhantel": "kurzhanteln",
    "langhantel": "langhantel",
    "kabel": "kabelzug / latzug",
    "barren": "dipstation / barren",
    "klimmzugstange": "klimmzugstange",
    "maschine": None,  # Generisch – wird separat behandelt
    "körpergewicht": "nur körpergewicht",
}

_MASCHINE_KEYWORDS = ["beinpresse", "leg curl", "leg extension", "maschine", "smith"]


def _load_templates() -> dict:
    """Lädt plan_templates.json und gibt den Inhalt zurück."""
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "plan_templates.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_equipment_available(template_equip_name: str, user_equipment_set: set[str]) -> bool:
    """Prüft ob ein Template-Equipment-Name im User-Equipment-Set verfügbar ist."""
    name_lower = template_equip_name.strip().lower()
    if name_lower == "körpergewicht":
        return True
    mapped = _EQUIPMENT_NAME_MAPPING.get(name_lower)
    if mapped is not None:
        return mapped in user_equipment_set
    if name_lower == "maschine":
        return any(kw in eq for eq in user_equipment_set for kw in _MASCHINE_KEYWORDS)
    return name_lower in user_equipment_set


def _find_uebung_for_exercise(exercise_data: dict, user_equipment_set: set[str]):
    """Sucht eine passende Uebung für einen Template-Exercise-Eintrag.

    Reihenfolge: exakter Name → Teilmatch → Substitut bei fehlendem Equipment.
    Gibt Uebung-Objekt oder None zurück.
    """
    exercise_name = exercise_data["name"]
    uebung = Uebung.objects.filter(bezeichnung=exercise_name).first()

    if not uebung:
        clean_name = exercise_name.split("(")[0].strip()
        uebung = Uebung.objects.filter(bezeichnung__icontains=clean_name).first()

    if not uebung and not _check_equipment_available(
        exercise_data["equipment"], user_equipment_set
    ):
        substitute = find_substitute_exercise(
            exercise_name, exercise_data["equipment"].strip().lower(), user_equipment_set
        )
        if substitute and "name" in substitute:
            uebung = Uebung.objects.filter(
                bezeichnung__icontains=substitute["name"].split("(")[0].strip()
            ).first()

    return uebung


def get_plan_templates(request: HttpRequest) -> JsonResponse:
    """API Endpoint: Liefert alle verfügbaren Plan-Templates."""
    try:
        templates = _load_templates()
        templates_overview = {
            key: {
                "name": t["name"],
                "description": t["description"],
                "frequency_per_week": t["frequency_per_week"],
                "difficulty": t["difficulty"],
                "goal": t["goal"],
                "days_count": len(t["days"]),
            }
            for key, t in templates.items()
        }
        return JsonResponse(templates_overview)
    except Exception as e:
        logger.error(f"Get Plan Templates Error: {e}", exc_info=True)
        return JsonResponse(
            {"error": "Templates konnten nicht geladen werden. Bitte später erneut versuchen."},
            status=500,
        )


@login_required
def get_template_detail(request: HttpRequest, template_key: str) -> JsonResponse:
    """API Endpoint: Liefert alle Details eines Templates inkl. Übungen."""

    try:
        templates = _load_templates()

        if template_key not in templates:
            return JsonResponse({"error": "Template nicht gefunden"}, status=404)

        template = templates[template_key]

        user_equipment_set = set(
            eq.get_name_display().strip().lower()
            for eq in Equipment.objects.filter(users=request.user)
        )
        logger.info(f"User equipment: {user_equipment_set}")

        # Template anpassen: Prüfe ob Übungen machbar sind
        adapted_template = {
            "name": template.get("name", ""),
            "description": template.get("description", ""),
            "frequency_per_week": template.get("frequency_per_week", 0),
            "difficulty": template.get("difficulty", ""),
            "goal": template.get("goal", ""),
            "days_adapted": [],
        }

        for day in template.get("days", []):
            adapted_day = {"name": day.get("name", ""), "exercises": []}

            for exercise in day.get("exercises", []):
                exercise_copy = {
                    "name": exercise.get("name", ""),
                    "sets": exercise.get("sets", 0),
                    "reps": exercise.get("reps", ""),
                    "equipment": exercise.get("equipment", ""),
                }
                required_equipment = exercise.get("equipment", "").strip()

                # Prüfe ob Equipment verfügbar (mit Mapping)
                if _check_equipment_available(required_equipment, user_equipment_set):
                    exercise_copy["available"] = True
                    exercise_copy["substitute"] = None
                else:
                    exercise_copy["available"] = False
                    # Finde Ersatzübung
                    substitute = find_substitute_exercise(
                        exercise.get("name", ""), required_equipment.lower(), user_equipment_set
                    )
                    exercise_copy["substitute"] = substitute

                adapted_day["exercises"].append(exercise_copy)

            adapted_template["days_adapted"].append(adapted_day)

        return JsonResponse(adapted_template)
    except Exception as e:
        logger.error(f"Template detail error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Trainingsplan-Vorlage konnte nicht geladen werden.",
                "template_key": template_key,
            },
            status=500,
        )


@login_required
def create_plan_from_template(request: HttpRequest, template_key: str) -> JsonResponse:
    """Erstellt einen neuen Plan basierend auf einem Template."""
    if request.method != "POST":
        return JsonResponse({"error": "Nur POST erlaubt"}, status=405)

    try:
        templates = _load_templates()

        if template_key not in templates:
            return JsonResponse({"error": "Template nicht gefunden"}, status=404)

        template = templates[template_key]
        user_equipment_set = set(
            eq.get_name_display().strip().lower()
            for eq in Equipment.objects.filter(users=request.user)
        )

        created_plans = []
        for day in template["days"]:
            plan = Plan.objects.create(
                user=request.user, name=day["name"], beschreibung=template["name"]
            )
            created_plans.append(plan)

            reihenfolge = 1
            for exercise_data in day["exercises"]:
                uebung = _find_uebung_for_exercise(exercise_data, user_equipment_set)
                if uebung:
                    PlanUebung.objects.create(
                        plan=plan,
                        uebung=uebung,
                        trainingstag=day["name"],
                        reihenfolge=reihenfolge,
                        saetze_ziel=exercise_data["sets"],
                        wiederholungen_ziel=exercise_data["reps"],
                    )
                    reihenfolge += 1

        plan_count = len(created_plans)
        messages.success(
            request, f"{plan_count} Pläne erstellt: {', '.join(p.name for p in created_plans)}"
        )
        return JsonResponse(
            {"success": True, "plan_ids": [p.id for p in created_plans], "plan_count": plan_count}
        )

    except Exception as e:
        logger.error(f"Plan creation error: {e}", exc_info=True)
        return JsonResponse({"error": "Trainingsplan konnte nicht erstellt werden."}, status=500)
