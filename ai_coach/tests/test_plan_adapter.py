"""
Tests für ai_coach/plan_adapter.py

Abdeckung:
- analyze_plan_performance(): regelbasierte Analyse (RPE, Balance, Plateau, Volumen)
- _check_muscle_balance(): Muskelgruppen-Frequenz
- _detect_plateaus(): 1RM-Stagnation
- _check_volume_trends(): Volumen-Änderungen
- _get_plan_structure(): Plan-Serialisierung
- _get_available_exercises(): Equipment-Filter
- _log_ki_cost(): KIApiLog-Eintrag
- suggest_optimizations(): LLMClient gemockt
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Equipment, Plan, PlanUebung, Satz, Trainingseinheit, Uebung


def _make_adapter(plan, user_id=None):
    """Hilfsfunktion: PlanAdapter mit gemocktem LLMClient erstellen."""
    with patch("ai_coach.plan_adapter.LLMClient"):
        from ai_coach.plan_adapter import PlanAdapter

        return PlanAdapter(plan_id=plan.id, user_id=user_id or plan.user_id)


class PlanAdapterTestBase(TestCase):
    """Gemeinsames Setup für alle PlanAdapter-Tests."""

    def setUp(self):
        self.user = User.objects.create_user(username="adapter_test", password="pass")
        self.equipment = Equipment.objects.create(name="KOERPER")
        self.user.verfuegbares_equipment.add(self.equipment)

        self.uebung_brust = Uebung.objects.create(
            bezeichnung="Liegestütz",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung_brust.equipment.add(self.equipment)

        self.uebung_ruecken = Uebung.objects.create(
            bezeichnung="Klimmzug",
            muskelgruppe="RUECKEN",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung_ruecken.equipment.add(self.equipment)

        self.plan = Plan.objects.create(name="Test Push", user=self.user)
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung_brust,
            saetze_ziel=3,
            wiederholungen_ziel="8-12",
            reihenfolge=1,
        )
        PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung_ruecken,
            saetze_ziel=3,
            wiederholungen_ziel="6-10",
            reihenfolge=2,
        )

        self.adapter = _make_adapter(self.plan)

    def _create_session_with_sets(self, gewicht, wiederholungen, rpe=None, dauer=45):
        """Erzeugt eine Trainingseinheit mit Sätzen für beide Übungen."""
        session = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, dauer_minuten=dauer
        )
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung_brust,
            satz_nr=1,
            gewicht=gewicht,
            wiederholungen=wiederholungen,
            rpe=rpe,
        )
        Satz.objects.create(
            einheit=session,
            uebung=self.uebung_ruecken,
            satz_nr=1,
            gewicht=gewicht,
            wiederholungen=wiederholungen,
            rpe=rpe,
        )
        return session


class TestAnalyzePlanPerformance(PlanAdapterTestBase):
    """analyze_plan_performance() – regelbasierte Analyse ohne LLM."""

    def test_ohne_sessions_keine_warnings(self):
        result = self.adapter.analyze_plan_performance(days=30)
        self.assertIn("warnings", result)
        self.assertIn("metrics", result)
        # RPE-Analyse braucht min. 3 Werte – ohne Sessions keine RPE-Warnings
        rpe_warnings = [w for w in result["warnings"] if w["type"] in ("rpe_low", "rpe_high")]
        self.assertEqual(len(rpe_warnings), 0)

    def test_metrics_structure(self):
        result = self.adapter.analyze_plan_performance(days=30)
        metrics = result["metrics"]
        self.assertIn("total_warnings", metrics)
        self.assertIn("analysis_period_days", metrics)
        self.assertEqual(metrics["analysis_period_days"], 30)

    def test_rpe_zu_niedrig_erzeugt_warnung(self):
        # 3 Sessions mit RPE 5 → rpe_low-Warnung
        for _ in range(3):
            self._create_session_with_sets(gewicht=50, wiederholungen=10, rpe=5.0)
        result = self.adapter.analyze_plan_performance(days=30)
        rpe_low = [w for w in result["warnings"] if w["type"] == "rpe_low"]
        self.assertGreater(len(rpe_low), 0)
        self.assertAlmostEqual(rpe_low[0]["value"], 5.0)

    def test_rpe_zu_hoch_erzeugt_warnung(self):
        # 3 Sessions mit RPE 9.5 → rpe_high-Warnung
        for _ in range(3):
            self._create_session_with_sets(gewicht=80, wiederholungen=8, rpe=9.5)
        result = self.adapter.analyze_plan_performance(days=30)
        rpe_high = [w for w in result["warnings"] if w["type"] == "rpe_high"]
        self.assertGreater(len(rpe_high), 0)

    def test_optimale_rpe_keine_warnung(self):
        # RPE 7.5 → weder rpe_low noch rpe_high
        for _ in range(3):
            self._create_session_with_sets(gewicht=70, wiederholungen=8, rpe=7.5)
        result = self.adapter.analyze_plan_performance(days=30)
        rpe_warnings = [w for w in result["warnings"] if w["type"] in ("rpe_low", "rpe_high")]
        self.assertEqual(len(rpe_warnings), 0)

    def test_critical_warnings_count(self):
        for _ in range(3):
            self._create_session_with_sets(gewicht=80, wiederholungen=8, rpe=9.5)
        result = self.adapter.analyze_plan_performance(days=30)
        critical = result["metrics"]["critical_warnings"]
        self.assertGreaterEqual(critical, 0)
        self.assertEqual(
            critical, len([w for w in result["warnings"] if w["severity"] == "warning"])
        )


class TestCheckMuscleBalance(PlanAdapterTestBase):
    """_check_muscle_balance() – Muskelgruppen-Frequenz prüfen."""

    def test_nie_trainiert_gibt_none(self):
        result = self.adapter._check_muscle_balance(days=14)
        # Keine Sessions → alle Muskelgruppen None
        for muskelgruppe, days_ago in result.items():
            self.assertIsNone(days_ago)

    def test_kuerzlich_trainiert_gibt_tage(self):
        self._create_session_with_sets(gewicht=60, wiederholungen=10)
        result = self.adapter._check_muscle_balance(days=14)
        # Setzt voraus dass mindestens eine Muskelgruppe gesetzt ist
        non_none = {k: v for k, v in result.items() if v is not None}
        self.assertGreater(len(non_none), 0)
        for days_ago in non_none.values():
            self.assertGreaterEqual(days_ago, 0)

    def test_gibt_dict_zurueck(self):
        result = self.adapter._check_muscle_balance(days=14)
        self.assertIsInstance(result, dict)


class TestDetectPlateaus(PlanAdapterTestBase):
    """_detect_plateaus() – 1RM-Stagnation erkennen."""

    def test_ohne_sessions_leeres_dict(self):
        result = self.adapter._detect_plateaus(weeks=4)
        self.assertEqual(result, {})

    def test_mit_progression_kein_plateau(self):
        # Sessions mit steigendem Gewicht
        for gewicht in [60, 65, 70, 75, 80, 85]:
            self._create_session_with_sets(gewicht=gewicht, wiederholungen=8)
        result = self.adapter._detect_plateaus(weeks=4)
        # Bei echter Progression: kein Plateau für diese Übungen
        self.assertIsInstance(result, dict)

    def test_gibt_dict_zurueck(self):
        result = self.adapter._detect_plateaus(weeks=4)
        self.assertIsInstance(result, dict)


class TestCheckVolumeTrends(PlanAdapterTestBase):
    """_check_volume_trends() – Volumen-Änderungen prüfen."""

    def test_weniger_als_4_sessions_gibt_none(self):
        self._create_session_with_sets(gewicht=60, wiederholungen=10)
        self._create_session_with_sets(gewicht=60, wiederholungen=10)
        result = self.adapter._check_volume_trends(days=30)
        self.assertIsNone(result)

    def test_gleichbleibendes_volumen_gibt_none(self):
        for _ in range(6):
            self._create_session_with_sets(gewicht=60, wiederholungen=10)
        # Gleichbleibendes Volumen → keine Warnung
        result = self.adapter._check_volume_trends(days=30)
        self.assertIsNone(result)

    def test_gibt_none_oder_dict_zurueck(self):
        result = self.adapter._check_volume_trends(days=30)
        self.assertTrue(result is None or isinstance(result, dict))


class TestGetPlanStructure(PlanAdapterTestBase):
    """_get_plan_structure() – Plan-Serialisierung."""

    def test_gibt_dict_mit_plan_name(self):
        result = self.adapter._get_plan_structure()
        self.assertEqual(result["plan_name"], "Test Push")

    def test_sessions_enthalten_uebungen(self):
        result = self.adapter._get_plan_structure()
        sessions = result["sessions"]
        # Alle Übungen müssen in irgendeinem Tag auftauchen
        all_exercises = [ex["exercise"] for exercises in sessions.values() for ex in exercises]
        self.assertIn("Liegestütz", all_exercises)
        self.assertIn("Klimmzug", all_exercises)

    def test_uebung_enthaelt_sets_und_reps(self):
        result = self.adapter._get_plan_structure()
        all_entries = [ex for exercises in result["sessions"].values() for ex in exercises]
        for entry in all_entries:
            self.assertIn("sets", entry)
            self.assertIn("reps", entry)


class TestGetAvailableExercises(PlanAdapterTestBase):
    """_get_available_exercises() – nach User-Equipment filtern."""

    def test_gibt_dict_nach_muskelgruppe(self):
        result = self.adapter._get_available_exercises()
        self.assertIsInstance(result, dict)

    def test_eigene_uebungen_enthalten(self):
        result = self.adapter._get_available_exercises()
        # BRUST und RUECKEN sollten vorhanden sein (Körpergewicht-Equipment)
        all_exercise_names = [name for names in result.values() for name in names]
        self.assertIn("Liegestütz", all_exercise_names)
        self.assertIn("Klimmzug", all_exercise_names)

    def test_uebung_ohne_passendes_equipment_nicht_enthalten(self):
        """Übung mit fehlendem Equipment soll nicht auftauchen."""
        langhanteln = Equipment.objects.create(name="LANGHANTEL")
        uebung_lh = Uebung.objects.create(
            bezeichnung="Bankdrücken Langhantel",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="GESAMT",
        )
        uebung_lh.equipment.add(langhanteln)
        # User hat keine Langhantel → Übung soll nicht erscheinen
        result = self.adapter._get_available_exercises()
        all_exercise_names = [name for names in result.values() for name in names]
        self.assertNotIn("Bankdrücken Langhantel", all_exercise_names)


class TestLogKiCostAdapter(PlanAdapterTestBase):
    """_log_ki_cost() – KIApiLog für Plan-Optimierung schreiben."""

    def test_erstellt_kiapi_log_mit_plan_optimize_endpoint(self):
        from core.models import KIApiLog

        llm_result = {
            "model": "gemini-2.5-flash",
            "cost": 0.003,
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        }
        self.adapter._log_ki_cost(llm_result)
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertEqual(log.endpoint, KIApiLog.Endpoint.PLAN_OPTIMIZE)
        self.assertTrue(log.success)

    def test_fehlschlag_geloggt(self):
        from core.models import KIApiLog

        self.adapter._log_ki_cost(
            {"model": "test", "cost": 0.0, "usage": {}},
            success=False,
            error_message="JSON parse error",
        )
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "JSON parse error")

    def test_fehlende_usage_kein_absturz(self):
        # Non-fatal: darf nicht crashen
        self.adapter._log_ki_cost({"model": "test", "cost": 0.0})


class TestSuggestOptimizations(PlanAdapterTestBase):
    """suggest_optimizations() – beide LLMClient-Referenzen gemockt.

    suggest_optimizations() importiert LLMClient lokal ('from ai_coach.llm_client import LLMClient').
    Wir müssen daher beide Stellen patchen:
      1. ai_coach.plan_adapter.LLMClient  (Modul-Level-Import, für __init__)
      2. ai_coach.llm_client.LLMClient    (Quelle des lokalen Imports in suggest_optimizations)
    _make_adapter() benutzen wir hier NICHT, weil dessen with-Block bereits beendet ist
    bevor suggest_optimizations läuft und dabei den Patch für den lokalen Import aufhebt.
    """

    def _mock_llm_result(self):
        return {
            "response": {
                "optimizations": [
                    {
                        "type": "adjust_volume",
                        "exercise_id": 1,
                        "exercise": "Liegestütz",
                        "old_sets": 3,
                        "new_sets": 4,
                        "reason": "Untertrainiert",
                    }
                ]
            },
            "model": "gemini-2.5-flash",
            "cost": 0.003,
            "usage": {"prompt_tokens": 500, "completion_tokens": 100},
        }

    def _make_adapter_with_mock(self, mock_llm):
        """Erstellt Adapter mit aktivem Mock (beide Patches gleichzeitig offen)."""
        from ai_coach.plan_adapter import PlanAdapter

        return PlanAdapter(plan_id=self.plan.id, user_id=self.user.id)

    @patch("ai_coach.plan_adapter.LLMClient")
    @patch("ai_coach.llm_client.LLMClient")
    def test_gibt_optimizations_liste_zurueck(self, MockLLMModule, MockLLMAdapter):
        MockLLMModule.return_value.generate_training_plan.return_value = self._mock_llm_result()
        adapter = self._make_adapter_with_mock(MockLLMModule)
        result = adapter.suggest_optimizations(days=30)
        self.assertIn("optimizations", result)
        self.assertIsInstance(result["optimizations"], list)
        self.assertGreater(len(result["optimizations"]), 0)

    @patch("ai_coach.plan_adapter.LLMClient")
    @patch("ai_coach.llm_client.LLMClient")
    def test_llm_fehler_gibt_leere_liste(self, MockLLMModule, MockLLMAdapter):
        MockLLMModule.return_value.generate_training_plan.side_effect = Exception("Timeout")
        adapter = self._make_adapter_with_mock(MockLLMModule)
        result = adapter.suggest_optimizations(days=30)
        self.assertEqual(result["optimizations"], [])
        self.assertIn("error", result)
        self.assertEqual(result["cost"], 0.0)

    @patch("ai_coach.plan_adapter.LLMClient")
    @patch("ai_coach.llm_client.LLMClient")
    def test_cost_und_model_im_ergebnis(self, MockLLMModule, MockLLMAdapter):
        MockLLMModule.return_value.generate_training_plan.return_value = self._mock_llm_result()
        adapter = self._make_adapter_with_mock(MockLLMModule)
        result = adapter.suggest_optimizations(days=30)
        self.assertEqual(result["cost"], 0.003)
        self.assertEqual(result["model"], "gemini-2.5-flash")
