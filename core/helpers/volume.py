"""Effektive Gewichts- und Volumenberechnung für alle Übungstypen.

Berücksichtigt Körpergewichtsübungen (Faktor + Richtung), PRO_SEITE-Übungen,
und assistierte Übungen mit Gegengewicht.
"""

from ..models import KoerperWerte


def get_user_kg(user) -> float:
    """Gibt das aktuelle Körpergewicht des Users zurück (0.0 wenn unbekannt)."""
    kw = KoerperWerte.objects.filter(user=user).order_by("-datum").first()
    return float(kw.gewicht) if kw else 0.0


def effective_weight(satz, user_kg: float) -> float:
    """Berechnet das effektive Gewicht eines Satzes unter Berücksichtigung von Typ/Richtung."""
    raw = float(satz.gewicht) if satz.gewicht else 0.0
    if satz.uebung.gewichts_typ == "KOERPERGEWICHT":
        faktor = satz.uebung.koerpergewicht_faktor or 1.0
        basis = user_kg * faktor
        if satz.uebung.gewichts_richtung == "GEGEN":
            return max(0.0, basis - raw)
        return basis + raw
    if satz.uebung.gewichts_typ == "PRO_SEITE":
        return raw * 2
    return raw


def calc_volume(saetze, user_kg: float) -> float:
    """Berechnet das Gesamtvolumen (effektives Gewicht × Wdh) für eine Satz-Liste."""
    return sum(
        effective_weight(s, user_kg) * s.wiederholungen
        for s in saetze
        if s.gewicht is not None and s.wiederholungen
    )
