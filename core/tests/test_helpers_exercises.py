"""
Tests für core/helpers/exercises.py
"""

from django.test import TestCase

from core.helpers.exercises import (
    _build_equipment_map,
    _find_bodyweight_fallback,
    _find_original_uebung,
    _find_substitute_by_priority,
    _get_available_equipment_objects,
    find_substitute_exercise,
)
from core.models import Equipment, Uebung


class ExerciseHelpersTestBase(TestCase):
    def setUp(self):
        self.eq_koerper = Equipment.objects.create(name="KOERPER")
        self.eq_hantel = Equipment.objects.create(name="HANTEL")
        self.eq_band = Equipment.objects.create(name="WIDERSTANDSBAND")

        self.uebung_brust = Uebung.objects.create(
            bezeichnung="Liegestütz",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung_brust.equipment.add(self.eq_koerper)

        self.uebung_brust_hantel = Uebung.objects.create(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        self.uebung_brust_hantel.equipment.add(self.eq_hantel)

        self.uebung_ruecken = Uebung.objects.create(
            bezeichnung="Klimmzüge",
            muskelgruppe="RUECKEN_LAT",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung_ruecken.equipment.add(self.eq_koerper)


class TestBuildEquipmentMap(ExerciseHelpersTestBase):
    def test_gibt_dict_zurueck(self):
        result = _build_equipment_map(Equipment.objects.all())
        self.assertIsInstance(result, dict)

    def test_schluessel_sind_lowercase(self):
        result = _build_equipment_map(Equipment.objects.all())
        for key in result:
            self.assertEqual(key, key.lower())

    def test_werte_sind_equipment_objekte(self):
        result = _build_equipment_map(Equipment.objects.all())
        for val in result.values():
            self.assertIsInstance(val, Equipment)

    def test_leere_liste_gibt_leeres_dict(self):
        result = _build_equipment_map([])
        self.assertEqual(result, {})


class TestGetAvailableEquipmentObjects(ExerciseHelpersTestBase):
    def test_gibt_equipment_objekte_fuer_namen(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        koerper_name = self.eq_koerper.get_name_display().strip().lower()
        result = _get_available_equipment_objects([koerper_name], eq_map)
        self.assertIn(self.eq_koerper, result)

    def test_unbekannter_name_wird_ignoriert(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        result = _get_available_equipment_objects(["GIBTS_NICHT"], eq_map)
        self.assertEqual(result, [])

    def test_leere_liste_gibt_leer(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        result = _get_available_equipment_objects([], eq_map)
        self.assertEqual(result, [])


class TestFindOriginalUebung(ExerciseHelpersTestBase):
    def test_exakter_match(self):
        result = _find_original_uebung("Liegestütz")
        self.assertIsNotNone(result)
        self.assertEqual(result.bezeichnung, "Liegestütz")

    def test_teilmatch(self):
        result = _find_original_uebung("Liegestütz (eng)")
        self.assertIsNotNone(result)
        self.assertEqual(result.bezeichnung, "Liegestütz")

    def test_keyword_mapping_bankdruecken(self):
        # Kein DB-Match, aber Keyword-Mapping greift
        result = _find_original_uebung("Bankdrücken flach")
        self.assertIsNotNone(result)
        self.assertEqual(result.muskelgruppe, "BRUST")

    def test_keyword_mapping_klimmzug(self):
        result = _find_original_uebung("Klimmzüge breit")
        # Exakter Teilmatch geht über DB; im Zweifel trotzdem nicht None
        self.assertIsNotNone(result)

    def test_unbekannte_uebung_gibt_none(self):
        result = _find_original_uebung("GIBTS_WIRKLICH_NICHT_IRGENDWIE")
        self.assertIsNone(result)


class TestFindSubstituteByPriority(ExerciseHelpersTestBase):
    def test_findet_uebung_gleiche_muskelgruppe(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        result = _find_substitute_by_priority(
            muscle_group="BRUST",
            movement_type="COMPOUND",
            original_id=self.uebung_brust_hantel.id,
            available_equipment_objects=[self.eq_koerper],
            equipment_map=eq_map,
        )
        self.assertIsNotNone(result)
        self.assertIn("name", result)

    def test_gibt_none_wenn_kein_equipment_verfuegbar(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        result = _find_substitute_by_priority(
            muscle_group="BRUST",
            movement_type="COMPOUND",
            original_id=-1,
            available_equipment_objects=[],
            equipment_map=eq_map,
        )
        self.assertIsNone(result)

    def test_schlie_original_aus(self):
        eq_map = _build_equipment_map(Equipment.objects.all())
        result = _find_substitute_by_priority(
            muscle_group="BRUST",
            movement_type="COMPOUND",
            original_id=self.uebung_brust.id,
            available_equipment_objects=[self.eq_koerper],
            equipment_map=eq_map,
        )
        # Liegestütz selbst darf nicht als Ersatz auftauchen
        if result:
            self.assertNotEqual(result["name"], "Liegestütz")


class TestFindBodyweightFallback(ExerciseHelpersTestBase):
    def test_findet_koerpergewicht_uebung(self):
        result = _find_bodyweight_fallback("BRUST", original_id=-1)
        self.assertIsNotNone(result)
        self.assertEqual(result["equipment"], "Nur Körpergewicht")

    def test_schlie_original_aus(self):
        result = _find_bodyweight_fallback("BRUST", original_id=self.uebung_brust.id)
        # Liegestütz darf nicht zurückkommen wenn es die Original-Übung ist
        if result:
            self.assertNotEqual(result["name"], "Liegestütz")

    def test_unbekannte_muskelgruppe_gibt_none(self):
        result = _find_bodyweight_fallback("GIBT_ES_NICHT", original_id=-1)
        self.assertIsNone(result)


class TestFindSubstituteExercise(ExerciseHelpersTestBase):
    def _koerper_display(self):
        return self.eq_koerper.get_name_display().strip().lower()

    def test_findet_ersatz_fuer_bekannte_uebung(self):
        result = find_substitute_exercise(
            original_name="Bankdrücken",
            required_equipment="Hantel",
            available_equipment=[self._koerper_display()],
        )
        self.assertIsInstance(result, dict)
        self.assertIn("name", result)

    def test_unbekannte_uebung_gibt_fallback_dict(self):
        result = find_substitute_exercise(
            original_name="GIBTS_WIRKLICH_NICHT",
            required_equipment="Hantel",
            available_equipment=[],
        )
        self.assertIsInstance(result, dict)
        self.assertIn("name", result)

    def test_ergebnis_hat_equipment_feld(self):
        result = find_substitute_exercise(
            original_name="Bankdrücken",
            required_equipment="Hantel",
            available_equipment=[self._koerper_display()],
        )
        self.assertIn("equipment", result)

    def test_kein_equipment_gibt_hinweis_zurueck(self):
        result = find_substitute_exercise(
            original_name="Kabelzug Brustübung XYZ",
            required_equipment="Kabelzug",
            available_equipment=[],
        )
        self.assertIn("name", result)
        # Irgendeine Antwort – kein Crash
        self.assertIsNotNone(result)
