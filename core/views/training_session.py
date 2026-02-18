"""
Module for core training session execution and set management.

Handles training session workflows including:
- Selection and display of training plans
- Starting training sessions with pre-configured exercises
- Managing individual sets during training (add, update, delete)
- Finishing training sessions with summary statistics and AI suggestions
"""

import json
import logging
import re
from collections import OrderedDict
from typing import Any, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, DecimalField, F, Max, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Plan, Satz, Trainingseinheit, Uebung, UserProfile

logger = logging.getLogger(__name__)


def _build_plan_gruppen(
    plaene, active_group_id: str | None
) -> tuple[OrderedDict, OrderedDict, list]:
    """Teilt Pläne in aktive Gruppe, andere Gruppen und einzelne Pläne auf.

    Returns:
        (active_plan_gruppen, plan_gruppen, einzelne_plaene)
    """
    active_plan_gruppen: OrderedDict = OrderedDict()
    plan_gruppen: OrderedDict = OrderedDict()
    einzelne_plaene: list = []

    for plan in plaene:
        if plan.gruppe_id:
            gruppe_key = str(plan.gruppe_id)
            target = active_plan_gruppen if gruppe_key == active_group_id else plan_gruppen
            if gruppe_key not in target:
                target[gruppe_key] = {"name": plan.gruppe_name or "Unbenannte Gruppe", "plaene": []}
            target[gruppe_key]["plaene"].append(plan)
        else:
            einzelne_plaene.append(plan)

    return active_plan_gruppen, plan_gruppen, einzelne_plaene


@login_required
def training_select_plan(request: HttpRequest) -> HttpResponse:
    """Zeigt alle verfügbaren Pläne zur Auswahl an. Priorisiert aktive Plan-Gruppe."""
    filter_type = request.GET.get("filter", "eigene")

    if filter_type == "public":
        plaene = (
            Plan.objects.filter(is_public=True)
            .exclude(user=request.user)
            .order_by("gruppe_name", "gruppe_reihenfolge", "name")
        )
    elif filter_type == "shared":
        plaene = request.user.shared_plans.all().order_by(
            "gruppe_name", "gruppe_reihenfolge", "name"
        )
    else:
        plaene = Plan.objects.filter(user=request.user).order_by(
            "gruppe_name", "gruppe_reihenfolge", "name"
        )

    active_group_id = None
    active_group_name = None
    try:
        profile = request.user.profile
        if profile.active_plan_group:
            active_group_id = str(profile.active_plan_group)
            active_group_plan = Plan.objects.filter(
                user=request.user, gruppe_id=profile.active_plan_group
            ).first()
            if active_group_plan:
                active_group_name = active_group_plan.gruppe_name or "Unbenannte Gruppe"
            else:
                active_group_id = None
    except UserProfile.DoesNotExist:
        pass

    active_plan_gruppen, plan_gruppen, einzelne_plaene = _build_plan_gruppen(
        plaene, active_group_id
    )

    context = {
        "plaene": plaene,
        "active_plan_gruppen": active_plan_gruppen,
        "active_group_name": active_group_name,
        "plan_gruppen": plan_gruppen,
        "einzelne_plaene": einzelne_plaene,
        "filter_type": filter_type,
        "shared_count": request.user.shared_plans.count(),
    }
    return render(request, "core/training_select_plan.html", context)


@login_required
def plan_details(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Zeigt Details eines Trainingsplans mit allen Übungen."""
    # Zugriff auf: eigene Pläne, öffentliche Pläne, oder mit mir geteilte Pläne
    plan = get_object_or_404(
        Plan, Q(user=request.user) | Q(is_public=True) | Q(shared_with=request.user), id=plan_id
    )

    # Prüfe ob User der Owner ist
    is_owner = plan.user == request.user
    plan_uebungen = plan.uebungen.select_related("uebung").order_by("reihenfolge")

    # Batch-Query: letzte Sätze für alle Übungen im Plan auf einmal laden (verhindert N+1)
    uebung_ids = [pu.uebung_id for pu in plan_uebungen]
    letzte_saetze_qs = Satz.objects.filter(
        uebung_id__in=uebung_ids, ist_aufwaermsatz=False
    ).order_by("-einheit__datum", "-satz_nr")
    letzte_saetze_map: dict[int, Satz] = {}
    for satz in letzte_saetze_qs:
        if satz.uebung_id not in letzte_saetze_map:
            letzte_saetze_map[satz.uebung_id] = satz

    # Für jede Übung das letzte verwendete Gewicht holen (für Vorschau)
    uebungen_mit_historie = []
    for plan_uebung in plan_uebungen:
        letzter_satz = letzte_saetze_map.get(plan_uebung.uebung_id)
        uebungen_mit_historie.append(
            {
                "plan_uebung": plan_uebung,
                "letztes_gewicht": letzter_satz.gewicht if letzter_satz else None,
                "letzte_wdh": letzter_satz.wiederholungen if letzter_satz else None,
            }
        )

    context = {
        "plan": plan,
        "uebungen_mit_historie": uebungen_mit_historie,
        "is_owner": is_owner,
    }
    return render(request, "core/plan_details.html", context)


def _get_deload_config(user, plan) -> tuple[bool, float, float, float]:
    """Liest Deload-Konfiguration aus dem UserProfile.

    Returns:
        (is_deload, vol_factor, weight_factor, rpe_target)
    """
    try:
        profile = user.profile
        if (
            profile.active_plan_group
            and plan.gruppe_id
            and str(plan.gruppe_id) == str(profile.active_plan_group)
        ):
            if not profile.cycle_start_date:
                profile.cycle_start_date = timezone.now().date()
                profile.save()
            return (
                profile.is_deload_week(),
                profile.deload_volume_factor,
                profile.deload_weight_factor,
                profile.deload_rpe_target,
            )
    except UserProfile.DoesNotExist:
        pass
    return False, 0.8, 0.9, 7.0


def _create_ghost_saetze(
    training, plan, is_deload: bool, deload_vol_factor: float, deload_weight_factor: float
) -> None:
    """Erstellt Platzhalter-Sätze aus dem Plan mit Ghosting und optionalen Deload-Anpassungen."""
    plan_uebungen = list(plan.uebungen.select_related("uebung").order_by("reihenfolge"))
    uebung_ids_ghost = [pu.uebung_id for pu in plan_uebungen]

    # Batch-Query: letzte Arbeitssätze aller Übungen auf einmal laden (verhindert N+1)
    letzte_saetze_qs = Satz.objects.filter(
        einheit__user=training.user,
        uebung_id__in=uebung_ids_ghost,
        ist_aufwaermsatz=False,
    ).order_by("-einheit__datum", "-satz_nr")
    letzte_saetze_ghost: dict[int, Any] = {}
    for satz in letzte_saetze_qs:
        if satz.uebung_id not in letzte_saetze_ghost:
            letzte_saetze_ghost[satz.uebung_id] = satz

    for plan_uebung in plan_uebungen:
        uebung = plan_uebung.uebung
        letzter_satz = letzte_saetze_ghost.get(uebung.id)
        start_gewicht = letzter_satz.gewicht if letzter_satz else 0
        start_wdh = 0

        ziel_text = plan_uebung.wiederholungen_ziel
        match = re.search(r"\d{1,4}", str(ziel_text)) if ziel_text else None
        if match:
            start_wdh = int(match.group())
        elif letzter_satz:
            start_wdh = letzter_satz.wiederholungen

        anzahl_saetze = plan_uebung.saetze_ziel
        if is_deload:
            anzahl_saetze = max(2, int(anzahl_saetze * deload_vol_factor))
            start_gewicht = round(float(start_gewicht) * deload_weight_factor, 1)

        for i in range(1, anzahl_saetze + 1):
            Satz.objects.create(
                einheit=training,
                uebung=uebung,
                satz_nr=i,
                gewicht=start_gewicht,
                wiederholungen=start_wdh,
                ist_aufwaermsatz=False,
                superset_gruppe=plan_uebung.superset_gruppe,
            )


@login_required
def training_start(request: HttpRequest, plan_id: Optional[int] = None) -> HttpResponse:
    """Startet Training. Wenn plan_id da ist, werden Übungen vor-angelegt."""
    training = Trainingseinheit.objects.create(user=request.user)

    if plan_id:
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        training.plan = plan
        training.save()

        is_deload, deload_vol_factor, deload_weight_factor, deload_rpe_target = _get_deload_config(
            request.user, plan
        )
        _create_ghost_saetze(training, plan, is_deload, deload_vol_factor, deload_weight_factor)

        if is_deload:
            vol_pct = int((1 - deload_vol_factor) * 100)
            weight_pct = int((1 - deload_weight_factor) * 100)
            messages.info(
                request,
                f"Deload-Woche: Volumen -{vol_pct}%, Gewicht -{weight_pct}% automatisch reduziert. Ziel-RPE: {deload_rpe_target}",
            )

    return redirect("training_session", training_id=training.id)


def _get_sorted_saetze(training):
    """Sortiert Sätze nach Plan-Reihenfolge oder alphabetisch nach Übungsname."""
    if training.plan:
        plan_reihenfolge = {pu.uebung_id: pu.reihenfolge for pu in training.plan.uebungen.all()}
        return sorted(
            training.saetze.select_related("uebung").all(),
            key=lambda s: (plan_reihenfolge.get(s.uebung_id, 999), s.satz_nr),
        )
    return training.saetze.select_related("uebung").all().order_by("uebung__bezeichnung", "satz_nr")


def _get_plan_ziele(training):
    """Gibt Satz- und Wiederholungsziele aus dem Plan zurück (leer wenn kein Plan)."""
    plan_ziele = {}
    if training.plan:
        for pu in training.plan.uebungen.all():
            plan_ziele[pu.uebung_id] = {
                "saetze_ziel": pu.saetze_ziel,
                "wiederholungen_ziel": pu.wiederholungen_ziel,
            }
    return plan_ziele


def _parse_ziel_wdh(ziel_wdh_str: str) -> tuple[int, int]:
    """Parst einen Wiederholungs-Zielbereich ('8-12' oder '10') in (min, max)."""
    try:
        if "-" in ziel_wdh_str:
            parts = ziel_wdh_str.split("-")
            return int(parts[0]), int(parts[1])
        val = int(ziel_wdh_str)
        return val, val
    except (ValueError, IndexError):
        return 8, 12


def _calculate_empfohlene_pause(hint: str, plan_pausenzeit) -> int:
    """Berechnet empfohlene Pause in Sekunden basierend auf Progressive-Overload-Hint."""
    if plan_pausenzeit:
        return plan_pausenzeit
    if "+2.5kg" in hint:
        return 180  # 3 Min für Kraftsteigerung
    if "mehr Wdh" in hint:
        return 90  # 90s für Volumen/Ausdauer
    return 120  # 2 Min Standard


def _determine_empfehlung_hint(
    letzter_satz, ziel_wdh_min: int, ziel_wdh_max: int, is_kg_uebung: bool = False
) -> tuple[float, int, str]:
    """Bestimmt Empfehlung basierend auf letztem Satz (RPE/Wdh-Progression).

    Bei Körpergewichts-Übungen ohne Zusatzgewicht wird Wdh-Progression
    empfohlen statt kg-Steigerung (da Gewicht = 0 → +2.5 wäre sinnlos).

    Returns:
        (empfohlenes_gewicht, empfohlene_wdh, hint)
    """
    gewicht = float(letzter_satz.gewicht)
    wdh = letzter_satz.wiederholungen

    # Körpergewichts-Übung ohne Zusatzgewicht: nur Wdh-Progression
    if is_kg_uebung and gewicht == 0:
        if letzter_satz.wiederholungen >= ziel_wdh_max:
            return 0.0, ziel_wdh_min, f"{ziel_wdh_max}+ Wdh → nächste Stufe (Zusatzgewicht?)"
        if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
            return 0.0, min(wdh + 2, ziel_wdh_max), f"RPE {letzter_satz.rpe} → +2 Wdh"
        return 0.0, min(wdh + 1, ziel_wdh_max), f"Ziel: +1 Wdh (aktuell {wdh})"

    if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
        return gewicht + 2.5, wdh, f"RPE {letzter_satz.rpe} → +2.5kg"
    if letzter_satz.wiederholungen >= ziel_wdh_max:
        return gewicht + 2.5, ziel_wdh_min, f"{ziel_wdh_max}+ Wdh → +2.5kg"
    if letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
        return gewicht, min(wdh + 1, ziel_wdh_max), f"RPE {letzter_satz.rpe} → mehr Wdh"
    return gewicht, wdh, "Niveau halten"


def _calculate_single_empfehlung(user, uebung_id: int, training):
    """
    Berechnet Gewichts- und Wiederholungsempfehlung für eine einzelne Übung.
    Gibt None zurück wenn kein Vorsatz vorhanden.

    Hinweis: Für Performance-kritische Pfade (training_session view) bitte
    _get_gewichts_empfehlungen verwenden, welches alle Übungen per Batch lädt.
    """
    letzter_satz = (
        Satz.objects.filter(
            einheit__user=user,
            uebung_id=uebung_id,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .exclude(einheit=training)
        .order_by("-einheit__datum", "-satz_nr")
        .first()
    )
    if not letzter_satz:
        return None

    ziel_wdh_str = "8-12"
    plan_pausenzeit = None

    if training.plan:
        pu = training.plan.uebungen.filter(uebung_id=uebung_id).first()
        if pu and pu.wiederholungen_ziel:
            ziel_wdh_str = pu.wiederholungen_ziel
        if pu and hasattr(pu, "pausenzeit") and pu.pausenzeit:
            plan_pausenzeit = pu.pausenzeit

    ziel_wdh_min, ziel_wdh_max = _parse_ziel_wdh(ziel_wdh_str)

    from core.models import Uebung as UebungModel

    try:
        uebung_obj = UebungModel.objects.get(id=uebung_id)
        is_kg = uebung_obj.gewichts_typ == "KOERPERGEWICHT"
    except UebungModel.DoesNotExist:
        is_kg = False

    empfohlenes_gewicht, empfohlene_wdh, hint = _determine_empfehlung_hint(
        letzter_satz, ziel_wdh_min, ziel_wdh_max, is_kg_uebung=is_kg
    )

    return {
        "gewicht": empfohlenes_gewicht,
        "wdh": empfohlene_wdh,
        "letztes_gewicht": float(letzter_satz.gewicht),
        "letzte_wdh": letzter_satz.wiederholungen,
        "hint": hint,
        "pause": _calculate_empfohlene_pause(hint, plan_pausenzeit),
        "pause_from_plan": bool(plan_pausenzeit),
    }


def _build_empfehlung_from_satz(letzter_satz: Any, plan_pu: Any) -> dict:
    """Baut Empfehlungs-Dict aus vorgeladenem letzten Satz (kein DB-Zugriff)."""
    ziel_wdh_str = "8-12"
    plan_pausenzeit = None
    if plan_pu:
        if plan_pu.wiederholungen_ziel:
            ziel_wdh_str = plan_pu.wiederholungen_ziel
        if hasattr(plan_pu, "pausenzeit") and plan_pu.pausenzeit:
            plan_pausenzeit = plan_pu.pausenzeit

    ziel_wdh_min, ziel_wdh_max = _parse_ziel_wdh(ziel_wdh_str)
    is_kg = (
        plan_pu
        and hasattr(plan_pu, "uebung")
        and getattr(plan_pu.uebung, "gewichts_typ", "") == "KOERPERGEWICHT"
    )
    empfohlenes_gewicht, empfohlene_wdh, hint = _determine_empfehlung_hint(
        letzter_satz, ziel_wdh_min, ziel_wdh_max, is_kg_uebung=bool(is_kg)
    )
    return {
        "gewicht": empfohlenes_gewicht,
        "wdh": empfohlene_wdh,
        "letztes_gewicht": float(letzter_satz.gewicht),
        "letzte_wdh": letzter_satz.wiederholungen,
        "hint": hint,
        "pause": _calculate_empfohlene_pause(hint, plan_pausenzeit),
        "pause_from_plan": bool(plan_pausenzeit),
    }


def _get_gewichts_empfehlungen(user, training) -> dict:
    """Berechnet Gewichtsempfehlungen für alle Übungen im aktuellen Training.

    Verwendet Batch-Queries statt N+1: 2 DB-Zugriffe unabhängig von der Übungsanzahl.
    """
    uebungen_ids = set(training.saetze.values_list("uebung_id", flat=True).distinct())
    if training.plan:
        uebungen_ids.update(training.plan.uebungen.values_list("uebung_id", flat=True))

    if not uebungen_ids:
        return {}

    # Batch-Query 1: letzte nicht-Deload Arbeitssätze für alle Übungen auf einmal
    letzte_saetze_qs = (
        Satz.objects.filter(
            einheit__user=user,
            uebung_id__in=uebungen_ids,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        )
        .exclude(einheit=training)
        .order_by("-einheit__datum", "-satz_nr")
    )
    letzte_saetze_map: dict[int, Any] = {}
    for satz in letzte_saetze_qs:
        if satz.uebung_id not in letzte_saetze_map:
            letzte_saetze_map[satz.uebung_id] = satz

    # Batch-Query 2: PlanUebungen auf einmal laden (pausenzeit & wdh_ziel & uebung.gewichts_typ)
    plan_uebungen_map: dict[int, Any] = {}
    if training.plan:
        for pu in training.plan.uebungen.select_related("uebung").all():
            plan_uebungen_map[pu.uebung_id] = pu

    empfehlungen = {}
    for uebung_id in uebungen_ids:
        letzter_satz = letzte_saetze_map.get(uebung_id)
        if not letzter_satz:
            continue
        empfehlungen[uebung_id] = _build_empfehlung_from_satz(
            letzter_satz, plan_uebungen_map.get(uebung_id)
        )
    return empfehlungen


@login_required
def training_session(request: HttpRequest, training_id: int) -> HttpResponse:
    training = get_object_or_404(
        Trainingseinheit.objects.select_related("plan"),
        id=training_id,
        user=request.user,
    )

    uebungen = Uebung.objects.filter(Q(is_custom=False) | Q(created_by=request.user)).order_by(
        "muskelgruppe", "bezeichnung"
    )
    saetze = _get_sorted_saetze(training)
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    total_volume = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)

    is_deload_week = False
    try:
        profile = request.user.profile
        is_deload_week = profile.is_deload_week()
    except UserProfile.DoesNotExist:
        pass

    context = {
        "training": training,
        "uebungen": uebungen,
        "saetze": saetze,
        "total_volume": round(total_volume, 1),
        "arbeitssaetze_count": arbeitssaetze.count(),
        "plan_ziele": _get_plan_ziele(training),
        "gewichts_empfehlungen": _get_gewichts_empfehlungen(request.user, training),
        "is_deload_week": is_deload_week,
    }
    return render(request, "core/training_session.html", context)


def _check_pr(user, uebung, neuer_satz, gewicht_float: float, wdh_int: int) -> str | None:
    """Prüft ob ein neuer PR erzielt wurde.

    Returns:
        PR-Meldung (str) oder None wenn kein PR.
    """
    current_1rm = gewicht_float * (1 + wdh_int / 30)
    alte_saetze = Satz.objects.filter(
        uebung=uebung,
        ist_aufwaermsatz=False,
        einheit__user=user,
        einheit__ist_deload=False,
    ).exclude(id=neuer_satz.id)

    if alte_saetze.exists():
        max_alter_1rm = max(
            float(s.gewicht) * (1 + int(s.wiederholungen) / 30) for s in alte_saetze
        )
        if current_1rm > max_alter_1rm:
            diff = round(current_1rm - max_alter_1rm, 1)
            return f"🎉 NEUER REKORD! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM) - +{diff} kg!"
    else:
        return f"🏆 Erster Rekord gesetzt! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM)"
    return None


@login_required
def add_set(request: HttpRequest, training_id: int) -> HttpResponse:
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)

    if request.method == "POST":
        uebung_id = request.POST.get("uebung")
        gewicht = request.POST.get("gewicht")
        wdh = request.POST.get("wiederholungen")
        rpe = request.POST.get("rpe")
        is_warmup = request.POST.get("ist_aufwaermsatz") == "on"
        notiz = request.POST.get("notiz", "").strip()
        superset_gruppe = request.POST.get("superset_gruppe", 0)

        uebung = get_object_or_404(Uebung, id=uebung_id)

        # Automatische Satz-Nummerierung
        max_satz = training.saetze.filter(uebung=uebung).aggregate(Max("satz_nr"))["satz_nr__max"]
        neue_nr = (max_satz or 0) + 1

        # Neuen Satz erstellen
        neuer_satz = Satz.objects.create(
            einheit=training,
            uebung=uebung,
            satz_nr=neue_nr,
            gewicht=gewicht,
            wiederholungen=wdh,
            ist_aufwaermsatz=is_warmup,
            rpe=rpe if rpe else None,
            notiz=notiz if notiz else None,
            superset_gruppe=int(superset_gruppe),
        )

        # PR-Check (nur für Arbeitssätze)
        pr_message = None
        if not is_warmup and gewicht and wdh:
            pr_message = _check_pr(request.user, uebung, neuer_satz, float(gewicht), int(wdh))
            if pr_message:
                messages.success(request, pr_message)

        # AJAX Request? Sende JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "satz_id": neuer_satz.id,
                    "pr_message": pr_message,  # Neu: PR-Message für Toast
                }
            )

        return redirect("training_session", training_id=training_id)


@login_required
@require_http_methods(["POST"])
def delete_set(request: HttpRequest, set_id: int) -> HttpResponse:
    """Löscht einen Satz und kehrt zur Liste zurück"""
    # Wir holen den Satz des eingeloggten Nutzers. Wenn er nicht existiert oder nicht dem Nutzer gehört, gibt's einen 404 Fehler.
    satz = get_object_or_404(Satz, id=set_id, einheit__user=request.user)

    # Wir merken uns die Training-ID, bevor wir löschen, damit wir zurückspringen können
    training_id = satz.einheit.id

    satz.delete()

    return redirect("training_session", training_id=training_id)


def _parse_set_post_data(post) -> tuple[float | None, int | None, float | None]:
    """Parst und validiert POST-Felder eines Satz-Updates.

    Returns:
        (gewicht, wiederholungen, rpe) – je None wenn leer/nicht gesetzt

    Raises:
        ValueError: Bei ungültigen oder out-of-range Werten
    """
    gewicht_raw = post.get("gewicht", "").strip()
    wiederholungen_raw = post.get("wiederholungen", "").strip()
    rpe_raw = post.get("rpe", "").strip()

    gewicht = None
    if gewicht_raw:
        gewicht = float(gewicht_raw.replace(",", "."))
        if not 0 <= gewicht <= 1000:
            raise ValueError("Gewicht außerhalb gültiger Bereich (0-1000)")

    wiederholungen = None
    if wiederholungen_raw:
        wiederholungen = int(wiederholungen_raw)
        if not 0 <= wiederholungen <= 999:
            raise ValueError("Wiederholungen außerhalb gültiger Bereich (0-999)")

    rpe = None
    if rpe_raw:
        rpe = float(rpe_raw.replace(",", "."))
        if not 0 <= rpe <= 10:
            raise ValueError("RPE muss zwischen 0 und 10 sein")

    return gewicht, wiederholungen, rpe


@login_required
def update_set(request: HttpRequest, set_id: int) -> HttpResponse:
    """Speichert Änderungen an einem existierenden Satz."""
    try:
        logger.info(f"update_set called for set_id={set_id}, method={request.method}")
        # Ownership-Check: Satz muss zum eingeloggten User gehören (IDOR-Fix)
        satz = get_object_or_404(Satz, id=set_id, einheit__user=request.user)
        training_id = satz.einheit.id

        if request.method == "POST":
            try:
                gewicht, wiederholungen, rpe = _parse_set_post_data(request.POST)
                logger.info(f"Validated - gewicht: {gewicht}, wdh: {wiederholungen}, rpe: {rpe}")

                satz.gewicht = gewicht
                satz.wiederholungen = wiederholungen
                satz.rpe = rpe
                satz.ist_aufwaermsatz = request.POST.get("ist_aufwaermsatz") == "on"
                notiz = request.POST.get("notiz", "").strip()
                satz.notiz = notiz if notiz else None
                superset_raw = request.POST.get("superset_gruppe", "0").strip()
                satz.superset_gruppe = int(superset_raw) if superset_raw else 0
                satz.save()
                logger.info(f"Satz {set_id} saved successfully")

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                return redirect("training_session", training_id=training_id)

            except (ValueError, TypeError) as e:
                logger.error(f"Validation error in update_set: {e}", exc_info=True)
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"success": False, "error": "Ungültige Eingabe"}, status=400
                    )
                return redirect("training_session", training_id=training_id)

        return redirect("training_session", training_id=training_id)

    except Exception as e:
        logger.exception(f"Unexpected error in update_set for set_id={set_id}: {e}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": False,
                    "error": "Ein unerwarteter Serverfehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
                },
                status=500,
            )
        return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def toggle_deload(request: HttpRequest, training_id: int) -> JsonResponse:
    """Setzt oder entfernt den Deload-Status eines Trainings via AJAX."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    try:
        data = json.loads(request.body)
        ist_deload_value = data.get("ist_deload", None)
        if not isinstance(ist_deload_value, bool):
            return JsonResponse(
                {
                    "success": False,
                    "error": 'Ungültiger Wert für "ist_deload". Es wird ein boolescher Wert erwartet.',
                },
                status=400,
            )
        training.ist_deload = ist_deload_value
        training.save(update_fields=["ist_deload"])
        return JsonResponse({"success": True, "ist_deload": training.ist_deload})
    except json.JSONDecodeError as e:
        logger.warning(f"toggle_deload JSON decode error: {e}")
        return JsonResponse(
            {
                "success": False,
                "error": "Die Anfrage konnte nicht verarbeitet werden. Bitte versuchen Sie es erneut.",
            },
            status=400,
        )
    except Exception:
        logger.exception(f"Unexpected error in toggle_deload for training_id={training_id}")
        return JsonResponse(
            {
                "success": False,
                "error": "Ein unerwarteter Serverfehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
            },
            status=500,
        )


def _save_training_post(request, training) -> bool:
    """
    Verarbeitet POST-Daten und speichert Dauer/Kommentar am Training.
    Gibt True zurück wenn erfolgreich gespeichert (Redirect nötig), False bei Fehler.
    """
    dauer_raw = request.POST.get("dauer_minuten")
    kommentar = request.POST.get("kommentar")
    has_error = False

    if dauer_raw:
        try:
            dauer = int(dauer_raw)
        except (TypeError, ValueError):
            messages.error(request, "Bitte eine gültige Trainingsdauer in Minuten angeben.")
            has_error = True
        else:
            if dauer <= 0 or dauer > 1440:
                messages.error(
                    request, "Die Trainingsdauer muss zwischen 1 und 1440 Minuten liegen."
                )
                has_error = True
            else:
                training.dauer_minuten = dauer

    if kommentar:
        training.kommentar = kommentar

    if not has_error:
        training.abgeschlossen = True
        training.save()
        return True
    return False


def _build_intensity_suggestion(avg_rpe: float) -> dict | None:
    """Gibt Intensitäts-Vorschlag zurück oder None."""
    if avg_rpe < 6.5:
        return {
            "type": "intensity",
            "title": "Intensität erhöhen",
            "message": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10",
            "action": "Steigere das Gewicht um 5-10% oder reduziere die Pausenzeit",
            "icon": "bi-arrow-up-circle",
            "color": "info",
        }
    if avg_rpe > 8.5:
        return {
            "type": "intensity",
            "title": "Regeneration priorisieren",
            "message": f"Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10",
            "action": "Reduziere die Intensität oder plane einen Deload",
            "icon": "bi-shield-check",
            "color": "warning",
        }
    return None


def _build_volume_suggestion(user, recent_training_ids: list, recent_sets) -> dict | None:
    """Gibt Volumen-Vorschlag basierend auf Vergleich letzte 3 vs. vorherige 3 Trainings zurück."""
    previous_ids = list(
        Trainingseinheit.objects.filter(user=user, ist_deload=False)
        .order_by("-datum")
        .values_list("id", flat=True)[3:6]
    )

    def _calc_volume(training_ids):
        # Einzelne aggregierte DB-Query statt N+1 (eine Query pro Training)
        result = Satz.objects.filter(einheit_id__in=training_ids, ist_aufwaermsatz=False).aggregate(
            total=Sum(F("gewicht") * F("wiederholungen"), output_field=DecimalField())
        )
        return float(result["total"] or 0)

    recent_vol = _calc_volume(recent_training_ids)
    prev_vol = _calc_volume(previous_ids)
    if not prev_vol:
        return None

    change_pct = ((recent_vol - prev_vol) / prev_vol) * 100
    if change_pct < -15:
        return {
            "type": "volume",
            "title": "Volumen gesunken",
            "message": f"Dein Volumen ist um {abs(change_pct):.0f}% gefallen",
            "action": "Füge 1-2 Sätze pro Übung hinzu oder trainiere häufiger",
            "icon": "bi-graph-down",
            "color": "danger",
        }
    if change_pct > 30:
        return {
            "type": "volume",
            "title": "Volumen stark gestiegen",
            "message": f"Dein Volumen ist um {change_pct:.0f}% gestiegen",
            "action": "Achte auf ausreichend Regeneration zwischen Trainings",
            "icon": "bi-graph-up",
            "color": "warning",
        }
    return None


def _build_ai_suggestions(user, recent_training_ids: list, recent_sets, avg_rpe: float) -> list:
    """Erstellt Trainingsoptimierungsvorschläge basierend auf RPE, Volumen und Vielfalt."""
    suggestions = []

    # Vorschlag 1: Intensität anpassen
    # Vorschlag 1: Intensität
    intensity = _build_intensity_suggestion(avg_rpe)
    if intensity:
        suggestions.append(intensity)

    # Vorschlag 2: Volumen
    volume = _build_volume_suggestion(user, recent_training_ids, recent_sets)
    if volume:
        suggestions.append(volume)

    # Vorschlag 3: Übungsvariation
    trained_exercises = set(recent_sets.values_list("uebung_id", flat=True).distinct())
    if len(trained_exercises) < 5:
        suggestions.append(
            {
                "type": "variety",
                "title": "Mehr Übungsvielfalt",
                "message": f"Du hast nur {len(trained_exercises)} verschiedene Übungen gemacht",
                "action": "Integriere neue Übungen für besseres Muskelwachstum",
                "icon": "bi-shuffle",
                "color": "info",
            }
        )
    return suggestions


def _get_ai_training_suggestion(user) -> tuple:
    """
    Gibt (ai_suggestion, training_count) zurück.
    ai_suggestion ist None wenn kein Vorschlag oder nicht jedes 3. Training.
    """
    training_count = Trainingseinheit.objects.filter(user=user).count()
    if training_count == 0 or training_count % 3 != 0:
        return None, training_count

    recent_training_ids = list(
        Trainingseinheit.objects.filter(user=user, ist_deload=False)
        .order_by("-datum")
        .values_list("id", flat=True)[:3]
    )
    recent_sets = Satz.objects.filter(
        einheit_id__in=recent_training_ids,
        ist_aufwaermsatz=False,
        einheit__ist_deload=False,
        rpe__isnull=False,
    )
    if not recent_sets.exists():
        return None, training_count

    avg_rpe = recent_sets.aggregate(Avg("rpe"))["rpe__avg"]
    suggestions = _build_ai_suggestions(user, recent_training_ids, recent_sets, avg_rpe)

    priority_order = {"danger": 0, "warning": 1, "info": 2}
    ai_suggestion = (
        sorted(suggestions, key=lambda x: priority_order[x["color"]])[0] if suggestions else None
    )
    return ai_suggestion, training_count


@login_required
def finish_training(request: HttpRequest, training_id: int) -> HttpResponse:
    """Zeigt Zusammenfassung und ermöglicht Speichern von Dauer/Kommentar."""
    training = get_object_or_404(
        Trainingseinheit.objects.select_related("plan"),
        id=training_id,
        user=request.user,
    )

    if request.method == "POST":
        if _save_training_post(request, training):
            return redirect("dashboard")

    # Statistiken für die Zusammenfassung berechnen
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    warmup_saetze = training.saetze.filter(ist_aufwaermsatz=True)

    # Volumen berechnen
    total_volume = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)

    # Anzahl Übungen
    uebungen_count = training.saetze.values("uebung").distinct().count()

    # Trainingsdauer schätzen (falls nicht manuell eingegeben)
    if training.datum:
        dauer_geschaetzt = int((timezone.now() - training.datum).total_seconds() / 60)
    else:
        dauer_geschaetzt = 60

    ai_suggestion, training_count = _get_ai_training_suggestion(request.user)

    context = {
        "training": training,
        "arbeitssaetze_count": arbeitssaetze.count(),
        "warmup_saetze_count": warmup_saetze.count(),
        "total_volume": round(total_volume, 1),
        "uebungen_count": uebungen_count,
        "dauer_geschaetzt": dauer_geschaetzt,
        "training_count": training_count,
        "ai_suggestion": ai_suggestion,
    }
    return render(request, "core/training_finish.html", context)
