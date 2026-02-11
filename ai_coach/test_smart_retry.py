"""
Test-Skript für Smart Retry Feature
Simuliert fehlerhafte Übungen ohne echte LLM-Generierung
KEIN Django/DB Setup nötig - isolierter Unit Test
"""

import json
import re
import sys
from pathlib import Path

# Füge ai_coach zum Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from llm_client import LLMClient


def create_dummy_plan_with_errors():
    """
    Erstellt einen Dummy-Plan mit absichtlich fehlerhaften Übungsnamen
    """
    return {
        "plan_name": "TEST Smart Retry Plan",
        "plan_description": "Dieser Plan enthält absichtlich fehlerhafte Übungen zum Testen",
        "sessions": [
            {
                "day_name": "Push Tag",
                "exercises": [
                    {
                        "exercise_name": "Bankdrücken (Langhantel)",  # ✅ Korrekt
                        "sets": 4,
                        "reps": "8-10",
                        "rpe_target": 8,
                        "order": 1,
                    },
                    {
                        "exercise_name": "Incline Dumbbell Press (Kurzhantel)",  # ❌ Fehler!
                        "sets": 3,
                        "reps": "10-12",
                        "rpe_target": 7,
                        "order": 2,
                    },
                    {
                        "exercise_name": "Cable Chest Fly (Kabelzug)",  # ❌ Fehler!
                        "sets": 3,
                        "reps": "12-15",
                        "rpe_target": 7,
                        "order": 3,
                    },
                ],
            },
            {
                "day_name": "Pull Tag",
                "exercises": [
                    {
                        "exercise_name": "Klimmzüge (breit)",  # ✅ Korrekt
                        "sets": 4,
                        "reps": "6-8",
                        "rpe_target": 9,
                        "order": 1,
                    },
                    {
                        "exercise_name": "Deadlifts (Langhantel)",  # ❌ Fehler!
                        "sets": 3,
                        "reps": "5",
                        "rpe_target": 9,
                        "order": 2,
                    },
                    {
                        "exercise_name": "Bicep Curls (Kurzhantel)",  # ❌ Fehler!
                        "sets": 3,
                        "reps": "10-12",
                        "rpe_target": 7,
                        "order": 3,
                    },
                ],
            },
            {
                "day_name": "Beine",
                "exercises": [
                    {
                        "exercise_name": "Kniebeugen (Langhantel)",  # ✅ Korrekt
                        "sets": 4,
                        "reps": "8-10",
                        "rpe_target": 8,
                        "order": 1,
                    },
                    {
                        "exercise_name": "Leg Press Machine",  # ❌ Fehler!
                        "sets": 3,
                        "reps": "12-15",
                        "rpe_target": 8,
                        "order": 2,
                    },
                    {
                        "exercise_name": "Standing Calf Raises (Körpergewicht)",  # ❌ Fehler!
                        "sets": 4,
                        "reps": "15-20",
                        "rpe_target": 7,
                        "order": 3,
                    },
                ],
            },
        ],
    }


def get_available_exercises() -> list:
    """
    Mock-Liste verfügbarer Übungen (aus echter DB, hardcoded für Test)
    """
    return [
        "Bankdrücken (Langhantel)",
        "Schrägbankdrücken (Langhantel)",
        "Schrägbankdrücken (Kurzhantel)",
        "Fliegende (Kurzhantel)",
        "Kabelzug Fliegende (Kabelzug)",
        "Klimmzüge (breit)",
        "Klimmzüge (eng)",
        "Latzug (breit)",
        "Rudern (Langhantel)",
        "Rudern (Kurzhantel)",
        "Kreuzheben (Langhantel)",
        "Kniebeugen (Langhantel)",
        "Beinpresse (Gerät)",
        "Ausfallschritte (Kurzhantel)",
        "Wadenheben (Kurzhantel)",
        "Seitheben (Kurzhantel)",
        "Seitheben (Kabelzug)",
        "Schulterdrücken (Langhantel)",
        "Schulterdrücken (Kurzhantel)",
        "Bizeps Curls (Kurzhantel)",
        "Bizeps Curls (Langhantel)",
        "Trizeps Dips (Körpergewicht)",
        "Trizepsdrücken (Kabelzug)",
        "Face Pulls (Kabelzug)",
        "Bulgarian Split Squats (Kurzhantel)",
    ]


def fix_invalid_exercises(plan_json, errors, available_exercises, llm_client):
    """
    Kopie der _fix_invalid_exercises() Methode aus plan_generator.py
    Ersetzt fehlerhafte Übungen durch LLM-Vorschläge
    """
    print("\n🔄 Smart Retry: Korrigiere fehlerhafte Übungen...")
    print("-" * 60)

    # Extrahiere fehlerhafte Übungen aus Errors
    invalid_exercises = []
    for error in errors:
        match = re.search(r"'([^']+)' nicht verfügbar", error)
        if match:
            invalid_exercises.append(match.group(1))

    if not invalid_exercises:
        print("⚠️ Keine fehlerhaften Übungen gefunden")
        return plan_json

    print(f"🔍 Gefundene fehlerhafte Übungen: {len(invalid_exercises)}")
    for ex in invalid_exercises:
        print(f"   ❌ {ex}")

    # Erstelle Korrektur-Prompt
    correction_prompt = f"""Die folgenden Übungen sind nicht verfügbar und müssen ersetzt werden:
{chr(10).join(f'- {ex}' for ex in invalid_exercises)}

Verfügbare Übungen:
{chr(10).join(f'- {ex}' for ex in available_exercises)}

Wähle für jede fehlerhafte Übung eine passende Ersatzübung aus der verfügbaren Liste.
Berücksichtige dabei:
- Gleiche Muskelgruppe
- Ähnliche Bewegung
- Gleiches oder kompatibles Equipment

Antworte NUR mit einem JSON-Objekt im Format:
{{
    "Fehlerhafte Übung 1": "Ersatzübung 1",
    "Fehlerhafte Übung 2": "Ersatzübung 2"
}}

WICHTIG: Nutze EXAKT die Übungsnamen aus der verfügbaren Liste (mit Equipment in Klammern)!
"""

    messages = [
        {
            "role": "system",
            "content": "Du bist ein Fitness-Experte. Antworte nur mit validem JSON.",
        },
        {"role": "user", "content": correction_prompt},
    ]

    print("\n📤 Sende Korrektur-Anfrage an LLM...")

    try:
        # LLM Call für Korrektur (mit Ollama oder OpenRouter)
        if hasattr(llm_client, "_generate_with_openrouter") and llm_client.use_openrouter:
            response = llm_client._generate_with_openrouter(messages, max_tokens=500)
        else:
            # Fallback zu lokalem Ollama
            response = llm_client._generate_with_ollama(messages, max_tokens=500, timeout=60)
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        return plan_json

    print(f"🔍 Response-Typ: {type(response)}")

    # Parse Response (Ollama gibt Dict, OpenRouter String)
    if isinstance(response, dict):
        replacements = response
        print(f"✓ Ersetzungen erhalten (direkt als Dict): {len(replacements)}")
    else:
        try:
            replacements = json.loads(response)
            print(f"✓ Ersetzungen erhalten (geparst aus String): {len(replacements)}")
        except json.JSONDecodeError as e:
            print(f"❌ Fehler beim Parsen der LLM-Antwort: {e}")
            print(f"Raw Response: {response[:500]}")
            return plan_json

    # Zeige Ersetzungen
    for old, new in replacements.items():
        print(f"   {old} → {new}")

    # Ersetze in Plan
    replaced_count = 0
    for session in plan_json["sessions"]:
        for exercise in session["exercises"]:
            exercise_name = exercise["exercise_name"]

            # Prüfe Ersetzungen
            for old, new in replacements.items():
                # Versuche teilweise Übereinstimmung (ohne Klammern)
                exercise_base = exercise_name.split("(")[0].strip()
                old_base = old.split("(")[0].strip()

                if exercise_base == old_base or exercise_name == old:
                    exercise["exercise_name"] = new
                    replaced_count += 1
                    print(f"✓ Ersetzt (partial match): {exercise_name} → {new}")
                    break

    print(f"\n✅ {replaced_count} Übungen korrigiert")
    return plan_json


def test_smart_retry(use_openrouter: bool = False):
    """
    Testet das Smart Retry Feature (OHNE DB-Verbindung)

    Args:
        use_openrouter: True = OpenRouter (kostet Geld), False = Ollama (lokal)
    """
    print("=" * 60)
    print("🧪 SMART RETRY TEST (Standalone)")
    print("=" * 60)
    print(f"LLM: {'OpenRouter (70B)' if use_openrouter else 'Ollama (8B)'}")
    print("=" * 60)

    # 1. Dummy-Plan mit Fehlern erstellen
    print("\n📋 SCHRITT 1: Erstelle Dummy-Plan mit Fehlern")
    print("-" * 60)
    plan_json = create_dummy_plan_with_errors()

    # Fehler zählen
    all_exercises = []
    for session in plan_json["sessions"]:
        for ex in session["exercises"]:
            all_exercises.append(ex["exercise_name"])

    print(f"✓ Plan erstellt: {plan_json['plan_name']}")
    print(f"✓ Sessions: {len(plan_json['sessions'])}")
    print(f"✓ Gesamt Übungen: {len(all_exercises)}")

    # 2. Verfügbare Übungen holen (Mock-Daten)
    print("\n📚 SCHRITT 2: Verfügbare Übungen laden (Mock-Daten)")
    print("-" * 60)
    available_exercises = get_available_exercises()
    print(f"✓ {len(available_exercises)} Übungen verfügbar")

    # 3. Validation (sollte Fehler finden)
    print("\n❌ SCHRITT 3: Initiale Validation (sollte Fehler finden)")
    print("-" * 60)

    llm_client = LLMClient(use_openrouter=use_openrouter, fallback_to_openrouter=False)
    valid, errors = llm_client.validate_plan(plan_json, available_exercises)

    if not valid:
        print(f"⚠️ {len(errors)} Fehler gefunden:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ Keine Fehler gefunden (Test fehlgeschlagen - Plan sollte Fehler haben!)")
        return

    # 4. Smart Retry
    print("\n🔄 SCHRITT 4: Smart Retry ausführen")
    print("-" * 60)

    corrected_plan = fix_invalid_exercises(
        plan_json=plan_json,
        errors=errors,
        available_exercises=available_exercises,
        llm_client=llm_client,
    )

    # 5. Re-Validation
    print("\n✅ SCHRITT 5: Re-Validation nach Korrektur")
    print("-" * 60)

    valid_after, errors_after = llm_client.validate_plan(corrected_plan, available_exercises)

    if valid_after:
        print("✅ ERFOLG! Plan ist jetzt valide!")
        print("\n📊 Zusammenfassung:")
        print(f"   Fehler vorher: {len(errors)}")
        print(f"   Fehler nachher: {len(errors_after)}")
        print(f"   Status: ✅ BESTANDEN")
    else:
        print(f"⚠️ {len(errors_after)} Fehler verblieben:")
        for error in errors_after:
            print(f"   - {error}")
        print(f"\n📊 Zusammenfassung:")
        print(f"   Fehler vorher: {len(errors)}")
        print(f"   Fehler nachher: {len(errors_after)}")
        print(f"   Status: ⚠️ TEILWEISE ERFOLGREICH")

    print("\n" + "=" * 60)
    print("🧪 TEST ABGESCHLOSSEN")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Smart Retry Feature")
    parser.add_argument(
        "--use-openrouter", action="store_true", help="Nutze OpenRouter (kostet Geld!)"
    )

    args = parser.parse_args()

    # Warnung bei OpenRouter
    if args.use_openrouter:
        print("\n⚠️ WARNUNG: Du nutzt OpenRouter - das kostet ~0.0005€ pro Korrektur!")
        response = input("Fortfahren? (y/n): ")
        if response.lower() != "y":
            print("Abgebrochen.")
            sys.exit(0)

    test_smart_retry(use_openrouter=args.use_openrouter)
