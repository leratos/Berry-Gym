"""Phase 29.3: Gemeinsame Muskelgruppen-Label-Zuordnung für den AI-Coach.

Single Source of Truth für die Zuordnung von Schwachstellen-Labels (wie sie
der `data_analyzer` liefert) zu DB-Muskelgruppen-Konstanten.

Hintergrund (Finding F3 / Diagnose 29.1): `data_analyzer` liefert
Schwachstellen mit DB-Konstanten als Label ("BEINE_HAM: Untertrainiert ..."),
nicht mit menschenlesbaren Namen. Früher kannte `prompt_builder` nur
menschenlesbare Keys und verwarf solche Schwachstellen still. Dieses Modul
erkennt BEIDE Formen und wird von `prompt_builder` und `plan_generator`
gemeinsam genutzt, damit die Zuordnungen nicht erneut auseinanderlaufen.

Bewusst hartcodiert (kein Import aus `core.models`), damit das Modul auch vor
`django.setup()` importierbar ist – der Generator wird im CLI-Modus geladen,
bevor Django bereitsteht.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# DB-Konstante → kurzer, menschenlesbarer Anzeigename (für Prompt-Ausgabe)
# ─────────────────────────────────────────────────────────────────────────────
KEY_TO_DISPLAY: dict[str, str] = {
    "BRUST": "Brust",
    "RUECKEN_LAT": "Latissimus",
    "RUECKEN_TRAPEZ": "Trapez",
    "RUECKEN_UNTEN": "Unterer Rücken",
    "RUECKEN_OBERER": "Oberer Rücken",
    "SCHULTER_VORN": "Vordere Schulter",
    "SCHULTER_SEIT": "Seitliche Schulter",
    "SCHULTER_HINT": "Hintere Schulter",
    "BIZEPS": "Bizeps",
    "TRIZEPS": "Trizeps",
    "BAUCH": "Bauch / Core",
    "BEINE_QUAD": "Quadrizeps",
    "BEINE_HAM": "Hamstrings",
    "PO": "Gesäß",
    "WADEN": "Waden",
    "UNTERARME": "Unterarme",
    "ADDUKTOREN": "Adduktoren (Oberschenkel innen)",
    "ABDUKTOREN": "Abduktoren (Oberschenkel außen)",
    "HUEFTBEUGER": "Hüftbeuger",
    "GANZKOERPER": "Ganzkörper",
}

# ─────────────────────────────────────────────────────────────────────────────
# Mindest-Satzzahl pro untertrainierter Muskelgruppe im Wochenplan (Phase 29.3)
#
# Bewusst 6 statt des Konzept-Vorschlags 12: Der Struktur-Validator deckelt
# eine Muskelgruppe pro Session auf 7 Sätze (_MAX_SETS_PER_MUSCLE_GROUP). In
# einem Split trifft eine Muskelgruppe oft nur einen Trainingstag (z.B.
# Hamstrings nur am Legs-Tag), daher ist ein Wochenziel >7 nicht konfliktfrei
# erreichbar. 6 Sätze (≈2 Übungen) sind klar "prominent" gegenüber dem alten
# "mind. 1 Übung" und bleiben innerhalb des Caps.
# ─────────────────────────────────────────────────────────────────────────────
MIN_SETS_PER_WEAKNESS = 6

# ─────────────────────────────────────────────────────────────────────────────
# Menschenlesbare Aliase + Gruppen-Aggregationen → DB-Konstanten
# ─────────────────────────────────────────────────────────────────────────────
_HUMAN_ALIASES: dict[str, list[str]] = {
    "brust": ["BRUST"],
    "rücken": ["RUECKEN_LAT", "RUECKEN_TRAPEZ", "RUECKEN_UNTEN", "RUECKEN_OBERER"],
    "beine": [
        "BEINE_QUAD",
        "BEINE_HAM",
        "PO",
        "WADEN",
        "ADDUKTOREN",
        "ABDUKTOREN",
        "HUEFTBEUGER",
    ],
    "schultern": ["SCHULTER_VORN", "SCHULTER_SEIT", "SCHULTER_HINT"],
    "vordere schulter": ["SCHULTER_VORN"],
    "seitliche schulter": ["SCHULTER_SEIT"],
    "hintere schulter": ["SCHULTER_HINT"],
    "lat": ["RUECKEN_LAT"],
    "latissimus": ["RUECKEN_LAT"],
    "trapez": ["RUECKEN_TRAPEZ"],
    "unterer rücken": ["RUECKEN_UNTEN"],
    "oberer rücken": ["RUECKEN_OBERER"],
    "oberschenkel vorne": ["BEINE_QUAD"],
    "oberschenkel hinten": ["BEINE_HAM"],
    "quadrizeps": ["BEINE_QUAD"],
    "hamstrings": ["BEINE_HAM"],
    "gesäß": ["PO"],
    "waden": ["WADEN"],
    "unterarme": ["UNTERARME"],
    "bizeps": ["BIZEPS"],
    "trizeps": ["TRIZEPS"],
    "bauch": ["BAUCH"],
    "adduktoren": ["ADDUKTOREN"],
    "abduktoren": ["ABDUKTOREN"],
    "hüfte": ["HUEFTBEUGER", "ADDUKTOREN", "ABDUKTOREN"],
    "hüftbeuger": ["HUEFTBEUGER"],
}

# DB-Konstante (lowercase) → [DB-Konstante]: deckt ab, was der data_analyzer
# tatsächlich liefert ("BEINE_HAM: Untertrainiert ...").
_DB_CONSTANT_KEYS: dict[str, list[str]] = {key.lower(): [key] for key in KEY_TO_DISPLAY}

# Kanonische Zuordnung: erkennt menschenlesbare Labels UND DB-Konstanten.
WEAKNESS_LABEL_TO_KEYS: dict[str, list[str]] = {**_DB_CONSTANT_KEYS, **_HUMAN_ALIASES}


def resolve_weakness_keys(label: str) -> list[str]:
    """Wandelt ein Schwachstellen-Label in DB-Muskelgruppen-Keys um.

    Erkennt DB-Konstanten ("BEINE_HAM") wie auch menschenlesbare Labels
    ("Hintere Schulter", "beine"). Gibt eine leere Liste zurück, wenn nichts
    passt.
    """
    return WEAKNESS_LABEL_TO_KEYS.get((label or "").strip().lower(), [])
