"""
Plan Generator - Hauptskript für AI Coach
Kombiniert: Data Analyzer → Prompt Builder → LLM → Django Plan Persistierung
"""

import argparse
import json
from datetime import datetime
from typing import Optional

from db_client import DatabaseClient
from data_analyzer import TrainingAnalyzer
from prompt_builder import PromptBuilder
from llm_client import LLMClient


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
        sets_per_session: int = 18
    ):
        """
        Args:
            user_id: Django User ID
            analysis_days: Wie viele Tage zurück analysieren
            plan_type: Art des Plans (3er-split, ppl, upper-lower, fullbody)
            llm_temperature: LLM Kreativität (0.0-1.0)
            sets_per_session: Ziel-Satzanzahl pro Trainingstag (18 = ca. 1h)
        """
        self.user_id = user_id
        self.analysis_days = analysis_days
        self.plan_type = plan_type
        self.llm_temperature = llm_temperature
        self.sets_per_session = sets_per_session
    
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
            with DatabaseClient() as db:
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
                
                llm_client = LLMClient(temperature=self.llm_temperature)
                plan_json = llm_client.generate_training_plan(
                    messages=messages,
                    max_tokens=4000,
                    timeout=120
                )
                
                # 5. Validierung
                print("\n✅ SCHRITT 5: Plan validieren")
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
        
        except Exception as e:
            print(f"\n❌ FEHLER bei Plan-Generierung: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
        sets_per_session=args.sets_per_session
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
