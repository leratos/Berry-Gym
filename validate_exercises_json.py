#!/usr/bin/env python3
"""
Script to validate and fix initial_exercises.json
"""
import json
from collections import defaultdict


def validate_and_fix_json():
    """Validiert und korrigiert die exercises JSON."""
    json_path = r"C:\Users\lerat\OneDrive\Projekt\App\Fitness\core\fixtures\initial_exercises.json"

    # JSON laden
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data.get("exercises", [])

    print(f"[INFO] Validiere {len(exercises)} Uebungen...\n")

    errors = []
    warnings = []
    fixes = []

    # 1. Prüfe auf Duplikate (IDs und Namen)
    ids_seen = defaultdict(list)
    names_seen = defaultdict(list)

    for i, exercise in enumerate(exercises):
        ex_id = exercise.get("id")
        ex_name = exercise.get("bezeichnung", "")

        ids_seen[ex_id].append(i)
        names_seen[ex_name].append(i)

    # Duplikate IDs
    for ex_id, indices in ids_seen.items():
        if len(indices) > 1:
            errors.append(f"[FEHLER] Doppelte ID {ex_id} bei Indizes: {indices}")

    # Duplikate Namen
    for ex_name, indices in names_seen.items():
        if len(indices) > 1:
            errors.append(f"[FEHLER] Doppelter Name '{ex_name}' bei Indizes: {indices}")

    # 2. Prüfe erforderliche Felder
    required_fields = ["id", "bezeichnung", "muskelgruppe", "bewegungstyp", "gewichts_typ"]

    for i, exercise in enumerate(exercises):
        for field in required_fields:
            if field not in exercise:
                errors.append(
                    f"[FEHLER] Index {i} ({exercise.get('bezeichnung', 'UNBEKANNT')}): Fehlendes Feld '{field}'"
                )

        # Prüfe ob hilfsmuskeln ein Array ist
        if "hilfsmuskeln" in exercise and not isinstance(exercise["hilfsmuskeln"], list):
            errors.append(
                f"[FEHLER] Index {i} ({exercise.get('bezeichnung')}): 'hilfsmuskeln' ist kein Array"
            )
            exercise["hilfsmuskeln"] = []
            fixes.append(f"[FIX] Index {i}: 'hilfsmuskeln' zu leerem Array korrigiert")

        # Prüfe ob equipment ein Array ist
        if "equipment" in exercise and not isinstance(exercise["equipment"], list):
            errors.append(
                f"[FEHLER] Index {i} ({exercise.get('bezeichnung')}): 'equipment' ist kein Array"
            )
            exercise["equipment"] = []
            fixes.append(f"[FIX] Index {i}: 'equipment' zu leerem Array korrigiert")

    # 3. Prüfe Standards-Konsistenz
    for i, exercise in enumerate(exercises):
        bezeichnung = exercise.get("bezeichnung", "")
        gewichts_typ = exercise.get("gewichts_typ", "")

        has_standards = all(
            k in exercise
            for k in [
                "standard_beginner",
                "standard_intermediate",
                "standard_advanced",
                "standard_elite",
            ]
        )

        if has_standards:
            # Prüfe Reihenfolge: beginner <= intermediate <= advanced <= elite
            beg = exercise.get("standard_beginner")
            inter = exercise.get("standard_intermediate")
            adv = exercise.get("standard_advanced")
            elite = exercise.get("standard_elite")

            if not (beg <= inter <= adv <= elite):
                errors.append(
                    f"[FEHLER] Index {i} ({bezeichnung}): Standards nicht aufsteigend: {beg}/{inter}/{adv}/{elite}"
                )

            # Prüfe ob Standards bei Zeit/Cardio gesetzt sind (sollten sie nicht)
            if gewichts_typ in ["ZEIT", "KOERPERGEWICHT"]:
                bewegungstyp = exercise.get("bewegungstyp", "")
                if (
                    bewegungstyp in ["CARDIO", "KOMPLEX"]
                    or "Plank" in bezeichnung
                    or "Crunch" in bezeichnung
                ):
                    warnings.append(
                        f"[WARNUNG] Index {i} ({bezeichnung}): Hat Standards aber ist {gewichts_typ}/{bewegungstyp}"
                    )
        else:
            # Hat keine Standards - ist das OK?
            if gewichts_typ not in ["ZEIT", "KOERPERGEWICHT"]:
                # Sollte Standards haben
                if "Band" not in bezeichnung and "Latziehen (Widerstandsband)" not in bezeichnung:
                    warnings.append(
                        f"[WARNUNG] Index {i} ({bezeichnung}): Keine Standards aber hat Gewichte ({gewichts_typ})"
                    )

    # 4. Prüfe auf leere/ungültige Werte
    for i, exercise in enumerate(exercises):
        bezeichnung = exercise.get("bezeichnung", "")

        if not bezeichnung or bezeichnung.strip() == "":
            errors.append(f"[FEHLER] Index {i}: Leere Bezeichnung")

        if not exercise.get("beschreibung") or exercise.get("beschreibung", "").strip() == "":
            warnings.append(f"[WARNUNG] Index {i} ({bezeichnung}): Keine Beschreibung")

    # 5. Sortiere nach ID
    try:
        exercises_sorted = sorted(exercises, key=lambda x: x.get("id", 999999))
        if exercises != exercises_sorted:
            data["exercises"] = exercises_sorted
            fixes.append("[FIX] Uebungen nach ID sortiert")
    except Exception as e:
        errors.append(f"[FEHLER] Konnte nicht nach ID sortieren: {e}")

    # Ausgabe
    print("\n" + "=" * 60)
    print("VALIDIERUNGSERGEBNIS")
    print("=" * 60)

    if errors:
        print(f"\n[FEHLER] {len(errors)} Fehler gefunden:")
        for error in errors[:20]:  # Max 20 anzeigen
            print(f"  {error}")
        if len(errors) > 20:
            print(f"  ... und {len(errors)-20} weitere")
    else:
        print("\n[OK] Keine kritischen Fehler gefunden!")

    if warnings:
        print(f"\n[WARNUNG] {len(warnings)} Warnungen:")
        for warning in warnings[:20]:
            print(f"  {warning}")
        if len(warnings) > 20:
            print(f"  ... und {len(warnings)-20} weitere")

    if fixes:
        print(f"\n[FIX] {len(fixes)} Korrekturen vorgenommen:")
        for fix in fixes:
            print(f"  {fix}")

    # Wenn Fixes vorgenommen wurden, Datei neu schreiben
    if fixes and not errors:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n[GESPEICHERT] Datei mit Korrekturen gespeichert: {json_path}")
    elif errors:
        print(f"\n[NICHT GESPEICHERT] Wegen kritischen Fehlern nicht gespeichert!")
    else:
        print(f"\n[KEINE AENDERUNGEN] Datei ist bereits korrekt.")

    # Statistiken
    print("\n" + "=" * 60)
    print("STATISTIKEN")
    print("=" * 60)

    with_standards = sum(1 for ex in exercises if "standard_beginner" in ex)
    without_standards = len(exercises) - with_standards

    print(f"Gesamt Uebungen: {len(exercises)}")
    print(f"Mit Standards: {with_standards}")
    print(f"Ohne Standards: {without_standards}")

    # Gruppierung nach Typ
    by_type = defaultdict(int)
    for ex in exercises:
        by_type[ex.get("bewegungstyp", "UNBEKANNT")] += 1

    print(f"\nNach Bewegungstyp:")
    for typ, count in sorted(by_type.items()):
        print(f"  {typ}: {count}")

    return len(errors) == 0


if __name__ == "__main__":
    success = validate_and_fix_json()
    exit(0 if success else 1)
