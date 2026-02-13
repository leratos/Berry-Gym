"""
Exercise utility functions for HomeGym application.
"""

import logging

logger = logging.getLogger(__name__)


def _build_equipment_map(all_equipment) -> dict:
    """Erstellt Reverse-Mapping: display_name.lower() → Equipment-Objekt."""
    return {eq.get_name_display().strip().lower(): eq for eq in all_equipment}


def _get_available_equipment_objects(available_equipment: list, equipment_map: dict) -> list:
    """Gibt Equipment-Objekte für die verfügbaren Display-Namen zurück."""
    objects = []
    for name in available_equipment:
        eq = equipment_map.get(name)
        if eq:
            objects.append(eq)
    logger.info(f"Available equipment objects: {[eq.name for eq in objects]}")
    return objects


def _find_original_uebung(original_name: str):
    """
    Sucht die Original-Übung in der DB.
    Fallback: Teilmatch, dann Keyword-Mapping (gibt Pseudo-Objekt zurück).
    Gibt None zurück wenn gar nichts gefunden.
    """
    from core.models import Uebung

    # 1. Exakter Match
    uebung = Uebung.objects.filter(bezeichnung=original_name).first()
    if uebung:
        return uebung

    # 2. Teilmatch
    clean_name = original_name.split("(")[0].strip()
    uebung = Uebung.objects.filter(bezeichnung__icontains=clean_name).first()
    if uebung:
        return uebung

    # 3. Keyword-Mapping → Pseudo-Objekt
    exercise_to_muscle = {
        "klimmzüge": "RUECKEN_LAT",
        "klimmzug": "RUECKEN_LAT",
        "lat pulldown": "RUECKEN_LAT",
        "latzug": "RUECKEN_LAT",
        "rudern": "RUECKEN_LAT",
        "dips": "TRIZEPS",
        "dip": "TRIZEPS",
        "liegestütz": "BRUST",
        "push-up": "BRUST",
        "bankdrücken": "BRUST",
        "fliegende": "BRUST",
        "crossover": "BRUST",
        "schulterdrücken": "SCHULTER_VORN",
        "shoulder press": "SCHULTER_VORN",
        "seitheben": "SCHULTER_SEIT",
        "lateral raise": "SCHULTER_SEIT",
        "facepull": "SCHULTER_HINT",
        "face pull": "SCHULTER_HINT",
        "bizeps": "BIZEPS",
        "curl": "BIZEPS",
        "trizeps": "TRIZEPS",
        "pushdown": "TRIZEPS",
        "squat": "BEINE_QUAD",
        "kniebeuge": "BEINE_QUAD",
        "beinpresse": "BEINE_QUAD",
        "beinstrecker": "BEINE_QUAD",
        "beinbeuger": "BEINE_HAM",
        "leg curl": "BEINE_HAM",
        "kreuzheben": "BEINE_HAM",
        "wadenheben": "WADEN",
        "calf": "WADEN",
    }
    for key, muscle in exercise_to_muscle.items():
        if key in original_name.lower():
            return type(
                "obj", (object,), {"muskelgruppe": muscle, "bewegungstyp": "ISOLATION", "id": -1}
            )()

    return None


def _find_substitute_by_priority(
    muscle_group: str,
    movement_type: str | None,
    original_id: int,
    available_equipment_objects: list,
    equipment_map: dict,
) -> dict | None:
    """
    Sucht Ersatzübung nach Priorität:
    1. Widerstandsband, 2. gleiches Bewegungsmuster, 3. gleiche Muskelgruppe.
    Gibt None zurück wenn kein Match gefunden.
    """
    from core.models import Uebung

    exclude_id = original_id if original_id > 0 else 0

    # 1. Band-Alternative
    band_eq = equipment_map.get("widerstandsbänder")
    if band_eq and band_eq in available_equipment_objects:
        result = (
            Uebung.objects.filter(muskelgruppe=muscle_group, equipment=band_eq)
            .exclude(id=exclude_id)
            .first()
        )
        if result:
            logger.info(f"Found band alternative: {result.bezeichnung}")
            return {
                "name": result.bezeichnung,
                "equipment": "Widerstandsbänder",
                "note": "Band-Alternative",
            }

    # 2. Gleiches Bewegungsmuster + verfügbares Equipment
    if movement_type:
        for eq in available_equipment_objects:
            result = (
                Uebung.objects.filter(
                    muskelgruppe=muscle_group, bewegungstyp=movement_type, equipment=eq
                )
                .exclude(id=exclude_id)
                .first()
            )
            if result:
                logger.info(f"Found same movement: {result.bezeichnung}")
                return {"name": result.bezeichnung, "equipment": eq.get_name_display()}

    # 3. Nur gleiche Muskelgruppe + verfügbares Equipment
    for eq in available_equipment_objects:
        result = (
            Uebung.objects.filter(muskelgruppe=muscle_group, equipment=eq)
            .exclude(id=exclude_id)
            .first()
        )
        if result:
            logger.info(f"Found same muscle: {result.bezeichnung}")
            return {"name": result.bezeichnung, "equipment": eq.get_name_display()}

    return None


def _find_bodyweight_fallback(muscle_group: str, original_id: int) -> dict | None:
    """Gibt Körpergewicht-Übung als letzten Fallback zurück."""
    from core.models import Equipment, Uebung

    koerper_eq = Equipment.objects.filter(name="KOERPER").first()
    if not koerper_eq:
        return None
    exclude_id = original_id if original_id > 0 else 0
    result = (
        Uebung.objects.filter(muskelgruppe=muscle_group, equipment=koerper_eq)
        .exclude(id=exclude_id)
        .first()
    )
    if result:
        logger.info(f"Found bodyweight: {result.bezeichnung}")
        return {
            "name": result.bezeichnung,
            "equipment": "Nur Körpergewicht",
            "note": "Körpergewicht-Alternative",
        }
    return None


def find_substitute_exercise(original_name, required_equipment, available_equipment):
    """
    Findet eine Ersatzübung aus der Datenbank.
    Priorität: 1. Band-Alternativen, 2. Gleiches Bewegungsmuster,
               3. Gleiche Muskelgruppe, 4. Körpergewicht
    """
    from core.models import Equipment

    logger.info(
        f"Finding substitute for: {original_name}, required: {required_equipment}, "
        f"available: {available_equipment}"
    )

    try:
        equipment_map = _build_equipment_map(Equipment.objects.all())
        available_equipment_objects = _get_available_equipment_objects(
            available_equipment, equipment_map
        )

        original_uebung = _find_original_uebung(original_name)

        if original_uebung:
            muscle_group = getattr(original_uebung, "muskelgruppe", None)
            movement_type = getattr(original_uebung, "bewegungstyp", None)
            original_id = getattr(original_uebung, "id", -1)

            logger.info(f"Found original: muscle={muscle_group}, movement={movement_type}")

            if muscle_group and available_equipment_objects:
                result = _find_substitute_by_priority(
                    muscle_group,
                    movement_type,
                    original_id,
                    available_equipment_objects,
                    equipment_map,
                )
                if result:
                    return result

            # Letzter Fallback: Körpergewicht
            if muscle_group:
                bodyweight = _find_bodyweight_fallback(muscle_group, original_id)
                if bodyweight:
                    return bodyweight

        logger.warning(f"No substitute found for {original_name}")
        return {
            "name": f'Bitte Equipment "{required_equipment}" ergänzen',
            "equipment": required_equipment,
            "note": "Keine passende Alternative gefunden",
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        return {
            "name": f'Alternative für "{original_name}" nicht gefunden',
            "equipment": required_equipment,
            "note": f"Fehler: {str(e)}",
        }
