"""
LLM Client - Ollama Integration für Trainingsplan-Generierung
Kommuniziert mit lokalem Llama 3.1 8B Model
"""

import json
import ollama
from typing import Dict, List, Any, Optional
import ai_config


class LLMClient:
    """
    Wrapper für Ollama API - generiert Trainingspläne mit Llama 3.1
    """
    
    def __init__(self, model: str = None, temperature: float = 0.7):
        """
        Args:
            model: Ollama Model Name (default: aus .env)
            temperature: Kreativität (0.0 = deterministisch, 1.0 = kreativ)
        """
        self.model = model or ai_config.OLLAMA_MODEL
        self.temperature = temperature
        
        # Validiere dass Ollama läuft
        self._check_ollama_available()
    
    def _check_ollama_available(self):
        """
        Prüft ob Ollama läuft und Model verfügbar ist
        """
        try:
            models_response = ollama.list()
            
            # Ollama list() gibt dict mit 'models' Liste zurück
            if hasattr(models_response, 'get'):
                models_list = models_response.get('models', [])
            elif hasattr(models_response, 'models'):
                models_list = models_response.models
            else:
                models_list = []
            
            # Model names extrahieren (verschiedene API Versionen)
            model_names = []
            for m in models_list:
                if hasattr(m, 'model'):
                    model_names.append(m.model)
                elif hasattr(m, 'name'):
                    model_names.append(m.name)
                elif isinstance(m, dict) and 'model' in m:
                    model_names.append(m['model'])
                elif isinstance(m, dict) and 'name' in m:
                    model_names.append(m['name'])
            
            if model_names and not any(self.model in name for name in model_names):
                raise Exception(
                    f"Model '{self.model}' nicht gefunden!\n"
                    f"Verfügbare Models: {', '.join(model_names)}\n"
                    f"Installiere mit: ollama pull {self.model}"
                )
            
            print(f"✓ Ollama Model '{self.model}' bereit")
        
        except Exception as e:
            raise Exception(f"Ollama nicht erreichbar: {e}\nStarte Ollama mit: ollama serve")
    
    def generate_training_plan(
        self, 
        messages: List[Dict[str, str]],
        max_tokens: int = 4000,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Generiert Trainingsplan via Ollama
        
        Args:
            messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            max_tokens: Maximale Response-Länge
            timeout: Timeout in Sekunden
        
        Returns:
            Parsed JSON Response als Dict
        
        Raises:
            JSONDecodeError: Wenn Response kein valides JSON ist
            Exception: Bei Ollama Errors
        """
        
        print(f"\n🤖 Generiere Trainingsplan mit {self.model}...")
        print(f"   Temperature: {self.temperature}")
        print(f"   Max Tokens: {max_tokens}")
        
        try:
            # Ollama Chat API
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': self.temperature,
                    'num_predict': max_tokens,  # max_tokens für Ollama
                }
            )
            
            # Response Content extrahieren
            content = response['message']['content']
            
            # Stats ausgeben
            total_duration = response.get('total_duration', 0) / 1e9  # Nanosekunden → Sekunden
            eval_count = response.get('eval_count', 0)  # Generated tokens
            
            print(f"✓ Response erhalten:")
            print(f"   Dauer: {total_duration:.1f}s")
            print(f"   Tokens: {eval_count}")
            print(f"   Länge: {len(content)} Zeichen\n")
            
            # JSON parsen
            plan_json = self._extract_json(content)
            
            return plan_json
        
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error: {e}")
            print("Raw Response:")
            print(content[:500])
            raise
        
        except Exception as e:
            print(f"\n❌ Ollama Error: {e}")
            raise
    
    def _extract_json(self, content: str) -> Dict[str, Any]:
        """
        Extrahiert JSON aus LLM Response
        Llama wrapped manchmal JSON in ```json ... ```
        """
        
        # Entferne markdown code blocks
        if '```json' in content:
            start = content.find('```json') + 7
            end = content.find('```', start)
            content = content[start:end].strip()
        elif '```' in content:
            start = content.find('```') + 3
            end = content.find('```', start)
            content = content[start:end].strip()
        
        # Parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: Suche nach erstem { bis letztem }
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
            raise
    
    def validate_plan(
        self, 
        plan_json: Dict[str, Any],
        available_exercises: List[str]
    ) -> tuple[bool, List[str]]:
        """
        Validiert generierten Trainingsplan
        
        Args:
            plan_json: Generierter Plan als Dict
            available_exercises: Liste verfügbarer Übungsnamen
        
        Returns:
            (valid: bool, errors: List[str])
        """
        
        errors = []
        
        # Required fields check
        required_fields = ['plan_name', 'sessions']
        for field in required_fields:
            if field not in plan_json:
                errors.append(f"Fehlendes Feld: '{field}'")
        
        # Sessions validieren
        if 'sessions' in plan_json:
            # Session-übergreifender Duplikat-Check
            all_exercises_across_sessions = []
            
            for i, session in enumerate(plan_json['sessions']):
                if 'exercises' not in session:
                    errors.append(f"Session {i+1}: Keine Übungen definiert")
                    continue
                
                # Übungen dieser Session sammeln
                session_exercises = [ex.get('exercise_name', '') for ex in session['exercises']]
                
                # Duplikat-Check INNERHALB der Session
                duplicates_in_session = [ex for ex in session_exercises if session_exercises.count(ex) > 1]
                if duplicates_in_session:
                    unique_dupes = list(set(duplicates_in_session))
                    errors.append(
                        f"Session {i+1}: Doppelte Übungen gefunden: {', '.join(unique_dupes)}"
                    )
                
                # Für Session-übergreifenden Check
                for ex_name in session_exercises:
                    all_exercises_across_sessions.append((ex_name, i+1))
                
                # Übungen validieren
                for j, exercise in enumerate(session['exercises']):
                    ex_name = exercise.get('exercise_name', '')
                    
                    # Übung existiert?
                    if ex_name not in available_exercises:
                        errors.append(
                            f"Session {i+1}, Übung {j+1}: '{ex_name}' nicht verfügbar "
                            f"(Equipment fehlt oder Übung existiert nicht)"
                        )
                    
                    # Required exercise fields
                    ex_required = ['sets', 'reps', 'order']
                    for field in ex_required:
                        if field not in exercise:
                            errors.append(
                                f"Session {i+1}, Übung {j+1} ('{ex_name}'): Fehlendes Feld '{field}'"
                            )
            
            # Duplikat-Check ÜBER alle Sessions hinweg
            seen_exercises = {}
            for ex_name, session_num in all_exercises_across_sessions:
                if ex_name in seen_exercises:
                    errors.append(
                        f"Übung '{ex_name}' kommt mehrfach vor "
                        f"(Session {seen_exercises[ex_name]} und Session {session_num})"
                    )
                else:
                    seen_exercises[ex_name] = session_num
        
        valid = len(errors) == 0
        
        if valid:
            print("✅ Plan Validation: OK")
        else:
            print(f"⚠️ Plan Validation: {len(errors)} Fehler gefunden")
            for error in errors:
                print(f"   - {error}")
        
        return valid, errors


if __name__ == "__main__":
    # Test: LLM Client mit Mock Messages
    import sys
    sys.path.insert(0, '..')
    
    print("=== LLM Client Test ===\n")
    
    try:
        # Mock Messages
        messages = [
            {
                "role": "system",
                "content": "Du bist ein Fitness Coach. Antworte mit einem JSON-Objekt."
            },
            {
                "role": "user",
                "content": """Erstelle einen simplen Test-Trainingsplan für einen User mit folgenden Übungen:
- Bankdrücken (Langhantel)
- Kniebeuge (Langhantel)
- Kreuzheben

Output als JSON:
{
  "plan_name": "Test Plan",
  "sessions": [
    {
      "day_name": "Ganzkörper",
      "exercises": [
        {
          "exercise_name": "Bankdrücken (Langhantel)",
          "sets": 3,
          "reps": "8-10",
          "order": 1
        }
      ]
    }
  ]
}"""
            }
        ]
        
        # LLM Client
        client = LLMClient(temperature=0.3)
        
        # Plan generieren
        plan = client.generate_training_plan(messages, max_tokens=1000)
        
        # Ausgabe
        print("📋 Generierter Plan:")
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        
        # Validation
        print("\n🔍 Validierung:")
        available = ["Bankdrücken (Langhantel)", "Kniebeuge (Langhantel)", "Kreuzheben"]
        valid, errors = client.validate_plan(plan, available)
        
        if not valid:
            print("\nFehler:")
            for err in errors:
                print(f"  - {err}")
    
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
