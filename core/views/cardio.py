"""
Cardio Tracking Module

This module contains view functions for tracking cardio activities.
Provides functionality to list, add, and delete cardio sessions.
"""

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import CARDIO_AKTIVITAETEN, CARDIO_INTENSITAET, CardioEinheit


@login_required
def cardio_list(request: HttpRequest) -> HttpResponse:
    """Zeigt alle Cardio-Einheiten des Users (letzte 30 Tage)."""
    # Filter: letzte 30 Tage oder alle
    show_all = request.GET.get("all", False)

    if show_all:
        cardio_einheiten = CardioEinheit.objects.filter(user=request.user)
    else:
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        cardio_einheiten = CardioEinheit.objects.filter(
            user=request.user, datum__gte=thirty_days_ago
        )

    # Statistiken
    total_minuten = sum(c.dauer_minuten for c in cardio_einheiten)
    total_einheiten = cardio_einheiten.count()

    context = {
        "cardio_einheiten": cardio_einheiten,
        "total_minuten": total_minuten,
        "total_einheiten": total_einheiten,
        "show_all": show_all,
    }
    return render(request, "core/cardio_list.html", context)


@login_required
def cardio_add(request: HttpRequest) -> HttpResponse:
    """Fügt eine neue Cardio-Einheit hinzu."""
    if request.method == "POST":
        aktivitaet = request.POST.get("aktivitaet")
        dauer = request.POST.get("dauer_minuten")
        intensitaet = request.POST.get("intensitaet", "MODERAT")
        notiz = request.POST.get("notiz", "")
        datum_str = request.POST.get("datum")

        # Datum parsen
        if datum_str:
            try:
                datum = datetime.strptime(datum_str, "%Y-%m-%d").date()
            except ValueError:
                datum = timezone.now().date()
        else:
            datum = timezone.now().date()

        # Validierung
        if not aktivitaet or not dauer:
            messages.error(request, "Bitte Aktivität und Dauer angeben.")
            return redirect("cardio_add")

        try:
            dauer_int = int(dauer)
            if dauer_int <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Bitte eine gültige Dauer in Minuten angeben.")
            return redirect("cardio_add")

        # Speichern
        CardioEinheit.objects.create(
            user=request.user,
            datum=datum,
            aktivitaet=aktivitaet,
            dauer_minuten=dauer_int,
            intensitaet=intensitaet,
            notiz=notiz[:200] if notiz else "",
        )

        messages.success(
            request,
            f"{dict(CARDIO_AKTIVITAETEN).get(aktivitaet, aktivitaet)} ({dauer_int} Min) hinzugefügt!",
        )
        return redirect("cardio_list")

    # GET: Formular anzeigen
    context = {
        "aktivitaeten": CARDIO_AKTIVITAETEN,
        "intensitaeten": CARDIO_INTENSITAET,
        "heute": timezone.now().date().isoformat(),
    }
    return render(request, "core/cardio_add.html", context)


@login_required
def cardio_delete(request: HttpRequest, cardio_id: int) -> HttpResponse:
    """Löscht eine Cardio-Einheit."""
    cardio = get_object_or_404(CardioEinheit, id=cardio_id, user=request.user)

    if request.method == "POST":
        aktivitaet = cardio.get_aktivitaet_display()
        cardio.delete()
        messages.success(request, f"{aktivitaet} gelöscht.")
        return redirect("cardio_list")

    # GET: Bestätigungs-Seite (oder redirect)
    return redirect("cardio_list")
