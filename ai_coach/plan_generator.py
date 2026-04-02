"""
Plan Generator - Hauptskript für AI Coach
Kombiniert: Data Analyzer → Prompt Builder → LLM → Django Plan Persistierung
"""

import argparse
import json
import sys
from typing import Dict, List

from .data_analyzer import TrainingAnalyzer
from .db_client import DatabaseClient
from .llm_client import LLMClient
from .prompt_builder import PromptBuilder

# ─────────────────────────────────────────────────────────────────────────────
# Helfer: DB-Konstanten → lesbare Muskelgruppen-Namen
# ─────────────────────────────────────────────────────────────────────────────

_MUSKELGRUPPE_LABELS: dict[str, str] = {
    "BRUST": "Brust",
    "RUECKEN_LAT": "Lat",
    "RUECKEN_TRAPEZ": "Trapez",
    "RUECKEN_UNTEN": "Unterer Rücken",
    "RUECKEN_OBERER": "Oberer Rücken",
    "SCHULTER_VORN": "Vordere Schulter",
    "SCHULTER_SEIT": "Seitliche Schulter",
    "SCHULTER_HINT": "Hintere Schulter",
    "BIZEPS": "Bizeps",
    "TRIZEPS": "Trizeps",
    "BAUCH": "Bauch",
    "BEINE_QUAD": "Quadrizeps",
    "BEINE_HAM": "Hamstrings",
    "PO": "Gesäß",
    "WADEN": "Waden",
    "UNTERARME": "Unterarme",
    "ADDUKTOREN": "Adduktoren",
    "ABDUKTOREN": "Abduktoren",
    "HUEFTBEUGER": "Hüftbeuger",
}


def _humanize_muskelgruppe(label: str) -> str:
    """Wandelt DB-Konstante in lesbaren Namen: 'SCHULTER_HINT' → 'Hintere Schulter'."""
    return _MUSKELGRUPPE_LABELS.get(label, label)


def _humanize_plan_name(name: str) -> str:
    """Ersetzt DB-Konstanten im Plan-Namen durch Klartext.

    'Fokus BAUCH_HUEFTBEUGER_SCHULTER_HINT' → 'Fokus Bauch, Hüftbeuger, Hintere Schulter'
    """
    import re

    for const, human in _MUSKELGRUPPE_LABELS.items():
        # Ersetze alleinstehende Konstanten (mit Wort-/Unterstrich-Grenzen)
        name = re.sub(rf"(?<![A-Za-z]){const}(?![A-Za-z])", human, name)

    # Unterstriche zwischen Klartext-Wörtern durch Komma+Leerzeichen ersetzen
    # z.B. "Bauch_Hüftbeuger_Hintere Schulter" → "Bauch, Hüftbeuger, Hintere Schulter"
    name = re.sub(r"(?<=[a-zäöüß])_(?=[A-ZÄÖÜ])", ", ", name)

    return name


class PlanGenerator:
    """
    Generiert personalisierte Trainingspläne mit AI
    """

    def __init__(
        self,
        user_id: int,
        analysis_days: int = 30,
        plan_type: str = "3er-split",
        llm_temperature: float = 0.3,
        sets_per_session: int = 18,
        periodization: str = "linear",
        target_profile: str = "hypertrophie",
        use_openrouter: bool = False,
        fallback_to_openrouter: bool = True,
        progress_callback=None,
        duration_weeks: int = 12,
    ):
        """
        Args:
            user_id: Django User ID
            analysis_days: Wie viele Tage zurück analysieren
            plan_type: Art des Plans (3er-split, ppl, upper-lower, fullbody)
            llm_temperature: LLM Kreativität (0.0-1.0, Default 0.3 für zuverlässiges JSON)
            sets_per_session: Ziel-Satzanzahl pro Trainingstag (18 = ca. 1h)
            periodization: Periodisierungsmodell (linear, wellenfoermig, block)
            target_profile: Zielprofil (kraft, hypertrophie, definition)
            use_openrouter: True = nutze nur OpenRouter (skip Ollama)
            fallback_to_openrouter: True = Fallback zu OpenRouter bei Ollama-Fehler
            progress_callback: Optional callable(percent: int, step: str) für SSE-Streaming
            duration_weeks: Plandauer in Wochen (4-16, Default 12)
        """
        self.user_id = user_id
        self.analysis_days = analysis_days
        self.plan_type = plan_type
        self.llm_temperature = llm_temperature
        self.sets_per_session = sets_per_session
        self.periodization = periodization
        self.target_profile = target_profile
        self.use_openrouter = use_openrouter
        self.fallback_to_openrouter = fallback_to_openrouter
        self._progress_callback = progress_callback
        self.duration_weeks = duration_weeks

    def _progress(self, percent: int, step: str) -> None:
        """Sendet Fortschrittsupdate – no-op wenn kein Callback gesetzt."""
        if self._progress_callback:
            self._progress_callback(percent, step)

    def _log_ki_cost(
        self,
        llm_result: dict,
        *,
        is_retry: bool = False,
        success: bool = True,
        error_message: str = "",
    ) -> None:
        """Schreibt einen KIApiLog-Eintrag für einen LLM-Call.

        Läuft im Django-Web-Kontext – wird still ignoriert wenn DB nicht
        verfügbar ist (CLI-Modus ohne Django-Setup).
        """
        try:
            from core.models import KIApiLog

            usage = llm_result.get("usage", {})
            KIApiLog.objects.create(
                user_id=self.user_id,
                endpoint=KIApiLog.Endpoint.PLAN_GENERATE,
                model_name=llm_result.get("model", ""),
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                cost_eur=llm_result.get("cost", 0.0),
                success=success,
                is_retry=is_retry,
                error_message=error_message,
            )
        except Exception as e:
            # Logging-Fehler dürfen nie den Plan-Generierungs-Flow unterbrechen
            print(f"   ⚠️ KI-Cost-Logging fehlgeschlagen (non-fatal): {e}")

    def _get_max_tokens(self) -> int:
        """
        Gibt plan-typ-spezifisches max_tokens zurück.

        Grundlage: ~700 Tokens pro Session (Übungen + Metadaten) +
        ~500 Tokens für Makrozyklus/Periodisierungs-Header.
        Puffer: +20% für Varianz in Übungsanzahl und Notizen.

        Hardcodiertes 4000 für alle Typen war falsch:
        - 2er-Split: ~1400 Tokens → 4000 verschwendet Geld
        - PPL (6 Sessions): ~4700 Tokens → 4000 schneidet den Plan ab
        """
        token_map = {
            "ganzkörper": 2000,  # 2-3 Sessions × ~500 + Header
            "2er-split": 2200,  # 2 Sessions × ~700 + Header
            "upper-lower": 2200,  # Alias für 2er-Split
            "3er-split": 3000,  # 3 Sessions × ~700 + Header
            "4er-split": 3800,  # 4 Sessions × ~700 + Header
            "ppl": 4500,  # bis 6 Sessions × ~650 + Header
            "push-pull-legs": 4500,  # Alias für ppl
        }
        return token_map.get(self.plan_type, 3500)

    def generate(self, save_to_db: bool = True) -> dict:
        """
        Generiert Trainingsplan und speichert in Django DB

        Args:
            save_to_db: Wenn True, speichert Plan in DB

        Returns:
            Dict mit plan_id, plan_data, analysis_data
        """

        print("=" * 60)
        print("🏋️ AI COACH - Trainingsplan Generierung")
        print("=" * 60)
        print(f"User ID: {self.user_id}")
        print(f"Plan Type: {self.plan_type}")
        print(f"Analyse: Letzte {self.analysis_days} Tage")
        print("=" * 60)

        try:
            # Prüfe ob Django bereits läuft (Web-Kontext)
            # Wenn ja, brauchen wir keinen DatabaseClient
            django_is_running = "django" in sys.modules and hasattr(sys.modules["django"], "apps")

            if django_is_running:
                # Django läuft bereits (Web-Kontext) - kein DB-Client nötig
                print("\n💡 Django-Kontext erkannt - nutze existierende DB-Verbindung")
                return self._generate_with_existing_django(save_to_db)
            else:
                # CLI-Modus - braucht DatabaseClient mit SSH-Tunnel
                print("\n💡 CLI-Modus - starte SSH-Tunnel")
                with DatabaseClient():
                    return self._generate_with_existing_django(save_to_db)

        except Exception as e:
            print(f"\n❌ FEHLER bei Plan-Generierung: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _generate_with_existing_django(self, save_to_db: bool) -> dict:
        """
        Generiert Plan mit vorhandener Django-Verbindung
        """
        # 1. Trainingshistorie analysieren
        print("\n📊 SCHRITT 1: Trainingshistorie analysieren")
        print("-" * 60)
        self._progress(5, "Analysiere Trainingsdaten...")

        analyzer = TrainingAnalyzer(user_id=self.user_id, days=self.analysis_days)
        analysis_data = analyzer.analyze()
        analyzer.print_summary()

        # 2. Verfügbare Übungen ermitteln (Equipment-Filter)
        print("\n🔧 SCHRITT 2: Verfügbare Übungen ermitteln")
        print("-" * 60)

        builder = PromptBuilder()
        available_exercises = builder.get_available_exercises_for_user(self.user_id)

        print(f"✓ {len(available_exercises)} Übungen mit verfügbarem Equipment")

        if len(available_exercises) < 10:
            print("\n⚠️ WARNUNG: Zu wenig Übungen verfügbar!")
            print("   Der User sollte mehr Equipment auswählen.")
            print("   Mindestens 15-20 Übungen empfohlen für gute Pläne.")

        # 3. Prompts erstellen
        print("\n🤖 SCHRITT 3: LLM Prompts erstellen")
        print("-" * 60)
        self._progress(20, "Erstelle personalisierten Prompt...")

        messages = builder.build_messages(
            analysis_data=analysis_data,
            available_exercises=available_exercises,
            plan_type=self.plan_type,
            sets_per_session=self.sets_per_session,
            target_profile=self.target_profile,
            periodization=self.periodization,
            duration_weeks=self.duration_weeks,
        )

        print(f"✓ System Prompt: {len(messages[0]['content'])} Zeichen")
        print(f"✓ User Prompt: {len(messages[1]['content'])} Zeichen")

        # 4. LLM Call - Trainingsplan generieren
        print("\n🧠 SCHRITT 4: Trainingsplan mit Llama generieren")
        print("-" * 60)
        self._progress(35, "KI generiert Plan (kann 15–20s dauern)...")

        llm_client = LLMClient(
            temperature=self.llm_temperature,
            use_openrouter=self.use_openrouter,
            fallback_to_openrouter=self.fallback_to_openrouter,
        )
        llm_result = llm_client.generate_training_plan(
            messages=messages, max_tokens=self._get_max_tokens(), timeout=120
        )
        self._log_ki_cost(llm_result)

        # Extrahiere JSON aus Result-Dict
        plan_json = llm_result.get("response") if isinstance(llm_result, dict) else llm_result

        # Debug: Prüfe was wir bekommen haben
        if not plan_json:
            print("\n❌ LLM hat leere Response geliefert!")
            print(f"   llm_result Typ: {type(llm_result)}")
            if isinstance(llm_result, dict):
                print(f"   llm_result Keys: {llm_result.keys()}")
            return {
                "success": False,
                "errors": ["LLM Response war leer - bitte erneut versuchen"],
                "plan_data": None,
                "analysis_data": analysis_data,
            }

        print(
            f"   ✓ Plan JSON erhalten mit Keys: {list(plan_json.keys()) if isinstance(plan_json, dict) else 'KEIN DICT!'}"
        )

        # Prüfe ob Schema komplett falsch ist (Ollama 8B Problem)
        required_keys = {"plan_name", "sessions"}
        actual_keys = set(plan_json.keys()) if isinstance(plan_json, dict) else set()

        if not required_keys.intersection(actual_keys):
            print(f"\n⚠️ Schema komplett falsch! Erwartet: {required_keys}, Erhalten: {actual_keys}")

            # Wenn Fallback erlaubt → OpenRouter versuchen
            if self.fallback_to_openrouter and not self.use_openrouter:
                print("→ Versuche OpenRouter (größeres Modell folgt Schema besser)...")

                # Neuen LLM Client mit OpenRouter erstellen
                llm_client_or = LLMClient(
                    temperature=self.llm_temperature,
                    use_openrouter=True,
                    fallback_to_openrouter=False,
                )
                llm_result = llm_client_or.generate_training_plan(
                    messages=messages, max_tokens=self._get_max_tokens(), timeout=120
                )
                self._log_ki_cost(llm_result)
                plan_json = (
                    llm_result.get("response") if isinstance(llm_result, dict) else llm_result
                )
                print(
                    f"   ✓ OpenRouter Plan JSON mit Keys: {list(plan_json.keys()) if isinstance(plan_json, dict) else 'KEIN DICT!'}"
                )

        plan_json = self._ensure_periodization_metadata(plan_json)

        # 5. Validierung mit Smart Retry
        print("\n✅ SCHRITT 5: Plan validieren")
        print("-" * 60)
        self._progress(70, "Antwort erhalten – validiere Plan...")

        valid, errors = llm_client.validate_plan(plan_json, available_exercises)

        if not valid:
            print(f"⚠️ Plan Validation: {len(errors)} Fehler gefunden")
            for error in errors:
                print(f"   - {error}")

            # Smart Retry: Fehlerhafte Übungen durch LLM ersetzen lassen
            print("\n🔄 SCHRITT 5b: Fehlerhafte Übungen korrigieren (Smart Retry)")
            print("-" * 60)
            self._progress(82, "Korrigiere halluzinierte Übungen...")

            plan_json = self._fix_invalid_exercises(
                plan_json=plan_json,
                errors=errors,
                available_exercises=available_exercises,
                llm_client=llm_client,
            )

            # Stelle sicher, dass Periodisierungs-Metadaten nach der Korrektur noch vorhanden sind
            plan_json = self._ensure_periodization_metadata(plan_json)

            # Nochmal validieren
            print("\n✅ Re-Validierung nach Korrektur")
            print("-" * 60)
            valid, errors = llm_client.validate_plan(plan_json, available_exercises)

        if not valid:
            print("\n⚠️ Plan hat Validierungsfehler:")
            for error in errors:
                print(f"   - {error}")
            print("\n   Plan wird NICHT gespeichert!")
            return {
                "success": False,
                "errors": errors,
                "plan_data": plan_json,
                "analysis_data": analysis_data,
            }

        # 5b. Erweiterte Planstruktur-Validierung (Phase 11)
        print("\n🔍 SCHRITT 5b: Erweiterte Plan-Validierung")
        print("-" * 60)
        self._progress(75, "Validiere Planstruktur erweitert...")

        from ai_coach.plan_validator import validate_plan_structure

        structure_warnings, structure_fixes = validate_plan_structure(
            plan_json, available_exercises
        )
        if structure_fixes.get("order_fixed", 0) > 0:
            print(
                f"   🔧 Übungsreihenfolge korrigiert in "
                f"{structure_fixes['order_fixed']} Sessions"
            )
        if structure_fixes.get("rest_fixed", 0) > 0:
            print(f"   🔧 Pausenzeiten korrigiert bei " f"{structure_fixes['rest_fixed']} Übungen")
        if structure_fixes.get("overrep_fixed", 0) > 0:
            print(
                f"   🔧 Überrepräsentation korrigiert in "
                f"{structure_fixes['overrep_fixed']} Sessions"
            )
        if structure_warnings:
            for w in structure_warnings:
                print(f"   ⚠️ {w}")
        if not structure_warnings and not structure_fixes:
            print("   ✓ Planstruktur OK")

        # 5c. Schwachstellen-Coverage prüfen + Auto-Fix
        print("\n🎯 SCHRITT 5c: Schwachstellen-Coverage prüfen")
        print("-" * 60)
        coverage_warnings = self._validate_weakness_coverage(
            plan_json, analysis_data.get("weaknesses", []), available_exercises
        )
        if coverage_warnings:
            print(f"   ⚠️ {len(coverage_warnings)} nicht abgedeckte Schwachstellen:")
            for w in coverage_warnings:
                print(f"      {w}")
        else:
            print("   ✓ Alle Schwachstellen im Plan abgedeckt")

        # 5d. Plan-Namen Fallback: generische Namen mit Datum ergänzen
        raw_name = plan_json.get("plan_name", "").strip()
        generic_names = {
            "mein trainingsplan",
            "trainingsplan",
            "3er split",
            "3er-split",
            "push pull legs",
            "push/pull/legs",
            "hypertrophie plan",
            "kraftplan",
        }
        if not raw_name or raw_name.lower() in generic_names or len(raw_name) < 10:
            from datetime import date as _date

            # Schwachstellen für Namen (alle "Untertrainiert"-Einträge)
            weaknesses = analysis_data.get("weaknesses", [])
            focus_labels = [
                _humanize_muskelgruppe(w.split(":")[0].strip())
                for w in weaknesses
                if ":" in w and "Untertrainiert" in w
            ]
            focus = ""
            if focus_labels:
                focus = f" – Fokus {', '.join(focus_labels)}"
            profile_label = {
                "kraft": "Kraft",
                "hypertrophie": "Hypertrophie",
                "definition": "Definition",
            }.get(self.target_profile, self.target_profile.capitalize())
            plan_json["plan_name"] = (
                f"{profile_label}-{self.plan_type.upper().replace('-', '/')}"
                f"{focus} ({_date.today().strftime('%d.%m.%Y')})"
            )
            print(f"   ℹ️  Plan-Name war generisch – ersetzt durch: '{plan_json['plan_name']}'")
        else:
            # Datum im LLM-generierten Namen korrigieren (LLM halluziniert oft falsche Daten)
            import re
            from datetime import date as _date

            today_str = _date.today().strftime("%d.%m.%Y")
            # Ersetze jedes Datum-Pattern im Namen durch heute
            # Formate: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY
            date_patterns = [
                r"\d{2}\.\d{2}\.\d{4}",  # 29.07.2024
                r"\d{4}-\d{2}-\d{2}",  # 2024-07-29
                r"\d{2}/\d{2}/\d{4}",  # 29/07/2024
            ]
            name_fixed = raw_name
            for pattern in date_patterns:
                name_fixed = re.sub(pattern, today_str, name_fixed)
            if name_fixed != raw_name:
                plan_json["plan_name"] = name_fixed
                print(f"   🔧 Datum im Plan-Name korrigiert: '{raw_name}' → '{name_fixed}'")

            # DB-Konstanten im LLM-generierten Namen durch Klartext ersetzen
            name_humanized = _humanize_plan_name(plan_json["plan_name"])
            if name_humanized != plan_json["plan_name"]:
                print(
                    f"   🔧 DB-Konstanten im Plan-Name ersetzt: "
                    f"'{plan_json['plan_name']}' → '{name_humanized}'"
                )
                plan_json["plan_name"] = name_humanized
            elif name_fixed == raw_name:
                print(f"   ✓ Plan-Name: '{raw_name}'")

        # 6. In Django DB speichern
        if save_to_db:
            print("\n💾 SCHRITT 6: Plan in Datenbank speichern")
            print("-" * 60)
            self._progress(90, "Speichere Plan in Datenbank...")

            plan_ids = self._save_plan_to_db(plan_json)

            print(f"✓ {len(plan_ids)} Pläne gespeichert (IDs: {', '.join(map(str, plan_ids))})")
            print(f"   Basis-Name: {plan_json['plan_name']}")
            print(f"   Sessions: {len(plan_json['sessions'])}")

            # 6b. Schwachstellen-Snapshot auf aktivem Block speichern
            self._save_weakness_snapshot(analysis_data)
        else:
            plan_ids = []
            print("\n💾 SCHRITT 6: ÜBERSPRUNGEN (save_to_db=False)")

        # Erfolg!
        print("\n" + "=" * 60)
        print("🎉 FERTIG! Trainingsplan erfolgreich generiert")
        print("=" * 60)

        # Füge Makrozyklus-Beschreibung hinzu (auch für Vorschau)
        macro_summary = self._format_macrocycle_summary(plan_json)
        if "plan_description" not in plan_json:
            plan_json["plan_description"] = ""
        plan_json["beschreibung"] = (
            plan_json["plan_description"] + "\n\nPeriodisierung / Makrozyklus\n" + macro_summary
        )

        return {
            "success": True,
            "plan_ids": plan_ids,
            "plan_data": plan_json,
            "analysis_data": analysis_data,
            "coverage_warnings": coverage_warnings,
            "structure_warnings": structure_warnings,
        }

    def _save_plan_to_db(self, plan_json: dict) -> list:
        """
        Speichert generierten Plan in Django DB
        Erstellt für jede Session einen separaten Plan

        Returns:
            Liste der Plan IDs
        """
        import uuid

        from django.contrib.auth.models import User
        from django.utils import timezone

        from core.models import Plan, PlanUebung, Uebung

        user = User.objects.get(id=self.user_id)
        plan_ids = []

        # Wenn mehrere Sessions (Split-Plan), generiere eine gemeinsame gruppe_id
        is_split = len(plan_json["sessions"]) > 1
        split_gruppe_id = uuid.uuid4() if is_split else None
        split_gruppe_name = plan_json["plan_name"][:200] if is_split else ""

        # ---------------------------------------------------------------
        # Batch-Lookup: alle Übungsnamen aus plan_json auf einmal laden.
        # Verhindert N+1 (vorher: 1 DB-Query pro Übung).
        # ---------------------------------------------------------------
        from django.db.models.functions import Lower

        all_ex_names = {
            ex["exercise_name"]
            for session in plan_json["sessions"]
            for ex in session.get("exercises", [])
        }

        # Query 1: exakter Match
        uebungen_exakt: dict[str, Uebung] = {
            u.bezeichnung: u for u in Uebung.objects.filter(bezeichnung__in=all_ex_names)
        }

        # Query 2 (nur wenn nötig): case-insensitiver + gestrippter Fallback
        # für LLM-Abweichungen wie "bankdrücken" statt "Bankdrücken"
        uebungen_fallback: dict[str, Uebung] = {}
        unmatched_names = {name for name in all_ex_names if name not in uebungen_exakt}
        if unmatched_names:
            normalized_unmatched = {name.strip().lower() for name in unmatched_names}
            for u in Uebung.objects.annotate(lower_name=Lower("bezeichnung")).filter(
                lower_name__in=normalized_unmatched
            ):
                uebungen_fallback[u.lower_name] = u

        def _find_uebung(name: str) -> Uebung | None:
            """Exakter Match, sonst case-insensitiver Strip-Fallback (kein extra DB-Hit)."""
            exact = uebungen_exakt.get(name)
            if exact:
                return exact
            normalized = name.strip().lower()
            fuzzy = uebungen_fallback.get(normalized)
            if fuzzy:
                print(f"      ℹ️  Fuzzy-Match: '{name}' → '{fuzzy.bezeichnung}'")
            return fuzzy

        # Übungen die nicht gefunden werden – für abschließende Warnung sammeln
        not_found: list[str] = []

        # Für jede Session einen separaten Plan erstellen
        for session_index, session in enumerate(plan_json["sessions"], start=1):
            day_name = session["day_name"]

            # Plan pro Session erstellen
            beschreibungsteile = [
                plan_json.get("plan_description", "")
                + f"\n\nTrainingstag {session_index}: {day_name}"
            ]
            macro_summary = self._format_macrocycle_summary(plan_json)
            if macro_summary:
                beschreibungsteile.append("Periodisierung / Makrozyklus" + "\n" + macro_summary)

            plan = Plan.objects.create(
                user=user,
                name=f"{plan_json['plan_name']} - {day_name}"[:200],
                beschreibung="\n\n".join([p for p in beschreibungsteile if p]),
                erstellt_am=timezone.now(),
                gruppe_id=split_gruppe_id,
                gruppe_name=split_gruppe_name,
                gruppe_reihenfolge=session_index - 1,  # 0-basiert: Tag 1 = 0, Tag 2 = 1, etc.
            )

            plan_ids.append(plan.id)
            print(f"   ✓ Plan erstellt: '{plan.name}' (ID: {plan.id})")

            # Übungen für diese Session
            for exercise_data in session["exercises"]:
                ex_name = exercise_data["exercise_name"]

                uebung = _find_uebung(ex_name)
                if uebung is None:
                    print(f"      ⚠️ Übung '{ex_name}' nicht gefunden - überspringe")
                    not_found.append(ex_name)
                    continue

                # PlanUebung erstellen
                rpe_target_raw = exercise_data.get("rpe_target")
                rpe_ziel_val = None
                if rpe_target_raw is not None:
                    try:
                        rpe_ziel_val = float(rpe_target_raw)
                    except (ValueError, TypeError):
                        pass
                PlanUebung.objects.create(
                    plan=plan,
                    uebung=uebung,
                    trainingstag=day_name,
                    reihenfolge=exercise_data.get("order", 1),
                    saetze_ziel=exercise_data.get("sets", 3),
                    wiederholungen_ziel=exercise_data.get("reps", "8-10"),
                    pausenzeit=exercise_data.get("rest_seconds", 120),
                    rpe_ziel=rpe_ziel_val,
                )

                rpe = exercise_data.get("rpe_target", "-")
                rest = exercise_data.get("rest_seconds", 120)
                notes = exercise_data.get("notes", "")
                print(
                    f"      ✓ {ex_name}: {exercise_data.get('sets')}x{exercise_data.get('reps')} (RPE {rpe}, Pause {rest}s)"
                )
                if notes:
                    print(f"        💡 {notes}")

            print()  # Leerzeile zwischen Sessions

        if not_found:
            print(
                f"   ⚠️  {len(not_found)} Übung(en) nicht in DB gefunden "
                f"(auch nach Fuzzy-Match): {', '.join(not_found)}"
            )

        return plan_ids

    def _save_weakness_snapshot(self, analysis_data: dict) -> None:
        """Speichert Schwachstellen-Snapshot auf dem aktiven Trainingsblock.

        Baut eine Liste von {muskelgruppe, ist_saetze, soll_min, soll_max} aus den
        identifizierten Schwachstellen und den aktuellen Satz-Zahlen.
        """
        from datetime import timedelta

        from django.contrib.auth.models import User
        from django.db.models import Count
        from django.utils import timezone

        from core.models import Satz, Trainingsblock
        from core.utils.periodization import MUSKELGRUPPEN_GROESSE, get_volumen_schwellenwerte

        try:
            user = User.objects.get(id=self.user_id)
            active_block = (
                Trainingsblock.objects.filter(user=user, end_datum__isnull=True)
                .order_by("-start_datum")
                .first()
            )
            if not active_block:
                print("   [INFO] Kein aktiver Block - Schwachstellen-Snapshot uebersprungen")
                return

            weaknesses = analysis_data.get("weaknesses", [])
            if not weaknesses:
                print("   [INFO] Keine Schwachstellen identifiziert - Snapshot uebersprungen")
                return

            # Aktuelle Arbeitssätze pro Muskelgruppe (letzte 30 Tage)
            seit = timezone.now() - timedelta(days=30)
            mg_counts = dict(
                Satz.objects.filter(
                    einheit__user=user,
                    einheit__datum__gte=seit,
                    ist_aufwaermsatz=False,
                    einheit__ist_deload=False,
                )
                .values_list("uebung__muskelgruppe")
                .annotate(count=Count("id"))
                .values_list("uebung__muskelgruppe", "count")
            )

            snapshot = []
            for weakness in weaknesses:
                if ":" not in weakness or "Untertrainiert" not in weakness:
                    continue
                label = weakness.split(":")[0].strip()
                # Label → DB-Key Mapping (gleiche Logik wie _validate_weakness_coverage)
                mg_key = label.upper().replace(" ", "_").replace("Ä", "AE").replace("Ü", "UE")
                # Spezial-Mappings für Klartext-Labels
                label_to_key = {
                    "Brust": "BRUST",
                    "Lat": "RUECKEN_LAT",
                    "Trapez": "RUECKEN_TRAPEZ",
                    "Unterer Rücken": "RUECKEN_UNTEN",
                    "Oberer Rücken": "RUECKEN_OBERER",
                    "Vordere Schulter": "SCHULTER_VORN",
                    "Seitliche Schulter": "SCHULTER_SEIT",
                    "Hintere Schulter": "SCHULTER_HINT",
                    "Bizeps": "BIZEPS",
                    "Trizeps": "TRIZEPS",
                    "Bauch": "BAUCH",
                    "Quadrizeps": "BEINE_QUAD",
                    "Hamstrings": "BEINE_HAM",
                    "Gesäß": "PO",
                    "Waden": "WADEN",
                    "Unterarme": "UNTERARME",
                    "Adduktoren": "ADDUKTOREN",
                    "Abduktoren": "ABDUKTOREN",
                    "Hüftbeuger": "HUEFTBEUGER",
                }
                resolved_key = label_to_key.get(label, mg_key)
                # Nur Muskelgruppen mit bekannten Volumen-Schwellenwerten
                if resolved_key not in MUSKELGRUPPEN_GROESSE:
                    continue
                schwelle = get_volumen_schwellenwerte(resolved_key, active_block.typ)
                if not schwelle:
                    continue
                ist_saetze = mg_counts.get(resolved_key, 0)
                snapshot.append(
                    {
                        "muskelgruppe": resolved_key,
                        "ist_saetze": ist_saetze,
                        "soll_min": schwelle[0],
                        "soll_max": schwelle[1],
                    }
                )

            if snapshot:
                active_block.schwachstellen_snapshot = snapshot
                active_block.save(update_fields=["schwachstellen_snapshot"])
                print(f"   [OK] Schwachstellen-Snapshot gespeichert: {len(snapshot)} Muskelgruppen")
                for entry in snapshot:
                    mg = _humanize_muskelgruppe(entry["muskelgruppe"])
                    print(
                        f"      {mg}: {entry['ist_saetze']} Saetze "
                        f"(Soll: {entry['soll_min']}-{entry['soll_max']})"
                    )
            else:
                print("   [INFO] Keine trackbaren Schwachstellen - Snapshot uebersprungen")
        except Exception as e:
            print(f"   [WARN] Schwachstellen-Snapshot Fehler: {e}")

    def _fix_invalid_exercises(
        self, plan_json: dict, errors: list, available_exercises: list, llm_client
    ) -> dict:
        """
        Smart Retry: Ersetzt halluzinierte Übungen durch valide Alternativen.

        Nutzt generate_training_plan() über die öffentliche API – nie direkt
        _generate_with_openrouter() aufrufen (internes Detail, gibt Wrapper-Dict zurück).

        Args:
            plan_json: Der generierte Plan mit Fehlern
            errors: Liste der Validierungsfehler
            available_exercises: Liste verfügbarer Übungen
            llm_client: LLM Client für Korrektur-Request

        Returns:
            Korrigierter Plan (unverändert wenn kein Retry nötig oder Korrektur fehlschlägt)
        """
        import re

        # Fehlerhafte Übungen aus Errors extrahieren
        invalid_exercises = []
        for error in errors:
            match = re.search(r"'([^']+)' nicht verfügbar", error)
            if match:
                invalid_exercises.append(match.group(1))

        if not invalid_exercises:
            print("   ℹ️ Keine automatisch korrigierbaren Fehler gefunden")
            return plan_json

        print(f"   🔍 Gefundene halluzinierte Übungen: {len(invalid_exercises)}")
        for ex in invalid_exercises:
            print(f"      ❌ {ex}")

        exercise_list = "\n".join([f"- {ex}" for ex in available_exercises])

        correction_prompt = f"""Du hast folgende NICHT-EXISTIERENDE Übungen verwendet:
{chr(10).join(f'- {ex}' for ex in invalid_exercises)}

Diese Übungen sind nicht in der Datenbank – sie wurden halluziniert.

Wähle für JEDE fehlerhafte Übung GENAU EINE passende Alternative aus der VERFÜGBAREN Liste.
Die Alternative sollte dieselbe Muskelgruppe trainieren und ähnlichen Bewegungstyp haben.

VERFÜGBARE ÜBUNGEN (NUR DIESE VERWENDEN!):
{exercise_list}

Antworte mit einem JSON-Objekt: Schlüssel = fehlerhafte Übung, Wert = Ersatz aus obiger Liste.
Beispiel:
{{
  "Cable Fly": "Fliegende (Kurzhantel)",
  "Leg Press (Maschine)": "Kniebeuge (Langhantel, Back Squat)"
}}

Kopiere die Ersatz-Namen EXAKT aus der Liste – keine Variationen!"""

        messages = [
            {"role": "system", "content": "Du bist ein Fitness-Experte."},
            {"role": "user", "content": correction_prompt},
        ]

        print("\n   🤖 Sende Korrektur-Request an LLM...")

        try:
            result = llm_client.generate_training_plan(messages=messages, max_tokens=500)
            self._log_ki_cost(result, is_retry=True)

            # generate_training_plan() gibt immer {"response": <dict>, ...} zurück
            replacements = result.get("response", {})

            if not isinstance(replacements, dict) or not replacements:
                print("   ⚠️ Leere oder ungültige Replacements-Response")
                return plan_json

            print(f"   ✓ {len(replacements)} Ersetzungen erhalten:")
            for old, new in replacements.items():
                print(f"      {old} → {new}")

            # Übungen im Plan ersetzen (nur exakter Match)
            replaced_count = 0
            for session in plan_json["sessions"]:
                for exercise in session["exercises"]:
                    ex_name = exercise["exercise_name"]
                    if ex_name in replacements:
                        exercise["exercise_name"] = replacements[ex_name]
                        replaced_count += 1
                        print(f"   ✓ Ersetzt: {ex_name} → {replacements[ex_name]}")

            print(f"\n   ✅ {replaced_count} Übungen korrigiert")
            return plan_json

        except Exception as e:
            print(f"   ⚠️ Korrektur fehlgeschlagen: {e}")
            print("   → Plan wird ohne Korrektur zurückgegeben")
            return plan_json

    def _ensure_periodization_metadata(self, plan_json: dict) -> dict:
        """Sichert Makrozyklus-/Periodisierungsdaten ab und ergänzt Defaults"""
        profile = (plan_json.get("target_profile") or self.target_profile or "hypertrophie").lower()
        periodization = (plan_json.get("periodization") or self.periodization or "linear").lower()
        deload_weeks = plan_json.get("deload_weeks") or [4, 8, 12]

        plan_json["target_profile"] = profile
        plan_json["periodization"] = periodization
        plan_json["duration_weeks"] = plan_json.get("duration_weeks", 12)
        plan_json["deload_weeks"] = deload_weeks
        plan_json["macrocycle"] = plan_json.get("macrocycle") or self._build_macrocycle(
            periodization, profile, deload_weeks
        )
        plan_json["microcycle_template"] = plan_json.get(
            "microcycle_template"
        ) or self._build_microcycle_template(profile)
        plan_json["progression_strategy"] = plan_json.get(
            "progression_strategy"
        ) or self._build_progression_strategy(profile)

        return plan_json

    def _get_profile_defaults(self, profile: str) -> Dict[str, object]:
        defaults = {
            "kraft": {
                "rep_range": "3-6",
                "rpe_range": "7.5-9",
                "base_rpe": 8.3,
                "notes": "Fokus auf Maximalkraft, längere Pausen, weniger Übungen",
            },
            "hypertrophie": {
                "rep_range": "6-12",
                "rpe_range": "7-8.5",
                "base_rpe": 7.8,
                "notes": "Muskelaufbau, moderates Volumen pro Übung",
            },
            "definition": {
                "rep_range": "10-15",
                "rpe_range": "6.5-8",
                "base_rpe": 7.2,
                "notes": "Kürzere Pausen, höheres metabolisches Volumen",
            },
        }
        return defaults.get(profile, defaults["hypertrophie"])

    def _build_macrocycle(
        self, periodization: str, profile: str, deload_weeks: List[int]
    ) -> Dict[str, object]:
        defaults = self._get_profile_defaults(profile)
        weeks = []

        for week in range(1, 13):
            block = ((week - 1) // 4) + 1
            pos_in_block = ((week - 1) % 4) + 1
            is_deload = week in deload_weeks

            volume_multiplier = (
                0.8 if is_deload else round(1.0 + 0.05 * (block - 1) + 0.02 * (pos_in_block - 1), 2)
            )
            intensity_rpe = self._calculate_weekly_rpe(
                periodization, defaults["base_rpe"], pos_in_block, block, is_deload
            )
            focus = self._week_focus(periodization, block, is_deload, profile)
            notes = (
                "Deload: Volumen -20%, Intensität -10%"
                if is_deload
                else self._periodization_note(periodization, block, pos_in_block)
            )

            weeks.append(
                {
                    "week": week,
                    "block": block,
                    "is_deload": is_deload,
                    "volume_multiplier": volume_multiplier,
                    "intensity_target_rpe": intensity_rpe,
                    "focus": focus,
                    "notes": notes,
                }
            )

        return {
            "duration_weeks": 12,
            "periodization": periodization,
            "target_profile": profile,
            "deload_weeks": deload_weeks,
            "weeks": weeks,
        }

    def _calculate_weekly_rpe(
        self, periodization: str, base_rpe: float, pos_in_block: int, block: int, is_deload: bool
    ) -> float:
        if is_deload:
            return round(max(6.5, base_rpe - 1.0), 1)

        # Linear: steigende Intensität innerhalb des Blocks
        if periodization.startswith("lin"):
            return round(min(9.0, base_rpe + 0.2 * (pos_in_block - 1) + 0.1 * (block - 1)), 1)

        # Wellenförmig: Heavy/Medium/Light pro Block
        if periodization.startswith("w"):  # wellenfoermig
            pattern = {1: 0.0, 2: 0.3, 3: -0.1}
            delta = pattern.get(pos_in_block, 0.0)
            return round(min(9.0, max(6.5, base_rpe + delta)), 1)

        # Block: Block 1 Basisvolumen, Block 2 Kraft, Block 3 Peaking/Definition
        if periodization.startswith("b"):
            block_delta = {1: -0.2, 2: 0.1, 3: 0.25}
            return round(min(9.0, max(6.5, base_rpe + block_delta.get(block, 0))), 1)

        # Fallback linear
        return round(min(9.0, base_rpe + 0.15 * (pos_in_block - 1)), 1)

    def _week_focus(self, periodization: str, block: int, is_deload: bool, profile: str) -> str:
        if is_deload:
            return "Deload & Technik"
        if periodization.startswith("w"):
            return f"Welle Block {block}: Schwer/Mittel/Leicht"
        if periodization.startswith("b"):
            focus_map = {1: "Volumenbasis", 2: "Kraft/Intensität", 3: "Top-/Definition"}
            return focus_map.get(block, "Volumenbasis")
        return f"Linearer Aufbau Block {block} ({profile})"

    def _periodization_note(self, periodization: str, block: int, pos_in_block: int) -> str:
        if periodization.startswith("w"):
            tags = {1: "Medium", 2: "Heavy", 3: "Light"}
            return f"Wellenförmig: {tags.get(pos_in_block, 'Medium')} Woche"
        if periodization.startswith("b"):
            if block == 1:
                return "Volumen priorisieren, Technik stabilisieren"
            if block == 2:
                return "Kraftfokus: schwerere Compounds"
            return "Top-Phase: niedrigeres Volumen, höhere RPE"
        return "Progressiv +0.5 RPE / Block"

    def _build_microcycle_template(self, profile: str) -> Dict[str, object]:
        defaults = self._get_profile_defaults(profile)
        return {
            "target_profile": profile,
            "rep_range": defaults["rep_range"],
            "rpe_range": defaults["rpe_range"],
            "set_progression": "+1 Satz pro Hauptübung in Nicht-Deload-Wochen bis Obergrenze, danach Deload-Reset",
            "deload_rules": "Woche 4/8/12: Volumen 80%, Intensität 90%",
            "notes": defaults["notes"],
        }

    def _build_progression_strategy(self, profile: str) -> Dict[str, object]:
        defaults = self._get_profile_defaults(profile)
        return {
            "target_profile": profile,
            "rpe_guardrails": f"Hauptübungen RPE Ziel {defaults['rpe_range']}",
            "auto_load": "Wenn RPE > Ziel +0.5 zweimal in Folge: -5% Gewicht oder 1 Satz weniger. Wenn RPE < Ziel -0.5 zweimal: +2.5-5% Gewicht.",
            "volume": f"Starte bei ~{self.sets_per_session} Sätzen pro Tag, erhöhe +1 Satz bei Hauptübung in Woche 2-3/6-7/10-11, Deload-Wochen resetten auf Basisvolumen.",
            "progression": "Steigere erst Wiederholungen innerhalb Range, dann Gewicht. Nach Deload: 1 Woche Re-Akklimatisierung.",
        }

    def _validate_weakness_coverage(
        self,
        plan_json: dict,
        weaknesses: list[str],
        available_exercises: list[str] | None = None,
    ) -> list[str]:
        """
        Prüft ob die identifizierten Schwachstellen im generierten Plan abgedeckt sind.
        Wenn available_exercises übergeben wird: Auto-Fix durch Einsetzen einer passenden
        Übung in die geeignetste Session (ersetzt die letzte Übung mit den wenigsten Sätzen).

        Returns:
            Liste von Warnungen (leer = alles abgedeckt)
        """
        if not weaknesses:
            return []

        LABEL_TO_KEYS: dict[str, list[str]] = {
            "brust": ["BRUST"],
            "rücken": ["RUECKEN_LAT", "RUECKEN_TRAPEZ", "RUECKEN_UNTEN", "RUECKEN_OBERER"],
            "beine": [
                "BEINE_QUAD",
                "BEINE_HAM",
                "PO",
                "WADEN",
                "ADDUKTOREN",
                "ABDUKTOREN",
                "HUEFTBEUGER",
            ],
            "schultern": ["SCHULTER_VORN", "SCHULTER_SEIT", "SCHULTER_HINT"],
            "vordere schulter": ["SCHULTER_VORN"],
            "seitliche schulter": ["SCHULTER_SEIT"],
            "hintere schulter": ["SCHULTER_HINT"],
            "bizeps": ["BIZEPS"],
            "trizeps": ["TRIZEPS"],
            "bauch": ["BAUCH"],
            "unterer rücken": ["RUECKEN_UNTEN"],
            "waden": ["WADEN"],
            "unterarme": ["UNTERARME"],
            "trapez": ["RUECKEN_TRAPEZ"],
            "oberer rücken": ["RUECKEN_OBERER"],
            "oberschenkel vorne": ["BEINE_QUAD"],
            "oberschenkel hinten": ["BEINE_HAM"],
            "gesäß": ["PO"],
            "adduktoren": ["ADDUKTOREN"],
            "abduktoren": ["ABDUKTOREN"],
            "hüfte": ["HUEFTBEUGER", "ADDUKTOREN", "ABDUKTOREN"],
            "hüftbeuger": ["HUEFTBEUGER"],
            # DB-Konstanten als Keys (data_analyzer liefert z.B. "HUEFTBEUGER: Untertrainiert")
            "hueftbeuger": ["HUEFTBEUGER"],
            "schulter_hint": ["SCHULTER_HINT"],
            "schulter_vorn": ["SCHULTER_VORN"],
            "schulter_seit": ["SCHULTER_SEIT"],
            "ruecken_lat": ["RUECKEN_LAT"],
            "ruecken_trapez": ["RUECKEN_TRAPEZ"],
            "ruecken_unten": ["RUECKEN_UNTEN"],
            "ruecken_oberer": ["RUECKEN_OBERER"],
            "beine_quad": ["BEINE_QUAD"],
            "beine_ham": ["BEINE_HAM"],
            "po": ["PO"],
        }

        # Welche Muskelgruppen-Keys kommen im Plan vor?
        # Phase 13.2: Primär (muskelgruppe) und sekundär (hilfsmuskeln) getrennt tracken.
        # hilfsmuskeln allein gilt NICHT als Coverage für Pflicht-Schwachstellen.
        try:
            from core.models import Uebung

            all_ex_names = {
                ex["exercise_name"]
                for session in plan_json.get("sessions", [])
                for ex in session.get("exercises", [])
            }
            plan_exercises = Uebung.objects.filter(bezeichnung__in=all_ex_names)
            primary_keys = set(plan_exercises.values_list("muskelgruppe", flat=True).distinct())
            secondary_keys: set[str] = set()
            for ex in plan_exercises:
                if ex.hilfsmuskeln:
                    secondary_keys.update(ex.hilfsmuskeln)
        except Exception as e:
            print(f"   ⚠️ Coverage-Check DB-Fehler: {e}")
            return []

        warnings = []
        for weakness in weaknesses:
            if ":" not in weakness or "Untertrainiert" not in weakness:
                continue
            label = weakness.split(":")[0].strip().lower()
            target_keys = LABEL_TO_KEYS.get(label)
            if not target_keys:
                continue

            # Phase 13.2: Nur primäre Muskelgruppe zählt als Coverage
            covered_primary = any(k in primary_keys for k in target_keys)
            if covered_primary:
                print(f"   ✓ Coverage OK: {weakness.split(':')[0].strip()}")
                continue

            mg_display = weakness.split(":")[0].strip()

            # Nur sekundär abgedeckt → nicht ausreichend, Auto-Fix versuchen
            covered_secondary = any(k in secondary_keys for k in target_keys)
            if covered_secondary:
                print(
                    f"   ⚠️ {mg_display}: nur als Hilfsmuskel abgedeckt, "
                    f"nicht primär – Auto-Fix wird versucht"
                )

            # --- Auto-Fix: passende Übung finden und einsetzen ---
            if available_exercises:
                fixed = self._auto_fix_weakness(
                    plan_json, target_keys, available_exercises, mg_display
                )
                if fixed:
                    primary_keys.update(target_keys)
                    continue

            qualifier = " (nur als Hilfsmuskel)" if covered_secondary else ""
            warnings.append(
                f"⚠️ Schwachstelle nicht abgedeckt: {mg_display}{qualifier} – "
                f"keine Übung mit primärer Muskelgruppe im Plan"
            )
            print(f"   ⚠️ Coverage fehlt: {mg_display} (Keys: {target_keys})")

        return warnings

    def _auto_fix_weakness(
        self,
        plan_json: dict,
        target_keys: list[str],
        available_exercises: list[str],
        mg_display: str,
    ) -> bool:
        """Setzt eine passende Übung für eine nicht abgedeckte Schwachstelle ein.

        Strategie:
        1. Finde verfügbare Übung für die Muskelgruppe
        2. Finde die Session mit den meisten verwandten Muskelgruppen (best fit)
        3. Ersetze die letzte Übung mit den wenigsten Sätzen in dieser Session

        Returns:
            True wenn Fix erfolgreich, False wenn keine passende Übung gefunden.
        """
        try:
            from core.models import Uebung

            # Passende Übung finden (bevorzuge Körpergewicht-Übungen)
            candidates = list(
                Uebung.objects.filter(
                    muskelgruppe__in=target_keys,
                    bezeichnung__in=available_exercises,
                )
                .order_by("gewichts_typ")  # KOERPERGEWICHT sortiert vor GESAMT/PRO_SEITE
                .values_list("bezeichnung", flat=True)[:5]
            )
            if not candidates:
                print(f"   ❌ Kein Auto-Fix: keine verfügbare Übung für {mg_display}")
                return False

            replacement_name = candidates[0]

            # Verwandte Muskelgruppen für Session-Matching
            RELATED = {
                "HUEFTBEUGER": {"BEINE_QUAD", "BEINE_HAM", "PO", "BAUCH"},
                "SCHULTER_HINT": {"RUECKEN_LAT", "RUECKEN_OBERER", "BIZEPS"},
                "BAUCH": {"BEINE_QUAD", "BEINE_HAM", "HUEFTBEUGER"},
                "ADDUKTOREN": {"BEINE_QUAD", "BEINE_HAM", "PO"},
                "ABDUKTOREN": {"BEINE_QUAD", "BEINE_HAM", "PO"},
                "WADEN": {"BEINE_QUAD", "BEINE_HAM"},
            }
            related_keys = set()
            for k in target_keys:
                related_keys.update(RELATED.get(k, set()))

            # Beste Session finden (meiste verwandte Übungen)
            best_session_idx = 0
            best_score = -1
            for idx, session in enumerate(plan_json.get("sessions", [])):
                ex_names = [e["exercise_name"] for e in session.get("exercises", [])]
                session_keys = set(
                    Uebung.objects.filter(bezeichnung__in=ex_names).values_list(
                        "muskelgruppe", flat=True
                    )
                )
                score = len(session_keys & related_keys)
                if score > best_score:
                    best_score = score
                    best_session_idx = idx

            session = plan_json["sessions"][best_session_idx]
            exercises = session.get("exercises", [])

            if not exercises:
                return False

            # Session-Satz-Budget prüfen: unter Budget → hinzufügen statt ersetzen
            current_sets = sum(ex.get("sets", 0) for ex in exercises)
            max_budget = self.sets_per_session  # Typ. 18

            if current_sets < max_budget - 2:
                # Session hat Platz → Übung hinzufügen
                new_ex = {
                    "exercise_name": replacement_name,
                    "sets": min(3, max_budget - current_sets),
                    "reps": "10-15",
                    "rpe_target": 7.5,
                    "rest_seconds": 60,
                    "order": len(exercises) + 1,
                    "notes": f"Auto-Fix: Schwachstelle {mg_display}",
                }
                exercises.append(new_ex)
                print(
                    f"   🔧 Auto-Fix: '{replacement_name}' hinzugefügt in "
                    f"'{session.get('day_name', '?')}' für {mg_display} "
                    f"({current_sets}→{current_sets + new_ex['sets']} Sätze)"
                )
                return True

            # Session ist voll → letzte Übung mit wenigsten Sätzen ersetzen (ab Position 3+)
            replaceable = [
                (i, ex)
                for i, ex in enumerate(exercises)
                if i >= 3  # Erste 3 Übungen (Compounds) nicht antasten
            ]
            if not replaceable:
                # Alle Übungen sind Compounds — füge stattdessen hinzu
                new_ex = {
                    "exercise_name": replacement_name,
                    "sets": 3,
                    "reps": "10-15",
                    "rpe_target": 7.5,
                    "rest_seconds": 60,
                    "order": len(exercises) + 1,
                    "notes": f"Auto-Fix: Schwachstelle {mg_display}",
                }
                exercises.append(new_ex)
                print(
                    f"   🔧 Auto-Fix: '{replacement_name}' hinzugefügt in "
                    f"'{session.get('day_name', '?')}' für {mg_display}"
                )
                return True

            # Ersetze die Übung mit den wenigsten Sätzen unter den ersetzbaren
            min_idx, min_ex = min(replaceable, key=lambda x: x[1].get("sets", 99))
            old_name = min_ex.get("exercise_name", "?")
            min_ex["exercise_name"] = replacement_name
            min_ex["notes"] = f"Auto-Fix: ersetzt '{old_name}' für Schwachstelle {mg_display}"
            print(
                f"   🔧 Auto-Fix: '{old_name}' → '{replacement_name}' in "
                f"'{session.get('day_name', '?')}' für {mg_display}"
            )
            return True

        except Exception as e:
            print(f"   ❌ Auto-Fix Fehler für {mg_display}: {e}")
            return False

    def _format_macrocycle_summary(self, plan_json: dict) -> str:
        """Formatiert benutzerfreundliche Makrozyklus-Zusammenfassung mit konkreten Anweisungen"""
        macro = plan_json.get("macrocycle", {}) or {}
        deload_weeks = plan_json.get("deload_weeks") or macro.get("deload_weeks") or []
        periodization = plan_json.get("periodization", self.periodization)
        profile = plan_json.get("target_profile", self.target_profile)
        duration = macro.get("duration_weeks") or plan_json.get("duration_weeks", 12)

        # Benutzerfreundliche Überschrift
        periodization_labels = {
            "linear": "Linearer Aufbau",
            "wellenfoermig": "Wellenförmige Periodisierung",
            "block": "Blockperiodisierung",
        }
        profile_labels = {
            "kraft": "Maximalkraft",
            "hypertrophie": "Muskelaufbau",
            "definition": "Definition & Ausdauer",
        }

        lines = [
            f"PLANÜBERSICHT: {duration}-Wochen-Plan",
            f"{periodization_labels.get(periodization, periodization)} für {profile_labels.get(profile, profile)}",
            "",
            "",
        ]

        # Mikrozyklus-Vorgaben (Wiederholungen & RPE)
        micro = plan_json.get("microcycle_template") or {}
        if micro:
            rep_range = micro.get("rep_range", "6-12")
            rpe_range = micro.get("rpe_range", "7-8.5")
            lines.append(f"ZIEL PRO SATZ: {rep_range} Wiederholungen bei RPE {rpe_range}")
            lines.append("")
            lines.append("")

        # Phase 13.3: Progressions-Text abhängig von Profil + Periodisierung
        defaults = self._get_profile_defaults(profile)
        rep_range = micro.get("rep_range") if micro else None
        rpe_range = micro.get("rpe_range") if micro else None
        if not rep_range:
            rep_range = defaults["rep_range"]
        if not rpe_range:
            rpe_range = defaults["rpe_range"]

        # Obere Rep-Grenze für Steigerungsregel ableiten
        rep_upper = rep_range.split("-")[-1] if "-" in rep_range else rep_range

        lines.append("PROGRESSION (Wochen 1-3, 5-7, 9-11):")
        if profile == "kraft":
            lines.append(
                f"   - Steigere Gewicht wenn RPE < {rpe_range.split('-')[0]} bei 2+ Trainings"
            )
            lines.append("   - Wiederholungen im unteren Range halten, Gewicht priorisieren")
            lines.append(f"   - Ziel: RPE {rpe_range}, längere Pausen (150-180s)")
        elif profile == "definition":
            lines.append("   - Halte das Gewicht stabil, reduziere Pausen schrittweise")
            lines.append("   - +1 Satz bei Hauptübungen statt Gewichtssteigerung")
            lines.append(f"   - Ziel: RPE {rpe_range}, kürzere Pausen (60-90s)")
        else:  # hypertrophie (default)
            lines.append(f"   - Steigere das Gewicht, wenn du >{rep_upper} Wdh schaffst")
            lines.append("   - Füge +1 Satz bei Hauptübungen hinzu (z.B. von 3 auf 4 Sätze)")
            lines.append(f"   - Ziel: RPE {rpe_range} (noch 1-2 Wdh Reserve)")

        if periodization.startswith("w"):
            lines.append("   - Wellenförmig: Heavy → Medium → Light innerhalb jedes Blocks")
        elif periodization.startswith("b"):
            lines.append(
                "   - Block 1: Volumen aufbauen → Block 2: Kraft steigern → Block 3: Peaking"
            )

        lines.append("")
        lines.append("")

        # Deload-Wochen: Werte aus Makrozyklus ableiten
        deload_str = ", ".join(map(str, deload_weeks)) if deload_weeks else "4, 8, 12"
        # Deload-Multiplier aus macrocycle ableiten wenn vorhanden
        deload_volume_pct = "80%"
        deload_intensity_pct = "~90%"
        if macro and isinstance(macro, dict):
            for week_data in macro.get("weeks", []):
                if week_data.get("is_deload"):
                    vol_mult = week_data.get("volume_multiplier")
                    if vol_mult:
                        deload_volume_pct = f"{int(vol_mult * 100)}%"
                    break

        lines.append(f"DELOAD-WOCHEN ({deload_str}):")
        lines.append(f"   - Reduziere das Volumen auf {deload_volume_pct} (z.B. 4 Sätze → 3 Sätze)")
        lines.append(
            f"   - Senke das Gewicht leicht ({deload_intensity_pct}), RPE sollte bei 6-7 liegen"
        )
        lines.append("   - Fokus auf Technik und Regeneration")
        lines.append("")
        lines.append("")

        # Wochenplan-Beispiele (nur wichtige Wochen)
        if macro and isinstance(macro, dict):
            lines.append("BEISPIEL-WOCHENPLAN:")
            week_examples = []
            for week_data in macro.get("weeks", []):
                week = week_data.get("week")
                if week in (1, 4, 5, 8, 9, 12):  # Zeige nur Start, Deload, neue Blöcke
                    focus = week_data.get("focus", "")
                    vol = week_data.get("volume_multiplier", 1.0)
                    rpe = week_data.get("intensity_target_rpe", 7.8)

                    if week_data.get("is_deload"):
                        week_examples.append(
                            f"   - Woche {week}: {focus} (weniger Volumen, mehr Erholung)"
                        )
                    else:
                        week_examples.append(
                            f"   - Woche {week}: {focus} (Volumen x{vol}, Ziel-RPE {rpe})"
                        )

            if week_examples:
                lines.extend(week_examples[:4])  # Max 4 Beispiele

        return "\n".join(lines)


def main():
    """
    CLI Entry Point
    """
    parser = argparse.ArgumentParser(
        description="AI Coach - Generiert personalisierte Trainingspläne",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # 3er-Split für User 1 generieren und speichern
  python plan_generator.py --user-id 1 --plan-type 3er-split

  # Push/Pull/Legs Split, nur Preview (nicht speichern)
  python plan_generator.py --user-id 1 --plan-type ppl --no-save

  # Ganzkörper-Plan mit mehr Kreativität
  python plan_generator.py --user-id 1 --plan-type fullbody --temperature 0.9
        """,
    )

    parser.add_argument("--user-id", type=int, required=True, help="Django User ID")

    parser.add_argument(
        "--plan-type",
        choices=["3er-split", "4er-split", "ppl", "upper-lower", "fullbody"],
        default="3er-split",
        help="Art des Trainingsplans (default: 3er-split)",
    )

    parser.add_argument(
        "--analysis-days",
        type=int,
        default=30,
        help="Wie viele Tage zurück analysieren (default: 30)",
    )

    parser.add_argument(
        "--sets-per-session",
        type=int,
        default=18,
        help="Ziel-Satzanzahl pro Trainingstag (default: 18, entspricht ca. 1h)",
    )

    parser.add_argument(
        "--temperature", type=float, default=0.7, help="LLM Kreativität 0.0-1.0 (default: 0.7)"
    )

    parser.add_argument(
        "--periodization",
        choices=["linear", "wellenfoermig", "block"],
        default="linear",
        help="Periodisierungsmodell (default: linear, Deload in Woche 4/8/12)",
    )

    parser.add_argument(
        "--target-profile",
        choices=["kraft", "hypertrophie", "definition"],
        default="hypertrophie",
        help="Zielprofil für RPE/Wdh-Zonen (default: hypertrophie)",
    )

    parser.add_argument(
        "--use-openrouter", action="store_true", help="Nutze nur OpenRouter 70B (skip Ollama lokal)"
    )

    parser.add_argument(
        "--no-fallback", action="store_true", help="Kein OpenRouter Fallback bei Ollama-Fehler"
    )

    parser.add_argument(
        "--no-save", action="store_true", help="Plan NICHT in DB speichern (nur Preview)"
    )

    parser.add_argument("--output", type=str, help="JSON Output Datei (optional)")

    args = parser.parse_args()

    # Generator starten
    generator = PlanGenerator(
        user_id=args.user_id,
        analysis_days=args.analysis_days,
        plan_type=args.plan_type,
        llm_temperature=args.temperature,
        sets_per_session=args.sets_per_session,
        periodization=args.periodization,
        target_profile=args.target_profile,
        use_openrouter=args.use_openrouter,
        fallback_to_openrouter=not args.no_fallback,
    )

    result = generator.generate(save_to_db=not args.no_save)

    # Optional: JSON exportieren
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Result gespeichert: {args.output}")

    # Exit code
    if result["success"]:
        print("\n✅ Erfolgreich abgeschlossen!")
        exit(0)
    else:
        print("\n❌ Fehlgeschlagen!")
        exit(1)


if __name__ == "__main__":
    main()
