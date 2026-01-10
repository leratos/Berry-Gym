"""
Plan Generator - Hauptskript für AI Coach
Kombiniert: Data Analyzer → Prompt Builder → LLM → Django Plan Persistierung
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Optional

from .db_client import DatabaseClient
from .data_analyzer import TrainingAnalyzer
from .prompt_builder import PromptBuilder
from .llm_client import LLMClient


class PlanGenerator:
    """
    Generiert personalisierte Trainingspläne mit AI
    """
    
    def __init__(
        self, 
        user_id: int,
        analysis_days: int = 30,
        plan_type: str = "3er-split",
        llm_temperature: float = 0.7,
        sets_per_session: int = 18,
        use_openrouter: bool = False,
        fallback_to_openrouter: bool = True
    ):
        """
        Args:
            user_id: Django User ID
            analysis_days: Wie viele Tage zurück analysieren
            plan_type: Art des Plans (3er-split, ppl, upper-lower, fullbody)
            llm_temperature: LLM Kreativität (0.0-1.0)
            sets_per_session: Ziel-Satzanzahl pro Trainingstag (18 = ca. 1h)
            use_openrouter: True = nutze nur OpenRouter (skip Ollama)
            fallback_to_openrouter: True = Fallback zu OpenRouter bei Ollama-Fehler
        """
        self.user_id = user_id
        self.analysis_days = analysis_days
        self.plan_type = plan_type
        self.llm_temperature = llm_temperature
        self.sets_per_session = sets_per_session
        self.use_openrouter = use_openrouter
        self.fallback_to_openrouter = fallback_to_openrouter
    
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
            django_is_running = 'django' in sys.modules and hasattr(sys.modules['django'], 'apps')
            
            if django_is_running:
                # Django läuft bereits (Web-Kontext) - kein DB-Client nötig
                print("\n💡 Django-Kontext erkannt - nutze existierende DB-Verbindung")
                return self._generate_with_existing_django(save_to_db)
            else:
                # CLI-Modus - braucht DatabaseClient mit SSH-Tunnel
                print("\n💡 CLI-Modus - starte SSH-Tunnel")
                with DatabaseClient() as db:
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
        
        analyzer = TrainingAnalyzer(
            user_id=self.user_id,
            days=self.analysis_days
        )
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
        
        messages = builder.build_messages(
            analysis_data=analysis_data,
            available_exercises=available_exercises,
            plan_type=self.plan_type,
            sets_per_session=self.sets_per_session
        )
        
        print(f"✓ System Prompt: {len(messages[0]['content'])} Zeichen")
        print(f"✓ User Prompt: {len(messages[1]['content'])} Zeichen")
        
        # 4. LLM Call - Trainingsplan generieren
        print("\n🧠 SCHRITT 4: Trainingsplan mit Llama generieren")
        print("-" * 60)
        
        llm_client = LLMClient(
            temperature=self.llm_temperature,
            use_openrouter=self.use_openrouter,
            fallback_to_openrouter=self.fallback_to_openrouter
        )
        plan_json = llm_client.generate_training_plan(
            messages=messages,
            max_tokens=4000,
            timeout=120
        )
        
        # 5. Validierung mit Smart Retry
        print("\n✅ SCHRITT 5: Plan validieren")
        print("-" * 60)
        
        valid, errors = llm_client.validate_plan(plan_json, available_exercises)
        
        if not valid:
            print(f"⚠️ Plan Validation: {len(errors)} Fehler gefunden")
            for error in errors:
                print(f"   - {error}")
            
            # Smart Retry: Fehlerhafte Übungen durch LLM ersetzen lassen
            print("\n🔄 SCHRITT 5b: Fehlerhafte Übungen korrigieren (Smart Retry)")
            print("-" * 60)
            
            plan_json = self._fix_invalid_exercises(
                plan_json=plan_json,
                errors=errors,
                available_exercises=available_exercises,
                llm_client=llm_client
            )
            
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
                'success': False,
                'errors': errors,
                'plan_data': plan_json,
                'analysis_data': analysis_data
            }
        
        # 6. In Django DB speichern
        if save_to_db:
            print("\n💾 SCHRITT 6: Plan in Datenbank speichern")
            print("-" * 60)
            
            plan_ids = self._save_plan_to_db(plan_json)
            
            print(f"✓ {len(plan_ids)} Pläne gespeichert (IDs: {', '.join(map(str, plan_ids))})")
            print(f"   Basis-Name: {plan_json['plan_name']}")
            print(f"   Sessions: {len(plan_json['sessions'])}")
        else:
            plan_ids = []
            print("\n💾 SCHRITT 6: ÜBERSPRUNGEN (save_to_db=False)")
        
        # Erfolg!
        print("\n" + "=" * 60)
        print("🎉 FERTIG! Trainingsplan erfolgreich generiert")
        print("=" * 60)
        
        return {
            'success': True,
            'plan_ids': plan_ids,
            'plan_data': plan_json,
            'analysis_data': analysis_data
        }
    
    def _save_plan_to_db(self, plan_json: dict) -> list:
        """
        Speichert generierten Plan in Django DB
        Erstellt für jede Session einen separaten Plan
        
        Returns:
            Liste der Plan IDs
        """
        from core.models import Plan, PlanUebung, Uebung
        from django.contrib.auth.models import User
        from django.utils import timezone
        
        user = User.objects.get(id=self.user_id)
        plan_ids = []
        
        # Für jede Session einen separaten Plan erstellen
        for session_index, session in enumerate(plan_json['sessions'], start=1):
            day_name = session['day_name']
            
            # Plan pro Session erstellen
            plan = Plan.objects.create(
                user=user,
                name=f"{plan_json['plan_name']} - {day_name}",
                beschreibung=plan_json.get('plan_description', '') + f"\n\nTrainingstag {session_index}: {day_name}",
                erstellt_am=timezone.now()
            )
            
            plan_ids.append(plan.id)
            print(f"   ✓ Plan erstellt: '{plan.name}' (ID: {plan.id})")
            
            # Übungen für diese Session
            for exercise_data in session['exercises']:
                ex_name = exercise_data['exercise_name']
                
                # Übung finden
                try:
                    uebung = Uebung.objects.get(bezeichnung=ex_name)
                except Uebung.DoesNotExist:
                    print(f"      ⚠️ Übung '{ex_name}' nicht gefunden - überspringe")
                    continue
                
                # PlanUebung erstellen
                PlanUebung.objects.create(
                    plan=plan,
                    uebung=uebung,
                    trainingstag=day_name,
                    reihenfolge=exercise_data.get('order', 1),
                    saetze_ziel=exercise_data.get('sets', 3),
                    wiederholungen_ziel=exercise_data.get('reps', '8-10')
                )
                
                rpe = exercise_data.get('rpe_target', '-')
                notes = exercise_data.get('notes', '')
                print(f"      ✓ {ex_name}: {exercise_data.get('sets')}x{exercise_data.get('reps')} (RPE {rpe})")
                if notes:
                    print(f"        💡 {notes}")
            
            print()  # Leerzeile zwischen Sessions
        
        return plan_ids
    
    def _fix_invalid_exercises(self, plan_json: dict, errors: list, available_exercises: list, llm_client) -> dict:
        """
        Smart Retry: Ersetzt fehlerhafte Übungen durch valide Alternativen
        Nutzt LLM um passende Ersatz-Übungen aus verfügbaren Optionen zu wählen
        
        Args:
            plan_json: Der generierte Plan mit Fehlern
            errors: Liste der Validierungsfehler
            available_exercises: Liste verfügbarer Übungen
            llm_client: LLM Client für Korrektur-Request
            
        Returns:
            Korrigierter Plan
        """
        import json
        import re
        
        # Fehlerhafte Übungen aus Errors extrahieren
        invalid_exercises = []
        for error in errors:
            # Pattern: "Session X, Übung Y: 'ÜBUNGSNAME' nicht verfügbar"
            match = re.search(r"'([^']+)' nicht verfügbar", error)
            if match:
                invalid_exercises.append(match.group(1))
        
        if not invalid_exercises:
            print("   ℹ️ Keine automatisch korrigierbaren Fehler gefunden")
            return plan_json
        
        print(f"   🔍 Gefundene fehlerhafte Übungen: {len(invalid_exercises)}")
        for ex in invalid_exercises:
            print(f"      ❌ {ex}")
        
        # Kurzer Prompt für Korrektur
        # available_exercises ist eine Liste von Strings (Übungsnamen)
        exercise_list = "\n".join([f"- {ex}" for ex in available_exercises])
        
        correction_prompt = f"""Du hast folgende NICHT-EXISTIERENDE Übungen verwendet:
{chr(10).join(f'- {ex}' for ex in invalid_exercises)}

⚠️ DIESE ÜBUNGEN EXISTIEREN NICHT IN DER DATENBANK!

Wähle für JEDE fehlerhafte Übung GENAU EINE passende Alternative aus der VERFÜGBAREN Liste.
Die Alternative sollte:
1. Die gleiche Muskelgruppe trainieren
2. Ähnlichen Bewegungstyp haben
3. Mit dem verfügbaren Equipment machbar sein

VERFÜGBARE ÜBUNGEN (NUR DIESE VERWENDEN!):
{exercise_list}

Antworte NUR mit einem JSON-Objekt in diesem Format:
{{
  "Fehlerhafte Übung 1": "Ersatz Übung aus Liste",
  "Fehlerhafte Übung 2": "Ersatz Übung aus Liste"
}}

Beispiel:
{{
  "Leg Press (Kurzhantel)": "Bulgarian Split Squat (Kurzhantel)",
  "Cable Fly": "Fliegende (Kurzhantel)"
}}

⚠️ KRITISCH: Verwende EXAKT die Übungsnamen aus der Liste oben! Keine Variationen!"""

        messages = [
            {"role": "system", "content": "Du bist ein Fitness-Experte. Antworte nur mit validem JSON."},
            {"role": "user", "content": correction_prompt}
        ]
        
        print("\n   🤖 Sende Korrektur-Request an LLM...")
        
        try:
            # LLM Call für Korrektur (mit Ollama oder OpenRouter)
            if hasattr(llm_client, '_generate_with_openrouter') and llm_client.use_openrouter:
                response = llm_client._generate_with_openrouter(messages, max_tokens=500)
            else:
                # Fallback zu lokalem Ollama
                response = llm_client._generate_with_ollama(messages, max_tokens=500, timeout=60)
            
            # Debug: Zeige Response-Typ und Struktur
            print(f"   🔍 Response-Typ: {type(response)}")
            
            # Response kann String oder Dict sein
            if isinstance(response, dict):
                # Ollama gibt bereits ein Dict zurück - direkt verwenden!
                replacements = response
                print(f"   ✓ Ersetzungen erhalten (direkt als Dict): {len(replacements)}")
            else:
                # OpenRouter gibt String zurück - muss geparst werden
                response_text = response
                
                # Debug
                print(f"   📝 LLM Response:")
                print(f"   {response_text}")
                
                # JSON parsen
                response_clean = response_text.strip()
                if response_clean.startswith("```json"):
                    response_clean = response_clean.split("```json")[1].split("```")[0].strip()
                elif response_clean.startswith("```"):
                    response_clean = response_clean.split("```")[1].split("```")[0].strip()
                
                # Versuche JSON zu finden wenn Response Text enthält
                import re
                json_match = re.search(r'\{[^}]+\}', response_clean, re.DOTALL)
                if json_match:
                    response_clean = json_match.group(0)
                
                replacements = json.loads(response_clean)
            
            print(f"   ✓ Ersetzungen erhalten: {len(replacements)}")
            for old, new in replacements.items():
                print(f"      {old} → {new}")
            
            # Übungen im Plan ersetzen
            replaced_count = 0
            for session in plan_json['sessions']:
                for exercise in session['exercises']:
                    exercise_name = exercise['exercise_name']
                    
                    # Exakte Übereinstimmung oder teilweise Übereinstimmung
                    if exercise_name in replacements:
                        old_name = exercise_name
                        new_name = replacements[old_name]
                        exercise['exercise_name'] = new_name
                        replaced_count += 1
                        print(f"   ✓ Ersetzt: {old_name} → {new_name}")
                    else:
                        # Versuche teilweise Übereinstimmung (ohne Klammern)
                        for old, new in replacements.items():
                            # Entferne Klammern für Vergleich
                            exercise_base = exercise_name.split('(')[0].strip()
                            old_base = old.split('(')[0].strip()
                            
                            if exercise_base == old_base or exercise_name == old:
                                exercise['exercise_name'] = new
                                replaced_count += 1
                                print(f"   ✓ Ersetzt (partial match): {exercise_name} → {new}")
                                break
            
            print(f"\n   ✅ {replaced_count} Übungen korrigiert")
            return plan_json
            
        except Exception as e:
            print(f"   ⚠️ Korrektur fehlgeschlagen: {e}")
            print("   → Plan wird ohne Korrektur zurückgegeben")
            return plan_json


def main():
    """
    CLI Entry Point
    """
    parser = argparse.ArgumentParser(
        description='AI Coach - Generiert personalisierte Trainingspläne',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # 3er-Split für User 1 generieren und speichern
  python plan_generator.py --user-id 1 --plan-type 3er-split
  
  # Push/Pull/Legs Split, nur Preview (nicht speichern)
  python plan_generator.py --user-id 1 --plan-type ppl --no-save
  
  # Ganzkörper-Plan mit mehr Kreativität
  python plan_generator.py --user-id 1 --plan-type fullbody --temperature 0.9
        """
    )
    
    parser.add_argument(
        '--user-id',
        type=int,
        required=True,
        help='Django User ID'
    )
    
    parser.add_argument(
        '--plan-type',
        choices=['3er-split', '4er-split', 'ppl', 'upper-lower', 'fullbody'],
        default='3er-split',
        help='Art des Trainingsplans (default: 3er-split)'
    )
    
    parser.add_argument(
        '--analysis-days',
        type=int,
        default=30,
        help='Wie viele Tage zurück analysieren (default: 30)'
    )
    
    parser.add_argument(
        '--sets-per-session',
        type=int,
        default=18,
        help='Ziel-Satzanzahl pro Trainingstag (default: 18, entspricht ca. 1h)'
    )
    
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.7,
        help='LLM Kreativität 0.0-1.0 (default: 0.7)'
    )
    
    parser.add_argument(
        '--use-openrouter',
        action='store_true',
        help='Nutze nur OpenRouter 70B (skip Ollama lokal)'
    )
    
    parser.add_argument(
        '--no-fallback',
        action='store_true',
        help='Kein OpenRouter Fallback bei Ollama-Fehler'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Plan NICHT in DB speichern (nur Preview)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='JSON Output Datei (optional)'
    )
    
    args = parser.parse_args()
    
    # Generator starten
    generator = PlanGenerator(
        user_id=args.user_id,
        analysis_days=args.analysis_days,
        plan_type=args.plan_type,
        llm_temperature=args.temperature,
        sets_per_session=args.sets_per_session,
        use_openrouter=args.use_openrouter,
        fallback_to_openrouter=not args.no_fallback
    )
    
    result = generator.generate(save_to_db=not args.no_save)
    
    # Optional: JSON exportieren
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Result gespeichert: {args.output}")
    
    # Exit code
    if result['success']:
        print("\n✅ Erfolgreich abgeschlossen!")
        exit(0)
    else:
        print("\n❌ Fehlgeschlagen!")
        exit(1)


if __name__ == "__main__":
    main()
