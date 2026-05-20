"""
Constants for PDF export: push/pull groupings.

Hinweis (Phase 30.0): Die früher hier definierten ``EMPFOHLENE_SAETZE``-
Schwellenwerte wurden entfernt. Die Tabelle hatte lowercase-deutsche Keys
("brust", "quadrizeps"), während der Aufrufer in ``stats_collector`` die
DB-Konstante als Key benutzt hat ("BRUST", "BEINE_QUAD") – der Lookup
matchte nie und fiel universell auf einen Default-Tupel zurück.

Single Source of Truth für Volumen-Schwellenwerte ist jetzt
``core/utils/periodization.py`` (``get_volumen_schwellenwerte``). Sie wird
sowohl vom Stats-Collector (PDF-Report) als auch vom Plan-Generator
(``_save_weakness_snapshot``) gemeinsam genutzt.
"""

PUSH_GROUPS = ["BRUST", "SCHULTER_VORN", "SCHULTER_SEIT", "TRIZEPS"]
PULL_GROUPS = [
    "RUECKEN_LAT",
    "RUECKEN_TRAPEZ",
    "RUECKEN_UNTEN",
    "RUECKEN_OBERER",
    "SCHULTER_HINT",
    "BIZEPS",
]
