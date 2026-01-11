"""
Prompt Builder - Erstellt strukturierte Prompts für LLM
"""

from typing import Dict, List, Any


class PromptBuilder:
    
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """Du bist ein professioneller Trainingsplan-Generator.

**ABSOLUTE REGEL #1 - ÜBUNGSNAMEN:**
⚠️ Du darfst AUSSCHLIESSLICH Übungen aus der vom User bereitgestellten Liste verwenden!
⚠️ Der "exercise_name" MUSS **EXAKT BUCHSTABE-FÜR-BUCHSTABE** aus der verfügbaren Übungsliste kopiert werden!
⚠️ KEINE Variationen, KEINE Übersetzungen, KEINE Umformulierungen, KEINE eigenen Übungen!

**Beispiele für KORREKTE Verwendung:**
✅ Liste enthält: "Kniebeuge (Langhantel, Back Squat)"
   → Du schreibst: "exercise_name": "Kniebeuge (Langhantel, Back Squat)"

❌ FALSCH: "Langhantel Kniebeuge" (anders formuliert)
❌ FALSCH: "Back Squat" (unvollständig)
❌ FALSCH: "Squat mit Langhantel" (eigene Formulierung)
❌ FALSCH: "Incline Dumbbell Press (Kurzhantel)" (nicht in Liste)

**KRITISCH:** Wenn eine Übung NICHT in der Liste ist, darfst du sie NICHT verwenden!
Erfinde NIEMALS eigene Übungsnamen! Nutze nur die bereitgestellte Liste!

**Output Format:**
Deine Antwort MUSS ein valides JSON-Objekt sein:
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
          "exercise_name": "EXAKTER NAME AUS LISTE - KOPIERE WORD-FOR-WORD!",
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

**DUPLIKATE & PROGRESSION:**
- ❌ KEINE Duplikate INNERHALB EINER SESSION (jede Übung nur 1x pro Tag)
- ✅ ÜBER MEHRERE SESSIONS sind identische Übungen ERLAUBT und ERWÜNSCHT (Progression!)
- Erstelle eine EINWÖCHIGE Session-Struktur, die für 4 Wochen verwendet wird
- Übungen & Reihenfolge bleiben gleich, Progression kommt in progression_notes

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
        # Plan-Type spezifische Anweisungen (Frontend-kompatible Keys)
        plan_instructions = {
            "2er-split": "Erstelle einen 2er-Split (z.B. Oberkörper/Unterkörper oder Push/Pull)",
            "3er-split": "Erstelle einen 3er-Split (z.B. Push/Pull/Legs oder Oberkörper/Unterkörper/Ganzkörper)",
            "4er-split": "Erstelle einen 4er-Split (z.B. Brust+Trizeps, Rücken+Bizeps, Schultern+Bauch, Beine)",
            "push-pull-legs": "Erstelle einen Push/Pull/Legs Split (6x pro Woche möglich)",
            "ganzkörper": "Erstelle einen Ganzkörper-Plan (2-3x pro Woche, alle Muskelgruppen pro Session)"
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
        
        # Satzbudget als Range (Flexibilität für LLM)
        min_sets = max(10, sets_per_session - 4)
        max_sets = sets_per_session
        
        # Coach-Sicherheitsregeln
        coach_rules = """**🏥 COACH-SICHERHEITSREGELN (MUST):**
- Wenn Bankdrücken ODER Schulterdrücken im Push-Tag: KEINE Front Raises (Überlastung vordere Schulter)
- Kreuzheben (conventional): max. 3 Sätze ODER max. 15 Gesamtwiederholungen pro Woche
- Pro Woche 2-4 Sätze hintere Schulter / Scapula-Hygiene (Face Pulls, Reverse Flys, etc.)
- Kein Lower-Back-Overkill: Vermeide Kreuzheben + RDL + schwere Squats am selben Tag"""
        
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

═══════════════════════════════════════════════════════════
⚠️  KRITISCH: VERFÜGBARE ÜBUNGEN - NUR DIESE VERWENDEN! ⚠️
═══════════════════════════════════════════════════════════

Du hast {len(available_exercises)} verfügbare Übungen.
** DU DARFST AUSSCHLIESSLICH AUS DIESER LISTE WÄHLEN!**
** KEINE EIGENEN ÜBUNGEN ERFINDEN!**
** KOPIERE DIE NAMEN EXAKT - BUCHSTABE FÜR BUCHSTABE!**

**Beispiele für KORREKTE Verwendung (kopiere exakt so):**
{examples_str}

**VOLLSTÄNDIGE LISTE ALLER VERFÜGBAREN ÜBUNGEN:**
{exercises_list}

═══════════════════════════════════════════════════════════
⚠️  NOCHMAL: KEINE ÜBUNG VERWENDEN, DIE NICHT OBEN STEHT! ⚠️
═══════════════════════════════════════════════════════════

Wenn du z.B. "Incline Dumbbell Press (Kurzhantel)" verwenden willst:
→ Prüfe ob GENAU dieser Text in der Liste oben steht!
→ Falls NEIN: Verwende eine andere ähnliche Übung aus der Liste!
→ Falls JA: Kopiere den Namen EXAKT!

**AUFGABE:**
{instruction}

{coach_rules}

**Anforderungen:**
1. ** VERWENDE NUR ÜBUNGEN AUS DER OBIGEN LISTE** - keine anderen!
2. Berücksichtige die Schwachstellen und priorisiere untertrainierte Muskelgruppen
3. Achte auf Push/Pull Balance (bei Unbalance gegensteuern)
4. SATZ-BUDGET: {min_sets}-{max_sets} Sätze pro Trainingstag (ca. 1 Stunde Training)
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
8. ** DUPLIKATE**: ❌ KEINE doppelten Übungen INNERHALB einer Session! ✅ ABER gleiche Übungen in verschiedenen Sessions sind ERWÜNSCHT (für Progression über 4 Wochen)!
9. Output: Valides JSON wie im System Prompt beschrieben
10. ** KOPIERE DIE EXERCISE_NAME WERTE EXAKT AUS DER LISTE - KEINE VARIATIONEN!**

Erstelle jetzt den optimalen Trainingsplan (NUR JSON, kein anderer Text):"""
        
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
