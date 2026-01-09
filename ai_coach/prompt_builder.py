"""
Prompt Builder - Erstellt strukturierte Prompts für LLM
"""

from typing import Dict, List, Any


class PromptBuilder:
    
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """Du bist ein professioneller Trainingsplan-Generator.

**Output Format:**
Deine Antwort MUSS ein valides JSON-Objekt sein mit dieser Struktur:
```json
{
  "plan_name": "Beschreibender Name (z.B. '3er-Split: Push/Pull/Legs - Woche 1-4')",
  "plan_description": "Kurze Beschreibung und Ziele",
  "duration_weeks": 4,
  "sessions": [
    {
      "day_name": "Push (Brust/Schultern/Trizeps)",
      "exercises": [
        {
          "exercise_name": "Bankdrücken (Langhantel)",
          "sets": 4,
          "reps": "8-10",
          "rpe_target": 8,
          "order": 1,
          "notes": "Hauptübung, progressive Overload"
        }
      ]
    }
  ],
  "weekly_structure": "Beschreibung des Wochenplans",
  "progression_notes": "Wie soll der User progressiv steigern"
}
```

**KRITISCH - ÜBUNGSNAMEN:**
- Der "exercise_name" MUSS **EXAKT WORD-FOR-WORD** aus der verfügbaren Übungsliste kopiert werden!
- **KEINE Variationen, Übersetzungen oder Umformulierungen!**
- Beispiel RICHTIG: "Kniebeuge (Langhantel, Back Squat)" ✅
- Beispiel FALSCH: "Langhantel Kniebeuge" ❌
- Beispiel FALSCH: "Back Squat" ❌
- **COPY & PASTE** die Namen exakt wie sie in der Liste stehen!

**Weitere Anforderungen:**
- Antworte NUR mit dem JSON-Objekt, kein zusätzlicher Text!
- Berücksichtige die Schwachstellen und Trainingsziele
- Achte auf realistische Satz/Wdh-Vorgaben basierend auf Historie"""
    
    def build_user_prompt(
        self, 
        analysis_data: Dict[str, Any],
        available_exercises: List[str],
        plan_type: str = "3er-split",
        sets_per_session: int = 18
    ) -> str:
        # Plan-Type spezifische Anweisungen
        plan_instructions = {
            "3er-split": "Erstelle einen 3er-Split (z.B. Push/Pull/Legs oder Oberkörper/Unterkörper/Ganzkörper)",
            "4er-split": "Erstelle einen 4er-Split (z.B. Brust+Trizeps, Rücken+Bizeps, Schultern+Bauch, Beine)",
            "ppl": "Erstelle einen Push/Pull/Legs Split (6x pro Woche möglich)",
            "upper-lower": "Erstelle einen Upper/Lower Split (4x pro Woche)",
            "fullbody": "Erstelle einen Ganzkörper-Plan (3x pro Woche)"
        }
        
        instruction = plan_instructions.get(plan_type, plan_instructions["3er-split"])
        
        # Trainingsfrequenz
        freq = analysis_data['training_stats']['frequency_per_week']
        freq_note = ""
        if freq < 2:
            freq_note = "User trainiert sehr selten! Plan sollte effizient sein (Compound Movements priorisieren)."
        elif freq < 3:
            freq_note = "User trainiert 2-3x pro Woche - Ganzkörper oder Upper/Lower empfohlen."
        elif freq < 5:
            freq_note = "User trainiert 3-4x pro Woche - 3er oder 4er Split empfohlen."
        else:
            freq_note = "User trainiert häufig - 5er Split oder PPL möglich."
        
        # Push/Pull Balance
        balance = analysis_data['push_pull_balance']
        balance_note = "Balanced" if balance['balanced'] else f"Unbalanced (Ratio: {balance['ratio']})"
        
        # Top 5 Muskelgruppen nach Volumen
        mg_sorted = sorted(
            analysis_data['muscle_groups'].items(),
            key=lambda x: x[1]['effective_reps'],
            reverse=True
        )[:5]
        top_muscles = ", ".join([f"{mg} ({int(data['effective_reps'])} eff.Wdh)" for mg, data in mg_sorted])
        
        # Schwachstellen
        weaknesses_str = "\n".join([f"  - {w}" for w in analysis_data['weaknesses'][:5]])
        
        # Few-shot examples mit EXAKTEN Namen aus der Liste
        example_exercises = [ex for ex in available_exercises if any(kw in ex for kw in ['Bankdrücken', 'Kniebeuge', 'Kreuzheben'])][:3]
        examples_str = "\n".join([f'  "{ex}"' for ex in example_exercises])
        
        # Build prompt
        exercises_list = "\n".join([f"  - {ex}" for ex in sorted(available_exercises)])
        
        prompt = f"""**TRAININGSANALYSE**

**User ID:** {analysis_data['user_id']}
**Analysezeitraum:** {analysis_data['analysis_period']}

**Trainingsfrequenz:**
- Sessions gesamt: {analysis_data['training_stats']['total_sessions']}
- Pro Woche: {freq}x
- Durchschnitt: {analysis_data['training_stats']['avg_duration_minutes']} Minuten
{freq_note}

**Muskelgruppen (Top 5 nach Volumen):**
{top_muscles}

**Push/Pull Balance:**
- Push: {balance['push_volume']} | Pull: {balance['pull_volume']}
- Ratio: {balance['ratio']} - {balance_note}

**Schwachstellen:**
{weaknesses_str}

**VERFÜGBARE ÜBUNGEN ({len(available_exercises)}):**
** WICHTIG:** Verwende die Namen **EXAKT** wie unten aufgelistet - KEIN Umformulieren!

Beispiele für KORREKTE Namen (kopiere exakt so):
{examples_str}

**VOLLSTÄNDIGE LISTE** (wähle aus diesen):
{exercises_list}

** NOCHMAL: Kopiere die "exercise_name" Werte EXAKT aus der Liste oben!**
Beispiel: Wenn du "Kniebeuge (Langhantel, Back Squat)" verwenden willst, schreibe EXAKT:
  "exercise_name": "Kniebeuge (Langhantel, Back Squat)"

NICHT schreiben: "Langhantel Kniebeuge", "Back Squat", oder andere Variationen!

**AUFGABE:**
{instruction}

**Anforderungen:**
1. Berücksichtige die Schwachstellen und priorisiere untertrainierte Muskelgruppen
2. Verwende NUR Übungen aus der Liste verfügbarer Übungen
3. Achte auf Push/Pull Balance (bei Unbalance gegensteuern)
4. SATZ-BUDGET: {sets_per_session} Sätze pro Trainingstag (ca. 1 Stunde Training)
   - Nutze das KOMPLETTE Satz-Budget aus (nicht weniger!)
   - Verteile die Sätze auf 5-6 Übungen
   - Beispiel Push-Tag (18 Sätze):
     * Brust Übung 1: 4 Sätze
     * Brust Übung 2: 3 Sätze
     * Schultern Übung 1: 3 Sätze
     * Schultern Übung 2: 3 Sätze
     * Trizeps Übung 1: 3 Sätze
     * Trizeps Übung 2: 2 Sätze
     = 18 Sätze total, 6 Übungen
5. ** MINDESTENS 2 ÜBUNGEN PRO HAUPTMUSKELGRUPPE**:
   - Push-Tag: 2x Brust, 2x Schultern, 2x Trizeps
   - Pull-Tag: 2x Rücken, 2x Latissimus, 1-2x Bizeps
   - Leg-Tag: 2x Quadrizeps, 2x Hamstrings, 1x Waden/Po
   - Verschiedene Winkel/Bewegungen für vollständige Entwicklung
6. Compound Movements (Langhantel-Kniebeuge, Bankdrücken, Kreuzheben) priorisieren als erste Übung
7. RPE-Targets: 7-9 für Hypertrophie, Compound Movements können RPE 8-9 haben
8. ** KEINE DOPPELTEN ÜBUNGEN**: Jede Übung darf nur EINMAL im GESAMTEN Plan vorkommen (nicht in mehreren Sessions wiederholen)!
9. Output: Valides JSON wie im System Prompt beschrieben

Erstelle jetzt den optimalen Trainingsplan:"""
        
        return prompt
    
    def build_messages(
        self,
        analysis_data: Dict[str, Any],
        available_exercises: List[str],
        plan_type: str = "3er-split",
        sets_per_session: int = 18
    ) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_user_prompt(analysis_data, available_exercises, plan_type, sets_per_session)}
        ]
    
    def get_available_exercises_for_user(self, user_id: int) -> List[str]:
        from core.models import Uebung
        from django.contrib.auth.models import User
        
        user = User.objects.get(id=user_id)
        user_equipment_ids = set(user.verfuegbares_equipment.values_list('id', flat=True))
        
        available_exercises = []
        
        for uebung in Uebung.objects.prefetch_related('equipment'):
            required_eq_ids = set(uebung.equipment.values_list('id', flat=True))
            
            if not required_eq_ids or required_eq_ids.issubset(user_equipment_ids):
                available_exercises.append(uebung.bezeichnung)
        
        return sorted(available_exercises)


if __name__ == "__main__":
    print("Prompt Builder Test")
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from db_client import DatabaseClient
        from data_analyzer import TrainingAnalyzer
        
        with DatabaseClient() as db:
            analyzer = TrainingAnalyzer(user_id=2, days=30)
            analysis_data = analyzer.analyze()
            
            builder = PromptBuilder()
            available_exercises = builder.get_available_exercises_for_user(2)
            
            print(f"\n{len(available_exercises)} verfügbare Übungen")
            
            messages = builder.build_messages(
                analysis_data=analysis_data,
                available_exercises=available_exercises,
                plan_type="3er-split",
                sets_per_session=18
            )
            
            print("Messages Array fertig für Ollama!")
            print(f"   - System Prompt: {len(messages[0]['content'])} Zeichen")
            print(f"   - User Prompt: {len(messages[1]['content'])} Zeichen")
    
    except Exception as e:
        print(f"\nFehler: {e}")
        import traceback
        traceback.print_exc()
