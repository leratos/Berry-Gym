#!/usr/bin/env python3
"""
Script to update existing exercises in DB with standards from JSON
"""
import os
import django
import json

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Uebung

def update_exercises_from_json():
    """Lädt Standards aus JSON und aktualisiert existierende Übungen in der DB."""
    json_path = r'C:\Users\lerat\OneDrive\Projekt\App\Fitness\core\fixtures\initial_exercises.json'

    # JSON laden
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    exercises = data.get('exercises', [])

    updated_count = 0
    not_found_count = 0
    already_has_standards = 0

    for exercise_data in exercises:
        bezeichnung = exercise_data.get('bezeichnung')

        # Prüfe ob Standards in JSON vorhanden sind
        if 'standard_beginner' not in exercise_data:
            continue

        try:
            # Suche Übung in DB
            uebung = Uebung.objects.get(bezeichnung=bezeichnung)

            # Prüfe ob bereits Standards gesetzt sind
            if uebung.standard_beginner is not None:
                print(f"[EXISTS] {bezeichnung} hat bereits Standards")
                already_has_standards += 1
                continue

            # Setze Standards
            uebung.standard_beginner = exercise_data['standard_beginner']
            uebung.standard_intermediate = exercise_data['standard_intermediate']
            uebung.standard_advanced = exercise_data['standard_advanced']
            uebung.standard_elite = exercise_data['standard_elite']
            uebung.save()

            print(f"[UPDATE] {bezeichnung}: {uebung.standard_beginner}/{uebung.standard_intermediate}/{uebung.standard_advanced}/{uebung.standard_elite}")
            updated_count += 1

        except Uebung.DoesNotExist:
            print(f"[NOT FOUND] {bezeichnung} nicht in DB")
            not_found_count += 1

    print(f"\n[ZUSAMMENFASSUNG]")
    print(f"   Aktualisiert: {updated_count}")
    print(f"   Bereits Standards: {already_has_standards}")
    print(f"   Nicht gefunden: {not_found_count}")

if __name__ == '__main__':
    update_exercises_from_json()
