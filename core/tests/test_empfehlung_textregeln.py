"""Phase 34.4 – Harte Textregel: keine Ernährungsbegriffe in Empfehlungstexten.

Regel im Testcode statt Konvention im Kopf (Phase-11-/30.1-Lektion): Das Tool
macht keine Ernährungsberatung (User-Entscheidung #1053, Sweep 34.3). Verboten
sind Kalorien-/Defizit-/Überschuss-/Stoffwechsel-/Ernährungs-Begriffe in allen
Modulen, die Empfehlungs-/Bewertungstexte erzeugen, und in den Templates, die
sie (oder eigene Bewertungslabels) rendern.

Bewusst NICHT geprüft (dokumentierte Ausnahmen, Konzept §3.3):
- ``core/management/commands/load_disclaimers.py`` und ``sources.html`` –
  rechtliche Disclaimer (nennen die Grundumsatz-Berechnung bzw. generische
  Einflussfaktoren, sprechen keine Empfehlung aus).
- ``core/models/body_tracking.py`` – Datenfeld ``grundumsatz_kcal`` (Anzeige
  eines vom User erfassten Werts, keine Empfehlung).
- ``core/views_old.py`` – toter Code (nirgends importiert/geroutet).
"""

import re
from pathlib import Path

import pytest

from core.utils.periodization import (
    _BLOCK_RECOMMENDATIONS,
    _DEFAULT_MODUS_PROFIL,
    _TRAININGSMODUS_PROFILE,
)

BASE_DIR = Path(__file__).resolve().parents[2]

VERBOTENE_BEGRIFFE = re.compile(
    "|".join(
        [
            "kalorien",
            "defizit",
            "überschuss",
            "überschüss",  # fängt auch „überschüssig" (Wortstamm)
            "ueberschuss",
            "stoffwechsel",
            "ernährung",
            "ernaehrung",
            "proteinzufuhr",
            "eiweiß",
            "eiweiss",
            "kohlenhydrat",
            "makronährstoff",
            "makronaehrstoff",
            "diät",
            "diaet",
        ]
    ),
    re.IGNORECASE,
)

# Alle Quellen, die Empfehlungs-/Bewertungstexte erzeugen oder rendern.
GEPRUEFTE_DATEIEN = [
    "core/utils/periodization.py",
    "core/views/ai_recommendations.py",
    "core/export/weight_analysis.py",
    "core/utils/advanced_stats.py",
    "core/views/training_stats.py",
    "core/templates/core/dashboard.html",
    "core/templates/core/training_pdf_simple.html",
]


def _texte(obj):
    """Alle Strings aus verschachtelten Dict-/Listen-Konstanten."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _texte(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _texte(value)


def test_empfehlungs_konstanten_ohne_ernaehrungsbegriffe():
    """Dict-Walk über die Periodisierungs-Konstanten (robust gegen Umbauten)."""
    for konstante in (_BLOCK_RECOMMENDATIONS, _TRAININGSMODUS_PROFILE, _DEFAULT_MODUS_PROFIL):
        for text in _texte(konstante):
            treffer = VERBOTENE_BEGRIFFE.search(text)
            assert treffer is None, f"Ernährungsbegriff '{treffer.group(0)}' in: {text!r}"


@pytest.mark.parametrize("relpfad", GEPRUEFTE_DATEIEN)
def test_quelltexte_ohne_ernaehrungsbegriffe(relpfad):
    """Zeilenweiser Quelltext-Scan – fängt auch neue Inline-Strings/Kommentare."""
    quelle = (BASE_DIR / relpfad).read_text(encoding="utf-8")
    verstoesse = []
    for nr, zeile in enumerate(quelle.splitlines(), start=1):
        treffer = VERBOTENE_BEGRIFFE.search(zeile)
        if treffer is not None:
            verstoesse.append(f"{relpfad}:{nr}: '{treffer.group(0)}': {zeile.strip()}")
    assert not verstoesse, "Ernährungsbegriffe gefunden:\n" + "\n".join(verstoesse)
