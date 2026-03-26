"""
Periodisierungs-Intelligence: Block-Typ-Empfehlungen und Block-Alter-Warnungen.

Verknüpft die Trainingsblock-Typen (Phase 3) mit der KI-Plangenerierung
(ai_coach/plan_generator.py), indem empfohlene Folge-Blöcke auf die
target_profile-Werte (kraft/hypertrophie/definition) gemappt werden.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Block-Typ → Empfehlung Mapping
#
# Trainingsblock.BLOCK_TYP_CHOICES:
#   definition, masse, kraft, peaking, deload, sonstige
#
# PlanGenerator target_profile:
#   kraft, hypertrophie, definition
# ─────────────────────────────────────────────────────────────────────────────

_BLOCK_RECOMMENDATIONS: dict[str, dict] = {
    "kraft": {
        "primary": {
            "typ": "masse",
            "label": "Hypertrophie / Masseaufbau",
            "target_profile": "hypertrophie",
            "reason": (
                "Nach einer Kraftphase profitierst du von höherem Volumen "
                "bei moderater Intensität – das neue Kraftniveau nutzen, "
                "um mehr Muskelreize zu setzen."
            ),
        },
        "alternative": {
            "typ": "definition",
            "label": "Definition",
            "target_profile": "definition",
            "reason": (
                "Alternativ: Definitionsphase – das aufgebaute Kraft­niveau "
                "halten, während Körperfett reduziert wird."
            ),
        },
    },
    "masse": {
        "primary": {
            "typ": "kraft",
            "label": "Kraft",
            "target_profile": "kraft",
            "reason": (
                "Nach einer Aufbauphase ist eine Kraftphase ideal – "
                "die neue Muskelmasse in Maximalkraft umsetzen."
            ),
        },
        "alternative": {
            "typ": "definition",
            "label": "Definition",
            "target_profile": "definition",
            "reason": (
                "Alternativ: Definitionsphase – überschüssiges Körperfett "
                "aus der Aufbauphase abbauen."
            ),
        },
    },
    "definition": {
        "primary": {
            "typ": "masse",
            "label": "Hypertrophie / Masseaufbau",
            "target_profile": "hypertrophie",
            "reason": (
                "Nach einer Definitionsphase ist Aufbau sinnvoll – "
                "der Stoffwechsel ist bereit für einen Kalorienüberschuss."
            ),
        },
        "alternative": {
            "typ": "kraft",
            "label": "Kraft",
            "target_profile": "kraft",
            "reason": (
                "Alternativ: Kraftphase – mit niedrigem Körperfett "
                "Maximalkraft aufbauen, bevor der nächste Aufbau startet."
            ),
        },
    },
    "peaking": {
        "primary": {
            "typ": "deload",
            "label": "Deload-Block",
            "target_profile": None,
            "reason": (
                "Nach einer Peaking-/Wettkampfphase braucht der Körper "
                "Regeneration. 1–2 Wochen Deload empfohlen."
            ),
        },
        "alternative": {
            "typ": "masse",
            "label": "Hypertrophie / Masseaufbau",
            "target_profile": "hypertrophie",
            "reason": ("Alternativ: Direkt in den Aufbau, wenn die Erholung " "ausreichend war."),
        },
    },
    "deload": {
        "primary": {
            "typ": "masse",
            "label": "Hypertrophie / Masseaufbau",
            "target_profile": "hypertrophie",
            "reason": (
                "Nach einem Deload bist du erholt – idealer Zeitpunkt "
                "für eine Aufbauphase mit progressivem Volumen."
            ),
        },
        "alternative": {
            "typ": "kraft",
            "label": "Kraft",
            "target_profile": "kraft",
            "reason": (
                "Alternativ: Kraftphase – frisch erholt in schwere " "Compounds einsteigen."
            ),
        },
    },
    "sonstige": {
        "primary": {
            "typ": "masse",
            "label": "Hypertrophie / Masseaufbau",
            "target_profile": "hypertrophie",
            "reason": (
                "Hypertrophie ist ein solider Default – moderates Volumen "
                "und Intensität für die meisten Trainingsziele."
            ),
        },
        "alternative": {
            "typ": "kraft",
            "label": "Kraft",
            "target_profile": "kraft",
            "reason": "Alternativ: Kraftphase für Maximalkraft-Fokus.",
        },
    },
}

# Schwellenwert ab dem eine Warnung angezeigt wird (in Wochen)
BLOCK_AGE_WARNING_THRESHOLD = 8


def get_next_block_recommendation(current_type: str) -> dict:
    """Gibt Primary- und Alternative-Empfehlung für den Folge-Block zurück.

    Args:
        current_type: Aktueller Block-Typ (einer der BLOCK_TYP_CHOICES Keys).

    Returns:
        Dict mit 'primary' und 'alternative', jeweils:
            typ: str – Block-Typ Key
            label: str – Anzeigename
            target_profile: str | None – Wert für PlanGenerator (None = kein Plan nötig)
            reason: str – Kurze Begründung
    """
    recommendation = _BLOCK_RECOMMENDATIONS.get(current_type)
    if not recommendation:
        # Unbekannter Typ → Fallback auf "sonstige"
        recommendation = _BLOCK_RECOMMENDATIONS["sonstige"]
    return recommendation


def get_block_age_warning(active_block) -> dict | None:
    """Prüft ob der aktive Trainingsblock eine Alterswarnung braucht.

    Args:
        active_block: Trainingsblock-Instanz oder None.

    Returns:
        Warning-Dict für das Dashboard-Template oder None.
        Keys: message, weeks, block_type_display, recommendation, severity
    """
    if active_block is None:
        return None

    weeks = active_block.weeks_since_start
    if weeks < BLOCK_AGE_WARNING_THRESHOLD:
        return None

    recommendation = get_next_block_recommendation(active_block.typ)
    primary = recommendation["primary"]

    return {
        "weeks": weeks,
        "block_type_display": active_block.get_typ_display(),
        "recommendation": primary,
        "severity": "danger" if weeks >= 12 else "warning",
    }
