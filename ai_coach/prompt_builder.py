"""
Prompt Builder - Erstellt strukturierte Prompts für LLM
"""

from typing import Any, Dict, List, Optional

# Mapping: Analyzer-Label (lowercase) → DB-Muskelgruppen-Keys
# Gleiche Quelle wie plan_generator._validate_weakness_coverage
WEAKNESS_LABEL_TO_KEYS: Dict[str, List[str]] = {
    "brust": ["BRUST"],
    "rücken": ["RUECKEN_LAT", "RUECKEN_TRAPEZ", "RUECKEN_UNTEN", "RUECKEN_OBERER"],
    "beine": ["BEINE_QUAD", "BEINE_HAM", "PO", "WADEN", "ADDUKTOREN", "ABDUKTOREN", "HUEFTBEUGER"],
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
}

# Lesbare Namen für DB-Keys (für Prompt-Ausgabe)
KEY_TO_DISPLAY: Dict[str, str] = {
    "BAUCH": "Bauch / Core",
    "ADDUKTOREN": "Adduktoren (Oberschenkel Innen)",
    "ABDUKTOREN": "Abduktoren (Oberschenkel Außen)",
    "HUEFTBEUGER": "Hüftbeuger",
    "BEINE_QUAD": "Quadrizeps",
    "BEINE_HAM": "Hamstrings",
    "PO": "Gesäß",
    "WADEN": "Waden",
    "BRUST": "Brust",
    "RUECKEN_LAT": "Latissimus",
    "RUECKEN_OBERER": "Oberer Rücken",
    "RUECKEN_TRAPEZ": "Trapez",
    "RUECKEN_UNTEN": "Unterer Rücken",
    "SCHULTER_VORN": "Vordere Schulter",
    "SCHULTER_SEIT": "Seitliche Schulter",
    "SCHULTER_HINT": "Hintere Schulter",
    "BIZEPS": "Bizeps",
    "TRIZEPS": "Trizeps",
    "UNTERARME": "Unterarme",
}


_PROFILE_DEFAULTS = {
    "kraft": {"rep_range": "3-6", "rpe_range": "7.5-9"},
    "hypertrophie": {"rep_range": "6-12", "rpe_range": "7-8.5"},
    "definition": {"rep_range": "10-15", "rpe_range": "6.5-8"},
}


def _build_periodization_note(periodization: str, target_profile: str) -> str:
    """Phase 13.3: Dynamische Periodisierungs-Beschreibung.

    Kombiniert Periodisierungs-Typ und Zielprofil zu spezifischem Text
    statt hardcodierter Einheitsbeschreibung.
    """
    defaults = _PROFILE_DEFAULTS.get(target_profile, _PROFILE_DEFAULTS["hypertrophie"])
    rpe_range = defaults["rpe_range"]
    rep_range = defaults["rep_range"]

    # Profil-spezifische Progression
    if target_profile == "kraft":
        progression = (
            f"Steigere Gewicht wenn RPE < {rpe_range.split('-')[0]} bei 2+ Trainings, "
            f"Wdh-Range {rep_range}, lange Pausen (150-180s)"
        )
    elif target_profile == "definition":
        progression = (
            f"Halte Gewicht stabil, reduziere Pausen schrittweise, "
            f"Wdh-Range {rep_range}, RPE {rpe_range}, kürzere Pausen (60-90s)"
        )
    else:
        rep_upper = rep_range.split("-")[-1]
        progression = (
            f"Steigere Gewicht wenn >{rep_upper} Wdh bei RPE {rpe_range}, "
            f"+1 Satz auf Hauptübungen in Nicht-Deload-Wochen"
        )

    # Periodisierungs-spezifischer Aufbau
    if periodization == "wellenfoermig":
        structure = "Wellenförmig: Heavy/Medium/Light innerhalb jedes 4-Wochen-Blocks"
    elif periodization == "block":
        structure = "Blockperiodisierung: Block 1 Volumen, Block 2 Kraft, Block 3 Peaking"
    else:
        structure = "Linear steigende Intensität pro Block"

    return f"{structure} + Deload in Woche 4/8/12. Progression: {progression}"


class PromptBuilder:

    def __init__(self):
        self.system_prompt = self._build_system_prompt()

    def _get_exercises_for_keys(
        self, muscle_keys: List[str], available_exercises: List[str]
    ) -> List[str]:
        """Gibt verfügbare Übungen zurück die eine der angegebenen Muskelgruppen trainieren."""
        try:
            from core.models import Uebung

            matches = list(
                Uebung.objects.filter(
                    muskelgruppe__in=muscle_keys,
                    bezeichnung__in=available_exercises,
                )
                .values_list("bezeichnung", flat=True)
                .order_by("bezeichnung")
            )
            return matches
        except Exception:
            return []

    def _build_weakness_block(
        self, weaknesses: List[str], available_exercises: List[str]
    ) -> Optional[str]:
        """
        Baut einen zwingenden Pflicht-Block für untertrainierte Muskelgruppen.
        Enthält konkrete Übungen aus der verfügbaren Liste.
        Gibt None zurück wenn keine relevanten Schwachstellen gefunden.
        """
        if not weaknesses:
            return None

        mandatory_items = []

        for weakness in weaknesses:
            # Format: "Bauch: Untertrainiert (nur X eff. Wdh vs. Ø Y)"
            # Nur Muskelgruppen-Schwachstellen, keine "Nicht trainiert seit X Tagen"
            if ":" not in weakness or "Untertrainiert" not in weakness:
                continue

            label = weakness.split(":")[0].strip()
            label_lower = label.lower()
            keys = WEAKNESS_LABEL_TO_KEYS.get(label_lower)
            if not keys:
                continue

            exercises_for_group = self._get_exercises_for_keys(keys, available_exercises)
            display_name = KEY_TO_DISPLAY.get(keys[0], label)

            # Zeige max. 5 Übungen als konkrete Auswahl
            ex_list = exercises_for_group[:5]
            if not ex_list:
                # Kein passendes Equipment → trotzdem Hinweis, aber ohne konkrete Übungen
                mandatory_items.append(
                    f"❗ {display_name.upper()} – PFLICHT: mind. 1 Übung\n"
                    f"   (Keine passende Übung in verfügbarer Equipment-Liste – "
                    f"trotzdem versuchen!)"
                )
            else:
                ex_lines = "\n".join(f'   → "{ex}"' for ex in ex_list)
                mandatory_items.append(
                    f"❗ {display_name.upper()} – PFLICHT: mind. 1 Übung aus dieser Liste:\n"
                    f"{ex_lines}"
                )

        if not mandatory_items:
            return None

        items_str = "\n\n".join(mandatory_items)
        return f"""🚨🚨🚨 PFLICHT-ANFORDERUNG #0 – HÖCHSTE PRIORITÄT 🚨🚨🚨

Folgende Muskelgruppen sind CHRONISCH UNTERTRAINIERT.
Sie MÜSSEN im fertigen Plan mit mind. 1 Übung vertreten sein.
Diese Anforderung hat VORRANG vor allen anderen strukturellen Regeln!

{items_str}

⛔ FEHLER wenn diese Muskelgruppen im Plan FEHLEN.
✅ Notfalls Sätze von anderen Gruppen KÜRZEN um Platz zu schaffen.
⚠️ ADDUKTOREN ≠ ABDUKTOREN: Adduktoren = Oberschenkel INNEN (Sumo Squats, Adduktoren-Maschine)
⚠️ ABDUKTOREN = Oberschenkel AUSSEN (Hip Abduction) – das ist NICHT dasselbe!
⚠️ Jede Pflicht-Schwachstelle braucht einen EIGENEN Übungsslot – nicht kombinieren!
"""

    def _build_system_prompt(self) -> str:
        return """Du bist ein professioneller Trainingsplan-Generator.

**ABSOLUTE REGEL #1 - ÜBUNGSNAMEN:**
⚠️ Du darfst AUSSCHLIESSLICH Übungen aus der vom User bereitgestellten Liste verwenden!
⚠️ Der "exercise_name" MUSS **EXAKT BUCHSTABE-FÜR-BUCHSTABE** aus der verfügbaren Übungsliste kopiert werden!
⚠️ KEINE Variationen, KEINE Übersetzungen, KEINE Umformulierungen, KEINE eigenen Übungen!

**ABSOLUTE REGEL #2 - JSON FORMAT:**
⚠️ "reps" MUSS ein STRING sein: "8-12" NICHT 8-12
⚠️ Alle Zahlen-Bereiche in Anführungszeichen: "6-8", "10-12", etc.
⚠️ Einzelne Zahlen können Integers sein: "sets": 3

**Beispiele für KORREKTE Verwendung:**
✅ Liste enthält: "Kniebeuge (Langhantel, Back Squat)"
   → Du schreibst: "exercise_name": "Kniebeuge (Langhantel, Back Squat)"

❌ FALSCH: "Langhantel Kniebeuge" (anders formuliert)
❌ FALSCH: "Back Squat" (unvollständig)
❌ FALSCH: "Squat mit Langhantel" (eigene Formulierung)
❌ FALSCH: "Incline Dumbbell Press (Kurzhantel)" (nicht in Liste)
❌ FALSCH: "reps": 8-12 (MUSS "reps": "8-12" sein!)

**KRITISCH:** Wenn eine Übung NICHT in der Liste ist, darfst du sie NICHT verwenden!
Erfinde NIEMALS eigene Übungsnamen! Nutze nur die bereitgestellte Liste!

**Output Format:**
Deine Antwort MUSS ein valides JSON-Objekt sein:
```json
{
  "plan_name": "Beschreibender Name (z.B. '3er-Split: Push/Pull/Legs - Woche 1-4')",
  "plan_description": "Kurze Beschreibung und Ziele",
  "duration_weeks": 12,
  "periodization": "linear | wellenfoermig | block",
  "target_profile": "kraft | hypertrophie | definition",
  "deload_weeks": [4, 8, 12],
  "macrocycle": {
    "duration_weeks": 12,
    "weeks": [
      {"week": 1, "focus": "Volumenaufbau", "volume_multiplier": 1.0, "intensity_target_rpe": 7.8, "notes": "Baseline"},
      {"week": 4, "focus": "Deload", "is_deload": true, "volume_multiplier": 0.8, "intensity_target_rpe": 6.8, "notes": "Volumen -20%, Intensität -10%"}
    ]
  },
  "microcycle_template": {
    "rep_range": "6-12",
    "rpe_range": "7-8.5",
    "set_progression": "+1 Satz pro Hauptübung in Nicht-Deload-Wochen, nach Deload reset",
    "deload_rules": "Woche 4/8/12: Volumen 80%, Intensität 90%"
  },
  "progression_strategy": {
    "auto_load": "Wenn RPE < Ziel -0.5 zweimal → +2.5-5% Gewicht. Wenn RPE > Ziel +0.5 → -5% Gewicht oder 1 Satz weniger.",
    "volume": "Nutze das Satzbudget voll aus, +1 Satz auf Hauptübungen in Nicht-Deload-Wochen",
    "after_deload": "Starte mit Basisvolumen, Woche nach Deload Re-Akklimatisierung"
  },
  "sessions": [
    {
      "day_name": "Push (Brust/Schultern/Trizeps)",
      "exercises": [
        {
          "exercise_name": "EXAKTER NAME AUS LISTE - KOPIERE WORD-FOR-WORD!",
          "sets": 4,
          "reps": "8-10",
          "rpe_target": 8,
          "rest_seconds": 120,
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
- Erstelle eine EINWÖCHIGE Session-Struktur, die für den 12-Wochen-Makrozyklus verwendet wird (inkl. Deload-Wochen)
- Übungen & Reihenfolge bleiben gleich, Progression kommt in progression_notes

**PAUSENZEITEN (rest_seconds):**
- Schwere Compound-Übungen (Kniebeugen, Kreuzheben, Bankdrücken): 150-180s
- Mittlere Compound-Übungen (Rudern, Schulterdrücken): 90-120s
- Isolation/Accessories (Bizeps, Trizeps, Waden): 60-90s
- Bei Kraft-Fokus: +30s, bei Definition-Fokus: -30s

**Weitere Anforderungen:**
- Berücksichtige die Schwachstellen und Trainingsziele
- Achte auf realistische Satz/Wdh-Vorgaben basierend auf Historie"""

    def build_user_prompt(
        self,
        analysis_data: Dict[str, Any],
        available_exercises: List[str],
        plan_type: str = "3er-split",
        sets_per_session: int = 18,
        target_profile: str = "hypertrophie",
        periodization: str = "linear",
    ) -> str:
        # Plan-Type spezifische Anweisungen (Frontend-kompatible Keys)
        plan_instructions = {
            "2er-split": "Erstelle einen 2er-Split (z.B. Oberkörper/Unterkörper oder Push/Pull)",
            "3er-split": "Erstelle einen 3er-Split (z.B. Push/Pull/Legs oder Oberkörper/Unterkörper/Ganzkörper)",
            "4er-split": "Erstelle einen 4er-Split (z.B. Brust+Trizeps, Rücken+Bizeps, Schultern+Bauch, Beine)",
            "ppl": "Erstelle einen Push/Pull/Legs Split (6x pro Woche möglich)",
            "push-pull-legs": "Erstelle einen Push/Pull/Legs Split (6x pro Woche möglich)",
            "ganzkörper": "Erstelle einen Ganzkörper-Plan (2-3x pro Woche, alle Muskelgruppen pro Session)",
        }

        instruction = plan_instructions.get(plan_type, plan_instructions["3er-split"])

        # Trainingsfrequenz
        freq = analysis_data["training_stats"]["frequency_per_week"]
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
        balance = analysis_data["push_pull_balance"]
        balance_note = (
            "Balanced" if balance["balanced"] else f"Unbalanced (Ratio: {balance['ratio']})"
        )

        # Top 5 Muskelgruppen nach Volumen
        mg_sorted = sorted(
            analysis_data["muscle_groups"].items(),
            key=lambda x: x[1]["effective_reps"],
            reverse=True,
        )[:5]
        top_muscles = ", ".join(
            [f"{mg} ({int(data['effective_reps'])} eff.Wdh)" for mg, data in mg_sorted]
        )

        # Schwachstellen-Pflicht-Block (höchste Priorität)
        weakness_block = self._build_weakness_block(
            analysis_data["weaknesses"][:5], available_exercises
        )
        weakness_section = (weakness_block + "\n\n") if weakness_block else ""

        # Schwachstellen für allgemeine Info-Anzeige (kompakt)
        weaknesses_str = "\n".join([f"  - {w}" for w in analysis_data["weaknesses"][:5]])

        # Few-shot examples mit EXAKTEN Namen aus der Liste
        example_exercises = [
            ex
            for ex in available_exercises
            if any(kw in ex for kw in ["Bankdrücken", "Kniebeuge", "Kreuzheben"])
        ][:3]
        # Fallback: erste 3 verfügbare Übungen wenn keine Standard-Compounds vorhanden
        if not example_exercises:
            example_exercises = available_exercises[:3]
        examples_str = "\n".join([f'  "{ex}"' for ex in example_exercises])

        # Satzbudget als Range (Flexibilität für LLM)
        min_sets = max(10, sets_per_session - 4)
        max_sets = sets_per_session

        # Coach-Sicherheitsregeln
        coach_rules = """**🏥 COACH-SICHERHEITSREGELN (MUST):**
- Wenn Bankdrücken ODER Schulterdrücken im Push-Tag: KEINE Front Raises (Überlastung vordere Schulter)
- Kreuzheben (conventional): max. 3 Sätze ODER max. 15 Gesamtwiederholungen pro Woche
- Pro Woche 2-4 Sätze hintere Schulter / Scapula-Hygiene (wähle aus verfügbarer Übungsliste)
- Kein Lower-Back-Overkill: Vermeide Kreuzheben + RDL + schwere Squats am selben Tag
- Pull-Tag: max. 1 horizontales Ruder (Langhantelrudern ODER Einarmiges Kurzhantelrudern – NICHT beides!)
  → zweite Rückenübung muss vertikaler Zug (Klimmzüge, Latzug) oder Oberer-Rücken-Übung sein
- Legs-Tag: Waden optional – nur wenn nach Pflicht-Schwachstellen noch Budget übrig ist"""

        # Build prompt
        exercises_list = "\n".join([f"  - {ex}" for ex in sorted(available_exercises)])

        profile_guides = {
            "kraft": "3-6 Wdh, RPE 7.5-9, lange Pausen, Compounds priorisieren",
            "hypertrophie": "6-12 Wdh, RPE 7-8.5, moderates Volumen, 5-6 Übungen/Tag",
            "definition": "10-15 Wdh, RPE 6.5-8, kürzere Pausen, metabolische Arbeit inkl. Core/Cardio",
        }

        # Für eindeutigen Plan-Namen: Top-Schwachstelle extrahieren
        top_weakness_label = ""
        if analysis_data["weaknesses"]:
            first = analysis_data["weaknesses"][0]
            if ":" in first:
                top_weakness_label = first.split(":")[0].strip()

        profile_label = {
            "kraft": "Kraft",
            "hypertrophie": "Hypertrophie",
            "definition": "Definition",
        }.get(target_profile, target_profile.capitalize())
        split_label = plan_type.upper().replace("-", "/")
        from datetime import date as _date

        today_str = _date.today().strftime("%d.%m.%Y")
        name_example = (
            f"{profile_label}-{split_label} – Fokus {top_weakness_label} ({today_str})"
            if top_weakness_label
            else f"{profile_label}-{split_label} ({today_str})"
        )

        # Phase 13.3: Dynamische Periodisierungs-Beschreibung
        # Kombiniert target_profile + periodization statt hardcodiertem Text
        periodization_note = _build_periodization_note(periodization, target_profile)

        # Frequenz-basierte Split-Empfehlung
        if freq < 2:
            freq_split_hint = f"⚠️ {freq}x/Woche: Ganzkörper-Plan empfohlen, kein Split!"
        elif freq <= 3:
            freq_split_hint = f"ℹ️ {freq}x/Woche: 2er- oder 3er-Split optimal. PPL nur wenn 3x."
        elif freq <= 4:
            freq_split_hint = f"ℹ️ {freq}x/Woche: 3er- oder 4er-Split optimal."
        else:
            freq_split_hint = f"ℹ️ {freq}x/Woche: PPL oder 4er-Split optimal."

        prompt = f"""**TRAININGSANALYSE**

**User ID:** {analysis_data['user_id']}
**Analysezeitraum:** {analysis_data['analysis_period']}

**Trainingsfrequenz:**
- Sessions gesamt: {analysis_data['training_stats']['total_sessions']}
- Pro Woche: {freq}x
- Durchschnitt: {analysis_data['training_stats']['avg_duration_minutes']} Minuten
- {freq_split_hint}
{freq_note}

**Muskelgruppen (Top 5 nach Volumen):**
{top_muscles}

**Push/Pull Balance:**
- Push: {balance['push_volume']} | Pull: {balance['pull_volume']}
- Ratio: {balance['ratio']} - {balance_note}

**Schwachstellen (alle müssen abgedeckt werden – siehe Pflicht-Block unten):**
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

{weakness_section}**Trainingsprogrammierung Defaults:**
- Makrozyklus: 12 Wochen, Periodisierung: {periodization_note}
- Deload: Wochen 4, 8, 12 → Volumen 80%, Intensität ~90% der Vorwoche
- Zielprofil: {target_profile} → {profile_guides.get(target_profile, profile_guides['hypertrophie'])}
- Mikrozyklus: Nutze das Satz-Budget ({min_sets}-{max_sets}) voll aus, +1 Satz auf Hauptübungen in Nicht-Deload-Wochen, danach Deload-Reset

**AUFGABE:**
{instruction}

⚠️ PLAN-NAME PFLICHT: Der "plan_name" MUSS eindeutig und beschreibend sein!
- Enthält: Ziel + Split-Typ + Hauptschwachstelle + Datum
- Beispiel: "{name_example}"
- KEIN generischer Name wie "Mein Trainingsplan" oder "3er Split"!
- Jeder generierte Plan muss einen EINZIGARTIGEN Namen haben!

{coach_rules}

**Anforderungen:**
0. 🚨 PFLICHT-SCHWACHSTELLEN: Alle im Pflicht-Block #0 genannten Muskelgruppen MÜSSEN mit mind. 1 Übung im Plan sein! Kein optionaler Hinweis – HARTE REGEL!
1. ** VERWENDE NUR ÜBUNGEN AUS DER OBIGEN LISTE** - keine anderen!
2. Push/Pull Balance beachten (bei Unbalance gegensteuern)
3. SATZ-BUDGET: {min_sets}-{max_sets} Sätze pro Trainingstag (ca. 1 Stunde Training)
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
   - Beispiel Pull-Tag (18 Sätze):
     * Klimmzüge (vertikaler Zug): 4 Sätze
     * Langhantelrudern ODER Einarmiges Rudern (1 horizontales Ruder – NICHT beides!): 3 Sätze
     * Oberer Rücken / Scapula (z.B. Face Pulls): 3 Sätze
     * Bizeps Übung 1: 3 Sätze
     * Bizeps Übung 2: 2 Sätze
     * Hintere Schulter oder Rücken Isolation: 3 Sätze
     = 18 Sätze total, 6 Übungen
   - Beispiel Legs-Tag (18 Sätze):
     * Kniebeuge (Hauptübung Quad): 4 Sätze
     * RDL oder Beinbeuger (Hamstrings): 3 Sätze
     * Split Squat oder Ausfallschritt (einbeinig): 3 Sätze
     * Adduktoren/Hüftbeuger (aus Pflicht-Block falls Schwachstelle): 3 Sätze
     * Core/Bauch (aus Pflicht-Block falls Schwachstelle): 3 Sätze
     * Wadenheben (optional, nur wenn Budget noch nicht voll): 2 Sätze
     = 16-18 Sätze total
4. ** MINDESTENS 2 ÜBUNGEN PRO HAUPTMUSKELGRUPPE**:
   - Push-Tag: 2x Brust, 2x Schultern, 1-2x Trizeps
   - Pull-Tag: 1x vertikaler Zug (Klimmzüge/Latzug) + NUR 1x horizontales Ruder + 1-2x Bizeps + 1x Scapula/hintere Schulter
   - Leg-Tag: 1x Quad-Dominant, 1x Hinge/Hamstrings, 1x einbeinig, Pflicht-Schwachstellen (Adduktoren/Core/Hüftbeuger), Waden nur wenn Budget reicht
   - Verschiedene Winkel/Bewegungen für vollständige Entwicklung
5. Compound Movements (Langhantel-Kniebeuge, Bankdrücken, Kreuzheben) priorisieren als erste Übung
6. RPE-Targets: 7-9 für Hypertrophie, Compound Movements können RPE 8-9 haben
7. ** DUPLIKATE**: ❌ KEINE doppelten Übungen INNERHALB einer Session! ✅ ABER gleiche Übungen in verschiedenen Sessions sind ERWÜNSCHT!
8. Periodisierung: Fülle periodization, deload_weeks, macrocycle, microcycle_template, progression_strategy gemäß Defaults oben aus (12 Wochen!)

Erstelle jetzt den optimalen Trainingsplan als JSON-Objekt:"""

        return prompt

    def build_messages(
        self,
        analysis_data: Dict[str, Any],
        available_exercises: List[str],
        plan_type: str = "3er-split",
        sets_per_session: int = 18,
        target_profile: str = "hypertrophie",
        periodization: str = "linear",
    ) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": self.build_user_prompt(
                    analysis_data,
                    available_exercises,
                    plan_type,
                    sets_per_session,
                    target_profile,
                    periodization,
                ),
            },
        ]

    def get_available_exercises_for_user(self, user_id: int) -> List[str]:
        from django.contrib.auth.models import User

        from core.models import Uebung

        user = User.objects.get(id=user_id)
        user_equipment_ids = set(user.verfuegbares_equipment.values_list("id", flat=True))

        available_exercises = []

        for uebung in Uebung.objects.prefetch_related("equipment"):
            required_eq_ids = set(uebung.equipment.values_list("id", flat=True))

            if not required_eq_ids or required_eq_ids.issubset(user_equipment_ids):
                available_exercises.append(uebung.bezeichnung)

        return sorted(available_exercises)


if __name__ == "__main__":
    print("Prompt Builder Test")

    try:
        import os
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from data_analyzer import TrainingAnalyzer
        from db_client import DatabaseClient

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
                sets_per_session=18,
            )

            print("Messages Array fertig für Ollama!")
            print(f"   - System Prompt: {len(messages[0]['content'])} Zeichen")
            print(f"   - User Prompt: {len(messages[1]['content'])} Zeichen")

    except Exception as e:
        print(f"\nFehler: {e}")
        import traceback

        traceback.print_exc()
