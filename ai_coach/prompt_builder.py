"""
Prompt Builder - Erstellt strukturierte Prompts für LLM
"""

from typing import Any, Dict, List, Optional

# Phase 29.3: gemeinsame Mapping-Quelle für prompt_builder und plan_generator.
# WEAKNESS_LABEL_TO_KEYS / KEY_TO_DISPLAY werden re-exportiert, damit bestehende
# Importe (ai_coach.prompt_builder.WEAKNESS_LABEL_TO_KEYS) weiter funktionieren.
from .muscle_labels import (  # noqa: F401
    KEY_TO_DISPLAY,
    MIN_SETS_PER_WEAKNESS,
    WEAKNESS_LABEL_TO_KEYS,
    resolve_weakness_keys,
)

_PROFILE_DEFAULTS = {
    "kraft": {"rep_range": "3-6", "rpe_range": "7.5-9"},
    "hypertrophie": {"rep_range": "6-12", "rpe_range": "7-8.5"},
    "definition": {"rep_range": "10-15", "rpe_range": "6.5-8"},
}


def calculate_deload_weeks(duration_weeks: int) -> list[int]:
    """Phase 17.2: Dynamische Deload-Platzierung alle 3-4 Wochen.

    Strategie: Deload alle 4 Wochen (optimal für Erholung).
    Bei kurzen Plänen (≤6 Wochen) nur letzte Woche als Deload.
    Letzte Woche ist immer Deload wenn sie auf ein 4er-Intervall fällt
    oder der Plan ≥8 Wochen dauert.

    Args:
        duration_weeks: Plandauer in Wochen (4-16).

    Returns:
        Sortierte Liste der Deload-Wochen (1-basiert).
    """
    if duration_weeks <= 0:
        return []
    if duration_weeks <= 6:
        # Kurze Pläne: nur letzte Woche als Deload
        return [duration_weeks]

    deloads = []
    week = 4
    while week <= duration_weeks:
        deloads.append(week)
        week += 4

    # Letzte Woche als Deload wenn Plan ≥8 Wochen und letzte Woche
    # nicht bereits ein Deload ist (z.B. 10 Wochen → [4, 8, 10])
    if duration_weeks >= 8 and duration_weeks not in deloads:
        # Nur wenn Abstand zur letzten Deload-Woche ≥ 2
        if not deloads or (duration_weeks - deloads[-1]) >= 2:
            deloads.append(duration_weeks)

    return sorted(deloads)


def _build_periodization_note(
    periodization: str, target_profile: str, duration_weeks: int = 12
) -> str:
    """Phase 13.3 + 17.3: Dynamische Periodisierungs-Beschreibung.

    Kombiniert Periodisierungs-Typ, Zielprofil und Plandauer zu spezifischem Text
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

    # Dynamische Deload-Wochen (Phase 17.2)
    deload_weeks = calculate_deload_weeks(duration_weeks)
    deload_str = "/".join(str(w) for w in deload_weeks)

    # Periodisierungs-spezifischer Aufbau
    if periodization == "wellenfoermig":
        block_len = 4 if duration_weeks >= 8 else duration_weeks
        structure = f"Wellenförmig: Heavy/Medium/Light innerhalb jedes {block_len}-Wochen-Blocks"
    elif periodization == "block":
        structure = "Blockperiodisierung: Block 1 Volumen, Block 2 Kraft, Block 3 Peaking"
    else:
        structure = "Linear steigende Intensität pro Block"

    return f"{structure} + Deload in Woche {deload_str}. Progression: {progression}"


def _distribute_example_sets(total: int, n_exercises: int = 6) -> List[int]:
    """Verteilt `total` Sätze möglichst gleichmäßig auf n Übungen.

    Der Rest wird auf die vorderen Positionen (Compounds) gelegt. Wird nur für
    die illustrativen Beispiel-Tage im Prompt verwendet (Phase 29.2 / F1) –
    damit die Beispiele mit `sets_per_session` skalieren statt fix bei 18 zu
    stehen.
    """
    n_exercises = max(1, n_exercises)
    base, remainder = divmod(max(0, total), n_exercises)
    return [base + 1 if i < remainder else base for i in range(n_exercises)]


def _format_example_day(day_label: str, target_sets: int, slots: List[str]) -> str:
    """Baut einen Beispiel-Trainingstag, dessen Satz-Summe exakt `target_sets` ist."""
    dist = _distribute_example_sets(target_sets, len(slots))
    lines = [f"   - Beispiel {day_label} (Summe = {target_sets} Sätze):"]
    for slot, sets in zip(slots, dist):
        lines.append(f"     * {slot}: {sets} Sätze")
    lines.append(f"     = {target_sets} Sätze total, {len(slots)} Übungen")
    return "\n".join(lines)


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

        Phase 29.3: Jede untertrainierte Muskelgruppe wird mit einer echten
        Volumen-Vorgabe (MIN_SETS_PER_WEAKNESS Sätze) gefordert, nicht mehr nur
        mit „mind. 1 Übung". Labels werden über die gemeinsame Mapping-Quelle
        aufgelöst – das erkennt auch DB-Konstanten (z.B. „BEINE_HAM"), die der
        data_analyzer liefert und die früher still verworfen wurden (F3).

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
            keys = resolve_weakness_keys(label)
            if not keys:
                continue

            exercises_for_group = self._get_exercises_for_keys(keys, available_exercises)
            display_name = KEY_TO_DISPLAY.get(keys[0], label)

            # Zeige max. 5 Übungen als konkrete Auswahl
            ex_list = exercises_for_group[:5]
            if not ex_list:
                # Kein passendes Equipment → trotzdem Hinweis, aber ohne konkrete Übungen
                mandatory_items.append(
                    f"❗ {display_name.upper()} – PFLICHT: mind. {MIN_SETS_PER_WEAKNESS} "
                    f"Arbeitssätze (1-2 Übungen)\n"
                    f"   (Keine passende Übung in verfügbarer Equipment-Liste – "
                    f"trotzdem versuchen!)"
                )
            else:
                ex_lines = "\n".join(f'   → "{ex}"' for ex in ex_list)
                mandatory_items.append(
                    f"❗ {display_name.upper()} – PFLICHT: mind. {MIN_SETS_PER_WEAKNESS} "
                    f"Arbeitssätze, verteilt auf 1-2 Übungen aus dieser Liste:\n"
                    f"{ex_lines}"
                )

        if not mandatory_items:
            return None

        items_str = "\n\n".join(mandatory_items)
        return f"""🚨🚨🚨 PFLICHT-ANFORDERUNG #0 – HÖCHSTE PRIORITÄT 🚨🚨🚨

Folgende Muskelgruppen sind CHRONISCH UNTERTRAINIERT.
Sie MÜSSEN im fertigen Plan mit jeweils mindestens {MIN_SETS_PER_WEAKNESS} Arbeitssätzen
(verteilt auf 1-2 Übungen) adressiert werden – nicht nur „vorhanden", sondern
mit spürbarem Volumen!
Diese Anforderung hat VORRANG vor allen anderen strukturellen Regeln!

{items_str}

⛔ FEHLER wenn eine dieser Muskelgruppen unter {MIN_SETS_PER_WEAKNESS} Sätzen bleibt oder ganz fehlt.
✅ Notfalls Sätze von anderen (gut trainierten) Gruppen KÜRZEN um Platz zu schaffen.
⚠️ ADDUKTOREN ≠ ABDUKTOREN: Adduktoren = Oberschenkel INNEN (Sumo Squats, Adduktoren-Maschine)
⚠️ ABDUKTOREN = Oberschenkel AUSSEN (Hip Abduction) – das ist NICHT dasselbe!
⚠️ Jede Pflicht-Schwachstelle braucht eigene Übungsslots – nicht mit anderen Gruppen kombinieren!
"""

    def _build_overtraining_cap_block(self, caps: List[Dict[str, Any]]) -> Optional[str]:
        """
        Phase 30.1: Baut den Pflicht-Block für aktuell ÜBERTRAINIERTE
        Muskelgruppen. Diese Gruppen dürfen im neuen Plan kein zusätzliches
        Wochenvolumen über ihrem Cap bekommen, damit ihr 30-Tage-Ist-Wert
        zurück in den Optimal-Bereich wandert.

        Gibt None zurück, wenn keine Muskelgruppe aktuell überlastet ist.
        """
        if not caps:
            return None

        items = []
        for cap in caps:
            items.append(
                f"❗ {cap['name'].upper()} – CAP: max. {cap['weekly_cap']} "
                f"Arbeitssätze pro Woche\n"
                f"   (aktuell {cap['ist_sets']} Sätze/30 Tage, "
                f"Optimal-Max {cap['soll_max']})"
            )
        items_str = "\n\n".join(items)

        return f"""🛑🛑🛑 ÜBERTRAINING-CAP – HÖCHSTE PRIORITÄT 🛑🛑🛑

Folgende Muskelgruppen sind in den letzten 30 Tagen ÜBERTRAINIERT
(zu viel Volumen). Der neue Plan DARF KEIN zusätzliches Volumen für diese
Gruppen aufbauen – das Wochen-Volumen MUSS unter dem Cap bleiben, damit der
30-Tage-Ist-Wert wieder in den Optimal-Bereich sinkt.

{items_str}

⛔ FEHLER wenn eine dieser Muskelgruppen im Plan ihr Cap überschreitet.
✅ Andere (untertrainierte oder optimale) Muskelgruppen bekommen das
   frei werdende Volumen.
ℹ️ Ziel: über 4 Plan-Wochen sinkt der 30-Tage-Wert wieder ins Optimum.
"""

    def _build_training_context_block(
        self, context: Optional[Dict[str, Optional[str]]]
    ) -> Optional[str]:
        """
        Phase 30.4: Soft-Hint-Block für Ermüdung, Trainings-Frequenz und
        Push/Pull-Balance. Jede Komponente ist optional – der Block wird
        nur erzeugt, wenn mindestens eine Komponente einen Hint liefert.

        ``context`` ist ein Dict mit den Schlüsseln ``fatigue_hint``,
        ``frequency_hint``, ``push_pull_hint`` (jeweils ``str | None``).
        """
        if not context:
            return None
        # Reihenfolge: stärkster Hinweis zuerst (Ermüdung → Frequenz →
        # Push/Pull-Balance). Leere/None-Felder einfach überspringen.
        ordered_keys = ("fatigue_hint", "frequency_hint", "push_pull_hint")
        bullets = [f"• {context[k]}" for k in ordered_keys if context.get(k)]
        if not bullets:
            return None
        bullets_str = "\n".join(bullets)
        return f"""🧭 TRAININGS-KONTEXT (Adaptions-Hinweise, Soft):

{bullets_str}
"""

    def _build_plateau_hint_block(self, plateau_hints: List[Dict[str, Any]]) -> Optional[str]:
        """
        Phase 30.3: Soft-Hint-Block für Top-Übungen mit Plateau-/
        Konsolidierungs-Status. Anders als der Untertrainiert- und der
        Übertraining-Block ist das KEIN PFLICHT-Constraint – nur eine
        Empfehlung, für diese Übungen kein zusätzliches Volumen anzusetzen.

        Phase 26: ``consolidation_ready`` ("Bereit für PR-Versuch") wird vom
        generischen "kein Volumen → Variation"-Rat getrennt. Beide Gruppen
        teilen die Botschaft "keine zusätzlichen Sätze", aber die empfohlene
        Alternative unterscheidet sich: Variation bei Konsolidierung/Plateau,
        Intensität bzw. PR-Versuch bei ``consolidation_ready``. Sonst bekäme
        der LLM für eine PR-reife Übung ein gegenläufiges Variations-Signal.

        Gibt None zurück, wenn keine Übung den „kein Volumen-Push"-Status
        hat.
        """
        if not plateau_hints:
            return None

        def _line(hint: Dict[str, Any]) -> str:
            mg = hint.get("muskelgruppe", "")
            mg_suffix = f" ({mg})" if mg else ""
            return f"- {hint['uebung']}{mg_suffix} – {hint['status_label']}"

        variation_items = []
        pr_attempt_items = []
        for hint in plateau_hints:
            if hint.get("status") == "consolidation_ready":
                pr_attempt_items.append(_line(hint))
            else:
                variation_items.append(_line(hint))

        sections = []
        if variation_items:
            sections.append(
                "Folgende deiner Top-Übungen sind aktuell in einer Phase, in der eine\n"
                "Volumen-Steigerung KONTRAPRODUKTIV wäre (Konsolidierung, PR-Pause oder\n"
                "Plateau). Für diese Übungen im neuen Plan KEINE zusätzlichen Sätze\n"
                "ansetzen – stattdessen Frequenz-/Tempo-Variation, kürzere/längere Pausen,\n"
                "oder eine Akzessoire-Übung mit anderem Bewegungswinkel ergänzen.\n\n"
                + "\n".join(variation_items)
            )
        if pr_attempt_items:
            sections.append(
                "Folgende Übungen konsolidieren seit Wochen bei sinkendem RPE und sind\n"
                "BEREIT FÜR EINEN PR-VERSUCH. Auch hier KEINE zusätzlichen Sätze – aber\n"
                "statt Variation die Intensität leicht erhöhen bzw. einen PR-Versuch\n"
                "einplanen (z.B. schwereres Top-Set bei gleichem Volumen).\n\n"
                + "\n".join(pr_attempt_items)
            )
        body = "\n\n".join(sections)

        return f"""ℹ️ TRAININGS-FORTSCHRITT-KONTEXT (Soft-Hint, nicht Pflicht-Block):

{body}
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
  "plan_description": "Kurze Beschreibung des Plan-KONZEPTS (Split-Typ, Periodisierung, Fokus-Themen) – KEINE quantitativen Coverage-Aussagen wie 'X Sätze' oder '≥N Arbeitssätze'",
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
- Erstelle eine EINWÖCHIGE Session-Struktur, die für den Makrozyklus verwendet wird (inkl. Deload-Wochen)
- Übungen & Reihenfolge bleiben gleich, Progression kommt in progression_notes

**PAUSENZEITEN (rest_seconds):**
- Schwere Compound-Übungen (Kniebeugen, Kreuzheben, Bankdrücken): 150-180s
- Mittlere Compound-Übungen (Rudern, Schulterdrücken): 90-120s
- Isolation/Accessories (Bizeps, Trizeps, Waden): 60-90s
- Bei Kraft-Fokus: +30s, bei Definition-Fokus: -30s

**Weitere Anforderungen:**
- Berücksichtige die Schwachstellen und Trainingsziele
- Achte auf realistische Satz/Wdh-Vorgaben basierend auf Historie
- ⚠️ plan_description: Beschreibe NUR das Plan-Konzept (Split-Typ, Periodisierung, Fokus-Themen). Mache dort KEINE quantitativen Behauptungen über Schwachstellen-Coverage (z.B. "alle Pflicht-Schwachstellen mit ≥6 Arbeitssätzen abgedeckt") – das tatsächliche Satz-Volumen steht im strukturierten Plan, nicht in der Beschreibung. Solche Aussagen werden serverseitig entfernt, wenn der Plan sie nicht deckt."""

    def build_user_prompt(
        self,
        analysis_data: Dict[str, Any],
        available_exercises: List[str],
        plan_type: str = "3er-split",
        sets_per_session: int = 18,
        target_profile: str = "hypertrophie",
        periodization: str = "linear",
        duration_weeks: int = 12,
        overtrained_caps: Optional[List[Dict[str, Any]]] = None,
        undertrained: Optional[List[str]] = None,
        plateau_hints: Optional[List[Dict[str, Any]]] = None,
        training_context: Optional[Dict[str, Optional[str]]] = None,
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

        # Schwachstellen-Pflicht-Block (höchste Priorität).
        # Phase 30.2: Pflicht-Quelle ist die kanonische Untertrainiert-Liste
        # aus dem Stats-Collector (durch den Aufrufer als ``undertrained``
        # übergeben). Wird sie nicht übergeben, fallen wir auf
        # ``analysis_data["weaknesses"]`` (data_analyzer-Heuristik) zurück –
        # damit existierende Aufrufer ohne den neuen Parameter weiterhin
        # funktionieren.
        weakness_source = (
            undertrained if undertrained is not None else analysis_data["weaknesses"][:5]
        )
        weakness_block = self._build_weakness_block(weakness_source, available_exercises)
        weakness_section = (weakness_block + "\n\n") if weakness_block else ""

        # Phase 30.1: Übertraining-Cap-Block (analog zum Weakness-Block, aber
        # in die Gegenrichtung: hier wird das Volumen begrenzt).
        overtrain_block = self._build_overtraining_cap_block(overtrained_caps or [])
        overtrain_section = (overtrain_block + "\n\n") if overtrain_block else ""
        # Anforderungs-Punkt "0b" – nur einbauen, wenn der Block oben da ist.
        overtrain_requirement = (
            "\n0b. 🛑 ÜBERTRAINING-CAP (PFLICHT): Jede im Übertraining-Cap-"
            "Block oben gelistete Muskelgruppe DARF im Plan NICHT mehr Sätze "
            "pro Woche bekommen als ihr Cap! Lieber das freie Volumen auf "
            "untertrainierte oder optimale Gruppen umleiten."
            if overtrain_section
            else ""
        )

        # Phase 30.3: Plateau-/Konsolidierungs-Soft-Hint (kein Pflicht-Block,
        # nur Hinweis „für diese Übungen kein Volumen-Push").
        plateau_block = self._build_plateau_hint_block(plateau_hints or [])
        plateau_section = (plateau_block + "\n\n") if plateau_block else ""

        # Phase 30.4: Trainings-Kontext-Soft-Hints (Ermüdung, Frequenz,
        # Push/Pull). Auch optional – Block nur, wenn mind. ein Hint da.
        context_block = self._build_training_context_block(training_context)
        context_section = (context_block + "\n\n") if context_block else ""

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

        # Phase 29.2 (F1): exakte Zielzahl statt 4 Sätze breiter Range.
        # Die alte Range (min = sets-4) erlaubte dem LLM, an der Untergrenze
        # zu landen; zusätzlich verstärkten fix bei 18 stehende Beispiel-Tage
        # diesen Anker. Jetzt: feste Zielzahl + dynamisch skalierte Beispiele.
        target_sets = sets_per_session
        push_example = _format_example_day(
            "Push-Tag",
            target_sets,
            [
                "Brust Übung 1",
                "Brust Übung 2",
                "Schultern Übung 1",
                "Schultern Übung 2",
                "Trizeps Übung 1",
                "Trizeps Übung 2",
            ],
        )
        pull_example = _format_example_day(
            "Pull-Tag",
            target_sets,
            [
                "Vertikaler Zug (Klimmzüge/Latzug)",
                "1 horizontales Ruder (NICHT zwei!)",
                "Oberer Rücken/Scapula (z.B. Face Pulls)",
                "Bizeps Übung 1",
                "Bizeps Übung 2",
                "Hintere Schulter / Rücken-Isolation",
            ],
        )
        legs_example = _format_example_day(
            "Legs-Tag",
            target_sets,
            [
                "Kniebeuge (Quad-Hauptübung)",
                "RDL oder Beinbeuger (Hamstrings)",
                "Split Squat / Ausfallschritt (einbeinig)",
                "Pflicht-Schwachstelle (Adduktoren/Hüftbeuger)",
                "Core/Bauch",
                "Wadenheben",
            ],
        )

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

        # Phase 13.3 + 17.3: Dynamische Periodisierungs-Beschreibung
        # Kombiniert target_profile + periodization + duration_weeks
        periodization_note = _build_periodization_note(
            periodization, target_profile, duration_weeks
        )

        # Phase 17.2: Dynamische Deload-Wochen
        deload_weeks = calculate_deload_weeks(duration_weeks)
        deload_weeks_str = ", ".join(str(w) for w in deload_weeks)

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

{weakness_section}{overtrain_section}{plateau_section}{context_section}**Trainingsprogrammierung Defaults:**
- Makrozyklus: {duration_weeks} Wochen, Periodisierung: {periodization_note}
- Deload: Wochen {deload_weeks_str} → Volumen 80%, Intensität ~90% der Vorwoche
- Zielprofil: {target_profile} → {profile_guides.get(target_profile, profile_guides['hypertrophie'])}
- Mikrozyklus: Basiswoche mit GENAU {target_sets} Arbeitssätzen pro Tag, +1 Satz auf Hauptübungen in Nicht-Deload-Wochen (siehe progression_strategy), danach Deload-Reset

**AUFGABE:**
{instruction}

⚠️ PLAN-NAME PFLICHT: Der "plan_name" MUSS eindeutig und beschreibend sein!
- Enthält: Ziel + Split-Typ + Hauptschwachstelle + Datum
- Beispiel: "{name_example}"
- KEIN generischer Name wie "Mein Trainingsplan" oder "3er Split"!
- Jeder generierte Plan muss einen EINZIGARTIGEN Namen haben!

{coach_rules}

**Anforderungen:**
0. 🚨 PFLICHT-SCHWACHSTELLEN: Alle im Pflicht-Block #0 genannten Muskelgruppen MÜSSEN mit dem geforderten Mindest-Volumen im Plan sein! Kein optionaler Hinweis – HARTE REGEL!{overtrain_requirement}
1. ** VERWENDE NUR ÜBUNGEN AUS DER OBIGEN LISTE** - keine anderen!
2. Push/Pull Balance beachten (bei Unbalance gegensteuern)
3. SATZ-BUDGET: Jeder Trainingstag MUSS GENAU {target_sets} Arbeitssätze enthalten (ca. 1 Stunde Training)
   - Die Summe aller "sets"-Werte eines Tages MUSS exakt {target_sets} ergeben – nicht weniger, nicht mehr!
   - Alle Trainingstage haben exakt dieselbe Satzzahl: jeder Tag {target_sets} Sätze, kein Tag mit weniger oder mehr
   - Verteile die {target_sets} Sätze auf 5-6 Übungen; Compounds zuerst und mit den meisten Sätzen
{push_example}
{pull_example}
{legs_example}
4. ** MINDESTENS 2 ÜBUNGEN PRO HAUPTMUSKELGRUPPE**:
   - Push-Tag: 2x Brust, 2x Schultern, 1-2x Trizeps
   - Pull-Tag: 1x vertikaler Zug (Klimmzüge/Latzug) + NUR 1x horizontales Ruder + 1-2x Bizeps + 1x Scapula/hintere Schulter
   - Leg-Tag: 1x Quad-Dominant, 1x Hinge/Hamstrings, 1x einbeinig, Pflicht-Schwachstellen (Adduktoren/Core/Hüftbeuger), Waden nur wenn Budget reicht
   - Verschiedene Winkel/Bewegungen für vollständige Entwicklung
5. Compound Movements (Langhantel-Kniebeuge, Bankdrücken, Kreuzheben) priorisieren als erste Übung
6. RPE-Targets: 7-9 für Hypertrophie, Compound Movements können RPE 8-9 haben
7. ** DUPLIKATE**: ❌ KEINE doppelten Übungen INNERHALB einer Session! ✅ ABER gleiche Übungen in verschiedenen Sessions sind ERWÜNSCHT!
8. Periodisierung: Fülle periodization, deload_weeks, macrocycle, microcycle_template, progression_strategy gemäß Defaults oben aus ({duration_weeks} Wochen!)

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
        duration_weeks: int = 12,
        overtrained_caps: Optional[List[Dict[str, Any]]] = None,
        undertrained: Optional[List[str]] = None,
        plateau_hints: Optional[List[Dict[str, Any]]] = None,
        training_context: Optional[Dict[str, Optional[str]]] = None,
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
                    duration_weeks,
                    overtrained_caps=overtrained_caps,
                    undertrained=undertrained,
                    plateau_hints=plateau_hints,
                    training_context=training_context,
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
