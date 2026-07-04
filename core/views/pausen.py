"""Views für Trainingspausen / Ausfallzeiten (Phase 32.2).

Function-based, `@login_required`, strikt user-scoped (IDOR-Schutz über
`get_object_or_404(..., user=request.user)`). Alle Schreibpfade laufen über den
Service `core/services/pausen.py` (transaktionaler Overlap-Schutz, §32.1).

Rückwirkende Eingabe ist der Normalfall. Pause-vs-Pause-Overlap blockt hart
(Service-`ValidationError`); ein Overlap mit Wochen, die bereits Trainings
enthalten, ist legitim (Teilwoche) und erzeugt nur eine nicht-blockende Warnung
(§32.2 / §32.3 Q3).
"""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import Trainingseinheit, TrainingsPause
from ..services.pausen import create_pause, update_pause


def _parse_date(value: str):
    """'YYYY-MM-DD' → date; leerer String → None. Raises ValueError bei Murks."""
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    return str(exc)


def _warn_if_overlaps_sessions(request: HttpRequest, pause: TrainingsPause) -> None:
    """Nicht-blockende Warnung, wenn im Pausen-Zeitraum bereits Trainings liegen."""
    ende = pause.end_datum or timezone.now().date()
    hat_sessions = Trainingseinheit.objects.filter(
        user=request.user,
        datum__date__gte=pause.start_datum,
        datum__date__lte=ende,
    ).exists()
    if hat_sessions:
        messages.warning(
            request,
            _(
                "Hinweis: In diesem Zeitraum sind bereits Trainings erfasst. "
                "Die Pause wurde trotzdem gespeichert."
            ),
        )


def _form_context(values: dict, *, pause=None, is_edit=False) -> dict:
    return {
        "gruende": TrainingsPause.Grund.choices,
        "heute": timezone.now().date().isoformat(),
        "values": values,
        "pause": pause,
        "is_edit": is_edit,
    }


def _values_from_post(request: HttpRequest) -> dict:
    return {
        "start_datum": request.POST.get("start_datum", "").strip(),
        "end_datum": request.POST.get("end_datum", "").strip(),
        "grund": request.POST.get("grund", TrainingsPause.Grund.SONSTIGES),
        "notiz": request.POST.get("notiz", "").strip(),
        "aerztliche_freigabe_noetig": request.POST.get("aerztliche_freigabe_noetig") == "on",
    }


@login_required
def pausen_list(request: HttpRequest) -> HttpResponse:
    """Listet alle Pausen des Users (neueste zuerst)."""
    pausen = TrainingsPause.objects.filter(user=request.user)
    return render(request, "core/pausen_list.html", {"pausen": pausen})


@login_required
def pausen_add(request: HttpRequest) -> HttpResponse:
    """Legt eine neue Pause an (rückwirkend möglich)."""
    if request.method == "POST":
        values = _values_from_post(request)
        try:
            start = _parse_date(values["start_datum"])
            end = _parse_date(values["end_datum"])
            if start is None:
                raise ValidationError(_("Bitte ein Startdatum angeben."))
            pause = create_pause(
                user=request.user,
                start_datum=start,
                end_datum=end,
                grund=values["grund"],
                notiz=values["notiz"],
                aerztliche_freigabe_noetig=values["aerztliche_freigabe_noetig"],
            )
        except (ValidationError, ValueError) as exc:
            messages.error(request, _error_text(exc))
            return render(request, "core/pausen_form.html", _form_context(values))
        _warn_if_overlaps_sessions(request, pause)
        messages.success(request, _("Pause gespeichert."))
        return redirect("pausen_list")

    return render(request, "core/pausen_form.html", _form_context(None))


@login_required
def pausen_edit(request: HttpRequest, pause_id: int) -> HttpResponse:
    """Bearbeitet eine bestehende Pause des Users."""
    pause = get_object_or_404(TrainingsPause, id=pause_id, user=request.user)

    if request.method == "POST":
        values = _values_from_post(request)
        try:
            start = _parse_date(values["start_datum"])
            end = _parse_date(values["end_datum"])
            if start is None:
                raise ValidationError(_("Bitte ein Startdatum angeben."))
            update_pause(
                pause,
                start_datum=start,
                end_datum=end,
                grund=values["grund"],
                notiz=values["notiz"],
                aerztliche_freigabe_noetig=values["aerztliche_freigabe_noetig"],
            )
        except (ValidationError, ValueError) as exc:
            messages.error(request, _error_text(exc))
            return render(
                request,
                "core/pausen_form.html",
                _form_context(values, pause=pause, is_edit=True),
            )
        _warn_if_overlaps_sessions(request, pause)
        messages.success(request, _("Pause aktualisiert."))
        return redirect("pausen_list")

    values = {
        "start_datum": pause.start_datum.isoformat(),
        "end_datum": pause.end_datum.isoformat() if pause.end_datum else "",
        "grund": pause.grund,
        "notiz": pause.notiz,
        "aerztliche_freigabe_noetig": pause.aerztliche_freigabe_noetig,
    }
    return render(
        request, "core/pausen_form.html", _form_context(values, pause=pause, is_edit=True)
    )


@login_required
def pausen_delete(request: HttpRequest, pause_id: int) -> HttpResponse:
    """Löscht eine Pause des Users (POST)."""
    pause = get_object_or_404(TrainingsPause, id=pause_id, user=request.user)
    if request.method == "POST":
        pause.delete()
        messages.success(request, _("Pause gelöscht."))
    return redirect("pausen_list")
