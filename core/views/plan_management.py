"""
Plan management views module.

Handles plan CRUD operations (create, read, update, delete), plan sharing,
public/private status management, plan duplication and copying, and the
plan library for browsing public plans and plan groups.
"""

import logging
import uuid
from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import MUSKELGRUPPEN, Plan, PlanUebung, Uebung, UserProfile

logger = logging.getLogger(__name__)


@login_required
def create_plan(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = request.POST.get("name")
        beschreibung = request.POST.get("beschreibung", "")
        is_public = request.POST.get("is_public") == "on"  # Checkbox-Wert
        uebungen_ids = request.POST.getlist("uebungen")  # Liste von Übungs-IDs

        if name and uebungen_ids:
            plan = Plan.objects.create(
                user=request.user, name=name, beschreibung=beschreibung, is_public=is_public
            )

            # Übungen zum Plan hinzufügen
            for idx, uebung_id in enumerate(uebungen_ids, start=1):
                uebung = get_object_or_404(Uebung, id=uebung_id)
                saetze = request.POST.get(f"saetze_{uebung_id}", 3)
                wdh = request.POST.get(f"wdh_{uebung_id}", "8-12")

                PlanUebung.objects.create(
                    plan=plan,
                    uebung=uebung,
                    reihenfolge=idx,
                    saetze_ziel=saetze,
                    wiederholungen_ziel=wdh,
                )

            messages.success(request, f'Trainingsplan "{name}" erfolgreich erstellt!')
            return redirect("plan_details", plan_id=plan.id)

    uebungen = Uebung.objects.all().order_by("muskelgruppe", "bezeichnung")

    # Gruppiere Übungen nach Muskelgruppen für bessere Darstellung
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []

        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            # Sicherstellen dass hilfsmuskeln eine Liste ist
            hilfsmuskeln = uebung.hilfsmuskeln if isinstance(uebung.hilfsmuskeln, list) else []
            for hm in hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))

        uebungen_nach_gruppe[mg_label].append(
            {
                "id": uebung.id,
                "bezeichnung": uebung.bezeichnung,
                "muskelgruppe": uebung.muskelgruppe,
                "muskelgruppe_label": mg_label,
                "hilfsmuskeln": hilfs_labels,
                "gewichts_typ": uebung.get_gewichts_typ_display(),
                "bewegungstyp": uebung.bewegungstyp,  # Für Empfehlungslogik
            }
        )

    context = {
        "uebungen_nach_gruppe": uebungen_nach_gruppe,
        "muskelgruppen": MUSKELGRUPPEN,
    }
    return render(request, "core/create_plan.html", context)


@login_required
def edit_plan(request: HttpRequest, plan_id: int) -> HttpResponse:
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    if request.method == "POST":
        plan.name = request.POST.get("name", plan.name)
        plan.beschreibung = request.POST.get("beschreibung", plan.beschreibung)
        plan.is_public = request.POST.get("is_public") == "on"  # Checkbox-Wert
        plan.save()

        # Lösche alte PlanUebung-Zuordnungen
        PlanUebung.objects.filter(plan=plan).delete()

        # Neue Zuordnungen erstellen
        uebungen_ids = request.POST.getlist("uebungen")
        for idx, uebung_id in enumerate(uebungen_ids, start=1):
            uebung = get_object_or_404(Uebung, id=uebung_id)
            saetze = request.POST.get(f"saetze_{uebung_id}", 3)
            wdh = request.POST.get(f"wdh_{uebung_id}", "8-12")
            superset_gruppe = request.POST.get(f"superset_gruppe_{uebung_id}", 0)
            pausenzeit = int(request.POST.get(f"pause_{uebung_id}", 120))

            PlanUebung.objects.create(
                plan=plan,
                uebung=uebung,
                reihenfolge=idx,
                saetze_ziel=saetze,
                wiederholungen_ziel=wdh,
                superset_gruppe=int(superset_gruppe),
                pausenzeit=pausenzeit,
            )

        messages.success(request, f'Trainingsplan "{plan.name}" erfolgreich aktualisiert!')
        return redirect("plan_details", plan_id=plan.id)

    uebungen = Uebung.objects.all().order_by("muskelgruppe", "bezeichnung")

    # Hole Plan-Übungen mit Details (Reihenfolge, Sets, Reps, Superset)
    plan_uebungen_details = {}
    for pu in plan.uebungen.all():
        plan_uebungen_details[pu.uebung_id] = {
            "reihenfolge": pu.reihenfolge,
            "saetze": pu.saetze_ziel,
            "wdh": pu.wiederholungen_ziel,
            "superset_gruppe": pu.superset_gruppe,
            "pausenzeit": pu.pausenzeit,
        }

    plan_uebung_ids = list(plan_uebungen_details.keys())

    # Gruppiere Übungen nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []

        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            # Sicherstellen dass hilfsmuskeln eine Liste ist
            hilfsmuskeln = uebung.hilfsmuskeln if isinstance(uebung.hilfsmuskeln, list) else []
            for hm in hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))

        uebung_data = {
            "id": uebung.id,
            "bezeichnung": uebung.bezeichnung,
            "muskelgruppe": uebung.muskelgruppe,
            "muskelgruppe_label": mg_label,
            "hilfsmuskeln": hilfs_labels,
            "gewichts_typ": uebung.get_gewichts_typ_display(),
            "bewegungstyp": uebung.bewegungstyp,  # Für Empfehlungslogik
            "in_plan": uebung.id in plan_uebung_ids,
        }

        # Füge Plan-Details hinzu wenn in Plan
        if uebung.id in plan_uebungen_details:
            uebung_data.update(plan_uebungen_details[uebung.id])

        uebungen_nach_gruppe[mg_label].append(uebung_data)

    context = {
        "plan": plan,
        "uebungen_nach_gruppe": uebungen_nach_gruppe,
        "muskelgruppen": MUSKELGRUPPEN,
        "plan_uebungen_details": plan_uebungen_details,  # Für JavaScript
    }
    return render(request, "core/edit_plan.html", context)


@login_required
def delete_plan(request: HttpRequest, plan_id: int) -> HttpResponse:
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    if request.method == "POST":
        name = plan.name
        plan.delete()
        messages.success(request, f'Trainingsplan "{name}" wurde gelöscht.')
        return redirect("training_select_plan")

    return redirect("plan_details", plan_id=plan_id)


@login_required
def copy_plan(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Kopiert einen öffentlichen Plan in die eigenen Pläne."""

    # Plan muss öffentlich sein oder dem User gehören
    original_plan = get_object_or_404(Plan, Q(is_public=True) | Q(user=request.user), id=plan_id)

    # Erstelle Kopie
    new_plan = Plan.objects.create(
        user=request.user,
        name=f"{original_plan.name} (Kopie)",
        beschreibung=original_plan.beschreibung,
        is_public=False,  # Kopien sind standardmäßig privat
    )

    # Kopiere alle Übungen
    for plan_uebung in original_plan.uebungen.all():
        PlanUebung.objects.create(
            plan=new_plan,
            uebung=plan_uebung.uebung,
            reihenfolge=plan_uebung.reihenfolge,
            trainingstag=plan_uebung.trainingstag,
            saetze_ziel=plan_uebung.saetze_ziel,
            wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
            superset_gruppe=plan_uebung.superset_gruppe,
        )

    messages.success(request, f'Plan "{original_plan.name}" wurde in deine Pläne kopiert!')
    return redirect("plan_details", plan_id=new_plan.id)


@login_required
def duplicate_plan(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Dupliziert einen eigenen Plan."""
    original_plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    # Erstelle Kopie
    new_plan = Plan.objects.create(
        user=request.user,
        name=f"{original_plan.name} (Kopie)",
        beschreibung=original_plan.beschreibung,
        is_public=False,  # Duplikate sind standardmäßig privat
    )

    # Kopiere alle Übungen
    for plan_uebung in original_plan.uebungen.all().order_by("reihenfolge"):
        PlanUebung.objects.create(
            plan=new_plan,
            uebung=plan_uebung.uebung,
            reihenfolge=plan_uebung.reihenfolge,
            trainingstag=plan_uebung.trainingstag,
            saetze_ziel=plan_uebung.saetze_ziel,
            wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
            pausenzeit=plan_uebung.pausenzeit,
            superset_gruppe=plan_uebung.superset_gruppe,
        )

    messages.success(request, f'Plan "{original_plan.name}" wurde dupliziert!')
    return redirect("plan_details", plan_id=new_plan.id)


@login_required
def duplicate_group(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Dupliziert eine komplette Plan-Gruppe."""

    # Alle Pläne dieser Gruppe finden
    original_plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).order_by(
        "gruppe_reihenfolge", "name"
    )

    if not original_plans.exists():
        messages.error(request, "Gruppe nicht gefunden.")
        return redirect("training_select_plan")

    # Neue Gruppe-ID erstellen
    new_gruppe_id = uuid.uuid4()

    # Original-Gruppenname mit "(Kopie)" ergänzen
    original_gruppe_name = original_plans.first().gruppe_name or "Gruppe"
    new_gruppe_name = f"{original_gruppe_name} (Kopie)"

    # Alle Pläne der Gruppe kopieren
    for idx, original_plan in enumerate(original_plans):
        new_plan = Plan.objects.create(
            user=request.user,
            name=original_plan.name,
            beschreibung=original_plan.beschreibung,
            is_public=False,
            gruppe_id=new_gruppe_id,
            gruppe_name=new_gruppe_name,
            gruppe_reihenfolge=idx,
        )

        # Übungen kopieren
        for plan_uebung in original_plan.uebungen.all().order_by("reihenfolge"):
            PlanUebung.objects.create(
                plan=new_plan,
                uebung=plan_uebung.uebung,
                reihenfolge=plan_uebung.reihenfolge,
                trainingstag=plan_uebung.trainingstag,
                saetze_ziel=plan_uebung.saetze_ziel,
                wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
                pausenzeit=plan_uebung.pausenzeit,
                superset_gruppe=plan_uebung.superset_gruppe,
            )

    messages.success(
        request,
        f'Gruppe "{original_gruppe_name}" wurde dupliziert ({original_plans.count()} Pläne)!',
    )
    return redirect("training_select_plan")


def share_plan(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Zeigt Sharing-Seite mit QR-Code für einen Plan."""

    plan = get_object_or_404(Plan, Q(is_public=True) | Q(user=request.user), id=plan_id)

    # Prüfe ob User der Owner ist
    is_owner = request.user.is_authenticated and plan.user == request.user

    # Generiere Share-URL
    share_url = request.build_absolute_uri(f"/plan/{plan.id}/")

    # QR-Code als Base64 generieren
    qr_base64 = None
    try:
        import base64
        from io import BytesIO

        import qrcode

        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    except ImportError:
        pass  # QR-Code Package nicht installiert

    context = {
        "plan": plan,
        "share_url": share_url,
        "qr_base64": qr_base64,
        "is_owner": is_owner,
    }
    return render(request, "core/share_plan.html", context)


def share_group(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Zeigt Sharing-Seite mit QR-Code für eine Plan-Gruppe."""

    # Finde alle Pläne dieser Gruppe (öffentlich oder eigene)
    if request.user.is_authenticated:
        plans = Plan.objects.filter(
            Q(is_public=True) | Q(user=request.user), gruppe_id=gruppe_id
        ).order_by("gruppe_reihenfolge", "name")
    else:
        plans = Plan.objects.filter(is_public=True, gruppe_id=gruppe_id).order_by(
            "gruppe_reihenfolge", "name"
        )

    if not plans.exists():
        messages.error(request, "Gruppe nicht gefunden oder nicht zugänglich.")
        return redirect("training_select_plan")

    gruppe_name = plans.first().gruppe_name or "Gruppe"
    is_owner = request.user.is_authenticated and plans.first().user == request.user

    # Generiere Share-URL zur Gruppen-Bibliothek
    share_url = request.build_absolute_uri(f"/plan-library/group/{gruppe_id}/")

    # QR-Code als Base64 generieren
    qr_base64 = None
    try:
        import base64
        from io import BytesIO

        import qrcode

        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    except ImportError:
        # QR-Code-Generierung ist optional: Wenn das 'qrcode'-Paket nicht installiert ist,
        # wird einfach kein QR-Code angezeigt und die Seite funktioniert weiterhin.
        logger.warning("QR code generation skipped because the 'qrcode' package is not installed.")

    context = {
        "plans": plans,
        "gruppe_name": gruppe_name,
        "gruppe_id": gruppe_id,
        "share_url": share_url,
        "qr_base64": qr_base64,
        "is_owner": is_owner,
    }
    return render(request, "core/share_group.html", context)


def plan_library(request: HttpRequest) -> HttpResponse:
    """Öffentliche Plan-Bibliothek - zeigt alle öffentlichen Pläne und Gruppen."""

    # Suchfilter
    search_query = request.GET.get("q", "").strip()

    # Alle öffentlichen Pläne
    public_plans = (
        Plan.objects.filter(is_public=True)
        .select_related("user")
        .order_by("gruppe_name", "gruppe_reihenfolge", "name")
    )

    if search_query:
        public_plans = public_plans.filter(
            models.Q(name__icontains=search_query)
            | models.Q(beschreibung__icontains=search_query)
            | models.Q(gruppe_name__icontains=search_query)
        )

    # Gruppiere nach gruppe_id
    plan_gruppen = OrderedDict()
    einzelne_plaene = []

    for plan in public_plans:
        if plan.gruppe_id:
            gruppe_key = str(plan.gruppe_id)
            if gruppe_key not in plan_gruppen:
                plan_gruppen[gruppe_key] = {
                    "name": plan.gruppe_name or "Unbenannte Gruppe",
                    "plaene": [],
                    "user": plan.user,
                }
            plan_gruppen[gruppe_key]["plaene"].append(plan)
        else:
            einzelne_plaene.append(plan)

    context = {
        "plan_gruppen": plan_gruppen,
        "einzelne_plaene": einzelne_plaene,
        "search_query": search_query,
        "total_count": public_plans.count(),
    }
    return render(request, "core/plan_library.html", context)


def plan_library_group(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Detail-Ansicht einer Plan-Gruppe in der Bibliothek."""
    # Finde alle öffentlichen Pläne dieser Gruppe
    plans = Plan.objects.filter(is_public=True, gruppe_id=gruppe_id).order_by(
        "gruppe_reihenfolge", "name"
    )

    if not plans.exists():
        messages.error(request, "Gruppe nicht gefunden.")
        return redirect("plan_library")

    gruppe_name = plans.first().gruppe_name or "Gruppe"
    owner = plans.first().user

    context = {
        "plans": plans,
        "gruppe_name": gruppe_name,
        "gruppe_id": gruppe_id,
        "owner": owner,
    }
    return render(request, "core/plan_library_group.html", context)


@login_required
def copy_group(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Kopiert eine öffentliche Gruppe in die eigenen Pläne."""

    # Alle öffentlichen Pläne dieser Gruppe finden
    original_plans = Plan.objects.filter(is_public=True, gruppe_id=gruppe_id).order_by(
        "gruppe_reihenfolge", "name"
    )

    if not original_plans.exists():
        messages.error(request, "Gruppe nicht gefunden.")
        return redirect("plan_library")

    # Neue Gruppe-ID erstellen
    new_gruppe_id = uuid.uuid4()

    original_gruppe_name = original_plans.first().gruppe_name or "Gruppe"
    new_gruppe_name = f"{original_gruppe_name} (Kopie)"

    # Alle Pläne kopieren
    for idx, original_plan in enumerate(original_plans):
        new_plan = Plan.objects.create(
            user=request.user,
            name=original_plan.name,
            beschreibung=original_plan.beschreibung,
            is_public=False,
            gruppe_id=new_gruppe_id,
            gruppe_name=new_gruppe_name,
            gruppe_reihenfolge=idx,
        )

        # Übungen kopieren
        for plan_uebung in original_plan.uebungen.all().order_by("reihenfolge"):
            PlanUebung.objects.create(
                plan=new_plan,
                uebung=plan_uebung.uebung,
                reihenfolge=plan_uebung.reihenfolge,
                trainingstag=plan_uebung.trainingstag,
                saetze_ziel=plan_uebung.saetze_ziel,
                wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
                pausenzeit=plan_uebung.pausenzeit,
                superset_gruppe=plan_uebung.superset_gruppe,
            )

    messages.success(
        request,
        f'Gruppe "{original_gruppe_name}" wurde in deine Pläne kopiert ({original_plans.count()} Pläne)!',
    )
    return redirect("training_select_plan")


@login_required
def toggle_plan_public(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Toggle public/private Status eines Plans."""
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    plan.is_public = not plan.is_public
    plan.save()

    status = "öffentlich" if plan.is_public else "privat"
    messages.success(request, f'Plan "{plan.name}" ist jetzt {status}.')
    return redirect("plan_details", plan_id=plan_id)


@login_required
def toggle_group_public(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Toggle public/private Status aller Pläne einer Gruppe."""
    plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)

    if not plans.exists():
        messages.error(request, "Gruppe nicht gefunden.")
        return redirect("training_select_plan")

    # Checke aktuellen Status (alle öffentlich?)
    all_public = all(p.is_public for p in plans)
    new_status = not all_public

    plans.update(is_public=new_status)

    gruppe_name = plans.first().gruppe_name or "Gruppe"
    status = "öffentlich" if new_status else "privat"
    messages.success(request, f'Gruppe "{gruppe_name}" ist jetzt {status}.')
    return redirect("training_select_plan")


def _validate_cycle_params(request: HttpRequest, profile: "UserProfile") -> int:
    """Liest und klemmt Zyklus- und Deload-Parameter aus POST, schreibt auf profile (kein save).

    Returns:
        Validierte Zykluslänge (2–12).
    """
    try:
        cycle_length = max(2, min(12, int(request.POST.get("cycle_length", "4").strip())))
    except (ValueError, TypeError):
        cycle_length = 4
    profile.cycle_length = cycle_length

    _DELOAD_BOUNDS: dict[str, tuple[str, float, float, float]] = {
        "deload_volume_factor": ("deload_volume_factor", 0.5, 1.0, 0.8),
        "deload_weight_factor": ("deload_weight_factor", 0.5, 1.0, 0.9),
        "deload_rpe_target": ("deload_rpe_target", 5.0, 9.0, 7.0),
    }
    for post_key, (attr, lo, hi, _default) in _DELOAD_BOUNDS.items():
        try:
            value = float(request.POST.get(post_key, str(_default)))
            setattr(profile, attr, max(lo, min(hi, value)))
        except (ValueError, TypeError):
            pass

    return cycle_length


def _apply_gruppe_selection(
    request: HttpRequest, profile: "UserProfile", gruppe_id: str, cycle_length: int
) -> None:
    """Setzt aktive Gruppe oder löscht sie; speichert profile; schreibt messages."""
    if gruppe_id:
        plan_exists = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).exists()
        if plan_exists:
            if str(profile.active_plan_group) != gruppe_id:
                profile.cycle_start_date = None
            profile.active_plan_group = gruppe_id

            # Optional: laufende Woche angeben → cycle_start_date rückwärts berechnen
            try:
                current_week = int(request.POST.get("current_week", "0"))
                if 1 <= current_week <= cycle_length:
                    from datetime import timedelta

                    from django.utils import timezone

                    weeks_back = current_week - 1
                    profile.cycle_start_date = (timezone.now() - timedelta(weeks=weeks_back)).date()
            except (ValueError, TypeError):
                pass

            profile.save()
            gruppe_name = (
                Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).first().gruppe_name
                or "Unbenannte Gruppe"
            )
            messages.success(
                request, f"Aktiver Plan gesetzt: {gruppe_name} ({cycle_length} Wochen Zyklus)"
            )
        else:
            messages.error(request, "Plan-Gruppe nicht gefunden!")
    else:
        profile.active_plan_group = None
        profile.cycle_start_date = None
        profile.save()
        messages.success(request, "Aktiver Plan entfernt.")


@login_required
def set_active_plan_group(request: HttpRequest) -> HttpResponse:
    """
    Ermöglicht User die Auswahl einer aktiven Plan-Gruppe.
    GET: Zeigt Liste aller Plan-Gruppen
    POST: Setzt die gewählte Gruppe als aktiv
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        gruppe_id = request.POST.get("gruppe_id", "").strip()
        cycle_length = _validate_cycle_params(request, profile)
        _apply_gruppe_selection(request, profile, gruppe_id, cycle_length)
        return redirect("dashboard")

    # GET: Zeige alle Plan-Gruppen des Users
    plan_gruppen = []
    gruppen_qs = (
        Plan.objects.filter(user=request.user, gruppe_id__isnull=False)
        .values("gruppe_id", "gruppe_name")
        .distinct()
        .order_by("gruppe_name")
    )

    for g in gruppen_qs:
        plan_count = Plan.objects.filter(user=request.user, gruppe_id=g["gruppe_id"]).count()
        plan_gruppen.append(
            {
                "gruppe_id": g["gruppe_id"],
                "name": g["gruppe_name"] or "Unbenannte Gruppe",
                "plan_count": plan_count,
            }
        )

    return render(
        request,
        "core/set_active_plan.html",
        {
            "plan_gruppen": plan_gruppen,
            "current_active": str(profile.active_plan_group) if profile.active_plan_group else None,
            "current_cycle_length": profile.cycle_length,
            "deload_volume_factor": profile.deload_volume_factor,
            "deload_weight_factor": profile.deload_weight_factor,
            "deload_rpe_target": profile.deload_rpe_target,
        },
    )
