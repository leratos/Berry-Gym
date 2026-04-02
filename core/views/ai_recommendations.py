"""
AI-powered training recommendations, plan generation, analysis, and optimization.

This module handles all AI/ML-related functionality including:
- Intelligent workout recommendations based on training data analysis
- AI-powered plan generation and customization
- Rule-based and AI-driven plan analysis
- Plan optimization suggestions using ML models
- Live guidance during training sessions
"""

import json
import logging
import os
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from ..models import (
    MUSKELGRUPPEN,
    Plan,
    PlanUebung,
    Satz,
    SiteSettings,
    Trainingsblock,
    Trainingseinheit,
    Uebung,
    UserProfile,
)
from ..utils.periodization import (
    get_modus_profil,
    get_volumen_schwellenwerte,
    klassifiziere_rep_range,
)

# ---------------------------------------------------------------------------
# Rate-Limit Helper
# ---------------------------------------------------------------------------


def _check_ai_rate_limit(request: HttpRequest, limit_type: str) -> JsonResponse | None:
    """
    Prüft das tägliche KI-Limit für den eingeloggten User.

    Hierarchie:
    1. User-spezifisches Custom-Limit (falls gesetzt)
    2. Site-weites Default-Limit (aus DB)
    3. Fallback: settings.py

    Gibt None zurück wenn der Request erlaubt ist.
    Gibt eine 429-JsonResponse zurück wenn das Limit erreicht ist.
    Im DEBUG/Test-Modus immer None (kein Limit).
    """
    if getattr(settings, "RATELIMIT_BYPASS", False):
        return None

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return None  # Kein Profil → durchlassen, Fehler wird anderswo behandelt

    # SCHRITT 1: User-spezifisches Custom-Limit?
    custom_limit_map = {
        "plan": profile.custom_ai_limit_plan,
        "guidance": profile.custom_ai_limit_guidance,
        "analysis": profile.custom_ai_limit_analysis,
    }
    limit = custom_limit_map.get(limit_type)

    # SCHRITT 2: Site-Einstellungen (wenn kein Custom-Limit)
    if limit is None:
        site_settings = SiteSettings.load()
        site_limit_map = {
            "plan": site_settings.ai_limit_plan_generation,
            "guidance": site_settings.ai_limit_live_guidance,
            "analysis": site_settings.ai_limit_analysis,
        }
        limit = site_limit_map.get(limit_type)

    # SCHRITT 3: Fallback auf settings.py (sollte nie nötig sein)
    if limit is None:
        fallback_map = {
            "plan": settings.AI_RATE_LIMIT_PLAN_GENERATION,
            "guidance": settings.AI_RATE_LIMIT_LIVE_GUIDANCE,
            "analysis": settings.AI_RATE_LIMIT_ANALYSIS,
        }
        limit = fallback_map.get(limit_type, 10)

    # Limit-Check durchführen
    allowed = profile.check_and_increment_ai_limit(limit_type, limit)
    if not allowed:
        label_map = {
            "plan": f"{limit} Plan-Generierungen",
            "guidance": f"{limit} Live-Guidance-Calls",
            "analysis": f"{limit} Analyse-Calls",
        }
        return JsonResponse(
            {
                "error": (
                    f"Tägliches Limit erreicht ({label_map.get(limit_type, str(limit))} pro Tag). "
                    "Das Limit wird um Mitternacht UTC zurückgesetzt."
                ),
                "success": False,
                "rate_limited": True,
            },
            status=429,
        )
    return None


logger = logging.getLogger(__name__)


def _range_or_none(value: float | None, lo: float, hi: float) -> float | None:
    """Gibt value zurück wenn im Bereich [lo, hi], sonst None."""
    return value if value is not None and lo <= value <= hi else None


def _extract_deload_params(
    plan_data: dict,
) -> tuple[int | None, float | None, float | None]:
    """Extrahiert Deload-Parameter aus KI-Plan-Daten.

    Returns:
        (cycle_length, volume_multiplier, rpe_target) – je None wenn nicht vorhanden.
    """
    deload_weeks = plan_data.get("deload_weeks") or []
    cycle_length = max(2, min(12, deload_weeks[0])) if deload_weeks else None

    macrocycle = plan_data.get("macrocycle") or {}
    deload_week_data = [w for w in (macrocycle.get("weeks") or []) if w.get("is_deload")]
    volume_mult = None
    rpe_target = None
    if deload_week_data:
        first = deload_week_data[0]
        volume_mult = _range_or_none(first.get("volume_multiplier"), 0.5, 1.0)
        rpe_target = _range_or_none(first.get("intensity_target_rpe"), 5.0, 9.0)

    return cycle_length, volume_mult, rpe_target


def _apply_mesocycle_from_plan(user: User, plan_data: dict[str, Any], plan_ids: list[int]) -> None:
    """
    Setzt Mesozyklus-Tracking auf dem UserProfile basierend auf KI-Plan-Daten.
    Wird nach dem Speichern eines KI-generierten Plans aufgerufen.
    """
    if not plan_ids:
        return

    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Gruppe-ID aus dem ersten gespeicherten Plan holen
    try:
        first_plan = Plan.objects.get(id=plan_ids[0])
        if first_plan.gruppe_id:
            profile.active_plan_group = first_plan.gruppe_id
    except Plan.DoesNotExist:
        return

    cycle_length, volume_mult, rpe_target = _extract_deload_params(plan_data)
    if cycle_length is not None:
        profile.cycle_length = cycle_length
    if volume_mult is not None:
        profile.deload_volume_factor = volume_mult
    if rpe_target is not None:
        profile.deload_rpe_target = rpe_target
    if profile.deload_volume_factor < 1.0:
        profile.deload_weight_factor = round(1.0 - (1.0 - profile.deload_volume_factor) * 0.5, 2)

    profile.cycle_start_date = None
    profile.save()

    logger.info(
        f"Mesozyklus gesetzt für User {user.username}: "
        f"Gruppe={profile.active_plan_group}, Zyklus={profile.cycle_length}W, "
        f"Deload: Vol={profile.deload_volume_factor}, RPE={profile.deload_rpe_target}, "
        f"Gewicht={profile.deload_weight_factor}"
    )


# ---------------------------------------------------------------------------
# Private helpers for workout_recommendations
# ---------------------------------------------------------------------------

PRIORITAET_ORDER = {"hoch": 0, "mittel": 1, "niedrig": 2, "info": 3}


def _build_muskelgruppe_stats(saetze) -> dict:
    """Baut Stats-Dict pro Muskelgruppe (RPE-gewichtete eff. Wdh + Satz-Anzahl)."""
    stats = {}
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        gruppe_saetze = saetze.filter(uebung__muskelgruppe=gruppe_key)
        effektive_wdh = sum(
            s.wiederholungen * (float(s.rpe) / 10.0)
            for s in gruppe_saetze
            if s.wiederholungen and s.rpe
        )
        if effektive_wdh > 0:
            stats[gruppe_key] = {
                "name": gruppe_name,
                "effektive_wdh": effektive_wdh,
                "saetze": gruppe_saetze.count(),
            }
    return stats


def _get_muscle_balance_empfehlung(letzte_30_tage_saetze, block_typ: str | None = None) -> list:
    """Analysiert Muskelgruppen-Balance mit gruppenspezifischen Volumen-Schwellenwerten.

    Phase 12: Differenzierte Schwellenwerte pro Muskelgruppengröße statt
    pauschaler relativer Heuristik. Block-Typ skaliert die Schwellenwerte.
    """
    muskelgruppen_stats = _build_muskelgruppe_stats(letzte_30_tage_saetze)

    if not muskelgruppen_stats:
        return []

    profil = get_modus_profil(block_typ)
    empfehlungen = []

    for gruppe_key, data in muskelgruppen_stats.items():
        schwellenwerte = get_volumen_schwellenwerte(gruppe_key, block_typ)
        if schwellenwerte is None:
            continue

        min_sets, max_sets = schwellenwerte
        saetze = data["saetze"]

        if saetze < min_sets:
            passende_uebungen = Uebung.objects.filter(muskelgruppe=gruppe_key)[:3]
            empfehlungen.append(
                {
                    "typ": "muskelgruppe",
                    "prioritaet": "hoch",
                    "titel": f'{data["name"]} – zu wenig Volumen',
                    "beschreibung": (
                        f'{data["name"]}: {saetze} Sätze in 30 Tagen '
                        f"(Empfehlung: mindestens {min_sets} Sätze)."
                    ),
                    "empfehlung": profil["volumen_empfehlung"],
                    "uebungen": [{"id": u.id, "name": u.bezeichnung} for u in passende_uebungen],
                }
            )
        elif saetze > max_sets:
            empfehlungen.append(
                {
                    "typ": "muskelgruppe",
                    "prioritaet": "niedrig",
                    "titel": f'{data["name"]} – sehr hohes Volumen',
                    "beschreibung": (
                        f'{data["name"]}: {saetze} Sätze in 30 Tagen '
                        f"(Empfehlung: maximal {max_sets} Sätze). "
                        f"Übermäßiges Volumen kann die Regeneration beeinträchtigen."
                    ),
                    "empfehlung": (
                        f'Reduziere das Volumen für {data["name"]} oder '
                        f"verteile die Sätze besser über den Monat."
                    ),
                    "uebungen": [],
                }
            )

    return empfehlungen


def _get_push_pull_empfehlung(letzte_30_tage_saetze) -> list:
    """Analysiert Push/Pull-Balance und gibt Empfehlung zurück.

    Konvention (angelehnt an Schultergesundheits-Empfehlungen der Sportmedizin):
    - Push >> Pull (ratio > 2.0): deutliches Ungleichgewicht, Risiko für Schulterimpingements.
      Threshold 2.0 statt 1.5: bis 2:1 gilt als tolerable Varianz im Alltag (viele Push-Übungen
      enthalten auch Schulter-Stabilisierung; erst ab 2.0 klares Ungleichgewicht).
    - Pull >= Push (ratio <= 1.0): neutral bis positiv für Schultergesundheit.
      → KEIN Warning bei zu viel Pull – das ist die häufig empfohlene Richtung.
    - Keine Push-Sätze (ratio = 999): gesonderte Meldung.
    """
    push_gruppen = ["BRUST", "SCHULTER_VORN", "SCHULTER_SEIT", "TRIZEPS"]
    pull_gruppen = ["RUECKEN_LAT", "RUECKEN_TRAPEZ", "BIZEPS"]

    def _eff_wdh(gruppen):
        return sum(
            s.wiederholungen * (float(s.rpe) / 10.0)
            for s in letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=gruppen)
            if s.wiederholungen and s.rpe
        )

    push_effektiv = _eff_wdh(push_gruppen)
    pull_effektiv = _eff_wdh(pull_gruppen)
    push_saetze = letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=push_gruppen).count()
    pull_saetze = letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=pull_gruppen).count()

    if not (push_effektiv > 0 and pull_effektiv > 0):
        return []

    ratio = push_effektiv / pull_effektiv if pull_effektiv > 0 else 999

    # Nur warnen wenn Push deutlich überwiegt (schadet der Schultergesundheit).
    # Threshold 2.0: bis 2:1 gilt als tolerable Varianz; erst darüber klares Risiko.
    # Mehr Pull als Push ist kein Problem – im Gegenteil, oft empfohlen.
    if ratio > 2.0:
        return [
            {
                "typ": "balance",
                "prioritaet": "mittel",
                "titel": "Zu viel Push, zu wenig Pull",
                "beschreibung": (
                    f"Dein Push-Training ({push_saetze} Sätze, {int(push_effektiv)} eff. Wdh) ist "
                    f"{ratio:.1f}× intensiver als dein Pull-Training ({pull_saetze} Sätze, "
                    f"{int(pull_effektiv)} eff. Wdh). Langfristig erhöht das das Risiko für "
                    f"Schulterimpingements und Haltungsprobleme."
                ),
                "empfehlung": "Mehr Zugübungen (Rücken, Bizeps) einbauen für 1:1 oder besser 1:2 Push:Pull",
                "uebungen": [
                    {"id": u.id, "name": u.bezeichnung}
                    for u in Uebung.objects.filter(muskelgruppe__in=pull_gruppen)[:3]
                ],
            }
        ]
    # Pull >= Push: kein Problem, keine Empfehlung nötig
    return []


def _is_stagnating(max_gewichte: list[float], rpe_werte: list[float] | None = None) -> bool:
    """Gibt True zurück wenn kein Fortschritt und konstantes Gewicht.

    Berücksichtigt RPE-Trend: sinkender RPE bei gleichem Gewicht
    ist Konsolidierung (kein echtes Plateau).
    """
    if len(max_gewichte) < 4:
        return False
    erste = max_gewichte[:2]
    letzte = max_gewichte[-2:]
    avg_erste = sum(erste) / len(erste)
    avg_letzte = sum(letzte) / len(letzte)
    fortschritt = ((avg_letzte - avg_erste) / avg_erste * 100) if avg_erste > 0 else 0
    gewicht_stagniert = fortschritt < 2.5 and len(set(max_gewichte)) == 1

    if not gewicht_stagniert:
        return False

    # Prüfe RPE-Trend: sinkender RPE = Konsolidierung, kein Plateau
    if rpe_werte and len(rpe_werte) >= 4:
        rpe_erste = rpe_werte[:2]
        rpe_letzte = rpe_werte[-2:]
        avg_rpe_erste = sum(rpe_erste) / len(rpe_erste)
        avg_rpe_letzte = sum(rpe_letzte) / len(rpe_letzte)
        if avg_rpe_erste - avg_rpe_letzte >= 0.5:
            return False  # RPE sinkt → Konsolidierung

    return True


def _get_stagnation_empfehlung(letzte_60_tage_saetze, block_typ: str | None = None) -> list:
    """Erkennt stagnierende Übungen (kein Fortschritt in 60 Tagen).

    Berücksichtigt RPE-Trend: sinkender RPE bei gleichem Gewicht
    wird nicht als Stagnation gewertet.
    Phase 12: Stagnation-Tipps sind modusabhängig; im Deload unterdrückt.
    """
    profil = get_modus_profil(block_typ)
    stagnation_tipp = profil["stagnation_tipp"]
    if not stagnation_tipp:
        return []

    uebung_trainings: dict = defaultdict(list)
    for satz in letzte_60_tage_saetze.select_related("uebung", "einheit"):
        if satz.gewicht and satz.gewicht > 0:
            uebung_trainings[satz.uebung_id].append(
                {
                    "datum": satz.einheit.datum,
                    "gewicht": float(satz.gewicht),
                    "rpe": float(satz.rpe) if satz.rpe is not None else None,
                }
            )

    # Batch-Query: alle benötigten Uebungen auf einmal laden (verhindert N+1)
    uebungen_map = {u.id: u for u in Uebung.objects.filter(id__in=list(uebung_trainings.keys()))}

    empfehlungen = []
    for uebung_id, saetze_list in uebung_trainings.items():
        trainings_max: dict = defaultdict(float)
        trainings_rpe: dict = defaultdict(list)
        for s in saetze_list:
            trainings_max[s["datum"]] = max(trainings_max[s["datum"]], s["gewicht"])
            if s["rpe"] is not None:
                trainings_rpe[s["datum"]].append(s["rpe"])
        max_gewichte = [g for _, g in sorted(trainings_max.items())]

        # Durchschnitts-RPE pro Training, chronologisch sortiert
        rpe_pro_training = []
        for datum in sorted(trainings_rpe.keys()):
            rpe_list = trainings_rpe[datum]
            rpe_pro_training.append(sum(rpe_list) / len(rpe_list))

        if len(max_gewichte) < 4:
            continue

        if _is_stagnating(max_gewichte, rpe_pro_training):
            uebung = uebungen_map.get(uebung_id)
            if uebung is None:
                continue
            empfehlungen.append(
                {
                    "typ": "stagnation",
                    "prioritaet": "niedrig",
                    "titel": f"{uebung.bezeichnung}: Stagnation",
                    "beschreibung": (
                        f"Bei dieser Übung gab es in den letzten {len(max_gewichte)} Trainings "
                        f"keinen Fortschritt (konstant {max_gewichte[-1]} kg)."
                    ),
                    "empfehlung": stagnation_tipp,
                    "uebungen": [],
                }
            )
    return empfehlungen


def _get_frequenz_empfehlung(user, heute) -> list:
    """Gibt Empfehlung bei zu niedriger Trainingsfrequenz zurück."""
    letzte_woche = Trainingseinheit.objects.filter(
        user=user, datum__gte=heute - timedelta(days=7)
    ).count()
    vorige_woche = Trainingseinheit.objects.filter(
        user=user, datum__gte=heute - timedelta(days=14), datum__lt=heute - timedelta(days=7)
    ).count()

    if letzte_woche == 0:
        return [
            {
                "typ": "frequenz",
                "prioritaet": "hoch",
                "titel": "Keine Trainings diese Woche",
                "beschreibung": "Du hast diese Woche noch nicht trainiert!",
                "empfehlung": "Starte heute ein Training - Konsistenz ist der Schlüssel zum Erfolg!",
                "uebungen": [],
            }
        ]
    if letzte_woche < vorige_woche - 1:
        return [
            {
                "typ": "frequenz",
                "prioritaet": "mittel",
                "titel": "Trainingsfrequenz gesunken",
                "beschreibung": f"Diese Woche: {letzte_woche} Trainings, letzte Woche: {vorige_woche} Trainings.",
                "empfehlung": "Versuche deine Konsistenz beizubehalten!",
                "uebungen": [],
            }
        ]
    return []


def _get_rpe_empfehlung(letzte_30_tage_saetze, block_typ: str | None = None) -> list:
    """Gibt RPE-basierte Intensitätsempfehlung zurück.

    Phase 12: RPE-Zielbereiche und Texte sind modusabhängig.
    Im Deload wird 'zu niedrig' unterdrückt.
    """
    avg_rpe = letzte_30_tage_saetze.filter(rpe__isnull=False).aggregate(Avg("rpe"))["rpe__avg"]
    if not avg_rpe:
        return []

    profil = get_modus_profil(block_typ)
    rpe_min, rpe_max = profil["rpe_target_range"]

    if avg_rpe < rpe_min and profil["rpe_zu_niedrig_text"]:
        return [
            {
                "typ": "intensitaet",
                "prioritaet": "mittel",
                "titel": "Zu niedrige Trainingsintensität",
                "beschreibung": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}.",
                "empfehlung": profil["rpe_zu_niedrig_text"],
                "uebungen": [],
            }
        ]
    if avg_rpe > rpe_max and profil["rpe_zu_hoch_text"]:
        return [
            {
                "typ": "intensitaet",
                "prioritaet": "hoch",
                "titel": "Zu hohe Trainingsintensität",
                "beschreibung": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}.",
                "empfehlung": profil["rpe_zu_hoch_text"],
                "uebungen": [],
            }
        ]
    return []


def _get_rep_range_advice(
    pct_kraft: float,
    pct_hypertrophie: float,
    pct_ausdauer: float,
    block_typ: str | None,
) -> str:
    """Generiert kontextspezifischen Ratschlag zur Rep-Range-Verteilung."""
    if block_typ == "kraft" and pct_kraft < 40:
        return (
            "Im Kraft-Modus sollten mindestens 40% deiner Sätze im Kraftbereich "
            "(1-6 Reps) liegen. Erhöhe den Anteil schwerer Sätze."
        )
    if block_typ == "masse" and pct_hypertrophie < 40:
        return (
            "Im Aufbau-Modus sollten mindestens 40% deiner Sätze im "
            "Hypertrophiebereich (7-12 Reps) liegen."
        )
    if block_typ == "definition" and pct_kraft + pct_hypertrophie < 50:
        return (
            "Im Definitionsmodus sollte der Großteil deiner Sätze schwer sein "
            "(6-12 Reps) um Muskelmasse zu erhalten."
        )
    return "Gute Mischung! Variiere bewusst zwischen Kraft-, Hypertrophie- und Ausdauerbereichen."


def _get_rep_range_empfehlung(letzte_30_tage_saetze, block_typ: str | None = None) -> list:
    """Analysiert die Wiederholungsbereich-Verteilung und gibt Empfehlungen.

    Phase 12.3: Berechnet den Anteil der Sätze in Kraft (1-6), Hypertrophie (7-12)
    und Ausdauer (13+) Bereichen. Im Definitionsmodus empfiehlt schwere
    Compounds statt leichter Sätze.
    """
    counts = {"kraft": 0, "hypertrophie": 0, "ausdauer": 0}
    total = 0

    for satz in letzte_30_tage_saetze:
        if satz.wiederholungen:
            bereich = klassifiziere_rep_range(satz.wiederholungen)
            counts[bereich] += 1
            total += 1

    if total < 10:
        return []

    pct_kraft = counts["kraft"] / total * 100
    pct_hypertrophie = counts["hypertrophie"] / total * 100
    pct_ausdauer = counts["ausdauer"] / total * 100

    empfehlungen = []

    # Basis-Info: Verteilungsanalyse (immer anzeigen wenn genug Daten)
    empfehlungen.append(
        {
            "typ": "rep_range",
            "prioritaet": "info",
            "titel": "Wiederholungsbereich-Verteilung",
            "beschreibung": (
                f"Kraft (1-6 Reps): {pct_kraft:.0f}% | "
                f"Hypertrophie (7-12 Reps): {pct_hypertrophie:.0f}% | "
                f"Ausdauer (13+ Reps): {pct_ausdauer:.0f}%"
            ),
            "empfehlung": _get_rep_range_advice(
                pct_kraft, pct_hypertrophie, pct_ausdauer, block_typ
            ),
            "uebungen": [],
            "rep_range_data": {
                "kraft_pct": round(pct_kraft),
                "hypertrophie_pct": round(pct_hypertrophie),
                "ausdauer_pct": round(pct_ausdauer),
                "total_sets": total,
            },
        }
    )

    # Kontextspezifische Warnung im Definitionsmodus
    if block_typ == "definition" and pct_ausdauer > 30:
        compound_uebungen = list(
            Uebung.objects.filter(bewegungstyp__in=["DRUECKEN", "ZIEHEN", "BEUGEN", "HEBEN"])[:4]
        )
        empfehlungen.append(
            {
                "typ": "rep_range",
                "prioritaet": "mittel",
                "titel": "Zu viele leichte Sätze im Definitionsmodus",
                "beschreibung": (
                    f"{pct_ausdauer:.0f}% deiner Sätze sind im Ausdauerbereich (13+ Reps). "
                    f"Im Defizit ist schweres Training effektiver zum Muskelerhalt."
                ),
                "empfehlung": (
                    "Ersetze leichte Sätze durch schwere Compounds (6-8 Reps). "
                    "Das erhält mehr Muskelmasse bei Kaloriendefizit."
                ),
                "uebungen": [{"id": u.id, "name": u.bezeichnung} for u in compound_uebungen],
            }
        )

    return empfehlungen


@login_required
def workout_recommendations(request: HttpRequest) -> HttpResponse:
    """Intelligente Trainingsempfehlungen basierend auf Datenanalyse."""
    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    letzte_60_tage = heute - timedelta(days=60)

    alle_saetze = Satz.objects.filter(einheit__user=request.user, ist_aufwaermsatz=False)
    letzte_30_tage_saetze = alle_saetze.filter(einheit__datum__gte=letzte_30_tage)
    letzte_60_tage_saetze = alle_saetze.filter(einheit__datum__gte=letzte_60_tage)

    # Aktiven Trainingsblock ermitteln (Phase 12)
    active_block = (
        Trainingsblock.objects.filter(user=request.user, end_datum__isnull=True)
        .order_by("-start_datum")
        .first()
    )
    block_typ = active_block.typ if active_block else None

    empfehlungen = (
        _get_muscle_balance_empfehlung(letzte_30_tage_saetze, block_typ)
        + _get_push_pull_empfehlung(letzte_30_tage_saetze)
        + _get_stagnation_empfehlung(letzte_60_tage_saetze, block_typ)
        + _get_frequenz_empfehlung(request.user, heute)
        + _get_rpe_empfehlung(letzte_30_tage_saetze, block_typ)
        + _get_rep_range_empfehlung(letzte_30_tage_saetze, block_typ)
    )

    if not empfehlungen:
        empfehlungen.append(
            {
                "typ": "erfolg",
                "prioritaet": "info",
                "titel": "\u270c\ufe0f Perfekt ausgewogenes Training!",
                "beschreibung": "Dein Training ist optimal ausbalanciert. Alle Muskelgruppen werden gleichm\u00e4\u00dfig trainiert!",
                "empfehlung": "Weiter so! Bleib konsistent und die Erfolge kommen.",
                "uebungen": [],
            }
        )

    empfehlungen.sort(key=lambda x: PRIORITAET_ORDER.get(x["prioritaet"], 99))

    context = {
        "empfehlungen": empfehlungen,
        "analysiert_tage": 30,
        "active_block": active_block,
        "block_typ_display": active_block.get_typ_display() if active_block else None,
    }

    return render(request, "core/workout_recommendations.html", context)


_VALID_PLAN_TYPES = ["2er-split", "3er-split", "4er-split", "ganzkörper", "push-pull-legs"]
_VALID_PERIODIZATIONS = ["linear", "wellenfoermig", "block"]
_VALID_PROFILES = ["kraft", "hypertrophie", "definition"]


def _handle_save_cached_plan(user: User, data: dict) -> JsonResponse:
    """Speichert einen gecachten KI-Plan direkt in die DB."""
    from ai_coach.plan_generator import PlanGenerator

    generator = PlanGenerator(user_id=user.id, plan_type="3er-split")
    plan_data = data["plan_data"]
    plan_ids = generator._save_plan_to_db(plan_data)
    # Nur als aktiv setzen wenn User das explizit gewählt hat (default: False)
    if data.get("set_as_active", False):
        _apply_mesocycle_from_plan(user, plan_data, plan_ids)
    return JsonResponse(
        {
            "success": True,
            "plan_ids": plan_ids,
            "plan_name": plan_data.get("plan_name", ""),
            "sessions": len(plan_data.get("sessions", [])),
            "message": f"Plan '{plan_data.get('plan_name', '')}' erfolgreich gespeichert!",
        }
    )


def _validate_plan_gen_params(
    data: dict,
) -> tuple[str, int, int, str, str, bool, int] | JsonResponse:
    """Validiert und normalisiert Parameter für die Plan-Generierung.

    Returns:
        (plan_type, sets_per_session, analysis_days, periodization,
         target_profile, preview_only, duration_weeks) bei Erfolg,
        sonst JsonResponse mit Fehler.
    """
    plan_type = data.get("plan_type", "3er-split")
    sets_per_session = int(data.get("sets_per_session", 18))
    analysis_days = int(data.get("analysis_days", 30))
    periodization = data.get("periodization", "linear")
    target_profile = data.get("target_profile", "hypertrophie")
    preview_only = data.get("previewOnly", False)
    duration_weeks = int(data.get("duration_weeks", 12))

    if plan_type not in _VALID_PLAN_TYPES:
        return JsonResponse(
            {"error": f'Ungültiger Plan-Typ. Erlaubt: {", ".join(_VALID_PLAN_TYPES)}'}, status=400
        )
    if sets_per_session < 10 or sets_per_session > 30:
        return JsonResponse({"error": "Sätze pro Session muss zwischen 10-30 liegen"}, status=400)
    if duration_weeks < 4 or duration_weeks > 16:
        return JsonResponse({"error": "Plandauer muss zwischen 4 und 16 Wochen liegen"}, status=400)
    if periodization not in _VALID_PERIODIZATIONS:
        periodization = "linear"
    if target_profile not in _VALID_PROFILES:
        target_profile = "hypertrophie"

    return (
        plan_type,
        sets_per_session,
        analysis_days,
        periodization,
        target_profile,
        preview_only,
        duration_weeks,
    )


def _execute_plan_generation(
    user: User, generator, preview_only: bool, use_openrouter: bool
) -> JsonResponse:
    """Führt die Plan-Generierung aus und gibt die JsonResponse zurück."""
    cost = 0.003 if use_openrouter else 0.0
    model = "OpenRouter 70B" if use_openrouter else "Ollama 8B"

    if preview_only:
        result = generator.generate(save_to_db=False)
        return JsonResponse(
            {
                "success": True,
                "preview": True,
                "plan_data": result.get("plan_data", {}),
                "cost": cost,
                "model": model,
            }
        )

    result = generator.generate(save_to_db=True)
    if result.get("success") and result.get("plan_ids"):
        _apply_mesocycle_from_plan(user, result.get("plan_data", {}), result.get("plan_ids", []))
    plan_name = result.get("plan_data", {}).get("plan_name", "")
    return JsonResponse(
        {
            "success": True,
            "plan_ids": result.get("plan_ids", []),
            "plan_name": plan_name,
            "sessions": len(result.get("plan_data", {}).get("sessions", [])),
            "cost": cost,
            "model": model,
            "message": f"Plan '{plan_name}' erfolgreich erstellt!",
        }
    )


@login_required
def generate_plan_api(request: HttpRequest) -> JsonResponse:
    """
    API Endpoint für KI-Plan-Generierung über Web-Interface
    POST: { plan_type, sets_per_session, analysis_days? }
    oder: { saveCachedPlan: true, plan_data: {...} }
    Returns: { success, plan_ids, cost, message }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # Rate Limit nur für echte Generierungen (nicht für saveCachedPlan)
    # saveCachedPlan: Plan wurde bereits via Stream generiert (Counter schon erhöht)
    malformed_json = False
    try:
        _peek = json.loads(request.body)
        _is_save_only = bool(_peek.get("saveCachedPlan") and _peek.get("plan_data"))
    except json.JSONDecodeError:
        _peek = None
        _is_save_only = False
        malformed_json = True
    except Exception:
        _peek = None
        _is_save_only = False

    if malformed_json:
        return JsonResponse({"error": "Ungültiges JSON im Request-Body"}, status=400)

    if not _is_save_only:
        rate_limit_response = _check_ai_rate_limit(request, "plan")
        if rate_limit_response:
            return rate_limit_response

    try:
        data = _peek if _peek is not None else json.loads(request.body)

        # Check ob wir einen gecachten Plan speichern sollen (zählt nicht als Generierung)
        if data.get("saveCachedPlan") and data.get("plan_data"):
            return _handle_save_cached_plan(request.user, data)

        params = _validate_plan_gen_params(data)
        if isinstance(params, JsonResponse):
            return params
        (
            plan_type,
            sets_per_session,
            analysis_days,
            periodization,
            target_profile,
            preview_only,
            duration_weeks,
        ) = params

        # Plan Generator importieren (korrekter Package-Import)
        from ai_coach.plan_generator import PlanGenerator

        use_openrouter = (
            not settings.DEBUG or os.getenv("USE_OPENROUTER", "False").lower() == "true"
        )
        generator = PlanGenerator(
            user_id=request.user.id,
            plan_type=plan_type,
            analysis_days=analysis_days,
            sets_per_session=sets_per_session,
            periodization=periodization,
            target_profile=target_profile,
            use_openrouter=use_openrouter,
            fallback_to_openrouter=True,
            duration_weeks=duration_weeks,
        )
        return _execute_plan_generation(request.user, generator, preview_only, use_openrouter)

    except Exception as e:
        logger.error(f"Generate Plan API Error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Plan-Generierung fehlgeschlagen. Bitte später erneut versuchen.",
                "success": False,
            },
            status=500,
        )


@login_required
def analyze_plan_api(request: HttpRequest) -> JsonResponse:
    """
    Regelbasierte Plan-Analyse (kostenlos)
    GET /api/analyze-plan/<plan_id>/

    Returns:
        {
            'warnings': [...],
            'suggestions': [...],
            'metrics': {...}
        }
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET request required"}, status=405)

    try:
        from ai_coach.plan_adapter import PlanAdapter

        plan_id = request.GET.get("plan_id")
        try:
            days = int(request.GET.get("days", 30))
        except (TypeError, ValueError):
            return JsonResponse({"error": "days muss eine ganze Zahl sein"}, status=400)

        if days <= 0:
            return JsonResponse({"error": "days muss größer als 0 sein"}, status=400)

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne analysieren
        plan = Plan.objects.filter(id=plan_id, user=request.user).first()
        if not plan:
            return JsonResponse({"error": "Plan nicht gefunden"}, status=404)

        adapter = PlanAdapter(plan_id=plan.id, user_id=request.user.id)
        result = adapter.analyze_plan_performance(days=days)

        return JsonResponse({"success": True, "plan_id": plan.id, "plan_name": plan.name, **result})

    except Exception as e:
        logger.error(f"Analyze Plan API Error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Plan-Analyse fehlgeschlagen. Bitte später erneut versuchen.",
                "success": False,
            },
            status=500,
        )


@login_required
def optimize_plan_api(request: HttpRequest) -> JsonResponse:
    """
    KI-gestützte Plan-Optimierung (~0.003€)
    POST /api/optimize-plan/

    Body:
        {
            'plan_id': 1,
            'days': 30
        }

    Returns:
        {
            'optimizations': [...],
            'cost': 0.003,
            'model': 'llama-3.1-70b'
        }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST request required"}, status=405)

    # Rate Limit: 10 Analyse/Optimierungs-Calls pro Tag
    rate_limit_response = _check_ai_rate_limit(request, "analysis")
    if rate_limit_response:
        return rate_limit_response

    try:
        from ai_coach.plan_adapter import PlanAdapter

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Ungültiges JSON im Request-Body"}, status=400)

        plan_id = data.get("plan_id")
        try:
            days = int(data.get("days", 30))
        except (TypeError, ValueError):
            return JsonResponse({"error": "days muss eine ganze Zahl sein"}, status=400)

        if days <= 0:
            return JsonResponse({"error": "days muss größer als 0 sein"}, status=400)

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne optimieren
        plan = Plan.objects.filter(id=plan_id, user=request.user).first()
        if not plan:
            return JsonResponse({"error": "Plan nicht gefunden"}, status=404)

        adapter = PlanAdapter(plan_id=plan.id, user_id=request.user.id)
        result = adapter.suggest_optimizations(days=days)

        return JsonResponse({"success": True, "plan_id": plan.id, "plan_name": plan.name, **result})

    except Exception as e:
        logger.error(f"Optimize Plan API Error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Plan-Optimierung fehlgeschlagen. Bitte später erneut versuchen.",
                "success": False,
            },
            status=500,
        )


def _apply_replace_exercise(plan: Plan, opt: dict) -> str | None:
    old_name = opt.get("old_exercise", "")
    new_name = opt.get("new_exercise", "")
    old_pu = PlanUebung.objects.filter(
        plan=plan, uebung__bezeichnung__icontains=old_name.split("(")[0].strip()
    ).first()
    if not old_pu:
        return f"Übung '{old_name}' nicht im Plan gefunden"
    new_uebung = Uebung.objects.filter(
        bezeichnung__icontains=new_name.split("(")[0].strip()
    ).first()
    if not new_uebung:
        return f"Übung '{new_name}' nicht gefunden"
    old_pu.uebung = new_uebung
    old_pu.save()
    return None


def _apply_adjust_volume(plan: Plan, opt: dict) -> str | None:
    exercise_name = opt.get("exercise", "")
    plan_pu = PlanUebung.objects.filter(
        plan=plan, uebung__bezeichnung__icontains=exercise_name.split("(")[0].strip()
    ).first()
    if not plan_pu:
        return f"Übung '{exercise_name}' nicht im Plan gefunden"
    if opt.get("new_sets"):
        plan_pu.saetze_ziel = opt["new_sets"]
    if opt.get("new_reps"):
        plan_pu.wiederholungen_ziel = opt["new_reps"]
    plan_pu.save()
    return None


def _apply_add_exercise(plan: Plan, opt: dict) -> str | None:
    exercise_name = opt.get("exercise", "")
    uebung = Uebung.objects.filter(
        bezeichnung__icontains=exercise_name.split("(")[0].strip()
    ).first()
    if not uebung:
        return f"Übung '{exercise_name}' nicht gefunden"
    max_r = (
        PlanUebung.objects.filter(plan=plan).aggregate(Max("reihenfolge"))["reihenfolge__max"] or 0
    )
    PlanUebung.objects.create(
        plan=plan,
        uebung=uebung,
        reihenfolge=max_r + 1,
        saetze_ziel=opt.get("sets", 3),
        wiederholungen_ziel=opt.get("reps", "8-12"),
    )
    return None


_OPT_HANDLERS = {
    "replace_exercise": _apply_replace_exercise,
    "adjust_volume": _apply_adjust_volume,
    "add_exercise": _apply_add_exercise,
}


def _apply_single_optimization(plan: Plan, opt: dict) -> str | None:
    """Wendet eine einzelne Optimierung auf den Plan an.

    Returns:
        Fehlermeldung als String wenn fehlgeschlagen, None bei Erfolg/No-op.
    """
    handler = _OPT_HANDLERS.get(opt.get("type"))
    if handler is None:
        return None  # "deload_recommended" und unbekannte Typen: No-op
    return handler(plan, opt)


@login_required
def apply_optimizations_api(request: HttpRequest) -> JsonResponse:
    """
    Wendet ausgewählte Optimierungen auf den Plan an
    POST /api/apply-optimizations/

    Body:
        {
            'plan_id': 1,
            'optimizations': [
                {
                    'type': 'replace_exercise',
                    'exercise_id': 15,
                    'old_exercise': 'Bankdrücken',
                    'new_exercise': 'Schrägbankdrücken'
                },
                ...
            ]
        }

    Returns:
        {
            'success': True,
            'applied_count': 3,
            'message': '3 Optimierungen erfolgreich angewendet'
        }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST request required"}, status=405)

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Ungültiges JSON im Request-Body"}, status=400)

        plan_id = data.get("plan_id")
        optimizations = data.get("optimizations", [])

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne bearbeiten
        plan = Plan.objects.filter(id=plan_id, user=request.user).first()
        if not plan:
            return JsonResponse({"error": "Plan nicht gefunden"}, status=404)

        applied_count = 0
        errors = []

        for opt in optimizations:
            try:
                error = _apply_single_optimization(plan, opt)
                if error:
                    errors.append(error)
                else:
                    applied_count += 1
            except Exception as e:
                opt_type = opt.get("type", "?")
                logger.error(f"Optimization error for {opt_type}: {e}", exc_info=True)
                errors.append(f"{opt_type}: Fehler beim Anwenden")

        return JsonResponse(
            {
                "success": True,
                "applied_count": applied_count,
                "errors": errors,
                "message": f"{applied_count} Optimierung(en) erfolgreich angewendet",
            }
        )

    except Exception as e:
        logger.error(f"Apply Optimizations API Error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Optimierungen konnten nicht angewendet werden. Bitte später erneut versuchen.",
                "success": False,
            },
            status=500,
        )


@login_required
def live_guidance_api(request: HttpRequest) -> JsonResponse:
    """
    API Endpoint für Live-Guidance während Training
    POST: { session_id, question, exercise_id?, set_number? }
    Returns: { answer, cost, model }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    # Rate Limit: 50 Live-Guidance-Calls pro Tag
    rate_limit_response = _check_ai_rate_limit(request, "guidance")
    if rate_limit_response:
        return rate_limit_response

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Ungültiges JSON im Request-Body"}, status=400)

        session_id = data.get("session_id")
        question = data.get("question", "").strip()
        exercise_id = data.get("exercise_id")
        set_number = data.get("set_number")
        chat_history = data.get("chat_history", [])  # Chat-Historie für Konversationsgedächtnis

        if not session_id or not question:
            return JsonResponse({"error": "session_id und question erforderlich"}, status=400)

        # Prüfe ob Session dem User gehört
        session = Trainingseinheit.objects.filter(id=session_id, user=request.user).first()
        if not session:
            return JsonResponse({"error": "Trainingseinheit nicht gefunden"}, status=404)

        # Live Guidance importieren (korrekter Package-Import)
        from ai_coach.live_guidance import LiveGuidance

        # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
        use_openrouter = (
            not settings.DEBUG or os.getenv("USE_OPENROUTER", "False").lower() == "true"
        )

        guidance = LiveGuidance(use_openrouter=use_openrouter)
        result = guidance.get_guidance(
            trainingseinheit_id=session_id,
            user_question=question,
            current_uebung_id=exercise_id,
            current_satz_number=set_number,
            chat_history=chat_history,  # Chat-Historie für Konversationsgedächtnis
        )

        # Security: Validate result structure before returning
        if not isinstance(result, dict) or "answer" not in result:
            logger.error("Invalid result structure from get_guidance")
            return JsonResponse({"error": "Ungültige Antwort vom AI-Coach"}, status=500)

        # Explizit nur bekannte skalare Felder extrahieren – bricht CodeQL Taint-Chain
        # result["context"] enthält DB-Werte (Uebung.bezeichnung etc.) und darf nie
        # direkt in die Response fließen
        answer: str = str(result.get("answer", "Keine Antwort"))
        cost: float = float(result.get("cost") or 0)
        model_name: str = str(result.get("model", "unknown"))

        return JsonResponse(
            {
                "answer": answer,
                "cost": cost,
                "model": model_name,
            }
        )

    except Exception as e:
        logger.error(f"Live Feedback API Error: {e}", exc_info=True)
        return JsonResponse(
            {"error": "Feedback konnte nicht gespeichert werden. Bitte später erneut versuchen."},
            status=500,
        )


@login_required
def generate_plan_stream_api(request: HttpRequest) -> HttpResponse:
    """
    Server-Sent Events Endpoint für KI-Plan-Generierung mit Echtzeit-Progress.

    GET  /api/generate-plan/stream/?plan_type=3er-split&sets_per_session=18&...

    Schickt SSE-Events:
      data: {"progress": 35, "step": "KI generiert Plan...", "done": false}

    Letztes Event bei Erfolg:
      data: {"progress": 100, "done": true, "success": true,
             "preview": true, "plan_data": {...}, "cost": 0.003}

    Letztes Event bei Fehler:
      data: {"done": true, "success": false, "error": "..."}

    Warum GET statt POST: SSE-Streams müssen per GET aufgebaut werden.
    Parameter kommen als Query-String. CSRF wird über Cookie-basierte
    Session-Auth (login_required) abgesichert.
    """
    if request.method != "GET":
        return HttpResponse("GET required", status=405)

    # Rate Limit: teilt Budget mit generate_plan_api (gleicher "plan"-Counter)
    rate_limit_response = _check_ai_rate_limit(request, "plan")
    if rate_limit_response:
        # SSE-Client erwartet text/event-stream – JSON-Response als SSE-Error wrappen
        import json as _json

        error_data = _json.loads(rate_limit_response.content)

        def _error_stream():
            yield f"data: {_json.dumps({'done': True, 'success': False, 'error': error_data['error']})}\n\n"

        from django.http import StreamingHttpResponse

        return StreamingHttpResponse(_error_stream(), content_type="text/event-stream", status=429)

    import threading

    from django.http import StreamingHttpResponse

    # Parameter aus Query-String lesen
    data = {
        "plan_type": request.GET.get("plan_type", "3er-split"),
        "sets_per_session": request.GET.get("sets_per_session", "18"),
        "analysis_days": request.GET.get("analysis_days", "30"),
        "periodization": request.GET.get("periodization", "linear"),
        "target_profile": request.GET.get("target_profile", "hypertrophie"),
        "duration_weeks": request.GET.get("duration_weeks", "12"),
        "previewOnly": True,  # Stream gibt immer Preview zurück; User bestätigt danach
    }

    params = _validate_plan_gen_params(data)
    if isinstance(params, JsonResponse):
        # Validierungsfehler als SSE-Error-Event zurückgeben
        error_msg = json.loads(params.content).get("error", "Ungültige Parameter")

        def error_stream():
            yield f'data: {json.dumps({"done": True, "success": False, "error": error_msg})}\n\n'

        return StreamingHttpResponse(error_stream(), content_type="text/event-stream")

    plan_type, sets_per_session, analysis_days, periodization, target_profile, _, duration_weeks = (
        params
    )

    use_openrouter = not settings.DEBUG or os.getenv("USE_OPENROUTER", "False").lower() == "true"

    # Thread-sichere Queue für Events zwischen Generator-Thread und SSE-Stream
    import queue

    event_queue: queue.Queue = queue.Queue()

    def progress_callback(percent: int, step: str) -> None:
        """Wird vom PlanGenerator aufgerufen und packt Event in Queue."""
        event_queue.put({"progress": percent, "step": step, "done": False})

    def run_generator():
        """Läuft in separatem Thread – blockiert nicht den SSE-Stream."""
        try:
            from ai_coach.plan_generator import PlanGenerator

            generator = PlanGenerator(
                user_id=request.user.id,
                plan_type=plan_type,
                analysis_days=analysis_days,
                sets_per_session=sets_per_session,
                periodization=periodization,
                target_profile=target_profile,
                use_openrouter=use_openrouter,
                fallback_to_openrouter=True,
                progress_callback=progress_callback,
                duration_weeks=duration_weeks,
            )
            result = generator.generate(save_to_db=False)

            if result.get("success"):
                event_queue.put(
                    {
                        "progress": 100,
                        "done": True,
                        "success": True,
                        "preview": True,
                        "plan_data": result.get("plan_data", {}),
                        "coverage_warnings": result.get("coverage_warnings", []),
                        "cost": 0.003 if use_openrouter else 0.0,
                        "model": "Gemini 2.5 Flash" if use_openrouter else "Ollama",
                    }
                )
            else:
                errors = result.get("errors") or ["Generierung fehlgeschlagen"]
                event_queue.put(
                    {
                        "done": True,
                        "success": False,
                        "error": errors[0] if errors else "Unbekannter Fehler",
                    }
                )
        except Exception as exc:
            logger.error(f"Stream Generator Error: {exc}", exc_info=True)
            event_queue.put(
                {
                    "done": True,
                    "success": False,
                    "error": "Plan-Generierung fehlgeschlagen. Bitte erneut versuchen.",
                }
            )

    # Generator im Hintergrund starten
    thread = threading.Thread(target=run_generator, daemon=True)
    thread.start()

    def event_stream():
        """Yield SSE-Events aus der Queue bis done=True empfangen wird."""
        # Initiales Event sofort senden (zeigt dem Browser: Verbindung steht)
        yield f'data: {json.dumps({"progress": 0, "step": "Starte Plan-Generierung...", "done": False})}\n\n'

        while True:
            try:
                event = event_queue.get(timeout=180)  # max 3 Minuten warten
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("done"):
                    break
            except queue.Empty:
                # Timeout – informiere Client
                yield f'data: {json.dumps({"done": True, "success": False, "error": "Timeout – bitte erneut versuchen."})}\n\n'
                break

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # nginx: Buffering deaktivieren
    return response
