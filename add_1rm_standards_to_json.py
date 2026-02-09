#!/usr/bin/env python3
"""
Script to add 1RM standards to initial_exercises.json
"""
import json

# Standards-Mapping: Übungsname-Pattern -> (beginner, intermediate, advanced, elite)
# Werte sind für 80kg Körpergewicht
standards_mapping = {
    # Große Verbundübungen - Brust
    'Bankdrücken (Kurzhantel)': (27.5, 40, 52.5, 65),
    'Bankdrücken (Langhantel)': (55, 80, 105, 130),
    'Schrägbankdrücken': (25, 37.5, 50, 62.5),
    'Floor Press': (25, 37.5, 50, 62.5),

    # Schulter
    'Schulterdrücken (Sitzend, Kurzhantel)': (17.5, 27.5, 37.5, 47.5),
    'Schulterdrücken (Stehend, Langhantel)': (35, 55, 75, 95),
    'Arnold Press': (15, 22.5, 30, 37.5),
    'Pike Push-ups': None,  # Körpergewicht

    # Beine - Kniebeuge
    'Kniebeuge': (70, 105, 140, 175),
    'Frontkniebeuge': (55, 85, 115, 145),
    'Goblet Squat': (20, 30, 40, 50),
    'Bulgarian Split Squat': (20, 30, 40, 50),
    'Wandsitz': None,  # Zeit-basiert

    # Beine - Kreuzheben
    'Kreuzheben': (95, 140, 185, 230),
    'Rumänisches Kreuzheben': (80, 120, 160, 200),
    'Stiff Leg Deadlift': (70, 105, 140, 175),
    'Good Mornings': (40, 60, 80, 100),

    # Beinpresse & Maschinen
    'Beinpresse': (140, 210, 280, 350),
    'Beinbeuger': (30, 45, 60, 75),
    'Beinstrecker': (35, 52.5, 70, 87.5),

    # Po & Hip Thrust
    'Hip Thrust': (80, 120, 160, 200),
    'Glute Bridge': None,  # Körpergewicht
    'Single Leg Hip Thrust': (15, 22.5, 30, 37.5),

    # Waden
    'Wadenheben': (70, 105, 140, 175),
    'Seated Calf Raises': (40, 60, 80, 100),
    'Single Leg Calf Raises': None,  # Körpergewicht
    'Donkey Calf Raises': None,  # Körpergewicht

    # Rücken - Klimmzüge & Rows
    'Klimmzüge': (0, 10, 25, 45),
    'Langhantel-Rudern': (50, 75, 100, 125),
    'Einarmiges Kurzhantelrudern': (25, 37.5, 50, 62.5),
    'Sitzendes Kabelrudern': (45, 67.5, 90, 112.5),
    'T-Bar Row': (50, 75, 100, 125),
    'Breites Rudern': (22.5, 33.75, 45, 56.25),
    'Seal Rows': (22.5, 33.75, 45, 56.25),
    'Inverted Rows': None,  # Körpergewicht

    # Lat Pulldown
    'Latzug': (40, 60, 80, 100),
    'Lat Pulldown': (40, 60, 80, 100),

    # Trapez & Shrugs
    'Shrugs': (50, 75, 100, 125),
    'Langhantel Shrugs': (80, 120, 160, 200),
    'Y-Raises': (5, 7.5, 10, 12.5),
    'Prone I-Y-T Raises': (5, 7.5, 10, 12.5),

    # Schulter - Isolation
    'Seitheben (Kurzhantel)': (8, 12, 17, 22),
    'Seitheben (Kabelzug)': (8, 12, 17, 22),
    'Front Raises': (8, 12, 17, 22),
    'Vorgebeugtes Seitheben': (7, 10.5, 14, 17.5),
    'Reverse Flys': (7, 10.5, 14, 17.5),
    'Face Pulls': (25, 40, 55, 70),
    'Lying Lateral Raises': (5, 7.5, 10, 12.5),
    'Upright Rows': (30, 45, 60, 75),

    # Bizeps
    'Bizeps Curls (Kurzhantel)': (10, 15, 20, 25),
    'Bizeps Curls (Langhantel)': (20, 30, 40, 50),
    'Hammer Curls': (12.5, 18.75, 25, 31.25),
    'Concentration Curls': (10, 15, 20, 25),

    # Trizeps
    'Dips': (0, 15, 30, 50),
    'Trizeps Overhead Extension': (15, 22.5, 30, 37.5),
    'Trizeps Pushdown': (25, 37.5, 50, 62.5),
    'Trizepsdrücken am Kabel': (25, 37.5, 50, 62.5),

    # Unterarme
    'Wrist Curls': (15, 22.5, 30, 37.5),
    'Reverse Curls': (15, 22.5, 30, 37.5),
    'Reverse Wrist Curls': (10, 15, 20, 25),

    # Brust - Isolation
    'Fliegende': (15, 22.5, 30, 37.5),
    'Cable Crossover': (15, 22.5, 30, 37.5),
    'Butterfly': (35, 52.5, 70, 87.5),

    # Lunges & Ausfallschritte
    'Ausfallschritte': (15, 22.5, 30, 37.5),
    'Side Lunges': (12.5, 18.75, 25, 31.25),

    # Adduktoren/Abduktoren
    'Abduktoren Maschine': (25, 37.5, 50, 62.5),
    'Adduktoren Maschine': (30, 45, 60, 75),
    'Sumo Squats': (30, 45, 60, 75),
    'Cossack Squats': (15, 22.5, 30, 37.5),

    # Ganzkörper
    'Farmer\'s Walk': (30, 45, 60, 75),
    'Ruderergometer': None,  # Cardio

    # Keine Standards für:
    # - Körpergewicht-Übungen ohne Gewichte
    # - Cardio (Burpees, Jump Squats, High Knees, etc.)
    # - Planks (zeit-basiert)
    # - Mobility (Bird Dogs, Dead Bug, etc.)
}

def get_standards_for_exercise(bezeichnung):
    """
    Findet passende Standards für eine Übung basierend auf dem Namen.
    Gibt (beginner, intermediate, advanced, elite) zurück oder None.
    """
    # Direkte Matches
    if bezeichnung in standards_mapping:
        return standards_mapping[bezeichnung]

    # Pattern-Matches (z.B. "Fliegende (Kurzhantel, flach)" matched "Fliegende")
    for pattern, standards in standards_mapping.items():
        if pattern in bezeichnung:
            return standards

    return None

def should_have_standards(exercise):
    """
    Bestimmt, ob eine Übung 1RM Standards haben sollte.
    Keine Standards für: Cardio, Zeit-basiert, reines Körpergewicht ohne Zusatzgewicht
    """
    gewichts_typ = exercise.get('gewichts_typ', '')
    bewegungstyp = exercise.get('bewegungstyp', '')
    bezeichnung = exercise.get('bezeichnung', '')

    # Zeit-basierte Übungen
    if gewichts_typ == 'ZEIT':
        return False

    # Cardio-Übungen
    if bewegungstyp == 'CARDIO' or bewegungstyp == 'KOMPLEX':
        return False

    # Spezielle Ausschlüsse
    no_standards_keywords = [
        'Burpees', 'Jump Squats', 'High Knees', 'Mountain Climbers',
        'Plank', 'Dead Bug', 'Bird Dogs', 'Bear Crawls', 'Broad Jumps',
        'Liegestütze', 'Push-ups', 'Pike Push-ups',
        'Glute Bridge', 'Glute Kickbacks', 'Fire Hydrants', 'Clamshells',
        'Side-Lying Leg Raises', 'Standing Hip Abduction', 'Standing Knee Raises',
        'Lying Leg Raises', 'Hanging Leg Raises', 'Psoas Marches',
        'Crunch', 'Reverse Crunch', 'Cable Crunches', 'Band Crunches',
        'Hyperextensions', 'Superman Holds', 'Copenhagen Planks',
        'Inverted Rows', 'Pallof Press'
    ]

    for keyword in no_standards_keywords:
        if keyword in bezeichnung:
            return False

    # Körpergewicht-Übungen ohne Zusatzgewicht (außer Klimmzüge/Dips die schon gemappt sind)
    if gewichts_typ == 'KOERPERGEWICHT':
        if bezeichnung not in ['Klimmzüge (Obergriff)', 'Dips (Barren)']:
            return False

    return True

def add_standards_to_json():
    """Liest die JSON, fügt Standards hinzu, und schreibt sie zurück."""
    json_path = r'C:\Users\lerat\OneDrive\Projekt\App\Fitness\core\fixtures\initial_exercises.json'

    # JSON laden
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    exercises = data.get('exercises', [])

    # Zähler
    added_count = 0
    skipped_count = 0

    for exercise in exercises:
        bezeichnung = exercise.get('bezeichnung', '')

        # Prüfe ob Standards Sinn machen
        if not should_have_standards(exercise):
            print(f"[SKIP] {bezeichnung} (kein Gewicht/Cardio/Zeit)")
            skipped_count += 1
            continue

        # Hole Standards
        standards = get_standards_for_exercise(bezeichnung)

        if standards:
            exercise['standard_beginner'] = standards[0]
            exercise['standard_intermediate'] = standards[1]
            exercise['standard_advanced'] = standards[2]
            exercise['standard_elite'] = standards[3]
            print(f"[OK] {bezeichnung}: {standards}")
            added_count += 1
        else:
            print(f"[WARN] Keine Standards fuer: {bezeichnung}")
            skipped_count += 1

    # JSON schreiben
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[ZUSAMMENFASSUNG]")
    print(f"   Standards hinzugefuegt: {added_count}")
    print(f"   Uebersprungen: {skipped_count}")
    print(f"   Datei aktualisiert: {json_path}")

if __name__ == '__main__':
    add_standards_to_json()
