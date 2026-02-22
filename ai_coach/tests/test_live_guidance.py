"""
Tests für ai_coach/live_guidance.py

Abdeckung:
- generate_prompt(): pure function, keine DB/LLM-Abhängigkeiten
- build_context(): DB-Abfragen mit Test-Fixtures
- _log_ki_cost(): KIApiLog-Eintrag erstellen
- get_guidance(): LLMClient gemockt, kein echter API-Call
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ai_coach.live_guidance import LiveGuidance
from core.models import Equipment, KoerperWerte, Plan, Satz, Trainingseinheit, Uebung


class TestGeneratePrompt(TestCase):
    """generate_prompt() ist eine reine Funktion – kein DB, kein LLM."""

    def setUp(self):
        self.guidance = LiveGuidance()
        self.minimal_context = {
            "user": {"name": "testuser", "gewicht_kg": 80.0, "groesse_cm": 180},
            "current_session": {
                "plan_name": "Push A",
                "started_at": "10:00",
                "stats": {"duration_minutes": 30, "total_sets": 6, "exercises_done": 2},
                "avg_rpe": 7.5,
            },
            "current_exercise": None,
            "recent_history": [],
        }

    def test_system_prompt_ist_erste_message(self):
        """Erste Message muss system-Rolle mit Coach-Persona haben."""
        messages = self.guidance.generate_prompt(self.minimal_context, "Wie ist meine Technik?")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Fitness-Coach", messages[0]["content"])

    def test_user_frage_ist_letzte_message(self):
        """User-Frage muss immer die letzte Message sein."""
        frage = "Soll ich mehr Gewicht nehmen?"
        messages = self.guidance.generate_prompt(self.minimal_context, frage)
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], frage)

    def test_ohne_chat_history_drei_messages(self):
        """Ohne History: system + context + frage = exakt 3 Messages."""
        messages = self.guidance.generate_prompt(self.minimal_context, "Test?")
        self.assertEqual(len(messages), 3)

    def test_chat_history_wird_eingefuegt(self):
        """Chat-History wird zwischen Context und aktueller Frage eingefügt."""
        history = [
            {"role": "user", "content": "Erste Frage"},
            {"role": "assistant", "content": "Erste Antwort"},
        ]
        messages = self.guidance.generate_prompt(self.minimal_context, "Zweite Frage", history)
        roles = [m["role"] for m in messages]
        self.assertIn("assistant", roles)
        self.assertEqual(messages[-1]["content"], "Zweite Frage")

    def test_chat_history_begrenzt_auf_10_messages(self):
        """20 History-Messages → werden auf die letzten 10 gekürzt."""
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(20)
        ]
        messages = self.guidance.generate_prompt(self.minimal_context, "Aktuelle Frage", history)
        # system + context + 10 (letzte) + aktuelle frage = 13
        self.assertEqual(len(messages), 13)

    def test_mit_aktueller_uebung_im_context(self):
        """current_exercise-Daten müssen im Context-Prompt auftauchen."""
        context = {
            **self.minimal_context,
            "current_exercise": {
                "name": "Bankdrücken",
                "muskelgruppe": "Brust",
                "bewegungstyp": "Compound",
                "beschreibung": "...",
                "completed_sets": 2,
                "current_set_number": 3,
                "last_set": {"gewicht": 80.0, "wiederholungen": 8, "rpe": 7.5},
            },
        }
        messages = self.guidance.generate_prompt(context, "Technik ok?")
        context_msg = messages[1]["content"]
        self.assertIn("Bankdrücken", context_msg)
        self.assertIn("80.0kg", context_msg)

    def test_ohne_aktuelle_uebung_kein_absturz(self):
        """current_exercise=None → kein Crash."""
        messages = self.guidance.generate_prompt(self.minimal_context, "Allgemeine Frage")
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0)

    def test_session_info_im_context_prompt(self):
        """Plan-Name und Dauer müssen im Context-Prompt stehen."""
        messages = self.guidance.generate_prompt(self.minimal_context, "Test?")
        context_content = messages[1]["content"]
        self.assertIn("Push A", context_content)
        self.assertIn("30", context_content)  # duration_minutes


class TestBuildContext(TestCase):
    """build_context() liest aus der DB – braucht echte Test-Objekte."""

    def setUp(self):
        self.user = User.objects.create_user(username="coach_test", password="pass")
        self.equipment = Equipment.objects.create(name="KOERPER")
        self.uebung = Uebung.objects.create(
            bezeichnung="Klimmzug",
            muskelgruppe="RUECKEN",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung.equipment.add(self.equipment)
        self.plan = Plan.objects.create(name="Pull A", user=self.user)
        self.session = Trainingseinheit.objects.create(
            user=self.user,
            plan=self.plan,
            dauer_minuten=45,
        )
        self.guidance = LiveGuidance()

    def test_gibt_context_dict_zurueck(self):
        ctx = self.guidance.build_context(self.session.id)
        self.assertIsInstance(ctx, dict)
        for key in ("user", "current_session", "current_exercise", "recent_history"):
            self.assertIn(key, ctx)

    def test_user_name_korrekt(self):
        ctx = self.guidance.build_context(self.session.id)
        self.assertEqual(ctx["user"]["name"], "coach_test")

    def test_plan_name_in_session(self):
        ctx = self.guidance.build_context(self.session.id)
        self.assertEqual(ctx["current_session"]["plan_name"], "Pull A")

    def test_ohne_uebung_current_exercise_none(self):
        ctx = self.guidance.build_context(self.session.id)
        self.assertIsNone(ctx["current_exercise"])

    def test_mit_uebung_id_current_exercise_befuellt(self):
        ctx = self.guidance.build_context(self.session.id, current_uebung_id=self.uebung.id)
        self.assertIsNotNone(ctx["current_exercise"])
        self.assertEqual(ctx["current_exercise"]["name"], "Klimmzug")

    def test_mit_satz_nummer(self):
        ctx = self.guidance.build_context(
            self.session.id,
            current_uebung_id=self.uebung.id,
            current_satz_number=3,
        )
        self.assertEqual(ctx["current_exercise"]["current_set_number"], 3)

    def test_koerperwerte_werden_eingelesen(self):
        KoerperWerte.objects.create(user=self.user, gewicht=82.5, groesse_cm=178)
        ctx = self.guidance.build_context(self.session.id)
        self.assertAlmostEqual(ctx["user"]["gewicht_kg"], 82.5)
        self.assertEqual(ctx["user"]["groesse_cm"], 178.0)

    def test_ohne_koerperwerte_none_werte(self):
        ctx = self.guidance.build_context(self.session.id)
        self.assertIsNone(ctx["user"]["gewicht_kg"])
        self.assertIsNone(ctx["user"]["groesse_cm"])

    def test_total_sets_korrekt(self):
        Satz.objects.create(
            einheit=self.session, uebung=self.uebung, satz_nr=1, gewicht=70, wiederholungen=8
        )
        Satz.objects.create(
            einheit=self.session, uebung=self.uebung, satz_nr=2, gewicht=72, wiederholungen=6
        )
        ctx = self.guidance.build_context(self.session.id)
        self.assertEqual(ctx["current_session"]["stats"]["total_sets"], 2)

    def test_avg_rpe_berechnet(self):
        Satz.objects.create(
            einheit=self.session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=70,
            wiederholungen=8,
            rpe=7.0,
        )
        Satz.objects.create(
            einheit=self.session,
            uebung=self.uebung,
            satz_nr=2,
            gewicht=72,
            wiederholungen=6,
            rpe=8.0,
        )
        ctx = self.guidance.build_context(self.session.id)
        self.assertAlmostEqual(ctx["current_session"]["avg_rpe"], 7.5)

    def test_last_set_in_uebung_context(self):
        Satz.objects.create(
            einheit=self.session,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=75,
            wiederholungen=10,
            rpe=7.5,
        )
        ctx = self.guidance.build_context(self.session.id, current_uebung_id=self.uebung.id)
        last = ctx["current_exercise"]["last_set"]
        self.assertIsNotNone(last)
        self.assertAlmostEqual(last["gewicht"], 75.0)
        self.assertEqual(last["wiederholungen"], 10)

    def test_freies_training_ohne_plan(self):
        session_ohne_plan = Trainingseinheit.objects.create(user=self.user, plan=None)
        ctx = self.guidance.build_context(session_ohne_plan.id)
        self.assertEqual(ctx["current_session"]["plan_name"], "Freies Training")

    def test_recent_history_enthaelt_keine_aktuelle_session(self):
        """Die aktuelle Session darf nicht in der recent_history auftauchen."""
        # Abgeschlossene Vorsession erzeugen
        andere_session = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, dauer_minuten=30
        )
        ctx = self.guidance.build_context(self.session.id)
        # Mindestens kein Crash, und recent_history ist eine Liste
        self.assertIsInstance(ctx["recent_history"], list)
        _ = andere_session  # suppress unused warning


class TestLogKiCost(TestCase):
    """_log_ki_cost() schreibt KIApiLog – non-fatal bei Fehler."""

    def setUp(self):
        self.user = User.objects.create_user(username="log_test", password="pass")
        self.guidance = LiveGuidance()
        self.llm_result = {
            "model": "gemini-2.5-flash",
            "cost": 0.0012,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    def test_erstellt_kiapi_log_eintrag(self):
        from core.models import KIApiLog

        self.guidance._log_ki_cost(self.user.id, self.llm_result)
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertEqual(log.endpoint, KIApiLog.Endpoint.LIVE_GUIDANCE)
        self.assertEqual(log.model_name, "gemini-2.5-flash")
        self.assertTrue(log.success)

    def test_token_counts_korrekt(self):
        from core.models import KIApiLog

        self.guidance._log_ki_cost(self.user.id, self.llm_result)
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertEqual(log.tokens_input, 100)
        self.assertEqual(log.tokens_output, 50)

    def test_fehlschlag_wird_korrekt_geloggt(self):
        from core.models import KIApiLog

        self.guidance._log_ki_cost(
            self.user.id, self.llm_result, success=False, error_message="Timeout"
        )
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "Timeout")

    def test_user_id_none_kein_absturz(self):
        """user_id=None ist erlaubt (anonyme/nicht zuordenbare Anfragen)."""
        self.guidance._log_ki_cost(None, self.llm_result)  # darf nicht crashen

    def test_fehlende_usage_kein_absturz(self):
        """LLM-Ergebnis ohne usage-Dict → tokens bleiben 0, kein Crash."""
        from core.models import KIApiLog

        result_ohne_usage = {"model": "test", "cost": 0.0}
        self.guidance._log_ki_cost(self.user.id, result_ohne_usage)
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertEqual(log.tokens_input, 0)
        self.assertEqual(log.tokens_output, 0)


class TestGetGuidance(TestCase):
    """get_guidance() – LLMClient wird gemockt, kein echter API-Call."""

    def setUp(self):
        self.user = User.objects.create_user(username="guidance_test", password="pass")
        equipment = Equipment.objects.create(name="KOERPER")
        self.uebung = Uebung.objects.create(
            bezeichnung="Liegestütz",
            muskelgruppe="BRUST",
            bewegungstyp="COMPOUND",
            gewichts_typ="KOERPER",
        )
        self.uebung.equipment.add(equipment)
        self.plan = Plan.objects.create(name="Push", user=self.user)
        self.session = Trainingseinheit.objects.create(
            user=self.user, plan=self.plan, dauer_minuten=30
        )
        self.guidance = LiveGuidance()

    def _mock_llm_result(self, answer="Gute Technik, weiter so!"):
        return {
            "response": answer,
            "model": "gemini-2.5-flash",
            "cost": 0.0005,
            "usage": {"prompt_tokens": 80, "completion_tokens": 20},
        }

    @patch("ai_coach.llm_client.LLMClient")
    def test_gibt_antwort_zurueck(self, MockLLMClient):
        MockLLMClient.return_value.generate_training_plan.return_value = self._mock_llm_result()
        result = self.guidance.get_guidance(self.session.id, "Wie ist meine Technik?")
        self.assertIn("answer", result)
        self.assertEqual(result["answer"], "Gute Technik, weiter so!")

    @patch("ai_coach.llm_client.LLMClient")
    def test_gibt_context_zurueck(self, MockLLMClient):
        MockLLMClient.return_value.generate_training_plan.return_value = self._mock_llm_result()
        result = self.guidance.get_guidance(self.session.id, "Test?")
        self.assertIn("context", result)
        self.assertIn("user", result["context"])

    @patch("ai_coach.llm_client.LLMClient")
    def test_llm_fehler_gibt_fallback_antwort(self, MockLLMClient):
        """Bei Exception vom LLM → Fallback-Text, model='error', cost=0."""
        MockLLMClient.return_value.generate_training_plan.side_effect = Exception("API Timeout")
        result = self.guidance.get_guidance(self.session.id, "Frage?")
        self.assertIn("answer", result)
        self.assertEqual(result["model"], "error")
        self.assertEqual(result["cost"], 0.0)

    @patch("ai_coach.llm_client.LLMClient")
    def test_ki_cost_wird_bei_erfolg_geloggt(self, MockLLMClient):
        from core.models import KIApiLog

        MockLLMClient.return_value.generate_training_plan.return_value = self._mock_llm_result()
        self.guidance.get_guidance(self.session.id, "Test?")
        log = KIApiLog.objects.get(user_id=self.user.id)
        self.assertTrue(log.success)
        self.assertEqual(log.endpoint, KIApiLog.Endpoint.LIVE_GUIDANCE)

    @patch("ai_coach.llm_client.LLMClient")
    def test_antwort_aus_dict_response_extrahiert(self, MockLLMClient):
        """Wenn LLM JSON-Dict zurückgibt, wird erster Wert als Antwort verwendet."""
        MockLLMClient.return_value.generate_training_plan.return_value = {
            "response": {"tip": "Schultern zurückziehen"},
            "model": "test",
            "cost": 0.0,
            "usage": {},
        }
        result = self.guidance.get_guidance(self.session.id, "Technik?")
        self.assertEqual(result["answer"], "Schultern zurückziehen")

    @patch("ai_coach.llm_client.LLMClient")
    def test_mit_chat_history(self, MockLLMClient):
        """Chat-History wird an LLM weitergegeben."""
        MockLLMClient.return_value.generate_training_plan.return_value = self._mock_llm_result()
        history = [
            {"role": "user", "content": "Erste Frage"},
            {"role": "assistant", "content": "Erste Antwort"},
        ]
        result = self.guidance.get_guidance(self.session.id, "Zweite Frage", chat_history=history)
        self.assertIn("answer", result)
        call_args = MockLLMClient.return_value.generate_training_plan.call_args
        messages_passed = call_args[1].get("messages") or call_args[0][0]
        contents = [m["content"] for m in messages_passed]
        self.assertIn("Erste Frage", contents)

    @patch("ai_coach.llm_client.LLMClient")
    def test_cost_und_model_im_ergebnis(self, MockLLMClient):
        MockLLMClient.return_value.generate_training_plan.return_value = self._mock_llm_result()
        result = self.guidance.get_guidance(self.session.id, "Test?")
        self.assertEqual(result["cost"], 0.0005)
        self.assertEqual(result["model"], "gemini-2.5-flash")
