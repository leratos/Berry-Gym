"""
Exercise utility functions for HomeGym application.
"""

import logging

logger = logging.getLogger(__name__)


def find_substitute_exercise(original_name, required_equipment, available_equipment):
    """
    Findet eine Ersatzübung aus der Datenbank.
    Versucht ähnliche Muskelgruppe und Bewegungstyp mit verfügbarem Equipment.
    Priorität: 1. Band-Alternativen, 2. Gleiches Bewegungsmuster, 3. Gleiche Muskelgruppe, 4. Körpergewicht
    """
    from core.models import Uebung, Equipment

    logger.info(f'Finding substitute for: {original_name}, required: {required_equipment}, available: {available_equipment}')

    # Erstelle Reverse-Mapping: Display-Name (lowercase) -> Equipment-Objekt
    all_equipment = Equipment.objects.all()
    equipment_map = {}
    for eq in all_equipment:
        display_name = eq.get_name_display().strip().lower()
        equipment_map[display_name] = eq

    # Sammle verfügbare Equipment-Objekte
    available_equipment_objects = []
    for equip_name in available_equipment:
        equip_obj = equipment_map.get(equip_name)
        if equip_obj:
            available_equipment_objects.append(equip_obj)

    logger.info(f'Available equipment objects: {[eq.name for eq in available_equipment_objects]}')

    # Versuche Original-Übung in DB zu finden
    try:
        # Erst exakter Match
        original_uebung = Uebung.objects.filter(bezeichnung=original_name).first()

        # Fallback: Teilmatch
        if not original_uebung:
            clean_name = original_name.split('(')[0].strip()
            original_uebung = Uebung.objects.filter(bezeichnung__icontains=clean_name).first()

        if not original_uebung:
            # Kein Original gefunden - versuche allgemeine Suche nach Muskelgruppe
            exercise_to_muscle = {
                'klimmzüge': 'RUECKEN_LAT',
                'klimmzug': 'RUECKEN_LAT',
                'lat pulldown': 'RUECKEN_LAT',
                'latzug': 'RUECKEN_LAT',
                'rudern': 'RUECKEN_LAT',
                'dips': 'TRIZEPS',
                'dip': 'TRIZEPS',
                'liegestütz': 'BRUST',
                'push-up': 'BRUST',
                'bankdrücken': 'BRUST',
                'fliegende': 'BRUST',
                'crossover': 'BRUST',
                'schulterdrücken': 'SCHULTER_VORN',
                'shoulder press': 'SCHULTER_VORN',
                'seitheben': 'SCHULTER_SEIT',
                'lateral raise': 'SCHULTER_SEIT',
                'facepull': 'SCHULTER_HINT',
                'face pull': 'SCHULTER_HINT',
                'bizeps': 'BIZEPS',
                'curl': 'BIZEPS',
                'trizeps': 'TRIZEPS',
                'pushdown': 'TRIZEPS',
                'squat': 'BEINE_QUAD',
                'kniebeuge': 'BEINE_QUAD',
                'beinpresse': 'BEINE_QUAD',
                'beinstrecker': 'BEINE_QUAD',
                'beinbeuger': 'BEINE_HAM',
                'leg curl': 'BEINE_HAM',
                'kreuzheben': 'BEINE_HAM',
                'wadenheben': 'WADEN',
                'calf': 'WADEN',
            }

            for key, muscle in exercise_to_muscle.items():
                if key in original_name.lower():
                    # Erstelle Pseudo-Objekt
                    original_uebung = type('obj', (object,), {
                        'muskelgruppe': muscle,
                        'bewegungstyp': 'ISOLATION',
                        'id': -1
                    })()
                    break

        if original_uebung:
            muscle_group = getattr(original_uebung, 'muskelgruppe', None)
            movement_type = getattr(original_uebung, 'bewegungstyp', None)
            original_id = getattr(original_uebung, 'id', -1)

            logger.info(f'Found original: muscle={muscle_group}, movement={movement_type}')

            if muscle_group and len(available_equipment_objects) > 0:
                # 1. Priorität: Band-Alternative (Widerstandsbänder)
                band_eq = equipment_map.get('widerstandsbänder')
                if band_eq and band_eq in available_equipment_objects:
                    band_exercise = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=band_eq
                    ).exclude(id=original_id if original_id > 0 else 0).first()

                    if band_exercise:
                        logger.info(f'Found band alternative: {band_exercise.bezeichnung}')
                        return {
                            'name': band_exercise.bezeichnung,
                            'equipment': 'Widerstandsbänder',
                            'note': 'Band-Alternative'
                        }

                # 2. Gleiches Bewegungsmuster + verfügbares Equipment
                if movement_type:
                    for equip_obj in available_equipment_objects:
                        similar = Uebung.objects.filter(
                            muskelgruppe=muscle_group,
                            bewegungstyp=movement_type,
                            equipment=equip_obj
                        ).exclude(id=original_id if original_id > 0 else 0).first()

                        if similar:
                            logger.info(f'Found same movement: {similar.bezeichnung}')
                            return {
                                'name': similar.bezeichnung,
                                'equipment': equip_obj.get_name_display()
                            }

                # 3. Nur gleiche Muskelgruppe + verfügbares Equipment
                for equip_obj in available_equipment_objects:
                    similar = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=equip_obj
                    ).exclude(id=original_id if original_id > 0 else 0).first()

                    if similar:
                        logger.info(f'Found same muscle: {similar.bezeichnung}')
                        return {
                            'name': similar.bezeichnung,
                            'equipment': equip_obj.get_name_display()
                        }

            # 4. Letzter Fallback: Körpergewicht-Übung
            if muscle_group:
                koerper_eq = Equipment.objects.filter(name='KOERPER').first()
                if koerper_eq:
                    bodyweight_exercise = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=koerper_eq
                    ).exclude(id=original_id if original_id > 0 else 0).first()

                    if bodyweight_exercise:
                        logger.info(f'Found bodyweight: {bodyweight_exercise.bezeichnung}')
                        return {
                            'name': bodyweight_exercise.bezeichnung,
                            'equipment': 'Nur Körpergewicht',
                            'note': 'Körpergewicht-Alternative'
                        }

        # Kein Match gefunden
        logger.warning(f'No substitute found for {original_name}')
        return {
            'name': f'Bitte Equipment "{required_equipment}" ergänzen',
            'equipment': required_equipment,
            'note': 'Keine passende Alternative gefunden'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'name': f'Alternative für "{original_name}" nicht gefunden',
            'equipment': required_equipment,
            'note': f'Fehler: {str(e)}'
        }
