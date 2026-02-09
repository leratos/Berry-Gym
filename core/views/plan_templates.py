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
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse

from ..helpers.exercises import find_substitute_exercise
from ..models import Equipment, Plan, PlanUebung, Uebung

logger = logging.getLogger(__name__)


def get_plan_templates(request):
    """API Endpoint: Liefert alle verfügbaren Plan-Templates."""
    try:
        templates_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "plan_templates.json"
        )
        with open(templates_path, "r", encoding="utf-8") as f:
            templates = json.load(f)

        # Nur Metadaten ohne Exercises zurückgeben
        templates_overview = {}
        for key, template in templates.items():
            templates_overview[key] = {
                "name": template["name"],
                "description": template["description"],
                "frequency_per_week": template["frequency_per_week"],
                "difficulty": template["difficulty"],
                "goal": template["goal"],
                "days_count": len(template["days"]),
            }

        return JsonResponse(templates_overview)
    except Exception as e:
        logger.error(f"Get Plan Templates Error: {e}", exc_info=True)
        return JsonResponse(
            {"error": "Templates konnten nicht geladen werden. Bitte später erneut versuchen."},
            status=500,
        )


@login_required
def get_template_detail(request, template_key):
    """API Endpoint: Liefert alle Details eines Templates inkl. Übungen."""

    try:
        templates_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "plan_templates.json"
        )
        with open(templates_path, "r", encoding="utf-8") as f:
            templates = json.load(f)

        if template_key not in templates:
            return JsonResponse({"error": "Template nicht gefunden"}, status=404)

        template = templates[template_key]

        # Mapping von Template-Equipment-Namen zu DB Display-Namen
        # Template verwendet vereinfachte Namen, DB hat exakte Display-Namen
        equipment_name_mapping = {
            "kurzhantel": "kurzhanteln",
            "langhantel": "langhantel",
            "kabel": "kabelzug / latzug",
            "barren": "dipstation / barren",
            "klimmzugstange": "klimmzugstange",
            "maschine": None,  # Generisch - wird separat behandelt
            "körpergewicht": "nur körpergewicht",
        }

        # User-Equipment ermitteln (Equipment hat ManyToMany 'users', kein 'verfuegbar' Feld)
        # Equipment für User abrufen
        user_equipment = Equipment.objects.filter(users=request.user)
        # Verwende get_name_display() für Display-Namen (z.B. "Klimmzugstange")
        user_equipment_set = set(eq.get_name_display().strip().lower() for eq in user_equipment)

        logger.info(f"User equipment: {user_equipment_set}")

        def check_equipment_available(template_equip_name):
            """Prüft ob Equipment verfügbar ist (mit Mapping)."""
            template_equip_lower = template_equip_name.strip().lower()

            # Körpergewicht ist immer verfügbar
            if template_equip_lower == "körpergewicht":
                return True

            # Mapping anwenden
            mapped_name = equipment_name_mapping.get(template_equip_lower)

            if mapped_name:
                # Direktes Mapping gefunden
                return mapped_name in user_equipment_set

            # Maschine-Equipment: Prüfe ob passende Maschine vorhanden
            if template_equip_lower == "maschine":
                # Prüfe ob User irgendeine Maschine hat (Beinpresse, Leg Curl, etc.)
                maschine_keywords = ["beinpresse", "leg curl", "leg extension", "maschine", "smith"]
                return any(kw in eq for eq in user_equipment_set for kw in maschine_keywords)

            # Fallback: Direkter Vergleich
            return template_equip_lower in user_equipment_set

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
                if check_equipment_available(required_equipment):
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
def create_plan_from_template(request, template_key):
    """Erstellt einen neuen Plan basierend auf einem Template."""
    if request.method != "POST":
        return JsonResponse({"error": "Nur POST erlaubt"}, status=405)

    try:
        # Template laden
        templates_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "plan_templates.json"
        )
        with open(templates_path, "r", encoding="utf-8") as f:
            templates = json.load(f)

        if template_key not in templates:
            return JsonResponse({"error": "Template nicht gefunden"}, status=404)

        template = templates[template_key]

        # User-Equipment mit Display-Namen
        user_equipment = Equipment.objects.filter(users=request.user)
        user_equipment_set = set(eq.get_name_display().strip().lower() for eq in user_equipment)

        # Mapping von Template-Equipment-Namen zu DB Display-Namen
        equipment_name_mapping = {
            "kurzhantel": "kurzhanteln",
            "langhantel": "langhantel",
            "kabel": "kabelzug / latzug",
            "barren": "dipstation / barren",
            "klimmzugstange": "klimmzugstange",
            "maschine": None,  # Generisch
            "körpergewicht": "nur körpergewicht",
        }

        def check_equipment_available(template_equip_name):
            """Prüft ob Equipment verfügbar ist (mit Mapping)."""
            template_equip_lower = template_equip_name.strip().lower()
            if template_equip_lower == "körpergewicht":
                return True
            mapped_name = equipment_name_mapping.get(template_equip_lower)
            if mapped_name:
                return mapped_name in user_equipment_set
            if template_equip_lower == "maschine":
                maschine_keywords = ["beinpresse", "leg curl", "leg extension", "maschine", "smith"]
                return any(kw in eq for eq in user_equipment_set for kw in maschine_keywords)
            return template_equip_lower in user_equipment_set

        # Für jeden Tag einen eigenen Plan erstellen
        created_plans = []

        for day in template["days"]:
            # Plan für diesen Tag erstellen
            plan = Plan.objects.create(
                user=request.user, name=day["name"], beschreibung=f"{template['name']}"
            )
            created_plans.append(plan)

            # Übungen zum Plan hinzufügen
            reihenfolge = 1
            for exercise_data in day["exercises"]:
                # Übung in DB suchen - exakter Match zuerst
                exercise_name = exercise_data["name"]
                uebung = Uebung.objects.filter(bezeichnung=exercise_name).first()

                # Fallback: Teilmatch
                if not uebung:
                    exercise_name_clean = exercise_name.split("(")[0].strip()
                    uebung = Uebung.objects.filter(
                        bezeichnung__icontains=exercise_name_clean
                    ).first()

                # Wenn nicht gefunden und Equipment fehlt, versuche Substitut
                if not uebung:
                    required_equipment = exercise_data["equipment"].strip().lower()
                    if not check_equipment_available(exercise_data["equipment"]):
                        substitute = find_substitute_exercise(
                            exercise_name, required_equipment, user_equipment_set
                        )
                        if substitute and "name" in substitute:
                            uebung = Uebung.objects.filter(
                                bezeichnung__icontains=substitute["name"].split("(")[0].strip()
                            ).first()

                # Wenn Übung gefunden, zum Plan hinzufügen
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
        plan_names = ", ".join([p.name for p in created_plans])
        messages.success(request, f"{plan_count} Pläne erstellt: {plan_names}")
        return JsonResponse(
            {"success": True, "plan_ids": [p.id for p in created_plans], "plan_count": plan_count}
        )

    except Exception as e:
        logger.error(f"Plan creation error: {e}", exc_info=True)
        return JsonResponse({"error": "Trainingsplan konnte nicht erstellt werden."}, status=500)
