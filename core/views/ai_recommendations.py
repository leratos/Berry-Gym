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
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..models import MUSKELGRUPPEN, Plan, PlanUebung, Satz, Trainingseinheit, Uebung, UserProfile

logger = logging.getLogger(__name__)


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

    # Zykluslänge aus deload_weeks ableiten
    deload_weeks = plan_data.get("deload_weeks") or []
    if deload_weeks and len(deload_weeks) >= 1:
        # Erste Deload-Woche = Zykluslänge (z.B. [4, 8, 12] → cycle_length = 4)
        profile.cycle_length = max(2, min(12, deload_weeks[0]))

    # Deload-Parameter aus Makrozyklus extrahieren
    macrocycle = plan_data.get("macrocycle") or {}
    weeks = macrocycle.get("weeks") or []
    deload_week_data = [w for w in weeks if w.get("is_deload")]
    if deload_week_data:
        first_deload = deload_week_data[0]
        volume_mult = first_deload.get("volume_multiplier")
        rpe_target = first_deload.get("intensity_target_rpe")
        if volume_mult and 0.5 <= volume_mult <= 1.0:
            profile.deload_volume_factor = volume_mult
        if rpe_target and 5.0 <= rpe_target <= 9.0:
            profile.deload_rpe_target = rpe_target

    # Gewichts-Faktor: Deload-Wochen haben typisch "Volumen -20%, Intensität -10%"
    # Wenn volume_multiplier 0.8 → weight_factor ~0.9
    if profile.deload_volume_factor < 1.0:
        profile.deload_weight_factor = round(1.0 - (1.0 - profile.deload_volume_factor) * 0.5, 2)

    # Zyklus-Start zurücksetzen (wird beim ersten Training neu gesetzt)
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


def _get_muscle_balance_empfehlung(letzte_30_tage_saetze) -> list:
    """Analysiert Muskelgruppen-Balance (RPE-gewichtet) und gibt Empfehlungen zurück."""
    muskelgruppen_stats = {}
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        effektive_wdh = sum(
            s.wiederholungen * (float(s.rpe) / 10.0)
            for s in letzte_30_tage_saetze.filter(uebung__muskelgruppe=gruppe_key)
            if s.wiederholungen and s.rpe
        )
        saetze_anzahl = letzte_30_tage_saetze.filter(uebung__muskelgruppe=gruppe_key).count()
        if effektive_wdh > 0:
            muskelgruppen_stats[gruppe_key] = {
                "name": gruppe_name,
                "effektive_wdh": effektive_wdh,
                "saetze": saetze_anzahl,
            }

    if not muskelgruppen_stats:
        return []

    avg_effektive_wdh = sum(m["effektive_wdh"] for m in muskelgruppen_stats.values()) / len(
        muskelgruppen_stats
    )
    empfehlungen = []
    for gruppe_key, data in muskelgruppen_stats.items():
        if data["effektive_wdh"] < avg_effektive_wdh * 0.5:
            passende_uebungen = Uebung.objects.filter(muskelgruppe=gruppe_key)[:3]
            empfehlungen.append(
                {
                    "typ": "muskelgruppe",
                    "prioritaet": "hoch",
                    "titel": f'{data["name"]} untertrainiert',
                    "beschreibung": (
                        f"Diese Muskelgruppe wurde in den letzten 30 Tagen unterdurchschnittlich trainiert "
                        f'(nur {int(data["effektive_wdh"])} effektive Wiederholungen vs. '
                        f"{int(avg_effektive_wdh)} Durchschnitt)."
                    ),
                    "empfehlung": f'Füge mehr Übungen für {data["name"]} hinzu',
                    "uebungen": [{"id": u.id, "name": u.bezeichnung} for u in passende_uebungen],
                }
            )
    return empfehlungen


def _get_push_pull_empfehlung(letzte_30_tage_saetze) -> list:
    """Analysiert Push/Pull-Balance und gibt Empfehlung zurück."""
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

    if ratio > 1.5:
        return [
            {
                "typ": "balance",
                "prioritaet": "mittel",
                "titel": "Push/Pull Unbalance",
                "beschreibung": (
                    f"Dein Push-Training ({push_saetze} Sätze, {int(push_effektiv)} eff. Wdh) ist "
                    f"{ratio:.1f}x intensiver als dein Pull-Training ({pull_saetze} Sätze, "
                    f"{int(pull_effektiv)} eff. Wdh). Dies kann zu Haltungsschäden führen."
                ),
                "empfehlung": "Mehr Zugübungen (Rücken, Bizeps) trainieren",
                "uebungen": [
                    {"id": u.id, "name": u.bezeichnung}
                    for u in Uebung.objects.filter(muskelgruppe__in=pull_gruppen)[:3]
                ],
            }
        ]
    if ratio < 0.67:
        return [
            {
                "typ": "balance",
                "prioritaet": "mittel",
                "titel": "Push/Pull Unbalance",
                "beschreibung": (
                    f"Dein Pull-Training ({pull_saetze} Sätze, {int(pull_effektiv)} eff. Wdh) ist "
                    f"intensiver als dein Push-Training ({push_saetze} Sätze, {int(push_effektiv)} eff. Wdh)."
                ),
                "empfehlung": "Mehr Druckübungen (Brust, Schultern, Trizeps) einbauen",
                "uebungen": [
                    {"id": u.id, "name": u.bezeichnung}
                    for u in Uebung.objects.filter(muskelgruppe__in=push_gruppen)[:3]
                ],
            }
        ]
    return []


def _get_stagnation_empfehlung(letzte_60_tage_saetze) -> list:
    """Erkennt stagnierende Übungen (kein Fortschritt in 60 Tagen)."""
    uebung_trainings: dict = defaultdict(list)
    for satz in letzte_60_tage_saetze.select_related("uebung", "einheit"):
        if satz.gewicht and satz.gewicht > 0:
            uebung_trainings[satz.uebung_id].append(
                {
                    "datum": satz.einheit.datum,
                    "gewicht": float(satz.gewicht),
                }
            )

    empfehlungen = []
    for uebung_id, saetze_list in uebung_trainings.items():
        trainings_max: dict = defaultdict(float)
        for s in saetze_list:
            trainings_max[s["datum"]] = max(trainings_max[s["datum"]], s["gewicht"])
        max_gewichte = [g for _, g in sorted(trainings_max.items())]

        if len(max_gewichte) < 4:
            continue

        erste = max_gewichte[:2]
        letzte = max_gewichte[-2:]
        avg_erste = sum(erste) / len(erste)
        avg_letzte = sum(letzte) / len(letzte)
        fortschritt = ((avg_letzte - avg_erste) / avg_erste * 100) if avg_erste > 0 else 0

        if fortschritt < 2.5 and len(set(max_gewichte)) == 1:
            uebung = Uebung.objects.get(id=uebung_id)
            empfehlungen.append(
                {
                    "typ": "stagnation",
                    "prioritaet": "niedrig",
                    "titel": f"{uebung.bezeichnung}: Stagnation",
                    "beschreibung": (
                        f"Bei dieser Übung gab es in den letzten {len(max_gewichte)} Trainings "
                        f"keinen Fortschritt (konstant {max_gewichte[-1]} kg)."
                    ),
                    "empfehlung": "Versuche: (1) Deload-Woche, (2) Wiederholungsbereich ändern, (3) Tempo variieren",
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


def _get_rpe_empfehlung(letzte_30_tage_saetze) -> list:
    """Gibt RPE-basierte Intensitätsempfehlung zurück."""
    avg_rpe = letzte_30_tage_saetze.filter(rpe__isnull=False).aggregate(Avg("rpe"))["rpe__avg"]
    if not avg_rpe:
        return []
    if avg_rpe < 6:
        return [
            {
                "typ": "intensitaet",
                "prioritaet": "mittel",
                "titel": "Zu niedrige Trainingsintensität",
                "beschreibung": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}. Das Training könnte intensiver sein.",
                "empfehlung": "Steigere das Gewicht, bis du bei RPE 7-9 trainierst für optimalen Muskelaufbau",
                "uebungen": [],
            }
        ]
    if avg_rpe > 9:
        return [
            {
                "typ": "intensitaet",
                "prioritaet": "hoch",
                "titel": "Zu hohe Trainingsintensität",
                "beschreibung": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}. Du trainierst möglicherweise zu nah am Muskelversagen.",
                "empfehlung": "Reduziere das Gewicht leicht - Deload-Woche empfohlen!",
                "uebungen": [],
            }
        ]
    return []


@login_required
def workout_recommendations(request: HttpRequest) -> HttpResponse:
    """Intelligente Trainingsempfehlungen basierend auf Datenanalyse."""
    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    letzte_60_tage = heute - timedelta(days=60)

    alle_saetze = Satz.objects.filter(einheit__user=request.user, ist_aufwaermsatz=False)
    letzte_30_tage_saetze = alle_saetze.filter(einheit__datum__gte=letzte_30_tage)
    letzte_60_tage_saetze = alle_saetze.filter(einheit__datum__gte=letzte_60_tage)

    empfehlungen = (
        _get_muscle_balance_empfehlung(letzte_30_tage_saetze)
        + _get_push_pull_empfehlung(letzte_30_tage_saetze)
        + _get_stagnation_empfehlung(letzte_60_tage_saetze)
        + _get_frequenz_empfehlung(request.user, heute)
        + _get_rpe_empfehlung(letzte_30_tage_saetze)
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
    }

    return render(request, "core/workout_recommendations.html", context)


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

    try:
        data = json.loads(request.body)

        # Check ob wir einen gecachten Plan speichern sollen
        if data.get("saveCachedPlan") and data.get("plan_data"):
            # Direkt den gecachten Plan speichern ohne neu zu generieren
            from ai_coach.plan_generator import PlanGenerator

            generator = PlanGenerator(
                user_id=request.user.id,
                plan_type="3er-split",  # Dummy, wird nicht genutzt
            )

            plan_data = data["plan_data"]

            # Plan in DB speichern
            plan_ids = generator._save_plan_to_db(plan_data)

            # Mesozyklus-Tracking aus KI-Plan-Daten setzen
            _apply_mesocycle_from_plan(request.user, plan_data, plan_ids)

            return JsonResponse(
                {
                    "success": True,
                    "plan_ids": plan_ids,
                    "plan_name": plan_data.get("plan_name", ""),
                    "sessions": len(plan_data.get("sessions", [])),
                    "message": f"Plan '{plan_data.get('plan_name', '')}' erfolgreich gespeichert!",
                }
            )

        plan_type = data.get("plan_type", "3er-split")
        sets_per_session = int(data.get("sets_per_session", 18))
        analysis_days = int(data.get("analysis_days", 30))
        periodization = data.get("periodization", "linear")
        target_profile = data.get("target_profile", "hypertrophie")
        preview_only = data.get("previewOnly", False)

        # Validierung
        valid_plan_types = ["2er-split", "3er-split", "4er-split", "ganzkörper", "push-pull-legs"]
        if plan_type not in valid_plan_types:
            return JsonResponse(
                {"error": f'Ungültiger Plan-Typ. Erlaubt: {", ".join(valid_plan_types)}'},
                status=400,
            )

        if sets_per_session < 10 or sets_per_session > 30:
            return JsonResponse(
                {"error": "Sätze pro Session muss zwischen 10-30 liegen"}, status=400
            )

        valid_periodizations = ["linear", "wellenfoermig", "block"]
        if periodization not in valid_periodizations:
            periodization = "linear"

        valid_profiles = ["kraft", "hypertrophie", "definition"]
        if target_profile not in valid_profiles:
            target_profile = "hypertrophie"

        # Plan Generator importieren (korrekter Package-Import)
        from ai_coach.plan_generator import PlanGenerator

        # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
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
        )

        if preview_only:
            # Generiere Plan ohne zu speichern für Vorschau
            result = generator.generate(save_to_db=False)
            return JsonResponse(
                {
                    "success": True,
                    "preview": True,
                    "plan_data": result.get("plan_data", {}),
                    "cost": 0.003 if use_openrouter else 0.0,
                    "model": "OpenRouter 70B" if use_openrouter else "Ollama 8B",
                }
            )
        else:
            # Generiere und speichere Plan
            result = generator.generate(save_to_db=True)

            # Mesozyklus-Tracking aus KI-Plan-Daten setzen
            if result.get("success") and result.get("plan_ids"):
                _apply_mesocycle_from_plan(
                    request.user, result.get("plan_data", {}), result.get("plan_ids", [])
                )

            return JsonResponse(
                {
                    "success": True,
                    "plan_ids": result.get("plan_ids", []),
                    "plan_name": result.get("plan_data", {}).get("plan_name", ""),
                    "sessions": len(result.get("plan_data", {}).get("sessions", [])),
                    "cost": 0.003 if use_openrouter else 0.0,
                    "model": "OpenRouter 70B" if use_openrouter else "Ollama 8B",
                    "message": f"Plan '{result.get('plan_data', {}).get('plan_name', '')}' erfolgreich erstellt!",
                }
            )

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
        days = int(request.GET.get("days", 30))

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne analysieren
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)

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

    try:
        from ai_coach.plan_adapter import PlanAdapter

        data = json.loads(request.body)
        plan_id = data.get("plan_id")
        days = int(data.get("days", 30))

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne optimieren
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)

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
        data = json.loads(request.body)
        plan_id = data.get("plan_id")
        optimizations = data.get("optimizations", [])

        if not plan_id:
            return JsonResponse({"error": "plan_id required"}, status=400)

        # Validierung: User darf nur eigene Pläne bearbeiten
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)

        applied_count = 0
        errors = []

        for opt in optimizations:
            try:
                opt_type = opt.get("type")

                if opt_type == "replace_exercise":
                    # Finde die zu ersetzende Übung
                    old_exercise_name = opt.get("old_exercise")
                    new_exercise_name = opt.get("new_exercise")

                    # Hole alte PlanUebung
                    old_plan_uebung = PlanUebung.objects.filter(
                        plan=plan,
                        uebung__bezeichnung__icontains=old_exercise_name.split("(")[0].strip(),
                    ).first()

                    if not old_plan_uebung:
                        errors.append(f"Übung '{old_exercise_name}' nicht im Plan gefunden")
                        continue

                    # Finde neue Übung
                    new_uebung = Uebung.objects.filter(
                        bezeichnung__icontains=new_exercise_name.split("(")[0].strip()
                    ).first()

                    if not new_uebung:
                        errors.append(f"Übung '{new_exercise_name}' nicht gefunden")
                        continue

                    # Ersetze Übung (behalte Sets/Reps/Reihenfolge)
                    old_plan_uebung.uebung = new_uebung
                    old_plan_uebung.save()
                    applied_count += 1

                elif opt_type == "adjust_volume":
                    # Finde Übung und ändere Sets/Reps
                    exercise_name = opt.get("exercise")
                    new_sets = opt.get("new_sets")
                    new_reps = opt.get("new_reps")

                    plan_uebung = PlanUebung.objects.filter(
                        plan=plan,
                        uebung__bezeichnung__icontains=exercise_name.split("(")[0].strip(),
                    ).first()

                    if not plan_uebung:
                        errors.append(f"Übung '{exercise_name}' nicht im Plan gefunden")
                        continue

                    if new_sets:
                        plan_uebung.saetze_ziel = new_sets
                    if new_reps:
                        plan_uebung.wiederholungen_ziel = new_reps
                    plan_uebung.save()
                    applied_count += 1

                elif opt_type == "add_exercise":
                    # Füge neue Übung hinzu
                    exercise_name = opt.get("exercise")
                    sets = opt.get("sets", 3)
                    reps = opt.get("reps", "8-12")

                    # Finde Übung
                    uebung = Uebung.objects.filter(
                        bezeichnung__icontains=exercise_name.split("(")[0].strip()
                    ).first()

                    if not uebung:
                        errors.append(f"Übung '{exercise_name}' nicht gefunden")
                        continue

                    # Füge am Ende des Plans hinzu
                    max_reihenfolge = (
                        PlanUebung.objects.filter(plan=plan).aggregate(Max("reihenfolge"))[
                            "reihenfolge__max"
                        ]
                        or 0
                    )

                    PlanUebung.objects.create(
                        plan=plan,
                        uebung=uebung,
                        reihenfolge=max_reihenfolge + 1,
                        saetze_ziel=sets,
                        wiederholungen_ziel=reps,
                    )
                    applied_count += 1

                elif opt_type == "deload_recommended":
                    # Keine direkte Aktion - nur Info
                    pass

            except Exception as e:
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

    try:
        data = json.loads(request.body)

        session_id = data.get("session_id")
        question = data.get("question", "").strip()
        exercise_id = data.get("exercise_id")
        set_number = data.get("set_number")
        chat_history = data.get("chat_history", [])  # Chat-Historie für Konversationsgedächtnis

        if not session_id or not question:
            return JsonResponse({"error": "session_id und question erforderlich"}, status=400)

        # Prüfe ob Session dem User gehört
        _ = get_object_or_404(Trainingseinheit, id=session_id, user=request.user)

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

    except Trainingseinheit.DoesNotExist:
        return JsonResponse({"error": "Trainingseinheit nicht gefunden"}, status=404)
    except Exception as e:
        logger.error(f"Live Feedback API Error: {e}", exc_info=True)
        return JsonResponse(
            {"error": "Feedback konnte nicht gespeichert werden. Bitte später erneut versuchen."},
            status=500,
        )
