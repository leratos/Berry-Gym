"""
Phase 3.4 - Helper Function Tests
Testet: core/helpers/exercises.py -> find_substitute_exercise

Diese Tests sichern die Logik vor dem Complexity-Refactoring ab.
"""

import pytest

from core.models import Equipment, Uebung


def create_equipment(name):
    """Erstellt Equipment mit gültigem Choices-Namen."""
    eq, _ = Equipment.objects.get_or_create(name=name)
    return eq


def create_uebung(bezeichnung, muskelgruppe, equipment, bewegungstyp="COMPOUND"):
    """Erstellt eine Übung und setzt Equipment via M2M."""
    uebung = Uebung.objects.create(
        bezeichnung=bezeichnung,
        muskelgruppe=muskelgruppe,
        bewegungstyp=bewegungstyp,
        is_custom=False,
    )
    uebung.equipment.set([equipment])
    return uebung


@pytest.mark.django_db
class TestFindSubstituteExercise:
    """Tests für die find_substitute_exercise Hilfsfunktion."""

    def test_returns_fallback_when_no_exercises_exist(self):
        """Gibt Fallback zurück wenn keine passende Übung in DB vorhanden."""
        from core.helpers.exercises import find_substitute_exercise

        result = find_substitute_exercise(
            original_name="Bankdrücken",
            required_equipment="LANGHANTEL",
            available_equipment=["kurzhanteln"],
        )
        assert "name" in result
        assert "equipment" in result

    def test_finds_substitute_by_muscle_group(self):
        """Findet eine Ersatzübung basierend auf Muskelgruppe + verfügbarem Equipment.
        Equipment-Name: KURZHANTEL → Display "Kurzhanteln" → Lookup "kurzhanteln"
        """
        from core.helpers.exercises import find_substitute_exercise

        kurzhanteln = create_equipment("KURZHANTEL")
        langhantel = create_equipment("LANGHANTEL")

        create_uebung("Bankdrücken Langhantel", "BRUST", langhantel)
        create_uebung("Kurzhantel Fliegende", "BRUST", kurzhanteln)

        result = find_substitute_exercise(
            original_name="Bankdrücken Langhantel",
            required_equipment="LANGHANTEL",
            available_equipment=["kurzhanteln"],
        )

        assert result["name"] == "Kurzhantel Fliegende"

    def test_uses_keyword_mapping_for_unknown_exercise(self):
        """Nutzt Keyword-Mapping wenn Original-Übung nicht in DB ist.
        'curl' → BIZEPS Muskelgruppe via exercise_to_muscle dict
        """
        from core.helpers.exercises import find_substitute_exercise

        kurzhanteln = create_equipment("KURZHANTEL")
        create_uebung("KH Bizeps Curl", "BIZEPS", kurzhanteln)

        result = find_substitute_exercise(
            original_name="irgendein curl",
            required_equipment="LANGHANTEL",
            available_equipment=["kurzhanteln"],
        )

        assert result["name"] == "KH Bizeps Curl"

    def test_returns_bodyweight_as_last_resort(self):
        """Gibt Körpergewicht-Übung zurück wenn keine Equipment-Alternative gefunden.
        Equipment-Name: KOERPER → Display "Nur Körpergewicht"
        """
        from core.helpers.exercises import find_substitute_exercise

        koerper = create_equipment("KOERPER")
        create_uebung("Liegestütz", "BRUST", koerper)

        result = find_substitute_exercise(
            original_name="Bankdrücken",
            required_equipment="LANGHANTEL",
            available_equipment=[],  # Kein Equipment verfügbar → Bodyweight-Fallback
        )

        assert result["name"] == "Liegestütz"

    def test_does_not_return_original_as_substitute(self):
        """Die originale Übung wird nicht als Ersatz vorgeschlagen."""
        from core.helpers.exercises import find_substitute_exercise

        langhantel = create_equipment("LANGHANTEL")
        create_uebung("Bankdrücken Langhantel Original", "BRUST", langhantel)

        result = find_substitute_exercise(
            original_name="Bankdrücken Langhantel Original",
            required_equipment="LANGHANTEL",
            available_equipment=[],  # Kein alternatives Equipment
        )

        # Die Original-Übung darf nicht als Ersatz kommen
        assert result["name"] != "Bankdrücken Langhantel Original"

    def test_handles_exception_gracefully(self):
        """Bei einem internen Fehler gibt die Funktion einen sicheren Fallback zurück."""
        from core.helpers.exercises import find_substitute_exercise

        # Ungültiger equipment-Parameter (None-Liste) kann Exception auslösen
        result = find_substitute_exercise(
            original_name="",
            required_equipment="UNBEKANNT",
            available_equipment=[],
        )

        # Muss immer einen Dict zurückgeben, nie Exception werfen
        assert isinstance(result, dict)
        assert "name" in result
