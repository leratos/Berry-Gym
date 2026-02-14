"""
Exercise Library View Module

Handles exercise browsing, search, and details display functionality.
Provides views for:
- Exercise selection and muscle map visualization
- Detailed exercise information and statistics
- Exercise recommendations and alternatives
- API endpoints for exercise data retrieval and favoriting
"""

import json
import logging
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..models import BEWEGUNGS_TYP, GEWICHTS_TYP, MUSKELGRUPPEN, Satz, Uebung

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hilfstext → Muskelgruppen-Code Mapping (shared across views)
# ---------------------------------------------------------------------------
_HILFSTEXT_TO_CODE: dict[str, str] = {
    "Trizeps": "TRIZEPS",
    "Bizeps": "BIZEPS",
    "Brust": "BRUST",
    "Schulter - Vordere": "SCHULTER_VORN",
    "Schulter - Seitliche": "SCHULTER_SEIT",
    "Schulter - Hintere": "SCHULTER_HINT",
    "Bauch": "BAUCH",
    "Po": "PO",
    "Unterarme": "UNTERARME",
    "Rücken - Nacken/Trapez": "RUECKEN_TRAPEZ",
    "Rücken - Breiter Muskel": "RUECKEN_LAT",
    "Rücken - Latissimus": "RUECKEN_LAT",
    "Unterer Rücken": "RUECKEN_UNTEN",
    "Beine - Quadrizeps": "BEINE_QUAD",
    "Beine - Hamstrings": "BEINE_HAM",
    "Waden": "WADEN",
    "Adduktoren": "ADDUKTOREN",
}


def _resolve_hilfsmuskeln_labels(uebung) -> list[str]:
    """Gibt Display-Labels der Hilfsmuskeln einer Übung zurück.

    Unterstützt sowohl kommaseparierte Strings als auch Listen.
    Unbekannte Codes/Texte werden als Fallback direkt zurückgegeben.
    """
    if not uebung.hilfsmuskeln:
        return []

    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    if isinstance(uebung.hilfsmuskeln, str):
        hilfs_texte = [h.strip() for h in uebung.hilfsmuskeln.split(",")]
    else:
        hilfs_texte = list(uebung.hilfsmuskeln)

    labels = []
    for text in hilfs_texte:
        text_clean = re.sub(r"\([^)]{0,50}\)", "", text).strip()
        code = _HILFSTEXT_TO_CODE.get(text_clean)
        if code:
            labels.append(muskelgruppen_dict.get(code, text_clean))
        else:
            labels.append(text_clean)
    return labels


@login_required
def uebungen_auswahl(request: HttpRequest) -> HttpResponse:
    """Übersicht aller Übungen mit grafischer Muskelgruppen-Darstellung"""
    # Equipment-Filter: Nur Übungen mit verfügbarem Equipment
    user_equipment_ids = request.user.verfuegbares_equipment.values_list("id", flat=True)

    # Include both global exercises and user's custom exercises
    base_queryset = Uebung.objects.filter(
        Q(is_custom=False) | Q(created_by=request.user)
    ).prefetch_related("equipment", "favoriten")

    if user_equipment_ids:
        # Filter: Übungen die ALLE ihre benötigten Equipment haben ODER keine Equipment-Anforderungen
        uebungen = []
        for uebung in base_queryset.order_by("muskelgruppe", "bezeichnung"):
            required_eq_ids = set(uebung.equipment.values_list("id", flat=True))
            # Verfügbar wenn: keine Equipment nötig ODER alle benötigten Equipment verfügbar
            if not required_eq_ids or required_eq_ids.issubset(set(user_equipment_ids)):
                uebungen.append(uebung)
    else:
        # Keine Equipment ausgewählt: Nur Übungen ohne Equipment-Anforderung
        uebungen = (
            base_queryset.filter(equipment__isnull=True)
            .distinct()
            .order_by("muskelgruppe", "bezeichnung")
        )

    # Gruppiere nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []

        # Add temporary attributes for template (avoid modifying model)
        hilfs_labels = _resolve_hilfsmuskeln_labels(uebung)
        uebung.muskelgruppe_label = mg_label
        uebung.hilfsmuskeln_labels = hilfs_labels
        uebung.hilfsmuskeln_count = len(hilfs_labels)

        uebungen_nach_gruppe[mg_label].append(uebung)

    # Get all tags for filter dropdown
    from ..models import UebungTag

    all_tags = UebungTag.objects.all().order_by("name")

    context = {
        "uebungen_nach_gruppe": uebungen_nach_gruppe,
        "user_equipment": request.user.verfuegbares_equipment.all(),
        "all_tags": all_tags,
    }
    return render(request, "core/uebungen_auswahl.html", context)


@login_required
def muscle_map(request: HttpRequest) -> HttpResponse:
    """Interaktive Muscle-Map mit klickbaren Muskelgruppen"""
    # Filter nach Muskelgruppe (optional)
    selected_group = request.GET.get("muskelgruppe", None)

    if selected_group:
        uebungen = Uebung.objects.filter(muskelgruppe=selected_group).order_by("bezeichnung")
        group_label = dict(MUSKELGRUPPEN).get(selected_group, selected_group)
    else:
        uebungen = None
        group_label = None

    # Mapping: SVG-ID -> Muskelgruppe
    muscle_mapping = {
        "BRUST": ["front_chest_left", "front_chest_right"],
        "SCHULTER_VORN": ["front_delt_left", "front_delt_right"],
        "SCHULTER_SEIT": ["front_delt_left", "front_delt_right"],  # Approximation
        "SCHULTER_HINT": ["back_delt_left", "back_delt_right"],
        "BIZEPS": ["front_biceps_left", "front_biceps_right"],
        "TRIZEPS": ["back_triceps_left", "back_triceps_right"],
        "UNTERARME": [
            "front_forearm_left",
            "front_forearm_right",
            "back_forearm_left",
            "back_forearm_right",
        ],
        "RUECKEN_LAT": ["back_lat_left", "back_lat_right"],
        "RUECKEN_TRAPEZ": [
            "back_traps_left",
            "back_traps_right",
            "front_traps_left",
            "front_traps_right",
        ],
        "RUECKEN_OBERER": ["back_midback"],
        "RUECKEN_UNTEN": ["back_erectors_left", "back_erectors_right"],
        "BAUCH": [
            "front_abs_upper",
            "front_abs_mid",
            "front_abs_lower",
            "front_oblique_left",
            "front_oblique_right",
        ],
        "BEINE_QUAD": ["front_quad_left", "front_quad_right"],
        "BEINE_HAM": ["back_hamstring_left", "back_hamstring_right"],
        "PO": ["back_glute_left", "back_glute_right"],
        "WADEN": ["front_calf_left", "front_calf_right", "back_calf_left", "back_calf_right"],
        "ADDUKTOREN": ["front_adductor_left", "front_adductor_right"],
        "ABDUKTOREN": [],  # Nicht direkt in SVG dargestellt
        "GANZKOERPER": [],
    }

    context = {
        "uebungen": uebungen,
        "selected_group": selected_group,
        "group_label": group_label,
        "muscle_mapping": json.dumps(muscle_mapping),
        "muskelgruppen": MUSKELGRUPPEN,
    }
    return render(request, "core/muscle_map.html", context)


@login_required
def uebung_detail(request: HttpRequest, uebung_id: int) -> HttpResponse:
    """Detail-Ansicht einer Übung mit anatomischer Visualisierung"""
    uebung = get_object_or_404(Uebung, id=uebung_id)

    # Mapping: Muskelgruppe -> SVG-IDs
    muscle_mapping = {
        "BRUST": ["front_chest_left", "front_chest_right"],
        "SCHULTER_VORN": ["front_delt_left", "front_delt_right"],
        "SCHULTER_SEIT": ["front_delt_left", "front_delt_right"],
        "SCHULTER_HINT": ["back_delt_left", "back_delt_right"],
        "BIZEPS": ["front_biceps_left", "front_biceps_right"],
        "TRIZEPS": ["back_triceps_left", "back_triceps_right"],
        "UNTERARME": [
            "front_forearm_left",
            "front_forearm_right",
            "back_forearm_left",
            "back_forearm_right",
        ],
        "RUECKEN_LAT": ["back_lat_left", "back_lat_right"],
        "RUECKEN_TRAPEZ": [
            "back_traps_left",
            "back_traps_right",
            "front_traps_left",
            "front_traps_right",
        ],
        "RUECKEN_OBERER": ["back_midback"],
        "RUECKEN_UNTEN": ["back_erectors_left", "back_erectors_right"],
        "BAUCH": [
            "front_abs_upper",
            "front_abs_mid",
            "front_abs_lower",
            "front_oblique_left",
            "front_oblique_right",
        ],
        "BEINE_QUAD": ["front_quad_left", "front_quad_right"],
        "BEINE_HAM": ["back_hamstring_left", "back_hamstring_right"],
        "PO": ["back_glute_left", "back_glute_right"],
        "WADEN": ["front_calf_left", "front_calf_right", "back_calf_left", "back_calf_right"],
        "ADDUKTOREN": ["front_adductor_left", "front_adductor_right"],
        "ABDUKTOREN": [],
        "GANZKOERPER": [],
    }

    # SVG-IDs für Hauptmuskel (rot)
    main_muscle_ids = muscle_mapping.get(uebung.muskelgruppe, [])

    # SVG-IDs für Hilfsmuskeln (blau)
    helper_muscle_ids = []
    if uebung.hilfsmuskeln:
        # hilfsmuskeln ist ein JSON-Array mit Muskelgruppen-Codes
        if isinstance(uebung.hilfsmuskeln, str):
            hilfs_codes = [h.strip() for h in uebung.hilfsmuskeln.split(",")]
        else:
            hilfs_codes = uebung.hilfsmuskeln

        for code in hilfs_codes:
            # Code ist bereits im Format 'BIZEPS', 'BAUCH' etc.
            # Direkt im muscle_mapping nachschlagen
            if code in muscle_mapping:
                helper_muscle_ids.extend(muscle_mapping.get(code, []))

    # Statistiken zur Übung
    alle_saetze = Satz.objects.filter(
        einheit__user=request.user, uebung=uebung, ist_aufwaermsatz=False
    )
    max_gewicht = alle_saetze.aggregate(Max("gewicht"))["gewicht__max"] or 0
    total_volumen = sum(float(s.gewicht) * s.wiederholungen for s in alle_saetze)

    context = {
        "uebung": uebung,
        "main_muscle_ids": json.dumps(main_muscle_ids),
        "helper_muscle_ids": json.dumps(helper_muscle_ids),
        "max_gewicht": max_gewicht,
        "total_volumen": round(total_volumen, 1),
        "anzahl_saetze": alle_saetze.count(),
    }
    return render(request, "core/uebung_detail.html", context)


def _compute_1rm_for_satz(satz, gewichts_typ: str) -> tuple[float, float, float]:
    """Berechnet (effektives_gewicht, one_rep_max, volumen_beitrag) für einen Satz."""
    effektives_gewicht = float(satz.gewicht) if satz.gewicht else 0.0
    if gewichts_typ == "PRO_SEITE":
        effektives_gewicht *= 2

    if gewichts_typ == "ZEIT":
        one_rep_max = float(satz.wiederholungen)
    elif effektives_gewicht > 0:
        one_rep_max = effektives_gewicht * (1 + (satz.wiederholungen / 30))
    else:
        one_rep_max = 0.0

    volumen = (
        float(satz.gewicht) * satz.wiederholungen if satz.gewicht and satz.wiederholungen else 0.0
    )
    return effektives_gewicht, one_rep_max, volumen


def _calc_1rm_stats(saetze, uebung) -> dict:
    """Berechnet 1RM-Verlauf, Bestleistungen und Gesamtvolumen aus Satz-QS.

    Returns:
        Dict mit keys: history_data, personal_record, best_weight,
        total_volume, total_sets.
    """
    history_data: dict[str, float] = {}
    personal_record = 0.0
    best_weight = 0.0
    total_volume = 0.0
    total_sets = saetze.count()

    for satz in saetze:
        eff_gewicht, one_rm, vol = _compute_1rm_for_satz(satz, uebung.gewichts_typ)
        datum_str = satz.einheit.datum.strftime("%d.%m.%Y")
        if datum_str not in history_data or one_rm > history_data[datum_str]:
            history_data[datum_str] = round(one_rm, 1)
        if one_rm > personal_record:
            personal_record = round(one_rm, 1)
        if eff_gewicht > best_weight:
            best_weight = eff_gewicht
        total_volume += vol

    return {
        "history_data": history_data,
        "personal_record": personal_record,
        "best_weight": best_weight,
        "total_volume": total_volume,
        "total_sets": total_sets,
    }


def _calc_rpe_trend(saetze, avg_rpe: float) -> str | None:
    """Berechnet RPE-Trend (improving / stable / declining) aus zwei 4-Wochen-Fenstern.

    Returns None wenn nicht genug Daten vorhanden.
    """
    heute = timezone.now()
    vier_wochen_alt = heute - timedelta(days=28)
    acht_wochen_alt = heute - timedelta(days=56)

    recent_rpe = saetze.filter(einheit__datum__gte=vier_wochen_alt).aggregate(Avg("rpe"))[
        "rpe__avg"
    ]
    older_rpe = saetze.filter(
        einheit__datum__gte=acht_wochen_alt, einheit__datum__lt=vier_wochen_alt
    ).aggregate(Avg("rpe"))["rpe__avg"]

    if not recent_rpe or not older_rpe:
        return None

    diff = recent_rpe - older_rpe
    if diff < -0.3:
        return "improving"
    if diff > 0.3:
        return "declining"
    return "stable"


@login_required
def exercise_detail(request: HttpRequest, uebung_id: int) -> HttpResponse:
    """Kombinierte Übungs-Detailansicht: Beschreibung, Muskelgruppen-Visualisierung, Statistiken."""
    uebung = get_object_or_404(Uebung.objects.prefetch_related("equipment"), id=uebung_id)

    # User-spezifische Sätze
    saetze = (
        Satz.objects.filter(einheit__user=request.user, uebung=uebung, ist_aufwaermsatz=False)
        .select_related("einheit")
        .order_by("einheit__datum")
    )

    has_data = saetze.exists()

    context = {
        "uebung": uebung,
        "has_data": has_data,
    }

    if has_data:
        stats = _calc_1rm_stats(saetze, uebung)
        history_data = stats["history_data"]

        avg_rpe = saetze.aggregate(Avg("rpe"))["rpe__avg"]
        avg_rpe_display = round(avg_rpe, 1) if avg_rpe else None
        rpe_trend = _calc_rpe_trend(saetze, avg_rpe) if avg_rpe else None

        letztes_training = saetze.last().einheit if saetze.exists() else None

        context.update(
            {
                "labels_json": json.dumps(list(history_data.keys())),
                "data_json": json.dumps(list(history_data.values())),
                "personal_record": stats["personal_record"],
                "best_weight": stats["best_weight"],
                "avg_rpe": avg_rpe_display,
                "rpe_trend": rpe_trend,
                "total_volume": round(stats["total_volume"], 0),
                "total_sets": stats["total_sets"],
                "letztes_training": letztes_training,
            }
        )

    return render(request, "core/exercise_detail.html", context)


@login_required
def toggle_favorite(request: HttpRequest, uebung_id: int) -> JsonResponse:
    """Toggle Favoriten-Status einer Übung."""
    uebung = get_object_or_404(Uebung, id=uebung_id)

    if request.user in uebung.favoriten.all():
        uebung.favoriten.remove(request.user)
        is_favorite = False
    else:
        uebung.favoriten.add(request.user)
        is_favorite = True

    return JsonResponse({"is_favorite": is_favorite})


@login_required
def toggle_favorit(request: HttpRequest, uebung_id: int) -> JsonResponse:
    """
    Toggle Favorit-Status einer Übung für den aktuellen User.
    Returns: JSON mit {'is_favorit': bool, 'message': str}
    """
    uebung = get_object_or_404(Uebung, id=uebung_id)

    # Toggle: Favorit hinzufügen oder entfernen
    if request.user in uebung.favoriten.all():
        uebung.favoriten.remove(request.user)
        is_favorit = False
        message = f'"{uebung.bezeichnung}" aus Favoriten entfernt'
    else:
        uebung.favoriten.add(request.user)
        is_favorit = True
        message = f'"{uebung.bezeichnung}" zu Favoriten hinzugefügt'

    return JsonResponse({"is_favorit": is_favorit, "message": message})


def _score_movement_muscle_match(exercise, original) -> tuple[int, list[str]]:
    """Berechnet Basis-Score für Bewegungstyp/Muskelgruppe-Übereinstimmung."""
    score = 0
    reasons: list[str] = []
    if (
        exercise.bewegungstyp == original.bewegungstyp
        and exercise.muskelgruppe == original.muskelgruppe
    ):
        score += 100
        reasons.append("Gleicher Bewegungstyp & Muskelgruppe")
    else:
        if exercise.bewegungstyp == original.bewegungstyp:
            score += 50
            reasons.append("Gleicher Bewegungstyp")
        if exercise.muskelgruppe == original.muskelgruppe:
            score += 40
            reasons.append("Gleiche Hauptmuskelgruppe")
    return score, reasons


def _score_alternative_exercise(
    exercise, original, user_equipment_ids: set
) -> tuple[int, list[str]] | None:
    """Bewertet eine Übung als Alternative zu `original`.

    Returns:
        (score, match_reasons) wenn score >= 40, sonst None.
        None auch wenn benötigtes Equipment nicht verfügbar.
    """
    required_eq_ids = set(exercise.equipment.values_list("id", flat=True))
    if required_eq_ids and not required_eq_ids.issubset(user_equipment_ids):
        return None

    score, match_reasons = _score_movement_muscle_match(exercise, original)

    if original.hilfsmuskeln and exercise.hilfsmuskeln:
        original_hilfs = (
            set(original.hilfsmuskeln) if isinstance(original.hilfsmuskeln, list) else set()
        )
        exercise_hilfs = (
            set(exercise.hilfsmuskeln) if isinstance(exercise.hilfsmuskeln, list) else set()
        )
        common = original_hilfs & exercise_hilfs
        if common:
            score += 10 * len(common)
            match_reasons.append(f"{len(common)} gemeinsame Hilfsmuskeln")

    return None if score < 40 else (score, match_reasons)


@login_required
def get_alternative_exercises(request: HttpRequest, uebung_id: int) -> JsonResponse:
    """
    API Endpoint: Gibt alternative Übungen zurück basierend auf:
    - Gleicher Bewegungstyp (Compound/Isolation)
    - Gleiche Hauptmuskelgruppe
    - Verfügbares Equipment des Users

    Scoring-System:
    - Exakte Übereinstimmung (bewegungstyp + muskelgruppe): 100 Punkte
    - Nur bewegungstyp: 50 Punkte
    - Nur muskelgruppe: 40 Punkte
    - Hilfsmuskel stimmt überein: +10 Punkte
    """
    original = get_object_or_404(Uebung, id=uebung_id)
    user_equipment_ids = set(request.user.verfuegbares_equipment.values_list("id", flat=True))

    all_exercises = (
        Uebung.objects.filter(Q(is_custom=False) | Q(created_by=request.user))
        .exclude(id=original.id)
        .prefetch_related("equipment")
    )

    alternatives = []
    for exercise in all_exercises:
        result = _score_alternative_exercise(exercise, original, user_equipment_ids)
        if result is None:
            continue
        score, match_reasons = result
        alternatives.append(
            {
                "id": exercise.id,
                "bezeichnung": exercise.bezeichnung,
                "muskelgruppe": exercise.muskelgruppe,
                "muskelgruppe_label": dict(MUSKELGRUPPEN).get(
                    exercise.muskelgruppe, exercise.muskelgruppe
                ),
                "bewegungstyp": exercise.get_bewegungstyp_display(),
                "gewichts_typ": exercise.get_gewichts_typ_display(),
                "is_custom": exercise.is_custom,
                "score": score,
                "match_reasons": match_reasons,
            }
        )

    alternatives.sort(key=lambda x: x["score"], reverse=True)
    alternatives = alternatives[:10]

    return JsonResponse(
        {
            "success": True,
            "original": {
                "id": original.id,
                "bezeichnung": original.bezeichnung,
                "muskelgruppe_label": dict(MUSKELGRUPPEN).get(
                    original.muskelgruppe, original.muskelgruppe
                ),
                "bewegungstyp": original.get_bewegungstyp_display(),
            },
            "alternatives": alternatives,
            "count": len(alternatives),
        }
    )


@login_required
def suggest_alternative_exercises(request: HttpRequest, exercise_id: int) -> JsonResponse:
    """
    Schlägt alternative Übungen vor basierend auf:
    - Gleiche Muskelgruppe
    - Verfügbares Equipment
    - Ähnlicher Bewegungstyp
    """
    original_exercise = get_object_or_404(Uebung, id=exercise_id)
    user_equipment_ids = set(request.user.verfuegbares_equipment.values_list("id", flat=True))

    # Alternative finden
    alternatives = Uebung.objects.filter(
        muskelgruppe=original_exercise.muskelgruppe, is_custom=False
    ).exclude(id=original_exercise.id)

    # Filter nach verfügbarem Equipment
    available_alternatives = []
    for alt in alternatives:
        required_eq = set(alt.equipment.values_list("id", flat=True))
        if not required_eq or required_eq.issubset(user_equipment_ids):
            # Score berechnen für Sortierung
            score = 0
            if alt.bewegungstyp == original_exercise.bewegungstyp:
                score += 10
            if set(alt.hilfsmuskeln) & set(
                original_exercise.hilfsmuskeln if original_exercise.hilfsmuskeln else []
            ):
                score += 5
            available_alternatives.append({"exercise": alt, "score": score})

    # Sortieren nach Score
    available_alternatives.sort(key=lambda x: x["score"], reverse=True)

    # Top 5
    top_alternatives = [item["exercise"] for item in available_alternatives[:5]]

    return JsonResponse(
        {
            "original": {
                "id": original_exercise.id,
                "name": original_exercise.bezeichnung,
                "muscle": original_exercise.get_muskelgruppe_display(),
            },
            "alternatives": [
                {
                    "id": alt.id,
                    "name": alt.bezeichnung,
                    "muscle": alt.get_muskelgruppe_display(),
                    "movement": alt.get_bewegungstyp_display(),
                    "equipment": [eq.get_name_display() for eq in alt.equipment.all()],
                }
                for alt in top_alternatives
            ],
        }
    )


def _resolve_display(code: str | None, mapping: dict, fallback: str = "") -> str:
    """Gibt Display-Namen zurück oder fallback wenn code None/leer."""
    return mapping.get(code, code) if code else fallback


def _build_exercise_api_data(uebung) -> dict:
    """Serialisiert eine Übung als JSON-Dict für den API-Endpoint."""
    muskelgruppen_dict = dict(MUSKELGRUPPEN)
    bewegungstyp_dict = dict(BEWEGUNGS_TYP)
    gewichts_typ_dict = dict(GEWICHTS_TYP)

    hilfsmuskeln_display = (
        [muskelgruppen_dict.get(m, m) for m in uebung.hilfsmuskeln] if uebung.hilfsmuskeln else []
    )
    equipment_list = [eq.get_name_display() for eq in uebung.equipment.all()]

    return {
        "id": uebung.id,
        "bezeichnung": uebung.bezeichnung,
        "beschreibung": uebung.beschreibung or "Keine Beschreibung verfügbar",
        "bild": uebung.bild.url if uebung.bild else None,
        "muskelgruppe": uebung.muskelgruppe or "",
        "muskelgruppe_display": _resolve_display(uebung.muskelgruppe, muskelgruppen_dict, "-"),
        "bewegungstyp": uebung.bewegungstyp or "",
        "bewegungstyp_display": _resolve_display(uebung.bewegungstyp, bewegungstyp_dict),
        "gewichts_typ": uebung.gewichts_typ or "",
        "gewichts_typ_display": _resolve_display(uebung.gewichts_typ, gewichts_typ_dict, "-"),
        "hilfsmuskeln": uebung.hilfsmuskeln or [],
        "hilfsmuskeln_display": hilfsmuskeln_display,
        "equipment": equipment_list,
    }


@login_required
def exercise_api_detail(request: HttpRequest, exercise_id: int) -> JsonResponse:
    """API Endpoint für Übungsdetails (für Modal). Gibt JSON mit allen Übungsinformationen zurück."""
    try:
        uebung = get_object_or_404(Uebung, id=exercise_id)
        return JsonResponse(_build_exercise_api_data(uebung))
    except Exception as e:
        logger.error(f"Exercise API Detail Error: {e}", exc_info=True)
        return JsonResponse(
            {
                "error": "Übungsdetails konnten nicht abgerufen werden. Bitte später erneut versuchen."
            },
            status=500,
        )
