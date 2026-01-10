"""
Live Guidance - KI-Coach während dem Training
Gibt kontextbasierte Tipps und beantwortet Fragen in Echtzeit
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
import os
import sys
from pathlib import Path

# Django Setup
sys.path.insert(0, str(Path(__file__).parent))
from db_client import DatabaseClient


class LiveGuidance:
    """
    KI-Coach für Live-Guidance während Training
    Analysiert aktuelle Session und gibt personalisierte Tipps
    """
    
    def __init__(self, use_openrouter: bool = False):
        """
        Args:
            use_openrouter: True = OpenRouter (Server), False = Ollama (lokal)
        """
        self.use_openrouter = use_openrouter
    
    def build_context(
        self,
        trainingseinheit_id: int,
        current_uebung_id: Optional[int] = None,
        current_satz_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sammelt alle relevanten Infos für KI-Coach
        
        Args:
            trainingseinheit_id: ID der aktuellen Trainingseinheit
            current_uebung_id: ID der aktuellen Übung (optional)
            current_satz_number: Satznummer bei aktueller Übung (optional)
        
        Returns:
            Context Dict mit allen relevanten Daten
        """
        from core.models import Trainingseinheit, Satz, Uebung, KoerperWerte
        from django.contrib.auth.models import User
        
        # Trainingseinheit laden
        session = Trainingseinheit.objects.select_related('user', 'plan').get(id=trainingseinheit_id)
        
        # Alle Sätze dieser Session (Feldname ist 'einheit', nicht 'trainingseinheit')
        saetze = Satz.objects.filter(einheit=session).select_related(
            'uebung'
        ).order_by('satz_nr')
        
        # User Info
        user = session.user
        latest_koerperwerte = KoerperWerte.objects.filter(user=user).order_by('-datum').first()
        
        # Aktuelle Übung Details
        current_exercise_context = None
        if current_uebung_id:
            current_uebung = Uebung.objects.get(id=current_uebung_id)
            
            # Sätze dieser Übung in aktueller Session
            exercise_saetze = saetze.filter(uebung=current_uebung)
            
            # Letzter Satz
            last_satz = exercise_saetze.last() if exercise_saetze.exists() else None
            
            current_exercise_context = {
                'name': current_uebung.bezeichnung,
                'muskelgruppe': current_uebung.get_muskelgruppe_display(),
                'bewegungstyp': current_uebung.get_bewegungstyp_display() if hasattr(current_uebung, 'bewegungstyp') else None,
                'beschreibung': current_uebung.beschreibung,
                'completed_sets': exercise_saetze.count(),
                'current_set_number': current_satz_number,
                'last_set': {
                    'gewicht': float(last_satz.gewicht) if last_satz and last_satz.gewicht else None,
                    'wiederholungen': last_satz.wiederholungen if last_satz else None,
                    'rpe': last_satz.rpe if last_satz else None
                } if last_satz else None
            }
        
        # Session Stats
        session_stats = {
            'total_sets': saetze.count(),
            'duration_minutes': session.dauer_minuten or int((timezone.now() - session.datum).total_seconds() / 60),
            'exercises_done': saetze.values('uebung').distinct().count()
        }
        
        # Durchschnittliche RPE
        rpe_values = [s.rpe for s in saetze if s.rpe]
        avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None
        
        # Letzte 5 Trainings für Kontext
        recent_sessions = Trainingseinheit.objects.filter(
            user=user,
            dauer_minuten__isnull=False
        ).exclude(id=trainingseinheit_id).order_by('-datum')[:5]
        
        recent_history = []
        for ts in recent_sessions:
            ts_saetze = Satz.objects.filter(einheit=ts)
            ts_rpe = [s.rpe for s in ts_saetze if s.rpe]
            recent_history.append({
                'date': ts.datum.strftime('%Y-%m-%d') if ts.datum else 'unknown',
                'plan_name': ts.plan.name if ts.plan else 'Kein Plan',
                'total_sets': ts_saetze.count(),
                'avg_rpe': round(sum(ts_rpe) / len(ts_rpe), 1) if ts_rpe else None
            })
        
        context = {
            'user': {
                'name': user.username,
                'gewicht_kg': float(latest_koerperwerte.gewicht) if latest_koerperwerte and latest_koerperwerte.gewicht else None,
                'groesse_cm': float(latest_koerperwerte.groesse_cm) if latest_koerperwerte and latest_koerperwerte.groesse_cm else None
            },
            'current_session': {
                'plan_name': session.plan.name if session.plan else 'Freies Training',
                'started_at': session.datum.strftime('%H:%M') if session.datum else None,
                'stats': session_stats,
                'avg_rpe': round(avg_rpe, 1) if avg_rpe else None
            },
            'current_exercise': current_exercise_context,
            'recent_history': recent_history
        }
        
        return context
    
    def generate_prompt(self, context: Dict[str, Any], user_question: str) -> List[Dict[str, str]]:
        """
        Erstellt LLM Prompt für Live-Guidance
        
        Args:
            context: Context Dict von build_context()
            user_question: Frage des Users
        
        Returns:
            Messages List für LLM
        """
        
        # System Prompt - KI-Coach Persona
        system_prompt = """Du bist ein erfahrener Fitness-Coach, der einen Athleten während des Trainings betreut.

DEINE ROLLE:
- Gib präzise, kurze und praktische Tipps
- Berücksichtige den aktuellen Zustand (Ermüdung, RPE)
- Fördere sichere Technik und Progression
- Sei motivierend aber realistisch

KOMMUNIKATIONSSTIL:
- Antworte in 2-4 Sätzen (max 80 Wörter)
- Direkt und umsetzbar
- Nutze Fitness-Fachbegriffe wenn passend
- Emojis sparsam einsetzen (max 1-2)

FOKUS:
- Form & Technik > Gewicht
- RPE 7-9 für Hypertrophie
- Individuelle Anpassung basierend auf Feedback"""
        
        # User Context für Prompt
        current_ex = context.get('current_exercise')
        session = context.get('current_session', {})
        
        # Baue User Prompt
        user_context_parts = []
        
        # Aktuelle Session Info
        if session:
            user_context_parts.append(f"AKTUELLE SESSION:")
            user_context_parts.append(f"- Plan: {session.get('plan_name', 'Unbekannt')}")
            user_context_parts.append(f"- Dauer: {session.get('stats', {}).get('duration_minutes', 0)} Minuten")
            user_context_parts.append(f"- Absolvierte Sätze: {session.get('stats', {}).get('total_sets', 0)}")
            if session.get('avg_rpe'):
                user_context_parts.append(f"- Durchschnittliche RPE: {session['avg_rpe']}")
        
        # Aktuelle Übung Info
        if current_ex:
            user_context_parts.append(f"\nAKTUELLE ÜBUNG:")
            user_context_parts.append(f"- Name: {current_ex['name']}")
            user_context_parts.append(f"- Muskelgruppe: {current_ex['muskelgruppe']}")
            user_context_parts.append(f"- Absolvierte Sätze: {current_ex['completed_sets']}")
            
            if current_ex.get('current_set_number'):
                user_context_parts.append(f"- Aktueller Satz: {current_ex['current_set_number']}")
            
            if current_ex.get('last_set'):
                last = current_ex['last_set']
                if last.get('gewicht') and last.get('wiederholungen'):
                    user_context_parts.append(
                        f"- Letzter Satz: {last['gewicht']}kg × {last['wiederholungen']} Wdh @ RPE {last.get('rpe', '?')}"
                    )
        
        # User Frage
        user_context_parts.append(f"\nFRAGE: {user_question}")
        
        user_prompt = "\n".join(user_context_parts)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return messages
    
    def get_guidance(
        self,
        trainingseinheit_id: int,
        user_question: str,
        current_uebung_id: Optional[int] = None,
        current_satz_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Hauptmethode: Holt KI-Guidance für User-Frage
        
        Args:
            trainingseinheit_id: ID der aktuellen Trainingseinheit
            user_question: Frage des Users
            current_uebung_id: ID der aktuellen Übung (optional)
            current_satz_number: Satznummer (optional)
        
        Returns:
            {
                'answer': str - KI Antwort,
                'context': dict - Verwendeter Context,
                'cost': float - Kosten in Euro,
                'model': str - Verwendetes LLM
            }
        """
        from llm_client import LLMClient
        
        print(f"\n🤖 Live Guidance Request")
        print(f"   Session: {trainingseinheit_id}")
        print(f"   Übung: {current_uebung_id}")
        print(f"   Frage: {user_question}")
        
        # 1. Context sammeln
        context = self.build_context(
            trainingseinheit_id=trainingseinheit_id,
            current_uebung_id=current_uebung_id,
            current_satz_number=current_satz_number
        )
        
        # 2. Prompt erstellen
        messages = self.generate_prompt(context, user_question)
        
        # 3. LLM Call
        llm_client = LLMClient(
            use_openrouter=self.use_openrouter,
            fallback_to_openrouter=False,
            temperature=0.7
        )
        
        try:
            # Kurze Antwort (max 200 tokens)
            if self.use_openrouter:
                # OpenRouter: Nutze _generate_with_openrouter und extrahiere Text
                import openai
                from secrets_manager import get_openrouter_key
                
                client = openai.OpenAI(
                    api_key=get_openrouter_key(),
                    base_url="https://openrouter.ai/api/v1"
                )
                
                model = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-70b-instruct')
                
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=200,
                    extra_headers={
                        "HTTP-Referer": "https://gym.last-strawberry.com",
                        "X-Title": "HomeGym AI Coach"
                    }
                )
                
                answer = response.choices[0].message.content
                cost = 0.002  # Geschätzte Kosten
            else:
                # Ollama: Direkter Chat Call (kein JSON!)
                import ollama
                
                response = ollama.chat(
                    model=llm_client.model,
                    messages=messages,
                    options={
                        'temperature': 0.7,
                        'num_predict': 200,
                    }
                )
                
                answer = response['message']['content']
                model = llm_client.model
                cost = 0.0  # Lokal kostenlos
            
            print(f"   ✓ Antwort erhalten ({len(answer)} Zeichen)")
            print(f"   Model: {model if self.use_openrouter else llm_client.model}")
            print(f"   Kosten: {cost}€")
            
            return {
                'answer': answer,
                'context': context,
                'cost': cost,
                'model': model if self.use_openrouter else llm_client.model
            }
        
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {
                'answer': f"Fehler beim Generieren der Antwort: {str(e)}",
                'context': context,
                'cost': 0.0,
                'model': 'error'
            }


# CLI Testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Live Guidance")
    parser.add_argument('--session-id', type=int, required=True, help='Trainingseinheit ID')
    parser.add_argument('--exercise-id', type=int, help='Aktuelle Übung ID')
    parser.add_argument('--set-number', type=int, help='Aktueller Satz')
    parser.add_argument('--question', type=str, required=True, help='User Frage')
    parser.add_argument('--use-openrouter', action='store_true', help='OpenRouter statt Ollama')
    
    args = parser.parse_args()
    
    # Setup Django
    db_client = DatabaseClient()
    db_client.setup_django()
    
    # Live Guidance Test
    guidance = LiveGuidance(use_openrouter=args.use_openrouter)
    
    result = guidance.get_guidance(
        trainingseinheit_id=args.session_id,
        user_question=args.question,
        current_uebung_id=args.exercise_id,
        current_satz_number=args.set_number
    )
    
    print("\n" + "=" * 60)
    print("💬 KI-COACH ANTWORT")
    print("=" * 60)
    print(result['answer'])
    print("\n" + "=" * 60)
