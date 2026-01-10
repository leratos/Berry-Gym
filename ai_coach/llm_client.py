"""
LLM Client - Hybrid Ollama + OpenRouter Integration
Unterstützt lokales Llama 3.1 8B mit OpenRouter 70B Fallback
"""

import json
import ollama
from typing import Dict, List, Any, Optional
from . import ai_config
import os


class LLMClient:
    """
    Hybrid LLM Wrapper - Ollama lokal + OpenRouter Fallback
    """
    
    def __init__(
        self, 
        model: str = None, 
        temperature: float = 0.7,
        use_openrouter: bool = False,
        fallback_to_openrouter: bool = True
    ):
        """
        Args:
            model: Ollama Model Name (default: aus .env)
            temperature: Kreativität (0.0 = deterministisch, 1.0 = kreativ)
            use_openrouter: True = nutze nur OpenRouter (skip Ollama)
            fallback_to_openrouter: True = nutze OpenRouter wenn Ollama fehlschlägt
        """
        self.model = model or ai_config.OLLAMA_MODEL
        self.temperature = temperature
        self.use_openrouter = use_openrouter
        self.fallback_to_openrouter = fallback_to_openrouter
        
        # OpenRouter Client (lazy init)
        self.openrouter_client = None
        
        # Ollama verfügbar?
        self.ollama_available = False
        if not use_openrouter:
            try:
                self._check_ollama_available()
                self.ollama_available = True
            except Exception as e:
                print(f"⚠️ Ollama nicht verfügbar: {e}")
                if not fallback_to_openrouter:
                    raise
                print("→ Werde OpenRouter als Fallback nutzen")
    
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
    
    def _get_openrouter_client(self):
        """Lazy init OpenRouter Client"""
        if self.openrouter_client is None:
            try:
                from openai import OpenAI
                from .secrets_manager import get_openrouter_key
                
                # Versuche API Key aus sicherer Quelle zu holen
                api_key = get_openrouter_key()
                
                if not api_key:
                    raise Exception(
                        "OPENROUTER_API_KEY nicht gefunden!\n\n"
                        "Sichere Speicherung (empfohlen):\n"
                        "  python ai_coach/secrets_manager.py set OPENROUTER_API_KEY\n\n"
                        "Oder in .env (nicht sicher):\n"
                        "  OPENROUTER_API_KEY=sk-or-v1-xxx\n\n"
                        "API Key erhältlich: https://openrouter.ai/keys"
                    )
                
                self.openrouter_client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                print("✓ OpenRouter Client bereit (Key aus sicherer Quelle)")
            except ImportError:
                raise Exception(
                    "OpenAI Package nicht installiert!\n"
                    "Installiere mit: pip install openai"
                )
        
        return self.openrouter_client
    
    def generate_training_plan(
        self, 
        messages: List[Dict[str, str]],
        max_tokens: int = 4000,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Generiert Trainingsplan - versucht erst Ollama, dann OpenRouter
        
        Args:
            messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            max_tokens: Maximale Response-Länge
            timeout: Timeout in Sekunden
        
        Returns:
            Parsed JSON Response als Dict
        
        Raises:
            Exception: Wenn beide Methoden fehlschlagen
        """
        
        # Strategie 1: OpenRouter direkt
        if self.use_openrouter:
            return self._generate_with_openrouter(messages, max_tokens)
        
        # Strategie 2: Ollama mit OpenRouter Fallback
        if self.ollama_available:
            try:
                return self._generate_with_ollama(messages, max_tokens, timeout)
            except Exception as e:
                if self.fallback_to_openrouter:
                    print(f"\n⚠️ Ollama fehlgeschlagen: {e}")
                    print("→ Versuche OpenRouter Fallback...\n")
                    return self._generate_with_openrouter(messages, max_tokens)
                else:
                    raise
        
        # Strategie 3: Nur OpenRouter (Ollama nicht verfügbar)
        if self.fallback_to_openrouter:
            return self._generate_with_openrouter(messages, max_tokens)
        
        raise Exception("Kein LLM verfügbar - weder Ollama noch OpenRouter konfiguriert")
    
    def _generate_with_ollama(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        timeout: int
    ) -> Dict[str, Any]:
        """Generiert Plan mit lokalem Ollama"""
        
        print(f"\n🤖 Generiere mit Ollama ({self.model})...")
        print(f"   Temperature: {self.temperature}")
        print(f"   Max Tokens: {max_tokens}")
        
        try:
            # Ollama Chat API
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': self.temperature,
                    'num_predict': max_tokens,
                }
            )
            
            # Response Content extrahieren
            content = response['message']['content']
            
            # Stats ausgeben
            total_duration = response.get('total_duration', 0) / 1e9
            eval_count = response.get('eval_count', 0)
            
            print(f"✓ Ollama Response:")
            print(f"   Dauer: {total_duration:.1f}s")
            print(f"   Tokens: {eval_count}")
            print(f"   Länge: {len(content)} Zeichen")
            print(f"   Kosten: 0€ (lokal)\n")
            
            # JSON parsen und mit Metadaten zurückgeben
            return {
                'response': self._extract_json(content),
                'cost': 0.0,
                'model': self.model,
                'tokens': eval_count
            }
        
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error: {e}")
            print("Raw Response:")
            print(content[:500])
            raise
        
        except Exception as e:
            print(f"\n❌ Ollama Error: {e}")
            raise
    
    def _generate_with_openrouter(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int
    ) -> Dict[str, Any]:
        """Generiert Plan mit OpenRouter (70B Remote)"""
        
        client = self._get_openrouter_client()
        model = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-70b-instruct')
        
        print(f"\n🌐 Generiere mit OpenRouter ({model})...")
        print(f"   Temperature: {self.temperature}")
        print(f"   Max Tokens: {max_tokens}")
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                extra_headers={
                    "HTTP-Referer": "https://gym.last-strawberry.com",
                    "X-Title": "HomeGym AI Coach"
                }
            )
            
            content = response.choices[0].message.content
            
            # Stats ausgeben
            tokens_used = response.usage.total_tokens
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            
            # Kosten berechnen (OpenRouter Llama 3.1 70B)
            cost_input = (prompt_tokens / 1_000_000) * 0.60
            cost_output = (completion_tokens / 1_000_000) * 0.80
            total_cost = cost_input + cost_output
            
            print(f"✓ OpenRouter Response:")
            print(f"   Tokens: {tokens_used} (in: {prompt_tokens}, out: {completion_tokens})")
            print(f"   Länge: {len(content)} Zeichen")
            print(f"   Kosten: {total_cost:.4f}€ (~{total_cost*100:.2f} Cent)\n")
            
            # JSON parsen und mit Metadaten zurückgeben
            return {
                'response': self._extract_json(content),
                'cost': total_cost,
                'model': model,
                'tokens': tokens_used
            }
        
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error: {e}")
            print("Raw Response:")
            print(content[:500])
            raise
        
        except Exception as e:
            print(f"\n❌ OpenRouter Error: {e}")
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
