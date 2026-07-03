"""Wiedereinstieg nach Pause – Detraining-bewusste Einstiegsgewichts-Empfehlung.

Phase 33.2 (Konzept `docs/concepts/phase33_concept.md`). Reine, DB-*lesende*
Logik: berechnet aus einer abgeschlossenen `TrainingsPause` und den zuletzt vor
der Pause geloggten Arbeitsgewichten einen reduzierten Start-Vorschlag pro Übung
plus eine Rückführungs-Rampe zurück auf 100 %.

Leitplanken (Konzept §2/§6):
- **Nur Anzeige, nie Auto-Änderung** – hier gibt es keinen Schreibpfad. Geloggte
  Sätze und Plan-Ziele bleiben unangetastet.
- Die Faktoren sind **Erfahrungs-/Richtwerte, kein ärztlicher Rat**. Bei
  `pause.aerztliche_freigabe_noetig` (Flag aus §33.1) wird konservativer gerechnet
  und der Medizin-Hinweis gesetzt (UI: verpflichtender ärztlicher-Freigabe-
  Disclaimer, §33.3).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import Satz, TrainingsPause

# ─────────────────────────────────────────────────────────────────────────────
# Konfiguration (zentral, bewusst als Konstanten – Heuristik, kein ärztlicher Rat)
# ─────────────────────────────────────────────────────────────────────────────

# Ab dieser (inklusiv gezählten) Pausendauer wird überhaupt eine Empfehlung
# gezeigt. Bewusst höher als PAUSE_BOUNDARY_MIN_DAYS (Phase 32 = 5): ein spürbarer
# Detraining-Effekt tritt eher ab ~10–14 Tagen auf (Konzept §6).
REENTRY_MIN_DAYS = 10

# Nur Übungen, die innerhalb dieses Fensters VOR der Pause trainiert wurden,
# gelten als "aktuelles Repertoire" und bekommen eine Empfehlung.
REENTRY_LOOKBACK_DAYS = 60

# Rundungsschritt für die vorgeschlagenen Gewichte (kg). 2.5 = kleinste übliche
# Hantelscheibe/Stecker; grobe Näherung, bewusst nicht gerätespezifisch.
REENTRY_WEIGHT_STEP = 2.5

# RPE-Deckel in Woche 1 (Basis / medizinisch) und die obere Grenze, gegen die er
# über die Rampe hochläuft.
RPE_CAP_START = 7.0
RPE_CAP_START_MEDIZINISCH = 6.0
RPE_CAP_MAX = 8.5
RPE_CAP_STEP_PER_WEEK = 0.5

# Detraining-Profil je Pausendauer (inklusiv): (Start-Faktor, Rampen-Wochen).
# Nach `ramp_weeks` Wochen ist man zurück auf 100 %.
_DETRAINING_STUFEN: list[tuple[int, float, int]] = [
    # (max_dauer_tage_inklusiv, start_faktor, rampen_wochen)
    (13, 0.95, 1),  # ~1–2 Wochen
    (27, 0.90, 2),  # 2–4 Wochen
    (41, 0.85, 3),  # 4–6 Wochen
]
_DETRAINING_AB_42 = (0.80, 4)  # 6+ Wochen

# Medizinische Pause: eine Stufe konservativer.
_MEDIZINISCH_FAKTOR_ABSCHLAG = 0.05
_MEDIZINISCH_FAKTOR_MIN = 0.70
_MEDIZINISCH_RAMPE_EXTRA = 1


def round_to_step(weight: float, step: float = REENTRY_WEIGHT_STEP) -> float:
    """Rundet auf das nächste Vielfache von `step` (Default 2.5 kg)."""
    if step <= 0:
        return round(weight, 1)
    return round(round(weight / step) * step, 2)


def _detraining_profil(dauer_tage: int, medizinisch: bool) -> tuple[float, int, float]:
    """Gibt (start_faktor, rampen_wochen, rpe_cap_woche1) für die Pausendauer.

    Args:
        dauer_tage: inklusiv gezählte Pausendauer ((end - start).days + 1).
        medizinisch: True → eine Stufe konservativer + niedrigerer RPE-Deckel.
    """
    start_faktor, rampen_wochen = _DETRAINING_AB_42
    for max_tage, faktor, wochen in _DETRAINING_STUFEN:
        if dauer_tage <= max_tage:
            start_faktor, rampen_wochen = faktor, wochen
            break

    rpe_cap = RPE_CAP_START
    if medizinisch:
        start_faktor = max(
            _MEDIZINISCH_FAKTOR_MIN, round(start_faktor - _MEDIZINISCH_FAKTOR_ABSCHLAG, 2)
        )
        rampen_wochen += _MEDIZINISCH_RAMPE_EXTRA
        rpe_cap = RPE_CAP_START_MEDIZINISCH

    return start_faktor, rampen_wochen, rpe_cap


def _baue_rampe(start_faktor: float, rampen_wochen: int, rpe_cap_start: float) -> list[dict]:
    """Baut die Wochen-Rampe: pro Woche Faktor (auf 100 %) + RPE-Deckel.

    Woche 1 = `start_faktor`; die Woche NACH `rampen_wochen` ist wieder 100 %.
    """
    rampe = []
    for i in range(1, rampen_wochen + 1):
        if rampen_wochen <= 1:
            faktor = start_faktor
        else:
            faktor = start_faktor + (1.0 - start_faktor) * (i - 1) / rampen_wochen
        rpe_cap = min(RPE_CAP_MAX, rpe_cap_start + RPE_CAP_STEP_PER_WEEK * (i - 1))
        rampe.append(
            {
                "woche": i,
                "faktor": round(faktor, 3),
                "prozent": round(faktor * 100),
                "rpe_cap": round(rpe_cap, 1),
            }
        )
    return rampe


def get_active_reentry_pause(user, *, today: date | None = None) -> TrainingsPause | None:
    """Die aktuell 'frische' Pause, für die eine Wiedereinstiegs-Empfehlung gilt.

    Kriterien:
    - Der User ist **heute nicht** (mehr) pausiert: keine laufende (offene) Pause
      und keine geschlossene Pause, deren inklusiver Range heute noch abdeckt.
      Die **Rampe startet am Tag NACH dem Pausenende** (Range ist inklusiv, wie
      der Overlap-Check in `core/views/pausen.py`).
    - **Nur die jüngste abgeschlossene Pause** bestimmt das aktuelle Erholungs-
      Segment. Eine spätere (auch kurze) Pause löst die Rampe einer älteren ab –
      es wird nicht auf ältere Pausen zurückgefallen, deren längere Rampe zufällig
      noch bis heute reicht (sonst Empfehlung auf veralteten Vor-Pausen-Gewichten).
    - Diese Pause muss ≥ `REENTRY_MIN_DAYS` dauern und ihre Rampe noch laufen
      (Tage seit Pausenende < Rampen-Länge).

    Gibt die passende Pause zurück oder None.
    """
    if today is None:
        today = timezone.localdate()

    # 1. Deckt heute noch eine Pause ab (laufend ODER geschlossen mit Ende ≥ heute)?
    #    Dann ist der User noch pausiert → kein Wiedereinstieg.
    if (
        TrainingsPause.objects.filter(user=user, start_datum__lte=today)
        .filter(Q(end_datum__isnull=True) | Q(end_datum__gte=today))
        .exists()
    ):
        return None

    # 2. Jüngste abgeschlossene Pause (Ende strikt vor heute) = aktuelles Segment.
    pause = (
        TrainingsPause.objects.filter(user=user, end_datum__isnull=False, end_datum__lt=today)
        .order_by("-end_datum")
        .first()
    )
    if pause is None:
        return None

    dauer_tage = (pause.end_datum - pause.start_datum).days + 1
    if dauer_tage < REENTRY_MIN_DAYS:
        return None
    _, rampen_wochen, _ = _detraining_profil(dauer_tage, pause.aerztliche_freigabe_noetig)
    tage_seit_ende = (today - pause.end_datum).days
    if tage_seit_ende < rampen_wochen * 7:
        return pause
    return None


def _letzte_arbeitsgewichte(user, pause: TrainingsPause) -> list[tuple]:
    """Pro zuletzt trainierter Übung das Arbeitsgewicht der letzten Einheit VOR der Pause.

    'Arbeitsgewicht' = max. Gewicht der Nicht-Aufwärmsätze in der jüngsten Einheit
    (vor Pausenbeginn, kein Deload-Training), in der die Übung vorkam. Übungen ohne
    Daten im Lookback-Fenster werden ausgelassen (Konzept §33.2).

    `GEGEN`-Übungen (assistierte Klimmzüge/Dips: `gewicht` = Gegengewicht,
    niedriger = schwerer) werden ausgelassen: ein Detraining-Faktor auf das
    Gegengewicht würde die Hilfe *reduzieren* und den Satz härter machen – das
    Gegenteil einer konservativen Empfehlung. Diese Übungen bräuchten die
    invertierte Semantik der Session-Progression und sind hier bewusst nicht
    abgedeckt (Codex-Review PR #203, P2).

    Returns:
        Liste von (Uebung, letztes_gewicht_float), sortiert nach Übungsname.
    """
    fenster_start = pause.start_datum - timedelta(days=REENTRY_LOOKBACK_DAYS)
    saetze = (
        Satz.objects.filter(
            einheit__user=user,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
            einheit__datum__date__gte=fenster_start,
            einheit__datum__date__lt=pause.start_datum,
            gewicht__gt=0,
        )
        .exclude(uebung__gewichts_richtung="GEGEN")
        .select_related("uebung", "einheit")
        .order_by("uebung_id", "-einheit__datum")
    )

    # Ordered by -datum → die erste gesehene Einheit je Übung ist die jüngste.
    letzte_einheit: dict[int, int] = {}
    best: dict[int, list] = {}
    for s in saetze:
        uid = s.uebung_id
        gewicht = float(s.gewicht)
        if uid not in best:
            letzte_einheit[uid] = s.einheit_id
            best[uid] = [s.uebung, gewicht]
        elif s.einheit_id == letzte_einheit[uid]:
            best[uid][1] = max(best[uid][1], gewicht)
        # ältere Einheiten der Übung → ignorieren

    ergebnis = [(uebung, gewicht) for uebung, gewicht in best.values()]
    ergebnis.sort(key=lambda t: t[0].bezeichnung.lower())
    return ergebnis


def build_reentry_recommendation(user, *, today: date | None = None) -> dict | None:
    """Vollständige Wiedereinstiegs-Empfehlung oder None, wenn keine aktive Pause.

    Verändert NICHTS (reine Anzeige-Daten). Struktur:
        {
          "pause", "dauer_tage", "medizinisch",
          "start_faktor", "rampen_wochen", "aktuelle_woche",
          "rampe": [{"woche","faktor","prozent","rpe_cap"}, ...],
          "uebungen": [{"uebung","letztes_gewicht","wochen_gewichte":[...]}],
        }
    `uebungen` kann leer sein (Pause aktiv, aber keine Vor-Pause-Daten im Fenster).
    """
    if today is None:
        today = timezone.localdate()

    pause = get_active_reentry_pause(user, today=today)
    if pause is None:
        return None

    dauer_tage = (pause.end_datum - pause.start_datum).days + 1
    medizinisch = pause.aerztliche_freigabe_noetig
    start_faktor, rampen_wochen, rpe_cap_start = _detraining_profil(dauer_tage, medizinisch)
    rampe = _baue_rampe(start_faktor, rampen_wochen, rpe_cap_start)

    tage_seit_ende = (today - pause.end_datum).days
    aktuelle_woche = min(rampen_wochen, tage_seit_ende // 7 + 1)

    uebungen = []
    for uebung, letztes_gewicht in _letzte_arbeitsgewichte(user, pause):
        wochen = [
            {
                "woche": r["woche"],
                "prozent": r["prozent"],
                "rpe_cap": r["rpe_cap"],
                "gewicht": round_to_step(letztes_gewicht * r["faktor"]),
                "ist_aktuell": r["woche"] == aktuelle_woche,
            }
            for r in rampe
        ]
        uebungen.append(
            {
                "uebung": uebung,
                "letztes_gewicht": round(letztes_gewicht, 2),
                "wochen": wochen,
            }
        )

    return {
        "pause": pause,
        "dauer_tage": dauer_tage,
        "medizinisch": medizinisch,
        "start_faktor": start_faktor,
        "rampen_wochen": rampen_wochen,
        "aktuelle_woche": aktuelle_woche,
        "rampe": rampe,
        "uebungen": uebungen,
    }
