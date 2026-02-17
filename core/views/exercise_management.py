"""
Exercise Management Module

Handles custom exercise creation, equipment management, and admin import/export functionality.
This module provides views for:
- Creating custom exercises (create_custom_uebung)
- Managing user equipment (equipment_management, toggle_equipment)
- Exporting and importing exercise data (export_uebungen, import_uebungen)
"""

import csv
import json
import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import EQUIPMENT_CHOICES, Equipment, Uebung

logger = logging.getLogger(__name__)


@login_required
def equipment_management(request: HttpRequest) -> HttpResponse:
    """
    Equipment/Ausrüstungs-Verwaltung
    User kann seine verfügbare Ausrüstung auswählen
    """
    # Alle verfügbaren Equipment-Typen laden (oder erstellen falls leer)

    # Equipment initial erstellen falls nicht vorhanden
    for eq_code, eq_name in EQUIPMENT_CHOICES:
        Equipment.objects.get_or_create(name=eq_code)

    all_equipment = Equipment.objects.all().order_by("name")
    user_equipment_ids = request.user.verfuegbares_equipment.values_list("id", flat=True)

    # Kategorien für bessere Darstellung mit Icons
    equipment_categories = {
        "Freie Gewichte": {
            "icon": "bi-hammer",
            "equipment": ["LANGHANTEL", "KURZHANTEL", "KETTLEBELL"],
            "color": "primary",
        },
        "Racks & Stangen": {
            "icon": "bi-border-all",
            "equipment": ["KLIMMZUG", "DIP", "SMITHMASCHINE"],
            "color": "success",
        },
        "Bänke": {"icon": "bi-layout-wtf", "equipment": ["BANK", "SCHRAEGBANK"], "color": "info"},
        "Maschinen": {
            "icon": "bi-gear-wide-connected",
            "equipment": [
                "KABELZUG",
                "BEINPRESSE",
                "LEG_CURL",
                "LEG_EXT",
                "HACKENSCHMIDT",
                "RUDERMASCHINE",
                "ADDUKTOREN_MASCHINE",
                "ABDUKTOREN_MASCHINE",
            ],
            "color": "warning",
        },
        "Funktionell": {
            "icon": "bi-bezier2",
            "equipment": ["WIDERSTANDSBAND", "SUSPENSION", "MEDIZINBALL", "BOXEN"],
            "color": "secondary",
        },
        "Basics": {"icon": "bi-person", "equipment": ["MATTE", "KOERPER"], "color": "dark"},
    }

    categorized_equipment = {}
    for category, config in equipment_categories.items():
        eq_list = all_equipment.filter(name__in=config["equipment"])
        if eq_list.exists():
            categorized_equipment[category] = {
                "icon": config["icon"],
                "color": config["color"],
                "items": eq_list,
            }

    # Statistik: Übungen mit verfügbarem Equipment
    total_uebungen = Uebung.objects.filter(is_custom=False).count()
    if user_equipment_ids:
        # Übungen die ALLE ihre benötigten Equipment-Teile beim User verfügbar haben
        available_uebungen = 0
        for uebung in Uebung.objects.filter(is_custom=False).prefetch_related("equipment"):
            required_eq = set(uebung.equipment.values_list("id", flat=True))
            if not required_eq or required_eq.issubset(set(user_equipment_ids)):
                available_uebungen += 1
    else:
        # Nur Übungen ohne Equipment-Anforderung
        available_uebungen = Uebung.objects.filter(is_custom=False, equipment__isnull=True).count()

    context = {
        "categorized_equipment": categorized_equipment,
        "user_equipment_ids": list(user_equipment_ids),
        "total_uebungen": total_uebungen,
        "available_uebungen": available_uebungen,
        "unavailable_uebungen": total_uebungen - available_uebungen,
    }

    return render(request, "core/equipment_management.html", context)


@login_required
def toggle_equipment(request: HttpRequest, equipment_id: int) -> HttpResponse:
    """
    Toggle Equipment für User (An/Aus)
    """
    equipment = get_object_or_404(Equipment, id=equipment_id)

    if request.user in equipment.users.all():
        equipment.users.remove(request.user)
        status = "removed"
    else:
        equipment.users.add(request.user)
        status = "added"

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": status, "equipment_name": str(equipment)})

    return redirect("equipment_management")


@staff_member_required
def export_uebungen(request: HttpRequest) -> HttpResponse:
    """
    Exportiert alle Übungen als JSON-Datei
    Nur für Admin-User (staff_member_required)
    """

    # Format-Parameter (json oder csv)
    export_format = request.GET.get("format", "json")

    if export_format == "json":
        # JSON Export mit allen Feldern
        uebungen = Uebung.objects.all().prefetch_related("equipment")

        exercises_data = []
        for uebung in uebungen:
            exercises_data.append(
                {
                    "id": uebung.id,
                    "bezeichnung": uebung.bezeichnung,
                    "muskelgruppe": uebung.muskelgruppe,
                    "hilfsmuskeln": uebung.hilfsmuskeln if uebung.hilfsmuskeln else [],
                    "bewegungstyp": uebung.bewegungstyp,
                    "gewichts_typ": uebung.gewichts_typ,
                    "koerpergewicht_faktor": float(uebung.koerpergewicht_faktor),
                    "standard_beginner": (
                        float(uebung.standard_beginner) if uebung.standard_beginner else None
                    ),
                    "standard_intermediate": (
                        float(uebung.standard_intermediate)
                        if uebung.standard_intermediate
                        else None
                    ),
                    "standard_advanced": (
                        float(uebung.standard_advanced) if uebung.standard_advanced else None
                    ),
                    "standard_elite": (
                        float(uebung.standard_elite) if uebung.standard_elite else None
                    ),
                    "equipment": [eq.get_name_display() for eq in uebung.equipment.all()],
                    "beschreibung": uebung.beschreibung if uebung.beschreibung else "",
                }
            )

        # Response als downloadbare JSON-Datei
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        response = HttpResponse(
            json.dumps({"exercises": exercises_data}, indent=2, ensure_ascii=False),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="uebungen_export_{timestamp}.json"'
        return response

    elif export_format == "csv":
        # CSV Export
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="uebungen_export_{timestamp}.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Bezeichnung",
                "Muskelgruppe",
                "Hilfsmuskeln",
                "Bewegungstyp",
                "Gewichtstyp",
                "Körpergewicht-Faktor",
                "1RM Anfänger (80kg)",
                "1RM Fortgeschritten (80kg)",
                "1RM Erfahren (80kg)",
                "1RM Elite (80kg)",
                "Equipment",
                "Beschreibung",
            ]
        )

        uebungen = Uebung.objects.all().prefetch_related("equipment")
        for uebung in uebungen:
            writer.writerow(
                [
                    uebung.id,
                    uebung.bezeichnung,
                    uebung.muskelgruppe,
                    ", ".join(uebung.hilfsmuskeln) if uebung.hilfsmuskeln else "",
                    uebung.bewegungstyp,
                    uebung.gewichts_typ,
                    float(uebung.koerpergewicht_faktor),
                    float(uebung.standard_beginner) if uebung.standard_beginner else "",
                    float(uebung.standard_intermediate) if uebung.standard_intermediate else "",
                    float(uebung.standard_advanced) if uebung.standard_advanced else "",
                    float(uebung.standard_elite) if uebung.standard_elite else "",
                    ", ".join([eq.get_name_display() for eq in uebung.equipment.all()]),
                    uebung.beschreibung if uebung.beschreibung else "",
                ]
            )

        return response

    return JsonResponse({"error": "Invalid format"}, status=400)


# ---------------------------------------------------------------------------
# Private helpers for import_uebungen
# ---------------------------------------------------------------------------


def _parse_import_file(import_file) -> tuple:
    """
    Parst eine JSON-Importdatei und extrahiert die Übungsliste.
    Gibt (exercises_list, error_message) zurück.
    """
    try:
        data = json.load(import_file)
    except json.JSONDecodeError as e:
        logger.warning("JSON import parse error: %s", e)
        return None, "Ungültiges JSON-Format. Bitte Datei prüfen."

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "exercises" in data:
        return data["exercises"], None
    return None, 'JSON muss Array oder Object mit "exercises" Key sein'


def _resolve_equipment_for_uebung(equipment_names: list, bezeichnung: str, errors: list) -> list:
    """
    Löst Equipment-Namen in Equipment-Objekte auf.
    Fehler werden in errors-Liste gesammelt (mutiert).
    """
    equipment_objs = []
    for eq_name in equipment_names:
        try:
            equipment_objs.append(Equipment.objects.get(name=eq_name))
        except Equipment.DoesNotExist:
            found = False
            for choice_value, choice_display in EQUIPMENT_CHOICES:
                if choice_display == eq_name:
                    try:
                        equipment_objs.append(Equipment.objects.get(name=choice_value))
                        found = True
                        break
                    except Equipment.DoesNotExist:
                        logger.warning(
                            'Equipment "%s" not found while resolving "%s".', choice_value, eq_name
                        )
            if not found:
                errors.append(f'Equipment "{eq_name}" nicht gefunden für Übung "{bezeichnung}"')
    return equipment_objs


def _save_or_count_uebung(
    ex_data: dict, equipment_objs: list, update_existing: bool, dry_run: bool, stats: dict
) -> None:
    """
    Erstellt/aktualisiert eine Übung oder zählt sie (bei dry_run).
    Mutiert stats-Dict: created_count, updated_count.
    """
    bezeichnung = ex_data["bezeichnung"]
    ex_id = ex_data.get("id")
    defaults = {
        "bezeichnung": bezeichnung,
        "muskelgruppe": ex_data.get("muskelgruppe", "SONSTIGES"),
        "hilfsmuskeln": ex_data.get("hilfsmuskeln", []),
        "bewegungstyp": ex_data.get("bewegungstyp", "COMPOUND"),
        "gewichts_typ": ex_data.get("gewichts_typ", "FREI"),
        "koerpergewicht_faktor": float(ex_data.get("koerpergewicht_faktor", 1.0)),
        "standard_beginner": ex_data.get("standard_beginner"),
        "standard_intermediate": ex_data.get("standard_intermediate"),
        "standard_advanced": ex_data.get("standard_advanced"),
        "standard_elite": ex_data.get("standard_elite"),
        "beschreibung": ex_data.get("beschreibung", ""),
    }

    if dry_run:
        if ex_id and Uebung.objects.filter(id=ex_id).exists():
            stats["updated_count"] += 1
        else:
            stats["created_count"] += 1
        return

    if ex_id and update_existing:
        uebung, created = Uebung.objects.update_or_create(id=ex_id, defaults=defaults)
        uebung.equipment.set(equipment_objs)
        stats["created_count" if created else "updated_count"] += 1
    else:
        uebung = Uebung.objects.create(
            **{k: v for k, v in defaults.items() if k != "bezeichnung"}, bezeichnung=bezeichnung
        )
        uebung.equipment.set(equipment_objs)
        stats["created_count"] += 1


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


@staff_member_required
def import_uebungen(request: HttpRequest) -> HttpResponse:
    """
    Importiert Übungen aus JSON-Datei.
    Nur für Admin-User (staff_member_required).
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Keine Datei ausgewählt")
            return redirect("uebungen_auswahl")

        exercises, parse_error = _parse_import_file(import_file)
        if parse_error:
            messages.error(request, parse_error)
            return redirect("uebungen_auswahl")

        update_existing = request.POST.get("update_existing") == "on"
        dry_run = request.POST.get("dry_run") == "on"
        stats = {"created_count": 0, "updated_count": 0, "skipped_count": 0}
        errors: list = []

        for ex_data in exercises:
            try:
                if not ex_data.get("bezeichnung"):
                    stats["skipped_count"] += 1
                    continue
                equipment_objs = _resolve_equipment_for_uebung(
                    ex_data.get("equipment", []), ex_data["bezeichnung"], errors
                )
                _save_or_count_uebung(ex_data, equipment_objs, update_existing, dry_run, stats)
            except Exception as e:
                logger.error(
                    "Import error for exercise '%s': %s",
                    ex_data.get("bezeichnung", "?"),
                    e,
                    exc_info=True,
                )
                errors.append(
                    f'Fehler bei "{ex_data.get("bezeichnung", "?")}" – Übung übersprungen'
                )

        c, u, s = stats["created_count"], stats["updated_count"], stats["skipped_count"]
        if dry_run:
            messages.info(
                request, f"Dry-Run: {c} würden erstellt, {u} aktualisiert, {s} übersprungen"
            )
        else:
            messages.success(request, f"Import: {c} erstellt, {u} aktualisiert, {s} übersprungen")
        if errors:
            messages.warning(request, f"{len(errors)} Fehler: " + "; ".join(errors[:5]))

    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        messages.error(request, "Import fehlgeschlagen. Bitte überprüfe das JSON-Format.")

    return redirect("uebungen_auswahl")


@login_required
def create_custom_uebung(request: HttpRequest) -> JsonResponse:
    """
    Erstellt eine benutzerdefinierte Übung.
    Returns: JSON mit {'success': bool, 'uebung_id': int, 'message': str}
    """
    try:
        data = json.loads(request.body)

        bezeichnung = data.get("bezeichnung", "").strip()
        muskelgruppe = data.get("muskelgruppe")
        gewichts_typ = data.get("gewichts_typ", "GESAMT")
        bewegungstyp = data.get("bewegungstyp", "ISOLATION")
        beschreibung = data.get("beschreibung", "").strip()
        equipment_ids = data.get("equipment", [])

        # Validation
        if not bezeichnung:
            return JsonResponse({"success": False, "error": "Name ist erforderlich"}, status=400)

        if not muskelgruppe:
            return JsonResponse(
                {"success": False, "error": "Muskelgruppe ist erforderlich"}, status=400
            )

        # Prüfe ob Name bereits existiert (nur für diesen User)
        if Uebung.objects.filter(bezeichnung__iexact=bezeichnung, created_by=request.user).exists():
            return JsonResponse(
                {"success": False, "error": "Du hast bereits eine Übung mit diesem Namen"},
                status=400,
            )

        # Erstelle Custom-Übung
        uebung = Uebung.objects.create(
            bezeichnung=bezeichnung,
            muskelgruppe=muskelgruppe,
            gewichts_typ=gewichts_typ,
            bewegungstyp=bewegungstyp,
            beschreibung=beschreibung,
            created_by=request.user,
            is_custom=True,
        )

        # Equipment zuweisen
        if equipment_ids:
            equipment_objs = Equipment.objects.filter(id__in=equipment_ids)
            uebung.equipment.set(equipment_objs)

        return JsonResponse(
            {
                "success": True,
                "uebung_id": uebung.id,
                "message": f'Übung "{bezeichnung}" erstellt',
                "uebung": {
                    "id": uebung.id,
                    "name": uebung.bezeichnung,
                    "muskelgruppe": uebung.get_muskelgruppe_display(),
                    "is_custom": True,
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Ungültige JSON-Daten"}, status=400)
    except Exception as e:
        logger.error(f"API request error: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": "Anfrage konnte nicht verarbeitet werden."}, status=500
        )
