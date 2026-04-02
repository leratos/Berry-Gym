"""
Periodisierungs-Intelligence: Block-Typ-Empfehlungen, Block-Alter-Warnungen
und kontextsensitive Trainingsmodus-Profile.

Verknüpft die Trainingsblock-Typen (Phase 3) mit der KI-Plangenerierung
(ai_coach/plan_generator.py), indem empfohlene Folge-Blöcke auf die
target_profile-Werte (kraft/hypertrophie/definition) gemappt werden.

Phase 12: Muskelgruppen-Größenklassifikation, differenzierte Volumen-Schwellenwerte,
Trainingsmodus-Profile und Wiederholungsbereich-Klassifikation.
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
    # Phase 17.4: Nutze geplante Dauer wenn vorhanden, sonst Fallback
    threshold = getattr(active_block, "warning_threshold_weeks", BLOCK_AGE_WARNING_THRESHOLD)
    if weeks < threshold:
        return None

    recommendation = get_next_block_recommendation(active_block.typ)
    primary = recommendation["primary"]

    # Severity: danger wenn 50% über Schwellenwert
    danger_threshold = int(threshold * 1.5)
    return {
        "weeks": weeks,
        "block_type_display": active_block.get_typ_display(),
        "recommendation": primary,
        "severity": "danger" if weeks >= danger_threshold else "warning",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12: Kontextsensitive Empfehlungen
# ─────────────────────────────────────────────────────────────────────────────

# Muskelgruppen-Größenklassifikation für differenzierte Volumen-Schwellenwerte
MUSKELGRUPPEN_GROESSE: dict[str, str] = {
    # Große Gruppen (12-25 Sätze / 30 Tage)
    "BRUST": "gross",
    "RUECKEN_LAT": "gross",
    "RUECKEN_TRAPEZ": "gross",
    "RUECKEN_OBERER": "gross",
    "BEINE_QUAD": "gross",
    "BEINE_HAM": "gross",
    "PO": "gross",
    # Mittlere Gruppen (10-18 Sätze / 30 Tage)
    "SCHULTER_VORN": "mittel",
    "SCHULTER_SEIT": "mittel",
    "SCHULTER_HINT": "mittel",
    "TRIZEPS": "mittel",
    "ADDUKTOREN": "mittel",
    "ABDUKTOREN": "mittel",
    "BAUCH": "mittel",
    # Kleine Gruppen (8-16 Sätze / 30 Tage)
    "BIZEPS": "klein",
    "WADEN": "klein",
    "UNTERARME": "klein",
    # Haltungsgruppen (6-12 Sätze / 30 Tage)
    "HUEFTBEUGER": "haltung",
    "RUECKEN_UNTEN": "haltung",
    # Spezial (kein Volumen-Schwellenwert sinnvoll)
    "GANZKOERPER": "spezial",
}

# Sätze pro 30 Tage (≈ 4 Wochen) – Schwellenwerte pro Größenkategorie
VOLUMEN_SCHWELLENWERTE: dict[str, tuple[int, int]] = {
    "gross": (12, 25),
    "mittel": (10, 18),
    "klein": (8, 16),
    "haltung": (6, 12),
}

# Trainingsmodus-Profile: Steuert Empfehlungstexte + Heuristiken pro Block-Typ
_TRAININGSMODUS_PROFILE: dict[str, dict] = {
    "masse": {
        "label": "Aufbau / Masseaufbau",
        "volumen_empfehlung": (
            "Volumen-Steigerung priorisieren – mehr Sätze, moderate Intensität."
        ),
        "rpe_target_range": (6.5, 8.5),
        "rpe_zu_niedrig_text": (
            "Im Aufbau-Modus solltest du mit RPE 7-9 trainieren, "
            "um ausreichend Muskelreize zu setzen."
        ),
        "rpe_zu_hoch_text": (
            "Im Aufbau-Modus ist RPE 9.5+ kontraproduktiv – "
            "reduziere das Gewicht leicht zugunsten von mehr Volumen."
        ),
        "stagnation_tipp": (
            "Im Aufbau: Erhöhe das Volumen (mehr Sätze) oder "
            "variiere den Wiederholungsbereich (8-12 Reps)."
        ),
        "volumen_faktor": 1.0,
    },
    "definition": {
        "label": "Definition",
        "volumen_empfehlung": (
            "Intensität halten statt Volumen steigern. "
            "Compounds priorisieren, Isolation reduzieren."
        ),
        "rpe_target_range": (7.0, 9.0),
        "rpe_zu_niedrig_text": (
            "Im Definitionsmodus ist hohe Intensität entscheidend – "
            "trainiere mit RPE 7-9, um Muskelmasse zu erhalten."
        ),
        "rpe_zu_hoch_text": (
            "RPE 9.5+ im Defizit erhöht das Verletzungsrisiko. "
            "Behalte RPE 7-9 bei und setze auf schwere Compounds."
        ),
        "stagnation_tipp": (
            "Im Defizit ist Stagnation normal. Halte das Gewicht – "
            "setze auf schwere Compounds (6-8 Reps) statt mehr Volumen."
        ),
        "volumen_faktor": 0.85,
    },
    "kraft": {
        "label": "Kraft",
        "volumen_empfehlung": (
            "Schwere Gewichte, niedrige Wiederholungen. "
            "Fokus auf Compound-Bewegungen mit 3-6 Reps."
        ),
        "rpe_target_range": (7.5, 9.5),
        "rpe_zu_niedrig_text": (
            "Im Kraft-Modus trainierst du zu leicht – "
            "steigere das Gewicht für 3-6 Reps bei RPE 8-9.5."
        ),
        "rpe_zu_hoch_text": (
            "Konstantes Training am Limit (RPE 10) erhöht das Verletzungsrisiko. "
            "Halte RPE 8-9.5 für nachhaltige Kraftsteigerung."
        ),
        "stagnation_tipp": (
            "Kraft-Plateau: Probiere Wellenperiodisierung, "
            "schwere Singles/Doubles oder einen kurzen Deload."
        ),
        "volumen_faktor": 0.75,
    },
    "deload": {
        "label": "Deload",
        "volumen_empfehlung": "Reduziertes Volumen und Intensität zur Erholung.",
        "rpe_target_range": (5.0, 7.0),
        "rpe_zu_niedrig_text": "",
        "rpe_zu_hoch_text": (
            "Im Deload-Block sollte RPE unter 7 bleiben – "
            "das Ziel ist Erholung, nicht Progression."
        ),
        "stagnation_tipp": "",
        "volumen_faktor": 0.5,
    },
}

# Default-Profil für peaking/sonstige/unbekannte Block-Typen
_DEFAULT_MODUS_PROFIL: dict = {
    "label": "Standard",
    "volumen_empfehlung": "Trainiere ausgewogen mit moderatem Volumen und Intensität.",
    "rpe_target_range": (6.0, 9.0),
    "rpe_zu_niedrig_text": (
        "Dein durchschnittlicher RPE ist niedrig. "
        "Steigere das Gewicht für optimalen Muskelaufbau."
    ),
    "rpe_zu_hoch_text": (
        "Dein durchschnittlicher RPE ist sehr hoch. "
        "Reduziere das Gewicht leicht – Deload-Woche empfohlen!"
    ),
    "stagnation_tipp": (
        "Versuche: (1) Deload-Woche, (2) Wiederholungsbereich ändern, (3) Tempo variieren"
    ),
    "volumen_faktor": 1.0,
}

# Wiederholungsbereich-Klassifikation
REP_RANGE_KRAFT = (1, 6)
REP_RANGE_HYPERTROPHIE = (7, 12)
REP_RANGE_AUSDAUER = (13, 100)


def get_modus_profil(block_typ: str | None) -> dict:
    """Gibt das Trainingsmodus-Profil für den gegebenen Block-Typ zurück.

    Args:
        block_typ: Block-Typ Key (z.B. 'masse', 'definition', 'kraft') oder None.

    Returns:
        Dict mit Empfehlungstexten, RPE-Zielbereichen, Volumen-Faktoren etc.
    """
    if block_typ is None:
        return _DEFAULT_MODUS_PROFIL
    return _TRAININGSMODUS_PROFILE.get(block_typ, _DEFAULT_MODUS_PROFIL)


def get_volumen_schwellenwerte(
    muskelgruppe_key: str, block_typ: str | None = None
) -> tuple[int, int] | None:
    """Gibt (min_sets, max_sets) pro 30 Tage für eine Muskelgruppe zurück.

    Berücksichtigt den Block-Typ via volumen_faktor.

    Args:
        muskelgruppe_key: Key aus MUSKELGRUPPEN (z.B. 'BRUST', 'BIZEPS').
        block_typ: Aktiver Block-Typ oder None.

    Returns:
        (min_sets, max_sets) oder None wenn keine Schwellenwerte definiert
        (z.B. GANZKOERPER).
    """
    groesse = MUSKELGRUPPEN_GROESSE.get(muskelgruppe_key)
    if groesse is None or groesse == "spezial":
        return None
    base = VOLUMEN_SCHWELLENWERTE.get(groesse)
    if base is None:
        return None
    profil = get_modus_profil(block_typ)
    faktor = profil.get("volumen_faktor", 1.0)
    return (round(base[0] * faktor), round(base[1] * faktor))


def klassifiziere_rep_range(wiederholungen: int) -> str:
    """Klassifiziert Wiederholungen in einen Trainingsbereich.

    Returns:
        'kraft' (1-6), 'hypertrophie' (7-12), or 'ausdauer' (13+).
    """
    if wiederholungen <= REP_RANGE_KRAFT[1]:
        return "kraft"
    elif wiederholungen <= REP_RANGE_HYPERTROPHIE[1]:
        return "hypertrophie"
    else:
        return "ausdauer"
