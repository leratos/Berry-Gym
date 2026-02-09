"""Assign Equipment to Exercises on Production Server"""

import sys

sys.path.insert(0, "..")

from db_client import DatabaseClient

with DatabaseClient() as db:
    from core.models import Equipment, Uebung

    print("\n🔧 Assign Equipment to Exercises (Production)\n")

    # Keyword mapping
    equipment_keywords = {
        "LANGHANTEL": ["langhantel", "barbell", "squat", "kreuzheben", "deadlift"],
        "KURZHANTEL": ["kurzhantel", "dumbbell", "db"],
        "BANK": ["bank", "bench", "press"],
        "KLIMMZUG": ["klimmzug", "pull-up", "pullup", "chin"],
        "HANTELSCHEIBEN": [],  # Implizit bei Langhantel
    }

    # Special cases
    special_cases = {
        "Bankdrücken (Langhantel)": ["LANGHANTEL", "BANK"],
        "Schrägbankdrücken (Langhantel)": ["LANGHANTEL", "BANK"],
        "Kniebeuge (Langhantel, Back Squat)": ["LANGHANTEL"],
        "Kreuzheben (Langhantel, Conventional)": ["LANGHANTEL"],
        "Rumänisches Kreuzheben (RDL)": ["LANGHANTEL"],
    }

    uebungen = Uebung.objects.all()
    print(f"Übungen: {uebungen.count()}\n")

    for uebung in uebungen:
        equipment_names = []

        # Check special cases first
        if uebung.bezeichnung in special_cases:
            equipment_names = special_cases[uebung.bezeichnung]
        else:
            # Keyword matching
            bez_lower = uebung.bezeichnung.lower()

            for eq_name, keywords in equipment_keywords.items():
                if any(kw in bez_lower for kw in keywords):
                    equipment_names.append(eq_name)

        # Assign equipment
        if equipment_names:
            eq_objects = Equipment.objects.filter(name__in=equipment_names)
            uebung.equipment.set(eq_objects)
            print(f"✓ {uebung.bezeichnung}: {', '.join(equipment_names)}")
        else:
            # Kein Equipment = Körpergewicht
            print(f"  {uebung.bezeichnung}: (kein equipment)")

    print(f"\n✅ Equipment Assignment abgeschlossen!")
