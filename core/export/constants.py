"""
Constants for PDF export: recommended sets per muscle group, push/pull groupings.
"""

EMPFOHLENE_SAETZE: dict[str, tuple[int, int]] = {
    "brust": (12, 20),
    "ruecken_breiter": (15, 25),
    "ruecken_unterer": (10, 18),
    "schulter_vordere": (8, 15),
    "schulter_seitliche": (12, 20),
    "schulter_hintere": (12, 20),
    "bizeps": (10, 18),
    "trizeps": (10, 18),
    "quadrizeps": (15, 25),
    "hamstrings": (12, 20),
    "glutaeus": (10, 18),
    "waden": (12, 20),
    "bauch": (12, 25),
    "unterer_ruecken": (8, 15),
}

PUSH_GROUPS = ["BRUST", "SCHULTER_VORN", "SCHULTER_SEIT", "TRIZEPS"]
PULL_GROUPS = [
    "RUECKEN_LAT",
    "RUECKEN_TRAPEZ",
    "RUECKEN_UNTEN",
    "RUECKEN_OBERER",
    "SCHULTER_HINT",
    "BIZEPS",
]
