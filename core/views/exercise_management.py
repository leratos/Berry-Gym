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
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import EQUIPMENT_CHOICES, Equipment, Uebung

logger = logging.getLogger(__name__)


@login_required
def equipment_management(request):
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
def toggle_equipment(request, equipment_id):
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
def export_uebungen(request):
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
                    "equipment": [eq.get_name_display() for eq in uebung.equipment.all()],
                    "beschreibung": uebung.beschreibung if hasattr(uebung, "beschreibung") else "",
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
                "Equipment",
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
                    ", ".join([eq.get_name_display() for eq in uebung.equipment.all()]),
                ]
            )

        return response

    return JsonResponse({"error": "Invalid format"}, status=400)


@staff_member_required
def import_uebungen(request):
    """
    Importiert Übungen aus JSON-Datei
    Nur für Admin-User (staff_member_required)
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Keine Datei ausgewählt")
            return redirect("uebungen_auswahl")

        # Parse JSON
        try:
            data = json.load(import_file)
        except json.JSONDecodeError as e:
            messages.error(request, f"Ungültiges JSON-Format: {e}")
            return redirect("uebungen_auswahl")

        # Extract exercises array
        if isinstance(data, list):
            exercises = data
        elif isinstance(data, dict) and "exercises" in data:
            exercises = data["exercises"]
        else:
            messages.error(request, 'JSON muss Array oder Object mit "exercises" Key sein')
            return redirect("uebungen_auswahl")

        # Options
        update_existing = request.POST.get("update_existing") == "on"
        dry_run = request.POST.get("dry_run") == "on"

        # Import-Statistiken
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for ex_data in exercises:
            try:
                bezeichnung = ex_data.get("bezeichnung")
                if not bezeichnung:
                    skipped_count += 1
                    continue

                # Equipment-Objekte finden
                equipment_names = ex_data.get("equipment", [])
                equipment_objs = []
                for eq_name in equipment_names:
                    try:
                        # Suche nach name (Display-Name aus Choices)
                        eq = Equipment.objects.get(name=eq_name)
                        equipment_objs.append(eq)
                    except Equipment.DoesNotExist:
                        # Fallback: Suche in EQUIPMENT_CHOICES by display name
                        found = False
                        for choice_value, choice_display in EQUIPMENT_CHOICES:
                            if choice_display == eq_name:
                                try:
                                    eq = Equipment.objects.get(name=choice_value)
                                    equipment_objs.append(eq)
                                    found = True
                                    break
                                except Equipment.DoesNotExist:
                                    logger.warning(
                                        'Equipment with internal name "%s" not found while resolving display name "%s".',
                                        choice_value,
                                        eq_name,
                                    )
                                    # Continue searching other equipment choices for a matching entry.
                                    continue
                        if not found:
                            errors.append(
                                f'Equipment "{eq_name}" nicht gefunden für Übung "{bezeichnung}"'
                            )

                # Übung erstellen oder aktualisieren
                ex_id = ex_data.get("id")

                if not dry_run:
                    if ex_id and update_existing:
                        # Update existing
                        uebung, created = Uebung.objects.update_or_create(
                            id=ex_id,
                            defaults={
                                "bezeichnung": bezeichnung,
                                "muskelgruppe": ex_data.get("muskelgruppe", "SONSTIGES"),
                                "hilfsmuskeln": ex_data.get("hilfsmuskeln", []),
                                "bewegungstyp": ex_data.get("bewegungstyp", "COMPOUND"),
                                "gewichts_typ": ex_data.get("gewichts_typ", "FREI"),
                            },
                        )

                        # Equipment zuweisen
                        uebung.equipment.set(equipment_objs)

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        # Create new (ohne ID-Angabe)
                        uebung = Uebung.objects.create(
                            bezeichnung=bezeichnung,
                            muskelgruppe=ex_data.get("muskelgruppe", "SONSTIGES"),
                            hilfsmuskeln=ex_data.get("hilfsmuskeln", []),
                            bewegungstyp=ex_data.get("bewegungstyp", "COMPOUND"),
                            gewichts_typ=ex_data.get("gewichts_typ", "FREI"),
                        )
                        uebung.equipment.set(equipment_objs)
                        created_count += 1
                else:
                    # Dry-Run: nur zählen
                    if ex_id and Uebung.objects.filter(id=ex_id).exists():
                        updated_count += 1
                    else:
                        created_count += 1

            except Exception as e:
                errors.append(f'Fehler bei "{ex_data.get("bezeichnung", "?")}": {str(e)}')

        # Feedback
        if dry_run:
            messages.info(
                request,
                f"Dry-Run abgeschlossen: {created_count} würden erstellt, {updated_count} würden aktualisiert, {skipped_count} übersprungen",
            )
        else:
            messages.success(
                request,
                f"Import erfolgreich: {created_count} erstellt, {updated_count} aktualisiert, {skipped_count} übersprungen",
            )

        if errors:
            messages.warning(request, f"{len(errors)} Fehler: " + "; ".join(errors[:5]))

    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        messages.error(request, "Import fehlgeschlagen. Bitte überprüfe das JSON-Format.")

    return redirect("uebungen_auswahl")


@login_required
def create_custom_uebung(request):
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
